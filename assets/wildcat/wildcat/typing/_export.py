"""
Type hints exclusive to the export command
----------
These type hints are separate from the base typing namespace because they require
importing fiona, which can slow down fast CLI operations.
"""

from fiona.crs import CRS

from wildcat.typing import Config, Parameters

# Properties
Schema = dict[str, dict]
PropSchema = dict[str, str]
PropNames = dict[str, str]

# Loaded results
Records = list[dict[str, dict]]
Results = tuple[CRS, Schema, Records, Records, Records]
