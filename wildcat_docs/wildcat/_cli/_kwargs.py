"""
Functions that convert CLI inputs to function kwarg dicts
----------
The CLI options for a command are not identical to the function kwargs for the
command. As such, CLI inputs must be parsed converted to a kwarg dict before a
command function can be run. The functions in this module implement these conversions.
----------
Functions:
    initialize      - Converts CLI inputs to kwargs for the initialize command
    preprocess      - Converts CLI inputs to kwargs for the preprocess command
    assess          - Converts CLI inputs to kwargs for the assess command
    export          - Converts CLI inputs to kwargs for the export command

Utilities:
    _parse_paths    - Parses filepath options, converting None to boolean False
    _invert         - Parses CLI switches that invert a function kwarg switch
    _copy_remaining - Copies all remaining kwargs directly from args
"""

from __future__ import annotations

import typing

import wildcat
from wildcat._utils import _args, _paths
from wildcat._utils._defaults import defaults

if typing.TYPE_CHECKING:
    from argparse import Namespace
    from typing import Any

    kwargs = dict[str, Any]


#####
# Command Parsers
#####


def initialize(args: Namespace) -> kwargs:
    "Converts CLI args to kwargs for the initialize function"

    # Parse the input folder options
    if args.no_inputs:
        inputs = None
    elif args.inputs is None:
        inputs = defaults.inputs
    else:
        inputs = args.inputs

    # Build the kwargs
    kwargs = {"inputs": inputs}
    _copy_remaining(args, kwargs)
    return kwargs


def preprocess(args: Namespace) -> kwargs:
    "Converts CLI args to kwargs for the preprocess function"

    # Parse paths that may be boolean. Parse inverted CLI switches
    kwargs = {}
    _parse_paths(args, _paths.preprocess.standard(), kwargs)
    _invert(
        args,
        ["constrain_dnbr", "estimate_severity", "contain_severity", "constrain_kf"],
        kwargs,
    )

    # Parse KF-fill values. Start with boolean options
    if args.kf_fill is not None:
        if args.kf_fill.lower() == "true":
            kwargs["kf_fill"] = True
        elif args.kf_fill.lower() == "false":
            kwargs["kf_fill"] = False

        # Attempt to convert to float. If it fails, interpret as filepath
        else:
            try:
                kwargs["kf_fill"] = float(args.kf_fill)
            except Exception:
                kwargs["kf_fill"] = args.kf_fill

    # Disable EVT codes by using an empty list
    if args.no_find_water:
        kwargs["water"] = []
    if args.no_find_developed:
        kwargs["developed"] = []
    if args.no_find_excluded:
        kwargs["excluded_evt"] = []

    # Copy all remaining fields directly
    _copy_remaining(args, kwargs)
    return kwargs


def assess(args: Namespace) -> kwargs:
    "Converts CLI args to kwargs for the assess function"

    # Initialize kwargs. Parse path options
    kwargs = {}
    _parse_paths(args, _paths.assess.all(), kwargs)

    # Misc renames
    kwargs["confinement_neighborhood"] = args.neighborhood
    kwargs["flow_continuous"] = not args.not_continuous
    kwargs["locate_basins"] = not args.no_basins
    kwargs["parallelize_basins"] = bool(args.parallel)

    # Force filtering in perimeter by setting exterior ratio to 0
    if args.filter_in_perimeter:
        kwargs["max_exterior_ratio"] = 0

    # Copy remainining args directly
    _copy_remaining(args, kwargs)
    return kwargs


def export(args: Namespace) -> kwargs:
    "Converts CLI args to kwargs for the export function"

    # Initialize kwargs. Invert switches
    kwargs = {}
    _invert(args, ["order_properties", "clean_names"], kwargs)

    # Parse CRS
    crs = args.crs
    if crs == "None":
        crs = None
    kwargs["export_crs"] = crs

    # Initialize renaming dict if appropriate
    if args.rename is not None or args.rename_parameter is not None:
        kwargs["rename"] = {}

    # Direct renames
    if args.rename is not None:
        for raw, rename in args.rename:
            kwargs["rename"][raw] = rename

    # Parameter renames
    if args.rename_parameter is not None:
        for renaming in args.rename_parameter:
            parameter = renaming[0]
            names = renaming[1:]
            kwargs["rename"][parameter] = names

    # Copy remainining args directly
    _copy_remaining(args, kwargs)
    return kwargs


#####
# Utilities
#####


def _parse_paths(args: Namespace, names: list[str], kwargs: kwargs) -> None:
    "Parses args that represent paths. Converts None to boolean False"

    for name in names:
        input = getattr(args, name)
        if input is not None and input.lower() == "none":
            input = False
        kwargs[name] = input


def _invert(args: Namespace, names: list[str], kwargs: kwargs) -> None:
    "Parses command line switches that invert a function kwarg"

    for name in names:
        kwargs[name] = not getattr(args, f"no_{name}")


def _copy_remaining(args: Namespace, kwargs: kwargs) -> None:
    "Copies all remaining kwargs directly from args"

    # Get the function parameters
    command = getattr(wildcat, args.command)
    parameters = _args.collect(command)

    # Copy remaining kwargs directly from args
    for parameter in parameters:
        if parameter not in kwargs:
            kwargs[parameter] = getattr(args, parameter)
