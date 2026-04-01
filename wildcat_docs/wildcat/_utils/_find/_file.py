"""
Determine a file path based on user input
----------
Wildcat commands allow a variety of inputs for parameters that represent file paths.
Most simply, users can use an absolute or relative file path, and the command will
check that such a path exists. However, many datasets are optional, and so the
command will return None if a file cannot be located. Raises an error if a required
file cannot be located, or if a user explicitly provides a dataset that cannot
be found.
----------
Functions:
    file                - Determines the path to an input file
    _resolve_path       - Returns the absolute path to an existing file or None
    _scan_extensions    - Scans supported extensions when a file is missing
"""

from __future__ import annotations

import typing

from wildcat._utils import _extensions
from wildcat._utils._defaults import defaults

if typing.TYPE_CHECKING:
    from pathlib import Path


def file(
    folder: Path, input: Path, name: str, required: bool, supports_features: bool
) -> Path | None:
    "Determines the path to an input dataset"

    # Locate the path. Path will be None if it does not exist
    path = _resolve_path(folder, input, supports_features)

    # Error if a required or non-default file is missing
    if path is None:
        altered = (input is not None) and str(input) != getattr(defaults, name)
        if required or altered:
            raise FileNotFoundError(f"Could not locate the {name} file.")
    return path


def _resolve_path(folder: Path, path: Path, supports_features: bool) -> Path | None:
    "Returns the absolute path to an existing file or None"

    # Convert to absolute path
    if not path.is_absolute():
        path = (folder / path).resolve()

    # Scan supported extensions if the Path does not exist
    if not path.exists():
        supported = _extensions.raster()
        if supports_features:
            supported += _extensions.vector()
        path = _scan_extensions(path, supported)
    return path


def _scan_extensions(path: Path, extensions: list[str]) -> Path | None:
    "Searches for a file with a supported extension"

    # Iterate through supported extensions
    folder = path.parent
    name = path.name
    for ext in extensions:
        path = folder / f"{name}{ext}"

        # Stop if an existing file is located. Otherwise return None
        if path.exists():
            return path
    return None
