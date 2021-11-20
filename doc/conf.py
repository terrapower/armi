# Copyright 2019 TerraPower, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: skip-file
# -*- coding: utf-8 -*-
#
# ARMI documentation build configuration file, created by
# sphinx-quickstart on Wed Apr 02 11:36:09 2014.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import logging
import pathlib
import re
import warnings
import sys
import os

import sphinx_rtd_theme

# handle python import locations for this execution
PYTHONPATH = os.path.abspath("..")
sys.path.insert(0, PYTHONPATH)
# Also add to os.environ which will be used by the nbsphinx extension environment
os.environ["PYTHONPATH"] = PYTHONPATH
import armi
from armi.context import RES
from armi import apps
from armi.bookkeeping import tests as bookkeepingTests
from armi.utils.dochelpers import *

# Configure the baseline framework "App" for framework doc building
armi.configure(apps.App())

# some examples have import armi;armi.configure() in them that are intended
# to be copy/pasted by new users. However, armi will crash with param locks if it is
# configured twice. We often use if armi.isConfigured() to guard against
# issues here, but prefer not to highlight that somewhat confusing
# conditional if a user is just copy pasting fresh code
# ("How on Earth," they might wonder "would it already be configured!?"). Thus,
# we tell armi to simply disable future configure calls with this advanced flag
armi._ignoreConfigures = True


APIDOC_REL = ".apidocs"
SOURCE_DIR = os.path.join("..", "armi")
APIDOC_DIR = APIDOC_REL
_TUTORIAL_FILES = [
    pathlib.Path(SOURCE_DIR) / "tests" / "tutorials" / fName
    for fName in bookkeepingTests.TUTORIAL_FILES
    if "ipynb" not in fName
]


def setup(app):
    """Method to make `python setup.py build_sphinx` generate api documentation"""
    app.add_directive("exec", ExecDirective)
    app.add_directive("pyreverse", PyReverse)

    # copy resources needed to build the tutorial notebooks. nbsphinx_link is slick, but
    # the working directory for running the notebooks is the directory of the link
    # itself, so relative paths don't work.
    for path in _TUTORIAL_FILES:
        shutil.copy(path, pathlib.Path("user") / "tutorials")


# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, os.path.abspath(".."))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.todo",
    "sphinx.ext.mathjax",
    "sphinx.ext.ifconfig",
    "sphinx.ext.inheritance_diagram",
    "sphinx.ext.extlinks",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinxcontrib.apidoc",
    "nbsphinx",
    "nbsphinx_link",
    "sphinxext.opengraph",
    "sphinx_gallery.gen_gallery",
]

# Our API should make sense without documenting private/special members.
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "private-members": False,
    "special-members": False,
}
autodoc_member_order = "bysource"
autoclass_content = "both"

apidoc_module_dir = SOURCE_DIR
apidoc_output_dir = APIDOC_REL
apidoc_excluded_paths = ["tests", "*/test*"]
apidoc_separate_modules = True
apidoc_module_first = True

# Napoleon settings listed here so we know what's configurable and can track changes (for numpy docstrings)
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True

nbsphinx_kernel_name = "python3"

ogp_site_url = "https://terrapower.github.io/armi/"
ogp_image = "https://terrapower.github.io/armi/_static/armiSchematicView.png"
ogp_site_name = "Advanced Reactor Modeling Interface"

# Add any paths that contain templates here, relative to this directory.
templates_path = [".templates"]

# The suffix of source filenames.
source_suffix = ".rst"

# The encoding of source files.
# source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = "index"

# General information about the project.
project = "ARMI"
copyright = "2009-{}, TerraPower, LLC".format(datetime.datetime.now().year)

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = armi.__version__  #'.'.join(armi.__version__.split('.')[:2])
# The full version, including alpha/beta/rc tags.
release = armi.__version__

# from here on out, we use the std library default logging
logging.setLoggerClass(logging.Logger)

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
# language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
# today = ''
# Else, today_fmt is used as the format for a strftime call.
# today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
"""
'library/xml.rst' – ignores the library/xml.rst file (replaces entry in unused_docs)
'library/xml' – ignores the library/xml directory (replaces entry in exclude_trees)
'library/xml*' – ignores all files and directories starting with library/xml
'**/.svn' – ignores all .svn directories (replaces entry in exclude_dirnames)
"""
exclude_patterns = [
    "**/Python27*",
    "**/ccl*",
    "**.ipynb_checkpoints",
    "_build",
]  # , '**/tests*']

