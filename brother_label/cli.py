# ruff: noqa: T201

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
import os
import string
import sys
import typing

import click

try:
    import colorlog
except ImportError:
    colorlog = None

logger = logging.getLogger(__name__)

from brother_label import backends, exceptions, models

###############################################################################
# Utility functions                                                           #
###############################################################################


def _print_table(
    f: typing.TextIO,
    header: typing.Sequence[str],
    rows: typing.Sequence[typing.Sequence[typing.Any]],
):
    def to_str(x):
        if x is None:
            return ""
        if isinstance(x, str):
            return x
        if isinstance(x, list) or isinstance(x, tuple):
            return ", ".join(to_str(y) for y in x)
        return repr(x)

    use_colour = _cli_use_colour()

    def write_row(row, bold: bool = False):
        bold = bold and use_colour
        for i, col in enumerate(row):
            if i > 0:
                f.write("│")
            s = to_str(col)
            f.write(" ")

            need_reset = False
            if bold:
                f.write("\033[1m")
                need_reset = True
            if use_colour and s == "✔":
                f.write("\033[32m")
                need_reset = True
            if use_colour and s == "✘":
                f.write("\033[31m")
                need_reset = True

            f.write(s)

            if need_reset:
                f.write("\033[0m")
            f.write(" " * (n_cols[i] - len(s)))
            f.write(" ")
        f.write("\n")

    # Determine the column lengths
    n_cols = [len(to_str(x)) for x in header]
    for row in rows:
        assert len(row) == len(header)
        for i, col in enumerate(row):
            n_cols[i] = max(n_cols[i], len(to_str(col)))

    # Print the actual table
    write_row(header, bold=True)
    for i, n in enumerate(n_cols):
        if i > 0:
            f.write("╪")
        f.write("═" * (2 + n))
    f.write("\n")
    for row in rows:
        write_row(row)


def _normalise(x: str):
    alnum = {*string.ascii_letters, *string.digits}
    return "".join(c for c in x.lower() if c in alnum)


def _fuzzy_match(
    needle: str,
    haystack: typing.Iterable[typing.Union[str, tuple[str, typing.Any]]],
    kind: str = "identifier",
) -> typing.Any:
    import difflib

    # Match the identifier after passing it through the `normalise` function
    possible_names: dict[str, str] = {}
    needle_norm = _normalise(needle)
    for obj in haystack:
        if isinstance(obj, str):
            obj_name, obj = obj, obj
        else:
            obj_name, obj = obj
        obj_name_norm = _normalise(obj_name)
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


def _discover(
    *,
    filter_backend_name: typing.Optional[str] = None,
    filter_model_name: typing.Optional[str] = None,
) -> list[backends.DeviceInfo]:
    """
    Automatically discovers all label printers. Filters devices by the given
    backend/model name.
    """

    # If no specific backend is given, then search all backends for devices
    if filter_backend_name is None:
        backend_names = backends.ALL_BACKEND_NAMES
    else:
        backend_names = [filter_backend_name]

    # Discover devices from all backends
    device_infos: list[backends.DeviceInfo] = []
    for backend_name in backend_names:
        device_infos += backends.backend_class(backend_name).discover()

    # Resolve USB Product IDs and model names to known models
    for device_info in device_infos:
        for model in models.ALL_MODELS:
            # Prefer the model name stored in our device database over the
            # model name read out via USB
            if device_info.model:
                if _normalise(device_info.model) == _normalise(model.name):
                    device_info.model = model.name

            # If we have a USB product and vendor ID match, then fill in
            # the model name from our device database
            usb_product_id = f"{model.usb_product_id:04x}"
            usb_vendor_id = f"{model.usb_vendor_id:04x}"
            if (usb_product_id == device_info.usb_product_id) and (
                usb_vendor_id == device_info.usb_vendor_id
            ):
                device_info.model = model.name

    # Filter by the given model name
    if filter_model_name is not None:
        filter_model_name = _normalise(filter_model_name)
        device_infos = [
            d for d in device_infos if _normalise(d.model) == filter_model_name
        ]

    # Mark devices as supported if we know the model
    for device_info in device_infos:
        device_info.supported = False
        for model in models.ALL_MODELS:
            if _normalise(device_info.model) == _normalise(model.name):
                device_info.supported = True

    # Sort the discovered devices by quality
    sorted_device_infos = []
    for device_info in device_infos:
        # Prefer descriptors where we were actually able to find the model
        has_model = bool(device_info.model)

        # Prefer descriptor where we have a serial number
        has_serial = bool(device_info.serial)

        # Prefer the linux kernel backend over other backends
        is_linux_backend = bool(device_info.backend == "linux")

        # Use the last plugged device (typically USB device numbers increase)
        usb_dev_num = device_info.usb_dev_num

        # Use the newest model
        model = str(device_info.model)

        # Assemble a tuple containing the various sort criteria
        sorted_device_infos.append(
            (
                device_info,
                device_info.supported,
                has_model,
                has_serial,
                is_linux_backend,
                usb_dev_num,
                model,
            )
        )
    sorted_device_infos = sorted(
        sorted_device_infos, key=lambda x: x[1:], reverse=True
    )

    # Now that the devices are sorted, assign a priority to them and return
    # the list
    res = []
    for i, device_info in enumerate(sorted_device_infos):
        res.append(device_info[0])
        res[-1].priority = len(sorted_device_infos) - i
    return res


