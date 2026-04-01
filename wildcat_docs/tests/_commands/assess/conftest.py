"""
Fixtures that mimic pieces of an analysis
----------
Raster Metadata:
    crs             - A raster CRS
    transform       - A raster transform

Delineation Rasters:
    perimeter       - Fire perimeter mask
    flow            - Flow directions
    area            - Catchment area raster
    burned_area     - Burned catchment area raster
    retainmenets    - Retainment features
    mask            - A water or exclude mask

Stream rasters:
    stream          - Basic stream raster
    masked_stream   - Stream raster for masked bottom-left corner
    split_stream    - Stream raster when using a max length

Filtering simplifications:
    ones            - Raster of all ones
    trues           - Boolean raster that is all True
    falses          - Boolean raster is all False

Modeling rasters:
    modhigh         - Moderate-high burn severity mask
    dnbr            - A dNBR raster
    kf              - KF-factors
    slope23         - Slopes suitable for the M1 model
    relief          - Vertical relief raster

Misc:
    config          - Configuration settings
    rasters         - Raster collection
    segments        - Stream segment network

Property Dicts:
    ...
"""

from math import nan

import numpy as np
import pytest
from pfdf.models import c10, g14, s17
from pfdf.raster import Raster
from pfdf.segments import Segments
from pfdf.utils import intensity

#####
# Raster metadata
#####


@pytest.fixture
def crs():
    return 26911


@pytest.fixture
def transform():
    return (10, -10, 0, 0)


#####
# Delineation Rasters
#####


@pytest.fixture
def perimeter(crs, transform):
    perimeter = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0],
            [0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0],
            [0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0],
            [0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0],
            [0, 1, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0],
            [0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0],
            [0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ],
        dtype=bool,
    )
    return Raster.from_array(perimeter, crs=crs, transform=transform, isbool=True)


@pytest.fixture
def dem(crs, transform):
    dem = np.arange(144).reshape(12, 12)
    return Raster.from_array(dem, crs=crs, transform=transform)


@pytest.fixture
def flow(crs, transform):
    "TauDEM style flow directions"
    flow = np.array(
        [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, 7, 5, 5, 1, 7, 5, 1, 7, 5, 5, -1],
            [-1, 7, 5, 5, 1, 7, 5, 1, 7, 1, 1, -1],
            [-1, 7, 5, 5, 1, 7, 5, 1, 1, 1, 7, -1],
            [-1, 1, 1, 7, 7, 7, 5, 1, 1, 1, 7, -1],
            [-1, 7, 1, 1, 1, 7, 5, 1, 7, 5, 5, -1],
            [-1, 5, 7, 1, 1, 7, 5, 1, 7, 1, 1, -1],
            [-1, 1, 7, 7, 1, 1, 7, 1, 1, 1, 6, -1],
            [-1, 5, 7, 7, 7, 1, 1, 7, 1, 6, 5, -1],
            [-1, 5, 7, 7, 7, 7, 1, 1, 7, 5, 5, -1],
            [-1, 5, 5, 5, 5, 5, 7, 1, 7, 5, 5, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ]
    )
    return Raster.from_array(flow, crs=crs, transform=transform, nodata=-1)


@pytest.fixture
def area(crs, transform):
    """
    5 - Sufficiently large area
    4 - Sufficiently large but unburned in perimeter
    6 - Sufficiently large but unburned outside perimeter
    """
    area = np.array(
        [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, 5, 0, 0, 0, 5, 0, 0, 5, 5, 5, -1],
            [-1, 5, 0, 0, 0, 5, 0, 0, 5, 0, 0, -1],
            [-1, 5, 0, 0, 0, 5, 0, 0, 5, 5, 5, -1],
            [-1, 5, 5, 5, 0, 5, 0, 0, 0, 0, 5, -1],
            [-1, 0, 0, 5, 5, 4, 0, 0, 5, 5, 5, -1],
            [-1, 0, 0, 0, 0, 4, 0, 0, 5, 0, 0, -1],
            [-1, 5, 5, 0, 0, 4, 4, 0, 5, 5, 5, -1],
            [-1, 0, 5, 0, 0, 0, 4, 5, 0, 5, 6, -1],
            [-1, 0, 5, 0, 0, 0, 0, 5, 5, 6, 6, -1],
            [-1, 5, 5, 5, 5, 5, 0, 0, 5, 6, 6, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ]
    )
    return Raster.from_array(area, crs=crs, transform=transform, nodata=-1)


