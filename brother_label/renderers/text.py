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

import math

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

from brother_label.renderers.base import PageSize, Renderer, RenderOptions

###############################################################################
# Class TextRenderer                                                          #
###############################################################################


class TextRenderer(Renderer):
    """
    Renderer instance responsible for handling PDF and PostScript documents
    using GhostScript.
    """

    def __init__(
        self,
        *,
        text: str,
        font_filename: str,
        font_size_pt: float = 16,
        margin_pt: float = 4,
        render_options: RenderOptions,
    ):
        super().__init__(render_options=render_options)
        self._text = text
        self._font_filename = font_filename
        self._font_size_pt = font_size_pt
        self._margin_pt = margin_pt
        self._font = None
        self._text_width_px = None
        self._text_height_px = None

    #######################
    # Protected functions #
    #######################

    def _compute_text_bbox(self, dpi: float):
        # Load the font
        font = PIL.ImageFont.truetype(
            font=self._font_filename,
            size=int(round(self._font_size_pt / 72 * dpi)),
        )

        # Compute the bounding box of the text that we're rendering, and of a
        # single (Latin) line
        img = PIL.Image.new("L", (1, 1))
        img_draw = PIL.ImageDraw.ImageDraw(img)

        text_bbox = img_draw.multiline_textbbox(
            (0, 0), self._text, font=font, align="center"
        )
        line_bbox = img_draw.multiline_textbbox(
            (0, 0), "AjQf't.,q", font=font, align="center"
        )

        # Return the actual text width...
        width = text_bbox[2] - text_bbox[0]

        # ...but make the height a multiple of a the standard Latin line height.
        # We might otherwise get different label heights for different text,
        # which would be odd.
        line_height = math.ceil(line_bbox[3] - line_bbox[1])
        height = line_height * len(self._text.split("\n"))

        return width, height

    def _do_open(self):
        # Compute the text bounding box at the target resolution
        w, h = self._compute_text_bbox(self.render_options.dpi)
        margin_px = self._margin_pt / 72 * self.render_options.dpi
        self._text_width_px = w + margin_px
        self._text_height_px = h + margin_px

    def _do_compute_page_size(self, page_idx: int) -> PageSize:
        return PageSize(
            max(self.render_options.printable_pixels[0], self._text_width_px),
            max(self.render_options.printable_pixels[1], self._text_height_px),
            self.render_options.dpi,
        )

    def _do_render(self, page_idx: int, page_size: PageSize) -> PIL.Image.Image:
        # Load the font
        font = PIL.ImageFont.truetype(
            font=self._font_filename,
            size=int(round(self._font_size_pt / 72 * page_size.dpi)),
        )

        # Render the text centered on the page
        w, h = page_size.width_px, page_size.height_px
        img = PIL.Image.new("L", (w, h), (255,))
        img_draw = PIL.ImageDraw.ImageDraw(img)
        img_draw.multiline_text(
            (w // 2, h // 2), self._text, font=font, anchor="mm", align="center", fill=(0,),
        )
        return img


if __name__ == "__main__":
    ro = RenderOptions()
    ro.device_pixels = (700, 0)
    ro.printable_pixels = (650, 0)
    ro.dpi = 300.0

    # ir = ImageRenderer(
    #     filename_or_handle="/home/andreas/bitmap.png", render_options=ro
    # )
    # for i, img in enumerate(ir.render()):
    #     img.save(f"test{i:04d}.png")
    fr = TextRenderer(
        text="foo",
        # font_filename="/usr/share/fonts/linux-libertine-biolinum-fonts/LinBiolinum_R.otf",
        font_filename="/usr/share/fonts/gdouros-symbola/Symbola.ttf",
        font_size_pt=72,
        render_options=ro,
    )
    for i, img in enumerate(fr.render()):
        img.save(f"test{i:04d}.png")
