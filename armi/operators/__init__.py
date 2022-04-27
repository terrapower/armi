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
Operators build and hold the ARMI reactor model and perform operations on it.

Different operators may perform different calculation loops upon the reactor model.
Operators can be thought of as schedulers for the interactions between the various
ARMI physics packages and the reactor object(s).

Operators are generally created by a :py:mod:`armi.cases` object and are chosen by
the ``runType`` setting. Custom operators may be introduced via the :py:mod:`armi.plugins` system.

The ARMI framework comes with two general-purpose Operators, which can be used for
very real analysis given a proper set of plugins. The :py:class:`~armi.operators.operator.Operator` 
is the Standard operator, which loops over cycles and timenodes. The 
:py:class:`~armi.operators.snapshots.OperatorSnapshots`
is the Snapshots operator, which loops over specific point in time from a previous Standard run
and performs additional analysis (e.g. for detailed follow-on analysis/transients). 

See Also
--------
armi.cases : Builds operators

armi.reactor : The reactor model that the operator operates upon

armi.interfaces : Code that operators schedule to perform the real analysis or
    math on the reactor model
"""

from armi import context
from armi import getPluginManagerOrFail
from armi import runLog
from armi.operators.runTypes import RunTypes
from armi.operators.operator import Operator
from armi.operators.operatorMPI import OperatorMPI
from armi.operators.snapshots import OperatorSnapshots


def factory(cs):
    """Choose an operator subclass and instantiate it object based on settings."""
    return getOperatorClassFromSettings(cs)(cs)


def getOperatorClassFromSettings(cs):  # pylint: disable=too-many-return-statements
    """Choose a operator class based on user settings (possibly from plugin).

    Parameters
    ----------
    cs : Settings

    Returns
    -------
    Operator : Operator

    Raises
    ------
    ValueError
        If the Operator class cannot be determined from the settings.
    """
    runType = cs["runType"]

    if runType == RunTypes.STANDARD:
        if context.MPI_SIZE == 1:
            return Operator
        else:
            return OperatorMPI

    elif runType == RunTypes.SNAPSHOTS:
        return OperatorSnapshots

    plugInOperator = None
    for potentialOperator in getPluginManagerOrFail().hook.getOperatorClassFromRunType(
        runType=runType
    ):
        if plugInOperator:
            raise ValueError(
                "More than one Operator class was "
                f"recognized for runType `{runType}`: "
                f"{plugInOperator} and {potentialOperator}. "
                "This is not allowed. Please adjust plugin config."
            )
        plugInOperator = potentialOperator
    if plugInOperator:
        return plugInOperator

    raise ValueError(
        f"No valid operator was found for runType: `{runType}`. "
        "Please adjust settings or plugin configuration."
    )
