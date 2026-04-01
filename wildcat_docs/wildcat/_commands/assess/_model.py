"""
Functions used to run hazard assessment models
----------
Main Functions:
    i15_hazard      - Estimates likelihood, volume, and relative hazard
    thresholds      - Computes rainfall thresholds needed for queried probabilities

Utilities:
    _m1_variables   - Computes the terrain, fire, and soil variables for the M1 model
    _likelihood      - Estimates debris-flow likelihood
    _volume          - Estimates debris-flow volumes
    _hazard          - Classifies relative hazard
"""

from __future__ import annotations

import typing

from pfdf.models import c10, g14, s17
from pfdf.utils import intensity

if typing.TYPE_CHECKING:
    from logging import Logger

    from pfdf.segments import Segments

    from wildcat.typing._assess import Config, PropertyDict, RasterDict

#####
# Main Functions
#####


def i15_hazard(
    config: Config,
    segments: Segments,
    rasters: RasterDict,
    properties: PropertyDict,
    log: Logger,
):
    "Estimates likelihood, volume, and hazard class when there are I15 values"

    # Just exit if there aren't intensities
    I15 = config["I15_mm_hr"]
    if len(I15) == 0:
        return

    # Estimate likelihood and volume. Classify hazard
    _likelihood(I15, segments, rasters, properties, log)
    _volume(config, segments, rasters, properties, log)
    _hazard(properties, log)


def thresholds(
    config: Config,
    segments: Segments,
    rasters: RasterDict,
    properties: PropertyDict,
    log: Logger,
) -> None:
    "Estimates rainfall thresholds using the S17 M1 model"

    # Exit if either durations or p are empty
    durations = config["durations"]
    p = config["probabilities"]
    if len(durations) == 0 or len(p) == 0:
        return

    # Get parameters and M1 variables
    log.info("Estimating rainfall thresholds")
    B, Ct, Cf, Cs = s17.M1.parameters(durations)
    _m1_variables(segments, rasters, properties, log)

    # Compute the threshold accumulations and convert to intensities
    log.debug("    Running model")
    accumulations = s17.accumulation(
        p,
        B,
        Ct,
        properties["Terrain_M1"],
        Cf,
        properties["Fire_M1"],
        Cs,
        properties["Soil_M1"],
        keepdims=True,
    )
    intensities = intensity.from_accumulation(accumulations, durations)

    # Collect results
    properties["accumulations"] = accumulations
    properties["intensities"] = intensities


#####
# Utilities
#####


def _m1_variables(
    segments: Segments, rasters: RasterDict, properties: PropertyDict, log: Logger
):
    "Computes the M1 variables for the segments"

    # Just exit if the variables were already computed
    if "Terrain_M1" in properties:
        return

    # Compute the variables
    log.debug("    Computing M1 variables")
    T, F, S = s17.M1.variables(
        segments,
        rasters["moderate-high"],
        rasters["slopes"],
        rasters["dnbr"],
        rasters["kf"],
        omitnan=True,
    )

    # Record as properties
    properties["Terrain_M1"] = T
    properties["Fire_M1"] = F
    properties["Soil_M1"] = S


def _likelihood(
    I15: list[float],
    segments: Segments,
    rasters: RasterDict,
    properties: PropertyDict,
    log: Logger,
) -> None:
    "Estimates debris-flow likelihood using the S17 M1 model"

    # Start log. Convert intensities to accumulations. Get parameters and variables
    log.info("Estimating debris-flow likelihood")
    R15 = intensity.to_accumulation(I15, durations=15)
    B, Ct, Cf, Cs = s17.M1.parameters(durations=15)
    _m1_variables(segments, rasters, properties, log)

    # Run the model and save the results
    log.debug("    Running model")
    properties["likelihood"] = s17.likelihood(
        R15,
        B,
        Ct,
        properties["Terrain_M1"],
        Cf,
        properties["Fire_M1"],
        Cs,
        properties["Soil_M1"],
        keepdims=True,
    )


def _volume(
    config: Config,
    segments: Segments,
    rasters: RasterDict,
    properties: PropertyDict,
    log: Logger,
) -> None:
    "Estimates potential sediment volume using the G14 emergency assessment model"

    # Start log and extract config fields
    log.info("Estimating potential sediment volume")
    I15 = config["I15_mm_hr"]
    CI = config["volume_CI"]
    dem_per_m = config["dem_per_m"]

    # Compute variables
    log.debug("    Computing catchment area burned at moderate-or-high severity")
    Bmh_km2 = segments.burned_area(rasters["moderate-high"], units="kilometers")
    log.debug("    Computing vertical relief")
    relief = segments.relief(rasters["relief"])
    relief = relief / dem_per_m

    # Run the model
    log.debug("    Running model")
    V, Vmin, Vmax = g14.emergency(I15, Bmh_km2, relief, CI=CI, keepdims=True)

    # Collect model variables and outputs
    properties["Bmh_km2"] = Bmh_km2
    properties["Relief_m"] = relief
    properties["V"] = V
    properties["Vmin"] = Vmin
    properties["Vmax"] = Vmax


def _hazard(properties: PropertyDict, log: Logger) -> None:
    "Classifies relative hazard using a modification of the C10 scheme"

    log.info("Classifying combined hazard")
    properties["hazard"] = c10.hazard(
        properties["likelihood"],
        properties["V"],
        p_thresholds=[0.2, 0.4, 0.6, 0.8],
    )
