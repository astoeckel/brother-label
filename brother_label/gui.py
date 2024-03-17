# Brother Label Printer User-Space Driver
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
This module provides a small GUI for displaying previews of the labels that are
being printed.
"""

import dataclasses
import tkinter
import tkinter as tk
import tkinter.ttk as ttk
import typing

import PIL
import PIL.ImageTk

from brother_label.spool import LabelMetadata


class LabelPreview(tk.Frame):
    """
    Frame responsible for drawing a preview of an individual label that is
    being printed.
    """

    def __init__(self, parent):
        super().__init__(parent)

        self._canvas = tk.Canvas(self, background="#f9f9f9")
        self._canvas.grid(row=0, column=0, sticky="news")
        self._canvas.bind("<Configure>", self.resize)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._meta = None
        self._image = None
        self._image_filename = ""
        self._image_tk = None

    @property
    def meta(self) -> typing.Optional[LabelMetadata]:
        return self._meta

    @meta.setter
    def meta(self, meta: typing.Optional[LabelMetadata]):
        self._meta = meta
        self.draw()

    def draw(self):
        """
        Used internally to draw the label preview to the TK canvas.
        """

        # Clean up the previous canvas state
        self._canvas.delete("all")

        # Fetch the canvas size
        w, h = self.winfo_width(), self.winfo_height()

        # Leave enough space to draw the arrow and size labels
        padding = max(200.0, min(w * 0.2, h * 0.2))
        w_use, h_use = w - 2.0 * padding, h - 1.5 * padding

        # Abort if no label for previewing is loaded
        if not self.meta:
            self._canvas.create_text(
                0.5 * w, 0.5 * h, text="No label", anchor="center"
            )
            self._image = None
            self._image_filename = ""
            self._image_tk = None
            return

        # Load the preview image if no image has been loaded
        if self._image_filename != self.meta.image_filename:
            with open(self.meta.image_filename, "rb") as f:
                self._image = PIL.Image.open(f)
                self._image.load()
            self._image_filename = self.meta.image_filename

        # Determine the area where to draw the label
        aspect_ratio = self.meta.label_height_mm / self.meta.label_width_mm
        w_lbl, h_lbl = int(w_use), int(w_use * aspect_ratio)
        if h_lbl > h_use:
            w_lbl, h_lbl = int(h_use / aspect_ratio), int(h_use)
        if w_lbl <= 1:
            w_lbl = 2
        if h_lbl <= 1:
            h_lbl = 2
        x0, y0 = 0.5 * (w - w_lbl), 0.5 * (h - h_lbl)
        x1, y1 = 0.5 * (w + w_lbl), 0.5 * (h + h_lbl)
        px_per_mm = w_lbl / self.meta.label_width_mm

        # Draw the label shadow and white background
        ss = max(5.0, min(w * 0.01, h * 0.01))  # Shadow size
        self._canvas.create_rectangle(
            (x0 + ss, y0 + ss), (x1 + ss, y1 + ss), fill="silver", width=0
        )
        self._canvas.create_rectangle((x0, y0), (x1, y1), fill="white")

        # Draw the label image
        image_resized = self._image.resize(
            (w_lbl - 1, h_lbl - 1), PIL.Image.BILINEAR
        )
        self._image_tk = PIL.ImageTk.PhotoImage(image_resized)
        self._canvas.create_image(
            x0 + 1, y0 + 1, image=self._image_tk, anchor="nw"
        )

        # Draw the print direction arrow
        ax = x1 + max(50.0, min(w * 0.1, h * 0.1))
        aw = max(5.0, min(w * 0.01, h * 0.01))
        self._canvas.create_line(
            (ax, y0),
            (ax, y1 - 2.0 * aw),
            width=0.75 * aw,
            fill="gray",
            dash=(int(aw), int(aw)),
        )
        self._canvas.create_polygon(
            (ax - aw, y1 - 2.0 * aw),
            (ax + aw, y1 - 2.0 * aw),
            (ax, y1),
            fill="gray",
        )

        # Draw the margins
        dw = int(max(5.0, min(w * 0.01, h * 0.01)))  # Dash length
        mx0 = x0 + px_per_mm * self.meta.margin_width_mm
        mx1 = x1 - px_per_mm * self.meta.margin_width_mm
        my0 = y0 + px_per_mm * self.meta.margin_height_mm
        my1 = y1 - px_per_mm * self.meta.margin_height_mm
        mo = max(20.0, min(w * 0.05, h * 0.05))  # Margin overdraw
        self._canvas.create_line(
            (x0 - mo, my0), (x1 + mo, my0), fill="blue", dash=(dw, dw)
        )
        self._canvas.create_line(
            (x0 - mo, my1), (x1 + mo, my1), fill="blue", dash=(dw, dw)
        )
        self._canvas.create_line(
            (mx0, y0 - mo), (mx0, y1 + mo), fill="blue", dash=(dw, dw)
        )
        self._canvas.create_line(
            (mx1, y0 - mo), (mx1, y1 + mo), fill="blue", dash=(dw, dw)
        )

        # Draw the label dimension markers
        dx = x0 - max(50.0, min(w * 0.1, h * 0.1))
        dy = y1 + max(50.0, min(w * 0.1, h * 0.1))
        self._canvas.create_line((x0, dy), (x1, dy), width=1)
        self._canvas.create_line((x0, dy - aw), (x0, dy + aw), width=2)
        self._canvas.create_line((x1, dy - aw), (x1, dy + aw), width=2)
        self._canvas.create_text(
            0.5 * (x0 + x1),
            dy + 2 * aw,
            text=f"{self.meta.label_width_mm: 0.2f} mm",
            anchor="center",
        )

        self._canvas.create_line((dx, y0), (dx, y1), width=1)
        self._canvas.create_line((dx - aw, y0), (dx + aw, y0), width=2)
        self._canvas.create_line((dx - aw, y1), (dx + aw, y1), width=2)
        try:
            # We're using the Tk 8.6 "angle" feature here, which isn't officially supported by the Python binding
            # yet.
            # noinspection PyArgumentList
            self._canvas.create_text(
                dx - 2 * aw,
                0.5 * (y0 + y1),
                text=f"{self.meta.label_height_mm: 0.2f} mm",
                anchor="center",
                angle=90,
            )
        except tkinter.TclError:
            self._canvas.create_text(
                dx - 2 * aw,
                0.5 * (y0 + y1),
                text=f"{self.meta.label_height_mm: 0.2f} mm",
                anchor="e",
            )

    def resize(self, _):
        self.draw()


class Gui:
    """
    Class that should be used to display the preview GUI. Call `run` to actually
    show the GUI; then inspect the "action" and "label_idx" properties to
    determine what the intended user interaction is.
    """

    default_action_btn_style = {
        "fg": "white",
        "bg": "mediumseagreen",
        "font": ("Sans", "10", "bold"),
    }

    page_ctrl_btn_style = {
        "fg": "white",
        "bg": "royalblue",
        "font": ("Sans", "10", "bold"),
    }

    def __init__(
        self,
        label_metadata: typing.Optional[typing.Sequence[LabelMetadata]] = None,
        printer_name: str = "No printer selected",
        has_print_single: bool = False,
        label_idx=0,
    ):
        # Copy the given label metadata
        if label_metadata is None:
            label_metadata = []
        self._label_metadata = [
            LabelMetadata(**dataclasses.asdict(x)) for x in label_metadata
        ]
        self._label_idx = 0
        self._action = None

        # Assemble
        self.root = tk.Tk()
        self.root.title("Label Printer Preview")
        self.root.minsize(800, 600)

        self.frm_main = ttk.Frame(self.root, width=800, height=600)
        self.frm_main.grid(sticky="news")

        self.frm_top = ttk.Frame(self.frm_main, padding=5)
        self.frm_top.grid(column=0, row=0, sticky="ew")

        self.btn_prev = tk.Button(
            self.frm_top,
            text="Previous",
            **self.page_ctrl_btn_style,
            command=self.prev_label_click,
            width=10,
        )
        self.btn_prev.grid(column=0, row=0, rowspan=2)
        self.btn_prev.configure(state="disabled")

        self.lbl_label_no = ttk.Label(
            self.frm_top, anchor="c", font=("Sans", "10", "bold")
        )
        self.lbl_label_no.grid(column=1, row=0, sticky="news")

        self.lbl_label_name = ttk.Label(self.frm_top, anchor="c")
        self.lbl_label_name.grid(column=1, row=1, sticky="news")

        self.btn_next = tk.Button(
            self.frm_top,
            text="Next",
            **self.page_ctrl_btn_style,
            command=self.next_label_click,
            width=10,
        )
        self.btn_next.grid(column=2, row=0, rowspan=2)
        self.btn_next.configure(state="disabled")

        self.preview_area = LabelPreview(self.frm_main)
        self.preview_area.grid(column=0, row=1, sticky="news")

        self.frm_bottom = ttk.Frame(self.frm_main, padding=5)
        self.frm_bottom.grid(column=0, row=2, sticky="ew")

        self.lbl_printer = ttk.Label(self.frm_bottom, text=printer_name)
        self.lbl_printer.grid(column=0, row=0, sticky="news")

        c = 1
        if has_print_single:
            self.btn_print_single = tk.Button(
                self.frm_bottom,
                text="Print single label",
                width=15,
                command=self.print_single_click,
            )
            self.btn_print_single.grid(column=c, row=0)
            c += 1
        else:
            self.btn_print_single = None

        self.btn_print_all = tk.Button(
            self.frm_bottom,
            text="Print all",
            width=15,
            **self.default_action_btn_style,
            command=self.print_all_click,
        )
        self.btn_print_all.grid(column=c, row=0)
        c += 1

        self.frm_top.columnconfigure(1, weight=1)
        self.frm_bottom.columnconfigure(0, weight=1)
        self.frm_main.columnconfigure(0, weight=1)
        self.frm_main.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.show_label(label_idx)

    @property
    def action(self):
        return self._action

    @property
    def label_idx(self):
        return self._label_idx

    def show_label(self, label_idx: int):
        # If no labels are loaded, then display nothing
        if not self._label_metadata:
            self.btn_prev.configure(state="disabled")
            self.btn_next.configure(state="disabled")
            self.btn_print_all.configure(state="disabled")
            if self.btn_print_single:
                self.btn_print_single.configure(state="disabled")
            self.lbl_label_no.configure(text="Label 0 of 0")
            self.lbl_label_name.configure(text="No label loaded")
            self.preview_area.meta = None
            return

        # Clamp the given label index to the valid range
        label_idx = max(0, min(len(self._label_metadata) - 1, label_idx))
        self._label_idx = label_idx
        meta = self._label_metadata[label_idx]

        # Display the correct text in the labels
        self.lbl_label_no.configure(
            text=f"Label {label_idx + 1} of {len(self._label_metadata)}"
        )
        if meta.label_name:
            self.lbl_label_name.configure(text=meta.label_name)
        else:
            self.lbl_label_name.configure(
                text="(No label description available)"
            )

        # Selectively enable/disable the next/previous buttons
        if label_idx == 0:
            self.btn_prev.configure(state="disabled")
        else:
            self.btn_prev.configure(state="normal")

        # Selectively enable/disable the next/previous buttons
        if label_idx == len(self._label_metadata) - 1:
            self.btn_next.configure(state="disabled")
        else:
            self.btn_next.configure(state="normal")

        # Enable the print buttons
        self.btn_print_all.configure(state="normal")
        if self.btn_print_single:
            self.btn_print_single.configure(state="normal")

        # Preview the label
        self.preview_area.meta = meta

    def poll(self):
        self.root.after(50, self.poll)

    def run(self):
        self.root.after(50, self.poll)
        self.root.mainloop()

    ##################
    # Event handlers #
    ##################

    def print_single_click(self):
        self._action = "single"
        self.root.destroy()

    def print_all_click(self):
        self._action = "all"
        self.root.destroy()

    def prev_label_click(self):
        self.show_label(self._label_idx - 1)

    def next_label_click(self):
        self.show_label(self._label_idx + 1)
