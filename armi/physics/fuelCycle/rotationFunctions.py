import os
import re
from armi import runLog
from armi.reactor.flags import Flags
from armi.utils.customExceptions import InputError


def simpleAssemblyRotation(fuelHandler):
    r"""
    Rotate all pin-detail assemblies that were just shuffled by 60 degrees.

    Notes
    -----
    Optionally rotate stationary (non-shuffled) assemblies if the setting is set. Only pin-detail
    assemblies can be rotated, because homogenized assemblies are isotropic.

    Examples
    --------
    >>> fh.simpleAssemblyRotation()

    See Also
    --------
    buReducingAssemblyRotation : an alternative rotation algorithm
    outage : calls this method based on a user setting
    """
    runLog.info("Rotating assemblies by 60 degrees")
    numRotated = 0
    hist = fuelHandler.o.getInterface("history")
    for assembly in hist.getDetailAssemblies():
        if (
            assembly in fuelHandler.moved
            or fuelHandler.cs["assemblyRotationStationary"]
        ):
            fuelHandler.rotateAssembly(assembly, 1)
            numRotated += 1
            location = assembly.getLocation()
            runLog.extra("Rotating Assembly {0} to Orientation {1}".format(location, 1))
    runLog.extra("Rotated {0} assemblies".format(numRotated))


def functionalAssemblyRotation(fuelHandler, function=None):
    r"""
    Rotates all detail assemblies to put the highest bu pin in the lowest power orientation.

    See Also
    --------
    simpleAssemblyRotation : an alternative rotation algorithm
    outage : calls this method based on a user setting
    """

    if not function:
        function = getOptimalAssemblyOrientation

    runLog.info("Algorithmically rotating assemblies to minimize burnup")
    numRotated = 0
    hist = fuelHandler.o.getInterface("history")
    for aPrev in fuelHandler.moved:
        # do we need to add a check for assemblies added from SFP / loadQueue
        aNow = fuelHandler.r.core.getAssemblyWithStringLocation(aPrev.lastLocationLabel)
        if aNow in hist.getDetailAssemblies():
            try:
                rot = function(aNow, aPrev)
            except:
                raise ValueError(
                    "Error evaluating rotation amount for {}".format(aNow.getLocation())
                )
            fuelHandler.rotateAssembly(aNow, rot)
            numRotated += 1
            location = aNow.getLocation()
            runLog.important(
                "Rotating Assembly {0} to Orientation {1}".format(location, rot)
            )
    # rotate NON-MOVING assemblies (stationary)
    if fuelHandler.cs["assemblyRotationStationary"]:
        for assembly in hist.getDetailAssemblies():
            if assembly not in fuelHandler.moved:
                try:
                    rot = function(assembly, assembly)
                except:
                    raise ValueError(
                        "Error evaluating rotation amount for {}".format(
                            assembly.getLocation()
                        )
                    )
                fuelHandler.rotateAssembly(assembly, rot)
                numRotated += 1
                location = assembly.getLocation()
                runLog.important(
                    "Rotating Assembly {0} to Orientation {1}".format(location, rot)
                )
    runLog.info("Rotated {0} assemblies".format(numRotated))


