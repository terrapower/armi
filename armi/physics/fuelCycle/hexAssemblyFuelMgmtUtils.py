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

import numpy

from armi import runLog
from armi.reactor.flags import Flags
from armi.utils.mathematics import findClosest


def getOptimalAssemblyOrientation(a, aPrev):
    """
    Get optimal assembly orientation/rotation to minimize peak burnup.

    Notes
    -----
    Works by placing the highest-BU pin in the location (of 6 possible locations) with lowest
    expected pin power. We evaluated "expected pin power" based on the power distribution in
    aPrev, which is the previous assembly located here. If aPrev has no pin detail, then we must use its
    corner fast fluxes to make an estimate.

    Parameters
    ----------
    a : Assembly object
        The assembly that is being rotated.

    aPrev : Assembly object
        The assembly that previously occupied this location (before the last shuffle).

        If the assembly "a" was not shuffled, then "aPrev" = "a".

        If "aPrev" has pin detail, then we will determine the orientation of "a" based on
        the pin powers of "aPrev" when it was located here.

        If "aPrev" does NOT have pin detail, then we will determine the orientation of "a" based on
        the corner fast fluxes in "aPrev" when it was located here.

    Returns
    -------
    rot : int
        An integer from 0 to 5 representing the "orientation" of the assembly.
        This orientation is relative to the current assembly orientation.
        rot = 0 corresponds to no rotation.
        rot represents the number of pi/3 counterclockwise rotations for the default orientation.

    Examples
    --------
    >>> getOptimalAssemblyOrientation(a, aPrev)
    4

    See Also
    --------
    rotateAssemblies : calls this to figure out how to rotate
    """
    # determine whether or not aPrev had pin details
    fuelPrev = aPrev.getFirstBlock(Flags.FUEL)
    if fuelPrev:
        aPrevDetailFlag = fuelPrev.p.pinLocation[4] is not None
    else:
        aPrevDetailFlag = False

    rot = 0  # default: no rotation
    # First get pin index of maximum BU in this assembly.
    _maxBuAssem, maxBuBlock = a.getMaxParam("percentBuMax", returnObj=True)
    if maxBuBlock is None:
        # no max block. They're all probably zero
        return rot

    # start at 0 instead of 1
    maxBuPinIndexAssem = int(maxBuBlock.p.percentBuMaxPinLocation - 1)
    bIndexMaxBu = a.index(maxBuBlock)

    if maxBuPinIndexAssem == 0:
        # Don't bother rotating if the highest-BU pin is the central pin. End this method.
        return rot
    else:
        # transfer percentBuMax rotated pin index to non-rotated pin index
        if aPrevDetailFlag:
            # aPrev has pin detail
            # Determine which of 6 possible rotated pin indices had the lowest power when aPrev was here.
            prevAssemPowHereMIN = float("inf")

            for possibleRotation in range(6):
                # get rotated pin index
                indexLookup = maxBuBlock.rotatePins(possibleRotation, justCompute=True)
                # rotated index of highest-BU pin
                index = int(indexLookup[maxBuPinIndexAssem])
                # get pin power at this index in the previously assembly located here
                # power previously at rotated index
                prevAssemPowHere = aPrev[bIndexMaxBu].p.linPowByPin[index - 1]

                if prevAssemPowHere is not None:
                    runLog.debug(
                        "Previous power in rotation {0} where pinLoc={1} is {2:.4E} W/cm"
                        "".format(possibleRotation, index, prevAssemPowHere)
                    )
                    if prevAssemPowHere < prevAssemPowHereMIN:
                        prevAssemPowHereMIN = prevAssemPowHere
                        rot = possibleRotation
        else:
            raise ValueError(
                "Cannot perform detailed rotation analysis without pin-level "
                "flux information."
            )

        runLog.debug("Best relative rotation is {0}".format(rot))
        return rot


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
    -------
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

    baseRings = [
        int(ring) for ring in numpy.linspace(dischargeRing, chargeRing, numSteps)
    ]
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
    Builds a ring schedule for convergent shuffling from chargeRing to dischargeRing.

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
        int(ring) for ring in numpy.linspace(dischargeRing, chargeRing, numSteps)
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


