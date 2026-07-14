"""
Function implementing the "preprocess" command
----------
Functions:
    preprocess  - Implements the preprocessor
"""

from __future__ import annotations

import typing

from wildcat._commands.preprocess import _check, _load, _save
from wildcat._commands.preprocess._numeric import (
    build_evt_masks,
    constrain_dnbr,
    constrain_kf,
    contain_severity,
    estimate_severity,
    fill_missing_kf,
)
from wildcat._commands.preprocess._spatial import clip, reproject
from wildcat._utils import _find, _setup

if typing.TYPE_CHECKING:
    from wildcat.typing import Config


def preprocess(locals: Config) -> None:
    "Runs the preprocessor"

    # Start log. Parse config settings. Locate IO folders and file paths
    config, log = _setup.command("preprocess", "Preprocessing", locals)
    inputs, preprocessed = _find.io_folders(config, "inputs", "preprocessed", log)
    paths = _find.inputs(config, inputs, log)

    # Build buffered burn perimeter. Load DEM and check resolution. Load
    # remaining datasets as rasters
    perimeter = _load.buffered_perimeter(config, paths, log)
    dem = _load.dem(paths, perimeter, log)
    _check.resolution(config, dem, log)
    rasters = _load.datasets(config, paths, perimeter, dem, log)

    # Reproject to match the DEM. Clip to the bounds of the perimeter
    reproject(rasters, log)
    clip(rasters, log)

    # Build rasters that are constant values
    _load.constants(config, rasters, log)

    # Preprocess dNBR and burn severity
    _check.dnbr_scaling(config, rasters, log)
    constrain_dnbr(config, rasters, log)
    estimate_severity(config, rasters, log)
    contain_severity(config, rasters, log)

    # Preprocess KF-factors, and build EVT masks
    constrain_kf(config, rasters, log)
    _check.missing_kf(config, rasters, log)
    fill_missing_kf(config, rasters, log)
    build_evt_masks(config, rasters, log)

    # Save the preprocessed rasters and configuration
    _save.rasters(preprocessed, rasters, log)
    _save.config(preprocessed, config, paths, log)
