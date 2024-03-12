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
Renderer base classes. The base class takes care of generic tasks such as
scaling, centering and rotating the content that is being printed, as well as
adding the required margins and quantising the images for printing.
"""


import typing
from dataclasses import dataclass

import PIL.Image

###############################################################################
# Data structures                                                             #
###############################################################################


class RGB(typing.NamedTuple):
    """
    Named tuple used to represent an RGB value.
    """

    r: float
    g: float
    b: float


class PageSize(typing.NamedTuple):
    """
    Names tuple used to represent a page size in pixels, potentially attached
    with a physical size.
    """

    width_px: int = 0
    """
    Width of the page in pixels at the given DPI value. 
    """

    height_px: int = 0
    """
    Height of the page in pixels at the given DPI value.
    """

    dpi: typing.Optional[float] = None
    """
    The DPI value relative to which the size in pixels is specified. If `None`,
    then the pixel numbers are concrete device pixels.
    """


@dataclass
class RenderOptions:
    rotate: int = 0
    """
    Rotation that should be applied to the loaded image or document.
    """

    auto_rotate: bool = True
    """
    If true, rotates the image such that it it wastes as little space as
    possible on the label.
    """

    allow_scale_raster: bool = True
    """
    If True, resizes loaded raster images, even if their size does not match
    the printable resolution.
    """

    allow_scale_physical_dims: bool = True
    """
    If False, prints images such that the final physical dimensions on paper
    reflect the metadata associated with the image.
    """

    printable_pixels: tuple[int, int] = (0, 0)
    """
    Number of printable pixels. For endless paper the second pixel count is set
    to zero.
    """

    device_pixels: tuple[int, int] = (0, 0)
    """
    Total number of device pixels. For endless paper the second pixel count is
    set to zero.
    """

    device_pixels_offs: tuple[int, int] = (0, 0)
    """
    Location where the printable pixels should be placed onto the device image.  
    """

    device_pixels_padding_bottom: int = 0
    """
    Whitespace to add at the bottom for endless paper.
    """

    dpi: float = 300.0
    """
    DPI value that should be used to convert from pixels to physical sizes.
    """

    dither: bool = True
    """
    If true, enables dithering. The threshold is ignored in that case.
    """

    palette: tuple[RGB, ...] = (RGB(0.0, 0.0, 0.0), RGB(1.0, 1.0, 1.0))
    """
    Colour palette the image should be converted to. Normally, this palette
    just contains black and white. However, some label printers also support
    three colours (black, white, red). This third colour should be placed
    in this array. 
    """

    @property
    def is_endless(self) -> bool:
        return self.printable_pixels[1] == 0

    def validate(self):
        """
        Checks this `RenderOptions` instance for internal consistency. Since
        this structure is not exposed to the end-user we're using asserts here.
        """
        assert self.printable_pixels[0] > 0
        assert self.printable_pixels[1] >= 0
        assert self.device_pixels[0] > 0
        assert self.device_pixels[1] >= 0
        assert self.printable_pixels[0] <= self.device_pixels[0]
        assert self.printable_pixels[1] <= self.device_pixels[1]
        assert self.device_pixels_padding_bottom >= 0
        assert self.dpi > 0.0

        if self.is_endless:
            assert self.printable_pixels[1] == 0
            assert self.device_pixels[1] == 0

        assert self.rotate in {0, 90, 180, 270}

        for colour in self.palette:
            assert 0.0 <= colour.r <= 1.0
            assert 0.0 <= colour.g <= 1.0
            assert 0.0 <= colour.b <= 1.0


###############################################################################
# Class Renderer                                                              #
###############################################################################


class Renderer:
    """
    Base class for raster, vector (e.g., GhostScript) and text rendering. This
    class performs generic tasks such as automatically applying rotations and to
    quantise images to two or three colours.
    """

    def __init__(self, *, render_options: RenderOptions):
        self._render_options = render_options

    @property
    def render_options(self):
        return self._render_options

    def render(self) -> typing.Iterable[PIL.Image.Image]:
        """
        Renders the represented element into a final device pixel map that
        makes used of the palette stored in the `RenderOptions`.

        The resulting bytearray contains one byte per device pixel in a
        row-major format.
        """

        # Open the underlying resource
        self._do_open()
        try:
            # Iterate over all pages in the document (for images, there is only
            # one page).
            for page_idx in range(self._do_compute_page_count()):
                yield self._render_page(page_idx)
        finally:
            # Free the underlying resource
            self._do_close()

    #####################
    # Private functions #
    #####################

    def _get_palette_image(
        self, size: tuple[int, int] = (1, 1)
    ) -> PIL.Image.Image:
        # Construct an array containing the palette data as a sequence of
        # (R, G, B) tuples.
        n = len(self.render_options.palette)
        assert 1 < n <= 256
        palette_data = []
        for colour in self.render_options.palette:
            palette_data.append(int(colour.r * 255))
            palette_data.append(int(colour.g * 255))
            palette_data.append(int(colour.b * 255))
        palette_data.extend(0 for _ in range(3 * (256 - n)))

        # Create a dummy image containing the palette
        palette_image = PIL.Image.new("P", size)
        palette_image.putpalette(palette_data)
        return palette_image

    def _render_page(self, page_idx: int) -> PIL.Image.Image:
        # Ensure that the render options make sense.
        ro = self.render_options
        ro.validate()

        # TODO: We're just implementing the easy path right now where everything
        #       is scaled to the target dimensions.
        if not ro.allow_scale_raster:
            raise NotImplementedError()
        if not ro.allow_scale_physical_dims:
            raise NotImplementedError()

        # Compute the dimensions of the page that we're going to print
        page_size = self._do_compute_page_size(page_idx)
        assert page_size.width_px > 0
        assert page_size.height_px > 0

        # From that, derive the aspect ratio of the image
        aspect_ratio = page_size.width_px / page_size.height_px

        # TODO: Figure out auto-rotation
        w = ro.printable_pixels[0]
        h = ro.printable_pixels[0] / aspect_ratio
        if (not ro.is_endless) and (h > ro.printable_pixels[1]):
            w = ro.printable_pixels[1] * aspect_ratio
            h = ro.printable_pixels[1]
            if w > ro.printable_pixels[0]:
                h *= ro.printable_pixels[0] / w
                w = ro.printable_pixels[0]
        w = int(round(w))
        h = int(round(h))

        # Compute the DPI at which the document should be rendered
        dpi = None
        if page_size.dpi:
            dpi = page_size.dpi * (w / page_size.width_px)

        # Render the image to the target shape
        src_image = self._do_render(page_idx, PageSize(w, h, dpi))
        assert src_image.width == w
        assert src_image.height == h

        # Quantize the image using dithering.
        # TODO: Implement thresholding mode, use HSV transformation to split
        #       out the red channel.
        src_image_quant = src_image.quantize(
            colors=len(ro.palette),
            method=PIL.Image.FASTOCTREE,
            palette=self._get_palette_image(),
            dither=PIL.Image.FLOYDSTEINBERG,
        )

        # Create the output image
        tw = ro.device_pixels[0]
        th = ro.device_pixels[1]
        if ro.is_endless:
            th = h + ro.device_pixels_padding_bottom
        tar_image = self._get_palette_image((tw, th))
        tar_image.paste(src_image_quant, ro.device_pixels_offs)
        return tar_image

    #######################
    # Protected functions #
    #######################

    def _do_open(self):
        """
        Instructs the backend to actually open the resource from which the
        final image is produced.
        """

    def _do_close(self):
        """
        Instructs the backend to close the resource from which the final
        image is produced.
        """

    def _do_compute_page_count(self) -> int:
        """
        Computes the number of pages in the document. This may be more than
        one for multi-page documents. This function is guaranteed to be called
        after `_do_open()` has been called, and before `_do_close()`.
        """
        return 1

    def _do_compute_page_size(self, page_idx: int) -> PageSize:
        """
        Returns the size of the element in millimeters. This function is
        guaranteed to be called after `_do_open()` has been called, and before
        `_do_close()`.
        """
        raise NotImplementedError()

    def _do_render(self, page_idx: int, page_size: PageSize) -> PIL.Image.Image:
        """
        Requests rendering of the specified page into an image that has the
        given number of pixels. This function is guaranteed to be called
        after `_do_open()` has been called, and before `_do_close()`.
        """
        raise NotImplementedError()
