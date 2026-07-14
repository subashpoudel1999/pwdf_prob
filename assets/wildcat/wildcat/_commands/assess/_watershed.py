"""
Functions that analyze the watershed
----------
Functions:]
    severity_masks  - Builds the burn mask and moderate-high severity mask
    _mask           - Builds a burn severity mask
    characterize    - Computes flow directions, slopes, and vertical relief
    accumulation    - Computes flow accumulations
"""

from __future__ import annotations

import typing

from pfdf import severity, watershed

if typing.TYPE_CHECKING:
    from logging import Logger

    from wildcat.typing import Config, RasterDict


def severity_masks(rasters: RasterDict, log: Logger) -> None:
    "Builds burned and moderate-high severity raster masks"

    log.info("Building burn severity masks")
    rasters["burned"] = _mask(rasters, "burned areas", log)
    rasters["moderate-high"] = _mask(rasters, "moderate-high burn severity", log)


def _mask(rasters: RasterDict, description: str, log: Logger) -> None:
    "Builds a burn severity raster mask"

    log.debug(f"    Locating {description}")
    description = description.split(" ")[0].split("-")
    return severity.mask(rasters["severity"], description)


def characterize(config: Config, rasters: RasterDict, log: Logger) -> None:
    "Computes flow directions, slopes, and vertical relief"

    # Condition the DEM
    log.info("Characterizing watershed")
    log.debug("    Conditioning the DEM")
    conditioned = watershed.condition(rasters["dem"])

    # Flow directions
    log.debug("    Determining flow directions")
    flow = watershed.flow(conditioned)

    # Slopes
    log.debug("    Computing flow slopes")
    slopes = watershed.slopes(conditioned, flow, config["dem_per_m"], check_flow=False)

    # Vertical relief
    log.debug("    Computing vertical relief")
    relief = watershed.relief(conditioned, flow, check_flow=False)

    # Collect rasters
    rasters["flow"] = flow
    rasters["slopes"] = slopes
    rasters["relief"] = relief


def accumulation(rasters: RasterDict, log: Logger) -> None:
    "Computes flow accumulations"

    # Setup
    log.info("Computing flow accumulations")
    pixel_area = rasters["dem"].pixel_area(units="kilometers")
    flow = rasters["flow"]

    # Total area
    log.debug("    Total catchment area")
    rasters["area"] = watershed.accumulation(flow, times=pixel_area, check_flow=False)

    # Burned area
    log.debug("    Burned catchment area")
    rasters["burned-area"] = watershed.accumulation(
        flow, mask=rasters["burned"], times=pixel_area, check_flow=False
    )

    # Areas below retainment features
    if "retainments" in rasters:
        log.debug("    Areas below retainment features")
        rasters["nretainments"] = watershed.accumulation(
            flow, mask=rasters["retainments"], check_flow=False
        )
