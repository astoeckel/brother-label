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
import math
import os.path
import shutil
import subprocess
import typing

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

from brother_label.renderers.base import PageSize, Renderer, RenderOptions

###############################################################################
# Private helper functions                                                    #
###############################################################################


def _find_exe(exe: str) -> str:
    # Use shutil to search for executables to resolve the environment just
    # like the shell would.
    path = shutil.which(exe)
    if not path:
        raise RuntimeError(f"Cannot find executable {exe!r}")
    return path


def _run_subprocess(*args, **kwargs) -> str:
    logging.debug(f"Executing {args!r}")
    res = subprocess.run(
        args,
        **kwargs,
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if res.returncode != 0:
        raise RuntimeError(f"Error while executing {args!r}: {res.stdout}")
    return res.stdout


def _resolve_font(font_name: str, bold: bool = False, italic: bool = False):
    # Default the font name to a resonable font
    if font_name is None:
        font_name = "Arial"

    # If we have a font filename, then we're done
    if os.path.isfile(font_name):
        return font_name

    # Assemble a query for font-config
    query = f'"{font_name}"'
    if bold:
        query += ":weight=bold"
    if italic:
        query += ":style=italic"

    # Search for the font using font-config
    fonts = _run_subprocess(
        _find_exe("fc-match"), "--format=%{file}", "--", query
    )
    fonts = fonts.splitlines()
    assert len(fonts) == 1
    assert os.path.isfile(fonts[0])
    return fonts[0]


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
        font_name: str = None,
        font_size_pt: float = 16,
        margin_pt: float = 4,
        render_options: RenderOptions,
    ):
        super().__init__(render_options=render_options)
        self._text = text
        self._font_filename = _resolve_font(font_name)
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

        # Compute the bounding box of the text that we're rendering,
        # and of a single (Latin) line
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
        height = text_bbox[3] - text_bbox[1]

        # ...but make the height a multiple of a the standard Latin line height.
        # We might otherwise get different label heights for different text,
        # which would be odd.
        line_height = math.ceil(line_bbox[3] - line_bbox[1])
        n_lines = len(self._text.splitlines())
        height = line_height * n_lines

        return width, height

    def _do_open(self):
        # Compute the text bounding box at the target resolution
        w, h = self._compute_text_bbox(self.render_options.dpi)
        margin_px = self._margin_pt / 72 * self.render_options.dpi
        self._text_width_px = w + margin_px
        self._text_height_px = h + margin_px

    def _do_compute_page_size(self, page_idx: int) -> PageSize:
        # We only support one "page"
        assert page_idx == 0

        # Compute the page size taken up by the text
        return PageSize(
            max(self.render_options.printable_pixels[0], self._text_width_px),
            max(self.render_options.printable_pixels[1], self._text_height_px),
            self.render_options.dpi,
        )

    def _do_render(self, page_idx: int, page_size: PageSize) -> PIL.Image.Image:
        # We only support one "page"
        assert page_idx == 0

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
            (w // 2, h // 2),
            self._text,
            font=font,
            anchor="mm",
            align="center",
            fill=(0,),
        )
        return img
