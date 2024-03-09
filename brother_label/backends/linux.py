#!/usr/bin/env python

"""
Backend to support Brother QL-series printers via the linux kernel USB printer interface.
Works on Linux.
"""

from __future__ import unicode_literals

import re
import subprocess
import shutil
import os
import select
import time
import logging
from builtins import str

from brother_label.backends.generic import DeviceInfo, BrotherQLBackendGeneric

logger = logging.getLogger(__name__)


RE_LP = re.compile("^lp[0-9]+$")
RE_DEVICE = re.compile("^(QL-[a-zA-Z0-9]+|PT-[a-zA-Z0-9])$")


class BrotherQLBackendLinux(BrotherQLBackendGeneric):
    """
    BrotherQL backend using the Linux Kernel USB Printer Device Handles
    """

    def __init__(self, device_specifier):
        """
        device_specifier: string or os.open(): identifier in the \
            format file:///dev/usb/lp0 or os.open() raw device handle.
        """
        self.read_timeout = 0.01
        # strategy : try_twice or select
        self.strategy = "select"
        if isinstance(device_specifier, str):
            if device_specifier.startswith("file://"):
                device_specifier = device_specifier[7:]
            self.dev = os.open(device_specifier, os.O_RDWR)
        elif isinstance(device_specifier, int):
            self.dev = device_specifier
        else:
            raise ValueError(
                "Currently the printer can be specified either via an "
                "appropriate string or via an os.open() handle."
            )

        self.write_dev = self.dev
        self.read_dev = self.dev

    def _write(self, data):
        os.write(self.write_dev, data)

    def _read(self, length=32):
        if self.strategy == "try_twice":
            data = os.read(self.read_dev, length)
            if data:
                return data
            else:
                time.sleep(self.read_timeout)
                return os.read(self.read_dev, length)
        elif self.strategy == "select":
            data = b""
            start = time.time()
            while (not data) and (time.time() - start < self.read_timeout):
                result, _, _ = select.select([self.read_dev], [], [], 0)
                if self.read_dev in result:
                    data += os.read(self.read_dev, length)
                if data:
                    break
                time.sleep(0.001)
            if not data:
                # one last try if still no data:
                return os.read(self.read_dev, length)
            else:
                return data
        else:
            raise NotImplementedError("Unknown strategy")

    def _dispose(self):
        os.close(self.dev)

    @staticmethod
    def discover() -> list[DeviceInfo]:
        # Abort if the "/dev/usb/" directory does not exist; we're most likely
        # not on Linux if that is the case.
        if not os.path.isdir("/dev/usb/"):
            return []

        # If the directory exists, search for all files starting with "lp...".
        # Use the `udevadm` executable to obtain more information about the
        # device.
        exe_udevadm = None
        res: list[DeviceInfo] = []
        for lp_file in os.listdir(os.path.join(os.sep, "dev", "usb")):
            if RE_LP.match(lp_file) is None:
                continue

            # Use udevadm to resolve the `lpX` device to the corresponding USB
            # device path
            if exe_udevadm is None:
                exe_udevadm = shutil.which("udevadm")
                if not exe_udevadm:
                    logger.warning(
                        "Cannot find `udevadm` executable; device "
                        "list may be incomplete"
                    )
                    return []
            lp_path = os.path.join(os.sep, "dev", "usb", lp_file)
            udevadm_output = subprocess.check_output(
                [exe_udevadm, "info", "--query=property", f"--name={lp_path}"],
                encoding="ascii",
            )
            device_path = None
            for res_line in udevadm_output.splitlines():
                if res_line.startswith("DEVPATH="):
                    device_path = res_line.split("DEVPATH=", 1)[1]
                    break
            if device_path is None:
                logger.warning(
                    "`DEVPATH` key not found in the udevadm output "
                    f"for {lp_path}. Skipping."
                )
                continue

            # Go three levels up from the device path to reach the USB device
            # (level 0: device file, level -1: driver, level -2: usb endpoint,
            #  level -3: usb device).
            device_path = os.path.normpath(
                os.path.join(os.sep, "sys", device_path[1:], "..", "..", "..")
            )

            # Read various sysfs files containing the information we need
            device_info = DeviceInfo(
                backend="linux_kernel",
                device_specifier=f"file://{lp_path}",
            )
            sysfs_file_to_info_map = {
                "idProduct": ("usb_product_id", True, str),
                "idVendor": ("usb_vendor_id", True, str),
                "busnum": ("usb_bus_num", True, int),
                "devnum": ("usb_dev_num", True, int),
                "manufacturer": ("manufacturer", False, str),
                "product": ("device", False, str),
                "serial": ("serial", False, str),
            }
            for sysfs_file, (key, req, type_) in sysfs_file_to_info_map.items():
                fn = os.path.join(device_path, sysfs_file)
                if not os.path.isfile(fn):
                    if not req:
                        continue
                    logger.warning(
                        f"Expected sysfs file {fn!r} for {lp_path!r} "
                        f"does not exist. Skipping."
                    )
                    continue
                with open(fn, "r", encoding="utf-8") as f:
                    try:
                        setattr(device_info, key, type_(f.read().strip()))
                    except ValueError:
                        logger.warning(f"Error while parsing {fn!r}")

            logger.debug(f"Extracted device info {lp_path!r}: {device_info!r}")
            res.append(device_info)

        return res


if __name__ == "__main__":
    print(BrotherQLBackendLinux.discover())
