# Brother Label Printer User-Space Driver and Printing Utility
# Copyright (C) 2024 Andreas Stöckel
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
This file adds rudimentary support for directly printing PDF and PS files. It
does that by calling the GhostScript executable in the background.
"""

import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
import typing

from PIL import Image


def find_exe(exe: str) -> str:
    # Use shutil to search for executables to resolve the environment just
    # like the shell would.
    path = shutil.which(exe)
    if not path:
        raise RuntimeError(f"Cannot find executable {exe!r}")
    return path


def run_subprocess(*args, **kwargs) -> str:
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


def extract_pdf_page_sizes_in_pt(
    pdf_filename: str,
) -> list[tuple[float, float]]:
    # List the number of pages and their sizes (in pt) from the PDF. See
    # https://stackoverflow.com/a/52644056
    res = run_subprocess(
        find_exe("gs"),
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


def convert_pdf_page_to_png(
    pdf_filename: str,
    png_filename: str,
    page_idx: int,
    dpi: float,
):
    run_subprocess(
        find_exe("gs"),
        "-o",
        png_filename,
        "-sDEVICE=pnggray",
        f"-r{dpi}",
        f"-dFirstPage={page_idx + 1}",
        f"-dFLastPage={page_idx + 1}",
        pdf_filename,
    )


def is_supported_file(f: io.BufferedReader) -> bool:
    # Read the first "line" of the file; this should contain the magic
    # bytes
    buf = f.peek(5)
    if re.match(b"^%PDF-", buf) is not None:
        return True
    if re.match(b"^%!", buf):
        return True
    return False


def rasterize(
    f: io.BufferedReader,
    target_width_px: int,
    target_height_px: typing.Optional[int] = None,
) -> typing.List[Image.Image]:
    """
    Converts the given PDF or PS document into a series of rasterized images.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f_src:
        f_src.write(f.read())
        f_src.flush()

        if target_height_px is not None and target_height_px <= 0:
            target_height_px = None

        images: typing.List[Image.Image] = []

        # Determine the number of pages, and size of each page in the source file
        page_sizes_pt = extract_pdf_page_sizes_in_pt(f_src.name)
        for page_idx, (page_width_pt, page_height_pt) in enumerate(
            page_sizes_pt
        ):
            # Determine the DPI that we need to use to fit onto the target image
            dpi_width = int(
                (target_width_px * 72 + 0.5 * page_width_pt) / page_width_pt
            )
            if target_height_px is None:
                dpi = dpi_width
            else:
                dpi_height = int(
                    (target_height_px * 72 + 0.5 * page_height_pt)
                    / page_height_pt
                )
                dpi = min(dpi_width, dpi_height)

            with tempfile.NamedTemporaryFile(
                suffix=".png", delete=False
            ) as f_tar:
                try:
                    # Convert the page to a PNG
                    convert_pdf_page_to_png(
                        pdf_filename=f_src.name,
                        png_filename=f_tar.name,
                        page_idx=page_idx,
                        dpi=dpi,
                    )

                    # Compose the image onto a PIL canvas of the desired size; this
                    # is because GhostScript tends to produce images that do not
                    # quite match our desired output size; we have to add a pixel
                    # here or there.
                    with Image.open(f_tar.name) as im_page:
                        if target_height_px is None:
                            target_height_px = im_page.height
                        im_tar = Image.new(
                            "L", (target_width_px, target_height_px), 255
                        )
                        im_tar.paste(im_page)
                        images.append(im_tar)

                finally:
                    os.unlink(f_tar.name)

    return images


def iterate_pages(
    images: typing.Union[str, io.BufferedReader],
    target_width_px: int,
    target_height_px: typing.Optional[int] = None,
) -> typing.Iterator[typing.Union[str, Image.Image]]:
    for image in images:
        if isinstance(image, io.BufferedReader) and is_supported_file(image):
            for subimage in rasterize(image, target_width_px, target_height_px):
                yield subimage
        else:
            yield image
