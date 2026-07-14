"""
Functions that reproject assessment results
----------
Functions:
    results     - Returns assessment results projected into a requested CRS
    _features   - Reprojects feature collection geometries in-place
"""

from __future__ import annotations

import typing

from fiona.transform import transform_geom
from pyproj import CRS

if typing.TYPE_CHECKING:
    from logging import Logger

    from wildcat.typing._export import Config, Records, Results


def results(results: Results, config: Config, log: Logger) -> Results:
    "Reprojects assessment results to match a requested CRS"

    # Just exit if there's no CRS
    fcrs = config["export_crs"]
    if fcrs is None:
        return results

    # Extract results and check if the CRS is changing. Exit if not
    icrs, schema, segments, basins, outlets = results
    icrs = CRS(icrs)
    if icrs == fcrs:
        return results

    # Reproject each set of features
    log.info(f"Reprojecting from {icrs.name} to {fcrs.name}")
    args = [icrs, fcrs, log]
    _features(segments, "segments", *args)
    _features(basins, "basins", *args)
    _features(outlets, "outlets", *args)

    # Return updated results
    return fcrs, schema, segments, basins, outlets


def _features(features: Records, name: str, icrs: CRS, fcrs: CRS, log: Logger) -> None:
    "Reprojects feature collection geometries in-place"

    # Skip empty features
    if features is None:
        return

    # Reproject the geometry
    log.debug(f"    Reprojecting {name}")
    for feature in features:
        feature["geometry"] = transform_geom(
            src_crs=icrs,
            dst_crs=fcrs,
            geom=feature["geometry"],
        )
