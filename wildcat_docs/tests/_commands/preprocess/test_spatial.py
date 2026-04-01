import numpy as np
from pfdf.raster import Raster

from wildcat._commands.preprocess import _spatial


class TestReproject:
    def test(_, logcheck):
        dem = Raster(np.arange(100).reshape(10, 10))
        perimeter = Raster(np.arange(400).reshape(20, 20))
        dnbr = Raster(np.arange(1000).reshape(20, 50))

        dem.crs = 26911
        perimeter.crs = 26910
        dnbr.crs = 4326

        dem.transform = (10, -10, 134891, 3880360)
        perimeter.transform = (6, -12, 682516, 3874870)
        dnbr.transform = (9e-5, -9e-5, -121, 35)

        rasters = {"dem": dem, "perimeter": perimeter, "dnbr": dnbr}
        _spatial.reproject(rasters, logcheck.log)

        for raster in rasters.values():
            assert raster.crs == 26911
            assert raster.resolution() == (10, 10)

        logcheck.check(
            [
                ("INFO", "Reprojecting rasters to match the DEM"),
                ("DEBUG", "    Reprojecting perimeter"),
                ("DEBUG", "    Reprojecting dnbr"),
            ]
        )


class TestClip:
    def test(_, logcheck):
        dem = Raster(np.arange(100).reshape(10, 10))
        perimeter = Raster(np.arange(400).reshape(20, 20))
        dnbr = Raster(np.arange(1000).reshape(20, 50))

        dem.crs = 26911
        perimeter.crs = 26911
        dnbr.crs = 26911

        perimeter.transform = (10, -10, 134891, 3880360)
        dnbr.transform = (10, -10, 134991, 3880760)
        dem.transform = (10, -10, 134591, 3881360)
        bounds = perimeter.bounds
        shape = perimeter.shape

        rasters = {"dem": dem, "perimeter": perimeter, "dnbr": dnbr}
        _spatial.clip(rasters, logcheck.log)

        for raster in rasters.values():
            assert raster.bounds == bounds
            assert raster.shape == shape
