"""
Builds the CLI parser for the "intialize" command
----------
Main Function:
    parser  - Adds the "initialize" parser to the subparsers

Options:
    _config - Adds the config file verbosity option
    _inputs - Adds options for the 'inputs' subfolder
"""

from __future__ import annotations

import typing

from wildcat._cli._parsers._utils import create_subcommand, logging, switch

if typing.TYPE_CHECKING:
    from argparse import ArgumentParser


def parser(subparsers) -> None:
    "Builds the parser for the initialize command"

    parser = create_subcommand(
        subparsers,
        "initialize",
        project_help="The path for the project folder",
        alternate_config=False,
    )
    _config(parser)
    _inputs(parser)
    logging(parser)


def _config(parser: ArgumentParser) -> None:
    "Adds config file verbosity option"
    parser = parser.add_argument_group("Config File")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        choices=["none", "empty", "default", "full"],
        default="default",
        help="The type of configuration file to create",
    )


def _inputs(parser: ArgumentParser) -> None:
    "Adds input folder options"

    # Create group
    parser = parser.add_argument_group("Inputs Folder")
    parser = parser.add_mutually_exclusive_group()

    # Add file name option and option to disable inputs folder
    parser.add_argument(
        "--inputs",
        type=str,
        help="The name for the 'inputs' subfolder",
        metavar="NAME",
    )
    switch(parser, "no-inputs", "Do not initialize an 'inputs' subfolder")
