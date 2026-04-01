"""
wildcat CLI entry point
----------
This module provides the entry point for the wildcat CLI (via the "main"
function). In brief, this function parses CLI args, and uses them to determine
a wildcat command and command args. The function then configures a console logger
(and optional file-based log), and then runs the appropriate wildcat command.
----------
Functions:
    main            - The entry point function for the wildcat CLI
    _configure_log  - Configures the log for a wildcat command
"""

from __future__ import annotations

import logging
import sys
import typing

import wildcat
from wildcat._cli import _kwargs, _parsers

if typing.TYPE_CHECKING:
    from argparse import Namespace


def main(args: list[str] = None) -> None:
    """
    Implements the wildcat command line interface (CLI)
    ----------
    main(args)
    Runs wildcat as if called from the command line. The "args" input should be
    a list of strings, as would be used to run wildcat from the CLI. Note that
    this list should not contain the "wildcat" string itself - only the strings
    following "wildcat" should be included.

    Note that this function will configure the wildcat logging format. It will
    also set the system traceback limit to 0 when an uncaught exception occurs,
    unless the "-t" or "--traceback" flags are included in the args.
    ----------
    Inputs:
        args: A list of strings that would follow the "wildcat" string when
            calling wildcat from the command line
    """

    # Parse the CLI inputs and convert to function kwargs
    parser = _parsers.main()
    args = parser.parse_args(args)
    converter = getattr(_kwargs, args.command)
    kwargs = converter(args)

    # Configure the logging format
    _configure_log(args)

    # Run the command, suppressing tracebacks unless explicitly enabled
    command = getattr(wildcat, args.command)
    try:
        command(**kwargs)
    except Exception:
        if not args.show_traceback:
            sys.tracebacklimit = 0
        raise


def _configure_log(args: Namespace) -> None:
    """Configures the logger for a wildcat command. Includes a console handler
    that prints basic messages at the indicated verbosity level. Optionally includes
    a file handler with DEBUG logging level and timestamps."""

    # Initialize logger
    logger = logging.getLogger(f"wildcat.{args.command}")
    logger.setLevel(logging.DEBUG)

    # Parse the verbosity for the console log. (File log is always verbose)
    if args.quiet:
        level = logging.WARNING
    elif args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    # Configure the console log
    console = logging.StreamHandler()
    console.setLevel(level)
    format = logging.Formatter("%(message)s")
    console.setFormatter(format)
    logger.addHandler(console)

    # Configure file logs
    if args.log is not None:
        file = logging.FileHandler(args.log)
        file.setLevel(logging.DEBUG)
        format = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
        file.setFormatter(format)
        logger.addHandler(file)
