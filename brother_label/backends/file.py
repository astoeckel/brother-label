# Brother Label Printer User-Space Driver and Printing Utility
# Copyright (C) 2024  Andreas Stöckel
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
Provides a backend simply writing RAW printer command sequences to a file.
The commands can be sent to a printer at a later point in time or analyzed
for debugging.
"""

from brother_label.backends.base import BackendBase


class BackendFile(BackendBase):
    """
    BrotherQL backend using the Linux Kernel USB Printer Device Handles
    """

    def __init__(self, device_url: str):
        """
        Path to a file or a URL in the "file://" scheme
        """
        super().__init__(device_url)

        # Remove the "file://" URL schema
        if device_url.startswith("file://"):
            device_url = device_url[7:]

        self._filename = device_url
        self._fd = None

    @property
    def filename(self):
        return self._filename

    @property
    def supports_read(self):
        return False

    ###########################################################################
    # Protected functions                                                     #
    ###########################################################################

    def _do_open(self):
        self._fd = open(self._filename, "wb")

    def _do_close(self):
        if self._fd is not None:
            self._fd.close()

    def _do_write(self, data):
        self._fd.write(data)
