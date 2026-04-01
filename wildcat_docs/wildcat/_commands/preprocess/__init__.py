"""
Subpackage to implement the preprocessor
----------
Main Function:
    preprocess  - Implements the preprocessor

Internal Modules:
    _check      - Functions that optionally raise warnings or errors when a condition is met
    _load       - Functions that load input datasets as rasters
    _locate     - Functions that locate file paths to preprocessing resources
    _numeric    - Functions that preprocess raster data arrays
    _preprocess - Implements the "preprocess" function
    _save       - Functions to save output files
    _spatial    - Functions to implement spatial preprocessing
"""

from wildcat._commands.preprocess._preprocess import preprocess
