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

import logging
import typing
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    backend: str = ""
    """
    Name of the backend that should be used to access this device.
    """

    manufacturer: str = ""
    """
    Manufacturer of the device (e.g., 'Brother').
    """

    model: str = ""
    """
    Model name of the device (e.g., 'QL-600').
    """

    serial: str = ""
    """
    Serial number of the device.
    """

    usb_product_id: str = ""
    """
    Four-digit hex representation of the USB product ID associated with the
    device.
    """

    usb_vendor_id: str = ""
    """
    Four-digit hex representation of the USB vendor ID associated with the
    device.
    """

    usb_bus_num: int = -1
    """
    USB bus number of the device (if the device is a USB device).
    """

    usb_dev_num: int = -1
    """
    USB device number (if the device is a USB device).
    """

    device_url: str = ""
    """
    URL can be passed to the specified backend to instantiate the file.
    """

    handle: object = None
    """
    Backend-specific handle.
    """

    supported: bool = False
    """
    Flag indicating whether the device is supported by us. This is filled in
    by the CLI code.
    """

    priority: int = 0
    """
    Sort-order of the device if the CLI has to choose between devices.
    """


class BackendBase(object):
    def __init__(self, device_url: typing.Optional[str]):
        self._device_url = device_url
        self._is_open = False

    @property
    def device_url(self) -> typing.Optional[str]:
        return self._device_url

    @property
    def supports_read(self) -> bool:
        return True

    def open(self):
        if not self._is_open:
            self._do_open()
            self._is_open = True

    def close(self):
        if self._is_open:
            self._do_close()
            self._is_open = False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    ###########################################################################
    # User-facing read and write functions                                    #
    ###########################################################################

    def write(self, data):
        logger.debug("Writing %d bytes.", len(data))
        self._do_write(data)

    def read(self, length=32):
        try:
            ret_bytes = self._do_read(length)
            if ret_bytes:
                logger.debug("Read %d bytes.", len(ret_bytes))
            return ret_bytes
        except Exception as e:
            logger.debug("Error reading... %s", e)
            raise

    ###########################################################################
    # Protected functions                                                     #
    ###########################################################################

    def _do_open(self):
        raise NotImplementedError()

    def _do_close(self):
        raise NotImplementedError()

    def _do_write(self, data: bytes):
        raise NotImplementedError()

    def _do_read(self, length: int) -> bytes:
        raise NotImplementedError()

    ###########################################################################
    # Static methods                                                          #
    ###########################################################################

    @staticmethod
    def discover(device_url: typing.Optional[str] = None) -> list[DeviceInfo]:
        return []
