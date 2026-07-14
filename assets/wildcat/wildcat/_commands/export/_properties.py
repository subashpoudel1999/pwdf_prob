"""
Functions to parse and build the final ordered list of exported properties
----------
The following outlines the steps of the parser:

* First, property group names (such as "results" or "filters") are unpacked
    into their consituent property names and prefixes
* Next, result array prefixes are converted into the complete set of dynamically
    named vector names. These are the prefixes followed by the indices of
    relevant hazard modeling parameters.
* Then, duplicate entries are removed, preserving the initial listing order.
* Finally, the remaining properties are optionally reordered to group related
    properties together. This clusters H/P/V results by I15 value. Thresholds
    are grouped by duration and then probability level. Then model inputs,
    watershed characterstics, and finally filters.
----------
Main Functions:
    validate    - Checks that base, excluded, and included properties are valid
    _validate   - Checks a set of properties are recognized and standardizes capitalization
    parse       - Builds the final ordered list of raw property names

Parser steps:
    standardize - Convert properties to a unique set of raw names
    finalize    - Handle excluded and included properties
    order       - Reorders properties to group related values together
    _add        - Adds a property to organized properties if available

Standardization:
    ungroup     - Replaces property groups with the associated fields
    collect     - Converts result prefixes to dynamic vector names
    _collect    - Converts a result prefix to dynamic vector names
    unique      - Returns unique properties in listed order
"""

from __future__ import annotations

import typing

from wildcat._utils import _parameters, _properties

if typing.TYPE_CHECKING:
    from logging import Logger
    from typing import Optional

    from wildcat.typing import Config


#####
# Main
#####


def validate(config: Config, parameters: Config) -> None:
    "Checks that properties are recognized and standardizes capitalization"

    # Get recognized properties
    dynamic = collect(parameters, _properties.results())
    allowed = _properties.all() + _properties.groups() + dynamic
    allowed_lower = [value.lower() for value in allowed]

    # Validate property selection settings
    for setting in ["properties", "exclude_properties", "include_properties"]:
        _validate(config, setting, allowed, allowed_lower)


def _validate(
    config: Config, setting: str, allowed: list[str], allowed_lower: list[str]
) -> None:
    "Check that properties are recognized and standardize capitalization"

    # Each element must be recognized
    properties = config[setting]
    for i, input in enumerate(properties):
        if input.lower() not in allowed_lower:
            raise ValueError(
                f'Each element of the "{setting}" setting must be a supported '
                f"property name or group. However, {setting}[{i}] (value = {input}) "
                f"is not."
            )

        # Standardize capitalization
        a = allowed_lower.index(input.lower())
        properties[i] = allowed[a]
    config[setting] = properties


def parse(config: Config, parameters: Config, log: Logger) -> list[str]:
    "Builds the final ordered list of raw property names"

    # Standardize the lists of base, excluded, and included properties
    log.info("Parsing exported properties")
    properties = standardize(parameters, config["properties"], log)
    exclude = standardize(parameters, config["exclude_properties"])
    include = standardize(parameters, config["include_properties"])

    # Finalize the property list and optionally reorder
    finalize(properties, exclude, include, log)
    return order(config, parameters, properties, log)


#####
# Parser steps
#####


def standardize(
    parameters: Config, properties: list[str], log: Optional[Logger] = None
) -> list[str]:
    "Converts a property list to a unique set of raw property names"

    # Convert groups to names and prefixes
    if log is not None:
        log.debug("    Unpacking property groups")
    properties = ungroup(properties)

    # Convert prefixes to dynamic names
    if log is not None:
        log.debug("    Parsing result vectors")
    properties = collect(parameters, properties)

    # Get unique names in list order
    if log is not None:
        log.debug("    Removing duplicate properties")
    return unique(properties)


def finalize(
    properties: list[str], exclude: list[str], include: list[str], log: Logger
) -> None:
    "Determines the final set of exported properties"

    # Remove excluded properties
    log.debug("    Removing excluded properties")
    for name in exclude:
        if name in properties:
            properties.remove(name)

    # Add included properties
    log.debug("    Adding included properties")
    for name in include:
        if name not in properties:
            properties.append(name)


def order(
    config: Config, parameters: Config, properties: list[str], log: Logger
) -> list[str]:
    "Optionally reorders properties to group related properties together"

    # Exit if not reordering
    if not config["order_properties"]:
        return properties

    # Count parameters. Group property lists. Add ID as first field
    log.debug("    Reordering properties")
    nI15, nCI, nDurations, nProb = _parameters.count(parameters)
    organized = []
    props = (organized, properties)
    _add("Segment_ID", *props)

    # I15 results grouped by I15 value
    for i in range(nI15):
        for prefix in ["H", "P", "V"]:
            _add(f"{prefix}_{i}", *props)

        # End with volume CIs, grouped by CI level
        for c in range(nCI):
            for prefix in ["Vmin", "Vmax"]:
                _add(f"{prefix}_{i}_{c}", *props)

    # Rainfall thresholds grouped by duration and then by probability level
    for d in range(nDurations):
        for p in range(nProb):
            for prefix in ["I", "R"]:
                _add(f"{prefix}_{d}_{p}", *props)

    # Model inputs, then watershed variables, then filters
    fields = (
        _properties.model_inputs() + _properties.watershed()[1:] + _properties.filters()
    )
    for field in fields:
        _add(field, *props)
    return organized


def _add(name: str, organized: list[str], properties: list[str]) -> None:
    "Adds a property to the organized properties if available"
    if name in properties:
        organized.append(name)


#####
# Standardization
#####


def ungroup(properties: list[str]) -> list[str]:
    "Replaces property group names with associated properties"

    # Initialize unpacked list and get group names
    unpacked = []
    groups = _properties.groups()

    # Unpack each group
    for property in properties:
        if property in groups:
            property = property.replace(" ", "_")
            values = getattr(_properties, property)()
        else:
            values = [property]
        unpacked += values
    return unpacked


def collect(parameters: Config, properties: list[str]) -> list[str]:
    """Converts result prefixes to dynamic vector names. Note that this will
    remove any prefixes with empty parameters"""

    nI15, nCI, nDurations, nProb = _parameters.count(parameters)
    for prefix in ["H", "P", "V"]:
        properties = _collect(properties, prefix, nI15)
    for prefix in ["Vmin", "Vmax"]:
        properties = _collect(properties, prefix, nI15, nCI)
    for prefix in ["R", "I"]:
        properties = _collect(properties, prefix, nDurations, nProb)
    return properties


def _collect(
    properties: list[str], prefix: str, N: int, M: Optional[int] = None
) -> list[str]:
    "Converts a result prefix to dynamic vector names"

    # Exit if the property is not being exported
    if prefix not in properties:
        return properties

    # Unpack names and update list
    k = properties.index(prefix)
    if M is None:
        names = [f"{prefix}_{j}" for j in range(N)]
    else:
        names = [f"{prefix}_{j}_{k}" for j in range(N) for k in range(M)]
    return properties[:k] + names + properties[k + 1 :]


def unique(properties: list[str]) -> list[str]:
    "Gets unique properties in listed order"

    unique = []
    for property in properties:
        if property not in unique:
            unique.append(property)
    return unique
