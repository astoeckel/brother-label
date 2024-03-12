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
import typing
from dataclasses import dataclass

from brother_label.labels import Color, FormFactor, Label


@dataclass
class Model(object):
    """
    This class represents a printer model. All specifics of a certain model
    and the opcodes it supports should be contained in this class.
    """

    name: str
    """
    A string identifier given to each model implemented. Eg. 'QL-500'.
    """

    min_max_length_dots: tuple[int, int]
    """
    Minimum and maximum number of rows or 'dots' that can be printed.
    Together with the dpi this gives the minimum and maximum length
    for continuous tape printing.
    """

    usb_product_id: int = 0x0000
    """
    USB product ID of the printer. Null indicates that the product ID is
    unknown.
    """

    usb_vendor_id: int = 0x04F9
    """
    USB vendor ID. The default id is for "Brother Industries, Ltd".
    """

    min_max_feed: tuple[int, int] = (35, 100)
    """
    The minimum and maximum amount of feeding a label.
    """

    number_bytes_per_row: int = 90
    """
    Number of bytes used to encode a raster line.
    """

    additional_offset_r: int = 0
    """
    Required additional offset from the right side.
    """

    supports_mode_setting: bool = True
    """
    Flag indicating whether the device supports the "mode setting" opcode.
    """

    supports_cutting: bool = True
    """
    Flag indicating whether the device supports automatically cutting the tape.
    """

    supports_expanded_mode: bool = True
    """
    Model has support for the 'expanded mode' opcode.
    (So far, all models that have cutting support do).
    """

    supports_compression: bool = True
    """
    Model has support for compressing the transmitted raster data.
    Some models with only USB connectivity don't support compression.
    """

    supports_two_color: bool = False
    """
    Support for two color printing (black/red/white)
    available only on some newer models.
    """

    num_invalidate_bytes: int = 200
    """
    Number of NULL bytes needed for the invalidate command.
    """

    @property
    def labels(self) -> list[Label]:
        return []


class ModelQL(Model):
    @property
    def labels(self):
        return super().labels + [
            # Continuous
            Label(
                ["12", "DK-22214"],
                (12, 0),
                FormFactor.ENDLESS,
                (142, 0),
                (106, 0),
                29,
                feed_margin=35,
            ),
            Label(
                ["18"],
                (18, 0),
                FormFactor.ENDLESS,
                (256, 0),
                (234, 0),
                171,
                feed_margin=14,
            ),
            Label(
                ["29", "DK-22210"],
                (29, 0),
                FormFactor.ENDLESS,
                (342, 0),
                (306, 0),
                6,
                feed_margin=35,
            ),
            Label(
                ["38", "DK-22225"],
                (38, 0),
                FormFactor.ENDLESS,
                (449, 0),
                (413, 0),
                12,
                feed_margin=35,
            ),
            Label(
                ["50", "DK-22223"],
                (50, 0),
                FormFactor.ENDLESS,
                (590, 0),
                (554, 0),
                12,
                feed_margin=35,
            ),
            Label(
                ["54", "DK-N55224"],
                (54, 0),
                FormFactor.ENDLESS,
                (636, 0),
                (590, 0),
                0,
                feed_margin=35,
            ),
            Label(
                ["62", "DK-22205", "DK-44205", "DK-44605"],
                (62, 0),
                FormFactor.ENDLESS,
                (732, 0),
                (696, 0),
                12,
                feed_margin=35,
            ),
            Label(
                ["62red", "DK-22251"],
                (62, 0),
                FormFactor.ENDLESS,
                (732, 0),
                (696, 0),
                12,
                feed_margin=35,
                color=Color.BLACK_RED_WHITE,
            ),
            # Die-Cut
            Label(
                ["17x54", "DK-11204"],
                (17, 54),
                FormFactor.DIE_CUT,
                (201, 636),
                (165, 566),
                0,
            ),
            Label(
                ["17x87", "DK-11203"],
                (17, 87),
                FormFactor.DIE_CUT,
                (201, 1026),
                (165, 956),
                0,
            ),
            Label(
                ["23x23", "DK-11221"],
                (23, 23),
                FormFactor.DIE_CUT,
                (272, 272),
                (202, 202),
                42,
            ),
            Label(
                ["29x42"],
                (29, 42),
                FormFactor.DIE_CUT,
                (342, 495),
                (306, 425),
                6,
            ),
            Label(
                ["29x90", "DK-11201"],
                (29, 90),
                FormFactor.DIE_CUT,
                (342, 1061),
                (306, 991),
                6,
            ),
            Label(
                ["39x90", "DK-11208"],
                (38, 90),
                FormFactor.DIE_CUT,
                (449, 1061),
                (413, 991),
                12,
            ),
            Label(
                ["39x48"],
                (39, 48),
                FormFactor.DIE_CUT,
                (461, 565),
                (425, 495),
                6,
            ),
            Label(
                ["52x29"],
                (52, 29),
                FormFactor.DIE_CUT,
                (614, 341),
                (578, 271),
                0,
            ),
            Label(
                ["54x29"],
                (54, 29),
                FormFactor.DIE_CUT,
                (630, 341),
                (598, 271),
                60,
            ),
            Label(
                ["60x86", "DK-11234", "DK-12343PK"],
                (60, 87),
                FormFactor.DIE_CUT,
                (708, 1024),
                (672, 954),
                18,
            ),
            Label(
                ["62x29", "DK-11209"],
                (62, 29),
                FormFactor.DIE_CUT,
                (732, 341),
                (696, 271),
                12,
            ),
            Label(
                ["62x100", "DK-11202"],
                (62, 100),
                FormFactor.DIE_CUT,
                (732, 1179),
                (696, 1109),
                12,
            ),
            # Round Die-Cut
            Label(
                ["d12", "DK-11219"],
                (12, 12),
                FormFactor.ROUND_DIE_CUT,
                (142, 142),
                (94, 94),
                113,
                feed_margin=35,
            ),
            Label(
                ["d24", "DK-11218"],
                (24, 24),
                FormFactor.ROUND_DIE_CUT,
                (284, 284),
                (236, 236),
                42,
            ),
            Label(
                ["d58", "DK-11207"],
                (58, 58),
                FormFactor.ROUND_DIE_CUT,
                (688, 688),
                (618, 618),
                51,
            ),
        ]


