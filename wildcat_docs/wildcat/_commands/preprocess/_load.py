"""
Functions that load datasets as rasters for the preprocessor
----------
Special Datasets:
    buffered_perimeter  - Loads and buffers the fire perimeter
    dem                 - Loads the DEM in the perimeter, requiring georeferencing
    constants           - Builds constant-valued datasets

General Loading:
    datasets            - Loads the remaining datasets as rasters
    _load_features      - Loads vector feature datasets
    _rasterize          - Converts a vector feature dataset to a raster
    _load_raster        - Loads a raster from file
"""

from __future__ import annotations

import typing
import warnings

import numpy as np
from pfdf.errors import NoOverlapError, NoOverlappingFeaturesError
from pfdf.raster import Raster
from pfdf.utils.nodata import default as default_nodata
from rasterio.errors import NotGeoreferencedWarning

import wildcat._utils._paths.preprocess as _paths
from wildcat._utils import _extensions
from wildcat.errors import GeoreferencingError

if typing.TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path
    from typing import Callable

    from wildcat.typing import Config, PathDict, RasterDict


#####
# Special Datasets
#####


def buffered_perimeter(config: Config, paths: PathDict, log: Logger) -> Raster:
    "Loads and buffers a fire perimeter"

    # Log step and extract inputs
    log.info("Building buffered burn perimeter")
    perimeter = paths["perimeter"]
    buffer_km = config["buffer_km"]

    # Load the initial raster
    log.debug("    Loading perimeter mask")
    if perimeter.suffix in _extensions.vector():
        perimeter = Raster.from_polygons(perimeter, resolution=10, units="meters")
    else:
        perimeter = Raster.from_file(perimeter, isbool=True)
    perimeter.name = "perimeter"

    # Buffer
    log.debug("    Buffering perimeter")
    perimeter.buffer(buffer_km, units="kilometers")
    return perimeter


def dem(paths: PathDict, perimeter: Raster, log: Logger) -> Raster:
    "Loads the DEM in the perimeter, requiring georeferencing"

    # Load the file
    log.info("Loading DEM")
    with warnings.catch_warnings(action="error", category=NotGeoreferencedWarning):
        try:
            dem = Raster.from_file(paths["dem"], name="dem", bounds=perimeter)

        # Informative error if missing a transform
        except NotGeoreferencedWarning:
            raise GeoreferencingError(
                "The input DEM does not have an affine transform. Please provide "
                "a properly georeferenced DEM instead."
            )
    return dem


def constants(config: Config, rasters: RasterDict, log: Logger) -> None:
    "Builds rasters that are constant values"

    # Iterate through datasets that are constants
    log_step = True
    for name in _paths.constant():
        value = config[name]
        if not isinstance(value, (int, float)):
            continue

        # Log the main step once and each individual raster
        if log_step:
            log.info("Building constant-valued rasters")
            log_step = False
        log.debug(f"    Building {name}")

        # Build the raster. Ensure the NoData value is not the same as the data value
        values = np.full(rasters["dem"].shape, value)
        nodata = default_nodata(values.dtype)
        if nodata == value:
            nodata = 0
        rasters[name] = Raster.from_array(values, nodata=nodata, spatial=rasters["dem"])


#####
# General Loading
#####


def datasets(
    config: Config, paths: PathDict, perimeter: Raster, dem: Raster, log: Logger
) -> RasterDict:
    """Loads all remaining datasets as rasters. Returns all loaded rasters
    (including the perimeter and DEM) in a dict"""

    # Initialize rasters dict. Exit if there aren't other file datasets. Log step
    rasters = {"perimeter": perimeter, "dem": dem}
    if len(paths) == 2:
        return rasters
    log.info("Loading file-based datasets")

    # Iterate through remaining file-based datasets.
    for name, path in paths.items():
        if name in ["perimeter", "dem"]:
            continue
        log.debug(f"    Loading {name}")

        # Load vector features or raster datasets, as appropriate
        if name in _paths.features() and path.suffix in _extensions.vector():
            raster = _load_features(name, path, perimeter, dem, config)
        else:
            raster = _load_raster(name, path, perimeter)

        # Name and record each raster
        rasters[name] = raster
    return rasters


def _load_features(
    name: str, path: Path, perimeter: Raster, dem: Raster, config: Config
) -> Raster:
    "Loads vector feature datasets"

    # Collect resolution and bounds
    kwargs = {"path": path, "resolution": dem, "bounds": perimeter}

    # Retainment features are points
    if name == "retainments":
        raster = _rasterize(name, Raster.from_points, kwargs)

    # KF and severity require a field
    elif name in _paths.field():
        field_arg = f"{name}_field"
        field = config[field_arg]
        if field is None:
            raise ValueError(
                f"{name} is a vector feature file, so {field_arg} cannot be None."
            )

        # Load the field features
        kwargs["field"] = field
        raster = _rasterize(name, Raster.from_polygons, kwargs)

    # All other features are masks
    else:
        raster = _rasterize(name, Raster.from_polygons, kwargs)

    # Name each raster to improve later error messages
    raster.name = name
    return raster


def _rasterize(name: str, factory: Callable, kwargs: dict) -> Raster:
    "Converts a feature dataset to a raster, providing informative errors as needed"

    try:
        return factory(**kwargs)
    except NoOverlappingFeaturesError as error:
        raise NoOverlappingFeaturesError(
            f"The {name} dataset does not overlap the buffered fire perimeter"
        ) from None


def _load_raster(name: str, path: Path, perimeter: Raster) -> Raster:
    "Loads a raster, providing informative errors as needed"

    try:
        return Raster.from_file(path, name=name, bounds=perimeter)
    except NoOverlapError as error:
        raise NoOverlapError(
            f"The {name} dataset does not overlap the buffered fire perimeter"
        ) from None
