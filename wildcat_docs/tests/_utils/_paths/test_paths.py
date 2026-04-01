from wildcat._utils import _paths


def test_folders():
    assert _paths.folders() == ["inputs", "preprocessed", "assessment", "exports"]
