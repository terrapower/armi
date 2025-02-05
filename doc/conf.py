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

"""
ARMI documentation build configuration file, created by
sphinx-quickstart on Wed Apr 02 11:36:09 2014.

This file is execfile()d with the current directory set to its containing dir.

Note that not all possible configuration values are present in this
autogenerated file.

All configuration values have a default; values that are commented out
serve to show the default.
"""
# ruff: noqa: E402
import datetime
import inspect
import os
import pathlib
import re
import shutil
import subprocess
import sys
import warnings

import sphinx_rtd_theme
from docutils import nodes, statemachine
from docutils.parsers.rst import Directive, directives
from sphinx.domains.python import PythonDomain

# from sphinx_needs.api import add_dynamic_function  # TODO: JOHN

# handle python import locations for this execution
PYTHONPATH = os.path.abspath("..")
sys.path.insert(0, PYTHONPATH)
# Also add to os.environ which will be used by the nbsphinx extension environment
os.environ["PYTHONPATH"] = PYTHONPATH
# Add dochelpers.py from doc/.static/ directory
sys.path.insert(0, ".static")

from armi import apps, context, disableFutureConfigures, meta
from armi import configure as armi_configure
from armi.bookkeeping import tests as bookkeepingTests
from armi.utils import safeCopy

context.Mode.setMode(context.Mode.BATCH)

# Configure the baseline framework "App" for framework doc building
armi_configure(apps.App())
disableFutureConfigures()

APIDOC_REL = ".apidocs"
SOURCE_DIR = os.path.join("..", "armi")
STATIC_DIR = ".static"
_TUTORIAL_FILES = [
    fName for fName in bookkeepingTests.TUTORIAL_FILES if "ipynb" not in fName
]
TEST_RESULTS = []


def getTestResult(app, need, needs):
    """Dynamic function used by sphinx-needs to gather the result of a test tag."""
    if not need["signature"]:
        return "none"

    # Get all the tests that match the method signature
    results = [
        test_case["result"]
        for test_case in TEST_RESULTS
        if need["signature"] == test_case["method"]
    ]
    # Logic is as follows if there are multiple matches:
    #   - If one is a "failure", then return "failure"
    #   - If all are "skipped", then return "skipped"
    #   - Otherwise, return "passed"
    if results:
        if "failure" in results:
            return "failure"
        elif "passed" in results:
            return "passed"
        else:
            return "skipped"

    # Things get a little more complicated when the test tag has a class-level signature.
    # Basically we have to determine if all the methods in the class passed or if any of skipped/failed.
    # First, gather all the results related to the class signature from the tag and categorize by method
    results = {}
    for test_case in TEST_RESULTS:
        if need["signature"] == test_case["class"]:
            if test_case["method"] in results:
                results[test_case["method"]].append(test_case["result"])
            else:
                results[test_case["method"]] = [test_case["result"]]

    # If we haven't found the test by now, we never will
    if not results:
        return "none"

    # Apply logic from before for each method in the class
    for m, r in results.items():
        if "failure" in r:
            results[m] = "failure"
        elif "passed" in r:
            results[m] = "passed"
        else:
            results[m] = "skipped"

    # Now for the class logic
    #  - If any of the methods failed, return "failure"
    #  - If any of the methods skipped, return "skipped"
    #  - If all of the methods passed, return "passed"
    if "failure" in results.values():
        return "failure"
    elif "skipped" in results.values():
        return "skipped"
    else:
        return "passed"


class PatchedPythonDomain(PythonDomain):
    def resolve_xref(self, env, fromdocname, builder, typ, target, node, contnode):
        if "refspecific" in node:
            del node["refspecific"]
        return super(PatchedPythonDomain, self).resolve_xref(
            env, fromdocname, builder, typ, target, node, contnode
        )


