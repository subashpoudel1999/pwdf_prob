from pathlib import Path

import pytest

from wildcat._cli import _kwargs, _parsers


def check(output, expected):
    for name, value in expected.items():
        assert output[name] == value


def run(command, args, expected):
    args = [command] + args
    args = _parsers.main().parse_args(args)
    converter = getattr(_kwargs, command)
    output = converter(args)
    check(output, expected)


class TestInitialize:
    def run(_, args, expected):
        run("initialize", args, expected)

    def test_no_inputs(self):
        self.run(
            ["--no-inputs"],
            {"project": None, "config": "default", "inputs": None},
        )

    def test_default_inputs(self):
        self.run(
            [],
            {"project": None, "config": "default", "inputs": "inputs"},
        )

    def test_custom_inputs(self):
        self.run(
            ["--inputs", "test"],
            {"project": None, "config": "default", "inputs": "test"},
        )

    def test_all_custom(self):
        self.run(
            ["test-project", "--inputs", "test-folder", "--config", "full"],
            {
                "project": Path("test-project"),
                "config": "full",
                "inputs": "test-folder",
            },
        )


class TestPreprocess:
    def run(_, args, expected):
        run("preprocess", args, expected)

    def test_default(self):
        expected = {
            "project": None,
            "buffer_km": None,
            "constrain_dnbr": True,
            "estimate_severity": True,
            "contain_severity": True,
            "constrain_kf": True,
            "kf_fill": None,
            "water": None,
            "developed": None,
            "excluded_evt": None,
        }
        self.run([], expected)

    def test_switches(self):
        args = [
            "--no-constrain-dnbr",
            "--no-estimate-severity",
            "--no-contain-severity",
            "--no-constrain-kf",
        ]
        expected = {
            "project": None,
            "buffer_km": None,
            "constrain_dnbr": False,
            "estimate_severity": False,
            "contain_severity": False,
            "constrain_kf": False,
        }
        self.run(args, expected)

    @pytest.mark.parametrize(
        "input, expected",
        (
            ("True", True),
            ("true", True),
            ("False", False),
            ("false", False),
            ("2", 2.0),
            ("2.23", 2.23),
            ("a/file/path", "a/file/path"),
        ),
    )
    def test_kf_fill(self, input, expected):
        self.run(["--kf-fill", input], {"kf_fill": expected})

    def test_disable_evt_codes(self):
        self.run(
            ["--no-find-water", "--no-find-developed", "--no-find-excluded"],
            {"water": [], "developed": [], "excluded_evt": []},
        )


class TestAssess:
    def run(_, args, expected):
        run("assess", args, expected)

    def test_default(self):
        expected = {
            "project": None,
            "min_area_km2": None,
            "confinement_neighborhood": None,
            "flow_continuous": True,
            "locate_basins": True,
            "parallelize_basins": False,
            "max_exterior_ratio": None,
        }
        self.run([], expected)

    def test_misc(self):
        self.run(
            ["--neighborhood", "5", "--not-continuous", "--no-basins"],
            {
                "confinement_neighborhood": 5,
                "flow_continuous": False,
                "locate_basins": False,
            },
        )

    def test_parallel(self):
        self.run(["--parallel"], {"locate_basins": True, "parallelize_basins": True})

    def test_filter_in_perimeter(self):
        self.run(
            ["--filter-in-perimeter", "--max-exterior-ratio", "0.95"],
            {"max_exterior_ratio": 0},
        )


class TestExport:
    def run(_, args, expected):
        run("export", args, expected)

    def test_default(self):
        expected = {
            "project": None,
            "format": None,
            "order_properties": True,
            "clean_names": True,
            "rename": None,
        }
        self.run([], expected)

    def test_switches(self):
        self.run(
            ["--no-order-properties", "--no-clean-names"],
            {"order_properties": False, "clean_names": False},
        )

    def test_crs(self):
        expected = {"export_crs": "4326"}
        self.run(["--crs", "4326"], expected)

        expected = {"export_crs": None}
        self.run(["--crs", "None"], expected)

    def test_single_rename(self):
        self.run(
            ["--rename", "H", "hazard"],
            {"rename": {"H": "hazard"}},
        )

    def test_multiple_rename(self):
        self.run(
            [
                "--rename",
                "H",
                "hazard",
                "--rename",
                "Segment_ID",
                "id",
                "--rename",
                "V",
                "volume",
            ],
            {"rename": {"H": "hazard", "Segment_ID": "id", "V": "volume"}},
        )

    def test_single_parameter(self):
        self.run(
            ["--rename-parameter", "I15_mm_hr", "20mmh", "24mmh", "40mmh"],
            {"rename": {"I15_mm_hr": ["20mmh", "24mmh", "40mmh"]}},
        )

    def test_multiple_parameters(self):
        args = [
            "--rename-parameter",
            "I15_mm_hr",
            "20mmh",
            "24mmh",
            "40mmh",
            "--rename-parameter",
            "volume_CI",
            "90%",
            "95%",
        ]
        rename = {
            "I15_mm_hr": ["20mmh", "24mmh", "40mmh"],
            "volume_CI": ["90%", "95%"],
        }
        self.run(args, {"rename": rename})

    def test_rename_and_parameter(self):
        args = [
            "--rename",
            "H",
            "hazard",
            "--rename",
            "Segment_ID",
            "id",
            "--rename-parameter",
            "I15_mm_hr",
            "20mmh",
            "24mmh",
            "40mmh",
            "--rename-parameter",
            "volume_CI",
            "90%",
            "95%",
        ]
        rename = {
            "H": "hazard",
            "Segment_ID": "id",
            "I15_mm_hr": ["20mmh", "24mmh", "40mmh"],
            "volume_CI": ["90%", "95%"],
        }
        self.run(args, {"rename": rename})
