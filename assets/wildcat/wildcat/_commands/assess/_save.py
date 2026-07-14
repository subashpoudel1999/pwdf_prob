"""
Functions that save assessment results to file
----------
Functions:
    _finalize   - Finalizes a property dict for geojson export
    results     - Saves the segments, basins, and outlets
    config      - Saves the configuration settings
"""

from __future__ import annotations

import typing

import wildcat._utils._paths.assess as _paths
from wildcat._utils import _parameters
from wildcat._utils._config import record

if typing.TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path

    from pfdf.segments import Segments

    from wildcat.typing._assess import Config, PathDict, PropertyDict


def _finalize(config: Config, properties: PropertyDict) -> None:
    "Converts result arrays to dynamically named vectors"

    # I15 variables
    nI15, nCI, nDurations, nProb = _parameters.count(config)
    if "hazard" in properties:
        for i in range(nI15):
            properties[f"H_{i}"] = properties["hazard"][:, i, 0]
            properties[f"P_{i}"] = properties["likelihood"][:, i, 0]
            properties[f"V_{i}"] = properties["V"][:, i, 0]

            # Volume confidence intervals
            for c in range(nCI):
                properties[f"Vmin_{i}_{c}"] = properties["Vmin"][:, i, 0, c]
                properties[f"Vmax_{i}_{c}"] = properties["Vmax"][:, i, 0, c]

    # Rainfall thresholds
    if "accumulations" in properties:
        for d in range(nDurations):
            for p in range(nProb):
                properties[f"I_{d}_{p}"] = properties["intensities"][:, p, d]
                properties[f"R_{d}_{p}"] = properties["accumulations"][:, p, d]

    # Remove arrays
    for field in [
        "hazard",
        "likelihood",
        "V",
        "Vmin",
        "Vmax",
        "accumulations",
        "intensities",
    ]:
        if field in properties:
            del properties[field]


def results(
    assessment: Path,
    config: Config,
    segments: Segments,
    properties: PropertyDict,
    log: Logger,
) -> None:
    "Saves segments, basins, and outlets"

    # Convert modeled arrays to vectors using dynamic naming
    log.info("Saving results")
    log.debug("    Finalizing properties")
    _finalize(config, properties)

    # Save segments
    log.debug("    Saving segments")
    segments.save(
        assessment / "segments.geojson", "segments", properties, overwrite=True
    )

    # Optionally save basins
    if config["locate_basins"]:
        log.debug("    Saving basins")
        segments.save(
            assessment / "basins.geojson", "basins", properties, overwrite=True
        )

    # Remove nested basins
    log.debug("    Removing nested drainages")
    nested = segments.isnested()
    segments.remove(nested)
    properties = {name: values[~nested] for name, values in properties.items()}

    # Export outlets
    log.debug("    Saving outlets")
    segments.save(assessment / "outlets.geojson", "outlets", overwrite=True)


def config(assessment: Path, config: Config, paths: PathDict, log: Logger) -> None:
    "Save the configuration settings for the assessment"

    # Start log and get path
    log.debug("    Saving configuration.txt")
    file = assessment / "configuration.txt"

    # Write each section
    with open(file, "w") as file:
        record.version(file, "Assessment configuration")
        record.section(file, "Preprocessed rasters", _paths.all(), config, paths)
        record.section(file, "Unit conversions", ["dem_per_m"], config)
        record.section(
            file,
            "Network delineation",
            ["min_area_km2", "min_burned_area_km2", "max_length_m"],
            config,
        )
        record.section(
            file,
            "Filtering",
            [
                "max_area_km2",
                "max_exterior_ratio",
                "min_burn_ratio",
                "min_slope",
                "max_developed_area_km2",
                "max_confinement",
                "confinement_neighborhood",
                "flow_continuous",
            ],
            config,
        )
        record.section(file, "Removed segments", ["remove_ids"], config)
        record.section(
            file,
            "Hazard Modeling",
            ["I15_mm_hr", "volume_CI", "durations", "probabilities"],
            config,
        )
        record.section(file, "Basins", ["locate_basins", "parallelize_basins"], config)
