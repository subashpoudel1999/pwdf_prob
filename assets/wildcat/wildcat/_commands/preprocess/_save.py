"""
Functions that save results from the preprocessor
----------
Functions:
    rasters - Saves preprocessed rasters as GeoTiff files
    config  - Saves the configuration settings used to run the preprocessor
"""

from __future__ import annotations

import typing

import wildcat._utils._paths.preprocess as _paths
from wildcat._utils._config import record

if typing.TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path

    from wildcat.typing import Config, PathDict, RasterDict


def rasters(preprocessed: Path, rasters: RasterDict, log: Logger) -> None:
    "Saves all preprocessed rasters as GeoTIFF files in the 'preprocessed' folder"

    log.info("Saving preprocessed rasters")
    for name, raster in rasters.items():
        log.debug(f"    Saving {name}")
        file = preprocessed / f"{name}.tif"
        raster.save(file, overwrite=True)


def config(
    preprocessed: Path,
    config: Config,
    paths: PathDict,
    log: Logger,
) -> None:
    "Saves the configuration values used to run the preprocessor"

    # Write the configuration to configuration.txt
    log.debug("    Saving configuration.txt")
    file = preprocessed / "configuration.txt"

    # Write each section
    with open(file, "w") as file:
        record.version(file, "Preprocessor configuration")
        record.section(file, "Input datasets", _paths.standard(), config, paths)
        record.section(file, "Perimeter", ["buffer_km"], config)
        record.section(file, "DEM", ["resolution_limits_m", "resolution_check"], config)
        record.section(
            file,
            "dNBR",
            ["dnbr_scaling_check", "constrain_dnbr", "dnbr_limits"],
            config,
        )
        record.section(
            file,
            "Burn Severity",
            [
                "severity_field",
                "estimate_severity",
                "severity_thresholds",
                "contain_severity",
            ],
            config,
        )
        record.section(
            file,
            "KF-factors",
            [
                "kf_field",
                "constrain_kf",
                "max_missing_kf_ratio",
                "missing_kf_check",
                "kf_fill",
                "kf_fill_field",
            ],
            config,
            paths,
        )
        record.section(
            file, "EVT masks", ["water", "developed", "excluded_evt"], config
        ),
