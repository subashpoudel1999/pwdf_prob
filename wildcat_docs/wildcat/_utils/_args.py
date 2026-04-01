"""
Function that returns the names of a function's args
----------
Function:
    collect - Returns a list of function arg names
"""

from __future__ import annotations

import inspect
import typing

if typing.TYPE_CHECKING:
    from typing import Callable


def collect(command: Callable) -> list[str]:
    "Returns a list of function arg names"

    return list(inspect.signature(command).parameters.keys())
