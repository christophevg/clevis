"""Sphinx configuration for clevis documentation."""
import os
import sys

# Add the source directory to the path
sys.path.insert(0, os.path.abspath("../src"))

# Project information
project = "clevis"
copyright = "2026, Christophe Van Ginneken"
author = "Christophe Van Ginneken"

# Extensions
extensions = [
  "sphinx.ext.autodoc",
  "sphinx.ext.napoleon",
  "sphinx.ext.viewcode",
  "myst_parser",
]

# Theme
html_theme = "sphinx_rtd_theme"

# Source file extensions
source_suffix = {
  ".rst": "restructuredtext",
  ".md": "markdown",
}

# Autodoc settings
autodoc_typehints = "description"
autodoc_member_order = "bysource"

# Napoleon settings for Google/NumPy style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = False