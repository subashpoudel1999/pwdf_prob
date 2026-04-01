import pytest

from wildcat._utils import _parameters


@pytest.fixture
def config():
    return {
        "buffer_km": 2,
        "test": 5,
        "I15_mm_hr": [20, 24, 40],
        "volume_CI": [0.9, 0.95],
        "durations": [15, 30, 60],
        "probabilities": [0.5, 0.75],
    }


class TestNames:
    def test(_):
        assert _parameters.names() == [
            "I15_mm_hr",
            "volume_CI",
            "durations",
            "probabilities",
        ]


class TestValues:
    def test(_, config):
        output = _parameters.values(config)
        assert output == (
            [20, 24, 40],
            [0.9, 0.95],
            [15, 30, 60],
            [0.5, 0.75],
        )


class TestCount:
    def test(_, config):
        output = _parameters.count(config)
        assert output == (3, 2, 3, 2)
