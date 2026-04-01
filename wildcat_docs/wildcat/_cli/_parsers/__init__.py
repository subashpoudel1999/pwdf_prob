"""
Subpackage to build the CLI argument parser
----------
This subpackage contains resources to build the CLI parser. This includes distinct
subparsers for the various wildcat commands. Note that the parser for a given command
should be in a module of the same name (prepended with an underscore), and the
main function to build the subparser should be named "parser".
----------
Main Function:
    main    - Returns the parser for the wildcat CLI, including all subcommand parsers

Subcommand modules:
    _initialize     - Builds the parser for the "initialize" subcommand
    _preprocess     - Builds the parser for the "preprocess" subcommand
    _assess         - Builds the parser for the "assess" subcommand
    _export         - Builds the parser for the "export" subcommand

Utility modules:
    _descriptions   - Lengthy help text descriptions of subcommands and input files
    _utils          - Utility functions used to build multiple subcommand parsers    -
"""

from argparse import ArgumentParser

import wildcat
from wildcat._cli._parsers import _assess, _export, _initialize, _preprocess


def main() -> ArgumentParser:
    "Builds the parser for the wildcat CLI, including subcommand parsers"

    # Initialize the main parser
    parser = ArgumentParser(
        prog="wildcat",
        description="Assess and map post-fire debris-flow hazards",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {wildcat.version()}"
    )

    # Add the subcommand parsers
    subparsers = parser.add_subparsers(dest="command", title="Commands")
    for command in [_initialize, _preprocess, _assess, _export]:
        add_parser = getattr(command, "parser")
        add_parser(subparsers)
    return parser
