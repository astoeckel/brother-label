#!/usr/bin/env python

"""
Backend to support Brother QL-series printers via PyUSB.
Works on Mac OS X and Linux.

Requires PyUSB: https://github.com/walac/pyusb/
Install via `pip install pyusb`
"""

from __future__ import unicode_literals

import os.path
import time
import typing
import logging
import select

import usb.core
import usb.util

from brother_label.backends.generic import DeviceInfo, BrotherQLBackendGeneric

logger = logging.getLogger(__name__)

###############################################################################
# Device discovery routines                                                   #
###############################################################################

USB_VENDOR_ID = 0x04F9
USB_PRINTER_CLASS = 0x7


def _fill_in_device_info_backend(device_info: DeviceInfo):
    if device_info.serial:
        device_info.device_specifier = \
            f"usb://0x{device_info.usb_vendor_id}:" \
            f"0x{device_info.usb_product_id}/{device_info.serial}"
    else:
        device_info.device_specifier = \
            f"usb://0x{device_info.usb_vendor_id}:" \
            f"0x{device_info.usb_product_id}"


def _discover_linux_sysfs() -> list[DeviceInfo]:
    """
    Linux specific discovery function. If this method works, then we can access
    all relevant information about the USB device without requiring special
    privileges.
    """

    # Abort if the Linux sysfs does not exist; most likely because this is
    # not Linux.
    sysfs_root = os.path.join(os.sep, "sys", "bus", "usb", "devices")
    if not os.path.isdir(sysfs_root):
        return []

    # Iterate over all devices listed by the Linux USB subsystem sysfs
    res: list[DeviceInfo] = []
    for dev_dirname in sorted(os.listdir(sysfs_root)):
        # Only consider files devices that have an "idVendor" file
        dev_path = os.path.join(sysfs_root, dev_dirname)
        dev_vendor_id_fn = os.path.join(dev_path, "idVendor")
        dev_product_id_fn = os.path.join(dev_path, "idProduct")
        if not (
            os.path.isfile(dev_vendor_id_fn)
            and os.path.isfile(dev_product_id_fn)
        ):
            continue

        # Try to read the vendor ID
        def read_hex_id(fn) -> typing.Optional[int]:
            with open(fn, "r", encoding="ascii") as f:
                try:
                    return int(f.read(), 16)
                except ValueError:
                    logger.warning(f"Cannot parse {fn!r}")
                    return None

        # Read the vendor and product ID
        vendor_id = read_hex_id(dev_vendor_id_fn)
        product_id = read_hex_id(dev_product_id_fn)
        if (vendor_id != USB_VENDOR_ID) or (product_id is None):
            logger.debug(
                f"Skipping {dev_path!r} because the vendor does not match"
            )
            continue

        # Determine whether this is a printer: that is, either the device is
        # directly marked as a printer, or one of its endpoints is marked as
        # a printer.
        is_printer = False
        for root, _, files in os.walk(dev_path):
            for class_file in ("bDeviceClass", "bInterfaceClass"):
                if class_file not in files:
                    continue
                class_file = os.path.join(root, class_file)
                if read_hex_id(class_file) == USB_PRINTER_CLASS:
                    logger.debug(
                        f"USB device {dev_path!r} is a printer according to "
                        f"{class_file!r}"
                    )
                    is_printer = True
                    break
        if not is_printer:
            logger.debug(f"Skipping {dev_path!r} because it is not a printer")
            continue

        # Perfect, now gather more device information by reading from the sysfs.
        device_info = DeviceInfo(
            backend="pyusb",
            usb_vendor_id=f"{vendor_id:04x}",
            usb_product_id=f"{product_id:04x}",
        )
        sysfs_file_to_info_map = {
            "busnum": ("usb_bus_num", True, int),
            "devnum": ("usb_dev_num", True, int),
            "manufacturer": ("manufacturer", False, str),
            "product": ("device", False, str),
            "serial": ("serial", False, str),
        }
        for sysfs_file, (key, req, type_) in sysfs_file_to_info_map.items():
            fn = os.path.join(dev_path, sysfs_file)
            if not os.path.isfile(fn):
                if not req:
                    continue
                logger.warning(
                    f"Expected sysfs file {fn!r} for {dev_path!r} "
                    f"does not exist. Skipping."
                )
                continue
            with open(fn, "r", encoding="utf-8") as f:
                try:
                    setattr(device_info, key, type_(f.read().strip()))
                except ValueError:
                    logger.warning(f"Error while parsing {fn!r}")

        # Finally, assemble the device specifier and append the device info
        # to the result list
        _fill_in_device_info_backend(device_info)
        res.append(device_info)

    return res


