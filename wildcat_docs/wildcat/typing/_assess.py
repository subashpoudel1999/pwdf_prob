"""
Type hints exclusive to the assess command
----------
These type hints are separate from the base typing namespace because they require
importing numpy, which can slow down fast CLI operations.
"""

from numpy import ndarray

from wildcat.typing import Config, PathDict, RasterDict

PropertyDict = dict[str, ndarray]