class ExecDirective(Directive):
    """
    Execute the specified python code and insert the output into the document.

    The code is used as the body of a method, and must return a ``str``. The string result is
    interpreted as reStructuredText.

    Error handling informed by https://docutils.sourceforge.io/docs/howto/rst-directives.html#error-handling
    The self.error function should both inform the documentation builder of the error and also
    insert an error into the built documentation.

    Warning
    -------
    This only works on a single node in the doctree, so the rendered code may not contain any new
    section names or labels. They will result in ``WARNING: Unexpected section title`` warnings.
    """

    has_content = True

    def run(self):
        try:
            code = inspect.cleandoc(
                """
            def usermethod():
                {}
            """
            ).format("\n    ".join(self.content))
            exec(code)
            result = locals()["usermethod"]()

            if result is None:
                raise self.error(
                    "Return value needed! The body of your `.. exec::` is used as a "
                    "function call that must return a value."
                )

            para = nodes.container()
            lines = statemachine.StringList(result.split("\n"))
            self.state.nested_parse(lines, self.content_offset, para)
            return [para]
        except Exception as e:
            docname = self.state.document.settings.env.docname
            raise self.error(
                "Unable to execute embedded doc code at {}:{} ... {}\n{}".format(
                    docname, self.lineno, datetime.datetime.now(), str(e)
                )
            )


class PyReverse(Directive):
    """Runs pyreverse to generate UML for specified module name and options.

    The directive accepts the same arguments as pyreverse, except you should not specify
    ``--project`` or ``-o`` (output format). These are automatically specified.

    If you pass ``-c`` to this, the figure generated is forced to be the className.png
    like ``BurnMatrix.png``. For .gitignore purposes, this is a pain. Thus, we
    auto-prefix ALL images generated by this directive with ``pyrev_``.
    """

    has_content = True
    required_arguments = 1
    optional_arguments = 50
    option_spec = {
        "alt": directives.unchanged,
        "height": directives.length_or_percentage_or_unitless,
        "width": directives.length_or_percentage_or_unitless,
        "align": lambda arg: directives.choice(arg, ("left", "right", "center")),
        "filename": directives.unchanged,
    }

    def run(self):
        try:
            args = list(self.arguments)
            args.append("--project")
            args.append(f"{args[0]}")
            args.append("-opng")

            # NOTE: cannot use "pylint.pyreverse.main.Run" because it calls `sys.exit`.
            fig_name = self.options.get("filename", "classes_{}.png".format(args[0]))
            command = [sys.executable, "-m", "pylint.pyreverse.main"]
            print("Running {}".format(command + args))
            env = dict(os.environ)
            # apply any runtime path mods to the pythonpath env variable (e.g. sys.path
            # mods made during doc confs)
            env["PYTHONPATH"] = os.pathsep.join(sys.path)
            subprocess.check_call(command + args, env=env)

            try:
                os.remove(os.path.join(APIDOC_REL, fig_name))
            except OSError:
                pass

            shutil.move(fig_name, APIDOC_REL)
            # add .gitignore helper prefix
            shutil.move(
                os.path.join(APIDOC_REL, fig_name),
                os.path.join(APIDOC_REL, f"pyr_{fig_name}"),
            )
            new_content = [f".. figure:: /{APIDOC_REL}/pyr_{fig_name}"]

            # assume we don't need the packages_, and delete.
            try:
                os.remove("packages_{}.png".format(args[0]))
            except OSError:
                pass

            # pass the other args through (figure args like align)
            for opt, val in self.options.items():
                if opt in ("filename",):
                    continue
                new_content.append("    :{}: {}\n".format(opt, val))

            new_content.append("\n")

            for line in self.content:
                new_content.append("    " + line)

            para = nodes.container()
            # tab_width = self.options.get('tab-width', self.state.document.settings.tab_width)
            lines = statemachine.StringList(new_content)
            self.state.nested_parse(lines, self.content_offset, para)
            return [para]
        except Exception as e:
            docname = self.state.document.settings.env.docname
            # add the error message directly to the built documentation and also tell the builder
            raise self.error(
                "Unable to execute embedded doc code at {}:{} ... {}\n{}".format(
                    docname, self.lineno, datetime.datetime.now(), str(e)
                )
            )


def autodoc_skip_member_handler(app, what, name, obj, skip, options):
    """Manually exclude certain methods/functions from docs."""
    # exclude special methods from unittest
    excludes = ["setUp", "setUpClass", "tearDown", "tearDownClass"]

    try:
        # special logic to fix inherited docstrings from yamlize.Attribute
        s = str(obj).strip()
        if s.startswith("<Attribute") and "_yamlized_" in s:
            return True
    except Exception:
        pass

    return name.startswith("_") or name in excludes


