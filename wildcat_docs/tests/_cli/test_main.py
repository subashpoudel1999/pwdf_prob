import traceback as tb

import pytest

from wildcat._cli._main import main


@pytest.fixture
def bad_project(project):
    path = project / "not-empty.txt"
    with open(path, "w") as file:
        file.write("The project folder is not empty")
    return project


class TestMain:
    def test_default_log(_, project, CleanCLI, capsys):
        with CleanCLI:
            main(["initialize", str(project)])
        assert capsys.readouterr().err == "Initializing project\n"

    def test_verbose(_, project, CleanCLI, capsys):
        with CleanCLI:
            main(["initialize", str(project), "--verbose"])
        assert capsys.readouterr().err == (
            f"Initializing project\n"
            f"    Located project folder: {project}\n"
            f"    Initializing inputs subfolder\n"
            f"    Writing configuration file\n"
        )

    def test_quiet(_, project, CleanCLI, capsys):
        with CleanCLI:
            main(["initialize", str(project), "--quiet"])
        assert capsys.readouterr().err == ""

    def test_log_file(_, project, outtext, CleanCLI, capsys):
        logfile = project.parent / "log.txt"
        with CleanCLI:
            main(["initialize", str(project), "--quiet", "--log", str(logfile)])
        assert capsys.readouterr().err == ""

        output = outtext(logfile)
        expected = [
            "- Initializing project",
            "-     Located project folder",
            "-     Initializing inputs subfolder",
            "-     Writing configuration file",
        ]
        for record in expected:
            assert record in output

    def test_no_traceback(_, CleanCLI, bad_project):
        with CleanCLI:
            try:
                main(["initialize", str(bad_project)])
            except Exception:
                output = tb.format_exc()
        assert output.startswith(
            "FileExistsError: Cannot initialize project because the project folder is not empty."
        )
        assert "Traceback" not in output

    def test_with_traceback(_, CleanCLI, bad_project):
        with CleanCLI:
            try:
                main(["initialize", str(bad_project), "--show-traceback"])
            except Exception:
                output = tb.format_exc()

        assert output.startswith("Traceback")
        expected = [
            "in initialize",
            "project = _validate_project(project, log)",
            "raise FileExistsError",
        ]
        for message in expected:
            assert message in output
