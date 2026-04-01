"""
Functions to design and manage the stream segment network
----------
Functions:
    delineate       - Delineates the initial stream segment network
    filter          - Filters the network to model worthy segments
    remove_ids      - Removes explicit IDs from the network
    locate_basins   - Locates the outlet basins

Utilities:
    _mask           - Returns a value for mask that can be used in logical expressions
    _developed_area - Computes the developed area in km2
    _included       - Indicates whether segments intersect an included area
"""

from __future__ import annotations

import typing

import numpy as np
from pfdf.segments import Segments

if typing.TYPE_CHECKING:
    from logging import Logger

    from wildcat.typing._assess import Config, PropertyDict, RasterDict


def delineate(config: Config, rasters: RasterDict, log: Logger) -> Segments:
    "Delineates a stream segment network"

    # Extract config settings
    log.info("Delineating initial network")
    min_area = config["min_area_km2"]
    min_burned_area = config["min_burned_area_km2"]
    max_length = config["max_length_m"]

    # Extract relevant raster data grids
    area = rasters["area"].values
    burned_area = rasters["burned-area"].values
    in_perimeter = rasters["perimeter"].values

    # Build essential delineation masks
    log.debug("    Building delineation mask")
    large_enough = area >= min_area
    below_burn = burned_area >= min_burned_area

    # Get optional exclusion masks
    retained = _mask(rasters, "nretainments", log, "areas below retainment features")
    water = _mask(rasters, "iswater", log, "water bodies")
    excluded = _mask(rasters, "excluded", log, "excluded areas")

    # Get the final mask and delineate
    log.debug("    Building network")
    mask = large_enough & (below_burn | in_perimeter) & ~retained & ~water & ~excluded
    return Segments(rasters["flow"], mask, max_length)


def _mask(
    rasters: RasterDict, name: str, log: Logger, description: str
) -> np.ndarray | np.bool:
    "Returns a value for an optional mask that can be used in logical expressions"

    # Just return False if the mask is not provided
    if name not in rasters:
        return np.bool(False)

    # Log and return mask
    log.debug(f"    Removing {description}")
    mask = rasters[name].values
    if mask.dtype != bool:
        mask = mask > 0
    return mask


def filter(
    config: Config, segments: Segments, rasters: RasterDict, log: Logger
) -> PropertyDict:
    "Filters the network to model-worthy segments"

    # Start log. Extract config settings and perimeter mask
    log.info("Filtering network")
    dem_per_m = config["dem_per_m"]
    max_area = config["max_area_km2"]
    max_exterior_ratio = config["max_exterior_ratio"]
    min_burn_ratio = config["min_burn_ratio"]
    min_slope = config["min_slope"]
    max_developed_area = config["max_developed_area_km2"]
    max_confinement = config["max_confinement"]
    neighborhood = config["confinement_neighborhood"]
    flow_continuous = config["flow_continuous"]
    perimeter = rasters["perimeter"].values

    # Compute physical variables characterizing the segments
    log.debug("    Characterizing segments")
    area = segments.area(units="kilometers")
    exterior_ratio = segments.catchment_ratio(~perimeter)
    burn_ratio = segments.burn_ratio(rasters["burned"])
    slopes = segments.slope(rasters["slopes"])
    confinement = segments.confinement(rasters["dem"], neighborhood, dem_per_m)
    developed_area = _developed_area(segments, rasters)

    # Determine which segments meet filtering criteria
    included = _included(segments, rasters)
    floodlike = area > max_area
    intersects_perimeter = segments.in_perimeter(perimeter)
    exterior = exterior_ratio >= max_exterior_ratio
    burned = burn_ratio >= min_burn_ratio
    steep = slopes >= min_slope
    confined = confinement <= max_confinement
    undeveloped = developed_area <= max_developed_area

    # Determine which segments to keep
    physical = burned & steep & confined & undeveloped
    in_perimeter = intersects_perimeter & ~exterior
    at_risk = ~floodlike & (in_perimeter | physical)
    keep = included | at_risk

    # Optionally preserve flow continuity
    if flow_continuous:
        passed_filters = keep
        keep = segments.continuous(keep)
        flow_saved = keep & ~passed_filters
    else:
        flow_saved = np.zeros(segments.size, dtype=bool)

    # Collect variables
    variables = {
        # Watershed characteristics
        "Segment_ID": segments.ids,
        "Area_km2": area,
        "ExtRatio": exterior_ratio,
        "BurnRatio": burn_ratio,
        "Slope": slopes,
        "ConfAngle": confinement,
        "DevAreaKm2": developed_area,
        # Filters
        "IsIncluded": included,
        "IsFlood": floodlike,
        "IsAtRisk": at_risk,
        "IsInPerim": in_perimeter,
        "IsXPerim": intersects_perimeter,
        "IsExterior": exterior,
        "IsPhysical": physical,
        "IsBurned": burned,
        "IsSteep": steep,
        "IsConfined": confined,
        "IsUndev": undeveloped,
        "IsFlowSave": flow_saved,
    }

    # Filter network and return filtered variables
    log.debug("    Removing filtered segments")
    segments.keep(keep)
    return {name: values[keep] for name, values in variables.items()}


def _developed_area(segments: Segments, rasters: RasterDict) -> np.ndarray:
    "Returns the developed area (in km2) of the segments"

    if "isdeveloped" in rasters:
        return segments.developed_area(rasters["isdeveloped"], units="kilometers")
    else:
        return np.zeros(segments.size)


def _included(segments: Segments, rasters: RasterDict) -> np.ndarray:
    "Indicates whether segments intersect an included area"

    if "included" in rasters:
        return segments.in_mask(rasters["included"])
    else:
        return np.zeros(segments.size, dtype=bool)


def remove_ids(
    config: Config, segments: Segments, variables: PropertyDict, log: Logger
) -> None:
    "Removes explicitly listed IDs from the network"

    # Just exit if there aren't any listed segments
    ids = config["remove_ids"]
    if len(ids) == 0:
        return
    log.info("Removing listed segments")

    # Listed IDs must be in the network
    in_network = np.isin(ids, segments.ids)
    if not np.all(in_network):
        bad = np.argwhere(~in_network)[0, 0]
        bad = ids[bad]
        raise ValueError(
            f"Cannot remove ID {bad} from the network because the network does "
            "not contain a segment with this ID."
        )

    # Remove segments from the network and filter the property dict
    remove = np.isin(segments.ids, ids)
    segments.remove(remove)
    for name, values in variables.items():
        variables[name] = values[~remove]


def locate_basins(config: Config, segments: Segments, log: Logger) -> None:
    "Optionally locates the basins"

    if config["locate_basins"]:
        log.info("Locating outlet basins")
        segments.locate_basins(parallel=config["parallelize_basins"])