def getTestAcceptanceCriteria(app, need, needs):
    # Return title if there is not just one requirement or the linked requirement doesn't exist
    if len(need.get("tests", [])) != 1 or need["tests"][0] not in needs:
        ac = need["title"].strip()

    req = needs[need["tests"][0]]
    # Return title if there is not just one test in the requirement
    if len(req.get("tests_back", [])) != 1:
        ac = need["title"].strip()
    else:
        ac = req["acceptance_criteria"].strip()

    # For some reason sphinx is adding another period at the end of this, so we'll just remove it
    return ac[:-1] if ac[-1] == "." else ac


def setup(app):
    """Method to make `make html` generate api documentation."""
    app.connect("autodoc-skip-member", autodoc_skip_member_handler)
    app.add_domain(PatchedPythonDomain, override=True)
    app.add_directive("exec", ExecDirective)
    app.add_directive("pyreverse", PyReverse)
    # add_dynamic_function(app, getTestAcceptanceCriteria, "get_test_acceptance_criteria")  # TODO: JOHN
    # add_dynamic_function(app, getTestResult, "get_test_result")
    # add_dynamic_function(app, getTestAcceptanceCriteria, "get_test_acceptance_criteria")

    # making tutorial data dir
    dataDir = pathlib.Path("user") / ".." / "anl-afci-177"
    if not os.path.exists(dataDir):
        os.mkdir(dataDir)

    # copy resources needed to build the tutorial notebooks. nbsphinx_link is slick, but the working
    # directory for running the notebooks is the directory of the link itself, so relative paths
    # don't work.
    for path in _TUTORIAL_FILES:
        safeCopy(path, dataDir)


# If extensions (or modules to document with autodoc) are in another directory, add these
# directories to sys.path here. If the directory is relative to the documentation root, use
# os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, os.path.abspath(".."))

# -- General configuration -----------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be extensions coming with Sphinx
# (named 'sphinx.ext.*') or your custom ones.
extensions = [
    "nbsphinx",
    "nbsphinx_link",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.extlinks",
    "sphinx.ext.ifconfig",
    "sphinx.ext.imgconverter",  # to convert GH Actions badge SVGs to PNG for LaTeX
    "sphinx.ext.inheritance_diagram",
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinx_gallery.gen_gallery",
    "sphinx_needs",  # needed for requirements tracking
    "sphinxcontrib.test_reports",
    "sphinx_rtd_theme",  # needed here for loading jquery in sphinx 6
    "sphinx_simplepdf",
    "sphinxcontrib.apidoc",
    "sphinxcontrib.jquery",  # see https://github.com/readthedocs/sphinx_rtd_theme/issues/1452
    "sphinxcontrib.plantuml",
    "sphinxext.opengraph",
]

# Our API should make sense without documenting private/special members.
autodoc_default_options = {
    "members": True,
    "private-members": False,
    "undoc-members": True,
    "ignore-module-all": True,
}
autodoc_member_order = "bysource"
# this line removes huge numbers of false and misleading, inherited docstrings
autodoc_inherit_docstrings = False
autoclass_content = "both"
autodoc_mock_imports = ["wx"]

apidoc_module_dir = SOURCE_DIR
apidoc_module_first = True
apidoc_output_dir = APIDOC_REL
apidoc_separate_modules = True

# Napoleon settings listed here so we know what's configurable and can track changes (for numpy docstrings)
napoleon_google_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False
napoleon_numpy_docstring = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = False
napoleon_use_ivar = True
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

# The top-level toctree document.
root_doc = "index"

# General information about the project.
project = "ARMI"
copyright = "2009-{}, TerraPower, LLC".format(datetime.datetime.now().year)

# Use the pre-existing version definition.
version = meta.__version__
release = meta.__version__

# List of patterns, relative to source directory, that match files and directories to ignore when
# looking for source files.
exclude_patterns = [
    "**.ipynb",
    "**.ipynb_checkpoints",
    "**/ccl*",
    "**/Python27*",
    "**_reqs.rst",  # needed so included reqs files render
    ".DS_Store",
    "_build",
    "logs",
    "Thumbs.db",
]

rst_epilog = r"""
.. |keff| replace:: k\ :sub:`eff`\
"""

wiki = {
    "GitHub Discussions": (
        "https://github.com/terrapower/armi/discussions" + "%s",
        None,
    )
}

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# A list of ignored prefixes for module index sorting.
modindex_common_prefix = ["armi."]

# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages. See the documentation for a list of builtin themes.
html_theme = "sphinx_rtd_theme"

