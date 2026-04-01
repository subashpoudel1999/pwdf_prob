from pathlib import Path

import numpy as np
from pfdf.raster import Raster

from wildcat._commands.assess import _load


def rasterize(array, path):
    raster = Raster.from_array(array, crs=26911, bounds=(0, 0, 100, 100))
    raster.save(path)


class TestDatasets:
    def test(_, tmp_path, logcheck):

        # Get folder
        folder = Path(tmp_path) / "preprocessed"
        folder.mkdir(parents=True)

        # Perimeter
        perimeter = np.zeros((10, 10), bool)
        perimeter[2:4, :] = True
        rasterize(perimeter, folder / "perimeter.tif")

        # DEM
        dem = np.arange(100).reshape(10, 10)
        rasterize(dem, folder / "dem.tif")

        # dNBR
        dnbr = dem * 100
        rasterize(dnbr, folder / "dnbr.tif")

        # Excluded
        excluded = np.zeros((10, 10), bool)
        excluded[0::2, :] = True
        rasterize(excluded, folder / "excluded.tif")

        paths = {
            "perimeter_p": folder / "perimeter.tif",
            "dem_p": folder / "dem.tif",
            "dnbr_p": folder / "dnbr.tif",
            "excluded_p": folder / "excluded.tif",
            "iswater_p": None,
            "included_p": None,
        }
        rasters = _load.datasets(paths, logcheck.log)

        assert isinstance(rasters, dict)
        assert list(rasters.keys()) == ["perimeter", "dem", "dnbr", "excluded"]

        expected = {
            "perimeter": perimeter,
            "dem": dem,
            "dnbr": dnbr,
            "excluded": excluded,
        }
        for name, values in expected.items():
            assert rasters[name].crs == 26911
            assert rasters[name].bounds.tolist(crs=False) == [0, 0, 100, 100]
            assert np.array_equal(rasters[name].values, values)

        assert rasters["perimeter"].dtype == bool
        assert rasters["excluded"].dtype == bool

        logcheck.check(
            [
                ("INFO", "Loading preprocessed rasters"),
                ("DEBUG", "    Loading perimeter"),
                ("DEBUG", "    Loading dem"),
                ("DEBUG", "    Loading dnbr"),
                ("DEBUG", "    Loading excluded"),
            ]
        )
