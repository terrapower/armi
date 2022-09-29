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
A place for additional functionality associated with the translation of assemblies. 
Typically these functions are utilized by a FuelHandler, including preprocessing 
user inputs to generate universal shuffle pattern data structures.
"""
import json
import math
import numpy
from armi import utils
from armi.reactor.flags import Flags


def buildRingSchedule(
    fuelHandler,
    internalRing=None,
    externalRing=None,
    diverging=False,
    jumpRingFrom=None,
    jumpRingTo=None,
    coarseFactor=0.0,
):
    r"""
    Build a ring schedule based on user inputs. This function returns an list, in order from discharge to charge,
    of groups of rings. This function will default to hexagonal ring structure if insufficient inputs are provided.
    The function is general enough to create inputs for convergent and divergent ring shuffling with jump rings.
    Ring numbering is consistant with DIF3D numbering scheme with ring 1 as the center assembly of the core.
    An outline of the functions behaviour is described below.

    Notes
    -----
    Jump ring behavior can be generalized by first building a base ring list where assemblies get discharged from
    A and charge to H::

        [A,B,C,D,E,F,G,H]


    If a jump should be placed where it jumps from ring G to C, reversed back to F, and then discharges from A,
    we simply reverse the sublist [C,D,E,F], leaving us with::

        [A,B,F,E,D,C,G,H]


    A less-complex, more standard convergent-divergent scheme is a subcase of this, where the sublist [A,B,C,D,E]
    or so is reversed, leaving::

        [E,D,C,B,A,F,G,H]

    Parameters
    ----------
    fuelHandler : Object
        An object for moving fuel around the core and reactor.

    internalRing : int, optional
        The center most ring of the ring shuffle. Default is 1.

    externalRing : int, optional
        Largest ring of the ring shuffle. Default is outermost ring

    diverging: bool, optional
        Is the ring schedule converging or diverging. default is false (converging)

    jumpRingFrom : int, optional
        The last ring an assembly sits in before jumping to the center

    jumpRingTo : int, optional
        The inner ring into which a jumping assembly jumps. Default is 1.

    coarseFactor : float, optional
        A number between 0 and 1 where 0 hits all rings and 1 only hits the outer, rJ, center, and rD rings.
        This allows coarse shuffling, with large jumps. Default: 0

    Returns
    -------
    ringSchedule : list
        A nested list of the rings in each group of the ring shuffle in order from discharge to charge.

    Examples
    -------
    >>> RingSchedule.buildRingSchedule(
            fuelHandler,
            internalRing=1,
            externalRing=17,
            jumpRingFrom = 14,
            coarseFactor=0.3)
    >>> [[12], [10, 11], [9], [7, 8], [5, 6], [4], [2, 3], [1], [13, 14], [15, 16], [17]]

    See Also
    --------
    findAssembly

    """
    # process arguments
    if internalRing is None:
        internalRing = 1

    if externalRing is None:
        if fuelHandler.r:
            externalRing = fuelHandler.r.core.getNumRings()
        else:
            externalRing = 18

    if diverging and not jumpRingTo:
        jumpRingTo = externalRing
    elif not jumpRingTo:
        jumpRingTo = internalRing

    if diverging and jumpRingFrom is not None and jumpRingFrom > jumpRingTo:
        raise RuntimeError("Cannot have inward jumps in divergent cases.")
    elif not diverging and jumpRingFrom is not None and jumpRingFrom < jumpRingTo:
        raise RuntimeError("Cannot have outward jumps in convergent cases.")

    # step 1: build the base rings
    numSteps = int((abs(internalRing - externalRing) + 1) * (1.0 - coarseFactor))
    # don't let it be smaller than 2 because linspace(1,5,1)= [1], linspace(1,5,2)= [1,5]
    if numSteps < 2:
        numSteps = 2
    # Build preliminary ring list
    if diverging:
        baseRings = [
            int(ring) for ring in numpy.linspace(externalRing, internalRing, numSteps)
        ]
    else:
        baseRings = [
            int(ring) for ring in numpy.linspace(internalRing, externalRing, numSteps)
        ]
    # eliminate duplicates.
    newBaseRings = []
    for br in baseRings:
        if br not in newBaseRings:
            newBaseRings.append(br)
    baseRings = newBaseRings

    # step 2: locate which rings should be reversed to give the jump-ring effect.
    if jumpRingFrom is not None:
        _closestRingFrom, jumpRingFromIndex = utils.findClosest(
            baseRings, jumpRingFrom, indx=True
        )
        _closestRingTo, jumpRingToIndex = utils.findClosest(
            baseRings, jumpRingTo, indx=True
        )
    else:
        jumpRingToIndex = 0

    # Update rings
    if diverging:
        for i, ring in enumerate(baseRings[:-1]):
            baseRings[i] = [j + 1 for j in range(baseRings[i + 1], ring)]
        baseRings[-1] = [baseRings[-1]]
    else:
        for i, ring in enumerate(baseRings[:-1]):
            baseRings[i] = [j for j in range(ring, baseRings[i + 1])]
        baseRings[-1] = [baseRings[-1]]

    # step 3: build the final ring list, potentially with a reversed section
    newBaseRings = []
    # add in the non-reversed section before the reversed section
    if jumpRingFrom is not None:
        newBaseRings.extend(baseRings[:jumpRingToIndex])
        # add in reversed section that is jumped
        newBaseRings.extend(reversed(baseRings[jumpRingToIndex:jumpRingFromIndex]))
        # add the rest.
        newBaseRings.extend(baseRings[jumpRingFromIndex:])
    else:
        # no jump section. Just fill in the rest.
        newBaseRings.extend(baseRings[jumpRingToIndex:])

    return newBaseRings


def buildConvergentRingSchedule(
    fuelHandler, dischargeRing=1, chargeRing=None, coarseFactor=0.0
):
    r"""
    Build a convergent ring schedule based on user inputs. This function returns a list, in order from discharge
    to charge, of groups of rings. This function will default to hexagonal ring structure. Ring numbering is
    consistent with DIF3D numbering scheme with ring 1 as the center assembly of the core. An outline of the
    function's behavior is described below.

    Parameters
    ----------
    fuelHandler : Object
        An object for moving fuel around the core and reactor.

    dischargeRing : int, optional
        The last ring an assembly sits in before discharging. Default is ring 1.

    chargeRing : int, optional
        The peripheral ring into which an assembly enters the core. Default is outermost ring.

    coarseFactor : float, optional
        A number between 0 and 1 where 0 hits all rings and 1 only hits the outer and center rings.
        This allows coarse shuffling, with large jumps. Default: 0

    Returns
    -------
    ringSchedule : list
        A nested list of the rings in each group of the ring shuffle in order from discharge to charge.

    Examples
    -------
    See Also
    --------
    findAssembly
    """
    # process arguments
    if chargeRing is None:
        if fuelHandler.r:
            chargeRing = fuelHandler.r.core.getNumRings()
        else:
            chargeRing = 18
    # step 1: build the ringSchedule rings
    numSteps = int((chargeRing - dischargeRing + 1) * (1.0 - coarseFactor))
    if numSteps < 2:
        # don't let it be smaller than 2 because linspace(1,5,1)= [1], linspace(1,5,2)= [1,5]
        numSteps = 2
    ringSchedule = [
        int(ring) for ring in numpy.linspace(dischargeRing, chargeRing, numSteps)
    ]
    # step 2. eliminate duplicates
    ringSchedule = sorted(list(set(ringSchedule)))
    # step 3. compute widths
    for i, ring in enumerate(ringSchedule[:-1]):
        ringSchedule[i] = [j for j in range(ring, ringSchedule[i + 1])]
    ringSchedule[-1] = [ringSchedule[-1]]
    # step 4. assemble and return
    return ringSchedule


def getRingAssemblies(fuelHandler, ringSchedule, circular=False, flags=Flags.FUEL):
    r"""
    Gather all assemblies within the ring groups described in ringSchedule. This function takes a ringSchedule, like
    those output by buildRingSchedule and buildConvergentRingSchedule, and returns all assemblies within those rings
    in a similar structure. An outline of the functions behaviour is described below.

    Example
    -------
    Assuming core state has all fuel assemblies in the first 6 hexagonal rings.
    ringSchedule = [[1,2],[3],[6],[4,5]]

    ringAssemblyArray = [[001-001, 002-001, 002-002, 002-003, 002-004, 002-005, 002-006],
                         [003-001, ...      003-012],
                         [006-001, ...      006-030],
                         [004-001, ...      004-018, 005-001, ...       005-024]]

    Note: Order of assemblies within each ring group is defined by the case settings "circularRingOrder

    Parameters
    ----------
    fuelHandler : Object
        An object for moving fuel around the core and reactor.

    ringSchedule: list
        A list of lists of rings in shuffle order from discharge to charge

    circular: bool, optional
        A variable to control the use of circular rings rather than hexagonal rings.
        Default is False

    flags: Flags object, options
        A variable to control the type of assemblies returned by the function.

    Returns
    -------
    ringAssemblyArray : list
        A nested list of the assemblies in each group of the ring shuffle in order from discharge to charge.
        The output is formatted the same as how batch loading zones are defined.

    """

    ringAssemblyArray = []

    for rings in ringSchedule:
        assemblies = []
        # Get assemblies for each ring group
        for ring in rings:
            if circular:
                assemblies += fuelHandler.r.core.getAssembliesInCircularRing(
                    ring, typeSpec=flags
                )
            else:
                assemblies += fuelHandler.r.core.getAssembliesInRing(
                    ring, typeSpec=flags
                )
        # Sort assemblies within each ring group
        if fuelHandler.cs["circularRingOrder"] == "angle":
            assemblies.sort(key=lambda x: squaredDistanceFromOrigin(x))
            assemblies.sort(key=lambda x: assemAngle(x))
        elif fuelHandler.cs["circularRingOrder"] == "distanceSmart":
            assemblies.sort(key=lambda x: assemAngle(x))
            assemblies.sort(key=lambda x: squaredDistanceFromOrigin(x))
        else:
            assemblies.sort(key=lambda x: assemAngle(x))
            assemblies.sort(key=lambda x: squaredDistanceFromOrigin(x))
        # append assemblies in ring group to data structure
        ringAssemblyArray.append(assemblies)

    return ringAssemblyArray


def getBatchZoneAssembliesFromLocation(
    fuelHandler,
    batchZoneAssembliesLocations,
    sortFun=None,
):
    r"""
    Gather all assembly objects by locations provided in BatchZoneAssembliesLocations. This function converts an
    array of location strings and converts it to an array of assemblies. New assemblies and assemblies that were
    previously removed from the core can also be gathered. The function can sort the assemblies in each zone by
    a user defined function if desired. An outline of the function behaviour is described below.

    Example
    -------
    batchZoneAssembliesLocations = [["001-001", "002-001", "002-002", "002-003", "002-004", "002-005", "002-006"],
                                    ["003-001", ...        "003-012"],
                                     ...
                                    ["004-001", ...        "004-018", "005-001",  ...       "005-024"]]

    batchAssemblyArray = [[<assembly 001-001>, ... <assembly 002-006>],
                          [<assembly 003-001>, ... <assembly 003-012>],
                           ...
                          [<assembly 004-001>, ... <assembly 005-024>]]

    Acceptable Input Formats
    ------------------------
    core assembly: "xxx-xxx"
    new assembly: "new: assemType"
    new assembly with modified enrichment: "new: assemType; enrichment: uniform value or [block specific values]"
    sfp assembly: "sfp: assemName"

    Parameters
    ----------
    fuelHandler : Object
        An object for moving fuel around the core and reactor.

    batchZoneAssembliesLocations: list

        A list of lists of assembly location strings. This function preserves the organization of this parameter.
        This input should be organized by zone, from discharge to charge, and include all assembly locations for
        each zone. See example above

    sortFun: function, optional
        A function that returns a value to sort assemblies in each zone.

    Returns
    -------
    batchAssemblyArray : list
        A nested list of the assemblies in each zone of a batch loading pattern in order from discharge to charge.
    """

    batchAssemblyArray = []

    for zone in batchZoneAssembliesLocations:
        zoneAssembly = []
        for assemblyLocation in zone:
            # is assemblyLocation a core location
            if assemblyLocation[:3].isnumeric():
                # is assemblyLocation the center of the core
                if int(assemblyLocation[:3]) == 1:
                    if int(assemblyLocation[4:]) == 1:
                        zoneAssembly.append(
                            fuelHandler.r.core.getAssemblyWithStringLocation(
                                assemblyLocation
                            )
                        )
                    else:
                        raise RuntimeError(
                            "the provided assembly location, {}, is not valid".format(
                                assemblyLocation
                            )
                        )
                elif int(assemblyLocation[:3]) <= fuelHandler.r.core.getNumRings():
                    if (int(assemblyLocation[:3]) - 1) * 6 >= int(assemblyLocation[4:]):
                        zoneAssembly.append(
                            fuelHandler.r.core.getAssemblyWithStringLocation(
                                assemblyLocation
                            )
                        )
                    else:
                        raise RuntimeError(
                            "the provided assembly location, {}, is not valid".format(
                                assemblyLocation
                            )
                        )
                else:
                    raise RuntimeError(
                        "the provided assembly location, {}, is not valid".format(
                            assemblyLocation
                        )
                    )
            # is assemblyLocation outside the core
            else:
                try:
                    assembly = None
                    for settings in assemblyLocation.split("; "):
                        setting, value = settings.split(": ")
                        # is assemblyLocation a new assembly
                        if setting.lower() == "new":
                            if value in fuelHandler.r.blueprints.assemblies.keys():
                                assembly = fuelHandler.r.core.createAssemblyOfType(
                                    assemType=value
                                )
                            else:
                                raise RuntimeError(
                                    "{} is not defined in the blueprint".format(value)
                                )
                        # is assemblyLocation in the SFP
                        elif setting.lower() == "sfp":
                            if value in [
                                i.getName()
                                for i in fuelHandler.r.core.sfp.getChildren()
                            ]:
                                assembly = fuelHandler.r.core.sfp.getAssembly(value)
                            else:
                                raise RuntimeError(
                                    "{} does not exist in the SFP".format(value)
                                )
                        # is the enrichment changing
                        elif setting.lower() == "enrichment":
                            if assembly and _is_list(value):
                                fuelEnr = json.loads(value)
                                changeBlockLevelEnrichment(assembly, fuelEnr)

                            else:
                                raise RuntimeError(
                                    "{} is not a valid enrichment".format(value)
                                )
                        else:
                            raise NotImplementedError(
                                "Setting, {}, not reconized".format(setting)
                            )
                    zoneAssembly.append(assembly)
                except:
                    raise RuntimeError("Error loading assemblies, check inputs")

        # if sort function provided, sort assemblies
        if sortFun:
            try:
                zoneAssembly.sort(key=lambda x: sortFun(x))
            except:
                raise RuntimeError("the provided sorting function is not valid")

        # append zoneAssembly to batchAssemblyArray
        batchAssemblyArray.append(zoneAssembly)

    return batchAssemblyArray


def getCascadesFromLocations(fuelHandler, cascadeAssemblyLocations):
    r"""
    Translate lists of locations into cascade shuffle data structure. This function converts an array of
    location strings into an array of assemblies. The locations in each list should be provided in order
    of discharge to charge. An outline of the function behavior is described below.

    Example
    -------
    cascadeAssemblyLocations = [["001-001", "002-001", "003-001", "003-007", "004-001"],
                                ["002-002", "003-001", "003-008", ...],
                                  ...
                                ["002-006", ...        "003-012", ...]]

    batchAssemblyArray = [[<assembly 001-001>, ... <assembly 004-001>],
                          [<assembly 003-001>, ... <assembly 003-008>, ...],
                           ...
                          [<assembly 002-006>, ... <assembly 003-012>, ...]]

    Parameters
    ----------
    fuelHandler : Object
        An object for moving fuel around the core and reactor.

    cascadeAssemblyLocations: list
        A list of cascade lists of assembly location strings. This function preserves the organization of this parameter.
        see getBatchZoneAssembliesFromLocation for more information.

    Returns
    -------
    see getBatchZoneAssembliesFromLocation
    """

    return getBatchZoneAssembliesFromLocation(
        fuelHandler, batchZoneAssembliesLocations=cascadeAssemblyLocations, sortFun=None
    )


def buildBatchCascades(
    assemblyArray,
    fromSort=None,
    toSort=None,
    newFuelName=None,
):
    r"""
    Gather all assemblies within the ring groups described in ringSchedule. This function takes a ringSchedule, like
    those output by buildRingSchedule and buildConvergentRingSchedule, and returns all assemblies within those rings
    in a similar structure. An outline of the functions behaviour is described below.

    Build cascade swap shuffle pattern data structures for the batch loading array provided. The function takes a batch
    loading array and creates a number of swap cascades equal to the number of assemblies in the charge zone. The number
    of assemblies in each zone does not need to be equal:

    if the number of cascades is greater than the number of spaces in a zone - The function will assign all cascades to
    each available location then assign the remaining cascades to spaces in the next zone. Further iterations will
    prioritize assigning further cascade steps to cascades assigned to initial location.

    if the number of cascades is less than the number of spaces in a zone - The function will assign all cascades to a
    space within the zone, then repeat the process for the remaining spaces.

    Parameters
    ----------
    assemblyArray : list
        A nested list of the assemblies in each batch loading zone ordered from discharge to charge. A number of cascades
        equal to the length of assemblyArray[-1] will be created.

    fromSort: function, optional
        A function that returns a value to sort assemblies that need to be moved, smallest to largest. Default function
        sorts by distance from center.
        e.g. If the highest burnup assemblies in assemblyArray[0] were moving to the highest flux region in assemblyArray[1].
            This function would return the burnup of an assembly.

    toSort: function, optional
        A function that returns a value to sort locations that assemblies are being moved to, smallest to largest. Default
        function sorts by distance from center.
        e.g. If the highest burnup assemblies in assemblyArray[0] were moving to the highest flux region in assemblyArray[1].
            This function would return the flux at an assemblies location.

    newFuelName: string, optional
        The string name of the assembly type to be charged on each shuffle cascade. Only functions if an input is provided.

    Returns
    -------
    dataStructure : array
        An array of assemblies to be sent to the swapCascade function of the fuel handler

    """

    if not fromSort:
        fromSort = _defaultSort

    if not toSort:
        toSort = _defaultSort

    # Clean input array and reverse order to match convention
    cleanArray = [i for i in assemblyArray if i != []]
    cleanArray.reverse()
    tempChains = [[[i] for i in cleanArray[0]], []]

    if len(cleanArray) > 1:
        check = True
        # Set up assembliesToAssign
        fromGroupIndex = 1
        assemblyFrom = cleanArray[fromGroupIndex]
        assemblyFrom.sort(key=lambda x: fromSort(x))
    else:
        check = False

    while check:
        # Sort current chains by previous assembly
        sortedAssemblyTo = tempChains[0]
        sortedAssemblyTo.sort(key=lambda x: toSort(x[-1]))

        if len(sortedAssemblyTo) < len(assemblyFrom):
            # Update tempChains to prevent doubling up
            if len(tempChains) == 1:
                tempChains = [[]]
            else:
                tempChains = tempChains[1:]
            # Add assemblies to swap chains and update tempChains
            for i in range(len(sortedAssemblyTo)):
                sortedAssemblyTo[i].append(assemblyFrom[i])
                tempChains[-1].append(sortedAssemblyTo[i])
            # Update assemblyFrom
            assemblyFrom = assemblyFrom[len(sortedAssemblyTo) :]

        elif len(tempChains[0]) == len(assemblyFrom):
            # Update tempChains to prevent doubling up
            if len(tempChains) == 1:
                tempChains = [[]]
            else:
                tempChains = tempChains[1:]
            # Add assemblies to swap chains and update tempChains
            for i in range(len(sortedAssemblyTo)):
                sortedAssemblyTo[i].append(assemblyFrom[i])
                tempChains[-1].append(sortedAssemblyTo[i])
            # Get next set of assemblies
            fromGroupIndex += 1
            if fromGroupIndex < len(cleanArray):
                assemblyFrom = cleanArray[fromGroupIndex]
                assemblyFrom.sort(key=lambda x: fromSort(x))
                tempChains.append([])

        elif len(sortedAssemblyTo) > len(assemblyFrom):
            # Update tempChains to prevent doubling up
            tempChains[0] = sortedAssemblyTo[len(assemblyFrom) :]
            # Add assemblies to swap chains and update tempChains
            for i in range(len(assemblyFrom)):
                sortedAssemblyTo[i].append(assemblyFrom[i])
                tempChains[-1].append(sortedAssemblyTo[i])
            # Get next set of assemblies
            fromGroupIndex += 1
            if fromGroupIndex < len(cleanArray):
                assemblyFrom = cleanArray[fromGroupIndex]
                assemblyFrom.sort(key=lambda x: fromSort(x))
                tempChains.append([])

        # Break Loop once complete
        if fromGroupIndex >= len(cleanArray):
            check = False

    dataStructure = [cascade for group in tempChains for cascade in group]

    # Reverse order to match convention
    for cascade in dataStructure:
        cascade.reverse()

    if newFuelName:
        if newFuelName in dataStructure[0][0].parent.r.blueprints.assemblies.keys():
            for cascade in dataStructure:
                cascade.append(
                    cascade[-1].parent.createAssemblyOfType(assemType=newFuelName)
                )
        else:
            raise ValueError("{} not a valid assembly name".format(newFuelName))

    return dataStructure


def changeBlockLevelEnrichment(
    assembly,
    enrichmentList,
):
    r"""
    This function changes the block level enrichment of an assembly to match an
    input value or list of values. The block level function adjustUEnrich is used
    to adjust the number uranium number density.

    Parameters
    ----------
    assembly : assembly object
        Object that represents an assembly within the simulation

    enrichmentList : list
        A list of enrichments values to assign to each block in the assembly.
        This variable can also be a single float to assign to all blocks in the assembly.
    """

    if isinstance(enrichmentList, list):
        # remove non fuel blocks from enrichment list (enrichment = 0)
        fuelBlockEnrichmentList = [enr for enr in enrichmentList if enr != 0]
        if len(assembly.getBlocks(Flags.FUEL)) == len(fuelBlockEnrichmentList):
            for block, enrichment in zip(
                assembly.getBlocks(Flags.FUEL), fuelBlockEnrichmentList
            ):
                block.adjustUEnrich(enrichment)
        else:
            raise RuntimeError(
                "Number of enrichment values provided does not match number of blocks in assembly {}"
                "".format(assembly.name)
            )
    elif isinstance(enrichmentList, float):
        for block in assembly:
            block.adjustUEnrich(enrichmentList)
    else:
        raise RuntimeError("{} is not a valid enrichment input".format(enrichmentList))


# define basic sorting functions
def squaredDistanceFromOrigin(assembly):
    origin = numpy.array([0.0, 0.0, 0.0])
    p = numpy.array(assembly.spatialLocator.getLocalCoordinates())
    return round(((p - origin) ** 2).sum(), 5)


def assemAngle(assembly):
    x, y, _ = assembly.spatialLocator.getLocalCoordinates()
    return round(math.atan2(y, x), 5)


def _defaultSort(assembly):
    origin = numpy.array([0.0, 0.0, 0.0])
    p = numpy.array(assembly.spatialLocator.getLocalCoordinates())
    return round(((p - origin) ** 2).sum(), 5)


def _is_list(string):
    try:
        json.loads(string)
        return True
    except ValueError:
        return False
