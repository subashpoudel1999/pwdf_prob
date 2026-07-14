"""
Functions that rename exported properties from default names
----------
The export command allows users to assign new names to properties being exported.
This is particularly useful for result vectors, as the default naming scheme
(indicating the indices of the associated hazard modeling parameters), is not
particularly human-readable. Wildcat implements a default renaming scheme for these
dynamically named vectors, which is implemented by the "clean" function. This
attempts to replace the indices in parameter names with simplified forms of the
associated parameters.

Users can also supersede the default naming scheme using a renaming dict. This
can be used to name result prefixes, parameter strings, and explicit property
names. This functionality is implemented by the "rename" function.
----------
Main:
    validate    - Checks that a renaming dict is valid
    parse       - Returns a dict mapping raw names to final names in the exported file

Result cleaning:
    clean       - Replaces dynamic index names with simplified parameter names
    _clean      - Replaces index names for a result prefix

Renaming:
    rename              - Renames properties following a user-provided renaming dict
    _rename_prefixes    - Replaces result array prefixes with new names
    _rename_parameters  - Replaces hazard model parameters with new names
    _rename_parameter   - Renames a hazard model parameter
    _rename_properties  - Renames explicitly listed properties
"""

from __future__ import annotations

import typing
from re import search

from wildcat._commands.export._properties import collect
from wildcat._utils import _parameters, _properties

if typing.TYPE_CHECKING:
    from logging import Logger
    from typing import Optional

    from wildcat.typing._export import Config, Parameters, PropNames

#####
# Main
#####


def validate(config: Config, parameters: Config) -> None:
    "Checks a renaming dict is valid, accounting for dynamic property names"

    # Get recognized renaming options
    dynamic = collect(parameters, _properties.results())
    allowed = _properties.all() + dynamic + _parameters.names()
    allowed_lower = [value.lower() for value in allowed]

    # Each renaming key must be a supported option
    rename = {}
    for k, (key, value) in enumerate(config["rename"].items()):
        if key.lower() not in allowed_lower:
            raise ValueError(
                f'Each key in the "rename" dict must be a property name, result '
                f"prefix, or the name of a modeling parameter. "
                f"However, key[{k}] (value = {key}) is not one of these options."
            )

        # Standardize capitalization
        a = allowed_lower.index(key.lower())
        key = allowed[a]
        rename[key] = value

        # Hazard modeling parameters must have the correct count
        if isinstance(value, list) and len(value) != len(parameters[key]):
            raise ValueError(
                f'The list for the "{key}" key in the "rename" dict must have '
                f"{len(parameters[key])} elements, but it has "
                f"{len(value)} elements instead."
            )
    config["rename"] = rename


def parse(
    config: Config, parameters: Config, properties: list[str], log: Logger
) -> PropNames:
    "Returns a dict mapping raw property names to their names in the final exported file"

    log.info("Parsing property names")
    names = clean(config, parameters, properties, log)
    rename(config, names, log)
    return names


#####
# Default cleaning
#####


def clean(
    config: Config, parameters: Config, properties: list[str], log: Logger
) -> PropNames:
    "Optionally replaces dynamic index names with simplified parameter names"

    # Initialize naming dict. Use raw names if not renaming
    cleaned = {name: name for name in properties}
    if not config["clean_names"]:
        return cleaned

    # Clean each set of dynamically named vectors
    log.debug("    Cleaning result names")
    I15s, CIs, durations, probabilities = _parameters.values(parameters)
    for prefix in ["H", "P", "V"]:
        _clean(cleaned, prefix, I15s)
    for prefix in ["Vmin", "Vmax"]:
        _clean(cleaned, prefix, I15s, CIs)
    for prefix in ["I", "R"]:
        _clean(cleaned, prefix, durations, probabilities, lstrip=True)
    return cleaned


def _clean(
    cleaned: PropNames,
    prefix: str,
    vector1: Parameters,
    vector100: Optional[Parameters] = None,
    lstrip: bool = False,
) -> None:
    "Replaces dynamic indices in names with simplified parameters"

    # Locate fields beginning with the prefix
    for field in cleaned.keys():
        if not field.startswith(f"{prefix}_"):
            continue

        # Get indices
        indices = field.split("_")[1:]
        indices = [int(index) for index in indices]

        # Get name for the first set of values
        value = vector1[indices[0]]
        edge = "_" * (not lstrip)
        name = f"{edge}{round(value)}"
        if vector100 is None:
            name += "mmh"

        # Optionally add second set of values. Update the name
        if vector100 is not None:
            value = vector100[indices[1]]
            name += f"_{round(100 * value)}"
        cleaned[field] = f"{prefix}{name}"


#####
# Renaming
#####


def rename(config: Config, names: PropNames, log: Logger) -> None:
    "Renames properties as specified by user"

    log.debug("    Applying user-provided names")
    rename = config["rename"]
    _rename_prefixes(names, rename)
    _rename_parameters(names, rename)
    _rename_properties(names, rename)


def _rename_prefixes(names: PropNames, rename: PropNames) -> None:
    "Replaces array prefixes with new names"

    # Iterate through renamed prefixes. Get the new string
    prefixes = [prefix for prefix in _properties.results() if prefix in rename]
    for prefix in prefixes:
        new = rename[prefix]

        # Rename any properties beginning with the prefix
        for raw, name in names.items():
            if raw.startswith(f"{prefix}_"):
                names[raw] = name.replace(prefix, new, 1)


def _rename_parameters(names: PropNames, rename: PropNames) -> None:
    "Replaces modeling parameter values with new names"

    # Parameter name, index in raw name, associated prefixes
    parameters = (
        ("I15_mm_hr", 1, ["H", "P", "V", "Vmin", "Vmax"]),
        ("volume_CI", 2, ["Vmin", "Vmax"]),
        ("durations", 1, ["R", "I"]),
        ("probabilities", 2, ["R", "I"]),
    )
    for parameter, k, prefixes in parameters:
        _rename_parameter(names, rename, parameter, k, prefixes)


def _rename_parameter(
    names: PropNames,
    rename: PropNames,
    parameter: str,
    k: int,  # Index of the parameter in the raw name when split by underscores
    prefixes: list[str],
) -> None:
    "Renames a parameter string"

    # Just exit if the field has no rename
    if parameter not in rename:
        return

    # Get the raw names of exported properties with the parameter
    values = rename[parameter]
    for prefix in prefixes:
        raws = [raw for raw in names.keys() if raw.startswith(f"{prefix}_")]

        # Get the new value and the current name for each renamed property
        for raw in raws:
            index = int(raw.split("_")[k])
            new = values[index]
            current = names[raw]

            # Update the name
            c = search(r"\d", current).start()  # index of first digit
            name = current[c:].split("_")
            name[k - 1] = new
            names[raw] = current[:c] + "_".join(name)


def _rename_properties(names: PropNames, rename: PropNames) -> None:
    "Replaces explicit property names"

    excluded = _properties.results() + _parameters.names()
    properties = [name for name in rename.keys() if name not in excluded]
    for property in properties:
        names[property] = rename[property]