class ModelQL10(ModelQL):
    @property
    def labels(self):
        return super().labels + [
            # Continuous
            Label(
                ["102", "DK-22243"],
                (102, 0),
                FormFactor.ENDLESS,
                (1200, 0),
                (1164, 0),
                12,
                feed_margin=35,
            ),
            Label(
                ["104"],
                (104, 0),
                FormFactor.ENDLESS,
                (1227, 0),
                (1200, 0),
                -8,
                feed_margin=35,
            ),
            # Die-Cut
            Label(
                ["102x51", "DK-11240"],
                (102, 51),
                FormFactor.DIE_CUT,
                (1200, 596),
                (1164, 526),
                12,
            ),
            Label(
                ["102x152", "DK-11241"],
                (102, 153),
                FormFactor.DIE_CUT,
                (1200, 1804),
                (1164, 1660),
                12,
            ),
        ]


class ModelQL11(ModelQL10):
    @property
    def labels(self):
        return super().labels + [
            # Continuous
            Label(
                ["103", "DK-22246"],
                (104, 0),
                FormFactor.ENDLESS,
                (1224, 0),
                (1200, 0),
                12,
                feed_margin=35,
            ),
            # Die-Cut
            Label(
                ["103x164", "DK-11247"],
                (104, 164),
                FormFactor.DIE_CUT,
                (1224, 1941),
                (1200, 1822),
                12,
            ),
        ]


class ModelPT(Model):
    @property
    def labels(self):
        return super().labels + [
            # Continuous
            Label(
                ["12", "pt12"],
                (12, 0),
                FormFactor.PTOUCH_ENDLESS,
                (170, 0),
                (150, 0),
                213,
                feed_margin=14,
            ),
            Label(
                ["18", "pt18"],
                (18, 0),
                FormFactor.PTOUCH_ENDLESS,
                (256, 0),
                (234, 0),
                171,
                feed_margin=14,
            ),
            Label(
                ["24", "pt24"],
                (24, 0),
                FormFactor.PTOUCH_ENDLESS,
                (128, 0),
                (128, 0),
                0,
                feed_margin=14,
            ),
            Label(
                ["36", "pt36"],
                (36, 0),
                FormFactor.PTOUCH_ENDLESS,
                (512, 0),
                (454, 0),
                61,
                feed_margin=14,
            ),
        ]


