"""
Functions that record configuration settings to file
----------
The functions in this module facilitate saving configuration settings to file.
Each function takes an open file object, and writes some formatted text based on
the configuration settings.
----------
Main Functions:
    version     - Writes the wildcat version at the top of the config file
    paths       - Records a set of config values that are all paths
    section     - Writes a group of configuration values under a section heading

Internal:
    _title      - Writes a section title
    _parameter  - Writes a 'name = value' line
"""

from __future__ import annotations

import typing
from pathlib import Path

import wildcat

if typing.TYPE_CHECKING:
    from typing import Any, TextIO

    from wildcat.typing import PathDict

#####
# Main Blocks
#####


def version(file: TextIO, title: str) -> None:
    "Writes the wildcat version at the top of the configuration file"
    file.write(f"# {title} for wildcat v{wildcat.version()}\n\n")


def section(
    file: TextIO,
    title: str,
    fields: list[str],
    config: dict,
    paths: PathDict = {},
) -> None:
    "Records a group of related config values"

    # Get the config value for each field
    _title(file, title)
    for field in fields:
        value = config[field]

        # Parse Path inputs
        if isinstance(value, Path):
            if field in paths:
                value = paths[field]
            else:
                value = None

        # Add the value to the record
        _parameter(file, field, value)
    file.write("\n")


#####
# Utilities
#####


def _title(file: TextIO, text: str) -> None:
    "Writes a section title"
    file.write(f"# {text}\n")


def _parameter(file: TextIO, field: str, value: Any) -> None:
    "Writes a 'name = value' line for a config parameter"
    if isinstance(value, str):
        value = f'"{value}"'
    elif isinstance(value, Path):
        value = f'r"{value}"'
    file.write(f"{field} = {value}\n")
