from wildcat._utils._paths import assess


def test_preprocessed():
    output = assess._preprocessed(["some", "test", "text"])
    assert output == ["some_p", "test_p", "text_p"]


def test_all():
    assert assess.all() == [
        "perimeter_p",
        "dem_p",
        "dnbr_p",
        "severity_p",
        "kf_p",
        "retainments_p",
        "excluded_p",
        "included_p",
        "iswater_p",
        "isdeveloped_p",
    ]


def test_required():
    assert assess.required() == [
        "perimeter_p",
        "dem_p",
        "dnbr_p",
        "severity_p",
        "kf_p",
    ]


def test_masks():
    assert assess.masks() == [
        "perimeter_p",
        "excluded_p",
        "included_p",
        "iswater_p",
        "isdeveloped_p",
    ]
