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

import PIL.Image

from brother_label.renderers.base import PageSize, Renderer, RenderOptions

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

    #######################
    # Protected functions #
    #######################

    def _do_open(self):
        pass

    def _do_close(self):
        pass

    def _do_compute_page_size(self, page_idx: int) -> PageSize:
        pass

    def _do_render(self, page_idx: int, page_size: PageSize) -> PIL.Image.Image:
        pass