def _buildEqRingScheduleHelper(ringSchedule, numRings):
    r"""
    turns ringScheduler into explicit list of rings.

    Pulled out of buildEqRingSchedule for testing.

    Parameters
    ----------
    ringSchedule : list
        List of ring bounds that is required to be an even number of entries.  These
        entries then are used in a from - to approach to add the rings.  The from ring will
        always be included.

    numRings : int
        The number of rings in the hex assembly reactor.

    Returns
    -------
    ringList : list
        List of all rings in the order they should be shuffled.

    Examples
    --------
    >>> _buildEqRingScheduleHelper([1,5])
    [1,2,3,4,5]

    >>> _buildEqRingScheduleHelper([1,5,9,6])
    [1,2,3,4,5,9,8,7,6]

    >>> _buildEqRingScheduleHelper([9,5,3,4,1,2])
    [9,8,7,6,5,3,4,1,2]

    >>> _buildEqRingScheduleHelper([2,5,1,1])
    [2,3,4,5,1]
    """
    if len(ringSchedule) % 2 != 0:
        runLog.error("Ring schedule: {}".format(ringSchedule))
        raise RuntimeError("Ring schedule does not have an even number of entries.")

    ringList = []
    for i in range(0, len(ringSchedule), 2):
        fromRing = ringSchedule[i]
        toRing = ringSchedule[i + 1]
        numRings = abs(toRing - fromRing) + 1

        ringList.extend([int(j) for j in numpy.linspace(fromRing, toRing, numRings)])

    # eliminate doubles (but allow a ring to show up multiple times)
    newList = []
    lastRing = None
    for ring in ringList:
        if ring != lastRing:
            newList.append(ring)
        if ring > numRings:
            # error checking
            runLog.warning(
                "Ring {0} in eqRingSchedule larger than largest ring in reactor {1}. "
                "Adjust shuffling.".format(ring, numRings),
                single=True,
                label="too many rings",
            )
        lastRing = ring

    return newList


def _squaredDistanceFromOrigin(a):
    """Get the squared distance from the origin of an assembly.

    Notes
    -----
    Just a helper for ``buildEqRingSchedule()``

    Parameters
    ----------
    a: Assembly
        Fully initialize Assembly object; already part of a reactor core.

    Returns
    -------
    float: Distance from reactor center
    """
    origin = numpy.array([0.0, 0.0, 0.0])
    p = numpy.array(a.spatialLocator.getLocalCoordinates())
    return ((p - origin) ** 2).sum()


def _assemAngle(a):
    """Get the angle of the Assembly, in the reactor core.

    Notes
    -----
    Just a helper for ``buildEqRingSchedule()``

    Parameters
    ----------
    a: Assembly
        Fully initialize Assembly object; already part of a reactor core.

    Returns
    -------
    float: Angle position of assembly around the reactor core
    """
    x, y, _ = a.spatialLocator.getLocalCoordinates()
    return math.atan2(y, x)


def buildEqRingSchedule(core, ringSchedule, circularRingOrder):
    r"""
    Expands simple ringSchedule input into full-on location schedule.

    Parameters
    ----------
    core : Core object
        Fully initialized Core object, for a hex assembly reactor.

    ringSchedule : list
        List of ring bounds that is required to be an even number of entries.  These
        entries then are used in a from - to approach to add the rings.  The from ring will
        always be included.

    circularRingOrder : str
        From the circularRingOrder setting. Valid values include angle and distanceSmart,
        anything else will

    Returns
    -------
    list: location schedule
    """
    # start by expanding the user-input eqRingSchedule list into a list containing
    # all the rings as it goes.
    ringList = _buildEqRingScheduleHelper(ringSchedule, core.getNumRings())

    # now build the locationSchedule ring by ring using this ringSchedule
    lastRing = 0
    locationSchedule = []
    for ring in ringList:
        assemsInRing = core.getAssembliesInRing(ring, typeSpec=Flags.FUEL)
        if circularRingOrder == "angle":
            sorter = lambda a: _assemAngle(a)
        elif circularRingOrder == "distanceSmart":
            if lastRing == ring + 1:
                # converging. Put things on the outside first.
                sorter = lambda a: -_squaredDistanceFromOrigin(a)
            else:
                # diverging. Put things on the inside first.
                sorter = _squaredDistanceFromOrigin
        else:
            # purely based on distance. Can mix things up in convergent-divergent cases. Prefer distanceSmart
            sorter = _squaredDistanceFromOrigin

        assemsInRing = sorted(assemsInRing, key=sorter)
        for a in assemsInRing:
            locationSchedule.append(a.getLocation())
        lastRing = ring

    return locationSchedule
