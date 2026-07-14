"""
Functions that validate a config field
----------
The functions in this module check that a config field meets various criteria.
The commands will also update the config dict as necessary to standardize config
settings for internal use.
----------
Utilities:
    aslist              - Converts an input to a list

Paths / Datasets:
    path                - Checks a field can be converted to a Path
    optional_path       - Checks a field is either a Path or None
    optional_path_or_constant   - Checks a field is an int, float, path, or None

String options:
    strlist             - Checks a field is a list of strings
    optional_string     - Checks a field is a string or None
    _option             - Checks a field is a recognized string option
    check               - Checks a field is either 'warn', 'error', or 'none'
    config_style        - Checks a field is either 'none', 'empty', 'default', or 'full'

Scalars:
    boolean             - Checks a field is a boolean
    scalar              - Checks a field is an int or finite float
    positive            - Checks a field is a positive scalar
    positive_integer    - Checks a field is a positive integer

Bounded Scalars:
    _bounded            - Checks a field is a scalar between two bounds
    ratio               - Checks a field is a scalar between 0 and 1
    angle               - Checks a field is a scalar between 0 and 360

Vectors:
    vector              - Checks a field is a vector of ints and/or finite floats
    ratios              - Checks a field is a vector of values between 0 and 1
    positives           - Checks a field is a vector of positive values
    positive_integers   - Checks a field is a vector of positive integers

Sorted:
    _ascending          - Checks a field is a vector of specific length with ascending values
    limits              - Checks a field is the bounds of an interval (ascending 2-vector)
    positive_limits     - Checks a field is the bounds of a positive interval
    severity_thresholds - Checks a field is a vector of 3 ascending values

Misc:
    kf_fill             - Checks a field is a boolean, int, float, Path, or None
    durations           - Checks a field is a vector of values equal to 15, 30, and/or 60
"""

from __future__ import annotations

import typing
from math import isinf, isnan
from pathlib import Path

if typing.TYPE_CHECKING:
    from typing import Any, Optional

    from wildcat.typing import Config

#####
# Utilities
#####


def aslist(input: Any) -> list:
    "Returns an input as a list"
    if isinstance(input, tuple):
        input = list(input)
    elif not isinstance(input, list):
        input = [input]
    return input


#####
# Paths / Datasets
#####


def path(config: Config, name: str) -> None:
    "Checks a user input can be converted to a path"

    # Common options that aren't allowed
    input = config[name]
    if isinstance(input, bool) and input == True:
        raise TypeError(
            f'The "{name}" setting should be a file path, so you cannot set {name}=True. '
        )
    elif isinstance(input, bool) and input == False:
        raise TypeError(f"The {name} path is required, so cannot be False")
    elif input is None:
        raise TypeError(f"The {name} path is required, so cannot be None")

    # Convert to Path
    try:
        path = Path(input)
    except Exception as error:
        raise TypeError(
            f'Could not convert the "{name}" setting to a file path'
        ) from error
    config[name] = path


def optional_path(config: Config, name: str) -> None:
    "Checks an input is either Pathlike or None/False"

    input = config[name]
    if input is None or (isinstance(input, bool) and input == False):
        config[name] = None
    else:
        path(config, name)


def optional_path_or_constant(config: Config, name: str) -> None:
    "Checks an input is an int, float, or optional path"

    if isinstance(config[name], (int, float)) and not isinstance(config[name], bool):
        scalar(config, name)
    else:
        optional_path(config, name)


#####
# Text
#####


def strlist(config: Config, name: str) -> None:
    "Checks an input represents a list of strings"

    # Convert None to empty list
    input = config[name]
    if input is None:
        input = []

    # Must be a list, tuple, or string. Convert to list
    if not isinstance(input, (list, tuple, str)):
        raise TypeError(f'The "{name}" setting must be a list, tuple, or string')
    input = aslist(input)

    # Each element must be a string
    for k, value in enumerate(input):
        if not isinstance(value, str):
            raise TypeError(
                f'Each element of the "{name}" setting must be a string, '
                f"but {name}[{k}] is not a string."
            )
    config[name] = input


def optional_string(config: Config, name: str) -> None:
    "Checks an input is either a string, or None"

    input = config[name]
    if input is not None and not isinstance(input, str):
        raise TypeError(f'The "{name}" setting must be a string, or None')


def _option(config: Config, name: str, allowed: list[str]) -> None:
    "Checks an input is an allowed string option"

    # Get commen error message
    allowed_str = ", ".join(allowed)
    message = (
        f'The "{name}" setting should be one of the following strings: {allowed_str}'
    )

    # Must be a string
    input = config[name]
    if not isinstance(input, str):
        raise TypeError(message)

    # Must be recognized (case-insensitive)
    input = input.lower()
    if input not in allowed:
        raise ValueError(message)
    config[name] = input


def check(config: Config, name: str) -> None:
    "Checks an input is one of the following strings: none, warn, error"
    input = config[name]
    if input is None:
        config[name] = "none"
    _option(config, name, ["warn", "error", "none"])


def config_style(config: Config, name: str) -> None:
    "Checks an input is 'none', 'empty', 'default', or 'full'"
    input = config[name]
    if input is None:
        config[name] = "none"
    _option(config, name, ["default", "full", "empty", "none"])


#####
# Basic Scalars
#####


def boolean(config: Config, name: str) -> None:
    "Checks an input is a boolean"
    if not isinstance(config[name], bool):
        raise TypeError(f'The "{name}" setting must be a bool')


