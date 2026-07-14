"""
Utilities for working with configuration settings
----------
This subpackage contains utilities to parse and record configuration settings for
wildcat commands.
----------
Contents:
    parse   - Function to parse configuration settings for a command
    load    - Function to compile a config file and return its namespace
    record  - Module with function to record configuration settings to file
    _parse  - Module implementing the configuration parser
"""

from wildcat._utils._config._parse import load, parse
