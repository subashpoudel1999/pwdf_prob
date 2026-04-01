"""
Custom errors raised by wildcat
----------
Errors:
    ConfigError         - When a configuration file cannot be read
    GeoreferencingError - When a DEM does not have valid georeferencing
"""


class ConfigError(Exception):
    "When a configuration file cannot be read"


class ConfigRecordError(ConfigError):
    "When a recorded configuration.txt file cannot be read"


class GeoreferencingError(Exception):
    "When a DEM does not have valid georeferencing"
