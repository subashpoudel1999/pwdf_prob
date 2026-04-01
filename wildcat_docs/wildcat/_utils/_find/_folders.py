"""
Determines the paths to IO folders
----------
Most wildcat commands take various input files and then save various output files.
Relative file paths are searched for in a default inputs folder for the command.
All output files are saved into an outputs file for the command. This module
provides functionality to locate these folder paths, given the project folder.
----------
Functions:
    io_folders      - Locate the input and output folders for a command
    _input_folder   - Locates an input folder
    _output_folder  - Locates an output folder, creating if it does not exist
    _folder         - Resolves the path to a folder
"""

from __future__ import annotations

import typing

from wildcat._utils._defaults import defaults

if typing.TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path

    from wildcat.typing import IOFolders


def io_folders(
    project: Path,
    input: Path,
    input_name: str,
    output: Path,
    output_name: str,
    log: Logger,
) -> IOFolders:
    "Determines the paths to the IO folders"

    log.info("Locating IO folders")
    input = _input_folder(project, input, input_name, log)
    output = _output_folder(project, output, output_name, log)
    return input, output


def _input_folder(project: Path, path: Path, name: str, log: Logger) -> Path:
    "Locates a folder used to search for input files"

    path = _folder(project, path, name, log)
    if not path.exists() and path.name != getattr(defaults, name):
        log.warning(f"\nWARNING: The {name} folder does not exist.\n")
    return path


def _output_folder(project: Path, path: Path, name: str, log: Logger) -> Path:
    "Locates a folder that will hold saved outputs"

    path = _folder(project, path, name, log)
    if not path.exists():
        path.mkdir(parents=True)
    return path


def _folder(project: Path, path: Path, name: str, log: Logger) -> Path:
    """Resolves the path to a folder. Relative paths are parsed relative to the
    project folder. If the path does exist, it must be a folder"""

    # Ensure absolute path
    if not path.is_absolute():
        path = (project / path).resolve()

    # If existing, must be a folder
    if path.exists() and not path.is_dir():
        raise ValueError(f"The '{name}' path is not a folder.")
    log.debug(f"    {name}: {path}")
    return path
