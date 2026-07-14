"""
Utility functions for working with hazard modeling parameters
----------
Wildcat assessments produce array-like model results, but vector feature files
typically record vector-like values (i.e. one value per feature per field). As
such, wildcat uses hazard modeling parameter indices to implement a dynamic naming
scheme for saved assessment results. This module provides small utility functions
to support working with these parameters in the context of the naming scheme.
----------
Functions:
    names   - Returns the names of the hazard modeling parameters in a config file
    values  - Returns the values of the hazard modeling parameters from a config namespace
    count   - Counts the number of elements for each hazard modeling parameter
"""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from wildcat.typing import Config, Parameters


def names() -> tuple[str, str, str, str]:
    "Returns the names of the hazard modeling parameters"
    return ["I15_mm_hr", "volume_CI", "durations", "probabilities"]


def values(config: Config) -> tuple[Parameters, Parameters, Parameters, Parameters]:
    "Returns the hazard modeling parameter vectors"
    return tuple(config[field] for field in names())


def count(config: Config) -> tuple[int, int, int, int]:
    "Returns the number of I15 values, CIs, durations, and probabilities"
    return tuple(len(vector) for vector in values(config))
