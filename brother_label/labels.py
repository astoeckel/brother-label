from dataclasses import dataclass
from enum import IntEnum


class FormFactor(IntEnum):
    """
    Enumeration representing the form factor of a label.
    The labels for the Brother QL series are supplied either as die-cut
    (pre-sized), or for more flexibility the continuous label tapes offer the
    ability to vary the label length.
    """

    #: rectangular die-cut labels
    DIE_CUT = 1
    #: endless (continuous) labels
    ENDLESS = 2
    #: round die-cut labels
    ROUND_DIE_CUT = 3
    #: endless P-touch labels
    PTOUCH_ENDLESS = 4


class Color(IntEnum):
    """
    Enumeration representing the colors to be printed on a label. Most labels
    only support printing black on white. Some newer ones can also print in
    black and red on white.
    """

    #: The label can be printed in black & white.
    BLACK_WHITE = 0
    #: The label can be printed in black, white & red.
    BLACK_RED_WHITE = 1


@dataclass
class Label:
    """
    This class represents a label. All specifics of a certain label
    and what the rasterizer needs to take care of depending on the
    label choosen, should be contained in this class.
    """

    # A string identifier given to each label that can be selected. Eg. '29'.
    identifiers: list[str]
    # The tape size of a single label (width, lenght) in mm. For endless labels, the
    # length is 0 by definition.
    tape_size: tuple[int, int]
    # The type of label
    form_factor: FormFactor
    # The total area (width, length) of the label in dots (@300dpi).
    dots_total: tuple[int, int]
    # The printable area (width, length) of the label in dots (@300dpi).
    dots_printable: tuple[int, int]
    # The required offset from the right side of the label in dots to obtain a centered
    # printout.
    offset_r: int
    # An additional amount of feeding when printing the label.
    # This is non-zero for some smaller label sizes and for endless labels.
    feed_margin: int = 0
    # Some labels allow printing in red, most don't.
    color: Color = Color.BLACK_WHITE

    @property
    def name(self) -> str:
        if self.form_factor in (FormFactor.DIE_CUT,):
            out = "{}mm x {}mm die-cut".format(*self.tape_size)
        elif self.form_factor in (FormFactor.ROUND_DIE_CUT,):
            out = f"{self.tape_size[0]}mm round die-cut"
        else:
            out = f"{self.tape_size[0]}mm endless"

        if self.color == Color.BLACK_RED_WHITE:
            out += " (black/red/white)"

        return out
