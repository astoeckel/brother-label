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

"""
Provides the command-line parser and main entry point.
"""
import logging
import typing

import click

try:
    import colorlog
except ImportError:
    colorlog = None

logger = logging.getLogger(__name__)

from brother_label import backends, exceptions


###############################################################################
# Utility functions                                                           #
###############################################################################


def _fuzzy_match(
    needle: str,
    haystack: typing.Iterable[typing.Union[str, tuple[str, typing.Any]]],
    kind: str = "identifier",
) -> typing.Any:
    import difflib
    import string

    # Helper function for stripping all non-alphanumeric characters from the
    # given string
    def normalise(x: str):
        alnum = {*string.ascii_letters, *string.digits}
        return "".join(c for c in x.lower() if c in alnum)

    # Match the identifier after passing it through the `normalise` function
    possible_names: dict[str, str] = {}
    needle_norm = normalise(needle)
    for obj in haystack:
        if isinstance(obj, str):
            obj_name, obj = obj, obj
        else:
            obj_name, obj = obj
        obj_name_norm = normalise(obj_name)
        possible_names[obj_name_norm] = obj_name
        if obj_name_norm == needle_norm:
            return obj

    # If that didn't work, try to provide a helpful error message.
    close_matches: typing.Sequence[str] = difflib.get_close_matches(
        needle_norm, possible_names.keys()
    )
    if close_matches:
        raise exceptions.BrotherQLUnknownId(
            f"Unknown {kind} {needle!r}. Close matches are: "
            f"{', '.join(sorted(possible_names[x] for x in close_matches))}."
        )

    raise exceptions.BrotherQLUnknownId(
        f"Unknown {kind} {needle!r}. Possible values are: "
        f"{', '.join(sorted(possible_names.values()))}."
    )


def _resolve_device(device: str):
    from brother_label import devices

    return _fuzzy_match(
        device, ((dev.name, dev) for dev in devices.ALL_DEVICES), "device"
    )


def _resolve_backend_name(backend: str):
    from brother_label import backends

    return _fuzzy_match(backend, backends.ALL_BACKENDS, "backend")


def _use_colour() -> bool:
    import os
    import sys

    # Do not use colour if the "colorlog" package is not installed
    if colorlog is None:
        return False

    # Honour the "NO_COLOR" environment variable (see https://no-color.org/)
    if ("NO_COLOR" in os.environ) and os.environ["NO_COLOR"]:
        return False

    # Do not use colour if we're writing to something that is not a TTY
    return os.isatty(sys.stderr.fileno())


def _setup_logging(level: int = logging.INFO):
    # Either use fancy colours for logging, or use the default formatter
    if _use_colour():
        handler = colorlog.StreamHandler()
        handler.setFormatter(
            colorlog.ColoredFormatter(
                "%(log_color)s[%(levelname)-5s]%(reset)s %(message)s",
                datefmt=None,
                reset=True,
                log_colors={
                    "DEBUG": "reset",
                    "INFO": "blue",
                    "WARN": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red",
                },
            )
        )
        logger.setLevel(level)
        logger.addHandler(handler)
    else:
        logging.basicConfig(level=level, format="[%(levelname)-5s] %(message)s")

    # Abbreviate "WARNING" so it fits in with the reset of the level names
    logging.addLevelName(logging.WARNING, "WARN")


###############################################################################
# Top-level CLI command                                                       #
###############################################################################


