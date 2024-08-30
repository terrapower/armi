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

.. warning:: Nothing should go in this file, but rotation algorithms.
"""
import math

from armi import runLog
from armi.physics.fuelCycle.hexAssemblyFuelMgmtUtils import (
    getOptimalAssemblyOrientation,
)
from armi.physics.fuelCycle.settings import CONF_ASSEM_ROTATION_STATIONARY


def _rotationNumberToRadians(rot: int) -> float:
    return rot * math.pi / 3


def buReducingAssemblyRotation(fh):
    """
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
            _rotateByComparingLocations(aNow, aPrev)
            numRotated += 1

    if fh.cs[CONF_ASSEM_ROTATION_STATIONARY]:
        for a in hist.getDetailAssemblies():
            if a not in fh.moved:
                _rotateByComparingLocations(a, a)
                numRotated += 1

    runLog.info("Rotated {0} assemblies".format(numRotated))


def _rotateByComparingLocations(aNow, aPrev):
    """Rotate an assembly based on its previous location.

    Parameters
    ----------
    aNow : Assembly
        Assembly to be rotated
    aPrev : Assembly
        Assembly that previously occupied the location of this assembly.
        If ``aNow`` has not been moved, this should be ``aNow``

    """
    rot = getOptimalAssemblyOrientation(aNow, aPrev)
    radians = _rotationNumberToRadians(rot)
    aNow.rotate(radians)
    (ring, pos) = aNow.spatialLocator.getRingPos()
    runLog.important(
        "Rotating Assembly ({0},{1}) to Orientation {2}".format(ring, pos, rot)
    )


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
    rot = math.radians(60)
    for a in hist.getDetailAssemblies():
        if a in fh.moved or fh.cs[CONF_ASSEM_ROTATION_STATIONARY]:
            a.rotate(rot)
            numRotated += 1
            ring, pos = a.spatialLocator.getRingPos()
            runLog.extra(
                "Rotating Assembly ({0},{1}) to Orientation {2}".format(ring, pos, 1)
            )

    runLog.extra("Rotated {0} assemblies".format(numRotated))