# (Optional) Logo. Should be small enough to fit the navbar (ideally 24x24).
# Path should be relative to the ``_static`` files directory.
html_logo = os.path.join(STATIC_DIR, "armiicon_24x24.ico")

# Theme options are theme-specific and customize the look and feel of a theme further.
html_theme_options = {
    "display_version": True,
    "logo_only": False,
    "prev_next_buttons_location": "bottom",
    "style_external_links": True,
    "style_nav_header_background": "#233C5B",  # TP blue looks better than green
    "vcs_pageview_mode": "",
    # Toc options
    "collapse_navigation": True,
    "includehidden": True,
    "navigation_depth": 4,
    "sticky_navigation": True,
    "titles_only": False,
}

# Add any paths that contain custom themes here, relative to this directory.
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

# as long as this file @import's the theme's main css it won't break anything
html_style = "css/theme_fixes.css"

# The name of an image file (within the static path) to use as favicon of the docs. This file should
# be a Windows icon file (.ico) being 16x16 or 32x32 pixels large.
html_favicon = os.path.join(STATIC_DIR, "armiicon_16x16.ico")

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = [STATIC_DIR]

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = "%Y-%m-%d"

# Output file base name for HTML help builder.
htmlhelp_basename = "ARMIdoc"

html_context = {
    "conf_py_path": "/doc/",  # Path in the checkout to the docs root
    "display_github": True,  # Integrate GitHub
    "github_repo": "armi",  # Repo name
    "github_user": "terrapower",  # Username
    "github_version": "main",  # Version
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
latex_logo = os.path.join(STATIC_DIR, "armi-logo.png")

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
    "default_thumb_file": os.path.join(STATIC_DIR, "TerraPowerLogo.png"),
}

suppress_warnings = ["autoapi.python_import_resolution"]

# filter out this warning which shows up in sphinx-gallery builds.
# this is suggested in the sphinx-gallery example but doesn't actually work?
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Matplotlib is currently using agg, which is a non-GUI"
    " backend, so cannot show the figure.",
)

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

# these are defaults in Windows in more recent versions of the imgconverter plugin and
# can be removed if/when we upgrade Sphinx beyond 2.2.
# Otherwise, 'convert' from system32 folder is used.
if "win32" in sys.platform:
    image_converter = "magick"
    image_converter_args = ["convert"]

# PDF-only settings
simplepdf_vars = {
    "links": "#FF3333",
    "primary": "#333333",
}

# sphinx-needs settings
needs_statuses = [
    dict(name=None, description="No status yet; not in any reviews"),
    dict(
        name="preliminary",
        description="Requirement that will have its wording reviewed and/or does not have implementation/testing yet.",
    ),
    dict(
        name="accepted",
        description="Requirement that either has completed or will undergo TP-ENG-PROC-0013 Appendix D Part 1 review.",
    ),
]

needs_extra_options = [
    "acceptance_criteria",
    "basis",
    "subtype",
]

needs_extra_links = [
    dict(option="tests", incoming="testing", outgoing="requirements"),
    dict(option="implements", incoming="implementations", outgoing="requirements"),
]

# TODO: JOHN Do I need or like these templates and layouts?
needs_template_folder = os.path.join(STATIC_DIR, "needs_templates")
needs_layouts = {
    "test_layout": {
        "grid": "simple",
        "layout": {
            "head": [
                '<<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>>  <<collapse_button("meta", '
                'collapsed="icon:arrow-down-circle", visible="icon:arrow-right-circle", initial=False)>> '
            ],
            "meta": [
                "signature: <<meta('signature')>>",
                "<<meta_links_all()>>",
            ],
        },
    },
    "req_hide_links": {
        "grid": "simple",
        "layout": {
            "head": [
                '<<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>>  <<collapse_button("meta", '
                'collapsed="icon:arrow-down-circle", visible="icon:arrow-right-circle", initial=False)>> '
            ],
            "meta": [
                "<<meta_all(no_links=True, exclude=['layout'])>>",
            ],
        },
    },
}

# TODO: JOHN
"""
needs_global_options = {
    # Defaults for test tags
    "acceptance_criteria": (
        ":ndf:`get_test_acceptance_criteria()`.",
        "type=='test'",
    ),
    "template": ("test", "type=='test'"),
    "layout": ("test_layout", "type=='test'"),
    "result": ("[[get_test_result()]]", "type=='test'"),
}
"""


# Formats need roles (reference to a req in text) as just the req ID
needs_role_need_template = "{id}"
