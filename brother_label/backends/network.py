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
Backend for printing to a network printer.
"""

import socket
import urllib.parse

from brother_label.backends.base import Backend
from brother_label.exceptions import BrotherQLError


class BackendNetwork(Backend):
    """
    BrotherQL backend using the Linux Kernel USB Printer Device Handles
    """

    def __init__(self, device_url):
        """
        Opens a printer on the network. The given device URL must be of the
        form "tcp://HOST:PORT".
        """
        super().__init__(device_url)
        self._socket = None
        self._write_timeout_s = 10.0

    @property
    def supports_read(self):
        # Technically the network backend supports reading, but we're never
        # using that when communicating with the printer; for some reason the
        # printer never sends anything on the return channel.
        return False

    ###########################################################################
    # Protected functions                                                     #
    ###########################################################################

    def _do_open(self):
        # Use urllib to parse the given URL; this is required because correctly
        # separating a port number and an IPv6 address is tricky.
        device_url = self.device_url
        if not "//" in device_url:
            device_url = f"tcp://{device_url}"
        url = urllib.parse.urlparse(device_url)

        # Ensure that no weird protocol or pathwas requested
        if url.scheme != "tcp":
            raise BrotherQLError(
                f"Unsupported URL scheme {url.scheme!r}. The `network` "
                "backend only supports the `tcp://` scheme"
            )
        if url.path and url.path != "/":
            raise BrotherQLError(
                f"Unsupported URL {device_url}. The `network` backend only "
                "supports URLs of the form `tcp://HOST:PORT`"
            )

        # Fetch the port and the hostname
        host = url.hostname
        port = url.port
        if not port:
            port = 9100

        # Create a client socket
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._socket.connect((host, port))
        self._socket.settimeout(self._write_timeout_s)

    def _do_close(self):
        self._socket.shutdown(socket.SHUT_RDWR)
        self._socket.close()
        self._socket = None

    def _do_write(self, data):
        self._socket.sendall(data)
