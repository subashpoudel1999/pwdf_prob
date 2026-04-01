"""
Lists of supported file extensions for rasters and vector features
----------
Lists:
    raster          - Supported raster file extensions
    vector          - Supported vector-feature file extensions

Internal:
    _RASTER         - List of raster extensions
    _VECTOR         - List of vector extensions
    _add_periods    - Adds periods to the extensions in a list
"""

import fiona
import rasterio
from pfdf.utils import driver

_RASTER: list[str] = list(rasterio.drivers.raster_driver_extensions().keys())
_VECTOR: list[str] = list(fiona.drvsupport.vector_driver_extensions().keys())


def _add_periods(exts: list[str]) -> list[str]:
    "Adds periods to extensions"
    return [f".{ext}" for ext in exts]


def raster() -> list[str]:
    "Returns a list of supported raster file extensions"
    return _add_periods(_RASTER)


def vector() -> list[str]:
    "Returns a list of supported vector feature file extensions"
    return _add_periods(_VECTOR)


def from_format(format: str) -> str:
    "Returns the extension for a vector format driver"

    return driver.vectors().loc[format].Extensions.split(", ")[0]
