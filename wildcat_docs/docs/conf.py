# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import tomllib
from pathlib import Path


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "wildcat"
author = "Jonathan King"

# Note: Override theme copyright with public domain attribution
# copyright = "USGS 2024, Public Domain"
html_static_path = ["_static"]
html_css_files = ["copyright.css"]

# Parse the release string from pyproject.toml
_pyproject = Path(__file__).parents[1] / "pyproject.toml"
with open(_pyproject, "rb") as file:
    _pyproject = tomllib.load(file)
release = _pyproject["project"]["version"]

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["sphinx_design"]
highlight_language = "none"
pygments_style = "sphinx"
exclude_patterns = ["images"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_copy_source = False
html_theme = "furo"
html_favicon = "_static/usgs.ico"
html_title = f"wildcat {release}"
html_logo = "_static/usgs-logo-green.svg"
