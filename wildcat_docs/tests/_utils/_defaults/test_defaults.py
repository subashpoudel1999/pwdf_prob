from importlib import import_module

import pytest

from wildcat import assess, export, preprocess
from wildcat._utils import _args


def namespace(module):
    module = import_module(f"wildcat._utils._defaults.{module}")
    namespace = dir(module)
    return [parameter for parameter in namespace if not parameter.startswith("_")]


@pytest.mark.parametrize("command", (preprocess, assess, export))
def test_command_has_defaults(command):

    # First and second args are the project folder and config file
    parameters = _args.collect(command)
    assert parameters[0] == "project"
    assert parameters[1] == "config"
    parameters = parameters[2:]

    # Check the remaining args have defaults
    defaults = namespace(command.__name__)
    folders = namespace("folders")
    for parameter in parameters:
        assert parameter in defaults or parameter in folders


@pytest.mark.parametrize("command", (preprocess, assess, export))
def test_defaults_in_command(command):

    args = _args.collect(command)
    defaults = namespace(command.__name__)
    for parameter in defaults:
        assert parameter in args


def test_no_duplicates():

    # Collect all default namespaces
    modules = ["folders", "preprocess", "assess", "export"]
    defaults = {}
    for module in modules:
        defaults[module] = namespace(module)

    # Check each parameter against the other namespaces
    for module, parameters in defaults.items():
        for parameter in parameters:
            check_duplicates(module, parameter, defaults)


def check_duplicates(name, parameter, defaults):
    for name2, namespace in defaults.items():
        if name == name2:
            continue
        assert parameter not in namespace