@pytest.fixture
def burned_area(crs, transform):
    """
    9: Burned area in perimeter
    8: Burned area outside perimeter
    2: Unburned area inside perimeter
    1: Unburned area outside perimeter
    """
    area = np.array(
        [
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
            [-1, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, -1],
            [-1, 8, 8, 8, 8, 8, 8, 8, 8, 8, 0, -1],
            [-1, 8, 8, 8, 8, 9, 9, 8, 8, 8, 8, -1],
            [-1, 8, 8, 9, 9, 9, 9, 9, 9, 8, 8, -1],
            [-1, 8, 8, 9, 9, 2, 9, 9, 9, 8, 8, -1],
            [-1, 9, 9, 9, 9, 2, 9, 9, 9, 8, 8, -1],
            [-1, 9, 9, 9, 9, 2, 2, 9, 9, 8, 8, -1],
            [-1, 9, 9, 9, 9, 9, 2, 8, 9, 8, 1, -1],
            [-1, 9, 9, 9, 9, 9, 8, 8, 8, 1, 1, -1],
            [-1, 9, 9, 8, 8, 8, 8, 8, 8, 1, 1, -1],
            [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
        ]
    )
    return Raster.from_array(area, crs=crs, transform=transform)


@pytest.fixture
def retainments(crs, transform):
    retainments = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 4, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ]
    )
    return Raster.from_array(retainments, crs=crs, transform=transform, nodata=-1)


@pytest.fixture
def mask(crs, transform):
    mask = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ],
        dtype=bool,
    )
    return Raster.from_array(mask, crs=crs, transform=transform, isbool=True)


#####
# Stream rasters
#####


@pytest.fixture
def stream(crs, transform):
    "The expected stream raster for the initial network"
    stream = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 2, 0, 0, 4, 4, 4, 0],
            [0, 1, 0, 0, 0, 2, 0, 0, 4, 0, 0, 0],
            [0, 1, 0, 0, 0, 2, 0, 0, 4, 4, 4, 0],
            [0, 1, 1, 1, 0, 2, 0, 0, 0, 0, 4, 0],
            [0, 0, 0, 1, 1, 3, 0, 0, 4, 4, 4, 0],
            [0, 0, 0, 0, 0, 3, 0, 0, 4, 0, 0, 0],
            [0, 6, 6, 0, 0, 3, 3, 0, 4, 4, 4, 0],
            [0, 0, 6, 0, 0, 0, 3, 3, 0, 4, 0, 0],
            [0, 0, 6, 0, 0, 0, 0, 3, 5, 0, 0, 0],
            [0, 8, 8, 7, 7, 7, 0, 0, 5, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ]
    )
    return Raster.from_array(stream, crs=crs, transform=transform, nodata=0)


@pytest.fixture
def masked_stream(crs, transform):
    stream = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 2, 0, 0, 4, 4, 4, 0],
            [0, 1, 0, 0, 0, 2, 0, 0, 4, 0, 0, 0],
            [0, 1, 0, 0, 0, 2, 0, 0, 4, 4, 4, 0],
            [0, 1, 1, 1, 0, 2, 0, 0, 0, 0, 4, 0],
            [0, 0, 0, 1, 1, 3, 0, 0, 4, 4, 4, 0],
            [0, 0, 0, 0, 0, 3, 0, 0, 4, 0, 0, 0],
            [0, 0, 0, 0, 0, 3, 3, 0, 4, 4, 4, 0],
            [0, 0, 0, 0, 0, 0, 3, 3, 0, 4, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 3, 5, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 5, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ]
    )
    return Raster.from_array(stream, crs=crs, transform=transform, nodata=0)