def getOptimalAssemblyOrientation(assembly, aPrev):
    """
    Get optimal assembly orientation/rotation to minimize peak burnup.

    Notes
    -----
    Works by placing the highest-BU pin in the location (of 6 possible locations) with lowest
    expected pin power. We evaluated "expected pin power" based on the power distribution in
    aPrev, which is the previous assembly located here. If aPrev has no pin detail, then we must
    use its corner fast fluxes to make an estimate.

    Parameters
    ----------
    assembly : Assembly object
        The assembly that is being rotated.
    aPrev : Assembly object
        The assembly that previously occupied this location (before the last shuffle).
        If the assembly "assembly" was not shuffled, then "aPrev" = "assembly".
        If "aPrev" has pin detail, then we will determine the orientation of "assembly" based on
        the pin powers of "aPrev" when it was located here.
        If "aPrev" does NOT have pin detail, then we will determine the orientation of "assembly"
        based on the corner fast fluxes in "aPrev" when it was located here.

    Returns
    -------
    rot : int
        An integer from 0 to 5 representing the "orientation" of the assembly.
        This orientation is relative to the current assembly orientation.
        rot = 0 corresponds to no rotation.
        rot represents the number of pi/3 counterclockwise rotations for the default orientation.

    Examples
    --------
    >>> fh.getOptimalAssemblyOrientation(a,aPrev)

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

    rot = 0
    # First get pin index of maximum BU in this assembly.
    _maxBuAssem, maxBuBlock = assembly.getMaxParam("percentBuMax", returnObj=True)
    if maxBuBlock is None:
        return rot

    maxBuPinIndexAssem = int(maxBuBlock.p.percentBuMaxPinLocation - 1)
    bIndexMaxBu = assembly.index(maxBuBlock)
    # Where is the max burnup pin
    if maxBuPinIndexAssem == 0:
        return rot
    else:
        if aPrevDetailFlag:
            prevAssemPowHereMIN = float("inf")
            for possibleRotation in range(6):
                indexLookup = maxBuBlock.rotatePins(possibleRotation, justCompute=True)
                index = int(indexLookup[maxBuPinIndexAssem])
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


def repeatAssemblyRotation(fuelHandler):
    r"""
    Description
    """

    rotations = _readRotations(fuelHandler)
    rotationList = rotations[fuelHandler.cycle + 1]
    rotationAssemblies = _processRotationList(fuelHandler, rotationList)
    for assembly, rotNum in rotationAssemblies:
        fuelHandler.rotateAssembly(assembly, rotNum)


def _readRotations(fuelHandler):
    # read in rotations
    fName = fuelHandler.cs["explicitRepeatShuffles"]
    try:
        f = open(fName)
    except:
        raise RuntimeError(
            "Could not find/open repeat shuffle file {} in working directory {}"
            "".format(fName, os.getcwd())
        )

    rotations = {}
    numRotations = 0
    headerText = r"Before cycle (\d+)"
    pat2Text = r"([A-Za-z0-9!\-]+) at ([A-Za-z0-9!\-]+) was rotated from ([A-Za-z0-9!\-]+) to ([A-Za-z0-9!\-]+)"

    for line in f:
        if "Before cycle" in line:
            m = re.search(headerText, line)
            if not m:
                raise InputError(
                    'Failed to parse line "{0}" in shuffle file'.format(line)
                )
            cycle = int(m.group(1))
            rotations[cycle] = []
        elif "moved from" in line or line == "\n":
            pass
        elif "rotated from" in line:
            m = re.search(pat2Text, line)
            if not m:
                raise InputError(
                    'Failed to parse line "{0}" in shuffle file'.format(line)
                )
            movingAssemName = m.group(1)
            newLoc = m.group(2)
            oldRot = m.group(3)
            newRot = m.group(4)
            rotations[cycle].append((movingAssemName, newLoc, oldRot, newRot))
            numRotations += 1

        else:
            runLog.info('Failed to parse line "{0}" in shuffle file'.format(line))

    f.close()

    runLog.info(
        "Read {0} rotations over {1} cycles".format(numRotations, len(rotations.keys()))
    )

    return rotations


def _processRotationList(
    fuelHandler,
    rotationList,
):
    r"""
    This function converts the rotations provided by readMoves into a shuffle data structure
    """
    rotationStructure = []
    rotNum = 0
    for assembly in rotationList:
        if assembly[2] > assembly[3]:
            rotNum = 6 - assembly[2] + assembly[3]
        else:
            rotNum = assembly[3] - assembly[2]

        rotationStructure.append(
            (fuelHandler.r.core.getAssemblyWithStringLocation(assembly[1]), rotNum)
        )
    return rotationStructure
