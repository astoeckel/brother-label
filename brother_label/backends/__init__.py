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

import os

from brother_label.backends.base import Backend, DeviceInfo

ALL_BACKEND_NAMES = [
    "pyusb",
    "network",
    "linux",
    "file",
]


def guess_backend_name(device_url: str) -> str:
    """
    Guesses the backend name from the given device URL.
    """

    if device_url.startswith("usb://") or device_url.startswith("0x"):
        return "pyusb"
    if (
        device_url.startswith("lp://")
        or device_url.startswith("/dev/usb/")
        or device_url.startswith("lp")
    ):
        return "linux"
    if device_url.startswith("tcp://"):
        return "network"
    if device_url.startswith("file://"):
        return "file"
    if device_url:
        try:
            path = os.path.realpath(device_url)
            if os.path.isfile(path):
                return "file"
            path = os.path.dirname(path)
            if os.access(path, os.O_RDWR):
                return "file"
        except OSError:
            pass

    raise ValueError(f"Cannot guess backend for {device_url!r}")


def backend_class(backend_name: str):
    """
    Converts the given backend name into the corresponding backend class.
    """

    if backend_name == "pyusb":
        from brother_label.backends.pyusb import BackendPyUSB

        return BackendPyUSB

    if backend_name == "linux":
        from brother_label.backends.linux import BackendLinux

        return BackendLinux

    if backend_name == "network":
        from brother_label.backends.network import BackendNetwork

        return BackendNetwork

    if backend_name == "file":
        from brother_label.backends.file import BackendFile

        return BackendFile

    raise NotImplementedError(f"Unknown backend {backend_name!r}")


def backend_factory(backend_name: str, device_url: str):
    return backend_class(backend_name)(device_url)