def scalar(config: Config, name: str) -> None:
    "Check an input is either an int or a finite float"

    input = config[name]
    if not isinstance(input, (int, float)):
        raise TypeError(f'The "{name}" setting must be an int or a float')
    elif isnan(input):
        raise ValueError(f'The "{name}" setting cannot be nan')
    elif isinf(input):
        raise ValueError(f'The "{name}" setting must be finite')


def positive(config: Config, name: str) -> None:
    "Checks an input is a positive scalar"
    scalar(config, name)
    if config[name] < 0:
        raise ValueError(f'The "{name}" setting must be positive')


def positive_integer(config: Config, name: str) -> None:
    "Checks an input is a positive integer"

    positive(config, name)
    if config[name] % 1 != 0:
        raise ValueError(f'The "{name}" setting must be an integer')


#####
# Bounded scalars
#####


def _bounded(config: Config, name: str, min: float, max: float) -> None:
    "Checks a field is a scalar between two bounds"
    scalar(config, name)
    if config[name] < min or config[name] > max:
        raise ValueError(f'The "{name}" setting must be between {min} and {max}')


def ratio(config: Config, name: str) -> None:
    "Checks a field is a scalar between 0 and 1"
    _bounded(config, name, 0, 1)


def angle(config: Config, name: str) -> None:
    "Checks a field is a scalar between 0 and 360"
    _bounded(config, name, 0, 360)


#####
# Vectors
#####


def vector(config: Config, name: str, length: Optional[int] = None) -> None:
    "Checks an input is a list of ints and/or floats. Optionally checks length"

    # Determine if scalars are allowed
    allowed = (list, tuple)
    if length is None:
        allowed += (int, float)

    # Check the type
    input = config[name]
    if not isinstance(input, allowed):
        allowed = ", ".join([type.__name__ for type in allowed])
        raise TypeError(
            f'The "{name}" setting must be one of the following types: {allowed}'
        )

    # Optionally check the length
    input = aslist(config[name])
    if length is not None and len(input) != length:
        raise ValueError(
            f'The "{name}" setting must have exactly {length} elements, '
            f"but it has {len(input)} elements instead."
        )

    # Check each element is valid
    for k, value in enumerate(input):
        if not isinstance(value, (int, float)):
            raise TypeError(
                f'The elements of the "{name}" setting must be ints and/or floats, '
                f"but {name}[{k}] is not."
            )
        elif isnan(value):
            raise ValueError(
                f'The elements of the "{name}" setting cannot be nan, '
                f"but {name}[{k}] is nan"
            )
        elif isinf(value):
            raise ValueError(
                f'The elements of the "{name}" setting must be finite, '
                f"but {name}[{k}] is not"
            )
    config[name] = input


def ratios(config: Config, name: str) -> None:
    "Checks an input is a vector of values between 0 and 1"
    vector(config, name)
    for k, value in enumerate(config[name]):
        if value < 0 or value > 1:
            raise ValueError(
                f'The elements of the "{name}" setting must be between 0 and 1. '
                f"However, {name}[{k}] (value = {value}) is not."
            )


def positives(config: Config, name: str) -> None:
    "Checks that an input is a vector of positive values"

    vector(config, name)
    for k, value in enumerate(config[name]):
        if value < 0:
            raise ValueError(
                f'The elements of the "{name}" setting must be positive, '
                f"but {name}[{k}] (value = {value}) is not."
            )


def positive_integers(config: Config, name: str) -> None:
    "Checks a field is a vector of positive integers"

    positives(config, name)
    for k, value in enumerate(config[name]):
        if value % 1 != 0:
            raise ValueError(
                f'The elements of the "{name}" setting must be integers, '
                f"but {name}[{k}] (value = {value}) is not an integer."
            )


#####
# Sorted
#####


def _ascending(config: Config, name: str, length: int) -> None:
    "Checks an input is a vector of certain length with elements in ascending order"

    vector(config, name, length)
    for k, value in enumerate(config[name]):
        if k != 0 and value < previous:
            raise ValueError(
                f'The elements of the "{name}" setting must be in ascending order. '
                f"However, {name}[{k}] (value = {value}) is less than {name}[{k-1}] (value = {previous})."
            )
        previous = value


def limits(config: Config, name: str) -> None:
    "Checks an input represents the bounds of an interval (2 ascending values)"
    _ascending(config, name, 2)


def positive_limits(config: Config, name: str) -> None:
    "Checks an input represents the bounds of a positive interval"
    limits(config, name)
    positives(config, name)


def severity_thresholds(config: Config, name: str) -> None:
    "Checks an input is 3 ascending numeric values"
    _ascending(config, name, 3)


#####
# Misc
#####


def kf_fill(config: Config, name: str) -> None:
    "Checks an input is a boolean, int, float, Path, or None"

    # Convert None to boolean
    input = config[name]
    if input is None:
        config[name] = False
        return

    # If not numeric, must be a path
    elif not isinstance(input, (bool, int, float)):
        path(config, name)


def durations(config: Config, name: str) -> None:
    "Checks an input is a vector of values equal to 15, 30, and/or 60"
    vector(config, name)
    for k, value in enumerate(config[name]):
        if value not in [15, 30, 60]:
            raise ValueError(
                f'The elements of the "{name}" setting must be 15, 30, and/or 60. '
                f"But {name}[{k}] (value = {value}) is not."
            )
