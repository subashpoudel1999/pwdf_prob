import pytest

import wildcat

"""
Note: These tests are just checking that the functions imported correctly. We do
this by testing that an invalid input fails a validation check, and also that the
expected command logger is activated. For detailed testing of the actual command
behavior, see the tests in the "_commands" folder.
"""


def test_version():
    assert isinstance(wildcat.version(), str)


def test_initialize(project):
    wildcat.initialize(project)
    config = project / "configuration.py"
    inputs = project / "inputs"
    assert config.exists()
    assert inputs.exists()


def test_preprocess(project, errcheck, logcheck):
    logcheck.start("wildcat.preprocess")
    with pytest.raises(ValueError) as error:
        wildcat.preprocess(project=project, buffer_km=-2)
    errcheck(error, 'The "buffer_km" setting must be positive')
    assert logcheck.caplog.record_tuples[0] == (
        "wildcat.preprocess",
        20,
        "----- Preprocessing -----",
    )


def test_assess(project, errcheck, logcheck):
    logcheck.start("wildcat.assess")
    with pytest.raises(ValueError) as error:
        wildcat.assess(project=project, confinement_neighborhood=-2)
    errcheck(error, 'The "confinement_neighborhood" setting must be positive')
    assert logcheck.caplog.record_tuples[0] == (
        "wildcat.assess",
        20,
        "----- Assessment -----",
    )


def test_export(project, errcheck, logcheck):
    logcheck.start("wildcat.export")
    with pytest.raises(TypeError) as error:
        wildcat.export(project=project, suffix=5)
    errcheck(error, 'The "suffix" setting must be a string, or None')
    assert logcheck.caplog.record_tuples[0] == (
        "wildcat.export",
        20,
        "----- Exporting Results -----",
    )
