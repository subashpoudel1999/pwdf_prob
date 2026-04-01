from wildcat._utils import _extensions


def test_add_periods():
    a = ["a", "list", "of", "exts"]
    output = _extensions._add_periods(a)
    assert a == ["a", "list", "of", "exts"]
    assert output == [".a", ".list", ".of", ".exts"]


def test_raster():
    exts = _extensions.raster()
    assert ".tif" in exts
    assert ".tiff" in exts
    assert ".shp" not in exts


def test_vector():
    exts = _extensions.vector()
    assert ".shp" in exts
    assert ".geojson" in exts
    assert ".tif" not in exts
