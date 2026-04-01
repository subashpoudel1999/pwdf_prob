from pathlib import Path

import pytest

from wildcat import version
from wildcat._utils._config import record


@pytest.fixture
def file(tmp_path):
    return Path(tmp_path) / "configuration.txt"


class TestParameter:
    def test_standard(_, file, outtext):
        with open(file, "w") as f:
            record._parameter(f, "test", 5)
        assert outtext(file) == "test = 5\n"

    def test_string(_, file, outtext):
        with open(file, "w") as f:
            record._parameter(f, "test", "some text")
        assert outtext(file) == 'test = "some text"\n'

    def test_path(_, file, outtext):
        path = Path(r"a/file/path")
        with open(file, "w") as f:
            record._parameter(f, "test", path)
        allowed = ['test = r"a/file/path"\n', 'test = r"a\\file\\path"\n']
        assert outtext(file) in allowed


class TestTitle:
    def test(_, file, outtext):
        with open(file, "w") as f:
            record._title(f, "Test Heading")
        assert outtext(file) == "# Test Heading\n"


class TestSection:
    def test_no_paths(_, file, outtext):
        config = {
            "string": "here is some text",
            "float": 2.2,
            "sequence": [1, 2, 3.3],
            "none": None,
            "bool": False,
        }
        with open(file, "w") as f:
            record.section(f, "Test Group", config.keys(), config)
        assert outtext(file) == (
            "# Test Group\n"
            'string = "here is some text"\n'
            "float = 2.2\n"
            "sequence = [1, 2, 3.3]\n"
            "none = None\n"
            "bool = False\n"
            "\n"
        )

    def test_with_path(_, file, outtext):
        config = {
            "string": "here is some text",
            "float": 2.2,
            "path": Path("test"),
        }
        absolute = Path("the") / "full" / "file" / "path"
        paths = {"path": absolute}
        with open(file, "w") as f:
            record.section(f, "Test Group", config.keys(), config, paths)
        assert outtext(file) == (
            "# Test Group\n"
            'string = "here is some text"\n'
            "float = 2.2\n"
            f'path = r"{absolute}"\n'
            "\n"
        )

    def test_missing_path(_, file, outtext):
        config = {
            "string": "here is some text",
            "float": 2.2,
            "path": Path("default"),
        }
        paths = {}
        with open(file, "w") as f:
            record.section(f, "Test Group", config.keys(), config, paths)
        assert outtext(file) == (
            "# Test Group\n"
            'string = "here is some text"\n'
            "float = 2.2\n"
            f"path = None\n"
            "\n"
        )


class TestVersion:
    def test(_, file, outtext):
        with open(file, "w") as f:
            record.version(f, "Test configuration")
        assert outtext(file) == f"# Test configuration for wildcat v{version()}\n\n"
