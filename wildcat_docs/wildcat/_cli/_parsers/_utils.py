"""
Utility functions used to build multiple parsers
----------
Functions:
    create_subcommand   - Returns a subcommand parser with the project folder as a positional argument
    io_folders          - Adds an IO folder argument group to a parser
    logging             - Adds a logging argument group to a parser
    switch              - Adds a boolean switch to an argument group

Utilities:
    _add_folder         - Adds a folder argument to a parser
"""

from __future__ import annotations

import typing
from argparse import RawDescriptionHelpFormatter
from pathlib import Path

from wildcat._cli._parsers import _descriptions

if typing.TYPE_CHECKING:
    from argparse import ArgumentParser


def create_subcommand(
    subparsers,
    command: str,
    project_help: str = "The folder containing the configuration file for the command",
    alternate_config: bool = True,
) -> ArgumentParser:
    """Creates a subcommand parser with the project folder as a positional argument.
    Also adds an error traceback option"""

    # Add the subcommand help text
    description = getattr(_descriptions, command)
    parser = subparsers.add_parser(
        command,
        help=description[0],
        description=description[1],
        formatter_class=RawDescriptionHelpFormatter,
    )

    # Add the project folder as the first positional argument
    parser.add_argument(
        "project",
        nargs="?",
        type=Path,
        help=project_help,
    )

    # Add a traceback option
    parser.add_argument(
        "-t",
        "--show-traceback",
        action="store_true",
        help="Show the full traceback when an error occurs",
    )

    # Add alternate config option
    if alternate_config:
        parser.add_argument(
            "-c",
            "--config",
            metavar="PATH",
            type=Path,
            help="Specify an alternate configuration file",
        )
    return parser


def io_folders(parser: ArgumentParser, input: str, output: str) -> None:
    "Adds an IO folder argument group to a subcommand parser"

    io = parser.add_argument_group(
        "IO Folders",
        "Paths should either be absolute, or relative to the project folder",
    )
    _add_folder(
        io,
        "i",
        input,
        f"Default folder in which to search for {_descriptions.folders[input]}",
    )
    _add_folder(
        io, "o", output, f"Folder in which to save {_descriptions.folders[output]}"
    )


def _add_folder(
    parser: ArgumentParser, short: str, name: str, description: str
) -> None:
    "Adds a folder argument to a parser"

    parser.add_argument(
        f"-{short}",
        f"--{name}",
        type=Path,
        help=description,
        metavar="FOLDER",
    )


def logging(parser: ArgumentParser) -> None:
    "Adds logging argument group (quiet, verbose, and file) to a parser"

    # Create the logging group
    logging = parser.add_argument_group("Logging")
    switches = logging.add_mutually_exclusive_group()

    # Add quiet and verbose options
    switches.add_argument(
        "-q", "--quiet", action="store_true", help="Do not print progress messages"
    )
    switches.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Prints more detailed progress messages (useful for debugging)",
    )

    # Add file logging option
    logging.add_argument(
        "--log",
        type=Path,
        metavar="PATH",
        help="Logs detailed progress to the indicated file",
    )


def switch(parser: ArgumentParser, name: str, help: str) -> None:
    "Adds a boolean switch to an argument group"
    parser.add_argument(f"--{name}", action="store_true", help=help)
