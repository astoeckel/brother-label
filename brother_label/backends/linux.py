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
Backend to support Brother QL-series printers via the linux kernel USB printer
interface. Works on Linux.
"""

from __future__ import unicode_literals

import logging
import os
import re
import select
import shutil
import subprocess
import time
import typing
from builtins import str

from brother_label.backends.base import BackendBase, DeviceInfo

logger = logging.getLogger(__name__)

RE_LP = re.compile("^lp[0-9]+$")
RE_DEVICE = re.compile("^(QL-[a-zA-Z0-9]+|PT-[a-zA-Z0-9])$")


class BackendLinux(BackendBase):
    """
    BrotherQL backend using the Linux Kernel USB Printer Device Handles
    """

    def __init__(self, device_url: str):
        """
        `device_url` is a URL of the form lp:///dev/usb/lp0
        """
        super().__init__(device_url)
        self._dev = None
        self._read_timeout_s: float = 10e-3

    ###########################################################################
    # Protected functions                                                     #
    ###########################################################################

    def _do_open(self):
        self._dev = os.open(self.device_url_to_file(self.device_url), os.O_RDWR)

    def _do_close(self):
        os.close(self._dev)
        self._dev = None

    def _do_write(self, data):
        os.write(self._dev, data)

    def _do_read(self, length=32):
        data = b""
        start = time.time()
        while (not data) and (time.time() - start < self._read_timeout_s):
            result, _, _ = select.select([self._dev], [], [], 0)
            if self._dev in result:
                data += os.read(self._dev, length)
            if data:
                break
            time.sleep(0.001)
        if not data:
            # one last try if still no data:
            return os.read(self._dev, length)
        else:
            return data

    ###########################################################################
    # Protected functions                                                     #
    ###########################################################################

    @staticmethod
    def device_url_to_file(device_url: str):
        if device_url.startswith("lp://"):
            device_url = device_url[5:]
        if RE_LP.match(device_url) is not None:
            device_url = f"/dev/usb/{device_url}"
        if not os.path.exists(device_url):
            raise FileNotFoundError(device_url)
        return os.path.normpath(device_url)

    @staticmethod
    def discover(device_url: typing.Optional[str] = None) -> list[DeviceInfo]:
        # Abort if the "/dev/usb/" directory does not exist; we're most likely
        # not on Linux if that is the case.
        if not os.path.isdir("/dev/usb/"):
            return []

        # If a specific device URL is given, then try to get information about
        # that one device; otherwise try to find all devices.
        if device_url:
            lp_files = [BackendLinux.device_url_to_file(device_url)]
        else:
            lp_files = [
                f
                for f in os.listdir(os.path.join(os.sep, "dev", "usb"))
                if RE_LP.match(f)
            ]

        # If the directory exists, search for all files starting with "lp...".
        # Use the `udevadm` executable to obtain more information about the
        # device.
        exe_udevadm = None
        res: list[DeviceInfo] = []
        for lp_file in lp_files:
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
                backend="linux",
                device_url=f"lp://{lp_path}",
            )
            sysfs_file_to_info_map = {
                "idProduct": ("usb_product_id", True, str),
                "idVendor": ("usb_vendor_id", True, str),
                "busnum": ("usb_bus_num", True, int),
                "devnum": ("usb_dev_num", True, int),
                "manufacturer": ("manufacturer", False, str),
                "product": ("model", False, str),
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
