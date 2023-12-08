# Copyright 2022 TerraPower, LLC
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
Algorithms used to rotate hex assemblies in a reactor core.

Notes
-----
These algorithms are defined in assemblyRotationAlgorithms.py, but they are used in:
``FuelHandler.outage()``.

.. warning:: Nothing should do in this file, but rotation algorithms.
"""
from armi import runLog
from armi.physics.fuelCycle.hexAssemblyFuelMgmtUtils import (
    getOptimalAssemblyOrientation,
)
from armi.physics.fuelCycle.settings import CONF_ASSEM_ROTATION_STATIONARY


def buReducingAssemblyRotation(fh):
    r"""
    Rotates all detail assemblies to put the highest bu pin in the lowest power orientation.

    Parameters
    ----------
    fh : FuelHandler object
        A fully initialized FuelHandler object.

    See Also
    --------
    simpleAssemblyRotation : an alternative rotation algorithm
    """
    runLog.info("Algorithmically rotating assemblies to minimize burnup")
    numRotated = 0
    hist = fh.o.getInterface("history")
    for aPrev in fh.moved:  # much more convenient to loop through aPrev first
        aNow = fh.r.core.getAssemblyWithStringLocation(aPrev.lastLocationLabel)
        # no point in rotation if there's no pin detail
        if aNow in hist.getDetailAssemblies():
            rot = getOptimalAssemblyOrientation(aNow, aPrev)
            aNow.rotatePins(rot)  # rot = integer between 0 and 5
            numRotated += 1
            # Print out rotation operation (mainly for testing)
            # hex indices (i,j) = (ring,pos)
            (i, j) = aNow.spatialLocator.getRingPos()
            runLog.important(
                "Rotating Assembly ({0},{1}) to Orientation {2}".format(i, j, rot)
            )

    # rotate NON-MOVING assemblies (stationary)
    if fh.cs[CONF_ASSEM_ROTATION_STATIONARY]:
        for a in hist.getDetailAssemblies():
            if a not in fh.moved:
                rot = getOptimalAssemblyOrientation(a, a)
                a.rotatePins(rot)  # rot = integer between 0 and 6
                numRotated += 1
                (i, j) = a.spatialLocator.getRingPos()
                runLog.important(
                    "Rotating Assembly ({0},{1}) to Orientation {2}".format(i, j, rot)
                )

    runLog.info("Rotated {0} assemblies".format(numRotated))


def simpleAssemblyRotation(fh):
    """
    Rotate all pin-detail assemblies that were just shuffled by 60 degrees.

    Parameters
    ----------
    fh : FuelHandler object
        A fully initialized FuelHandler object.

    Notes
    -----
    Also, optionally rotate stationary (non-shuffled) assemblies if the setting is set.
    Obviously, only pin-detail assemblies can be rotated, because homogenized assemblies are isotropic.

    Examples
    --------
    >>> simpleAssemblyRotation(fh)

    See Also
    --------
    FuelHandler.outage : calls this method based on a user setting
    """
    runLog.info("Rotating assemblies by 60 degrees")
    numRotated = 0
    hist = fh.o.getInterface("history")
    for a in hist.getDetailAssemblies():
        if a in fh.moved or fh.cs[CONF_ASSEM_ROTATION_STATIONARY]:
            a.rotatePins(1)
            numRotated += 1
            i, j = a.spatialLocator.getRingPos()  # hex indices (i,j) = (ring,pos)
            runLog.extra(
                "Rotating Assembly ({0},{1}) to Orientation {2}".format(i, j, 1)
            )

    runLog.extra("Rotated {0} assemblies".format(numRotated))