@pytest.fixture
def split_stream(crs, transform):
    "The expected stream raster for the initial network"
    stream = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 2, 0, 0, 4, 4, 4, 0],
            [0, 1, 0, 0, 0, 2, 0, 0, 4, 0, 0, 0],
            [0, 1, 0, 0, 0, 2, 0, 0, 4, 4, 4, 0],
            [0, 1, 1, 1, 0, 2, 0, 0, 0, 0, 4, 0],
            [0, 0, 0, 1, 1, 3, 0, 0, 5, 5, 4, 0],
            [0, 0, 0, 0, 0, 3, 0, 0, 5, 0, 0, 0],
            [0, 7, 7, 0, 0, 3, 3, 0, 5, 5, 5, 0],
            [0, 0, 7, 0, 0, 0, 3, 3, 0, 5, 0, 0],
            [0, 0, 7, 0, 0, 0, 0, 3, 6, 0, 0, 0],
            [0, 9, 9, 8, 8, 8, 0, 0, 6, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ]
    )
    return Raster.from_array(stream, crs=crs, transform=transform, nodata=0)


@pytest.fixture
def excluded(stream):
    excluded = stream.values == 0
    return Raster.from_array(excluded, isbool=True, spatial=stream)


#####
# Filtering simplifications
#####


@pytest.fixture
def ones(crs, transform):
    array = np.ones((12, 12))
    return Raster.from_array(array, crs=crs, transform=transform)


@pytest.fixture
def trues(crs, transform):
    array = np.ones((12, 12), bool)
    return Raster.from_array(array, crs=crs, transform=transform, isbool=True)


@pytest.fixture
def falses(crs, transform):
    array = np.zeros((12, 12), bool)
    return Raster.from_array(array, crs=crs, transform=transform, isbool=True)


#####
# Modeling rasters
#####


@pytest.fixture
def modhigh(crs, transform):
    modhigh = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0],
            [0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0],
            [0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0],
            [0, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ],
        dtype=bool,
    )
    return Raster.from_array(modhigh, crs=crs, transform=transform, isbool=True)


@pytest.fixture
def dnbr(crs, transform):
    dnbr = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 0],
            [0, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 0],
            [0, 100, 100, 100, 100, 999, 999, 100, 100, 100, 100, 0],
            [0, 100, 100, 400, 700, 700, 999, 999, 999, 100, 100, 0],
            [0, 100, 100, 400, 700, 700, 999, 999, 999, 100, 100, 0],
            [0, 400, 400, 400, 400, 400, 700, 700, 700, 100, 100, 0],
            [0, 200, 200, 200, 400, 400, 400, 400, 400, 100, 100, 0],
            [0, 200, 200, 200, 400, 400, 400, 100, 400, 100, 100, 0],
            [0, 200, 200, 200, 400, 400, 100, 100, 100, 100, 100, 0],
            [0, 200, 200, 100, 100, 100, 100, 100, 100, 100, 100, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ],
    )
    return Raster.from_array(dnbr, crs=crs, transform=transform)


@pytest.fixture
def severity(crs, transform):
    severity = np.array(
        [
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 4, 4, 1, 1, 1, 1, 1],
            [1, 1, 1, 3, 4, 4, 4, 4, 4, 1, 1, 1],
            [1, 1, 1, 3, 4, 4, 4, 4, 4, 1, 1, 1],
            [1, 3, 3, 3, 3, 3, 4, 4, 4, 1, 1, 1],
            [1, 2, 2, 2, 3, 3, 3, 3, 3, 1, 1, 1],
            [1, 2, 2, 2, 3, 3, 3, 1, 3, 1, 1, 1],
            [1, 2, 2, 2, 3, 3, 1, 1, 1, 1, 1, 1],
            [1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        ]
    )
    return Raster.from_array(severity, crs=crs, transform=transform)


@pytest.fixture
def kf(crs, transform):
    kf = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0],
            [0, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0],
            [0, 0.2, 0.2, nan, nan, nan, nan, 0.2, 0.2, 0.2, 0.2, 0],
            [0.2, 0.2, 0.2, nan, nan, nan, nan, 1.2, 1.2, 0.2, 0.2, 0],
            [0.2, 0.2, 0.2, nan, nan, nan, nan, 1.2, 1.2, 0.2, 0.2, 0],
            [0.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 0.2, 0.2, 0],
            [0.2, 0.2, 0.2, 0.2, 1.2, 1.2, 1.2, 1.2, 1.2, 0.2, 0.2, 0],
            [0.2, 0.2, 0.2, 0.2, 0.2, 1.2, 1.2, 0.2, 1.2, 0.2, 0.2, 0],
            [0.2, 0.2, 0.2, 0.2, 0.2, 1.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0],
            [0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0],
            [0, 0.2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ]
    )
    return Raster.from_array(kf, crs=crs, transform=transform, nodata=0)


