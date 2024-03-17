# Brother Label Printer User-Space Driver and Printing Utility
# Copyright (C) 2015-2024  Andreas Stöckel
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

from brother_label.cli import cli
from brother_label.exceptions import BrotherQLError


def main():
    import sys

    try:
        cli()
        sys.exit(0)
    except BrotherQLError as e:
        logging.error(e.args[0])
        sys.exit(1)
    except PermissionError as e:
        logging.error(e.args[0])
        sys.exit(1)
    except FileNotFoundError as e:
        logging.error(f"File not found: {e.args[0]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
