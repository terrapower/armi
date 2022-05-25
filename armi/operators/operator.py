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
The standard ARMI operator.

This builds and maintains the interface stack and loops through it for a
certain number of cycles with a certain number of timenodes per cycle.

This is analogous to a real reactor operating over some period of time,
often from initial startup, through the various cycles, and out to
the end of plant life.

.. impl:: ARMI controls the time flow of the reactor, by running a sequence of Interfaces at each time step.
   :id: IMPL_EVOLVING_STATE_0
   :links: REQ_EVOLVING_STATE
"""
import os
import re
import shutil
import time

from armi import context
from armi import interfaces
from armi import runLog
from armi import settings
from armi.bookkeeping import memoryProfiler
from armi.bookkeeping.report import reportingUtils
from armi.operators import settingsValidation
from armi.operators.runTypes import RunTypes
from armi.utils import codeTiming
from armi.utils import (
    pathTools,
    getPowerFractions,
    getAvailabilityFactors,
    getStepLengths,
    getCycleLengths,
    getBurnSteps,
    getMaxBurnSteps,
    getCycleNames,
)


class Operator:  # pylint: disable=too-many-public-methods
    """
    Orchestrates an ARMI run, building all the pieces, looping through the interfaces, and manipulating the reactor.

    This Standard Operator loops over a user-input number of cycles, each with a
    user-input number of subcycles (called time nodes). It calls a series of
    interaction hooks on each of the
    :py:class:`~armi.interfaces.Interface` in the Interface Stack.

    .. figure:: /.static/armi_general_flowchart.png
        :align: center

    **Figure 1.** The computational flow of the interface hooks in a Standard Operator

    .. note:: The :doc:`/developer/guide` has some additional narrative on this topic.

    Attributes
    ----------
    cs : CaseSettings object
            Global settings that define the run.

    cycleNames : list of str
        The name of each cycle. Cycles without a name are `None`.

    stepLengths : list of list of float
        A two-tiered list, where primary indices correspond to cycle and
        secondary indices correspond to the length of each intra-cycle step (in days).

    cycleLengths : list of float
        The duration of each individual cycle in a run (in days). This is the entire cycle,
        from startup to startup and includes outage time.

    burnSteps : list of int
        The number of sub-cycles in each cycle.

    availabilityFactors : list of float
        The fraction of time in a cycle that the plant is producing power. Note that capacity factor
        is always less than or equal to this, depending on the power fraction achieved during each cycle.
        Note that this is not a two-tiered list like stepLengths or powerFractions,
        because each cycle can have only one availabilityFactor.

    powerFractions : list of list of float
        A two-tiered list, where primary indices correspond to cycles and secondary
        indices correspond to the fraction of full rated capacity that the plant achieves
        during that step of the cycle.
        Zero power fraction can indicate decay-only cycles.

    interfaces : list
        The Interface objects that will operate upon the reactor
    """

    inspector = settingsValidation.Inspector

    def __init__(self, cs):
        """
        Constructor for operator.

        Parameters
        ----------
        cs : CaseSettings object
            Global settings that define the run.

        Raises
        ------
        OSError
            If unable to create the FAST_PATH directory.
        """
        self.r = None
        self.cs = cs
        runLog.LOG.startLog(self.cs.caseTitle)
        self.timer = codeTiming.getMasterTimer()
        self.interfaces = []
        self.restartData = []
        self.loadedRestartData = []
        self._cycleNames = None
        self._stepLengths = None
        self._cycleLengths = None
        self._burnSteps = None
        self._maxBurnSteps = None
        self._powerFractions = None
        self._availabilityFactors = None

        # Create the welcome headers for the case (case, input, machine, and some basic reactor information)
        reportingUtils.writeWelcomeHeaders(self, cs)

        self._initFastPath()

    @property
    def burnSteps(self):
        if not self._burnSteps:
            self._burnSteps = getBurnSteps(self.cs)
            if self._burnSteps == [] and self.cs["nCycles"] == 1:
                # it is possible for there to be one cycle with zero burn up,
                # in which case burnSteps is an empty list
                pass
            else:
                self._checkReactorCycleAttrs({"burnSteps": self._burnSteps})
        return self._burnSteps

    @property
    def maxBurnSteps(self):
        if not self._maxBurnSteps:
            self._maxBurnSteps = getMaxBurnSteps(self.cs)
        return self._maxBurnSteps

    @property
    def stepLengths(self):
        if not self._stepLengths:
            self._stepLengths = getStepLengths(self.cs)
            if self._stepLengths == [] and self.cs["nCycles"] == 1:
                # it is possible for there to be one cycle with zero burn up,
                # in which case stepLengths is an empty list
                pass
            else:
                self._checkReactorCycleAttrs({"Step lengths": self._stepLengths})
            self._consistentPowerFractionsAndStepLengths()
        return self._stepLengths

    @property
    def cycleLengths(self):
        if not self._cycleLengths:
            self._cycleLengths = getCycleLengths(self.cs)
            self._checkReactorCycleAttrs({"cycleLengths": self._cycleLengths})
        return self._cycleLengths

    @property
    def powerFractions(self):
        if not self._powerFractions:
            self._powerFractions = getPowerFractions(self.cs)
            self._checkReactorCycleAttrs({"powerFractions": self._powerFractions})
            self._consistentPowerFractionsAndStepLengths()
        return self._powerFractions

    @property
    def availabilityFactors(self):
        if not self._availabilityFactors:
            self._availabilityFactors = getAvailabilityFactors(self.cs)
            self._checkReactorCycleAttrs(
                {"availabilityFactors": self._availabilityFactors}
            )
        return self._availabilityFactors

    @property
    def cycleNames(self):
        if not self._cycleNames:
            self._cycleNames = getCycleNames(self.cs)
            self._checkReactorCycleAttrs({"Cycle names": self._cycleNames})
        return self._cycleNames

    @staticmethod
    def _initFastPath():
        """
        Create the FAST_PATH directory for fast local operations

        Notes
        -----
        The FAST_PATH was once created at import-time in order to support modules
        that use FAST_PATH without operators (e.g. Database). However, we decided
        to leave FAST_PATH as the CWD in INTERACTIVE mode, so this should not
        be a problem anymore, and we can safely move FAST_PATH creation
        back into the Operator.

        If the operator is being used interactively (e.g. at a prompt) we will still
        use a temporary local fast path (in case the user is working on a slow network path).
        """
        context.activateLocalFastPath()
        try:
            os.makedirs(context.getFastPath())
        except OSError:
            # If FAST_PATH exists already that generally should be an error because
            # different processes will be stepping on each other.
            # The exception to this rule is in cases that instantiate multiple operators in one
            # process (e.g. unit tests that loadTestReactor). Since the FAST_PATH is set at
            # import, these will use the same path multiple times. We pass here for that reason.
            if not os.path.exists(context.getFastPath()):
                # if it actually doesn't exist, that's an actual error. Raise
                raise

    def _checkReactorCycleAttrs(self, attrsDict):
        """Check that the list has nCycles number of elements."""
        for name, param in attrsDict.items():
            if len(param) != self.cs["nCycles"]:
                raise ValueError(
                    "The `{}` setting did not have a length consistent with the number of cycles.\n"
                    "Expected {} value(s), but only had {} defined.\n"
                    "Current input: {}".format(
                        name, self.cs["nCycles"], len(param), param
                    )
                )

    def _consistentPowerFractionsAndStepLengths(self):
        """
        Check that the internally-resolved _powerFractions and _stepLengths have
        consistent shapes, if they both exist.
        """
        if self._powerFractions and self._stepLengths:
            for cycleIdx in range(len(self._powerFractions)):
                if len(self._powerFractions[cycleIdx]) != len(
                    self._stepLengths[cycleIdx]
                ):
                    raise ValueError(
                        "The number of entries in lists for subcycle power "
                        f"fractions and sub-steps are inconsistent in cycle {cycleIdx}"
                    )

    @property
    def atEOL(self):
        """
        Return whether we are approaching EOL.

        For the standard operator, this will return true when the current cycle
        is the last cycle (cs["nCycles"] - 1). Other operators may need to
        impose different logic.
        """
        return self.r.p.cycle == self.cs["nCycles"] - 1

    def initializeInterfaces(self, r):
        """
        Attach the reactor to the operator and initialize all interfaces.

        This does not occur in `__init__` so that the ARMI operator can be initialized before a
        reactor is created, which is useful for summarizing the case information quickly.

        Parameters
        ----------
        r : Reactor
            The Reactor object to attach to this Operator.
        """
        self.r = r
        r.o = self  # TODO: this is only necessary for fuel-handler hacking
        with self.timer.getTimer("Interface Creation"):
            self.createInterfaces()
            self._processInterfaceDependencies()
            if context.MPI_RANK == 0:
                runLog.header("=========== Interface Stack Summary  ===========")
                runLog.info(reportingUtils.getInterfaceStackSummary(self))
                self.interactAllInit()
            else:
                self._attachInterfaces()

        self._loadRestartData()

    def __repr__(self):
        return "<{} {} {}>".format(self.__class__.__name__, self.cs["runType"], self.cs)

    def __enter__(self):
        """Context manager to enable interface-level error handling hooks."""
        return self

    def __exit__(self, exception_type, exception_value, stacktrace):
        if any([exception_type, exception_value, stacktrace]):
            runLog.error(
                r"{}\n{}\{}".format(exception_type, exception_value, stacktrace)
            )
            self.interactAllError()

    def operate(self):
        """
        Run the operation loop.

        See Also
        --------
        mainOperator : run the operator loop on the primary MPI node (for parallel runs)
        workerOperate : run the operator loop for the worker MPI nodes
        """
        self._mainOperate()

    def _mainOperate(self):
        """
        Main loop for a standard ARMI run. Steps through time interacting with the interfaces.
        """
        self.interactAllBOL()
        startingCycle = self.r.p.cycle  # may be starting at t != 0 in restarts
        for cycle in range(startingCycle, self.cs["nCycles"]):
            keepGoing = self._cycleLoop(cycle, startingCycle)
            if not keepGoing:
                break
        self.interactAllEOL()

    def _cycleLoop(self, cycle, startingCycle):
        """Run the portion of the main loop that happens each cycle."""
        self.r.p.cycleLength = self.cycleLengths[cycle]
        self.r.p.availabilityFactor = self.availabilityFactors[cycle]
        self.r.p.cycle = cycle
        self.r.core.p.coupledIteration = 0
        if cycle == startingCycle:
            startingNode = self.r.p.timeNode
        else:
            startingNode = 0
            self.r.p.timeNode = startingNode
        halt = self.interactAllBOC(self.r.p.cycle)
        if halt:
            return False

        for timeNode in range(startingNode, int(self.burnSteps[cycle])):
            self.r.core.p.power = (
                self.powerFractions[cycle][timeNode] * self.cs["power"]
            )
            self.r.p.capacityFactor = (
                self.r.p.availabilityFactor * self.powerFractions[cycle][timeNode]
            )
            self.r.p.stepLength = self.stepLengths[cycle][timeNode]

            self._timeNodeLoop(cycle, timeNode)
        else:  # do one last node at the end using the same power as the previous node
            timeNode = self.burnSteps[cycle]
            self._timeNodeLoop(cycle, timeNode)

        self.interactAllEOC(self.r.p.cycle)

        return True

    def _timeNodeLoop(self, cycle, timeNode):
        """Run the portion of the main loop that happens each subcycle."""
        self.r.p.timeNode = timeNode
        self.interactAllEveryNode(cycle, timeNode)
        # perform tight coupling if requested
        if self.cs["numCoupledIterations"]:
            for coupledIteration in range(self.cs["numCoupledIterations"]):
                self.r.core.p.coupledIteration = coupledIteration + 1
                self.interactAllCoupled(coupledIteration)

    def _interactAll(self, interactionName, activeInterfaces, *args):
        """
        Loop over the supplied activeInterfaces and perform the supplied interaction on each.

        Notes
        -----
        This is the base method for the other ``interactAll`` methods.
        """
        interactMethodName = "interact{}".format(interactionName)

        printMemUsage = self.cs["verbosity"] == "debug" and self.cs["debugMem"]
        if self.cs["debugDB"]:
            self._debugDB(interactionName, "start", 0)

        halt = False

        cycleNodeTag = self._expandCycleAndTimeNodeArgs(*args)
        runLog.header(
            "===========  Triggering {} Event ===========".format(
                interactionName + cycleNodeTag
            )
        )

        for statePointIndex, interface in enumerate(activeInterfaces, start=1):
            self.printInterfaceSummary(
                interface, interactionName, statePointIndex, *args
            )

            # maybe make this a context manager
            if printMemUsage:
                memBefore = memoryProfiler.PrintSystemMemoryUsageAction()
                memBefore.broadcast()
                memBefore.invoke(self, self.r, self.cs)

            interactionMessage = " {} interacting with {} ".format(
                interactionName, interface.name
            )
            with self.timer.getTimer(interactionMessage):
                interactMethod = getattr(interface, interactMethodName)
                halt = halt or interactMethod(*args)

            if self.cs["debugDB"]:
                self._debugDB(interactionName, interface.name, statePointIndex)

            if printMemUsage:
                memAfter = memoryProfiler.PrintSystemMemoryUsageAction()
                memAfter.broadcast()
                memAfter.invoke(self, self.r, self.cs)
                memAfter -= memBefore
                memAfter.printUsage(
                    "after {:25s} {:15s} interaction".format(
                        interface.name, interactionName
                    )
                )

            self._checkCsConsistency()

        runLog.header(
            "===========  Completed {} Event ===========\n".format(
                interactionName + cycleNodeTag
            )
        )

        return halt

    def printInterfaceSummary(self, interface, interactionName, statePointIndex, *args):
        """
        Log which interaction point is about to be executed.

        This looks better as multiple lines but it's a lot easier to grep as one line.
        We leverage newlines instead of long banners to save disk space.
        """
        nodeInfo = self._expandCycleAndTimeNodeArgs(*args)
        line = "=========== {:02d} - {:30s} {:15s} ===========".format(
            statePointIndex, interface.name, interactionName + nodeInfo
        )
        runLog.header(line)

    @staticmethod
    def _expandCycleAndTimeNodeArgs(*args):
        """Return text annotating the (cycle, time node) args for each that are present."""
        cycleNodeInfo = ""
        for label, step in zip((" - cycle {}", ", node {}"), args):
            cycleNodeInfo += label.format(step)
        return cycleNodeInfo

    def _debugDB(self, interactionName, interfaceName, statePointIndex=0):
        """
        Write state to DB with a unique "statePointName", or label.

        Notes
        -----
        Used within _interactAll to write details between each physics interaction when cs['debugDB'] is enabled.

        Parameters
        ----------
        interactionName : str
            name of the interaction (e.g. BOL, BOC, EveryNode)
        interfaceName : str
            name of the interface that is interacting (e.g. globalflux, lattice, th)
        statePointIndex : int (optional)
            used as a counter to make labels that increment throughout an _interactAll call. The result should be fed
            into the next call to ensure labels increment.
        """
        dbiForDetailedWrite = self.getInterface("database")
        db = dbiForDetailedWrite.database if dbiForDetailedWrite is not None else None

        if db is not None and db.isOpen():
            # looks something like "c00t00-BOL-01-main"
            statePointName = "c{:2<0}t{:2<0}-{}-{:2<0}-{}".format(
                self.r.p.cycle,
                self.r.p.timeNode,
                interactionName,
                statePointIndex,
                interfaceName,
            )
            db.writeStateToDB(self.r, statePointName=statePointName)

    def _checkCsConsistency(self):
        """Debugging check to verify that CS objects are not unexpectedly multiplying."""
        cs = settings.getMasterCs()
        wrong = (self.cs is not cs) or any((i.cs is not cs) for i in self.interfaces)
        if wrong:
            msg = ["Master cs ID is {}".format(id(cs))]
            for i in self.interfaces:
                msg.append("{:30s} has cs ID: {:12d}".format(str(i), id(i.cs)))
            msg.append("{:30s} has cs ID: {:12d}".format(str(self), id(self.cs)))
            raise RuntimeError("\n".join(msg))

        runLog.debug(
            "Reactors, operators, and interfaces all share master cs: {}".format(id(cs))
        )

    def interactAllInit(self):
        """Call interactInit on all interfaces in the stack after they are initialized."""
        allInterfaces = self.interfaces[:]  # copy just in case
        self._interactAll("Init", allInterfaces)

    def interactAllBOL(self, excludedInterfaceNames=()):
        """
        Call interactBOL for all interfaces in the interface stack at beginning-of-life.

        All enabled or bolForce interfaces will be called excluding interfaces with excludedInterfaceNames.
        """
        activeInterfaces = [
            ii
            for ii in self.interfaces
            if (ii.enabled() or ii.bolForce()) and not ii.name in excludedInterfaceNames
        ]
        activeInterfaces = [
            ii
            for ii in activeInterfaces
            if ii.name not in self.cs["deferredInterfaceNames"]
        ]
        self._interactAll("BOL", activeInterfaces)

    def interactAllBOC(self, cycle):
        """Interact at beginning of cycle of all enabled interfaces."""
        activeInterfaces = [ii for ii in self.interfaces if ii.enabled()]
        if cycle < self.cs["deferredInterfacesCycle"]:
            activeInterfaces = [
                ii
                for ii in activeInterfaces
                if ii.name not in self.cs["deferredInterfaceNames"]
            ]
        return self._interactAll("BOC", activeInterfaces, cycle)

    def interactAllEveryNode(self, cycle, tn, excludedInterfaceNames=None):
        """
        Call the interactEveryNode hook for all enabled interfaces.

        All enabled interfaces will be called excluding interfaces with excludedInterfaceNames.

        Parameters
        ----------
        cycle : int
            The cycle that is currently being run. Starts at 0
        tn : int
            The time node that is currently being run (0 for BOC, etc.)
        excludedInterfaceNames : list, optional
            Names of interface names that will not be interacted with.

        """
        excludedInterfaceNames = excludedInterfaceNames or ()
        activeInterfaces = [
            ii
            for ii in self.interfaces
            if ii.enabled() and ii.name not in excludedInterfaceNames
        ]
        self._interactAll("EveryNode", activeInterfaces, cycle, tn)

    def interactAllEOC(self, cycle, excludedInterfaceNames=None):
        """Interact end of cycle for all enabled interfaces."""
        excludedInterfaceNames = excludedInterfaceNames or ()
        activeInterfaces = [
            ii
            for ii in self.interfaces
            if ii.enabled() and ii.name not in excludedInterfaceNames
        ]
        self._interactAll("EOC", activeInterfaces, cycle)

    def interactAllEOL(self):
        """
        Run interactEOL for all enabled interfaces.

        Notes
        -----
        If the interfaces are flagged to be reversed at EOL, they are separated from the main stack and appended
        at the end in reverse order. This allows, for example, an interface that must run first to also run last.
        """
        activeInterfaces = [ii for ii in self.interfaces if ii.enabled()]
        interfacesAtEOL = [ii for ii in activeInterfaces if not ii.reverseAtEOL]
        activeReverseInterfaces = [ii for ii in activeInterfaces if ii.reverseAtEOL]
        interfacesAtEOL.extend(reversed(activeReverseInterfaces))
        self._interactAll("EOL", interfacesAtEOL)

    def interactAllCoupled(self, coupledIteration):
        """
        Interact for tight physics coupling over all enabled interfaces.

        Tight coupling implies operator-split iterations between two or more physics solvers at the same solution
        point in time. For example, a flux solution might be computed, then a temperature solution, and then
        another flux solution based on updated temperatures (which updated densities, dimensions, and Doppler).

        This is distinct from loose coupling, which would simply uses the temperature values from the previous timestep
        in the current flux solution. It's also distinct from full coupling where all fields are solved simultaneously.
        ARMI supports tight and loose coupling.
        """
        activeInterfaces = [ii for ii in self.interfaces if ii.enabled()]
        self._interactAll("Coupled", activeInterfaces, coupledIteration)

    def interactAllError(self):
        """Interact when an error is raised by any other interface. Provides a wrap-up option on the way to a crash."""
        for i in self.interfaces:
            runLog.extra("Error-interacting with {0}".format(i.name))
            i.interactError()

    def createInterfaces(self):
        """
        Dynamically discover all available interfaces and call their factories, potentially adding
        them to the stack.

        An operator contains an ordered list of interfaces. These communicate between
        the core ARMI structure and auxiliary computational modules and/or external codes.
        At specified interaction points in a run, the list of interfaces is executed.

        Each interface optionally defines interaction "hooks" for each of the interaction points.
        The normal interaction points are BOL, BOC, every node, EOC, and EOL. If an interface defines
        an interactBOL method, that will run at BOL, and so on.

        The majority of ARMI capabilities lie within interfaces, and this architecture provides
        much of the flexibility of ARMI.

        See Also
        --------
        addInterface : Adds a particular interface to the interface stack.
        armi.interfaces.STACK_ORDER : A system to determine the required order of interfaces.
        armi.interfaces.getActiveInterfaceInfo : Collects the interface classes from relevant
            packages.
        """
        interfaceList = interfaces.getActiveInterfaceInfo(self.cs)

        for klass, kwargs in interfaceList:
            self.addInterface(klass(self.r, self.cs), **kwargs)

    def addInterface(
        self,
        interface,
        index=None,
        reverseAtEOL=False,
        enabled=True,
        bolForce=False,
    ):
        """
        Attach an interface to this operator.

        Notes
        -----
        Order matters.

        Parameters
        ----------
        interface : Interface
            the interface to add
        index : int, optional. Will insert the interface at this index rather than appending it to the end of
            the list
        reverseAtEOL : bool, optional.
            The interactEOL hooks will run in reverse order if True. All interfaces with this flag will be run
            as a group after all other interfaces.
            This allows something to run first at BOL and last at EOL, etc.
        enabled : bool, optional
            If enabled, will run at all hooks. If not, won't run any (with possible exception at BOL, see bolForce).
            Whenever possible, Interfaces that are needed during runtime for some peripheral
            operation but not during the main loop should be instantiated by the
            part of the code that actually needs the interface.
        bolForce: bool, optional
            If true, will run at BOL hook even if disabled. This is often a sign
            that the interface in question should be ephemerally instantiated on demand
            rather than added to the interface stack at all.

        Raises
        ------
        RuntimeError
            If an interface of the same name or function is already attached to the
            Operator.
        """

        if self.getInterface(interface.name):
            raise RuntimeError(
                "An interface with name {0} is already attached.".format(interface.name)
            )

        iFunc = self.getInterface(function=interface.function)

        if iFunc:
            if issubclass(type(iFunc), type(interface)):
                runLog.info(
                    "Ignoring Interface {newFunc} because existing interface {old} already "
                    " more specific".format(newFunc=interface, old=iFunc)
                )
                return
            elif issubclass(type(interface), type(iFunc)):
                self.removeInterface(iFunc)
                runLog.info(
                    "Will Insert Interface {newFunc} because it is a subclass of {old} interface and "
                    " more derived".format(newFunc=interface, old=iFunc)
                )
            else:
                raise RuntimeError(
                    "Cannot add {0}; the {1} already is designated "
                    "as the {2} interface. Multiple interfaces of the same "
                    "function is not supported.".format(
                        interface, iFunc, interface.function
                    )
                )

        runLog.debug("Adding {0}".format(interface))
        if index is None:
            self.interfaces.append(interface)
        else:
            self.interfaces.insert(index, interface)
        if reverseAtEOL:
            interface.reverseAtEOL = True

        if not enabled:
            interface.enabled(False)

        interface.bolForce(bolForce)
        interface.attachReactor(self, self.r)

    def _processInterfaceDependencies(self):
        """
        Check all interfaces' dependencies and adds missing ones.

        Notes
        -----
        Order does not matter here because the interfaces added here are disabled and playing supporting
        role so it is not intended to run on the interface stack. They will be called by other interfaces.

        As mentioned in :py:meth:`addInterface`, it may be better to just insantiate utility code
        when its needed rather than rely on this system.
        """
        # Make multiple passes in case there's one added that depends on another.
        for _dependencyPass in range(5):
            numInterfaces = len(self.interfaces)
            # manipulation friendly, so it's ok to add additional things to the stack
            for i in self.getInterfaces():
                for dependency in i.getDependencies(self.cs):
                    name = dependency.name
                    function = dependency.function
                    klass = dependency

                    if not self.getInterface(name, function=function):
                        runLog.extra(
                            "Attaching {} interface (disabled, BOL forced) due to dependency in {}".format(
                                klass.name, i.name
                            )
                        )
                        self.addInterface(
                            klass(r=self.r, cs=self.cs), enabled=False, bolForce=True
                        )
            if len(self.interfaces) == numInterfaces:
                break
        else:
            raise RuntimeError("Interface dependency resolution did not converge.")

    def removeAllInterfaces(self):
        """Removes all of the interfaces"""
        for interface in self.interfaces:
            interface.detachReactor()
        self.interfaces = []

    def removeInterface(self, interface=None, interfaceName=None):
        """
        Remove a single interface from the interface stack.

        Parameters
        ----------
        interface : Interface, optional
            An actual interface object to remove.
        interfaceName : str, optional
            The name of the interface to remove.

        Returns
        -------
        success : boolean
            True if the interface was removed
            False if it was not (because it wasn't there to be removed)

        """
        if interfaceName:
            interface = self.getInterface(interfaceName)

        if interface and interface in self.interfaces:
            self.interfaces.remove(interface)
            interface.detachReactor()
            return True
        else:
            runLog.warning(
                "Cannot remove interface {0} because it is not in the interface stack.".format(
                    interface
                )
            )
            return False

    def getInterface(self, name=None, function=None):
        """
        Returns a specific interface from the stack by its name or more generic function.

        Parameters
        ----------
        name : str, optional
            Interface name
        function : str
            Interface function (general, like 'globalFlux','th',etc.). This is useful when you need
            the ___ solver (e.g. globalFlux) but don't care which particular one is active (e.g. SERPENT vs. DIF3D)

        Raises
        ------
        RuntimeError
            If there are more than one interfaces of the given name or function.
        """
        candidateI = None
        for i in self.interfaces:
            if (name and i.name == name) or (function and i.function == function):
                if candidateI is None:
                    candidateI = i
                else:
                    raise RuntimeError(
                        "Cannot retrieve a single interface as there are multiple "
                        "interfaces with name {} or function {} attached. ".format(
                            name, function
                        )
                    )

        return candidateI

    def interfaceIsActive(self, name):
        """True if named interface exists and is active."""
        i = self.getInterface(name)
        return i and i.enabled()

    def getInterfaces(self):
        """
        Get list of interfaces in interface stack.

        Notes
        -----
        Returns a copy so you can manipulate the list in an interface, like dependencies.
        """
        return self.interfaces[:]

    def reattach(self, r, cs=None):
        """Add links to globally-shared objects to this operator and all interfaces.

        Notes
        -----
        Could be a good opportunity for weakrefs.
        """
        self.r = r
        self.r.o = self
        if cs is not None:
            self.cs = cs
        for i in self.interfaces:
            i.r = r
            i.o = self
            if cs is not None:
                i.cs = cs

    def detach(self):
        """
        Break links to globally-shared objects to this operator and all interfaces.

        May be required prior to copying these objects over the network.

        Notes
        -----
        Could be a good opportunity for weakrefs.
        """
        if self.r:
            self.r.o = None
        self.r = None
        for i in self.interfaces:
            i.o = None
            i.r = None
            i.cs = None

    def _attachInterfaces(self):
        """
        Links all the interfaces in the interface stack to the operator, reactor, and cs.

        See Also
        --------
        createInterfaces : creates all interfaces
        addInterface : adds a single interface to the stack

        """
        for i in self.interfaces:
            i.attachReactor(self, self.r)

    def dumpRestartData(self, cycle, time_, factorList):
        """
        Write some information about the cycle and shuffling to a auxiliary file for potential restarting.

        Notes
        -----
        This is old and can be deprecated now that the database contains
        the entire state. This was historically needed to have complete information regarding
        shuffling when figuring out ideal fuel management operations.
        """
        if cycle >= len(self.restartData):
            self.restartData.append((cycle, time_, factorList))
        else:
            # try to preserve loaded restartdata so we don't lose it in restarts.
            self.restartData[cycle] = (cycle, time_, factorList)
        with open(self.cs.caseTitle + ".restart.dat", "w") as restart:
            for info in self.restartData:
                restart.write("cycle=%d   time=%10.6E   factorList=%s\n" % info)

    def _loadRestartData(self):
        """
        Read a restart.dat file which contains all the fuel management factorLists and cycle lengths.

        Notes
        -----
        This allows the ARMI to do the same shuffles that it did last time, assuming fuel management logic
        has not changed. Note, it would be better if the moves were just read from a table in the database.

        """
        restartName = self.cs.caseTitle + ".restart.dat"
        if not os.path.exists(restartName):
            return
        else:
            runLog.info("Loading restart data from {}".format(restartName))

        with open(restartName, "r") as restart:
            for line in restart:
                match = re.search(
                    r"cycle=(\d+)\s+time=(\d+\.\d+[Ee+-]+\d+)\s+factorList=[\[\{](.+?)[\]\}]",
                    line,
                )
                if match:
                    newStyle = re.findall(r"'(\w+)':\s*(\d*\.?\d*)", line)
                    if newStyle:
                        # key-based factorList. load a dictionary.
                        factorList = {}
                        for key, val in newStyle:
                            factorList[key] = float(val)
                    else:
                        # list based factorList. Load a list. (old style, backward compat)
                        try:
                            factorList = [
                                float(item) for item in match.group(3).split(",")
                            ]
                        except ValueError:
                            factorList = match.group(3).split(",")
                    runLog.debug(
                        "loaded restart data for cycle %d" % float(match.group(1))
                    )

                    self.restartData.append(
                        (float(match.group(1)), float(match.group(2)), factorList)
                    )
        runLog.info("loaded restart data for {0} cycles".format(len(self.restartData)))

    def loadState(
        self, cycle, timeNode, timeStepName="", fileName=None, updateMassFractions=None
    ):
        """
        Convenience method reroute to the database interface state reload method

        See also
        --------
        armi.bookeeping.db.loadOperator:
            A method for loading an operator given a database. loadOperator does not
            require an operator prior to loading the state of the reactor. loadState
            does, and therefore armi.init must be called which requires access to the
            blueprints, settings, and geometry files. These files are stored implicitly
            on the database, so loadOperator creates the reactor first, and then attaches
            it to the operator. loadState should be used if you are in the middle
            of an ARMI calculation and need load a different time step. If you are
            loading from a fresh ARMI session, either method is sufficient if you have
            access to all the input files.
        """
        dbi = self.getInterface("database")
        if not dbi:
            raise RuntimeError("Cannot load from snapshot without a database interface")

        if updateMassFractions is not None:
            runLog.warning(
                "deprecated: updateMassFractions is no longer a valid option for loadState"
            )

        dbi.loadState(cycle, timeNode, timeStepName, fileName)

    def snapshotRequest(self, cycle, node):
        """
        Process a snapshot request at this time.

        This copies various physics input and output files to a special folder that
        follow-on analysis be executed upon later.

        Notes
        -----
        This was originally used to produce MC2/DIF3D inputs for external
        parties (who didn't have ARMI) to review. Since then, the concept
        of snapshots has evolved with respect to the
        :py:class:`~armi.operators.snapshots.OperatorSnapshots`.
        """
        runLog.info("Producing snapshot for cycle {0} node {1}".format(cycle, node))
        self.r.core.zones.summary()

        newFolder = "snapShot{0}_{1}".format(cycle, node)
        if os.path.exists(newFolder):
            runLog.important("Deleting existing snapshot data in {0}".format(newFolder))
            pathTools.cleanPath(newFolder, context.MPI_RANK)  # careful with cleanPath!
            # give it a minute.
            time.sleep(1)

        if os.path.exists(newFolder):
            runLog.warning(
                "Deleting existing snapshot data in {0} failed".format(newFolder)
            )
        else:
            os.mkdir(newFolder)

        # copy the cross section inputs
        for fileName in os.listdir("."):
            if "mcc" in fileName and re.search(r"[A-Z]AF?\d?.inp", fileName):
                base, ext = os.path.splitext(fileName)
                # add the cycle and timenode to the XS input file names so that a rx-coeff case that runs
                # in here won't overwrite them.
                shutil.copy(
                    fileName,
                    os.path.join(
                        newFolder, "{0}_{1:03d}_{2:d}{3}".format(base, cycle, node, ext)
                    ),
                )

        isoFName = "ISOTXS-c{0}".format(cycle)
        pathTools.copyOrWarn(
            "ISOTXS for snapshot", isoFName, pathTools.armiAbsPath(newFolder, "ISOTXS")
        )
        pathTools.copyOrWarn(
            "DIF3D output for snapshot",
            self.cs.caseTitle + "{0:03d}.out".format(cycle),
            newFolder,
        )
        pathTools.copyOrWarn(
            "Shuffle logic for snapshot", self.cs["shuffleLogic"], newFolder
        )
        pathTools.copyOrWarn(
            "Geometry file for snapshot", self.cs["geomFile"], newFolder
        )
        pathTools.copyOrWarn(
            "Loading definition for snapshot", self.cs["loadingFile"], newFolder
        )
        pathTools.copyOrWarn(
            "Flow history for snapshot",
            self.cs.caseTitle + ".flow_history.txt",
            newFolder,
        )
        pathTools.copyOrWarn(
            "Pressure history for snapshot",
            self.cs.caseTitle + ".pressure_history.txt",
            newFolder,
        )

    @staticmethod
    def setStateToDefault(cs):
        """Update the state of ARMI to fit the kind of run this operator manages"""
        return cs.modified(newSettings={"runType": RunTypes.STANDARD})

    def couplingIsActive(self):
        """True if any kind of physics coupling is active."""
        return self.cs["looseCoupling"] or self.cs["numCoupledIterations"] > 0
