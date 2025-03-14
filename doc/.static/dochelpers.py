# Copyright 2024 TerraPower, LLC
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
"""Helpers for Sphinx documentation."""


def escapeSpecialCharacters(s):
    """Escapes RST special characters in inputted string.

    Special characters include: ``*|_``. More to be added when found troublesome.

    Parameters
    ----------
    s : str
        String with characters to be escaped.

    Returns
    -------
    str
        Input string with special characters escaped.
    """
    news = s[:]
    for char in ["*", "|", "_"]:
        news = news.replace(char, "\\" + char)
    return news


def createTable(
    rst_table, caption=None, label=None, align=None, widths=None, width=None
):
    """
    This method is available within ``.. exec::``. It allows someone to create a table with a
    caption.

    The ``rst_table``
    """
    rst = [".. table:: {}".format(caption or "")]
    if label:
        rst += ["    :name: {}".format(label)]
    if align:
        rst += ["    :align: {}".format(align)]
    if width:
        rst += ["    :width: {}".format(width)]
    if widths:
        rst += ["    :widths: {}".format(widths)]
    rst += [""]
    rst += ["    " + line for line in rst_table.split("\n")]
    return "\n".join(rst)


def createListTable(
    rows, caption=None, align=None, widths=None, width=None, klass=None
):
    """Take a list of data, and produce an RST-type string for a list-table.

    Parameters
    ----------
    rows: list
        List of input data (first row is the header).
    align: str
        "left", "center", or "right"
    widths: str
        "auto", "grid", or a list of integers
    width: str
        length or percentage of the line, surrounded by backticks
    klass: str
        Should be "class", but that is a reserved keyword.
        "longtable", "special", or something custom

    Returns
    -------
    str
        RST list-table string
    """
    # we need valid input data
    assert len(rows) > 1, "Not enough input data."
    len0 = len(rows[0])
    for row in rows[1:]:
        assert len(row) == len0, "Rows aren't all the same length."

    # build the list-table header block
    rst = [".. list-table:: {}".format(caption or "")]
    rst += ["    :header-rows: 1"]
    if klass:
        rst += ["    :class: {}".format(klass)]
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


def generateParamTable(klass, fwParams, app=None):
    """
    Return a string containing one or more restructured text list tables containing parameter
    descriptions for the passed ArmiObject class.

    Parameters
    ----------
    klass : ArmiObject subclass
        The Class for which parameter tables should be generated
    fwParams : ParameterDefinitionCollection
        A parameter definition collection containing the parameters that are always defined for the
        passed ``klass``. The rest of the parameters come from the plugins registered with the
        passed ``app``
    app : App, optional
        The ARMI-based application to draw plugins from.

    Returns
    -------
    str
        RST-formatted string table
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
.. container:: break_before ssp-landscape

    .. list-table:: {} Parameters from {{}}
        :class: ssp-tiny
        :widths: 30 40 30
        :header-rows: 1

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
            pluginContent += f"""    * - {pd.name}
          - {escapeSpecialCharacters(str(pd.description))}
          - {escapeSpecialCharacters(pd.units)}
    """
        content.append(pluginContent + "\n")

    return "\n".join(content)
