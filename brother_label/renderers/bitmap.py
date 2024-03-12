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

import logging
import typing

import PIL.Image

from brother_label.renderers.base import PageSize, Renderer, RenderOptions

logger = logging.getLogger(__name__)

###############################################################################
# Class BitmapRenderer                                                         #
###############################################################################


class BitmapRenderer(Renderer):
    """
    Renderer instance responsible for handling raster images.
    """

    def __init__(
        self,
        *,
        filename_or_handle: typing.Union[str, typing.BinaryIO, None] = None,
        image: typing.Optional[PIL.Image.Image] = None,
        render_options: RenderOptions,
    ):
        # Pass the given render options to the inherited constructor
        super().__init__(render_options=render_options)

        # Validate the given parameters
        if (filename_or_handle is None) and (image is None):
            raise ValueError(
                "Either `filename_or_handle` or `image` must be provided"
            )
        if (filename_or_handle is not None) and (image is not None):
            raise ValueError(
                "Cannot provide both `filename_or_handle` or `image`"
            )

        # Copy the given arguments
        self._filename_or_handle = filename_or_handle
        self._image = image
        self._own_image = image is None

    #######################
    # Protected functions #
    #######################

    def _do_open(self):
        if self._own_image:
            logger.debug(f"Reading bitmap {self._filename_or_handle!r}")
            if isinstance(self._filename_or_handle, str):
                with open(self._filename_or_handle, "rb") as f:
                    self._image = PIL.Image.open(f)
                    self._image.load()
            else:
                self._image = PIL.Image.open(self._filename_or_handle)
                self._image.load()

    def _do_close(self):
        if self._own_image:
            self._image = None

    def _do_compute_page_size(self, page_idx: int) -> PageSize:
        assert page_idx == 0
        assert isinstance(self._image, PIL.Image.Image)

        # If available, fetch the DPI from the image
        dpi = None
        if "dpi" in self._image.info:
            if self._image.info["dpi"][0] != self._image.info["dpi"][1]:
                logger.warning(
                    "Input image is anamorphic: DPI differs for x- and y-axis. "
                    "Using DPI value for the x-axis."
                )
            dpi = float(self._image.info["dpi"][0])

        return PageSize(self._image.width, self._image.height, dpi)

    def _do_render(self, page_idx: int, page_size: PageSize) -> PIL.Image.Image:
        assert page_idx == 0
        assert isinstance(self._image, PIL.Image.Image)
        size = (page_size.width_px, page_size.height_px)

        print(page_size)

        # Create an image with a white background
        res = PIL.Image.new("RGB", size, (255, 255, 255))

        # Paste a resized version of the internal image onto the
        res.paste(self._image.resize(size), (0, 0))
        return res
