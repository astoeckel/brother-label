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
import os
import shutil
import subprocess
import tempfile

import PIL.Image

from brother_label.renderers.base import PageSize, Renderer, RenderOptions

logger = logging.getLogger("__name__")


###############################################################################
# Private functions                                                           #
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


def _extract_pdf_page_sizes_in_pt(
    pdf_filename: str,
) -> list[tuple[float, float]]:
    # List the number of pages and their sizes (in pt) from the PDF. See
    # https://stackoverflow.com/a/52644056
    res = _run_subprocess(
        _find_exe("gs"),
        "-dQUIET",
        "-dNODISPLAY",
        "-dNOSAFER",
        f"-sFileName={pdf_filename}",
        "-c",
        """FileName (r) file
runpdfbegin
1 1 pdfpagecount {
    pdfgetpage
    /MediaBox get
    {
        =print
        ( ) print
    } forall
    (\\n) print
} for
quit""",
    )

    # Iterate over all pages and compute the width/height of each page
    page_sizes_pt = []
    for line in res.splitlines():
        media_box_pt = [float(x) for x in line.strip().split(" ")]
        assert len(media_box_pt) == 4

        media_width_pt = media_box_pt[2] - media_box_pt[0]
        media_height_pt = media_box_pt[3] - media_box_pt[1]
        page_sizes_pt.append((media_width_pt, media_height_pt))

    return page_sizes_pt


def _convert_pdf_page_to_png(
    pdf_filename: str,
    png_filename: str,
    page_idx: int,
    dpi: float,
):
    _run_subprocess(
        _find_exe("gs"),
        "-o",
        png_filename,
        "-sDEVICE=pnggray",
        f"-r{dpi}",
        f"-dFirstPage={page_idx + 1}",
        f"-dFLastPage={page_idx + 1}",
        pdf_filename,
    )


###############################################################################
# Class GhostScriptRenderer                                                   #
###############################################################################


class GhostScriptRenderer(Renderer):
    """
    Renderer instance responsible for handling PDF and PostScript documents
    using GhostScript.
    """

    def __init__(
        self,
        *,
        filename: str,
        render_options: RenderOptions,
    ):
        super().__init__(render_options=render_options)
        self._filename = filename
        self._bboxes = None

    #######################
    # Protected functions #
    #######################

    def _do_open(self):
        self._bboxes = _extract_pdf_page_sizes_in_pt(self._filename)

    def _do_close(self):
        self._bboxes = None

    def _do_compute_page_count(self) -> int:
        return len(self._bboxes)

    def _do_compute_page_size(self, page_idx: int) -> PageSize:
        assert page_idx < len(self._bboxes)
        return PageSize(
            width_px=self._bboxes[page_idx][0] / 72 * self._render_options.dpi,
            height_px=self._bboxes[page_idx][1] / 72 * self._render_options.dpi,
            dpi=self._render_options.dpi,
        )

    def _do_render(self, page_idx: int, page_size: PageSize) -> PIL.Image.Image:
        # Extract the original page width and height
        assert page_idx < len(self._bboxes)
        page_width_pt = self._bboxes[page_idx][0]
        page_height_pt = self._bboxes[page_idx][1]

        # Compute the DPI to use
        target_width_px = page_size.width_px
        target_heigth_px = page_size.height_px
        dpi_width = round(72 * (target_width_px / page_width_pt))
        dpi_height = round(72 * (target_heigth_px / page_height_pt))
        dpi = min(dpi_width, dpi_height)

        # Convert the image to a temporary PNG using GhostScript
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_png:
            f_png.close()
            try:
                _convert_pdf_page_to_png(
                    pdf_filename=self._filename,
                    png_filename=f_png.name,
                    page_idx=page_idx,
                    dpi=dpi,
                )

                # Load the image using PIL, since we're going to delete the
                # temporary file
                img = PIL.Image.open(f_png.name)
                img.load()
                return img
            finally:
                os.unlink(f_png.name)
