from pathlib import Path

import pytest

from wildcat._utils._find import _file


class TestScanExtensions:
    def test_in_list(_, raster):
        path = raster.parent / raster.stem
        output = _file._scan_extensions(path, [".csv", ".md", ".txt", ".tif"])
        assert output == raster

    def test_missing(_, missing):
        output = _file._scan_extensions(missing, [".tif", ".shp", ".txt"])
        assert output is None


class TestResolvePath:
    def test_missing(_, inputs, missing):
        output = _file._resolve_path(inputs, missing, False)
        assert output is None

    def test_relative(_, raster):
        output = _file._resolve_path(raster.parent, Path(raster.name), False)
        assert output == raster

    def test_absolute(_, raster):
        output = _file._resolve_path(raster.parent, raster, False)
        assert output == raster

    def test_raster_extension(_, raster):
        output = _file._resolve_path(raster.parent, Path(raster.stem), False)
        assert output == raster

    def test_vector_extension(_, vector):
        output = _file._resolve_path(vector.parent, Path(vector.stem), True)
        assert output == vector


class TestFile:
    def test_missing_optional(_, missing):
        output = _file.file(missing.parent, Path("dem"), "dem", False, False)
        assert output is None

    def test_missing_required(_, inputs, missing, errcheck):
        with pytest.raises(FileNotFoundError) as error:
            _file.file(inputs, missing, "dem", True, False)
        errcheck(error, "Could not locate the dem file")

    def test_missing_altered(_, inputs, missing, errcheck):
        with pytest.raises(FileNotFoundError) as error:
            _file.file(inputs, missing, "dem", False, False)
        errcheck(error, "Could not locate the dem file")

    def test_relative(_, raster):
        output = _file.file(raster.parent, Path(raster.name), "test", True, False)
        assert output == raster

    def test_absolute(_, raster):
        output = _file.file(raster.parent, raster, "test", True, False)
        assert output == raster

    def test_raster_extension(_, raster):
        output = _file.file(raster.parent, Path(raster.stem), "test", True, False)
        assert output == raster

    def test_vector_extension(_, vector):
        output = _file.file(vector.parent, Path(vector.stem), "test", True, True)
        assert output == vector
