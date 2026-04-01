"""
Functions that preprocess the values in raster data arrays
----------
Functions:
    constrain_dnbr      - Constrains the dNBR to a valid data range
    constrain_kf        - Constrains KF factors to positive values
    fill_missing_kf     - Replaces NoData KF-factor pixels with fill values
    estimate_severity   - Estimates burn severity from the dNBR
    contain_severity    - Restricts burn severity data to the perimeter mask
    build_evt_masks     - Builds raster masks of water, developed, and excluded EVT pixels
"""

from __future__ import annotations

import typing

import numpy as np
from pfdf import severity
from pfdf.raster import Raster

if typing.TYPE_CHECKING:
    from logging import Logger

    from wildcat.typing import Config, RasterDict


def constrain_dnbr(config: Config, rasters: RasterDict, log: Logger) -> None:
    "Optionally constrains the dNBR to a valid data range"

    # Just exit if not constraining
    if not config["constrain_dnbr"] or "dnbr" not in rasters:
        return

    # Constrain the dNBR
    log.info("Constraining dNBR data range")
    min, max = config["dnbr_limits"]
    rasters["dnbr"].set_range(min=min, max=max)


def constrain_kf(config: Config, rasters: RasterDict, log: Logger) -> None:
    "Optionally constrains KF-factors to positive values"

    # Just exit if not constraining
    if not config["constrain_kf"] or "kf" not in rasters:
        return

    # Constrain KF to positive values
    log.info("Constraining KF-factors to positive values")
    rasters["kf"].set_range(min=0, fill=True, exclude_bounds=True)


def fill_missing_kf(config: Config, rasters: RasterDict, log: Logger) -> None:

    # Just exit if not filling
    kf_fill = config["kf_fill"]
    disabled = isinstance(kf_fill, bool) and kf_fill == False
    if disabled or "kf" not in rasters:
        return

    # Also exit if there isn't any missing data
    kf = rasters["kf"]
    missing = kf.nodata_mask
    if not np.any(missing):
        return

    # Log step and get data array
    log.info("Filling missing KF-factors")
    values = kf.values.copy()

    # Fill using median of available data
    if isinstance(kf_fill, bool):
        data = values[~missing]
        fill = np.nanmedian(data)
        log.debug(f"    Filling with median KF: {fill}")

    # Or replace with a numeric value
    elif isinstance(kf_fill, (float, int)):
        fill = kf_fill
        log.debug(f"    Filling with {fill}")

    # Or fill from rasterized polygons
    else:
        fill = rasters["kf_fill"].values[missing]
        log.debug("    Filling using kf_fill file")

    # Build the final raster
    values[missing] = fill
    kf = Raster.from_array(values, nodata=kf.nodata, spatial=kf, copy=False)
    kf.name = "kf"
    rasters["kf"] = kf


def estimate_severity(config: Config, rasters: RasterDict, log: Logger) -> None:
    "Optionally estimates severity from the dNBR when the severity dataset is missing"

    # Just exit if not estimating
    if (
        (not config["estimate_severity"])
        or ("severity" in rasters)
        or ("dnbr" not in rasters)
    ):
        return

    # Estimate severity
    log.info("Estimating severity from dNBR")
    rasters["severity"] = severity.estimate(
        rasters["dnbr"], thresholds=config["severity_thresholds"]
    )


def contain_severity(config: Config, rasters: RasterDict, log: Logger) -> None:
    "Restricts severity data to pixels in the perimeter mask"

    # Just exit if not clipping
    if (not config["contain_severity"]) or ("severity" not in rasters):
        return

    # Clip data values to perimeter mask
    log.info("Containing severity data to the perimeter")
    severity = rasters["severity"]
    perimeter = rasters["perimeter"].values
    contained = severity.values.copy()
    contained[~perimeter] = severity.nodata

    # Create the final raster
    severity = Raster.from_array(
        contained, nodata=severity.nodata, spatial=severity, copy=False
    )
    severity.name = "severity"
    rasters["severity"] = severity


def build_evt_masks(config: Config, rasters: RasterDict, log: Logger) -> None:
    "Optionally creates water, development, and excluded EVT raster masks"

    # Map EVT parameter names onto raster mask names. Extract EVT integer codes
    masks = {  # parameter, raster
        "water": "iswater",
        "developed": "isdeveloped",
        "excluded_evt": "excluded",
    }
    codes = {name: config[name] for name in masks}

    # Just exit if there aren't any masks
    no_masks = all([len(group) == 0 for group in codes.values()])
    if no_masks or "evt" not in rasters:
        return

    # Iterate through sets of EVT codes. Skip any empty groups
    log.info("Building EVT masks")
    for name, values in codes.items():
        if len(values) == 0:
            continue

        # Get the mask
        log.debug(f"    Locating {name} pixels")
        mask = rasters["evt"].find(values)

        # Combine with pre-existing, file-based mask if available
        raster = masks[name]
        if raster in rasters:
            log.debug(f'    Merging {name} mask with "{raster}" file')
            mask = mask.values | rasters[raster].values
            mask = Raster.from_array(mask, nodata=False, spatial=rasters["evt"])
        rasters[raster] = mask
