from pathlib import Path

import pytest

from wildcat._utils._find import _folders


class TestFolder:
    def test_relative(_, project, inputs, logcheck):
        path = _folders._folder(project, Path("inputs"), "test", logcheck.log)
        assert path == inputs
        logcheck.check([("DEBUG", f"    test: {inputs}")])

    def test_absolute(_, inputs, logcheck):
        path = _folders._folder(None, inputs, "test", logcheck.log)
        assert path == inputs
        logcheck.check([("DEBUG", f"    test: {inputs}")])

    def test_not_exists(_, project, logcheck):
        path = _folders._folder(project, Path("missing"), "test", logcheck.log)
        assert path == project / "missing"

    def test_not_folder(_, raster, errcheck, logcheck):
        with pytest.raises(ValueError) as error:
            _folders._folder(None, raster, "test", logcheck.log)
        errcheck(error, "The 'test' path is not a folder")


class TestOutputFolder:
    def test_exists(_, project, outputs, logcheck):
        output = _folders._output_folder(
            project, Path(outputs.name), "test", logcheck.log
        )
        assert output == outputs
        logcheck.check([("DEBUG", f"    test: {outputs}")])

    def test_not_exists(_, project, missing, logcheck):
        output = _folders._output_folder(
            project, Path(missing.name), "test", logcheck.log
        )
        assert output == missing
        assert output.exists()
        assert output.is_dir()
        logcheck.check([("DEBUG", f"    test: {missing}")])


class TestInputFolder:
    def test_exists(_, project, inputs, logcheck):
        output = _folders._input_folder(
            project, Path(inputs.name), "inputs", logcheck.log
        )
        assert output == inputs
        logcheck.check([("DEBUG", f"    inputs: {inputs}")])

    def test_not_exists_default(_, project, logcheck):
        output = _folders._input_folder(project, Path("inputs"), "inputs", logcheck.log)
        expected = project / "inputs"
        assert output == expected
        logcheck.check([("DEBUG", f"    inputs: {expected}")])

    def test_not_exists_altered(_, project, missing, logcheck):
        output = _folders._input_folder(
            project, Path("missing"), "inputs", logcheck.log
        )
        assert output == missing
        logcheck.check(
            [
                ("DEBUG", f"    inputs: {missing}"),
                ("WARNING", "\nWARNING: The inputs folder does not exist.\n"),
            ]
        )


class TestIOFolders:
    def test(_, project, inputs, logcheck):
        inpath, outpath = _folders.io_folders(
            project, Path(inputs.name), "inputs", Path("new"), "outputs", logcheck.log
        )

        assert inpath == inputs
        assert outpath == project / "new"
        assert outpath.exists()

        logcheck.check(
            [
                ("INFO", "Locating IO folders"),
                ("DEBUG", f"    inputs: {inputs}"),
                ("DEBUG", f'    outputs: {project/"new"}'),
            ]
        )
