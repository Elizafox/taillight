"""Sphinx configuration for the taillight documentation."""

import sys
from importlib.metadata import version as package_version
from pathlib import Path

# Import the working tree rather than an installed copy when running autodoc.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

project = "taillight"
copyright = "2015-2026, Elizabeth Ashford"
author = "Elizabeth Ashford"
release = package_version("taillight")
version = ".".join(release.split(".")[:2])

extensions = ["sphinx.ext.autodoc"]
root_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Keep the generated API pages compact while ensuring every public member and
# its docstring is included. Individual pages add inheritance information and
# undocumented public members as well.
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "show-inheritance": True,
    "undoc-members": True,
}
autodoc_typehints = "description"
autodoc_typehints_format = "short"

html_theme = "alabaster"
html_title = f"taillight {release} documentation"
htmlhelp_basename = "taillightdoc"

latex_documents = [
    (root_doc, "taillight.tex", "taillight Documentation", author, "manual"),
]
