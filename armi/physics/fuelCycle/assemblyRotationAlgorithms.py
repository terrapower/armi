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
from collections import defaultdict

from armi import runLog
from armi.physics.fuelCycle.hexAssemblyFuelMgmtUtils import (
    getOptimalAssemblyOrientation,
)
from armi.physics.fuelCycle.settings import CONF_ASSEM_ROTATION_STATIONARY
from armi.physics.fuelCycle.utils import (
    assemblyHasFuelPinBurnup,
    assemblyHasFuelPinPowers,
)
from armi.reactor.assemblies import Assembly


def _rotationNumberToRadians(rot: int) -> float:
    """Convert a rotation number to radians, assuming a HexAssembly."""
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
    # Store how we should rotate each assembly but don't perform the rotation just yet
    # Consider assembly A is shuffled to a new location and rotated.
    # Now, assembly B is shuffled to where assembly A used to be. We need to consider the
    # power profile of A prior to it's rotation to understand the power profile B may see.
    rotations: dict[int, list[Assembly]] = defaultdict(list)
    for aPrev in fh.moved:
        # If the assembly was out of the core, it will not have pin powers.
        # No rotation information to be gained.
        if aPrev.lastLocationLabel in Assembly.NOT_IN_CORE:
            continue
        aNow = fh.r.core.getAssemblyWithStringLocation(aPrev.lastLocationLabel)
        # An assembly in the SFP could have burnup but if it's coming from the load
        # queue it's totally fresh. Skip a check over all pins in the model
        if aNow.lastLocationLabel == Assembly.LOAD_QUEUE:
            continue
        # no point in rotation if there's no pin detail
        if assemblyHasFuelPinPowers(aPrev) and assemblyHasFuelPinBurnup(aNow):
            rot = getOptimalAssemblyOrientation(aNow, aPrev)
            rotations[rot].append(aNow)

    if fh.cs[CONF_ASSEM_ROTATION_STATIONARY]:
        for a in filter(
            lambda asm: asm not in fh.moved and assemblyHasFuelPinPowers(asm) and assemblyHasFuelPinBurnup(asm),
            fh.r.core,
        ):
            rot = getOptimalAssemblyOrientation(a, a)
            rotations[rot].append(a)

    nRotations = 0
    for rot, assems in filter(lambda item: item[0], rotations.items()):
        # Radians used for the actual rotation. But a neater degrees print out is nice for logs
        radians = _rotationNumberToRadians(rot)
        degrees = round(math.degrees(radians), 3)
        for a in assems:
            runLog.important(f"Rotating assembly {a} {degrees} CCW.")
            a.rotate(radians)
            nRotations += 1

    runLog.info(f"Rotated {nRotations} assemblies.")


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
            runLog.extra("Rotating Assembly ({0},{1}) to Orientation {2}".format(ring, pos, 1))

    runLog.extra("Rotated {0} assemblies".format(numRotated))
