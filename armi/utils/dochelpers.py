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
Helpers for sphinx documentation.

Can be used by armi docs or docs of anything else that
can import armi.
"""
import datetime
import inspect
import os
import shutil
import subprocess
import sys

from docutils import nodes, statemachine
from docutils.parsers.rst import Directive, directives

APIDOC_DIR = ".apidocs"


def create_figure(path, caption=None, align=None, alt=None, width=None):
    """
    This method is available within ``.. exec::``. It allows someone to create a figure with a
    caption.
    """
    rst = [".. figure:: {}".format(path)]
    if align:
        rst += ["    :align: {}".format(align)]
    if alt:
        rst += ["    :alt: {}".format(alt)]
    if width:
        rst += ["    :width: {}".format(width)]
    if caption:
        rst += [""]
    if caption:
        rst += ["    {}".format(caption)]
    return rst


def create_table(rst_table, caption=None, align=None, widths=None, width=None):
    """
    This method is available within ``.. exec::``. It allows someone to create a table with a
    caption.

    The ``rst_table``
    """
    rst = [".. table:: {}".format(caption or "")]
    if align:
        rst += ["    :align: {}".format(align)]
    if width:
        rst += ["    :width: {}".format(width)]
    if widths:
        rst += ["    :widths: {}".format(widths)]
    rst += [""]
    rst += ["    " + line for line in rst_table.split("\n")]
    return "\n".join(rst)


def createListTable(rows, caption=None, align=None, widths=None, width=None):
    """Take a list of data, and produce an RST-type string for a list-table.

    Parameters
    ----------
    rows: list
        List of input data (first row is the header).
    align: str
        “left”, “center”, or “right”
    widths: str
        “auto”, “grid”, or a list of integers
    width: str
        `length`_ or `percentage`_ of the current line width

    Returns
    -------
        str: RST list-table string
    """
    # we need valid input data
    assert len(rows) > 1, "Not enough input data."
    len0 = len(rows[0])
    for row in rows[1:]:
        assert len(row) == len0, "Rows aren't all the same length."

    # build the list-table header block
    rst = [".. list-table:: {}".format(caption or "")]
    rst += ["    :header-rows: 1"]
    if align:
        rst += ["    :align: {}".format(align)]
    if width:
        rst += ["    :width: {}".format(width)]
    if widths:
        rst += ["    :widths: " + " ".join([str(w) for w in widths])]
    rst += [""]

    # build the list-table data
    for row in rows:
        rst += [f"    * - {row[0]}"]
        rst += [f"      - {word}" for word in row[1:]]

    return "\n".join(rst)


class ExecDirective(Directive):
    """
    Execute the specified python code and insert the output into the document.

    The code is used as the body of a method, and must return a ``str``. The string result is
    interpreted as reStructuredText.

    Error handling informed by https://docutils.sourceforge.io/docs/howto/rst-directives.html#error-handling
    The self.error function should both inform the documentation builder of the error and also
    insert an error into the built documentation.

    .. warning:: This only works on a single node in the doctree, so the rendered code
        may not contain any new section names or labels. They will result in
        ``WARNING: Unexpected section title`` warnings.
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
            # tab_width = self.options.get('tab-width', self.state.document.settings.tab_width)
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
                os.remove(os.path.join(APIDOC_DIR, fig_name))
            except OSError:
                pass

            shutil.move(fig_name, APIDOC_DIR)
            # add .gitignore helper prefix
            shutil.move(
                os.path.join(APIDOC_DIR, fig_name),
                os.path.join(APIDOC_DIR, f"pyr_{fig_name}"),
            )
            new_content = [f".. figure:: /{APIDOC_DIR}/pyr_{fig_name}"]

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
            # add the error message directly to the built documentation and also tell the
            # builder
            raise self.error(
                "Unable to execute embedded doc code at {}:{} ... {}\n{}".format(
                    docname, self.lineno, datetime.datetime.now(), str(e)
                )
            )


def generateParamTable(klass, fwParams, app=None):
    """
    Return a string containing one or more restructured text list tables containing
    parameter descriptions for the passed ArmiObject class.

    Parameters
    ----------
    klass : ArmiObject subclass
        The Class for which parameter tables should be generated

    fwParams : ParameterDefinitionCollection
        A parameter definition collection containing the parameters that are always
        defined for the passed ``klass``. The rest of the parameters come from the
        plugins registered with the passed ``app``

    app : App, optional
        The ARMI-based application to draw plugins from.

    Notes
    -----
    It would be nice to have better section labels between the different sources
    but this cannot be done withing an ``exec`` directive in Sphinx so we settle
    for just putting in anchors for hyperlinking to.
    """
    from armi import apps

    if app is None:
        app = apps.App()

    defs = {None: fwParams}

    app = apps.App()
    for plugin in app.pluginManager.get_plugins():
        plugParams = plugin.defineParameters()
        if plugParams is not None:
            pDefs = plugParams.get(klass, None)
            if pDefs is not None:
                defs[plugin] = pDefs

    headerContent = """
    .. list-table:: {} Parameters from {{}}
       :header-rows: 1
       :widths: 30 40 30

       * - Name
         - Description
         - Units
    """.format(
        klass.__name__
    )

    content = []

    for plugin, pdefs in defs.items():
        srcName = plugin.__name__ if plugin is not None else "Framework"
        content.append(f".. _{srcName}-{klass.__name__}-param-table:")
        pluginContent = headerContent.format(srcName)
        for pd in pdefs:
            pluginContent += f"""   * - {pd.name}
         - {pd.description}
         - {pd.units}
    """
        content.append(pluginContent + "\n")

    return "\n".join(content)


def generatePluginSettingsTable(settings, pluginName):
    """
    Return a string containing one or more restructured text list tables containing
    settings descriptions for a plugin.

    Parameters
    ----------
    settings : list of Settings
        This is a list of settings definitions, typically returned by a
        ``defineSettings`` plugin hook.
    """
    headerContent = """
    .. list-table:: Settings defined in the {}
       :header-rows: 1
       :widths: 20 10 50 20

       * - Name
         - Label
         - Description
         - Default Value
    """.format(
        pluginName
    )

    content = [f".. _{pluginName}-settings-table:"]
    pluginContent = headerContent
    for setting in settings:
        default = None if setting.default == "" else setting.default
        pluginContent += f"""   * - ``{setting.name}``
         - {setting.label}
         - {setting.description}
         - {default}
    """
    content.append(pluginContent + "\n")
    return "\n".join(content)
