"""
Functions to help determine file paths
----------
Functions:
    io_folders      - Locates the paths to input and output folders
    inputs          - Locates the paths to input datasets for the preprocessor
    preprocessed    - Locates the paths to preprocessed rasters for the assessment

Internal Modules:
    _main           - Functions to resolve paths from config setttings and log the locations
    _file           - Functions to determine the path to a file
    _folders        - Functions to determine the paths to IO folders
"""

from wildcat._utils._find._main import inputs, io_folders, preprocessed
