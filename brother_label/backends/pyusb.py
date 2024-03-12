# Brother Label Printer User-Space Driver and Printing Utility
# Copyright (C) 2015-2024  Philipp Klaus, Dean Gardiner, Andreas Stöckel
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Backend to support Brother QL-series printers via PyUSB.
Works on Mac OS X and Linux.

Requires PyUSB: https://github.com/walac/pyusb/
Install via `pip install pyusb`
"""

from __future__ import unicode_literals

import logging
import os
import re
import time
import typing

import usb.core
import usb.util

from brother_label.backends.base import BackendBase, DeviceInfo
from brother_label.exceptions import BrotherQLError

logger = logging.getLogger(__name__)

###############################################################################
# Device discovery routines                                                   #
###############################################################################

RE_DEVICE_SPECIFIER = re.compile(
    r"^(usb://)?0x([0-9A-Fa-f]{4}):0x([0-9A-Fa-f]{4})(/([A-Za-z0-9]+)?)?$"
)

USB_VENDOR_ID = 0x04F9
USB_PRINTER_CLASS = 0x7


def _fill_in_device_info_backend(device_info: DeviceInfo):
    if device_info.serial:
        device_info.device_url = (
            f"usb://0x{device_info.usb_vendor_id}:"
            f"0x{device_info.usb_product_id}/{device_info.serial}"
        )
    else:
        device_info.device_url = (
            f"usb://0x{device_info.usb_vendor_id}:"
            f"0x{device_info.usb_product_id}"
        )


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
                f"Skipping {dev_path!r} because the vendor ID does not match"
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
            "product": ("model", False, str),
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
                intf = usb.util.find_descriptor(cfg, bInterfaceClass=usb_class)
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


class BackendPyUSB(BackendBase):
    """
    BrotherQL backend using PyUSB
    """

    def __init__(self, device_url: str):
        """
        Initializes the PyUSB printer backend. Supports device URLs of the
        following form:

        ```
        [usb://]0xVENDOR_ID:0xPRODUCT_ID[/SERIAL]
        ```
        """
        super().__init__(device_url)
        self._usb_device = None
        self._usb_ep_in = None
        self._usb_ep_out = None
        self._read_timeout_ms: int = 10
        self._write_timeout_ms: int = 15000
        self._was_kernel_driver_active: bool = True

    ###########################################################################
    # Protected functions                                                     #
    ###########################################################################

    def _do_open(self):
        # Fetch the underlying USB device
        self._usb_device = self.device_url_to_usb_device(self.device_url)

        # Now we are sure to have self.dev around, start using it:
        try:
            assert self._usb_device.is_kernel_driver_active(0)
            self._usb_device.detach_kernel_driver(0)
            self._was_kernel_driver_active = True
        except (NotImplementedError, AssertionError):
            self._was_kernel_driver_active = False

        # Set the active configuration. With no arguments, the first
        # configuration will be the active one.
        self._usb_device.set_configuration()

        # Find the printer endpoints
        cfg = self._usb_device.get_active_configuration()
        intf = usb.util.find_descriptor(cfg, bInterfaceClass=USB_PRINTER_CLASS)
        if intf is None:
            raise BrotherQLError(
                f"Cannot find a printer endpoint for {self._device_url}"
            )

        ep_match_in = (
            lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_IN
        )
        ep_match_out = (
            lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_OUT
        )
        self._usb_ep_in = usb.util.find_descriptor(
            intf, custom_match=ep_match_in
        )
        self._usb_ep_out = usb.util.find_descriptor(
            intf, custom_match=ep_match_out
        )
        if (self._usb_ep_in is None) or (self._usb_ep_out is None):
            raise BrotherQLError(
                f"Error getting input/output endpoints for {self._device_url}"
            )

    def _do_close(self):
        usb.util.dispose_resources(self._usb_device)
        del self._usb_ep_out
        del self._usb_ep_in
        if self._was_kernel_driver_active:
            self._usb_device.attach_kernel_driver(0)
        del self._usb_device

        self._usb_device = None
        self._usb_ep_out = None
        self._usb_ep_in = None

    def _raw_read(self, length):
        return bytes(self._usb_ep_in.read(length))

    def _do_read(self, length):
        data = self._raw_read(length)
        if data:
            return bytes(data)
        else:
            time.sleep(self._read_timeout_ms / 1000.0)
            return self._raw_read(length)

    def _do_write(self, data):
        self._usb_ep_out.write(data, self._write_timeout_ms)

    ###########################################################################
    # Static methods                                                          #
    ###########################################################################

    @staticmethod
    def discover(device_url: typing.Optional[str] = None) -> list[DeviceInfo]:
        # If a URL is given, then we first need to parse that and then match
        # it against all discovered devices.
        if device_url:
            return list(BackendPyUSB.device_url_to_device_infos(device_url))

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

    @staticmethod
    def parse_device_url(device_specifier: str):
        vendor_id, product_id, serial_id = None, None, None
        if (match := RE_DEVICE_SPECIFIER.match(device_specifier)) is not None:
            vendor_id = match.groups()[1]
            product_id = match.groups()[2]
            serial_id = match.groups()[4]
        return vendor_id.lower(), product_id.lower(), serial_id

    @classmethod
    def device_url_to_device_infos(
        cls, device_url: str
    ) -> typing.Iterable[DeviceInfo]:
        vendor_id, product_id, serial_id = cls.parse_device_url(device_url)
        for device_info in cls.discover():
            if vendor_id and (device_info.usb_vendor_id != vendor_id):
                continue
            if product_id and (device_info.usb_product_id != product_id):
                continue
            if serial_id and (device_info.serial != serial_id):
                continue
            yield device_info

    @classmethod
    def device_url_to_usb_device(cls, device_url: str) -> usb.core.Device:
        printer: typing.Optional[usb.core.Device] = None
        for device_info in cls.device_url_to_device_infos(device_url):
            if printer:
                logger.warning(
                    f"Multiple printers match {device_url!r}, "
                    f"using first one!"
                )
            else:
                assert isinstance(device_info.handle, usb.core.Device)
                printer = device_info.handle

        if printer is None:
            raise BrotherQLError(f"Cannot find printer {device_url!r}!")

        return printer
