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
This is a selection of fuel management utilities that seem generally useful enough to
keep in ARMI, but they still only apply to hex assembly reactors.

Notes
-----
We are keeping these in ARMI even if they appear unused internally.
"""
import math
import typing

import numpy as np

from armi import runLog
from armi.physics.fuelCycle.utils import maxBurnupBlock, maxBurnupLocator
from armi.utils.mathematics import findClosest

if typing.TYPE_CHECKING:
    from armi.reactor.assemblies import HexAssembly


def getOptimalAssemblyOrientation(a: "HexAssembly", aPrev: "HexAssembly") -> int:
    """
    Get optimal hex assembly orientation/rotation to minimize peak burnup.

    Works by placing the highest-burnup pin in the location (of 6 possible locations) with lowest
    expected pin power. We evaluated "expected pin power" based on the power distribution in
    ``aPrev``, the previous assembly located where ``a`` is going. The algorithm goes as follows.

    1. Get all the pin powers and ``IndexLocation`` s from the block at the previous location/timenode.
    2. Obtain the ``IndexLocation`` of the pin with the highest burnup in the current assembly.
    3. For each possible rotation,

        - Find the new location with ``HexGrid.rotateIndex``
        - Find the index where that location occurs in previous locations
        - Find the previous power at that location

    4. Return the rotation with the lowest previous power

    This algorithm assumes a few things.

    1. ``len(HexBlock.getPinCoordinates()) == len(HexBlock.p.linPowByPin)`` and,
       by extension, ``linPowByPin[i]`` is found at ``getPinCoordinates()[i]``.
    2. Your assembly has at least 60 degree symmetry of fuel pins and
       powers. This means if we find a fuel pin and rotate it 60 degrees, there should
       be another fuel pin at that lattice site. This is mostly a safe assumption
       since many hexagonal reactors have at least 60 degree symmetry of fuel pin layout.
       This assumption holds if you have a full hexagonal lattice of fuel pins as well.
    3. Fuel pins in ``a`` have similar locations in ``aPrev``. This is mostly a safe
       assumption in that most fuel assemblies have similar layouts so it's plausible
       that if ``a`` has a fuel pin at ``(1, 0, 0)``, so does ``aPrev``.

    .. impl:: Provide an algorithm for rotating hexagonal assemblies to equalize burnup
        :id: I_ARMI_ROTATE_HEX_BURNUP
        :implements: R_ARMI_ROTATE_HEX_BURNUP

    Parameters
    ----------
    a : Assembly object
        The assembly that is being rotated.
    aPrev : Assembly object
        The assembly that previously occupied this location (before the last shuffle).
        If the assembly "a" was not shuffled, it's sufficient to pass ``a``.

    Returns
    -------
    int
        An integer from 0 to 5 representing the number of pi/3 (60 degree) counterclockwise
        rotations from where ``a`` is currently oriented to the "optimal" orientation

    Raises
    ------
    ValueError
        If there is insufficient information to determine the rotation of ``a``. This could
        be due to a lack of fuel blocks or parameters like ``linPowByPin``.
    """
    maxBuBlock = maxBurnupBlock(a)
    if maxBuBlock.spatialGrid is None:
        msg = f"Block {maxBuBlock} in {a} does not have a spatial grid. Cannot rotate."
        runLog.error(msg)
        raise ValueError(msg)
    maxBuPinLocation = maxBurnupLocator(maxBuBlock)
    # No need to rotate if max burnup pin is the center
    if maxBuPinLocation.i == 0 and maxBuPinLocation.j == 0:
        return 0

    if aPrev is not a:
        blockAtPreviousLocation = aPrev[a.index(maxBuBlock)]
    else:
        blockAtPreviousLocation = maxBuBlock

    previousLocations = blockAtPreviousLocation.getPinLocations()
    previousPowers = blockAtPreviousLocation.p.linPowByPin
    if len(previousLocations) != len(previousPowers):
        msg = (
            f"Inconsistent pin powers and number of pins in {blockAtPreviousLocation}. "
            f"Found {len(previousLocations)} locations but {len(previousPowers)} powers."
        )
        runLog.error(msg)
        raise ValueError(msg)

    ringPowers = {
        (loc.i, loc.j): p for loc, p in zip(previousLocations, previousPowers)
    }

    targetGrid = blockAtPreviousLocation.spatialGrid
    candidateRotation = 0
    candidatePower = ringPowers.get((maxBuPinLocation.i, maxBuPinLocation.j), math.inf)
    for rot in range(1, 6):
        candidateLocation = targetGrid.rotateIndex(maxBuPinLocation, rot)
        newPower = ringPowers.get((candidateLocation.i, candidateLocation.j), math.inf)
        if newPower < candidatePower:
            candidateRotation = rot
            candidatePower = newPower
    return candidateRotation


def buildRingSchedule(
    maxRingInCore,
    chargeRing=None,
    dischargeRing=None,
    jumpRingFrom=None,
    jumpRingTo=None,
    coarseFactor=0.0,
):
    r"""
    Build a ring schedule for shuffling.

    Notes
    -----
    General enough to do convergent, divergent, or any combo, plus jumprings.

    The center of the core is ring 1, based on the DIF3D numbering scheme.

    Jump ring behavior can be generalized by first building a base ring list
    where assemblies get charged to H and discharge from A::

        [A,B,C,D,E,F,G,H]

    If a jump should be placed where it jumps from ring G to C, reversed back to F, and then discharges from A,
    we simply reverse the sublist [C,D,E,F], leaving us with::

        [A,B,F,E,D,C,G,H]

    A less-complex, more standard convergent-divergent scheme is a subcase of this, where the
    sublist [A,B,C,D,E] or so is reversed, leaving::

        [E,D,C,B,A,F,G,H]

    So the task of this function is simply to determine what subsection, if any, to reverse of
    the baselist.

    Parameters
    ----------
    maxRingInCore : int
        The number of rings in the hex assembly reactor.

    chargeRing : int, optional
        The peripheral ring into which an assembly enters the core. Default is outermost ring.

    dischargeRing : int, optional
        The last ring an assembly sits in before discharging. Default is jumpRing-1

    jumpRingFrom : int
        The last ring an assembly sits in before jumping to the center

    jumpRingTo : int, optional
        The inner ring into which a jumping assembly jumps. Default is 1.

    coarseFactor : float, optional
        A number between 0 and 1 where 0 hits all rings and 1 only hits the outer, rJ, center, and rD rings.
        This allows coarse shuffling, with large jumps. Default: 0

    Returns
    -------
    ringSchedule : list
        A list of rings in order from discharge to charge.

    ringWidths : list
        A list of integers corresponding to the ringSchedule determining the widths of each ring area

    Examples
    --------
    >>> f.buildRingSchedule(17,1,jumpRingFrom=14)
    ([13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 14, 15, 16, 17],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    """
    if dischargeRing > maxRingInCore:
        runLog.warning(
            f"Discharge ring {dischargeRing} is outside the core (max {maxRingInCore}). "
            "Changing it to be the max ring"
        )
        dischargeRing = maxRingInCore
    if chargeRing > maxRingInCore:
        runLog.warning(
            f"Charge ring {chargeRing} is outside the core (max {maxRingInCore}). "
            "Changing it to be the max ring."
        )
        chargeRing = maxRingInCore

    # process arguments
    if dischargeRing is None:
        # No discharge ring given, so we default to converging from outside to inside
        # and therefore discharging from the center
        dischargeRing = 1
    if chargeRing is None:
        # Charge ring not specified. Since we default to convergent shuffling, we
        # must insert the fuel at the periphery.
        chargeRing = maxRingInCore
    if jumpRingFrom is not None and not (1 < jumpRingFrom < maxRingInCore):
        raise ValueError(f"JumpRingFrom {jumpRingFrom} is not in the core.")
    if jumpRingTo is not None and not (1 <= jumpRingTo < maxRingInCore):
        raise ValueError(f"JumpRingTo {jumpRingTo} is not in the core.")

    if chargeRing > dischargeRing and jumpRingTo is None:
        # a convergent shuffle with no jumping. By setting
        # jumpRingTo to be 1, no jumping will be activated
        # in the later logic.
        jumpRingTo = 1
    elif jumpRingTo is None:
        # divergent case. Disable jumpring by putting jumpring at periphery.
        jumpRingTo = maxRingInCore

    if (
        chargeRing > dischargeRing
        and jumpRingFrom is not None
        and jumpRingFrom < jumpRingTo
    ):
        raise RuntimeError("Cannot have outward jumps in convergent cases.")
    if (
        chargeRing < dischargeRing
        and jumpRingFrom is not None
        and jumpRingFrom > jumpRingTo
    ):
        raise RuntimeError("Cannot have inward jumps in divergent cases.")

    # step 1: build the base rings
    numSteps = int((abs(dischargeRing - chargeRing) + 1) * (1.0 - coarseFactor))
    # don't let it be smaller than 2 because linspace(1,5,1)= [1], linspace(1,5,2)= [1,5]
    numSteps = max(numSteps, 2)

    baseRings = [int(ring) for ring in np.linspace(dischargeRing, chargeRing, numSteps)]
    # eliminate duplicates.
    newBaseRings = []
    for br in baseRings:
        if br not in newBaseRings:
            newBaseRings.append(br)

    baseRings = newBaseRings

    # build widths
    widths = []
    for i, ring in enumerate(baseRings[:-1]):
        # 0 is the most restrictive, meaning don't even look in other rings.
        widths.append(abs(baseRings[i + 1] - ring) - 1)
    widths.append(0)  # add the last ring with width 0.

    # step 2: locate which rings should be reversed to give the jump-ring effect.
    if jumpRingFrom is not None:
        _closestRingFrom, jumpRingFromIndex = findClosest(
            baseRings, jumpRingFrom, indx=True
        )
        _closestRingTo, jumpRingToIndex = findClosest(baseRings, jumpRingTo, indx=True)
    else:
        jumpRingToIndex = 0

    # step 3: build the final ring list, potentially with a reversed section
    newBaseRings = []
    newWidths = []
    # add in the non-reversed section before the reversed section

    if jumpRingFrom is not None:
        newBaseRings.extend(baseRings[:jumpRingToIndex])
        newWidths.extend(widths[:jumpRingToIndex])
        # add in reversed section that is jumped
        newBaseRings.extend(reversed(baseRings[jumpRingToIndex:jumpRingFromIndex]))
        newWidths.extend(reversed(widths[jumpRingToIndex:jumpRingFromIndex]))
        # add the rest.
        newBaseRings.extend(baseRings[jumpRingFromIndex:])
        newWidths.extend(widths[jumpRingFromIndex:])
    else:
        # no jump section. Just fill in the rest.
        newBaseRings.extend(baseRings[jumpRingToIndex:])
        newWidths.extend(widths[jumpRingToIndex:])

    return newBaseRings, newWidths


def buildConvergentRingSchedule(chargeRing, dischargeRing=1, coarseFactor=0.0):
    r"""
    Builds a ring schedule for convergent shuffling from ``chargeRing`` to ``dischargeRing``.

    Parameters
    ----------
    chargeRing : int
        The peripheral ring into which an assembly enters the core. A good default is
        outermost ring: ``r.core.getNumRings()``.

    dischargeRing : int, optional
        The last ring an assembly sits in before discharging. If no discharge, this is the one that
        gets placed where the charge happens. Default: Innermost ring

    coarseFactor : float, optional
        A number between 0 and 1 where 0 hits all rings and 1 only hits the outer, rJ, center, and rD rings.
        This allows coarse shuffling, with large jumps. Default: 0

    Returns
    -------
    convergent : list
        A list of rings in order from discharge to charge.

    conWidths : list
        A list of integers corresponding to the ringSchedule determining the widths of each ring area
    """
    # step 1: build the convergent rings
    numSteps = int((chargeRing - dischargeRing + 1) * (1.0 - coarseFactor))
    # don't let it be smaller than 2 because linspace(1,5,1)= [1], linspace(1,5,2)= [1,5]
    numSteps = max(numSteps, 2)
    convergent = [
        int(ring) for ring in np.linspace(dischargeRing, chargeRing, numSteps)
    ]

    # step 2. eliminate duplicates
    convergent = sorted(list(set(convergent)))

    # step 3. compute widths
    conWidths = []
    for i, ring in enumerate(convergent[:-1]):
        conWidths.append(convergent[i + 1] - ring)
    conWidths.append(1)

    # step 4. assemble and return
    return convergent, conWidths