@click.group()
@click.option(
    "-b",
    "--backend",
    type=click.Choice(backends.available_backends),
    default="auto",
    help="Printer backend. One of "
    f"{{{', '.join(backends.available_backends)}}}. "
    "Default is `auto`.",
    envvar="BROTHER_LABEL_BACKEND",
)
@click.option(
    "-d",
    "--device",
    type=str,
    default=None,
    help="Printer model name (such as `QL-600`). Leave blank to "
    "detect automatically.",
    envvar="BROTHER_LABEL_MODEL",
)
@click.option(
    "-t",
    "--target",
    type=str,
    default=None,
    envvar="BROTHER_LABEL_TARGET",
    help="The identifier for the printer. Leave blank to use the "
    "first detected printer. This could be a string "
    "like `tcp://192.168.1.21:9100` for a networked printer or "
    "`usb://0x04f9:0x2015/000M6Z401370` for a printer connected "
    "via USB.",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable debug messages.")
@click.version_option()
@click.pass_context
def cli(ctx, backend, device, target, verbose):
    # Copy the options used by all backends into the global "meta" variable
    ctx.meta["backend"] = backend
    ctx.meta["device"] = device
    ctx.meta["target"] = target

    # Enable logging, including coloured level names
    _setup_logging(logging.DEBUG if verbose else logging.INFO)


###############################################################################
# Discover command                                                            #
###############################################################################


@cli.command("discover", help="Automatically discover available printers")
@click.pass_context
def discover_cmd(ctx):
    from brother_label import backends

    if ctx.meta["backend"]:
        backend_names = [_resolve_backend_name(ctx.meta["backend"])]
    else:
        backend_names = [backends.ALL_BACKENDS]

    for backend_name in backend_names:
        backend = backends.backend_factory(backend_name)
        backend.discover()


###############################################################################
# Info commands                                                               #
###############################################################################


@cli.group(help="Commands for listing available backends, models and targets")
def info():
    pass


@info.command("devices", help="Lists known devices/printer models")
def info_devices_cmd():
    from brother_label import devices

    print(" ".join(dev.name for dev in devices.ALL_DEVICES))


@info.command(
    "labels",
    help="List label types supported by the selected device or all "
    "label types if no device has been specified",
)
@click.pass_context
def info_labels_cmd(ctx):
    from brother_label import devices
    from brother_label.labels import FormFactor

    if ctx.meta["device"]:
        devs = [_resolve_device(ctx.meta["device"])]
    else:
        devs = devices.ALL_DEVICES

    fmt = "{name:36s} {dots_printable:24s} {identifiers:26s}"
    print(
        fmt.format(
            name="\tName",
            dots_printable="Printable (dots)",
            identifiers="Identifiers",
        )
    )
    print("=" * 128)

    for device in devs:
        print("" + device.identifier)

        for label in device.labels:
            if label.form_factor in (
                FormFactor.DIE_CUT,
                FormFactor.ROUND_DIE_CUT,
            ):
                dp_fmt = "{0:4d} x {1:d}"
            elif label.form_factor in (
                FormFactor.ENDLESS,
                FormFactor.PTOUCH_ENDLESS,
            ):
                dp_fmt = "{0:4d}"
            else:
                dp_fmt = " - unknown - "

            print(
                fmt.format(
                    name=f"\t{label.name}",
                    dots_printable=dp_fmt.format(*label.dots_printable).strip(),
                    identifiers=", ".join(label.identifiers),
                )
            )

        print()


@info.command("env", help="Prints environment information for debugging")
@click.pass_context
def env_cmd(ctx, *args, **kwargs):
    import platform
    import shutil
    import sys

    from pkg_resources import get_distribution

    print("\n##################\n")
    print("Information about the running environment of brother_label.")
    print("(Please provide this information when reporting any issue.)\n")
    # computer
    print("About the computer:")
    for attr in (
        "platform",
        "processor",
        "release",
        "system",
        "machine",
        "architecture",
    ):
        print("  * " + attr.title() + ":", getattr(platform, attr)())
    # Python
    print("About the installed Python version:")
    py_version = str(sys.version).replace("\n", " ")
    print("  *", py_version)
    # brother_label
    print("About the brother_label package:")
    pkg = get_distribution("brother_label")
    print("  * package location:", pkg.location)
    print("  * package version: ", pkg.version)
    try:
        cli_loc = shutil.which("brother_label")
    except:
        cli_loc = "unknown"
    print("  * brother_label CLI path:", cli_loc)
    # brother_label's requirements
    print("About the requirements of brother_label:")
    fmt = "  {req:14s} | {spec:10s} | {ins_vers:17s}"
    print(
        fmt.format(
            req="requirement", spec="requested", ins_vers="installed version"
        )
    )
    print(fmt.format(req="-" * 14, spec="-" * 10, ins_vers="-" * 17))
    requirements = list(pkg.requires())
    requirements.sort(key=lambda x: x.project_name)
    for req in requirements:
        proj = req.project_name
        req_pkg = get_distribution(proj)
        spec = " ".join(req.specs[0]) if req.specs else "any"
        print(fmt.format(req=proj, spec=spec, ins_vers=req_pkg.version))
    print("\n##################\n")
