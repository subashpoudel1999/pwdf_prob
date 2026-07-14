"""
Functions that implement spatial preprocessing routines
----------
Functions:
    reproject   - Reprojects rasters to the same CRS, alignment, and resolution as the DEM
    clip        - Clips rasters to the bounds of the buffered perimeter
"""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from logging import Logger

    from wildcat.typing import RasterDict


def reproject(rasters: RasterDict, log: Logger) -> None:
    "Reprojects rasters to the same CRS, resolution, and alignment as the DEM"

    # Log step. Iterate through rasters, but skip the DEM
    log.info("Reprojecting rasters to match the DEM")
    for name, raster in rasters.items():
        if name == "dem":
            continue

        # Reproject to match the DEM
        log.debug(f"    Reprojecting {name}")
        raster.reproject(template=rasters["dem"], resampling="nearest")


def clip(rasters: RasterDict, log: Logger) -> None:
    "Clips rasters to the bounds of the perimeter"

    # Log step. Iterate through rasters, but skip the perimeter
    log.info("Clipping rasters to the buffered perimeter")
    for name, raster in rasters.items():
        if name == "perimeter":
            continue

        # Clip to the perimeter
        log.debug(f"    Clipping {name}")
        raster.clip(bounds=rasters["perimeter"])
