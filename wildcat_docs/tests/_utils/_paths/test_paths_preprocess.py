from wildcat._utils._paths import preprocess


def test_all():
    assert preprocess.all() == [
        "perimeter",
        "dem",
        "dnbr",
        "severity",
        "kf",
        "kf_fill",
        "evt",
        "retainments",
        "excluded",
        "included",
        "iswater",
        "isdeveloped",
    ]


def test_standard():
    assert preprocess.standard() == [
        "perimeter",
        "dem",
        "dnbr",
        "severity",
        "kf",
        "evt",
        "retainments",
        "excluded",
        "included",
        "iswater",
        "isdeveloped",
    ]


def test_required():
    assert preprocess.required() == ["perimeter", "dem"]


def test_raster_only():
    assert preprocess.raster_only() == ["dem", "dnbr", "evt"]


def test_features():
    assert preprocess.features() == [
        "perimeter",
        "severity",
        "kf",
        "kf_fill",
        "retainments",
        "excluded",
        "included",
        "iswater",
        "isdeveloped",
    ]


def test_constant():
    assert preprocess.constant() == ["dnbr", "severity", "kf"]


def test_points():
    assert preprocess.points() == ["retainments"]


def test_polygons():
    assert preprocess.polygons() == [
        "perimeter",
        "severity",
        "kf",
        "kf_fill",
        "excluded",
        "included",
        "iswater",
        "isdeveloped",
    ]


def test_field():
    assert preprocess.field() == ["severity", "kf", "kf_fill"]
