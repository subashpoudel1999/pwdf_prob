"""
Builds the CLI parser for the "export" command
----------
Functions:
    parser          - Adds the "export" parser to the subparsers
    _output_files   - Output file formats and names
    _properties     - Exported property options
    _formatting     - Default property formatting options
    _rename         - Renaming options
"""

from __future__ import annotations

import typing

from wildcat._cli._parsers._utils import create_subcommand, io_folders, logging, switch

if typing.TYPE_CHECKING:
    from argparse import ArgumentParser


def parser(subparsers) -> None:
    "Creates the parser for the export command"

    # Initialize with project folder, IO folders, logging, data files
    parser = create_subcommand(subparsers, "export")
    io_folders(parser, "assessment", "exports")
    logging(parser)

    # Add argument groups
    _output_files(parser)
    _properties(parser)
    _order(parser)
    _rename(parser)


def _output_files(parser: ArgumentParser) -> None:
    "Options for output files"

    parser = parser.add_argument_group("Output files")
    options = {
        "format": "The file format of exported files",
        "crs": "The coordinate reference system of the exported files",
        "prefix": "String prepended to the beginning of exported file names",
        "suffix": "String appended to the end of exported file names",
    }
    for name, description in options.items():
        parser.add_argument(
            f"--{name}",
            type=str,
            help=description,
        )


def _properties(parser: ArgumentParser) -> None:
    "Exported property options"

    parser = parser.add_argument_group("Properties")
    options = {
        "properties": "Properties that should be included in the exported files",
        "exclude-properties": "Properties removed from the base property list",
        "include-properties": "Properties added to the list, following the removal of excluded properties",
    }
    for name, description in options.items():
        parser.add_argument(
            f"--{name}",
            type=str,
            nargs="*",
            metavar="PROPERTY",
            help=description,
        )


def _order(parser: ArgumentParser) -> None:
    "Property order options"

    parser = parser.add_argument_group("Property Order")
    switch(parser, "no-order-properties", "Do not reorder exported properties")


def _rename(parser: ArgumentParser) -> None:
    "Renaming options"

    # Properties and prefixes
    parser = parser.add_argument_group("Renaming")
    parser.add_argument(
        "--rename",
        nargs=2,
        type=str,
        metavar=("FROM", "TO"),
        action="append",
        help="Specifies a custom name for an exported property or prefix. Can be used multiple times.",
    )
    parser.add_argument(
        "--rename-parameter",
        nargs="+",
        type=str,
        metavar=("PARAMETER", "RENAME"),
        action="append",
        help="Custom names for the values of a hazard modeling parameter. Can be used multiple times.",
    )
    switch(
        parser,
        "no-clean-names",
        "Do not convert hazard parameter indices to values in property names",
    )