def _discover_pyusb() -> list[DeviceInfo]:
    """
    Generic pyusb function. This should work on all supported platforms, but
    (on Linux) may not be able to access all information about the printer that
    we would optimally like to access.
    """

    # Filter factory for a callback that checks whether either the given device
    # itself, or any of its endpoints is of the specified USB class
    def filter_usb_class(usb_class: int):
        def callback(dev):
            if dev.bDeviceClass == usb_class:
                return True
            for cfg in dev:
                intf = usb.util.find_descriptor(
                    cfg, bInterfaceClass=usb_class
                )
                if intf is not None:
                    return True
            return False

        return callback

    # List all Brother printers
    printers = usb.core.find(
        find_all=1,
        custom_match=filter_usb_class(USB_PRINTER_CLASS),
        idVendor=USB_VENDOR_ID,
    )

    # Create the `DeviceInfo` structures
    res = []
    for printer in printers:
        # Fill in some basic information
        device_info = DeviceInfo(
            backend="pyusb",
            usb_bus_num=printer.bus,
            usb_dev_num=printer.address,
            usb_vendor_id=f"{printer.idVendor:04x}",
            usb_product_id=f"{printer.idProduct:04x}",
            handle=printer,
        )

        # Attempt to read more detailed information about the device
        try:
            device_info.serial = printer.serial_number
            device_info.product = printer.product
            device_info.manufacturer = printer.manufacturer
        except ValueError:
            logging.debug(f"Error accessing detailed info for {printer!r}")

        # Finally, assemble the device specifier and append the device info
        # to the result list
        _fill_in_device_info_backend(device_info)
        res.append(device_info)

    return res


###############################################################################
# Actual USB device driver                                                    #
###############################################################################

class BrotherQLBackendPyUSB(BrotherQLBackendGeneric):
    """
    BrotherQL backend using PyUSB
    """

    def __init__(self, device_specifier):
        """
        device_specifier: string or pyusb.core.Device: identifier of the \
            format usb://idVendor:idProduct/iSerialNumber or pyusb.core.Device instance.
        """

        self.dev = None
        self.read_timeout = 10.0  # ms
        self.write_timeout = 15000.0  # ms
        # strategy : try_twice or select
        self.strategy = "try_twice"
        if isinstance(device_specifier, str):
            if device_specifier.startswith("usb://"):
                device_specifier = device_specifier[6:]
            vendor_product, _, serial = device_specifier.partition("/")
            vendor, _, product = vendor_product.partition(":")
            vendor, product = int(vendor, 16), int(product, 16)
            for result in list_available_devices():
                printer = result["instance"]
                if (
                    printer.idVendor == vendor
                    and printer.idProduct == product
                    or (serial and printer.iSerialNumber == serial)
                ):
                    self.dev = printer
                    break
            if self.dev is None:
                raise ValueError("Device not found")
        elif isinstance(device_specifier, usb.core.Device):
            self.dev = device_specifier
        else:
            raise NotImplementedError(
                "Currently the printer can be specified either via an appropriate string or via a usb.core.Device instance."
            )

        # Now we are sure to have self.dev around, start using it:

        try:
            assert self.dev.is_kernel_driver_active(0)
            self.dev.detach_kernel_driver(0)
            self.was_kernel_driver_active = True
        except (NotImplementedError, AssertionError):
            self.was_kernel_driver_active = False

        # set the active configuration. With no arguments, the first configuration will be the active one
        self.dev.set_configuration()

        cfg = self.dev.get_active_configuration()
        intf = usb.util.find_descriptor(cfg, bInterfaceClass=7)
        assert intf is not None

        ep_match_in = (
            lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
                      == usb.util.ENDPOINT_IN
        )
        ep_match_out = (
            lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
                      == usb.util.ENDPOINT_OUT
        )

        ep_in = usb.util.find_descriptor(intf, custom_match=ep_match_in)
        ep_out = usb.util.find_descriptor(intf, custom_match=ep_match_out)

        assert ep_in is not None
        assert ep_out is not None

        self.write_dev = ep_out
        self.read_dev = ep_in

    def _raw_read(self, length):
        # pyusb Device.read() operations return array() type - let's convert it to bytes()
        return bytes(self.read_dev.read(length))

    def _read(self, length=32):
        if self.strategy == "try_twice":
            data = self._raw_read(length)
            if data:
                return bytes(data)
            else:
                time.sleep(self.read_timeout / 1000.0)
                return self._raw_read(length)
        elif self.strategy == "select":
            data = b""
            start = time.time()
            while (not data) and (
                time.time() - start < self.read_timeout / 1000.0
            ):
                result, _, _ = select.select([self.read_dev], [], [], 0)
                if self.read_dev in result:
                    data += self._raw_read(length)
                if data:
                    break
                time.sleep(0.001)
            if not data:
                # one last try if still no data:
                return self._raw_read(length)
            else:
                return data
        else:
            raise NotImplementedError("Unknown strategy")

    def _write(self, data):
        self.write_dev.write(data, int(self.write_timeout))

    def _dispose(self):
        usb.util.dispose_resources(self.dev)
        del self.write_dev, self.read_dev
        if self.was_kernel_driver_active:
            self.dev.attach_kernel_driver(0)
        del self.dev

    @staticmethod
    def discover() -> list[DeviceInfo]:
        # Try both the "Linux sysfs" and "pyusb" method to discover attached
        # devices
        device_infos = [
            *_discover_linux_sysfs(),
            *_discover_pyusb(),
        ]

        # Now deduplicate the DeviceInfo entries; use the one with the most
        # information
        device_map: dict[str, DeviceInfo] = {}
        for info in device_infos:
            # Use the bus and device number to disambiguate USB devices
            key = f"{info.usb_bus_num}:{info.usb_dev_num}"

            # Do nothing if we only have one instance of the device info
            if key not in device_map:
                device_map[key] = info
                continue

            # Merge the two dictionaries
            for dkey, dvalue in info.__dict__.items():
                if not getattr(device_map[key], dkey):
                    setattr(device_map[key], dkey, dvalue)

        return list(device_map.values())


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print(BrotherQLBackendPyUSB.discover())