@pytest.fixture
def slope23(crs, transform):
    slope = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0.4, 0.4, 0.5, 0.5, 0.5, 0.5, 0.4, 0.4, 0.4, 0.4, 0],
            [0, 0.4, 0.4, 0.5, 0.5, 0.5, 0.5, 0.4, 0.4, 0.4, 0.4, 0],
            [0, 0.4, 0.4, 0.5, 0.5, 0.5, 0.5, 0.4, 0.4, 0.4, 0.4, 0],
            [0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0],
            [0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0],
            [0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0],
            [0, 0.4, 0.4, 0.4, 0.4, 0.4, 0.5, 0.5, 0.5, 0.5, 0.4, 0],
            [0, 0.4, 0.4, 0.4, 0.5, 0.5, 0.4, 0.4, 0.4, 0.4, 0.4, 0],
            [0, 0.5, 0.5, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0],
            [0, 0.5, 0.5, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ]
    )
    return Raster.from_array(slope, crs=crs, transform=transform)


@pytest.fixture
def relief(crs, transform):
    relief = np.arange(144).reshape(12, 12)
    return Raster.from_array(relief, crs=crs, transform=transform)


#####
# Misc
#####


@pytest.fixture
def config():
    return {
        # Delineation
        "min_area_km2": 1,
        "min_burned_area_km2": 3,
        "max_length_m": 9000,
        # Permissive filtering by default
        "dem_per_m": 1,
        "max_area_km2": 1000,
        "max_exterior_ratio": 1,
        "min_burn_ratio": 0,
        "min_slope": 0,
        "max_developed_area_km2": 1000,
        "max_confinement": 1000,
        "confinement_neighborhood": 1,
        "flow_continuous": True,
        # Basins
        "locate_basins": True,
        "parallelize_basins": False,
        # Modeling
        "I15_mm_hr": [16, 20, 24],
        "volume_CI": [0.9, 0.95],
        "durations": [15, 30, 60],
        "probabilities": [0.5, 0.75],
    }


@pytest.fixture
def rasters(flow, perimeter, area, burned_area, ones, modhigh, dnbr, kf, relief):
    return {
        "flow": flow,
        "area": area,
        "burned-area": burned_area,
        "perimeter": perimeter,
        "burned": ones,
        "dem": ones,
        "slopes": ones,
        "moderate-high": modhigh,
        "dnbr": dnbr,
        "kf": kf,
        "relief": relief,
    }


@pytest.fixture
def segments(flow, stream):
    mask = stream.values > 0
    return Segments(flow, mask)


#####
# Property Dicts
#####


@pytest.fixture
def filter_vars(segments):
    props = {"Segment_ID": segments.ids}
    for field in [
        "Area_km2",
        "ExtRatio",
        "BurnRatio",
        "Slope",
        "ConfAngle",
        "DevAreaKm2",
    ]:
        props[field] = segments.area()
    props["InPerim"] = segments.area() > 0.0020
    return props


@pytest.fixture
def m1_vars(segments, rasters, slope23):
    rasters["slopes"] = slope23
    T, F, S = s17.M1.variables(
        segments,
        rasters["moderate-high"],
        rasters["slopes"],
        rasters["dnbr"],
        rasters["kf"],
        omitnan=True,
    )
    return {
        "Terrain_M1": T,
        "Fire_M1": F,
        "Soil_M1": S,
    }


@pytest.fixture
def volume_vars(segments, rasters):
    Bmh = segments.burned_area(rasters["moderate-high"], units="kilometers")
    relief = segments.relief(rasters["relief"])
    return {"Bmh_km2": Bmh, "Relief_m": relief}


@pytest.fixture
def model_inputs(m1_vars, volume_vars):
    return m1_vars | volume_vars


