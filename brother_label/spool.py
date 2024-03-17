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
Contains high-level helper functions for assembling a queue of labels that
should be printed on the label printer.
"""

import dataclasses
import os
import tempfile
import typing
import logging

from brother_label import (
    backends,
    engine,
    exceptions,
    labels,
    models,
    raster,
    reader,
    renderers,
)

logger = logging.getLogger(__name__)

IMAGE_FILE_EXTS = [".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".png"]

DOCUMENT_FILE_EXTS = [".eps", ".ps", ".pdf"]


@dataclasses.dataclass
class LabelMetadata:
    """
    Class describing a single label that is being printed. The metadata contains
    the label size, margin, and the location of the preview image that should
    be displayed. We're deliberately not holding the preview image in memory
    to avoid having too many images open at the same time.
    """

    label_name: str = ""
    image_filename: str = ""
    label_width_mm: float = 0.0
    label_height_mm: float = 0.0
    margin_width_mm: float = 0.0
    margin_height_mm: float = 0.0

    def __bool__(self):
        return (
            self.image_filename
            and (self.label_width_mm >= 0.0)
            and (self.label_height_mm >= 0.0)
            and (self.margin_width_mm >= 0.0)
            and (self.margin_height_mm >= 0.0)
            and os.path.isfile(self.image_filename)
        )


class Spool:
    """
    Class used to manage a print job.

    Renders the objects to the final raster commands and offers functionality
    for previewing the rasterized objects and to send them to the actual printer
    backend.
    """

    def __init__(self, model: models.Model, label: labels.Label) -> None:
        self._model = model
        self._label = label
        self._spool_fd = None
        self._spool_fn = None
        self._spool_file = None
        self._spool_dir = None
        self._raster = None
        self._metadata_templates = []

        self._rotate = 0
        self._auto_rotate = True
        self._auto_cut = True
        self._high_quality = True
        self._compress = True

    def cleanup(self):
        if self._spool_file:
            self._spool_file.close()
            self._spool_file = None

        self._spool_fd = None

        if self._spool_fn and os.path.isfile(self._spool_fn):
            os.unlink(self._spool_fn)
        self._spool_fn = None

        if self._spool_dir:
            self._spool_dir.cleanup()
            self._spool_dir = None

        self._raster = None
        self._metadata_templates = []

    def __enter__(self):
        # Open the spool file and create the corresponding raster object
        self._spool_fd, self._spool_fn = tempfile.mkstemp(suffix=".spl")
        self._spool_file = open(self._spool_fd, "r+b", closefd=True)
        self._raster = raster.BrotherLabelRaster(self._spool_file, self._model)

        # Add a bunch of initialization commands
        try:
            self._raster.add_switch_mode()
        except exceptions.BrotherQLUnsupportedCmd:
            pass
        self._raster.add_invalidate()
        self._raster.add_initialize()
        try:
            self._raster.add_switch_mode()
        except exceptions.BrotherQLUnsupportedCmd:
            pass

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __del__(self):
        self.cleanup()

    @property
    def model(self):
        return self._model

    @property
    def label(self):
        return self._label

    @property
    def rotate(self):
        return 0 if self._auto_rotate else self._rotate

    @rotate.setter
    def rotate(self, value: typing.Union[str, int]):
        if value == "auto":
            self._rotate = 0
            self._auto_rotate = True
            return

        value = int(value)
        if value not in {0, 90, 180, 270}:
            raise ValueError(f"Unsupported rotation {value!r}")
        self._rotate = value
        self._auto_rotate = False

    @property
    def auto_rotate(self):
        return self._auto_rotate

    @auto_rotate.setter
    def auto_rotate(self, value: bool):
        self._auto_rotate = bool(value)

    @property
    def auto_cut(self):
        return self._auto_cut

    @auto_cut.setter
    def auto_cut(self, value: bool):
        self._auto_cut = bool(value)

    @property
    def high_quality(self) -> bool:
        return bool(self._high_quality)

    @high_quality.setter
    def high_quality(self, value: bool):
        self._high_quality = bool(value)

    @property
    def compress(self) -> bool:
        return self._compress

    @compress.setter
    def compress(self, value: bool):
        self._compress = bool(value)

    @property
    def render_options(self) -> renderers.RenderOptions:
        # TODO: Support for 600 DPI
        # TODO: Support for two colour modes
        ro = renderers.RenderOptions()
        ro.rotate = self._rotate
        ro.auto_rotate = self._auto_rotate
        ro.allow_scale_physical_dims = True
        ro.allow_scale_raster = True
        ro.printable_pixels = self._label.dots_printable
        ro.device_pixels = (
            self._model.number_bytes_per_row * 8,
            self._label.dots_total[1],
        )
        ro.device_pixels_offs = (
            self._label.offset_r + self._model.additional_offset_r,
            0,
        )
        return ro

    @property
    def ro(self) -> renderers.RenderOptions:
        return self.render_options

    def _resolve_auto_obj(self, obj: str):
        # Apply some heuristics to determine whether the given argument is
        # simple text or an image file.
        is_file, is_text = False, False

        # The image is a file if it points at an existing file
        if os.path.isfile(obj):
            is_file = True
        elif "." in obj:
            # The image is text if the extension is not a known image or
            # document file extension
            ext = obj.rsplit(".", 1)[-1].lower()
            if (ext not in IMAGE_FILE_EXTS) and (ext not in DOCUMENT_FILE_EXTS):
                is_text = True
        else:
            is_text = True

        # If the argument is ambiguous, throw an error. Better to be safe than
        # to be sorry.
        if (not is_text) and (not is_file):
            raise exceptions.BrotherQLError(
                f"Ambiguous object {obj!r}. Looks like a file, but that file"
                "does not exist. Explicitly use `--file` or `--text` to"
                "specify a file or text label"
            )

        # Produce the actual render objects
        if is_file:
            return self._resolve_file_obj(obj)
        else:  # is_text
            return self._resolve_text_obj(obj)

    def _resolve_file_obj(self, obj: str):
        ext = os.path.splitext(obj)[1].lower()
        if ext in IMAGE_FILE_EXTS:
            return renderers.BitmapRenderer(
                filename_or_handle=obj, render_options=self.ro
            )
        elif ext in DOCUMENT_FILE_EXTS:
            return renderers.GhostScriptRenderer(
                filename=obj, render_options=self.ro
            )
        raise exceptions.BrotherQLError(f"Unknown file extension {ext!r}")

    def _resolve_text_obj(self, obj: str):
        return renderers.TextRenderer(text=obj, render_options=self.ro)

    def render(
        self,
        obj: typing.Union[renderers.Renderer | str],
        kind: str = "auto",
    ):
        assert self._spool_file
        assert self._raster
        assert kind in {"auto", "text", "file"}

        # If the given object is a string, convert it to a `Render` instance
        orig_obj = obj
        if isinstance(obj, str):
            if kind == "auto":
                obj = self._resolve_auto_obj(obj)
            elif kind == "file":
                obj = self._resolve_file_obj(obj)
            elif kind == "text":
                obj = self._resolve_text_obj(obj)

        if not isinstance(obj, renderers.Renderer):
            raise TypeError("Expected a string or a `Renderer` instance")

        # Render the object to an image
        imgs = obj.render()

        for page_idx, img in enumerate(imgs):
            # Write information about the print media
            self._raster.add_status_information()
            if self.label.form_factor in (
                labels.FormFactor.DIE_CUT,
                labels.FormFactor.ROUND_DIE_CUT,
            ):
                self._raster.mtype = 0x0B
                self._raster.mwidth = self.label.tape_size[0]
                self._raster.mlength = self.label.tape_size[1]
            elif self.label.form_factor in (labels.FormFactor.ENDLESS,):
                self._raster.mtype = 0x0A
                self._raster.mwidth = self.label.tape_size[0]
                self._raster.mlength = 0
            elif self.label.form_factor in (labels.FormFactor.PTOUCH_ENDLESS,):
                self._raster.mtype = 0x00
                self._raster.mwidth = self.label.tape_size[0]
                self._raster.mlength = 0

            # Write information about the print quality
            self._raster.pquality = int(self.high_quality)
            self._raster.add_media_and_quality(img.size[1])
            try:
                if self.auto_cut:
                    self._raster.add_autocut(True)
                    self._raster.add_cut_every(1)
            except exceptions.BrotherQLUnsupportedCmd:
                pass

            # Write extended command information
            dpi_600 = False  # TODO
            red = False  # TODO
            try:
                self._raster.dpi_600 = dpi_600  # TODO
                self._raster.cut_at_end = self.auto_cut
                self._raster.two_color_printing = red  # TODO
                self._raster.add_expanded_mode()
            except exceptions.BrotherQLUnsupportedCmd:
                pass

            # Move the label to the correct location
            self._raster.add_margins(self.label.feed_margin)

            # Enable image compression (if supported)
            try:
                if self.compress:
                    self._raster.add_compression(True)
            except exceptions.BrotherQLUnsupportedCmd:
                pass

            # Write the actual image
            # TODO: Handle red image
            self._raster.add_raster_data(img)

            # Finalise the print
            self._raster.add_print()

            # Remember what we printed
            label_name = None
            if isinstance(orig_obj, str):
                if isinstance(obj, renderers.TextRenderer):
                    label_name = f"Text {orig_obj!r}"
                elif isinstance(obj, renderers.BitmapRenderer):
                    label_name = f"Bitmap {orig_obj!r}"
                elif isinstance(obj, renderers.GhostScriptRenderer):
                    label_name = f"Document {orig_obj!r}"

                if len(label_name) > 60:
                    label_name = label_name[:30] + "[...]" + label_name[-30:]

                if obj.page_count > 1:
                    label_name += f" (pg. {page_idx + 1}/{obj.page_count})"
                logger.info(f"Processed: {label_name}")

            self._metadata_templates.append(
                LabelMetadata(
                    label_name=label_name,
                    label_width_mm=self.label.tape_size[0],
                    label_height_mm=(img.size[1] * 25.4) / 300.0,
                )
            )

    def preview(self):
        # Clean up a previous preview
        if self._spool_dir:
            self._spool_dir.cleanup()
            self._spool_dir = None

        # Create a temporary directory containing the preview files
        self._spool_dir = tempfile.TemporaryDirectory()

        # Seek the spool file to the beginning
        self._spool_file.seek(0, 0)
        logger.info(f"Writing preview images to {self._spool_dir.name!r}")
        rdr = reader.BrotherQLReader(
            self._spool_file,
            filename_fmt=os.path.join(
                self._spool_dir.name, "spool{counter:04d}.png"
            ),
        )
        rdr.analyse()

        # Seek the spool file back to the end
        self._spool_file.seek(0, 2)

        # Assemble a list of preview images
        res = []
        for i, file in enumerate(sorted(os.listdir(self._spool_dir.name))):
            assert i < len(self._metadata_templates)
            meta = LabelMetadata(
                **dataclasses.asdict(self._metadata_templates[i])
            )
            meta.image_filename = os.path.join(self._spool_dir.name, file)
            res.append(meta)
        return res

    def print(self, backend: backends.Backend):
        logger.info(f"Printing to {backend.device_url!r}")
        try:
            self._spool_file.seek(0, 0)
            with backend:
                engine.communicate(self._spool_file.read(), backend)
        finally:
            self._spool_file.seek(0, 2)
