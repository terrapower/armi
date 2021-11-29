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
Collection of code that needs to be executed before most ARMI components are safe to
import.
"""

import sys
import tabulate

# This needs to happen pretty darn early, as one of it's purposes is to provide a better
# python version warning than "invalid syntax". Maybe this is enough of a crutch that we
# should get rid of it...
if (
    sys.version_info.major < 3
    or sys.version_info.major == 3
    and sys.version_info.minor < 6
):
    raise RuntimeError(
        "ARMI highly recommends using Python 3.7. Are you sure you are using the correct "
        "interpreter?\nUsing: {}".format(sys.executable)
    )


from armi import context


def _addCustomTabulateTables():
    """Create a custom ARMI tables within tabulate."""
    tabulate._table_formats["armi"] = tabulate.TableFormat(
        lineabove=tabulate.Line("", "-", "  ", ""),
        linebelowheader=tabulate.Line("", "-", "  ", ""),
        linebetweenrows=None,
        linebelow=tabulate.Line("", "-", "  ", ""),
        headerrow=tabulate.DataRow("", "  ", ""),
        datarow=tabulate.DataRow("", "  ", ""),
        padding=0,
        with_header_hide=None,
    )
    tabulate.tabulate_formats = list(sorted(tabulate._table_formats.keys()))
    tabulate.multiline_formats["armi"] = "armi"


# runLog makes tables, so make sure this is setup before we initialize the runLog
_addCustomTabulateTables()


from armi import runLog

from armi.nucDirectory import nuclideBases

# Nuclide bases get built explicitly here to have better determinism
# about when they get instantiated. The burn chain is not applied
# at this point, but only after input is read. Nuclides need to be built super early
# because some import-time code needs them to function. Namely, Block parameter
# collection uses them to create number density params.
nuclideBases.factory()
