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
``shuffleLogic`` and ``fuelHandlerName`` settings, as described in :doc:`/user/inputs/fuel_management`.
These subclasses override ``chooseSwaps`` that determine
the particular shuffling of a case.

This module also handles repeat shuffles when doing a restart.
"""
import re
import os
import collections
import math
import importlib.util
import warnings

import numpy

import armi
from armi import interfaces
from armi import runLog
from armi.localization.exceptions import InputError
from armi.reactor.flags import Flags
from armi.operators import RunTypes
from armi.utils import directoryChangers, pathTools
from armi import utils


class FuelHandlerInterface(interfaces.Interface):
    """
    Moves and/or processes fuel in a Standard Operator.

    Fuel management traditionally runs at the beginning of a cycle, before
    power or temperatures have been updated. This allows pre-run fuel management
    steps for highly customized fuel loadings. In typical runs, no fuel management
    occurs at the beginning of the first cycle and the as-input state is left as is.
    """

    name = "fuelHandler"

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)
        # assembly name key, (x, y) values. used for making shuffle arrows.
        self.oldLocations = {}
        # need order due to nature of moves but with fast membership tests
        self.moved = collections.OrderedDict([])
        self.cycle = 0
        # filled during summary of EOC time in years of each cycle (time at which shuffling occurs)
        self.cycleTime = {}

    @staticmethod
    def specifyInputs(cs):
        files = [cs[label] for label in ["shuffleLogic", "explicitRepeatShuffles"] if cs[label]]
        return {"fuel management": files}

    def interactBOC(self, cycle=None):
        """
        Move and/or process fuel.

        Also, if requested, first have the lattice physics system update XS.
        """
        # if lattice physics is requested, compute it here instead of after fuel management.
        # This enables XS to exist for branch searching, etc.
        mc2 = self.o.getInterface(function="latticePhysics")
        if mc2 and self.cs["runLatticePhysicsBeforeShuffling"]:
            runLog.extra(
                'Running {0} lattice physics before fuel management due to the "runLatticePhysicsBeforeShuffling"'
                " setting being activated.".format(mc2)
            )
            mc2.interactBOC(cycle=cycle)

        if self.enabled():
            self.manageFuel(cycle)

        self.r.core.p.numAssembliesInSFP = self.r.core.powerMultiplier * len(
            self.r.core.sfp
        )

    def interactEOC(self, cycle=None):
        timeYears = self.r.p.time
        # keep track of the EOC time in years.
        self.cycleTime[cycle] = timeYears
        runLog.extra(
            "There are {} assemblies in the Spent Fuel Pool".format(
                len(self.r.core.sfp)
            )
        )
        runLog.extra(
            "There are {} assemblies in the Fresh Fuel Pool".format(
                len(self.r.core.cfp)
            )
        )

    def interactEOL(self):
        """Make reports at EOL"""
        self.makeShuffleReport()

    def manageFuel(self, cycle):
        """Perform the fuel management for this cycle."""
        fh = fuelHandlerFactory(self.o)
        fh.prepCore()
        fh.prepShuffleMap()
        # take note of where each assembly is located before the outage
        # for mapping after the outage
        self.r.core.locateAllAssemblies()
        cycleDuration = self.r.p.cycleLength
        shuffleFactors, factorSearchFlags = fh.getFactorList(cycle)
        fh.outage(shuffleFactors)  # move the assemblies around
        if self.cs["plotShuffleArrows"]:
            arrows = fh.makeShuffleArrows()
            self.r.core.plotFaceMap(
                "percentBu",
                labelFmt=None,
                fName="{}.shuffles_{}.png".format(self.cs.caseTitle, self.r.p.cycle),
                shuffleArrows=arrows,
            )

    def makeShuffleReport(self):
        """
        Create a data file listing all the shuffles that occurred in a case.

        This can be used to export shuffling to an external code or to
        perform explicit repeat shuffling in a restart.
        It creates a *SHUFFLES.txt file based on the Reactor.moveList structure

        See Also
        --------
        readMoves : reads this file and parses it.

        """
        fname = self.cs.caseTitle + "-SHUFFLES.txt"
        out = open(fname, "w")
        for cycle in range(self.cs["nCycles"]):
            # do cycle+1 because cycle 0 at t=0 isn't usually interesting
            # remember, we put cycle 0 in so we could do BOL branch searches.
            # This also syncs cycles up with external physics kernel cycles.
            out.write("Before cycle {0}:\n".format(cycle + 1))
            movesThisCycle = self.r.core.moveList.get(cycle)
            if movesThisCycle is not None:
                for (
                    fromLoc,
                    toLoc,
                    chargeEnrich,
                    assemblyType,
                    movingAssemName,
                ) in movesThisCycle:
                    enrichLine = " ".join(
                        ["{0:.8f}".format(enrich) for enrich in chargeEnrich]
                    )
                    if fromLoc in ["ExCore", "SFP"]:
                        # this is a re-entering assembly. Give extra info so repeat shuffles can handle it
                        out.write(
                            "{0} moved to {1} with assembly type {2} ANAME={4} with enrich list: {3}\n"
                            "".format(
                                fromLoc,
                                toLoc,
                                assemblyType,
                                enrichLine,
                                movingAssemName,
                            )
                        )
                    else:
                        # skip extra info. regular expression in readMoves will handle it just fine.
                        out.write(
                            "{0} moved to {1} with assembly type {2} with enrich list: {3}\n"
                            "".format(fromLoc, toLoc, assemblyType, enrichLine)
                        )
            out.write("\n")
        out.close()

    def workerOperate(self, cmd):
        """Delegate mpi command to the fuel handler object."""
        fh = fuelHandlerFactory(self.o)
        return fh.workerOperate(cmd)


def fuelHandlerFactory(operator):
    """
    Return an instantiated FuelHandler object based on user settings.

    The FuelHandler is expected to be a short-lived object that only lives for
    the cycle upon which it acts. At the next cycle, this factory will be
    called again to instantiate a new FuelHandler.
    """
    cs = operator.cs
    fuelHandlerClassName = cs["fuelHandlerName"]
    fuelHandlerModulePath = cs["shuffleLogic"]

    if not fuelHandlerClassName:
        # User did not request a custom fuel handler.
        # This is code coupling that should be untangled.
        # Special case for equilibrium-mode shuffling
        if cs["eqDirect"] and cs["runType"].lower() == RunTypes.STANDARD.lower():
            from terrapower.physics.neutronics.equilibrium import fuelHandler as efh

            return efh.EqDirectFuelHandler(operator)
        else:
            # give the default FuelHandler. This does not have an implemented outage, but
            # still offers moving capabilities. Useful when you just need to make explicit
            # moves but do not have a fully-defined fuel management input.
            return FuelHandler(operator)

    # User did request a custom fuel handler. We must go find and import it
    # from the input directory.
    with directoryChangers.DirectoryChanger(cs.inputDirectory):
        try:
            module = pathTools.importCustomPyModule(fuelHandlerModulePath)

            if not hasattr(module, fuelHandlerClassName):
                raise KeyError(
                    "The requested fuel handler object {0} is not "
                    "found in the fuel management input file {1} from CWD {2}. "
                    "Check input"
                    "".format(
                        fuelHandlerClassName, fuelHandlerModulePath, cs.inputDirectory
                    )
                )
            # instantiate the custom object
            fuelHandlerCls = getattr(module, fuelHandlerClassName)
            fuelHandler = fuelHandlerCls(operator)

            # also get getFactorList function from module level if it's there.
            # This is a legacy input option, getFactorList should now generally
            # be an method of the FuelHandler object
            if hasattr(module, "getFactorList"):
                # staticmethod binds the provided getFactorList function to the
                # fuelHandler object without passing the implicit self argument.
                # The __get__ pulls the actual function out from the descriptor.
                fuelHandler.getFactorList = staticmethod(module.getFactorList).__get__(
                    fuelHandlerCls
                )

        except IOError:
            raise ValueError(
                "Either the file specified in the `shuffleLogic` setting ({}) or the "
                "fuel handler class name specified in the `fuelHandlerName` setting ({}) "
                "cannot be found. CWD is: {}. Update input.".format(
                    fuelHandlerModulePath, fuelHandlerClassName, cs.inputDirectory
                )
            )
    return fuelHandler


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
        self.moved = collections.OrderedDict([])
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

    def outage(self, factor=1.0):
        r"""
        Simulates a reactor reload outage. Moves and tracks fuel.

        This sets the moveList structure.
        """
        if self.moved:
            raise ValueError(
                "Cannot perform two outages with same FuelHandler instance."
            )

        # determine if a repeat shuffle is occurring or a new shuffle pattern
        if self.cs["explicitRepeatShuffles"]:
            # repeated shuffle
            if not os.path.exists(self.cs["explicitRepeatShuffles"]):
                raise RuntimeError(
                    "Requested repeat shuffle file {0} does not exist. Cannot perform shuffling. "
                    "".format(self.cs["explicitRepeatShuffles"])
                )
            runLog.important(
                "Repeating a shuffling pattern from {}".format(
                    self.cs["explicitRepeatShuffles"]
                )
            )
            self.repeatShufflePattern(self.cs["explicitRepeatShuffles"])
        else:
            # Normal shuffle from user-provided shuffle logic input
            self.chooseSwaps(factor)

        # do rotations if pin-level details are available (requires fluxRecon plugin)
        if self.cs["fluxRecon"] and self.cs["assemblyRotationAlgorithm"]:
            # Rotate assemblies ONLY IF at least some assemblies have pin detail (enabled by fluxRecon)
            # The user can choose the algorithm method name directly in the settings
            if hasattr(self, self.cs["assemblyRotationAlgorithm"]):
                rotationMethod = getattr(self, self.cs["assemblyRotationAlgorithm"])
                rotationMethod()
            else:
                raise RuntimeError(
                    "FuelHandler {0} does not have a rotation algorithm called {1}.\n"
                    'Change your "assemblyRotationAlgorithm" setting'
                    "".format(self, self.cs["assemblyRotationAlgorithm"])
                )

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
                    runLog.important("The moved list is {}".format(self.moved.keys()))
                    raise
        else:
            numMoved = 0

        self.o.r.core.p.numMoves = numMoved

        runLog.important(
            "Fuel handler performed {0} assembly shuffles.".format(numMoved)
        )

        # now wipe out the self.moved version so it doesn't transmit the assemblies during distributeState
        moved = self.moved.copy()
        self.moved = collections.OrderedDict([])
        return moved

    def chooseSwaps(self, shuffleFactors=None):
        """
        Moves the fuel around or otherwise processes it between cycles.
        """
        raise NotImplementedError

    @staticmethod
    def getFactorList(cycle, cs=None, fallBack=False):
        """
        Return factors between 0 and 1 that control fuel management.

        This is the default shuffle control function. Usually you would override this
        with your own in a custom shuffleLogic.py file. For more details about how this
        works, refer to :doc:`/user/inputs/fuel_management`.

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

    def simpleAssemblyRotation(self):
        """
        Rotate all pin-detail assemblies that were just shuffled by 60 degrees

        Notes
        -----
        Also, optionally rotate stationary (non-shuffled) assemblies if the setting is set.
        Obviously, only pin-detail assemblies can be rotated, because homogenized assemblies are isotropic.

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
        hist = self.o.getInterface("history")
        for a in hist.getDetailAssemblies():
            if a in self.moved or self.cs["assemblyRotationStationary"]:
                a.rotatePins(1)
                numRotated += 1
                i, j = a.spatialLocator.getRingPos()  # hex indices (i,j) = (ring,pos)
                runLog.extra(
                    "Rotating Assembly ({0},{1}) to Orientation {2}".format(i, j, 1)
                )
        runLog.extra("Rotated {0} assemblies".format(numRotated))

    def buReducingAssemblyRotation(self):
        r"""
        Rotates all detail assemblies to put the highest bu pin in the lowest power orientation

        See Also
        --------
        simpleAssemblyRotation : an alternative rotation algorithm
        outage : calls this method based on a user setting

        """

        runLog.info("Algorithmically rotating assemblies to minimize burnup")
        numRotated = 0
        hist = self.o.getInterface("history")
        for aPrev in self.moved:  # much more convenient to loop through aPrev first
            aNow = self.r.core.getAssemblyWithStringLocation(aPrev.lastLocationLabel)
            if (
                aNow in hist.getDetailAssemblies()
            ):  # no point in rotation if there's no pin detail

                rot = self.getOptimalAssemblyOrientation(aNow, aPrev)
                aNow.rotatePins(rot)  # rot = integer between 0 and 5
                numRotated += 1
                # Print out rotation operation (mainly for testing)
                (
                    i,
                    j,
                ) = aNow.spatialLocator.getRingPos()  # hex indices (i,j) = (ring,pos)
                runLog.important(
                    "Rotating Assembly ({0},{1}) to Orientation {2}".format(i, j, rot)
                )

        if self.cs[
            "assemblyRotationStationary"
        ]:  # rotate NON-MOVING assemblies (stationary)
            for a in hist.getDetailAssemblies():
                if a not in self.moved:
                    rot = self.getOptimalAssemblyOrientation(a, a)
                    a.rotatePins(rot)  # rot = integer between 0 and 6
                    numRotated += 1
                    (
                        i,
                        j,
                    ) = a.spatialLocator.getRingPos()  # hex indices (i,j) = (ring,pos)
                    runLog.important(
                        "Rotating Assembly ({0},{1}) to Orientation {2}".format(
                            i, j, rot
                        )
                    )

        runLog.info("Rotated {0} assemblies".format(numRotated))

    def getOptimalAssemblyOrientation(self, a, aPrev):
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
        >>> fh.getOptimalAssemblyOrientation(a,aPrev)
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
        maxBuPinIndexAssem = int(
            maxBuBlock.p.percentBuMaxPinLocation - 1
        )  # start at 0 instead of 1
        bIndexMaxBu = a.index(maxBuBlock)

        if maxBuPinIndexAssem == 0:
            # Don't bother rotating if the highest-BU pin is the central pin. End this method.
            return rot

        else:

            # transfer percentBuMax rotated pin index to non-rotated pin index
            # maxBuPinIndexAssem = self.pinIndexLookup[maxBuPinIndexAssem]
            # dummyList = numpy.where(self.pinIndexLookup == maxBuPinIndexAssem)
            # maxBuPinIndexAssem = dummyList[0][0]

            if aPrevDetailFlag:

                # aPrev has pin detail. Excellent!
                # Determine which of 6 possible rotated pin indices had the lowest power when aPrev was here.

                prevAssemPowHereMIN = float("inf")

                for possibleRotation in range(6):  # k = 1,2,3,4,5
                    # get rotated pin index
                    indexLookup = maxBuBlock.rotatePins(
                        possibleRotation, justCompute=True
                    )
                    index = indexLookup[
                        maxBuPinIndexAssem
                    ]  # rotated index of highest-BU pin
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
                # aPrev has no pin-detail, so we must resort to using the corner fast fluxes.
                # These corner quantities will be set for ALL assemblies whenever fluxRecon runs,
                # even if only a few assemblies have pin-detail.
                # We rotate the assembly so that the highest-BU pin is closest to the lowest-fast-flux corner.

                # First find the corner with the LOWEST fast flux when aPrev was located here.
                prevAssemFastFluxCornerMIN = 0.0
                cornerMinFastFlux = -1
                prevBlock = aPrev[bIndexMaxBu]
                for possibleRotation in range(6):

                    fastFlux = prevBlock.p.fastFlux[possibleRotation]

                    if fastFlux < prevAssemFastFluxCornerMIN:
                        prevAssemFastFluxCornerMIN = fastFlux
                        cornerMinFastFlux = possibleRotation

                # Find the x,y coordinates of this corner
                xCor = (a.getPitch() / math.sqrt(3.0)) * math.cos(
                    math.pi * (cornerMinFastFlux + 1) / 3.0
                )  # cm
                yCor = (a.getPitch() / math.sqrt(3.0)) * math.sin(
                    math.pi * (cornerMinFastFlux + 1) / 3.0
                )  # cm

                # print('xCor,yCor =')
                # print(xCor,yCor)

                # Find the assembly rotation that will result in the MINIMUM distance
                # between the highest-BU pin and the lowest-fast-flux corner
                distanceToCorMIN = float("inf")
                for possibleRotation in range(6):  # k = 0,1,2,3,4,5

                    # get rotated pin index
                    indexLookup = numpy.array(
                        prevBlock.rotatePins(possibleRotation, justCompute=True)
                    )
                    pinLocationOfMaxBuInThisRotation = indexLookup[maxBuPinIndexAssem]

                    x = a.pinXVals[pinLocationOfMaxBuInThisRotation]  # cm
                    y = a.pinYVals[pinLocationOfMaxBuInThisRotation]  # cm

                    distanceToCor = math.sqrt(
                        (xCor - x) ** 2.0 + (yCor - y) ** 2.0
                    )  # cm
                    if distanceToCor < distanceToCorMIN:
                        distanceToCorMIN = distanceToCor
                        rot = possibleRotation

                    runLog.debug(
                        "Distance to low flux corner in rotation {0} is {1:.2E}W".format(
                            possibleRotation, distanceToCor
                        )
                    )

            runLog.debug("Best relative rotation is {0}".format(rot))
            return rot

    def prepCore(self):
        """Aux. function to run before XS generation (do moderation, etc. here)"""

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
                x, y = a.getLocationObject().coords(a.getPitch())
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
                    elif abs(a.getLocationObject().i1 - targetRing) < minDiff[0]:
                        minDiff = (abs(a.getLocationObject().i1 - targetRing), a)

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
                    ring = a.getLocationObject().i1
                if ring in ringList:
                    # keep it in the right order
                    assemblyList[ringList.index(ring)].append(a)

        return assemblyList

    def buildRingSchedule(
        self,
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

        See Also
        --------
        findAssembly

        """
        # process arguments
        if dischargeRing is None:
            # default to convergent
            dischargeRing = 1
        if chargeRing is None:
            chargeRing = self.r.core.getNumRings()

        if chargeRing > dischargeRing and not jumpRingTo:
            jumpRingTo = 1
        elif not jumpRingTo:
            if self.r:
                jumpRingTo = self.r.core.getNumRings()
            else:
                jumpRingTo = 18

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
        if numSteps < 2:
            # don't let it be smaller than 2 because linspace(1,5,1)= [1], linspace(1,5,2)= [1,5]
            numSteps = 2
        baseRings = [
            int(ring) for ring in numpy.linspace(dischargeRing, chargeRing, numSteps)
        ]
        # eliminate duplicates.
        newBaseRings = []
        for br in baseRings:
            if br not in newBaseRings:
                newBaseRings.append(br)
        baseRings = newBaseRings
        # baseRings = list(set(baseRings)) # eliminate duplicates. but ruins order.
        # build widths
        widths = []
        for i, ring in enumerate(baseRings[:-1]):
            widths.append(
                abs(baseRings[i + 1] - ring) - 1
            )  # 0 is the most restrictive, meaning don't even look in other rings.
        widths.append(0)  # add the last ring with width 0.

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

    def buildConvergentRingSchedule(
        self, dischargeRing=1, chargeRing=None, coarseFactor=0.0
    ):
        r"""
        Builds a ring schedule for convergent shuffling from chargeRing to dischargeRing

        Parameters
        ----------
        dischargeRing : int, optional
            The last ring an assembly sits in before discharging. If no discharge, this is the one that
            gets placed where the charge happens. Default: Innermost ring

        chargeRing : int, optional
            The peripheral ring into which an assembly enters the core. Default is outermost ring.

        coarseFactor : float, optional
            A number between 0 and 1 where 0 hits all rings and 1 only hits the outer, rJ, center, and rD rings.
            This allows coarse shuffling, with large jumps. Default: 0

        Returns
        -------
        convergent : list
            A list of rings in order from discharge to charge.

        conWidths : list
            A list of integers corresponding to the ringSchedule determining the widths of each ring area

        Examples
        -------

        See Also
        --------
        findAssembly

        """
        # process arguments
        if chargeRing is None:
            chargeRing = self.r.core.getNumRings()

        # step 1: build the convergent rings
        numSteps = int((chargeRing - dischargeRing + 1) * (1.0 - coarseFactor))
        if numSteps < 2:
            # don't let it be smaller than 2 because linspace(1,5,1)= [1], linspace(1,5,2)= [1,5]
            numSteps = 2
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
                self.moved[a] = a  # use as ordered set

        oldA1Location = a1.spatialLocator
        self._transferStationaryBlocks(a1, a2)
        a1.moveTo(a2.spatialLocator)
        a2.moveTo(oldA1Location)

        self._swapFluxParam(a1, a2)

    def _transferStationaryBlocks(self, assembly1, assembly2):
        """
        Exchange the stationary blocks (e.g. grid plate) between the moving assemblies

        These blocks in effect are not moved at all.
        """
        for index in self.cs["stationaryBlocks"]:
            # this block swap is designed to ensure that all blocks have the
            # correct parents and children structure at the end of the swaps.
            tempBlock1 = assembly1[index]
            assembly1.remove(tempBlock1)

            tempBlock2 = assembly2[index]
            assembly2.remove(tempBlock2)

            assembly1.insert(index, tempBlock2)
            assembly2.insert(index, tempBlock1)

    def dischargeSwap(self, incoming, outgoing):
        r"""
        Removes one assembly from the core and replace it with another assembly

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
        # keep it unique so we don't get blow-up nummobes
        for a in [incoming, outgoing]:
            if a not in self.moved:
                self.moved[a] = a

        self._transferStationaryBlocks(incoming, outgoing)

        # replace the goingOut guy.
        loc = outgoing.spatialLocator
        # say it happened at the end of the previous cycle by sending cycle-1
        # to removeAssembly, which will look up EOC of last cycle,
        # which, coincidentally is the same time we're at right now at BOC.
        self.r.core.removeAssembly(outgoing)

        if incoming in self.r.core.sfp.getChildren():
            # pull it out of the sfp if it's in there.
            runLog.extra("removing {0} from the sfp".format(incoming))
            self.r.core.sfp.remove(incoming)
        self.r.core.add(incoming, loc)

        self._swapFluxParam(incoming, outgoing)

    def _swapFluxParam(self, incoming, outgoing):
        """
        Set the flux and power params of the new blocks to that of the old and vice versa.

        This is essential for getting loosely-coupled flux-averaged cross sections from things like
        :py:class:`armi.physics.neutronics.crossSectionGroupManager.BlockCollectionAverageFluxWeighted`

        Parameters
        ----------
        incoming, outgoing : Assembly
            Assembly objects to be swapped

        Notes
        -----
        Assumes assemblies have the same block structure. If not, blocks will be swapped one-for-one until
        the shortest one has been used up and then the process will truncate.
        """
        if len(incoming) != len(outgoing):
            runLog.warning(
                "{0} and {1} have different numbers of blocks. Flux swapping (for XS weighting) will "
                "be questionable".format(incoming, outgoing)
            )
        for bi, (bIncoming, bOutgoing) in enumerate(zip(incoming, outgoing)):
            if (
                bi not in self.cs["stationaryBlocks"]
            ):  # stationary blocks are already swapped.
                incomingFlux = bIncoming.p.flux
                incomingMgFlux = bIncoming.p.mgFlux
                incomingPower = bIncoming.p.power
                outgoingFlux = bOutgoing.p.flux
                outgoingMgFlux = bOutgoing.p.mgFlux
                outgoingPower = bOutgoing.p.power
                if outgoingFlux > 0.0:
                    bIncoming.p.flux = outgoingFlux
                    bIncoming.p.mgFlux = outgoingMgFlux
                    bIncoming.p.power = outgoingPower
                if incomingFlux > 0.0:
                    bOutgoing.p.flux = incomingFlux
                    bOutgoing.p.mgFlux = incomingMgFlux
                    bOutgoing.p.power = incomingPower

    def swapCascade(self, assemList):
        """
        Perform swaps on a list of assemblies.

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
                runLog.extra("Warning: %s is in the cascade more than once!" % assem)

        # now swap.
        levels = len(assemList)
        for level in range(levels - 1):
            if not assemList[level + 1]:
                # If None in the cascade, just skip it. this will lead to slightly unintended shuffling if
                # the user wasn't careful enough. Their problem.
                runLog.extra(
                    "Skipping level %d in the cascade because it is none" % (level + 1)
                )
                continue
            self.swapAssemblies(assemList[0], assemList[level + 1])

    def repeatShufflePattern(self, explicitRepeatShuffles):
        r"""
        Repeats the fuel management from a previous ARMI run

        Parameters
        ----------
        explicitRepeatShuffles : str
            The file name that contains the shuffling history from a previous run

        Returns
        -------
        moved : list
            list of assemblies that moved this cycle

        Notes
        -----
        typically the explicitRepeatShuffles will be "caseName"+"-SHUFFLES.txt"

        See Also
        --------
        doRepeatShuffle : Performs moves as processed by this method
        processMoveList : Converts a stored list of moves into a functional list of assemblies to swap
        makeShuffleReport : Creates the file that is processed here
        """

        # read moves file
        moves = self.readMoves(explicitRepeatShuffles)
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
            _alreadyDone,
        ) = self.processMoveList(moveList)

        # Now have the move locations
        moved = self.doRepeatShuffle(
            loadChains, loopChains, enriches, loadChargeTypes, loadNames
        )

        return moved

    def readMoves(self, fname):
        r"""
        reads a shuffle output file and sets up the moves dictionary

        Parameters
        ----------
        fname : str
            The shuffles file to read

        Returns
        -------
        moves : dict
            A dictionary of all the moves. Keys are the cycle number. Values are a list
            of tuples, one tuple for each individual move that happened in the cycle.
            The items in the tuple are (oldLoc, newLoc, enrichList, assemType).
            Where oldLoc and newLoc are str representations of the locations and
            enrichList is a list of mass enrichments from bottom to top.

        See Also
        --------
        repeatShufflePattern : reads this file and repeats the shuffling
        outage : creates the moveList in the first place.
        makeShuffleReport : writes the file that is read here.

        """

        try:
            f = open(fname)
        except:
            raise RuntimeError(
                "Could not find/open repeat shuffle file {} in working directory {}"
                "".format(fname, os.getcwd())
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
                pat = r"([A-Za-z0-9!]+) moved to ([A-Za-z0-9!]+) with assembly type ([A-Za-z0-9!\s]+)\s*(ANAME=\S+)?\s*with enrich list: (.+)"
                m = re.search(pat, line)
                if not m:
                    raise InputError(
                        'Failed to parse line "{0}" in shuffle file'.format(line)
                    )
                oldLoc = m.group(1)
                newLoc = m.group(2)
                assemType = m.group(
                    3
                ).strip()  # take off any possible trailing whitespace
                movingAssemName = m.group(
                    4
                )  # will be None for legacy shuffleLogic files. (pre 2013-08)
                if movingAssemName:
                    movingAssemName = movingAssemName.split("=")[
                        1
                    ]  # extract the actual assembly name.
                enrichList = [float(i) for i in m.group(5).split()]
                moves[cycle].append(
                    (oldLoc, newLoc, enrichList, assemType, movingAssemName)
                )
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
                    raise InputError(
                        'Failed to parse line "{0}" in shuffle file'.format(line)
                    )
                oldLoc = m.group(1)
                newLoc = m.group(2)
                enrichList = [float(i) for i in m.group(3).split()]
                # old loading style, just assume that there is a booster as our surrogate
                moves[cycle].append((oldLoc, newLoc, enrichList, None))
                numMoves += 1

        f.close()

        runLog.info(
            "Read {0} moves over {1} cycles".format(numMoves, len(moves.keys()))
        )
        return moves

    def trackChain(self, moveList, startingAt, alreadyDone=None):
        r"""
        builds a chain of locations based on starting location

        Notes
        -----
        Takes a moveList and extracts chains. Remembers all it touches.
        If A moved to B, C moved to D, and B moved to C, this returns
        A, B, C ,D.

        Used in some monte carlo physics writers and in repeatShufflePattern

        Parameters
        ----------
        moveList : list
            a list of (fromLoc,toLoc,enrichList,assemType,assemName) tuples that occurred at a single outage.

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
        repeatShufflePattern
        mcnpInterface.getMoveCards
        processMoveList

        """
        if alreadyDone is None:
            alreadyDone = []

        enrich = None  # in case this is a load chain, prep for getting enrich.
        loadName = None
        assemType = (
            None  # in case this is a load chain, prep for getting an assembly type
        )

        for fromLoc, toLoc, _enrichList, _assemblyType, _assemName in moveList:
            if "SFP" in toLoc and "LoadQueue" in fromLoc:
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
                    chain[-1] not in ["LoadQueue", "ExCore", "SFP"]
                    and not complete
                    and safeCount < 100
                ):
                    # look for something going to where the previous one is from
                    lookingFor = chain[-1]
                    for (
                        cFromLoc,
                        cToLoc,
                        cEnrichList,
                        cAssemblyType,
                        cAssemName,
                    ) in moveList:
                        if cToLoc == lookingFor:
                            chain.append(cFromLoc)
                            if cFromLoc in ["LoadQueue", "ExCore", "SFP"]:
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
                    raise RuntimeError(
                        "Chain tracking got too long. Check moves.\n{0}".format(chain)
                    )

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
            A list of information about fuel management from a previous case. Each entry represents a
            move and includes the following items as a tuple:

            fromLoc
                the label of where the assembly was before the move
            toLoc
                the label of where the assembly was after the move
            enrichList
                a list of block enrichments for the assembly
            assemType
                the type of assembly that this is
            movingAssemName
                the name of the assembly that is moving from to

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
        alreadyDone : list
            All the locations that were read.

        Notes
        -----
        Used in the some Monte Carlo interfaces to convert ARMI moves to their format moves. Also used in
        repeat shuffling.

        See Also
        --------
        makeShuffleReport : writes the file that is being processed
        repeatShufflePattern : uses this to repeat shuffles

        """
        alreadyDone = []
        loadChains = []  # moves that have discharges
        loadChargeTypes = (
            []
        )  # the assembly types (strings) that should be used in a load chain.
        loopChains = []  # moves that don't have discharges
        enriches = []  # enrichments of each loadChain
        loadNames = []  # assembly name of each load assembly (to read from SFP)

        # first handle all charge/discharge chains by looking for things going to SFP
        for fromLoc, toLoc, _enrichList, _assemType, _movingAssemName in moveList:
            if toLoc in ["SFP", "ExCore"] and "LoadQueue" in fromLoc:
                # skip dummy moves
                continue

            elif "SFP" in toLoc or "ExCore" in toLoc:
                # discharge. Track chain.
                chain, enrichList, assemType, loadAssemName = self.trackChain(
                    moveList, startingAt=fromLoc
                )
                runLog.extra(
                    "Load Chain with load assem {0}: {1}".format(assemType, chain)
                )
                loadChains.append(chain)
                enriches.append(enrichList)
                loadChargeTypes.append(assemType)
                loadNames.append(loadAssemName)
                # track all the locations we saw already so we
                # don't use them in the loop moves.
                alreadyDone.extend(chain)

        # go through again, looking for stuff that isn't in chains.
        # put them in loop type 3 moves (arbitrary order)
        for fromLoc, toLoc, _enrichList, assemType, _movingAssemName in moveList:
            if toLoc in ["SFP", "ExCore"] or fromLoc in ["LoadQueue", "SFP", "ExCore"]:
                # skip loads/discharges; they're already done.
                continue
            elif fromLoc in alreadyDone:
                # skip repeats
                continue
            else:
                # normal move
                chain, _enrichList, _assemType, _loadAssemName = self.trackChain(
                    moveList, startingAt=fromLoc
                )
                loopChains.append(chain)
                alreadyDone.extend(chain)

                runLog.extra("Loop Chain: {0}".format(chain))

        return loadChains, loopChains, enriches, loadChargeTypes, loadNames, alreadyDone

    def assignXSValues(self, a):
        r"""
        Takes in an assembly and assigns the correct xs values to it for the given enrichment

        Notes
        -----
        This is only used for booster assemblies with strange enrichment distributions
        """

        xsList = [
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "I",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O",
            "P",
            "S",
            "T",
            "U",
            "V",
            "W",
            "X",
        ]
        enrichList = [
            0,
            0.01,
            0.02,
            0.03,
            0.04,
            0.05,
            0.06,
            0.07,
            0.08,
            0.09,
            0.1,
            0.11,
            0.12,
            0.13,
            0.14,
            0.15,
            0.16,
            0.17,
            0.18,
            0.19,
            0.2,
            1,
        ]

        if len(xsList) != len(enrichList):
            print(xsList)
            print(enrichList)
            raise ValueError("lengths are not the same")

        for b in a:
            if b.hasFlags(Flags.FUEL):
                # make sure we have the correct enrichment
                c = b.getComponent(Flags.FUEL)
                enrich = c.getMassEnrichment()

                # get the location in the enrichList
                counter = 0
                for val in enrichList:
                    if enrich < val:
                        break
                    counter += 1

                # set the xsType of the block to the new xsType based on enrichment
                b.p.xsType = xsList[counter - 1]

    def guessAssemblyType(self, enrichList):
        r"""
        Guess the assembly type of an assembly based on its enrichment

        Parameters
        ----------
        enrichList : list
            floats of enriches of each block

        Returns
        -------
        assemblyType : str
            The guessed assembly type

        Notes
        -----
        Useful for repeating shuffles from legacy shuffles files.
        since the assembly type isn't specified, we will make an educated guess
        based on the convention of the time.  So this will either be a "feed fuel" (depleted uranium)
        or a booster assembly that is enriched.  So, just have to look at the enrichments.

        """

        if max(enrichList) > 0.01:
            # looks like there is a higher than 1% enrichment.  This assembly is a booster
            assemblyType = "booster fuel"
        else:
            assemblyType = "feed fuel"  # looks like a feed fuel

        # check to see if that type is in the bolAssems, if not, error!
        if assemblyType not in self.r.blueprints.assemDesigns:
            runLog.error(
                "Assembly type {} not in bol Assems: {}".format(
                    assemblyType, ", ".join(self.r.blueprints.assemDesigns)
                )
            )
            raise RuntimeError("Failed to find assembly in BOL Assems.")

        return assemblyType

    def doRepeatShuffle(
        self, loadChains, loopChains, enriches, loadChargeTypes, loadNames
    ):
        r"""
        Actually does the fuel movements required to repeat a shuffle order

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
        repeatShufflePattern : coordinates the moves for this cycle
        processMoveList : builds the input lists

        Notes
        -----
        This is a helper function for repeatShufflePattern
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
            # initialize swap chains and enrichment information
            if not assemblyType:
                if not enrichList:
                    raise RuntimeError(
                        "Cannot determine assemblyType for {0} in {1} with enrich {2}"
                        "".format(assemblyName, assemblyChain, enrichList)
                    )
                assemblyType = self.guessAssemblyType(enrichList)

            # convert the labels into actual assemblies to be swapped
            assemblyList = self.r.core.getLocationContents(
                assemblyChain, assemblyLevel=True, locContents=locContents
            )

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
                loadAssembly = self.r.core.sfp.getAssembly(assemblyName)
                if not loadAssembly:
                    runLog.error(
                        "the required assembly {0} is not found in the SFP. It contains: {1}"
                        "".format(assemblyName, self.r.core.sfp.getChildren())
                    )
                    raise RuntimeError(
                        "the required assembly {0} is not found in the SFP.".format(
                            loadAssembly
                        )
                    )
            else:
                # create a new assembly from the BOL assem templates and adjust the enrichment
                loadAssembly = self.r.core.createAssemblyOfType(
                    enrichList=enrichList, assemType=assemblyType
                )

            # replace the goingOut guy (for continual feed cases)
            runLog.debug(
                "Calling discharge swap with {} and {}".format(
                    loadAssembly, assemblyList[0]
                )
            )
            self.dischargeSwap(loadAssembly, assemblyList[0])
            moved.append(loadAssembly)

        # shuffle all of the loop chain assemblies (no charge/discharge)

        for assemblyChain in loopChains:
            # convert the labels into actual assemblies to be swapped
            assemblyList = self.r.core.getLocationContents(
                assemblyChain, assemblyLevel=True, locContents=locContents
            )

            for a in assemblyList:
                moved.append(a)

            # go through and swap the assemblies knowing that there is a discharge (first one)
            # and a new assembly brought it (last one)
            # for i in range(0,-(len(assemblyList)-1),-1):
            for i in range(0, -(len(assemblyList) - 1), -1):
                self.swapAssemblies(assemblyList[i], assemblyList[i + 1])

        return moved

    def buildEqRingSchedule(self, ringSchedule):
        r"""
        Expands simple ringSchedule input into full-on location schedule

        Parameters
        ----------
        ringSchedule, r, cs

        Returns
        -------
        locationSchedule : list

        """
        locationSchedule = []
        # start by expanding the user-input eqRingSchedule list into a list containing
        # all the rings as it goes.
        ringList = self.buildEqRingScheduleHelper(ringSchedule)

        # now build the locationSchedule ring by ring using this ringSchedule.
        lastRing = 0
        for ring in ringList:
            assemsInRing = self.r.core.getAssembliesInRing(ring, typeSpec=Flags.FUEL)
            if self.cs["circularRingOrder"] == "angle":
                sorter = lambda a: a.getLocationObject().getAngle()
            elif self.cs["circularRingOrder"] == "distanceSmart":
                if lastRing == ring + 1:
                    # converging. Put things on the outside first.
                    sorter = lambda a: -a.getLocationObject().getDistanceOfLocationToPoint(
                        (0, 0)
                    )
                else:
                    # diverging. Put things on the inside first.
                    sorter = lambda a: a.getLocationObject().getDistanceOfLocationToPoint(
                        (0, 0)
                    )
            else:
                # purely based on distance. Can mix things up in convergent-divergent cases. Prefer distanceSmart
                sorter = lambda a: a.getLocationObject().getDistanceOfLocationToPoint(
                    (0, 0)
                )
            assemsInRing = sorted(assemsInRing, key=sorter)
            for a in assemsInRing:
                locationSchedule.append(a.getLocation())
            lastRing = ring
        return locationSchedule

    def buildEqRingScheduleHelper(self, ringSchedule):
        r"""
        turns ringScheduler into explicit list of rings

        Pulled out of buildEqRingSchedule for testing.

        Parameters
        ----------
        ringSchedule : list
            List of ring bounds that is required to be an even number of entries.  These
            entries then are used in a from - to approach to add the rings.  The from ring will
            always be included.

        Returns
        -------
        ringList : list
            List of all rings in the order they should be shuffled.

        Examples
        --------
        >>> buildEqRingScheduleHelper([1,5])
        [1,2,3,4,5]

        >>> buildEqRingScheduleHelper([1,5,9,6])
        [1,2,3,4,5,9,8,7,6]

        >>> buildEqRingScheduleHelper([9,5,3,4,1,2])
        [9,8,7,6,5,3,4,1,2]

        >>> buildEqRingScheduleHelper([2,5,1,1])
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

            ringList.extend(
                [int(j) for j in numpy.linspace(fromRing, toRing, numRings)]
            )

        # eliminate doubles (but allow a ring to show up multiple times)
        newList = []
        lastRing = None
        for ring in ringList:
            if ring != lastRing:
                newList.append(ring)
            if self.r.core and ring > self.r.core.getNumRings():
                # error checking.
                runLog.warning(
                    "Ring {0} in eqRingSchedule larger than largest ring in reactor {1}. "
                    "Adjust shuffling.".format(ring, self.r.core.getNumRings()),
                    single=True,
                    label="too many rings",
                )
            lastRing = ring
        ringList = newList

        return ringList

    def workerOperate(self, cmd):
        """Handle a mpi command on the worker nodes."""
        pass

    def prepShuffleMap(self):
        """Prepare a table of current locations for plotting shuffle maneuvers."""
        self.oldLocations = {}
        for a in self.r.core.getAssemblies():
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
        for a in self.r.core.getAssemblies():
            currentCoords = a.spatialLocator.getGlobalCoordinates()
            oldCoords = self.oldLocations.get(a.getName(), None)
            if oldCoords is None:
                oldCoords = numpy.array((-50, -50, 0))
            elif any(currentCoords != oldCoords):
                arrows.append((oldCoords, currentCoords))
        return arrows
