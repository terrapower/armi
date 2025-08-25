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
This module handles fuel management operations such as shuffling, rotation, and
fuel processing (in fluid systems).

The :py:class:`FuelHandlerInterface` instantiates a ``FuelHandler``, which is typically a user-defined
subclass the :py:class:`FuelHandler` object in custom shuffle-logic input files.
Users point to the code modules with their custom fuel handlers using the
``shuffleLogic`` and ``fuelHandlerName`` settings, as described in :ref:`fuel-management-input`.
These subclasses override ``chooseSwaps`` that determine
the particular shuffling of a case.

This module also handles repeat shuffles when doing a restart.
"""

# ruff: noqa: F401
import inspect
import math
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError

from armi import runLog
from armi.physics.fuelCycle import assemblyRotationAlgorithms as rotAlgos
from armi.physics.fuelCycle.fuelHandlerFactory import fuelHandlerFactory
from armi.physics.fuelCycle.fuelHandlerInterface import FuelHandlerInterface
from armi.physics.fuelCycle.settings import (
    CONF_ASSEMBLY_ROTATION_ALG,
    CONF_SHUFFLE_SEQUENCE_FILE,
)
from armi.reactor import grids
from armi.reactor.flags import Flags
from armi.reactor.parameters import ParamLocation
from armi.utils.customExceptions import InputError


@dataclass(eq=True)
class AssemblyMove:
    """Description of an individual shuffle move.

    Parameters
    ----------
    fromLoc : str
        Original location label.
    toLoc : str
        Destination location label.
    enrichList : list[float]
        Axial U235 weight percent enrichment values for each block.
    assemType : str, optional
        Type of assembly that is moving.
    nameAtDischarge : str, optional
        Name of the assembly moving (for SFP/ExCore interactions).
    rotation : float, optional
        Degrees of manual rotation to apply after shuffling.
    """

    fromLoc: str
    toLoc: str
    enrichList: List[float] = field(default_factory=list)
    assemType: Optional[str] = None
    nameAtDischarge: Optional[str] = None
    rotation: Optional[float] = None


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

    DISCHARGE_LOCS = frozenset({"SFP", "ExCore"})
    """Special strings to indicate an assembly is no longer in the core."""

    def __init__(self, operator):
        # we need access to the operator to find the core, get settings, grab other interfaces, etc.
        self.o = operator
        self.moved = []
        self.pendingRotations = []

    @property
    def cycle(self):
        """
        Link to the current cycle number.

        Notes
        -----
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

    def outage(self, factor=1.0):
        """
        Simulates a reactor reload outage. Moves and tracks fuel.

        This sets the moveList structure.
        """
        if self.moved:
            raise ValueError("Cannot perform two outages with same FuelHandler instance.")

        # determine if a repeat shuffle is occurring or a new shuffle pattern
        if self.cs[CONF_SHUFFLE_SEQUENCE_FILE]:
            if not os.path.exists(self.cs[CONF_SHUFFLE_SEQUENCE_FILE]):
                raise FileNotFoundError(
                    "Requested shuffle sequence file {0} does not exist. Cannot perform shuffling. ".format(
                        self.cs[CONF_SHUFFLE_SEQUENCE_FILE]
                    )
                )
            runLog.important("Applying shuffle sequence from {}".format(self.cs[CONF_SHUFFLE_SEQUENCE_FILE]))
            self.performShuffle(self.cs[CONF_SHUFFLE_SEQUENCE_FILE], yaml=True)
        elif self.cs["explicitRepeatShuffles"]:
            # repeated shuffle
            if not os.path.exists(self.cs["explicitRepeatShuffles"]):
                raise RuntimeError(
                    "Requested repeat shuffle file {0} does not exist. Cannot perform shuffling. ".format(
                        self.cs["explicitRepeatShuffles"]
                    )
                )
            runLog.important("Repeating a shuffling pattern from {}".format(self.cs["explicitRepeatShuffles"]))
            self.performShuffle(self.cs["explicitRepeatShuffles"])
        else:
            # Normal shuffle from user-provided shuffle logic input
            self.chooseSwaps(factor)

        # do rotations if pin-level details are available (requires fluxRecon plugin)
        if self.cs["fluxRecon"] and self.cs[CONF_ASSEMBLY_ROTATION_ALG]:
            # Rotate assemblies ONLY IF at least some assemblies have pin detail
            # The user can choose the algorithm method name directly in the settings
            if hasattr(rotAlgos, self.cs[CONF_ASSEMBLY_ROTATION_ALG]):
                rotationMethod = getattr(rotAlgos, self.cs[CONF_ASSEMBLY_ROTATION_ALG])
                rotationMethod(self)
            else:
                raise RuntimeError(
                    "FuelHandler {0} does not have a rotation algorithm called {1}.\nChange your {2} setting".format(
                        rotAlgos,
                        self.cs[CONF_ASSEMBLY_ROTATION_ALG],
                        CONF_ASSEMBLY_ROTATION_ALG,
                    )
                )

        for loc, deg in self.pendingRotations:
            assem = self.r.core.getAssemblyWithStringLocation(loc)
            if assem is None:
                runLog.warning(f"No assembly found at {loc} for manual rotation")
                continue
            runLog.important(f"Rotating assembly {assem} in {loc} by {deg} degrees CCW from shuffle file")
            assem.rotate(math.radians(deg))
        self.pendingRotations = []

        # inform the reactor of how many moves occurred so it can put the number in the database.
        if self.moved:
            numMoved = len(self.moved) * self.r.core.powerMultiplier

            # tell the reactor which assemblies moved where
            # also tell enrichments of each block in case there's some autoboosting going on.
            # This is also essential for repeating shuffles in later restart runs.
            for a in self.moved:
                try:
                    self.r.core.setMoveList(
                        self.cycle,
                        a.lastLocationLabel,
                        a.getLocation(),
                        [b.getUraniumMassEnrich() for b in a],
                        a.getType(),
                        a.getName(),
                    )
                except:
                    runLog.important("A fuel management error has occurred. ")
                    runLog.important("Trying operation on assembly {}".format(a))
                    runLog.important("The moved list is {}".format(self.moved))
                    raise
        else:
            numMoved = 0

        self.o.r.core.p.numMoves = numMoved
        self.o.r.core.setBlockMassParams()

        runLog.important("Fuel handler performed {0} assembly shuffles.".format(numMoved))

        # now wipe out the self.moved version so it doesn't transmit the assemblies during distributeState
        moved = self.moved[:]
        self.moved = []
        return moved

    def chooseSwaps(self, shuffleFactors=None):
        """Moves the fuel around or otherwise processes it between cycles."""
        raise NotImplementedError

    @staticmethod
    def getFactorList(cycle, cs=None, fallBack=False):
        """
        Return factors between 0 and 1 that control fuel management.

        This is the default shuffle control function. Usually you would override this
        with your own in a custom shuffleLogic.py file. For more details about how this
        works, refer to :ref:`fuel-management-input`.

        This will get bound to the default FuelHandler as a static method below. This is
        done to allow a user to mix and match FuelHandler class implementations and
        getFactorList implementations at run time.

        Notes
        -----
        Ultimately, this approach will likely get replaced using the plugin framework, but
        we aren't there yet.
        """
        # prefer to keep these 0 through 1 since this is what the branch search can do.
        defaultFactorList = {"eqShuffles": 1}
        factorSearchFlags = []
        return defaultFactorList, factorSearchFlags

    def prepCore(self):
        """Aux function to run before XS generation (do moderation, etc)."""
        pass

    @staticmethod
    def _compareAssem(candidate, current):
        """Check whether the candidate assembly should replace the current ideal assembly.

        Given a candidate tuple (diff1, a1) and current tuple (diff2, a2), decide whether the
        candidate is better than the current ideal. This first compares the diff1 and diff2 values.
        If diff1 is sufficiently less than diff2, a1 wins, returning True. Otherwise, False. If
        diff1 and diff2 are sufficiently close, the assembly with the lesser assemNum wins. This
        should result in a more stable comparison than on floating-point comparisons alone.
        """
        if np.isclose(candidate[0], current[0], rtol=1e-8, atol=1e-8):
            return candidate[1].p.assemNum < current[1].p.assemNum
        else:
            return candidate[0] < current[0]

    @staticmethod
    def _getParamMax(a, paramName, blockLevelMax=True):
        """Get assembly/block-level maximum parameter value in assembly."""
        multiplier = a.getSymmetryFactor()
        if multiplier != 1:
            # handle special case: volume-integrated parameters where symmetry factor is not 1
            if blockLevelMax:
                paramCollection = a[0].p
            else:
                paramCollection = a.p
            isVolumeIntegrated = paramCollection.paramDefs[paramName].location == ParamLocation.VOLUME_INTEGRATED
            multiplier = a.getSymmetryFactor() if isVolumeIntegrated else 1.0

        if blockLevelMax:
            return a.getChildParamValues(paramName).max() * multiplier
        else:
            return a.p[paramName] * multiplier

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
            multiplier) tuple the code will still work as expected.

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
            If list, must correspond to parameters in maxVal in order.

        minVal : float or list, optional
            a value or a (parameter, multiplier) tuple for setting lower bounds

            For instance, if minParam='timeToLimit' and minVal=10, only assemblies with timeToLimit
            higher than 10 will be returned. (Of course, there is also maxParam and maxVal)

        maxVal : float or list, optional
            a value or a (parameter, multiplier) tuple for setting upper bounds

        mandatoryLocations : list, optional
            A list of string-representations of locations in the core for limiting the search to
            several places. Any locations also included in `excludedLocations` will be excluded.

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
            If true, will look in the spent-fuel pool instead of in the core.

        maxNumAssems : int, optional
            The maximum number of assemblies to return. Only relevant if findMany==True

        circularRingFlag : bool, optional
            Toggle using rings that are based on distance from the center of the reactor

        Notes
        -----
        The call signature on this method may have gotten slightly out of hand as valuable
        capabilities were added in fuel management studies. For additional expansion, it may be
        worth reconsidering the design of these query operations.

        Returns
        -------
        Assembly instance or assemList of assembly instances that match criteria, or None if none
        match

        Examples
        --------
        This returns the feed fuel assembly in ring 4 that has a burnup closest to 100%
        (the highest burnup assembly)::

            feed = self.findAssembly(targetRing=4,
                                     width=(0,0),
                                     param='maxPercentBu',
                                     compareTo=100,
                                     typeSpec=Flags.FEED | Flags.FUEL)

        """
        # list for storing multiple results if findMany is true.
        assemList = []

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

        if isinstance(compareTo, (float, int)):
            # floating point or int.
            compVal = compareTo * mult
        elif param:
            # assume compareTo is an assembly
            compVal = FuelHandler._getParamMax(compareTo, param, blockLevelMax) * mult

        if coords:
            # find the assembly closest to xt,yt if coords are given without considering params.
            aTarg = None
            minD = 1e10
            xt, yt = coords  # assume (x,y) tuple
            for a in self.r.core:
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
                    candidateRings.append(targetRing - inner - 1)  # +1 to get 1,2,3 instead of 0,1,2
            if width[1] >= 0:
                # if 1, add in the outer rings
                for outer in range(width[0]):
                    candidateRings.append(targetRing + outer + 1)

        # get lists of assemblies in each candidate ring. Do it in this order in case we prefer ones in the first.
        # scan through all assemblies and find the one (or more) that best fits the criteria
        for ringI, assemsInRings in enumerate(
            self._getAssembliesInRings(candidateRings, typeSpec, exactType, exclusions, circularRingFlag)
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
                            realMinVal = FuelHandler._getParamMax(a, minVal[0], blockLevelMax) * minVal[1]
                        else:
                            realMinVal = minVal

                        if FuelHandler._getParamMax(a, minParam, blockLevelMax) < realMinVal:
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
                            realMaxVal = FuelHandler._getParamMax(a, maxVal[0], blockLevelMax) * maxVal[1]
                        else:
                            realMaxVal = maxVal

                        if FuelHandler._getParamMax(a, maxParam, blockLevelMax) > realMaxVal:
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

                # only process of the Assembly is in a Zone
                if not self.isAssemblyInAZone(zoneList, a):
                    continue

                # Now find the assembly with the param closest to the target val.
                if param:
                    diff = abs(FuelHandler._getParamMax(a, param, blockLevelMax) - compVal)

                    if (
                        forceSide == 1
                        and FuelHandler._getParamMax(a, param, blockLevelMax) > compVal
                        and FuelHandler._compareAssem((diff, a), minDiff)
                    ):
                        # forceSide=1, so that means look in rings further out
                        minDiff = (diff, a)
                    elif (
                        forceSide == -1
                        and FuelHandler._getParamMax(a, param, blockLevelMax) < compVal
                        and FuelHandler._compareAssem((diff, a), minDiff)
                    ):
                        # forceSide=-1, so that means look in rings closer in from the targetRing
                        minDiff = (diff, a)
                    elif FuelHandler._compareAssem((diff, a), minDiff):
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
                    elif abs(a.spatialLocator.getRingPos()[0] - targetRing) < minDiff[0]:
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
            # can't find assembly in targetRing with close param to compareTo
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

    @staticmethod
    def isAssemblyInAZone(zoneList, a):
        """Does the given assembly in one of these zones."""
        if zoneList:
            # ruff: noqa: SIM110
            for zone in zoneList:
                if a.getLocation() in zone:
                    # Success!
                    return True

            return False
        else:
            # A little counter-intuitively, if there are no zones, we return True.
            return True

    def _getAssembliesInRings(
        self,
        ringList,
        typeSpec=Flags.FUEL,
        exactType=False,
        exclusions=None,
        circularRingFlag=False,
    ):
        """
        Find assemblies in particular rings.

        Parameters
        ----------
        ringList : list
            List of integer ring numbers to find assemblies in. Optionally, a string specifying a
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
        if "SFP" in ringList and self.r.excore.get("sfp") is None:
            sfpAssems = []
            runLog.warning(
                f"{self} can't pull from SFP; no SFP is attached to the reactor {self.r}."
                "To get assemblies from an SFP, you must add an SFP system to the blueprints"
                f"or otherwise instantiate a SpentFuelPool object as r.excore['sfp']"
            )
        else:
            sfpAssems = list(self.r.excore["sfp"])

        assemblyList = [[] for _i in range(len(ringList))]  # empty lists for each ring
        if exclusions is None:
            exclusions = []
        exclusions = set(exclusions)

        if circularRingFlag:
            assemListTmp = []
            assemListTmp2 = []
            if ringList[0] == "SFP":
                # kind of a hack for now. Need the capability.
                assemblyList = sfpAssems
            else:
                for i, ringNumber in enumerate(ringList):
                    assemListTmp = self.r.core.getAssembliesInCircularRing(ringNumber, typeSpec, exactType, exclusions)
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
                assemList = sfpAssems
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
        """Moves a whole assembly from one place to another.

        .. impl:: User-specified blocks can be left in place during within-core swaps.
            :id: I_ARMI_SHUFFLE_STATIONARY0
            :implements: R_ARMI_SHUFFLE_STATIONARY

            Before assemblies are moved, the ``_transferStationaryBlocks`` class method is called to
            check if there are any block types specified by the user as stationary via the
            ``stationaryBlockFlags`` case setting. Using these flags, blocks are gathered from each
            assembly which should remain stationary and checked to make sure that both assemblies
            have the same number and same height of stationary blocks. If not, return an error.

            If all checks pass, the :py:meth:`~armi.reactor.assemblies.Assembly.remove` and
            :py:meth:`~armi.reactor.assemblies.Assembly.insert` methods are used to swap the
            stationary blocks between the two assemblies.

            Once this process is complete, the actual assembly movement can take place. Through this
            process, the stationary blocks remain in the same core location.

        Parameters
        ----------
        a1 : :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
            The first assembly
        a2 : :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
            The second assembly

        See Also
        --------
        dischargeSwap : swap assemblies where one is outside the core and the other is inside
        """
        if a1 is None or a2 is None:
            runLog.warning("Cannot swap None assemblies. Check your findAssembly results. Skipping swap")
            return

        runLog.extra("Swapping {} with {}.".format(a1, a2))
        # add assemblies into the moved location
        for a in [a1, a2]:
            if a not in self.moved:
                self.moved.append(a)
        oldA1Location = a1.spatialLocator
        self._transferStationaryBlocks(a1, a2)
        a1.moveTo(a2.spatialLocator)
        a2.moveTo(oldA1Location)

    def _transferStationaryBlocks(self, assembly1, assembly2):
        """
        Exchange the stationary blocks (e.g. grid plate) between the moving assemblies.

        These blocks in effect are not moved at all.
        """
        # grab stationary block flags
        sBFList = self.r.core.stationaryBlockFlagsList

        # identify stationary blocks for assembly 1
        a1StationaryBlocks = [
            [block, block.spatialLocator.k] for block in assembly1 if any(block.hasFlags(sbf) for sbf in sBFList)
        ]
        # identify stationary blocks for assembly 2
        a2StationaryBlocks = [
            [block, block.spatialLocator.k] for block in assembly2 if any(block.hasFlags(sbf) for sbf in sBFList)
        ]

        # check for any inconsistencies in stationary blocks and ensure alignment
        if [block[1] for block in a1StationaryBlocks] != [block[1] for block in a2StationaryBlocks]:
            raise ValueError(
                """Different number and/or locations of stationary blocks 
                 between {} (Stationary Blocks: {}) and {} (Stationary Blocks: {}).""".format(
                    assembly1, a1StationaryBlocks, assembly2, a2StationaryBlocks
                )
            )
        if a1StationaryBlocks and a2StationaryBlocks:
            if a1StationaryBlocks[-1][0].p.ztop != a2StationaryBlocks[-1][0].p.ztop:
                runLog.warning(
                    """Difference in top elevation of stationary blocks 
                     between {} (Stationary Blocks: {}, Elevation at top of stationary blocks {}) 
                     and {} (Stationary Blocks: {}, Elevation at top of stationary blocks {}))""".format(
                        assembly1,
                        a1StationaryBlocks,
                        a1StationaryBlocks[-1][0].p.ztop,
                        assembly2,
                        a2StationaryBlocks,
                        a2StationaryBlocks[-1][0].p.ztop,
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

    @staticmethod
    def _validateLoc(loc, cycle):
        """Validate a location label from a shuffle YAML file.

        Parameters
        ----------
        loc : str
            Location label to validate.
        cycle : int
            Cycle currently being processed, used for context in error messages.
        """
        if loc in FuelHandler.DISCHARGE_LOCS:
            return

        try:
            grids.locatorLabelToIndices(loc)
        except Exception:
            raise InputError(
                f"Invalid location label {loc!r} in cycle {cycle} in shuffle YAML. "
                "Location labels must be non-empty and contain integers."
            )

    def dischargeSwap(self, incoming, outgoing):
        """Removes one assembly from the core and replace it with another assembly.

        .. impl:: User-specified blocks can be left in place for the discharge swap.
            :id: I_ARMI_SHUFFLE_STATIONARY1
            :implements: R_ARMI_SHUFFLE_STATIONARY

            Before assemblies are moved, the ``_transferStationaryBlocks`` class method is called to
            check if there are any block types specified by the user as stationary via the
            ``stationaryBlockFlags`` case setting. Using these flags, blocks are gathered from each
            assembly which should remain stationary and checked to make sure that both assemblies
            have the same number and same height of stationary blocks. If not, return an error.

            If all checks pass, the :py:meth:`~armi.reactor.assemblies.Assembly.remove` and
            :py:meth:`~armi.reactor.assemblies.Assembly.insert` methods are used to swap the
            stationary blocks between the two assemblies.

            Once this process is complete, the actual assembly movement can take place. Through this
            process, the stationary blocks from the outgoing assembly remain in the original core
            position, while the stationary blocks from the incoming assembly are discharged with the
            outgoing assembly.

        Parameters
        ----------
        incoming : :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
            The assembly getting swapped into the core.
        outgoing : :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
            The assembly getting discharged out the core.

        See Also
        --------
        swapAssemblies : swaps assemblies that are already in the core
        """
        runLog.debug("Discharge swapping {} for {}.".format(incoming, outgoing))
        if incoming is None or outgoing is None:
            runLog.warning("Cannot discharge swap None assemblies. Check your findAssembly calls. Skipping")
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

        # adjust the assembly multiplicity so that it does not forget how many it really
        # represents. This allows us to discharge an assembly from any location in
        # fractional-core models where the central location may only be one assembly,
        # whereas other locations are more, and keep proper track of things. In the
        # future, this mechanism may be used to handle symmetry in general.
        outgoing.p.multiplicity = len(loc.getSymmetricEquivalents()) + 1

        if self.r.excore.get("sfp") is not None:
            if incoming in self.r.excore["sfp"].getChildren():
                # pull it out of the sfp if it's in there.
                runLog.extra("removing {0} from the sfp".format(incoming))
                self.r.excore["sfp"].remove(incoming)

        incoming.p.multiplicity = 1
        self.r.core.add(incoming, loc)

    def swapCascade(self, assemList):
        """
        Perform swaps on a list of assemblies.

        Parameters
        ----------
        assemList: list
            A list of assemblies to be shuffled.

        Notes
        -----
        [goingOut,inter1,inter2,goingIn]  will go to
        [inter1, inter2, goingIn, goingOut] in terms of positions
        or, in ASCII art::

             >---------------v
             |               |
            [A  <- B <- C <- D]

        """
        # first check for duplicates
        for assem in assemList:
            if assemList.count(assem) != 1:
                runLog.warning(f"{assem} is in the cascade more than once.")

        # now swap
        levels = len(assemList)
        for level in range(levels - 1):
            if not assemList[level + 1]:
                runLog.info(
                    f"Skipping level {level + 1} in the cascade because it is None. Be careful, "
                    "this might cause an unexpected shuffling order."
                )
                continue
            self.swapAssemblies(assemList[0], assemList[level + 1])

    def performShuffle(self, shuffleFile, yaml=False):
        """
        Execute shuffling instructions from a previous run or YAML file.

        Parameters
        ----------
        shuffleFile : str
            Path to the shuffle sequence file.
        yaml : bool, optional
            If True, interpret ``shuffleFile`` as a YAML shuffle sequence.

        Returns
        -------
        moved : list
            List of assemblies that moved this cycle.

        Notes
        -----
        Typically the shuffle file from a previous run will be ``caseTitle``-"SHUFFLES.txt".

        See Also
        --------
        doRepeatShuffle : Performs moves as processed by this method
        processMoveList : Converts a stored list of moves into a functional list of assemblies to swap
        makeShuffleReport : Creates the file that is processed here
        """
        # read moves file
        if yaml:
            moves = self.readMovesYaml(shuffleFile)
            cycle = self.r.p.cycle
            if cycle == 0:
                # if cycle is 0, we are at the beginning of the first cycle
                # this is a special case where we don't have any moves
                # so we return an empty list
                return []
        else:
            moves = self.readMoves(shuffleFile)
            # get the correct cycle number
            # +1 since cycles starts on 0 and looking for the end of 1st cycle shuffle
            cycle = self.r.p.cycle + 1

        # setup the load and loop chains to be run per cycle
        moveList = moves[cycle]
        (
            loadChains,
            loopChains,
            enriches,
            loadChargeTypes,
            loadNames,
            rotations,
            _alreadyDone,
        ) = self.processMoveList(moveList)

        # Now have the move locations
        moved = self.doRepeatShuffle(loadChains, loopChains, enriches, loadChargeTypes, loadNames)
        self.pendingRotations = rotations

        return moved

    @staticmethod
    def readMoves(fname):
        r"""
        Reads a shuffle output file and sets up the moves dictionary.

        Parameters
        ----------
        fname : str
            The shuffles file to read

        Returns
        -------
        moves : dict
            A dictionary of all the moves. Keys are the cycle number. Values are a list
            of :class:`~armi.physics.fuelCycle.fuelHandlers.AssemblyMove` objects, one for each individual
            move that happened in the cycle. ``oldLoc`` and ``newLoc`` are string
            representations of the locations and ``enrichList`` is a list of mass
            enrichments from bottom to top.

        See Also
        --------
        performShuffle : reads this file and executes the shuffling
        outage : creates the moveList in the first place.
        makeShuffleReport : writes the file that is read here.
        """
        try:
            f = open(fname)
        except OSError:
            raise RuntimeError(
                "Could not find/open repeat shuffle file {} in working directory {}".format(fname, os.getcwd())
            )

        moves = {}
        numMoves = 0
        for line in f:
            if "ycle" in line:
                # Used to say "Cycle 1 at 0.0 years". Now says: "Before cycle 1 at 0.0 years" to be more specific.
                # This RE allows backwards compatibility.
                # Later, we removed the at x years
                m = re.search(r"ycle (\d+)", line)
                cycle = int(m.group(1))
                moves[cycle] = []
            elif "assembly" in line:
                # this is the new load style where an actual assembly type is written to the shuffle logic
                # due to legacy reasons, the assembly type will be put into group 4
                pat = (
                    r"([A-Za-z0-9!\-]+) moved to ([A-Za-z0-9!\-]+) with assembly type "
                    + r"([A-Za-z0-9!\s]+)\s*(ANAME=\S+)?\s*with enrich list: (.+)"
                )
                m = re.search(pat, line)
                if not m:
                    raise InputError('Failed to parse line "{0}" in shuffle file'.format(line))
                oldLoc = m.group(1)
                newLoc = m.group(2)
                assemType = m.group(3).strip()  # take off any possible trailing whitespace
                nameAtDischarge = m.group(4)  # will be None for legacy shuffleLogic files. (pre 2013-08)
                if nameAtDischarge:
                    nameAtDischarge = nameAtDischarge.split("=")[1]  # extract the actual assembly name.
                enrichList = [float(i) for i in m.group(5).split()]
                moves[cycle].append(AssemblyMove(oldLoc, newLoc, enrichList, assemType, nameAtDischarge))
                numMoves += 1
            elif "moved" in line:
                # very old shuffleLogic file.
                runLog.warning(
                    "Using old *.SHUFFLES.txt loading file",
                    single=True,
                    label="Using old shuffles file",
                )
                m = re.search(
                    "([A-Za-z0-9!]+) moved to ([A-Za-z0-9!]+) with enrich list: (.+)",
                    line,
                )
                if not m:
                    raise InputError('Failed to parse line "{0}" in shuffle file'.format(line))
                oldLoc = m.group(1)
                newLoc = m.group(2)
                enrichList = [float(i) for i in m.group(3).split()]
                # old loading style, just assume that there is a booster as our surrogate
                moves[cycle].append(AssemblyMove(oldLoc, newLoc, enrichList))
                numMoves += 1

        f.close()

        runLog.info("Read {0} moves over {1} cycles".format(numMoves, len(moves.keys())))
        return moves

    @staticmethod
    def readMovesYaml(fname):
        """Read a shuffle file in YAML format."""
        try:
            with open(fname, "r") as stream:
                yaml = YAML(typ="safe")
                data = yaml.load(stream)
        except DuplicateKeyError as e:
            raise InputError(str(e)) from e
        except OSError as ee:
            raise RuntimeError(
                f"Could not find/open repeat shuffle file {fname!r} in working directory {os.getcwd()}: {ee}"
            ) from ee

        if "sequence" not in data:
            raise InputError("Shuffle YAML missing required 'sequence' mapping")

        moves = {}
        # cycles may be provided in any order; verify only that there are no gaps
        cycleNums = {int(c) for c in data["sequence"].keys()}
        if cycleNums:
            expected = set(range(min(cycleNums), max(cycleNums) + 1))
            missing = sorted(expected - cycleNums)
            if missing:
                if len(missing) == 1:
                    raise InputError(f"Missing cycle {missing[0]} in shuffle sequence")
                raise InputError(f"Missing cycles {missing} in shuffle sequence")

        for cycleKey, actions in data["sequence"].items():
            cycle = int(cycleKey)
            moves[cycle] = []
            seenLocs = set()

            if actions is None and cycle != 0:
                runLog.warning(f"Cycle {cycleKey} has no shuffle actions defined, skipping.")
                continue

            elif cycle == 0:
                raise InputError(
                    "Cycle 0 is not allowed in shuffle YAML. "
                    "This cycle is reserved for the initial core loading."
                    "Shuffling is available at the beginning of cycle 1"
                )

            for action in actions:
                allowed = {"cascade", "fuelEnrichment", "extraRotations", "misloadSwap"}
                unknown = set(action) - allowed
                if unknown:
                    raise InputError(f"Unknown action keys {unknown} in shuffle YAML")

                if "cascade" in action:
                    chain = list(action["cascade"])
                    if len(chain) < 2:
                        raise InputError("cascade must contain an assembly type and at least one location")
                    if any(not isinstance(item, str) for item in chain):
                        raise InputError("cascade entries must be strings")

                    assemType = chain[0]
                    locs = chain[1:]
                    for loc in locs:
                        FuelHandler._validateLoc(loc, cycle)
                        if loc not in FuelHandler.DISCHARGE_LOCS and loc in seenLocs:
                            raise InputError(f"Location {loc} appears in multiple cascades in cycle {cycle}")
                        seenLocs.add(loc)

                    enrich = []
                    enrichList = action.get("fuelEnrichment", [])
                    try:
                        enrich = [float(e) for e in enrichList]
                    except (TypeError, ValueError):
                        raise InputError("fuelEnrichment values must be numeric. Got {enrichList}")
                    if any(e < 0 or e > 100 for e in enrich):
                        raise InputError("fuelEnrichment values must be between 0 and 100. Got {enrich}")

                    moves[cycle].append(AssemblyMove("LoadQueue", locs[0], enrich, assemType))
                    for i in range(len(locs) - 1):
                        moves[cycle].append(AssemblyMove(locs[i], locs[i + 1]))
                    if locs[-1] not in FuelHandler.DISCHARGE_LOCS:
                        moves[cycle].append(AssemblyMove(locs[-1], "SFP"))

                elif "misloadSwap" in action:
                    swap = action["misloadSwap"]
                    if not isinstance(swap, list) or len(swap) != 2:
                        raise InputError("misloadSwap must be a list of two location labels, got {swap}")
                    if any(not isinstance(item, str) for item in swap):
                        raise InputError("misloadSwap entries must be strings, got {swap}")
                    for loc in swap:
                        FuelHandler._validateLoc(loc, cycle)
                    loc1, loc2 = swap
                    moves[cycle].append(AssemblyMove(loc1, loc2))

                elif "extraRotations" in action:
                    for loc, angle in action.get("extraRotations", {}).items():
                        FuelHandler._validateLoc(loc, cycle)
                        moves[cycle].append(AssemblyMove(loc, loc, rotation=float(angle)))

                else:
                    raise InputError(f"Unable to process {action} in {cycle}")

        return moves

    @staticmethod
    def trackChain(moveList, startingAt, alreadyDone=None):
        r"""
        Builds a chain of locations based on starting location.

        Notes
        -----
        Takes a moveList and extracts chains. Remembers all it touches.
        If A moved to B, C moved to D, and B moved to C, this returns
        A, B, C ,D.

        Used in some monte carlo physics writers and in performShuffle

        Parameters
        ----------
        moveList : list
            a list of :class:`~armi.physics.fuelCycle.fuelHandlers.AssemblyMove`
            objects that occurred at a single outage.

        startingAt : str
            A location label where the chain would start. This is important because the discharge
            moves are built when the SFP is found in a move. This method must find all
            assemblies in the chain leading up to this particular discharge.

        alreadyDone : list
            A list of locations that have already been tracked.

        Returns
        -------
        chain : list
            The chain as a location list in order
        enrich : list
            The axial enrichment distribution of the load assembly.
        loadName : str
            The assembly name of the load assembly

        See Also
        --------
        performShuffle
        processMoveList
        """
        if alreadyDone is None:
            alreadyDone = []

        enrich = None  # in case this is a load chain, prep for getting enrich.
        loadName = None
        assemType = None  # in case this is a load chain, prep for getting an assembly type

        for move in moveList:
            fromLoc = move.fromLoc
            toLoc = move.toLoc
            if toLoc in FuelHandler.DISCHARGE_LOCS and "LoadQueue" in fromLoc:
                # skip dummy moves
                continue
            elif (fromLoc, toLoc) in alreadyDone:
                # skip this pair
                continue

            elif startingAt in fromLoc:
                # looking for chain involving toLoc
                # back-track the chain of moves
                chain = [fromLoc]
                safeCount = 0  # to break out of crazy loops.
                complete = False
                while (
                    chain[-1] not in ({"LoadQueue"} | FuelHandler.DISCHARGE_LOCS) and not complete and safeCount < 100
                ):
                    # look for something going to where the previous one is from
                    lookingFor = chain[-1]
                    for innerMove in moveList:
                        cFromLoc = innerMove.fromLoc
                        cToLoc = innerMove.toLoc
                        cEnrichList = innerMove.enrichList
                        cAssemblyType = innerMove.assemType
                        cAssemName = innerMove.nameAtDischarge
                        if cToLoc == lookingFor:
                            chain.append(cFromLoc)
                            if cFromLoc in ({"LoadQueue"} | FuelHandler.DISCHARGE_LOCS):
                                # charge-discharge loop complete.
                                enrich = cEnrichList
                                loadName = cAssemName
                                assemType = cAssemblyType
                                # break from here or else we might get the next LoadQueue's enrich.
                                break

                    if chain[-1] == startingAt:
                        # non-charging loop complete
                        complete = True

                    safeCount += 1

                if not safeCount < 100:
                    raise RuntimeError("Chain tracking got too long. Check moves.\n{0}".format(chain))

                # delete the last item, it's loadqueue location or the startingFrom
                # location.
                chain.pop()

                # chain tracked. Can jump out of loop early.
                return chain, enrich, assemType, loadName

        # if we get here, the startingAt location was not found.
        runLog.warning("No chain found starting at {0}".format(startingAt))
        return [], enrich, assemType, loadName

    def processMoveList(self, moveList):
        """
        Processes a move list and extracts fuel management loops and charges.

        Parameters
        ----------
        moveList : list
            A list of :class:`~armi.physics.fuelCycle.fuelHandlers.AssemblyMove` objects describing each
            move.

        Returns
        -------
        loadChains : list
            list of lists of location labels for each load chain (with charge/discharge). These DO NOT include
            special location labels like LoadQueue or SFP
        loopChains : list
            list of lists of location labels for each loop chain (no charge/discharge)
        enriches : list
            The block enrichment distribution of each load assembly
        loadChargeTypes :list
            The types of assemblies that get charged.
        loadNames : list
            The assembly names of assemblies that get brought into the core from the SFP (useful for pulling out
            of SFP for round 2, etc.). Will be None for anything else.
        rotations : list
            Tuples of (location, degrees) indicating manual rotations to perform after shuffling.
        alreadyDone : list
            All the locations that were read.

        Notes
        -----
        Used in some Monte Carlo interfaces to convert ARMI moves to their format moves. Also used in
        repeat shuffling.

        See Also
        --------
        makeShuffleReport : writes the file that is being processed
        performShuffle : uses this to repeat shuffles
        """
        alreadyDone = []
        loadChains = []  # moves that have discharges
        loadChargeTypes = []  # the assembly types (str) to be used in a load chain.
        loopChains = []  # moves that don't have discharges
        enriches = []  # enrichments of each loadChain
        loadNames = []  # assembly name of each load assembly (to read from SFP)
        rotations = []

        # first handle all charge/discharge chains by looking for things going to SFP
        for move in moveList:
            fromLoc = move.fromLoc
            toLoc = move.toLoc
            rot = move.rotation
            if fromLoc == toLoc:
                if rot is not None:
                    rotations.append((fromLoc, rot))
                continue
            if toLoc in self.DISCHARGE_LOCS and "LoadQueue" in fromLoc:
                # skip dummy moves
                continue

            elif toLoc in self.DISCHARGE_LOCS:
                # discharge. Track chain.
                chain, enrichList, assemType, loadAssemName = FuelHandler.trackChain(moveList, startingAt=fromLoc)
                runLog.extra("Load Chain with load assem {0}: {1}".format(assemType, chain))
                loadChains.append(chain)
                enriches.append(enrichList)
                loadChargeTypes.append(assemType)
                loadNames.append(loadAssemName)
                # track all the locations we saw already so we
                # don't use them in the loop moves.
                alreadyDone.extend(chain)

        # go through again, looking for stuff that isn't in chains.
        # put them in loop type 3 moves (arbitrary order)
        for move in moveList:
            fromLoc = move.fromLoc
            toLoc = move.toLoc
            if fromLoc == toLoc:
                # rotation or no-op
                continue
            if toLoc in self.DISCHARGE_LOCS or fromLoc in ({"LoadQueue"} | self.DISCHARGE_LOCS):
                # skip loads/discharges; they're already done.
                continue
            elif fromLoc in alreadyDone:
                # skip repeats
                continue
            else:
                # normal move
                chain, _enrichList, _assemType, _loadAssemName = FuelHandler.trackChain(moveList, startingAt=fromLoc)
                loopChains.append(chain)
                alreadyDone.extend(chain)

                runLog.extra("Loop Chain: {0}".format(chain))

        return loadChains, loopChains, enriches, loadChargeTypes, loadNames, rotations, alreadyDone

    def doRepeatShuffle(self, loadChains, loopChains, enriches, loadChargeTypes, loadNames):
        r"""
        Actually does the fuel movements required to repeat a shuffle order.

        Parameters
        ----------
        loadChains : list
            list of lists of location labels for each load chain (with charge/discharge)
        loopChains : list
            list of lists of location labels for each loop chain (no charge/discharge)
        enriches : list
            The block enrichment distribution of each load assembly
        loadChargeTypes :list
            The types of assemblies that get charged.
        loadNames : list
            The assembly names of assemblies that get brought into the core (useful for pulling out
            of SFP for round 2, etc.)

        See Also
        --------
        performShuffle  : coordinates the moves for this cycle
        processMoveList : builds the input lists

        Notes
        -----
        This is a helper function for performShuffle
        """
        moved = []

        # shuffle all of the load chain assemblies (These include discharges to SFP
        # and loads from Loadqueue)

        # build a lookup table of locations throughout the current core and cache it.
        locContents = self.r.core.makeLocationLookup(assemblyLevel=True)

        # perform load swaps (with charge/discharge)
        for assemblyChain, enrichList, assemblyType, assemblyName in zip(
            loadChains, enriches, loadChargeTypes, loadNames
        ):
            # convert the labels into actual assemblies to be swapped
            assemblyList = self.r.core.getLocationContents(assemblyChain, assemblyLevel=True, locContents=locContents)

            moved.extend(assemblyList)

            # go through and swap the assemblies knowing that there is a discharge (first one)
            # and a new assembly brought it (last one)
            for i in range(0, -(len(assemblyList) - 1), -1):
                self.swapAssemblies(assemblyList[i], assemblyList[i - 1])

            # Now, everything has been set except the first assembly in the list, which must now be
            # replaced with a fresh assembly... but which one? The assemblyType string
            # tells us.
            # Sometimes enrichment is set on-the-fly by branch searches, so we must
            # not only use the proper assembly type but also adjust the enrichment.
            if assemblyName:
                # get this assembly from the SFP
                if self.r.excore.get("sfp") is None:
                    loadAssembly = None
                else:
                    loadAssembly = self.r.excore["sfp"].getAssembly(assemblyName)

                if not loadAssembly:
                    msg = f"The required assembly {assemblyName} is not found in the SFP."
                    runLog.error(msg)
                    raise RuntimeError(msg)
            else:
                # create a new assembly from the BOL assem templates and adjust the enrichment
                loadAssembly = self.r.core.createAssemblyOfType(enrichList=enrichList, assemType=assemblyType)

            # replace the goingOut guy (for continual feed cases)
            runLog.debug("Calling discharge swap with {} and {}".format(loadAssembly, assemblyList[0]))
            self.dischargeSwap(loadAssembly, assemblyList[0])
            moved.append(loadAssembly)

        # shuffle all of the loop chain assemblies (no charge/discharge)

        for assemblyChain in loopChains:
            # convert the labels into actual assemblies to be swapped
            assemblyList = self.r.core.getLocationContents(assemblyChain, assemblyLevel=True, locContents=locContents)

            for a in assemblyList:
                moved.append(a)

            # go through and swap the assemblies knowing that there is a discharge (first one)
            # and a new assembly brought it (last one)
            # for i in range(0,-(len(assemblyList)-1),-1):
            for i in range(0, -(len(assemblyList) - 1), -1):
                self.swapAssemblies(assemblyList[i], assemblyList[i + 1])

        return moved

    def workerOperate(self, cmd):
        """Handle a mpi command on the worker nodes."""
        pass

    def prepShuffleMap(self):
        """Prepare a table of current locations for plotting shuffle maneuvers."""
        self.oldLocations = {}
        for a in self.r.core:
            self.oldLocations[a.getName()] = a.spatialLocator.getGlobalCoordinates()

    def makeShuffleArrows(self):
        """
        Build data for plotting all the previous shuffles as arrows.

        Returns
        -------
        arrows : list
            Values are (currentCoords, oldCoords) tuples
        """
        arrows = []
        runLog.extra("Building list of shuffle arrows.")
        for a in self.r.core:
            currentCoords = a.spatialLocator.getGlobalCoordinates()
            oldCoords = self.oldLocations.get(a.getName(), None)
            if oldCoords is None:
                oldCoords = np.array((-50, -50, 0))
            elif any(currentCoords != oldCoords):
                arrows.append((oldCoords, currentCoords))

        return arrows