@pytest.fixture
def likelihoods(config, m1_vars):
    props = m1_vars
    R15 = intensity.to_accumulation(config["I15_mm_hr"], durations=15)
    B, Ct, Cf, Cs = s17.M1.parameters(durations=15)
    return s17.likelihood(
        R15,
        B,
        Ct,
        props["Terrain_M1"],
        Cf,
        props["Fire_M1"],
        Cs,
        props["Soil_M1"],
        keepdims=True,
    )


@pytest.fixture
def volumes(config, volume_vars):
    Bmh = volume_vars["Bmh_km2"]
    relief = volume_vars["Relief_m"]
    I15 = config["I15_mm_hr"]
    CI = config["volume_CI"]
    return g14.emergency(I15, Bmh, relief, CI=CI, keepdims=True)


@pytest.fixture
def i15_preresults(likelihoods, volumes):
    return {
        "likelihood": likelihoods,
        "V": volumes[0],
        "Vmin": volumes[1],
        "Vmax": volumes[2],
    }


@pytest.fixture
def i15_results(i15_preresults):
    props = i15_preresults
    props["hazard"] = c10.hazard(
        props["likelihood"],
        props["V"],
        p_thresholds=[0.2, 0.4, 0.6, 0.8],
    )
    return props


@pytest.fixture
def thresholds():
    return {
        "accumulations": np.array(
            [
                [
                    [9.43163365, 12.28609883],
                    [14.56379223, 18.99591443],
                    [24.88372093, 33.40009526],
                ],
                [
                    [6.51813013, 8.49082927],
                    [10.30136219, 13.43632149],
                    [17.28002349, 23.19405656],
                ],
                [
                    [4.89842804, 6.38092756],
                    [7.41402728, 9.67029915],
                    [13.07924121, 17.55556991],
                ],
                [
                    [5.16240969, 6.72480273],
                    [7.76378715, 10.12649961],
                    [13.96281737, 18.7415472],
                ],
                [
                    [5.37930364, 7.0073392],
                    [8.1201048, 10.59125353],
                    [14.45712746, 19.40503335],
                ],
                [
                    [6.94338179, 9.0447825],
                    [10.44560185, 13.62445685],
                    [18.88235294, 25.34477817],
                ],
                [
                    [9.7029997, 12.63959329],
                    [14.64173051, 19.09757125],
                    [27.88610039, 37.43002953],
                ],
                [
                    [8.89569612, 11.58796089],
                    [13.42319312, 17.50820279],
                    [25.00486855, 33.56270527],
                ],
            ]
        ).transpose(0, 2, 1),
        "intensities": np.array(
            [
                [
                    [37.72653459, 49.14439534],
                    [29.12758447, 37.99182885],
                    [24.88372093, 33.40009526],
                ],
                [
                    [26.07252052, 33.96331706],
                    [20.60272437, 26.87264298],
                    [17.28002349, 23.19405656],
                ],
                [
                    [19.59371217, 25.52371024],
                    [14.82805455, 19.34059831],
                    [13.07924121, 17.55556991],
                ],
                [
                    [20.64963877, 26.89921093],
                    [15.52757431, 20.25299922],
                    [13.96281737, 18.7415472],
                ],
                [
                    [21.51721456, 28.0293568],
                    [16.2402096, 21.18250706],
                    [14.45712746, 19.40503335],
                ],
                [
                    [27.77352716, 36.17912998],
                    [20.8912037, 27.24891371],
                    [18.88235294, 25.34477817],
                ],
                [
                    [38.81199881, 50.55837315],
                    [29.28346102, 38.19514249],
                    [27.88610039, 37.43002953],
                ],
                [
                    [35.5827845, 46.35184354],
                    [26.84638624, 35.01640559],
                    [25.00486855, 33.56270527],
                ],
            ]
        ).transpose(0, 2, 1),
    }


@pytest.fixture
def results(i15_results, thresholds):
    return i15_results | thresholds


@pytest.fixture
def unmodeled_vars(filter_vars, model_inputs):
    return filter_vars | model_inputs


@pytest.fixture
def all_props(unmodeled_vars, results):
    return unmodeled_vars | results