# The reST default role (used for this markup: `text`) to use for all documents.
# default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
# add_function_parentheses = True

rst_epilog = r"""
.. |keff| replace:: k\ :sub:`eff`\
"""

wiki = {
    "GitHub Discussions": (
        "https://github.com/terrapower/armi/discussions" + "%s",
        None,
    )
}

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
# add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
# show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# A list of ignored prefixes for module index sorting.
modindex_common_prefix = ["armi."]


# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = "sphinx_rtd_theme"

# (Optional) Logo. Should be small enough to fit the navbar (ideally 24x24).
# Path should be relative to the ``_static`` files directory.
html_logo = os.path.join(".static", "armiicon_24x24.ico")

# Theme options are theme-specific and customize the look and feel of a theme further.
html_theme_options = {
    "style_external_links": True,
    "style_nav_header_background": "#233C5B",  # TP blue looks better than green
}


# Add any paths that contain custom themes here, relative to this directory.
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
# html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
# html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
# html_logo = None

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
html_favicon = os.path.join(".static", "armiicon_16x16.ico")

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = [".static"]

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = "%Y-%m-%d"

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
# html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
# html_sidebars = {'**': ['localtoc.html']} # enable this is you want a sidebar nav, it doesn't work super super well though, more options for functionality include - 'sourcelink.html', 'searchbox.html'

# Additional templates that should be rendered to pages, maps page names to
# template names.
# html_additional_pages = {}

# If false, no module index is generated.
# html_domain_indices = True

# If false, no index is generated.
# html_use_index = True

# If true, the index is split into individual pages for each letter.
# html_split_index = False

# If true, links to the reST sources are added to the pages.
# html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
# html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
# html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
# html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
# html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = "ARMIdoc"

# Need to manually add gallery css files or else the theme_fixes override them.
html_context = {
    "css_files": [
        "_static/theme_fixes.css",  # overrides for wide tables in RTD theme
        "_static/gallery.css",  # for the sphinx-gallery plugin
        "_static/gallery-binder.css",
        "_static/gallery-dataframe.css",
    ],
    "display_github": True,  # Integrate GitHub
    "github_user": "terrapower",  # Username
    "github_repo": "armi",  # Repo name
    "github_version": "master",  # Version
    "conf_py_path": "/doc/",  # Path in the checkout to the docs root
}

# -- Options for LaTeX output --------------------------------------------------
latex_engine = "xelatex"

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    #'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    "preamble": r"\usepackage{amsmath} \usepackage{wasysym}"
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual], toctree_only).
latex_documents = [
    (
        "index",
        "ARMI.tex",
        "Advanced Reactor Modeling Interface (ARMI) Manual",
        "TerraPower, LLC",
        "manual",
        False,
    )
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
latex_logo = os.path.join(".static", "armi-logo.png")

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
latex_toplevel_sectioning = "part"

# If true, show page references after internal links.
latex_show_pagerefs = True

# If true, show URL addresses after external links.
latex_show_urls = "inline"

# Documents to append as an appendix to all manuals.
latex_appendices = []

# If false, no module index is generated.
latex_domain_indices = ["py-modindex"]

# Configuration for the sphinx-gallery
from sphinx_gallery.sorting import ExplicitOrder, FileNameSortKey

sphinx_gallery_conf = {
    "examples_dirs": ["gallery-src"],
    "filename_pattern": re.escape(os.sep) + "run_",
    "gallery_dirs": ["gallery"],
    "line_numbers": False,
    "download_all_examples": False,
    "subsection_order": ExplicitOrder(
        [
            os.path.join("gallery-src", "framework"),
            os.path.join("gallery-src", "analysis"),
            os.path.join("gallery-src", "applications"),
        ]
    ),
    "within_subsection_order": FileNameSortKey,
    "default_thumb_file": os.path.join(RES, "images", "TerraPowerLogo.png"),
}

suppress_warnings: ["autoapi.python_import_resolution"]

# filter out this warning which shows up in sphinx-gallery builds.
# this is suggested in the sphinx-gallery example but doesn't actually work?
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Matplotlib is currently using agg, which is a non-GUI"
    " backend, so cannot show the figure.",
)

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}