def _resolve_model(model_name: str) -> models.Model:
    return _fuzzy_match(
        model_name, ((dev.name, dev) for dev in models.ALL_MODELS), "model"
    )


def _resolve_backend_name(backend: str) -> str:
    from brother_label import backends

    return _fuzzy_match(backend, backends.ALL_BACKEND_NAMES, "backend")


def _instantiate_backend_and_model(
    *,
    device_url: typing.Optional[str] = None,
    backend_name: typing.Optional[str] = None,
    model_name: typing.Optional[str] = None,
    need_backend: bool = True,
) -> tuple[backends.Backend, models.Model]:
    # If no device is given, then automatically find a device
    if not device_url:
        device_infos = _discover(
            filter_model_name=model_name,
            filter_backend_name=backend_name,
        )
        if need_backend and (not device_infos or not device_infos[0].supported):
            raise exceptions.BrotherQLError(
                "Did not discover a supported label printer. Double-check that "
                "the printer is plugged into the computer and powered on. "
                "Alternatively, to skip auto-discovery, explicitly override "
                "the target device using the -d/--device option."
            )
        if device_infos:
            device_info = device_infos[0]
            device_url = device_info.device_url
            if not backend_name:
                backend_name = device_info.backend
            if not model_name:
                model_name = device_info.model

    # Try to determine the backend that we're printing to
    if (backend_name is None) and device_url:
        backend_name = backends.guess_backend_name(device_url)

    assert (backend_name is not None) or (not need_backend)

    # If we have no model, then try to determine the model that we're printing
    # to
    if (model_name is None) and backend_name:
        model_names = set()
        for device_info in backends.backend_class(backend_name).discover(
            device_url
        ):
            model_names.add(device_info.model)
        if len(model_names) == 1:
            model_name = next(iter(model_names))

    if model_name is None:
        raise exceptions.BrotherQLError(
            "Could not determine the model of printer we're printing to. "
            "Please explicitly specify the model using the -m/--model option."
        )

    # Convert the model name into an internal model reference
    model = None
    for m in models.ALL_MODELS:
        if _normalise(model_name) == _normalise(m.name):
            model = m
            break
    if model is None:
        raise exceptions.BrotherQLError(
            f"Model {model_name!r} is not supported."
        )

    # Instantiate the backend
    if backend_name and device_url:
        backend = backends.backend_factory(backend_name, device_url)
    else:
        backend = None

    # Return the instantiated
    return backend, model


