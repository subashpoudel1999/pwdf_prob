"""
Module holding all default parameters in a single namespace
----------
This module collects all default parameters into a single namespace. This allows
the configuration parser to query parameters without needing to know the specific
parameter groups housing the values.
----------
"""

from wildcat._utils._defaults.assess import *
from wildcat._utils._defaults.export import *
from wildcat._utils._defaults.folders import *
from wildcat._utils._defaults.preprocess import *
