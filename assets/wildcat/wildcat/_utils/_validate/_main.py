"""
Functions that validate configuration settings for specific wildcat commands:
----------
Functions:
    _validate   - Checks that configuration fields meet indicated criteria
    preprocess  - Checks the config settings for the preprocessor
    assess      - Checks the config settings for an assessment
    model_parameters    - Checks hazard modeling parameters
    export      - Checks the config settings for an export
"""

from __future__ import annotations

import typing

from wildcat._utils._validate._core import (
    angle,
    boolean,
    check,
    config_style,
    durations,
    kf_fill,
    limits,
    optional_path,
    optional_path_or_constant,
    optional_string,
    path,
    positive,
    positive_integer,
    positive_integers,
    positive_limits,
    positives,
    ratio,
    ratios,
    scalar,
    severity_thresholds,
    strlist,
    vector,
)
from wildcat._utils._validate._export import crs, file_format, filename, rename

if typing.TYPE_CHECKING:
    from wildcat.typing import Config


def _validate(config: Config, checks: dict) -> None:
    "Checks that config fields meet indicated criteria"
    for field, validate in checks.items():
        validate(config, field)


def initialize(config: Config) -> None:
    "Validates settings for the 'initialize' command"

    checks = {
        "project": optional_path,
        "config": config_style,
        "inputs": optional_string,
    }
    _validate(config, checks)


def preprocess(config: Config) -> None:
    "Validates the configuration settings for the preprocessor"

    checks = {
        # Folders
        "project": path,
        "config": path,
        "inputs": path,
        "preprocessed": path,
        # Required
        "perimeter": path,
        "dem": path,
        # Recommended
        "dnbr": optional_path_or_constant,
        "severity": optional_path_or_constant,
        "kf": optional_path_or_constant,
        "evt": optional_path,
        # Optional
        "retainments": optional_path,
        "excluded": optional_path,
        "included": optional_path,
        "iswater": optional_path,
        "isdeveloped": optional_path,
        # Perimeter
        "buffer_km": positive,
        # DEM
        "resolution_limits_m": positive_limits,
        "resolution_check": check,
        # dNBR
        "dnbr_scaling_check": check,
        "constrain_dnbr": boolean,
        "dnbr_limits": limits,
        # Burn severity
        "severity_field": optional_string,
        "estimate_severity": boolean,
        "severity_thresholds": severity_thresholds,
        "contain_severity": boolean,
        # KF-factors
        "kf_field": optional_string,
        "constrain_kf": boolean,
        "max_missing_kf_ratio": ratio,
        "missing_kf_check": check,
        "kf_fill": kf_fill,
        "kf_fill_field": optional_string,
        # EVT masks
        "water": vector,
        "developed": vector,
        "excluded_evt": vector,
    }
    _validate(config, checks)


def assess(config: Config) -> None:
    "Validates the config settings for an assessment"

    checks = {
        # Folders
        "project": path,
        "config": path,
        "preprocessed": path,
        "assessment": path,
        # Required datasets
        "perimeter_p": path,
        "dem_p": path,
        "dnbr_p": path,
        "severity_p": path,
        "kf_p": path,
        # Optional masks
        "retainments_p": optional_path,
        "excluded_p": optional_path,
        "included_p": optional_path,
        "iswater_p": optional_path,
        "isdeveloped_p": optional_path,
        # Unit conversions
        "dem_per_m": scalar,
        # Delineation
        "min_area_km2": positive,
        "min_burned_area_km2": positive,
        "max_length_m": positive,
        # Filtering
        "max_area_km2": positive,
        "max_exterior_ratio": ratio,
        "min_burn_ratio": ratio,
        "min_slope": scalar,
        "max_developed_area_km2": positive,
        "max_confinement": angle,
        "confinement_neighborhood": positive_integer,
        "flow_continuous": boolean,
        # Specific IDs
        "remove_ids": positive_integers,
        # Hazard modeling
        # ...see below...
        # Basins
        "locate_basins": boolean,
        "parallelize_basins": boolean,
    }
    _validate(config, checks)
    model_parameters(config)


def model_parameters(config: Config) -> None:
    "Validates hazard model parameters"

    checks = {
        "I15_mm_hr": positives,
        "volume_CI": ratios,
        "durations": durations,
        "probabilities": ratios,
    }
    _validate(config, checks)


def export(config: Config) -> None:
    "Validates config settings for export"

    checks = {
        # Folders
        "project": path,
        "config": path,
        "assessment": path,
        "exports": path,
        # Output files
        "prefix": filename,
        "suffix": filename,
        "format": file_format,
        # Properties
        "properties": strlist,
        "exclude_properties": strlist,
        "include_properties": strlist,
        # Property formatting
        "order_properties": boolean,
        "clean_names": boolean,
        "rename": rename,
        # CRS
        "export_crs": crs,
    }
    _validate(config, checks)
