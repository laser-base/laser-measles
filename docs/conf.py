#
# Configuration file for the Sphinx documentation builder.

import os

import sciris as sc

on_rtd = os.environ.get("READTHEDOCS") == "True"


# -- Project information -----------------------------------------------------

project = "laser-measles"
copyright = f"2024 - {sc.now().year}, Bill & Melinda Gates Foundation. All rights reserved."

# The short X.Y version
version = release = "0.9.4"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here
extensions = [
    "sphinx.ext.autodoc",  # Core Sphinx library for auto html doc generation from docstrings
    "sphinx.ext.autosummary",  # Create neat summary tables for modules/classes/methods etc -- causes warnings with Napoleon however
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",  # Add a link to the Python source code for classes, functions etc.
    "sphinx.ext.napoleon",
    "sphinx.ext.autosectionlabel",
    # "sphinx.ext.doctest",  # Enable doctest builder
    "sphinx_autodoc_typehints",  # Automatically document param types (less noise in class signature)
    "sphinx_design",  # Add e.g. grid layout
    "sphinx_search.extension",  # search across multiple docsets in domain
    "nbsphinx",
    "sphinxcontrib.autodoc_pydantic",
]

# Use Google docstrings
napoleon_google_docstring = True

# Configure autosummary
autosummary_generate = True  # Turn on sphinx.ext.autosummary
autosummary_ignore_module_all = False  # Respect __all__
autodoc_member_order = "bysource"  # Keep original ordering
add_module_names = False  # NB, does not work
autodoc_inherit_docstrings = True  # Allow subclasses to inherit docs from parent classes
autoclass_content = "both"  # Render both class docstring AND __init__ docstring in API pages

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# Syntax highlighting style
pygments_style = "sphinx"
modindex_common_prefix = ["laser.measles."]

# List of patterns, relative to source directory, to exclude
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "**.ipynb_checkpoints",
    "tutorials/not_ready/**",
    "tutorials/convert_tutorials.ipynb",
]

# Suppress certain warnings
suppress_warnings = ["autosectionlabel.*"]

# Configure pydantic


# -- Options for HTML output -------------------------------------------------

html_theme = "pydata_sphinx_theme"
html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 3,
    "show_prev_next": True,
    "icon_links": [
        {"name": "Web", "url": "https://laser-measles.readthedocs.io/en/latest/", "icon": "fas fa-home"},
        {
            "name": "GitHub",
            "url": "https://github.com/InstituteforDiseaseModeling/laser-measles",
            "icon": "fab fa-github-square",
        },
    ],
    "navbar_end": ["theme-switcher", "navbar-icon-links"],
    "secondary_sidebar_items": [],
    "header_links_before_dropdown": 5,
    "footer_start": ["copyright", "footer_start"],
    "footer_end": ["theme-version", "footer_end"],
}
html_sidebars = {
    "**": ["page-toc"],
}
html_logo = "images/idm-logo-transparent.png"
html_favicon = "images/favicon.ico"
html_static_path = ["_static"]
html_baseurl = "https://docs.idmod.org/"
html_context = {
    "rtd_url": "https://docs.idmod.org/",
    "versions_dropdown": {
        "latest": "devel (latest)",
        "stable": "current (stable)",
    },
    "default_mode": "light",
}
# Add any extra paths that contain custom files
if not on_rtd:
    html_extra_path = ["robots.txt"]


# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_last_updated_fmt = "%Y-%b-%d"
html_show_sourcelink = True
html_show_sphinx = False
html_copy_source = False
htmlhelp_basename = "laser-measles"


# Add customizations
def setup(app):
    app.add_css_file("theme_overrides.css")


# Modify this to not rerun the Jupyter notebook cells -- usually set by build_docs
nbsphinx_execute = "auto"
nbsphinx_timeout = 600
nbsphinx_allow_errors = True
nbsphinx_execute_arguments = [
    "--InlineBackend.figure_formats={'png'}",
    "--InlineBackend.rc={'figure.dpi': 96}",
]

# OpenSearch options
html_use_opensearch = "docs.idmod.org/projects/laser-measles/en/latest"

# -- RTD Sphinx search for searching across the entire domain, default child -------------
if os.environ.get("READTHEDOCS") == "True":
    search_project_parent = "institute-for-disease-modeling-idm"
    search_project = os.environ["READTHEDOCS_PROJECT"]
    search_version = os.environ["READTHEDOCS_VERSION"]

    rtd_sphinx_search_default_filter = f"subprojects:{search_project_parent}/{search_version}"

    rtd_sphinx_search_filters = {
        "Search this project": f"project:{search_project}/{search_version}",
        "Search all IDM docs": f"subprojects:{search_project_parent}/{search_version}",
    }

# -- Linkcheck configuration -------------------------------------------------
# Configuration for sphinx-build -b linkcheck

# URLs that should be ignored during link checking
linkcheck_ignore = [
    r"https://chatgpt\.com/g/g-674f5fd33aec8191bcdc1a2736fb7c8d-laser-gpt-jenner",  # Requires authentication
    r"https://.*\.idmod\.org/.*",  # Internal IDM links that may require auth
    r"https://.*\.gatesfoundation\.org/.*",  # Gates Foundation internal links
    r"https://example.com/restricted-path",
    r"https://github.com/InstituteforDiseaseModeling/laser-mcp/blob/main/README.md",  # 404 error
    r"https://chatgpt.com/g/g-678ae681f5b48191b3e91619e649e598-jenner-measles",  # 404 error
    r"https://chatgpt.com/g/g-674f5fd33aec8191bcdc1a2736fb7c8d-laser-gpt-jenner",  # likely restricted
    r"https://laser.idmod.org/laser-generic/",  # likely restricted
    r"https://codecov\.io/.*",  # External service, may return 502
]

# HTTP status codes that should be considered as "working" (not broken)
# 403 = Forbidden (requires authentication)
# 401 = Unauthorized (requires authentication)
linkcheck_allowed_redirects = {
    r"https://.*\.idmod\.org/.*": r".*",
    r"https://.*\.gatesfoundation\.org/.*": r".*",
}

# Timeout for link checking (in seconds)
linkcheck_timeout = 30

# Number of workers for parallel link checking
linkcheck_workers = 5

# Whether to check anchors in links
linkcheck_anchors = False

# Whether to check anchors in relative links
linkcheck_anchors_ignore = [
    r"#.*",  # Ignore all anchor links
]

# Retry count for failed links
linkcheck_retries = 2
