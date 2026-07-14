"""
Common type hints used throughout the package
"""

from pathlib import Path
from typing import Any, Literal, Sequence

# Basic user inputs
Pathlike = str | Path
scalar = int | float
vector = scalar | Sequence[scalar]
strs = str | list[str]
CRS = str | int | Literal["base"]

# User string options
Check = Literal["error", "warn", "none"]
ConfigType = Literal["none", "empty", "default", "full"]

# Internal
IOFolders = tuple[Path, Path]
Config = dict[str, Any]
PathDict = dict[str, Path]
RasterDict = dict

# Hazard modeling parameter values
Parameters = list[int | float]
