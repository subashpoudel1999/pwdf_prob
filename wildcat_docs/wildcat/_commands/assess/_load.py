"""
Function to load preprocessed rasters
----------
Functions:
    datasets    - Loads preprocessed raster datasets
"""

from __future__ import annotations

import typing

from pfdf.raster import Raster

import wildcat._utils._paths.assess as _paths

if typing.TYPE_CHECKING:
    from logging import Logger

    from wildcat.typing import PathDict, RasterDict


def datasets(paths: PathDict, log: Logger) -> RasterDict:
    "Loads preprocessed raster datasets"

    # Start log and initialize raster dict
    log.info("Loading preprocessed rasters")
    rasters = {}

    # Iterate through datasets. Skip missing files
    for name_p, path in paths.items():
        if path is None:
            continue
        name = name_p.removesuffix("_p")

        # Load each preprocessed raster. Load masks as booleans
        log.debug(f"    Loading {name}")
        rasters[name] = Raster.from_file(
            path, name=name, isbool=name_p in _paths.masks()
        )
    return rasters
