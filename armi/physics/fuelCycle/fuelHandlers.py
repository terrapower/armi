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
This module handles fuel management operations such as translation, rotation, and
fuel processing (in fluid systems).

The :py:class:`FuelHandlerInterface` instantiates a ``FuelHandler``, which is typically a user-defined
subclass the :py:class:`FuelHandler` object in custom shuffle-logic input files.
Users point to the code modules with their custom fuel handlers using the
``shuffleLogic`` and ``fuelHandlerName`` settings, as described in :doc:`/user/inputs/fuel_management`.
These subclasses override ``chooseSwaps`` that determine
the particular shuffling of a case.

This module also handles repeat shuffles when doing a restart.
"""
import math
import os
import re
import warnings

import numpy


from armi.utils.customExceptions import InputError
from armi.reactor.flags import Flags
from armi.utils.mathematics import resampleStepwise
from armi import runLog
from armi.physics.fuelCycle import shuffleStructure
from armi.physics.fuelCycle import rotationFunctions
from armi.physics.fuelCycle import translationFunctions


class FuelHandler:
    """
    A fuel handling machine can move fuel around the core and reactor.

    It makes decisions on how to shuffle fuel based on user specifications.
    It provides some supervisory data tracking, such as having the ability
    to print out information about all moves that happened in a cycle (without
    the user needing to explicitly track this information).

    To use this, simply create an input Python file and point to it by path
    with the ``fuelHandler`` setting. In that file, subclass this object.
    """

    def __init__(self, operator):
        # we need access to the operator to find the core, get settings, grab
        # other interfaces, etc.
        self.o = operator
        self.moved = []
        self._handleBackwardsCompatibility()

    def _handleBackwardsCompatibility(self):
        # prepSearch used to be part of the API but is deprecated. This will
        # trigger a warning if it's implemented.
        # We have to do this hack until we phase out old inputs.
        # This basically asks: "Did the custom subclass override prepSearch?"
        if self.prepSearch.__func__ is not FuelHandler.prepSearch:
            self.prepSearch()

    @property
    def cycle(self):
        """
        Link to the current cycle number.

        Notes
        ------
        This retains backwards compatibility with previous fuel handler inputs.
        """
        return self.o.r.p.cycle

    @property
    def cs(self):
        """Link to the Case Settings object."""
        return self.o.cs

    @property
    def r(self):
        """Link to the Reactor object."""
        return self.o.r

    def preoutage(self):
        r"""
        Stores locations of assemblies before they are shuffled to support generation of shuffle reports, etc.
        Also performs any additional functionality before shuffling.
        """
        self.prepCore()
        self._prepShuffleMap()
        self.r.core.locateAllAssemblies()

    def outage(self, factor=1.0):
        r"""
        This function coordinates any fuel movement and rotation between cycles
        """
        # Check that this is a new fuel handler instance
        if self.moved:
            raise ValueError(
                "Cannot perform two outages with same FuelHandler instance."
            )

            # Perform and record assembly translation
        self.chooseSwaps(factor)

        # Perform (and record) assembly rotations
        if self.cs["fluxRecon"] and self.cs["assemblyRotationAlgorithm"]:
            self.chooseRotations()

        self.recordShuffle()

    def chooseSwaps(self, shuffleFactors=None):
        r"""
        This function is for managing assembly translation between cycles.
        Users should update this function to implement assembly translation logic in subclasses of fuelHandler.
        """
        runLog.important("No logic implemented in chooseSwaps")

    def getFactorList(self, cycle):
        r"""
        Return cycle specific factor. Default is 1
        """
        return 1.0

    def recordShuffle(self):
        r"""
        This function records information about the shuffle performed by this fuelHandler object
        Recorded data includes:
            Starting assembly location  : str (xxx-xxx)             : lastLocationLabel
            Current assembly location   : str (xxx-xxx)             : getLocation()
            Starting rotation location  : int (0 - 5)               : lastRotationLabel
            Current rotation location   : int (0 - 5)               : getRotation()
            Block level enrichment      : list ([x.xx, ..., x.xx])  : [block.getUraniumMassEnrich() for block in assembly]
            Assembly blueprint type     : str (assembly name)       : getType()
            Assembly name               : str (Axxxx)               : getName()
        """
        if self.moved:
            numMoved = len(self.moved) * self.r.core.powerMultiplier

            for assembly in self.moved:
                try:
                    self.r.core.setMoveList(
                        self.cycle,
                        assembly.lastLocationLabel,
                        assembly.getLocation(),
                        assembly.lastRotationLabel,
                        assembly.getRotationNum(),
                        [block.getUraniumMassEnrich() for block in assembly],
                        assembly.getType(),
                        assembly.getName(),
                    )
                except:
                    runLog.important("A fuel management error has occurred. ")
                    runLog.important("Trying operation on assembly {}".format(assembly))
                    runLog.important("The moved list is {}".format(self.moved))
                    raise
        else:
            numMoved = 0

        self.o.r.core.p.numMoves = numMoved

        runLog.important(
            "Fuel handler performed {0} assembly shuffles.".format(numMoved)
        )

    def chooseRotations(self):
        r"""
        This function manages assembly rotations between cycles.
        Users should not use this function to implement assembly rotation logic in subclasses of fuelHandler, unlike chooseSwaps.
        The rotation function to be used is defined by self.cs["assemblyRotationAlgorithm"]. Users should create a new function with
        the desired rotation logic if self.cs["assemblyRotationAlgorithm"] is not one of the default rotation functions.
        """
        if hasattr(rotationFunctions, self.cs["assemblyRotationAlgorithm"]):
            rotationMethod = getattr(
                rotationFunctions, self.cs["assemblyRotationAlgorithm"]
            )
        elif hasattr(self, self.cs["assemblyRotationAlgorithm"]):
            rotationMethod = getattr(self, self.cs["assemblyRotationAlgorithm"])
        else:
            raise RuntimeError(
                "FuelHandler {0} does not have a rotation algorithm called {1}.\n"
                'Change your "assemblyRotationAlgorithm" setting'
                "".format(self, self.cs["assemblyRotationAlgorithm"])
            )

        rotationMethod(self)

    def prepCore(self):
        r"""
        Pre-fuel managment function space to update object parameters.
        Built in function calls .core.locateAllAssemblies() to update
        lastLocationLabel of all assembly objects in the core.
        """
        self.r.core.locateAllAssemblies()

    def prepShuffleMap(self):
        """Prepare a table of current locations for plotting shuffle maneuvers."""
        self.oldLocations = {}
        for a in self.r.core.getAssemblies():
            self.oldLocations[a.getName()] = a.spatialLocator.getGlobalCoordinates()

    def prepSearch(self, *args, **kwargs):
        """
        Optional method that can be implemented in preparation of shuffling.

        Often used to prepare the scope of a shuffling branch search.

        Notes
        -----
        This was used historically to keep a long-lived fuel handler in sync
        with the reactor and can now technically be removed from the API, but
        many historical fuel management inputs still expect it to be called
        by the framework, so here it remains. New developments should
        avoid using it. Most code using it has been refactored to just use
        a ``_prepSearch`` private method.

        It now should not be used and will trigger a DeprecationWarning
        in the constructor. It's still here because old user-input code
        calls the parent's prepSearch, which is this.
        """
        warnings.warn(
            "`FuelHandler.prepSearch` is being deprecated from the framework. Please "
            "change your fuel management input to call this method directly.",
            DeprecationWarning,
        )

    def findAssembly(
        self,
        targetRing=None,
        width=(0, 0),
        param=None,
        compareTo=None,
        forceSide=None,
        exclusions=None,
        typeSpec=None,
        mandatoryLocations=None,
        zoneList=None,
        excludedLocations=None,
        minParam=None,
        minVal=None,
        maxParam=None,
        maxVal=None,
        findMany=False,
        coords=None,
        exactType=False,
        acceptFirstCandidateRing=False,
        blockLevelMax=False,
        findFromSfp=False,
        maxNumAssems=None,
        circularRingFlag=False,
    ):
        r"""
        Search reactor for assemblies with various criterion. Primarily for shuffling.

        Parameters
        ----------
        targetRing : int, optional
            The ring in which to search

        width : tuple of integers
            A (size, side) tuple where size is the number of rings on either side to also check.
            side=1: only look in higher, -1: only look lower, 0: both sides

        param : string, optional
            A block (if blockLevelMax) or assem level param name such as 'power' or 'percentBu'
            (requires compareTo).

        compareTo : float or Assembly instance
            an assembly to be compared to. Alternatively, a floating point number to compare to.
            Even more alternatively,  an (assembly,mult) or (float,mult) tuple where mult is a
            multiplier. For example, if you wanted an assembly that had a bu close to half of
            assembly bob, you'd give param='percentBu', compareTo=(bob,0.5) If you want one with a
            bu close to 0.3, you'd do param='percentBu',compareTo=0.3. Yes, if you give a (float,
            multiplier) tuple, the code will make fun of you for not doing your own math, but will
            still operate as expected.

        forceSide : bool, optional
            requires the found assembly to have either 1: higher, -1: lower, None: any param than
             compareTo

        exclusions : list, optional
            List of assemblies that will be excluded from the search

        minParam : float or list, optional
            a parameter to compare to minVal for setting lower bounds. If list, must correspond to
            parameters in minVal in order.

        maxParam : float or list, optional
            a parameter to compare to maxVal for setting upper bounds of acceptable assemblies.
            If list,
            must correspond to parameters in maxVal in order.

        minVal : float or list, optional
            a value or a (parameter, multiplier) tuple for setting lower bounds

            For instance, if minParam = 'timeToLimit' and minVal=10, only assemblies with
            timeToLimit higher than 10 will be returned.  (Of course, there is also maxParam and
            maxVal)

        maxVal : float or list, optional
            a value or a (parameter, multiplier) tuple for setting upper bounds

        mandatoryLocations : list, optional
            a list of string-representations of locations in the core for limiting the search to
            several places

            Any locations also included in `excludedLocations` will be excluded.

        excludedLocations : list, optional
            a list of string-representations of locations in the core that will be excluded from
            the search

        zoneList : list, optional
            name of a zone defined in settings.py that will be picked from. Under development

        findMany : bool, optional
            If True, will return a list of assembies that match. Don't give a param.

        typeSpec : Flags or list of Flags, optional
            only assemblies with this type list will be returned. If none, only fuel will be found.

        coords : tuple, optional
            x,y tuple in cm. the fuel handler will try to find an assembly with a center closest to
            that point

        exactType : bool, optional
            require type to be exactly equal to what's in the type list. So
            Flags.IGNITER | Flags.FUEL is not Flags.INNER | Flags.IGNITER | Flags.FUEL

        acceptFirstCandidateRing : bool, optional
            takes the first assembly found in the earliest ring (without searching all rings for a
            maxBu, for example) So if the candidate rings are 1-10 and we're looking for igniter
            fuel with a maxBurnup, we don't get the max burnup in all those rings, but rather the
            igniter with the max burnup in the ring closest to 1. If there are no igniters until
            ring 4, you will get an igniter in ring 4.

        blockLevelMax : bool, optional
            If true, the param to search for will be built as the maximum block-level param of this
            name instead of the assembly param. This avoids the need to assign assembly level params
            sometimes.
            default: false.

        findFromSfp : bool, optional
            if true, will look in the spent-fuel pool instead of in the core.

        maxNumAssems : int, optional
            The maximum number of assemblies to return. Only relevant if findMany==True

        circularRingFlag : bool, optional
            A flag to toggle on using rings that are based on distance from the center of the
            reactor

        Notes
        -----
        The call signature on this method may have gotten slightly out of hand as
        valuable capabilities were added in fuel management studies. For additional expansion,
        it may be worth reconsidering the design of these query operations ;).

        Returns
        -------
        Assembly instance or assemList of assembly instances that match criteria, or None if none
        match

        Examples
        --------
        feed = self.findAssembly(targetRing=4,
                                 width=(0,0),
                                 param='maxPercentBu',
                                 compareTo=100,
                                 typeSpec=Flags.FEED | Flags.FUEL)

        returns the feed fuel assembly in ring 4 that has a burnup closest to 100% (the highest
        burnup assembly)
        """

        def compareAssem(candidate, current):
            """Check whether the candidate assembly should replace the current ideal
            assembly.

            Given a candidate tuple (diff1, a1) and current tuple (diff2, a2), decide
            whether the candidate is better than the current ideal. This first compares
            the diff1 and diff2 values. If diff1 is sufficiently less than diff2, a1
            wins, returning True. Otherwise, False. If diff1 and diff2 are sufficiently
            close, the assembly with the lesser assemNum wins. This should result in a
            more stable comparison than on floating-point comparisons alone.
            """
            if numpy.isclose(candidate[0], current[0], rtol=1e-8, atol=1e-8):
                return candidate[1].p.assemNum < current[1].p.assemNum
            else:
                return candidate[0] < current[0]

        def getParamWithBlockLevelMax(a, paramName):
            if blockLevelMax:
                return a.getChildParamValues(paramName).max()
            return a.p[paramName]

        assemList = []  # list for storing multiple results if findMany is true.

        # process input arguments
        if targetRing is None:
            # look through the full core
            targetRing = 0
            width = (100, 0)

        if exclusions is None:
            exclusions = []

        if isinstance(minVal, list):
            # list given with multiple mins
            minVals = minVal
            minParams = minParam
        else:
            minVals = [minVal]
            minParams = [minParam]

        if isinstance(maxVal, list):
            maxVals = maxVal
            maxParams = maxParam
        else:
            # just one given. put it in a list so the below machinery can handle it.
            maxVals = [maxVal]
            maxParams = [maxParam]

        if typeSpec is None:
            # restrict motions to fuel only
            # not really necessary. take this default out if you want to move control rods, etc.
            typeSpec = Flags.FUEL

        minDiff = (1e60, None)

        # compareTo can either be a tuple, a value, or an assembly
        # if it's a tuple, it can either be an int/float and a multiplier, or an assembly and a multiplier
        # if it's not a tuple, the multiplier will be assumed to be 1.0

        mult = 1.0  # if no mult brought in, just assume 1.0
        if isinstance(compareTo, tuple):
            # tuple (assem or int/float, multiplier) brought in.
            # separate it
            compareTo, mult = compareTo

        if isinstance(compareTo, float) or isinstance(compareTo, int):
            # floating point or int.
            compVal = compareTo * mult
        elif param:
            # assume compareTo is an assembly
            compVal = getParamWithBlockLevelMax(compareTo, param) * mult

        if coords:
            # find the assembly closest to xt,yt if coords are given without considering params.
            aTarg = None
            minD = 1e10
            xt, yt = coords  # assume (x,y) tuple.
            for a in self.r.core.getAssemblies():
                x, y, _ = a.spatialLocator.getLocalCoordinates()
                d = (y - yt) ** 2 + (x - xt) ** 2
                if d < minD:
                    minD = d
                    aTarg = a
            return aTarg

        if findFromSfp:
            # hack to enable SFP searching.
            candidateRings = ["SFP"]
        else:
            # set up candidateRings based on targetRing and width. The target rings comes first b/c it is preferred.
            candidateRings = [targetRing]
            if width[1] <= 0:
                # 0 or -1 implies that the inner rings can be added.
                for inner in range(width[0]):
                    candidateRings.append(
                        targetRing - inner - 1
                    )  # +1 to get 1,2,3 instead of 0,1,2
            if width[1] >= 0:
                # if 1, add in the outer rings
                for outer in range(width[0]):
                    candidateRings.append(targetRing + outer + 1)

        # get lists of assemblies in each candidate ring. Do it in this order in case we prefer ones in the first.
        # scan through all assemblies and find the one (or more) that best fits the criteria
        for ringI, assemsInRings in enumerate(
            self._getAssembliesInRings(
                candidateRings, typeSpec, exactType, exclusions, circularRingFlag
            )
        ):
            for a in assemsInRings:
                innocent = True
                # Check that this assembly's minParam is > the minimum for each minParam
                for minIndex, minVal in enumerate(minVals):
                    minParam = minParams[minIndex]
                    if minParam:
                        # a minimum was specified. Check to see if we're ok
                        if isinstance(minVal, tuple):
                            # tuple turned in. it's a multiplier and a param
                            realMinVal = (
                                getParamWithBlockLevelMax(a, minVal[0]) * minVal[1]
                            )
                        else:
                            realMinVal = minVal

                        if getParamWithBlockLevelMax(a, minParam) < realMinVal:
                            # this assembly does not meet the minVal specifications. Skip it.
                            innocent = False
                            break  # for speed (not a big deal here)

                if not innocent:
                    continue

                # Check upper bounds, to make sure this assembly doesn't have maxParams>maxVals
                for maxIndex, maxVal in enumerate(maxVals):
                    maxParam = maxParams[maxIndex]
                    if maxParam:
                        if isinstance(maxVal, tuple):
                            # tuple turned in. it's a multiplier and a param
                            realMaxVal = (
                                getParamWithBlockLevelMax(a, maxVal[0]) * maxVal[1]
                            )
                        else:
                            realMaxVal = maxVal

                        if getParamWithBlockLevelMax(a, maxParam) > realMaxVal:
                            # this assembly has a maxParam that's higher than maxVal and therefore
                            # doesn't qualify. skip it.
                            innocent = False
                            break

                if not innocent:
                    continue

                # Check to see if this assembly is in the list of candidate locations. if not, skip it.
                if mandatoryLocations:
                    if a.getLocation() not in mandatoryLocations:
                        continue

                if excludedLocations:
                    if a.getLocation() in excludedLocations:
                        # this assembly is in the excluded location list. skip it.
                        continue

                if zoneList:
                    found = False  # guilty until proven innocent
                    for zone in zoneList:
                        if a.getLocation() in zone:
                            # great! it's in there, so we'll accept this assembly
                            found = True  # innocent
                            break
                    if not found:
                        # this assembly is not in any of the zones in the zone list. skip it.
                        continue

                # Now find the assembly with the param closest to the target val.
                if param:
                    diff = abs(getParamWithBlockLevelMax(a, param) - compVal)

                    if (
                        forceSide == 1
                        and getParamWithBlockLevelMax(a, param) > compVal
                        and compareAssem((diff, a), minDiff)
                    ):
                        # forceSide=1, so that means look in rings further out
                        minDiff = (diff, a)
                    elif (
                        forceSide == -1
                        and getParamWithBlockLevelMax(a, param) < compVal
                        and compareAssem((diff, a), minDiff)
                    ):
                        # forceSide=-1, so that means look in rings closer in from the targetRing
                        minDiff = (diff, a)
                    elif compareAssem((diff, a), minDiff):
                        # no preference of which side, just take the one with the closest param.
                        minDiff = (diff, a)
                else:
                    # no param specified. Just return one closest to the target ring
                    diff = None
                    if a.spatialLocator.getRingPos()[0] == targetRing:
                        # short circuit the search
                        if findMany:
                            assemList.append((diff, a))
                            continue
                        else:
                            return a
                    elif (
                        abs(a.spatialLocator.getRingPos()[0] - targetRing) < minDiff[0]
                    ):
                        minDiff = (
                            abs(a.spatialLocator.getRingPos()[0] - targetRing),
                            a,
                        )

                if findMany:
                    # returning many assemblies. If there's a param, we'd like it to be honored by
                    # ordering this list from smallest diff to largest diff.
                    assemList.append((diff, a))

            if ringI == 0 and acceptFirstCandidateRing and minDiff[1]:
                # an acceptable assembly was found in the targetRing (ringI==0)
                # and the user requested this to be returned. Therefore, return it without
                # scanning through the additional rings.
                return minDiff[1]

        if not minDiff[1]:
            # warning("can't find assembly in targetRing %d with close %s to %s" % (targetRing,param,compareTo),'findAssembly')
            pass

        if findMany:
            assemList.sort()  # prefer items that have params that are the closest to the value.
            # extract the assemblies.
            assemsInRings = [a for diff, a in assemList]
            if maxNumAssems:
                return assemsInRings[:maxNumAssems]
            else:
                return assemsInRings
        else:
            return minDiff[1]

    def _getAssembliesInRings(
        self,
        ringList,
        typeSpec=Flags.FUEL,
        exactType=False,
        exclusions=None,
        circularRingFlag=False,
    ):
        r"""
        find assemblies in particular rings

        Parameters
        ----------
        ringList : list
            List of integer ring numbers to find assemblies in. Optionally, a string specifiying a
            special location like the SFP (spent fuel pool)

        typeSpec : Flags or iterable of Flags, optional
            Flag types to restrict assemblies to

        exactType : bool, optional
            Match the type in typelist exactly

        exclusions : list of Assemblies, optional
            exclude these assemblies from the results

        circularRingFlag : bool
            A flag to toggle on using rings that are based on distance from the center of the reactor

        Returns
        -------
        assemblyList : list
            List of assemblies in each ring of the ringList. [[a1,a2,a3],[a4,a5,a6,a7],...]

        """
        assemblyList = [[] for _i in range(len(ringList))]  # empty lists for each ring
        if exclusions is None:
            exclusions = []
        exclusions = set(exclusions)

        if circularRingFlag:
            assemListTmp = []
            assemListTmp2 = []
            if ringList[0] == "SFP":
                # kind of a hack for now. Need the capability.
                assemblyList = self.r.core.sfp.getChildren()
            else:
                for i, ringNumber in enumerate(ringList):
                    assemListTmp = self.r.core.getAssembliesInCircularRing(
                        ringNumber, typeSpec, exactType, exclusions
                    )
                    for a in assemListTmp:
                        if a in exclusions:
                            continue
                        if not a.hasFlags(typeSpec, exact=exactType):
                            continue
                        # save only the assemblies not in the exclusions and with the proper type
                        assemListTmp2.append(a)
                    # make the list of lists of assemblies
                    assemblyList[i] = assemListTmp2

        else:

            if ringList[0] == "SFP":
                # kind of a hack for now. Need the capability.
                assemList = self.r.core.sfp.getChildren()
            else:
                assemList = self.r.core.getAssemblies()

            for a in assemList:
                if a in exclusions:
                    continue
                if not a.hasFlags(typeSpec, exact=exactType):
                    continue

                if a.getLocation() == "SFP":
                    ring = "SFP"
                else:
                    ring = a.spatialLocator.getRingPos()[0]
                if ring in ringList:
                    # keep it in the right order
                    assemblyList[ringList.index(ring)].append(a)

        return assemblyList

    def swapAssemblies(self, a1, a2):
        r"""
        Moves a whole assembly from one place to another

        Parameters
        ----------
        a1 : Assembly
            The first assembly
        a2 : Assembly
            The second assembly

        See Also
        --------
        dischargeSwap : swap assemblies where one is outside the core and the other is inside
        """
        if a1 is None or a2 is None:
            runLog.warning(
                "Cannot swap None assemblies. Check your findAssembly results. Skipping swap"
            )
            return

        runLog.extra("Swapping {} with {}.".format(a1, a2))
        # add assemblies into the moved location
        for a in [a1, a2]:
            if a not in self.moved:
                self.moved.append(a)
        oldA1Location = a1.spatialLocator
        oldA2Location = a2.spatialLocator
        a1StationaryBlocks, a2StationaryBlocks = self._transferStationaryBlocks(a1, a2)
        a1.moveTo(oldA2Location)
        a2.moveTo(oldA1Location)

        self._validateAssemblySwap(
            a1StationaryBlocks, oldA1Location, a2StationaryBlocks, oldA2Location
        )

    def rotateAssembly(self, assembly, rotNum):
        assembly.rotatePins(rotNum)
        if assembly not in self.moved:
            self.moved.append(assembly)

    def _validateAssemblySwap(
        self, a1StationaryBlocks, oldA1Location, a2StationaryBlocks, oldA2Location
    ):
        """
        Detect whether any blocks containing stationary components were moved
        after a swap.
        """
        for assemblyBlocks, oldLocation in [
            [a1StationaryBlocks, oldA1Location],
            [a2StationaryBlocks, oldA2Location],
        ]:
            for block in assemblyBlocks:
                if block.parent.spatialLocator != oldLocation:
                    raise ValueError(
                        """Stationary block {} has been moved. Expected to be in location {}. Was moved to {}.""".format(
                            block, oldLocation, block.parent.spatialLocator
                        )
                    )

    def _transferStationaryBlocks(self, assembly1, assembly2):
        """
        Exchange the stationary blocks (e.g. grid plate) between the moving assemblies.

        These blocks in effect are not moved at all.
        """
        # grab stationary block flags
        sBFList = self.r.core.stationaryBlockFlagsList

        # identify stationary blocks for assembly 1
        a1StationaryBlocks = [
            [block, block.spatialLocator.k]
            for block in assembly1
            if any(block.hasFlags(sbf) for sbf in sBFList)
        ]
        # identify stationary blocks for assembly 2
        a2StationaryBlocks = [
            [block, block.spatialLocator.k]
            for block in assembly2
            if any(block.hasFlags(sbf) for sbf in sBFList)
        ]

        # check for any inconsistencies in stationary blocks and ensure alignment
        if [block[1] for block in a1StationaryBlocks] != [
            block[1] for block in a2StationaryBlocks
        ]:
            raise ValueError(
                """Different number and/or locations of stationary blocks 
                 between {} (Stationary Blocks: {}) and {} (Stationary Blocks: {}).""".format(
                    assembly1, a1StationaryBlocks, assembly2, a2StationaryBlocks
                )
            )

        # swap stationary blocks
        for (assem1Block, assem1BlockIndex), (assem2Block, assem2BlockIndex) in zip(
            a1StationaryBlocks, a2StationaryBlocks
        ):
            # remove stationary blocks
            assembly1.remove(assem1Block)
            assembly2.remove(assem2Block)
            # insert stationary blocks
            assembly1.insert(assem1BlockIndex, assem2Block)
            assembly2.insert(assem2BlockIndex, assem1Block)

        return [item[0] for item in a1StationaryBlocks], [
            item[0] for item in a2StationaryBlocks
        ]

        return [item[0] for item in a1StationaryBlocks], [
            item[0] for item in a2StationaryBlocks
        ]

    def dischargeSwap(self, incoming, outgoing):
        r"""
        Removes one assembly from the core and replace it with another assembly.

        See Also
        --------
        swapAssemblies : swaps assemblies that are already in the core
        """
        runLog.debug("Discharge swapping {} for {}.".format(incoming, outgoing))
        if incoming is None or outgoing is None:
            runLog.warning(
                "Cannot discharge swap None assemblies. Check your findAssembly calls. Skipping"
            )
            return

        # add assemblies into the moved location
        # keep it unique so we don't get artificially inflated numMoves
        for a in [incoming, outgoing]:
            if a not in self.moved:
                self.moved.append(a)

        self._transferStationaryBlocks(incoming, outgoing)

        # replace the goingOut guy.
        loc = outgoing.spatialLocator
        # say it happened at the end of the previous cycle by sending cycle-1
        # to removeAssembly, which will look up EOC of last cycle,
        # which, coincidentally is the same time we're at right now at BOC.
        self.r.core.removeAssembly(outgoing)

        # adjust the assembly multiplicity so that it doesnt forget how many it really
        # represents. This allows us to discharge an assembly from any location in
        # fractional-core models where the central location may only be one assembly,
        # whereas other locations are more, and keep proper track of things. In the
        # future, this mechanism may be used to handle symmetry in general.
        outgoing.p.multiplicity = len(loc.getSymmetricEquivalents()) + 1

        if incoming in self.r.core.sfp.getChildren():
            # pull it out of the sfp if it's in there.
            runLog.extra("removing {0} from the sfp".format(incoming))
            self.r.core.sfp.remove(incoming)

        incoming.p.multiplicity = 1
        self.r.core.add(incoming, loc)

    def swapCascade(self, cascInput):
        """
        This function performs a cascade of swaps on a list of assemblies.

        Notes
        -----
        Assemblies are moved from their original location to that of the assembly ahead of them
        or, in ASCII art::

             >---------------v
             |               |
            [A  <- B <- C <- D]

        """
        # Determine if input is shuffle data structure or single cascade
        if issubclass(type(cascInput), shuffleStructure.shuffleDataStructure):
            cascInput.checkTranslations()

        else:
            raise ValueError(
                "Translations were not provided in the correct format.\n"
                "Provide translations as shuffleStructure Class."
            )

        # Run cascade swaps
        for assemList in cascInput.translations:
            levels = len(assemList)
            for level in range(levels - 1):
                if not assemList[level + 1]:
                    # If None element is in the cascade it will be skipped.
                    runLog.extra(
                        "Skipping level %d in the cascade because it is None"
                        % (level + 1)
                    )
                    continue
                if (
                    assemList[level + 1].getLocation() == "LoadQueue"
                    or assemList[level + 1].getLocation() == "SFP"
                ):
                    self.dischargeSwap(assemList[level + 1], assemList[0])
                elif assemList[0].getLocation() == "SFP":
                    self.dischargeSwap(assemList[0], assemList[level + 1])
                else:
                    self.swapAssemblies(assemList[0], assemList[level + 1])

    def workerOperate(self, cmd):
        """Handle a mpi command on the worker nodes."""
        pass

    def _prepShuffleMap(self):
        """Prepare a table of current locations for plotting shuffle maneuvers."""
        self.oldLocations = {}
        for a in self.r.core.getAssemblies():
            self.oldLocations[a.getName()] = a.spatialLocator.getGlobalCoordinates()

    def makeShuffleArrows(self):
        r"""
        This function returns data for plotting all the precious shuffles as arrows

        Returns
        -------
        arrows : list
            Values are (currentCoords, oldCoords) tuples

        """
        arrows = []
        runLog.extra("Building list of shuffle arrows.")
        for a in self.r.core.getAssemblies():
            currentCoords = a.spatialLocator.getGlobalCoordinates()
            oldCoords = self.oldLocations.get(a.getName(), None)
            if oldCoords is None:
                oldCoords = numpy.array((-50, -50, 0))
            elif any(currentCoords != oldCoords):
                arrows.append((oldCoords, currentCoords))
        return arrows