class ModelPTE(Model):
    @property
    def labels(self):
        return super().labels + [
            # Continuous
            Label(
                ["6", "pte6"],
                (6, 0),
                FormFactor.PTOUCH_ENDLESS,
                (42, 0),
                (32, 0),
                48,
                feed_margin=14,
            ),
            Label(
                ["9", "pte9"],
                (9, 0),
                FormFactor.PTOUCH_ENDLESS,
                (64, 0),
                (50, 0),
                39,
                feed_margin=14,
            ),
            Label(
                ["12", "pte12"],
                (12, 0),
                FormFactor.PTOUCH_ENDLESS,
                (84, 0),
                (70, 0),
                29,
                feed_margin=14,
            ),
            Label(
                ["18", "pte18"],
                (18, 0),
                FormFactor.PTOUCH_ENDLESS,
                (128, 0),
                (112, 0),
                8,
                feed_margin=14,
            ),
            Label(
                ["24", "pte24"],
                (24, 0),
                FormFactor.PTOUCH_ENDLESS,
                (170, 0),
                (128, 0),
                0,
                feed_margin=14,
            ),
        ]


ALL_MODELS: list[Model] = [
    ModelQL(
        "QL-500",
        (295, 11811),
        supports_compression=False,
        supports_mode_setting=False,
        supports_expanded_mode=False,
        supports_cutting=False,
        usb_product_id=0x2015,
    ),
    ModelQL(
        "QL-550",
        (295, 11811),
        supports_compression=False,
        supports_mode_setting=False,
        usb_product_id=0x2016,
    ),
    ModelQL(
        "QL-560",
        (295, 11811),
        supports_compression=False,
        supports_mode_setting=False,
        usb_product_id=0x2027,
    ),
    ModelQL(
        "QL-570",
        (150, 11811),
        supports_compression=False,
        supports_mode_setting=False,
        usb_product_id=0x2028,
    ),
    ModelQL(
        "QL-580N",
        (150, 11811),
        usb_product_id=0x2029,
    ),
    ModelQL(
        "QL-600",
        (150, 11811),
        usb_product_id=0x20C0,
    ),
    ModelQL(
        "QL-650TD",
        (295, 11811),
        usb_product_id=0x201B,
    ),
    ModelQL(
        "QL-700",
        (150, 11811),
        supports_compression=False,
        supports_mode_setting=False,
        usb_product_id=0x2042,
    ),
    ModelQL(
        "QL-710W",
        (150, 11811),
        usb_product_id=0x2043,
    ),
    ModelQL(
        "QL-720NW",
        (150, 11811),
        usb_product_id=0x2044,
    ),
    ModelQL(
        "QL-800",
        (150, 11811),
        supports_two_color=True,
        supports_compression=False,
        num_invalidate_bytes=400,
        usb_product_id=0x209B,
    ),
    ModelQL(
        "QL-810W",
        (150, 11811),
        supports_two_color=True,
        num_invalidate_bytes=400,
        usb_product_id=0x209C,
    ),
    ModelQL(
        "QL-820NWB",
        (150, 11811),
        supports_two_color=True,
        num_invalidate_bytes=400,
        usb_product_id=0x209D,
    ),
    # QL 10 Series
    ModelQL10(
        "QL-1050",
        (295, 35433),
        number_bytes_per_row=162,
        additional_offset_r=44,
        usb_product_id=0x2020,
    ),
    ModelQL10(
        "QL-1060N",
        (295, 35433),
        number_bytes_per_row=162,
        additional_offset_r=44,
        usb_product_id=0x202A,
    ),
    # QL 11 Series
    ModelQL11(
        "QL-1100",
        (301, 35434),
        number_bytes_per_row=162,
        additional_offset_r=44,
        usb_product_id=0x20A7,
    ),
    ModelQL11(
        "QL-1100NWB",
        (301, 35434),
        number_bytes_per_row=162,
        additional_offset_r=44,
        usb_product_id=0x20A8,
    ),
    ModelQL11(
        "QL-1115NWB",
        (301, 35434),
        number_bytes_per_row=162,
        additional_offset_r=44,
        usb_product_id=0x20AC,
    ),
    # PT Series
    ModelPT(
        "PT-P750W",
        (31, 14172),
        number_bytes_per_row=16,
    ),
    ModelPT(
        "PT-P900W",
        (57, 28346),
        number_bytes_per_row=70,
    ),
    ModelPT(
        "PT-P950NW",
        (57, 28346),
        number_bytes_per_row=70,
    ),
    # PTE Series
    ModelPTE(
        "PT-E550W",
        (31, 14172),
        number_bytes_per_row=16,
        usb_product_id=0x2060,
    ),
]