def _cli_use_colour() -> bool:
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
    if _cli_use_colour():
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
        logging.root.setLevel(level)
        logging.root.addHandler(handler)
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
    type=click.Choice(backends.ALL_BACKEND_NAMES),
    default=None,
    help="Printer backend. One of "
    f"{{{', '.join(['auto'] + backends.ALL_BACKEND_NAMES)}}}. "
    "Auto-detects backend if none is given.",
    envvar="BROTHER_LABEL_BACKEND",
)
@click.option(
    "-m",
    "--model",
    type=str,
    default=None,
    help="Printer model name (such as `QL-600`). Use `auto` to auto-detect.",
    envvar="BROTHER_LABEL_MODEL",
)
@click.option(
    "-d",
    "--device",
    type=str,
    default=None,
    envvar="BROTHER_LABEL_DEVICE",
    help="The device URL for the printer. Leave blank to use the "
    "first detected printer. This could be a string "
    "like `tcp://192.168.1.21:9100` for a networked printer or "
    "`usb://0x04f9:0x2015/000M6Z401370` for a printer connected "
    "via USB.",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable debug messages.")
@click.version_option()
@click.pass_context
def cli(ctx, backend, model, device, verbose):
    # Resolve the special "auto" string to `None`. This way the user can
    # override environment variables.
    if backend and (backend.lower() == "auto"):
        backend = None
    if model and (model.lower() == "auto"):
        model = None
    if device and (device.lower() == "auto"):
        device = None

    # Canonicalize the backend and model name
    if backend is not None:
        backend = _resolve_backend_name(backend)
    if model is not None:
        model = _resolve_model(model).name

    # Copy the options used by all backends into the global "meta" variable
    ctx.meta["backend"] = backend
    ctx.meta["model"] = model
    ctx.meta["device"] = device

    # Enable logging, including coloured level names
    _setup_logging(logging.DEBUG if verbose else logging.INFO)


###############################################################################
# Discover command                                                            #
###############################################################################


@cli.command("discover", help="Automatically discover available printers")
@click.pass_context
def discover_cmd(ctx):
    device_infos = _discover(
        filter_backend_name=ctx.meta["backend"],
        filter_model_name=ctx.meta["model"],
    )

    n_devices = len(device_infos)
    n_supported = sum(1 for d in device_infos if d.supported)
    if not device_infos:
        raise exceptions.BrotherQLError("No device discovered")
    else:
        logger.info(
            f"Discovered {n_devices} devices ({n_supported}/{n_devices} are supported)."
        )

    header = [
        "Manufacturer",
        "Model",
        "Serial",
        "Device URL",
        "Default",
        "Supported",
    ]
    rows = []
    for i, device_info in enumerate(device_infos):
        rows.append(
            [
                device_info.manufacturer,
                device_info.model,
                device_info.serial,
                device_info.device_url,
                "✔" if i == 0 else "",
                "✔" if device_info.supported else "✘",
            ]
        )
    _print_table(sys.stdout, header, rows)
    sys.stdout.flush()


###############################################################################
# Info commands                                                               #
###############################################################################


@cli.group(
    "info", help="Commands for listing available backends, models and targets"
)
def info_group():
    pass


@info_group.command("devices", help="Lists known devices/printer models")
def info_devices_cmd():
    print(" ".join(model.name for model in models.ALL_MODELS))


@info_group.command(
    "labels",
    help="List label types supported by the selected device or all "
    "label types if no device has been specified",
)
@click.pass_context
def info_labels_cmd(ctx):
    from brother_label import models
    from brother_label.labels import FormFactor

    if ctx.meta["model"]:
        ms = [_resolve_model(ctx.meta["model"])]
    else:
        ms = models.ALL_MODELS

    header = [
        "Name",
        "Dots (printable)",
        "Label identifiers",
    ]

    for i, model in enumerate(ms):
        if i:
            print()
        print(f"{model.name}:")

        rows = []
        for label in model.labels:
            if label.form_factor in (
                FormFactor.DIE_CUT,
                FormFactor.ROUND_DIE_CUT,
            ):
                dp_fmt = "{0:4d} x {1:4d}"
            elif label.form_factor in (
                FormFactor.ENDLESS,
                FormFactor.PTOUCH_ENDLESS,
            ):
                dp_fmt = "{0:4d}"
            else:
                dp_fmt = " - unknown - "

            rows.append(
                [
                    label.name,
                    dp_fmt.format(*label.dots_printable),
                    label.identifiers,
                ]
            )

        _print_table(sys.stdout, header, rows)


@info_group.command("env", help="Prints environment information for debugging")
def env_cmd():
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


###############################################################################
# Debug commands                                                              #
###############################################################################


@cli.group("debug", help="Printer commands used for debugging")
def debug_group():
    pass


@debug_group.group("analyze", help="Interprets a raw instruction file")
@click.argument("instructions", type=click.File("rb"))
@click.option(
    "-f",
    "--filename-format",
    default="label{counter:04d}.png",
    type=str,
    help="Filename format string. Default is: label{counter:04d}.png.",
)
def analyze_cmd(instructions: typing.BinaryIO, filename_format: str):
    from .reader import BrotherQLReader

    br = BrotherQLReader(instructions, filename_fmt=filename_format)
    br.analyse()


@debug_group.command("send", help="Send a raw instruction file to the printer")
@click.argument("instructions", type=click.File("rb"))
def send_cmd(ctx, instructions: typing.BinaryIO):
    # TODO
    pass


###############################################################################
# Print command                                                               #
###############################################################################


@cli.command("print", help="Prints a label")
@click.argument(
    "args",
    nargs=-1,
    type=str,
    metavar="FILE_OR_TEXT [FILE_OR_TEXT] ...",
)
@click.option(
    "-f",
    "--file",
    multiple=True,
    type=str,
    help="Explicitly prints a file",
)
@click.option(
    "-t",
    "--text",
    multiple=True,
    type=str,
    help="Explicitly prints a text label",
)
@click.option("--no-preview", is_flag=True, help="Disables the print preview.")
@click.option(
    "-l",
    "--label",
    envvar="BROTHER_QL_LABEL",
    required=True,
    help="The label (size, type - die-cut or endless). Run `brother_label "
    "info labels` for a full list including ideal pixel dimensions.",
)
@click.option(
    "-r",
    "--rotate",
    type=click.Choice(("auto", "0", "90", "180", "270")),
    default="auto",
    help="Angle in degrees by which to rotate the label (counter clock-wise).",
)
@click.option(
    "--600dpi",
    "dpi_600",
    is_flag=True,
    help="Print with 600x300 dpi available on some models. Provide your image "
    "as 600x600 dpi; perpendicular to the feeding the image will be "
    "resized to 300dpi.",
)
@click.option(
    "--low-quality",
    is_flag=True,
    help="Print with low quality (faster). Default is high quality.",
)
@click.option(
    "--borderless",
    is_flag=True,
    help="If specified, prints the document ",
)
@click.option(
    "--no-compress",
    is_flag=True,
    help="Disable compression.",
)
@click.option(
    "--no-cut",
    is_flag=True,
    help="Don't cut the tape after printing the label.",
)
@click.option(
    "--no-resize",
    is_flag=True,
    help="Expect the resolution of raster images to exactly match the number "
    "of dots in the printable area.",
)
@click.pass_context
def print_cmd(ctx, args, file, text, **kwargs):
    import brother_label.spool

    # Ensure that there is at least one render target
    if (not args) and (not file) and (not text):
        raise exceptions.BrotherQLError(
            "Requiring at least one file or text to print"
        )

    # Instantiate the backend and fetch the model
    backend, model = _instantiate_backend_and_model(
        device_url=ctx.meta["device"],
        backend_name=ctx.meta["backend"],
        model_name=ctx.meta["model"],
        need_backend=False,
    )

    # Fetch the correct label
    label = _fuzzy_match(
        kwargs["label"], ((id, l) for l in model.labels for id in l.identifiers)
    )

    # Create a print spool directory and rasterize the individual files
    with brother_label.spool.Spool(model, label) as spool:
        # Convert the options passed on the command line to internal render
        # options
        spool.rotate = kwargs["rotate"]
        spool.high_quality = not kwargs["low_quality"]

        # Render all render queue elements to the spool
        for f in file:
            spool.render(f, kind="file")
        for t in text:
            spool.render(t, kind="text")
        for arg in args:
            spool.render(arg, kind="auto")

        # Unless previews were deactivated, open a preview window
        if not kwargs["no_preview"]:
            import brother_label.gui

            # Render the labels into preview images and fetch the corresponding
            # metadata
            label_metadata = spool.preview()

            # Assemble a human-readable printer name
            printer_name = model.name
            if backend is not None:
                printer_name += f" ({backend.device_url})"
            else:
                printer_name += " (no connection)"

            # View the metadata
            gui = brother_label.gui.Gui(
                label_metadata, printer_name=printer_name
            )
            gui.run()
            if gui.action is None:
                return

        # If we have not acquired a backend at this point, then do so now!
        if not backend:
            backend, model = _instantiate_backend_and_model(
                device_url=ctx.meta["device"],
                backend_name=ctx.meta["backend"],
                model_name=model.name,
            )

        # Do the actual printing!
        spool.print(backend)
