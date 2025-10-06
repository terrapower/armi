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

This builds and maintains the interface stack and loops through it for a certain number of cycles with a certain number
of timenodes per cycle.

This is analogous to a real reactor operating over some period of time, often from initial startup, through the various
cycles, and out to the end of plant life.
"""

import collections
import os
import re
import time
from typing import Tuple

from armi import context, getPluginManagerOrFail, interfaces, runLog
from armi.bookkeeping import memoryProfiler
from armi.bookkeeping.report import reportingUtils
from armi.operators.runTypes import RunTypes
from armi.physics.fuelCycle.settings import CONF_SHUFFLE_LOGIC
from armi.physics.neutronics.globalFlux.globalFluxInterface import (
    GlobalFluxInterfaceUsingExecuters,
)
from armi.settings import settingsValidation
from armi.settings.fwSettings.globalSettings import (
    CONF_CYCLES_SKIP_TIGHT_COUPLING_INTERACTION,
    CONF_DEFERRED_INTERFACE_NAMES,
    CONF_DEFERRED_INTERFACES_CYCLE,
    CONF_TIGHT_COUPLING,
    CONF_TIGHT_COUPLING_MAX_ITERS,
)
from armi.utils import (
    codeTiming,
    getAvailabilityFactors,
    getBurnSteps,
    getCycleLengths,
    getCycleNames,
    getMaxBurnSteps,
    getPowerFractions,
    getPreviousTimeNode,
    getStepLengths,
    pathTools,
    units,
)


class Operator:
    """
    Orchestrate an ARMI run, building all the pieces, looping through the interfaces, and manipulating the reactor.

    This Operator loops over a user-input number of cycles, each with a user-input number of subcycles (called time
    nodes). It calls a series of interaction hooks on each of the :py:class:`~armi.interfaces.Interface` in the
    Interface Stack.

    .. figure:: /.static/armi_general_flowchart.png
        :align: center

    **Figure 1.** The computational flow of the interface hooks in a Standard Operator

    .. note:: The :doc:`/developer/guide` has some additional narrative on this topic.

    .. impl:: An operator will have a reactor object to communicate between plugins.
        :id: I_ARMI_OPERATOR_COMM
        :implements: R_ARMI_OPERATOR_COMM

        A major design feature of ARMI is that the Operator orchestrates the simulation, and as part of that, the
        Operator has access to the Reactor data model. In code, this just means the reactor object is a mandatory
        attribute of an instance of the Operator. But conceptually, this means that while the Operator drives the
        simulation of the reactor, all code has access to the same copy of the reactor data model. This is a crucial
        idea that allows disparate external nuclear models to interact; they interact with the ARMI reactor data model.

    .. impl:: An operator is built from user settings.
        :id: I_ARMI_OPERATOR_SETTINGS
        :implements: R_ARMI_OPERATOR_SETTINGS

        A major design feature of ARMI is that a run is built from user settings. In code, this means that a case
        ``Settings`` object is passed into this class to initialize an Operator. Conceptually, this means that the
        Operator that controls a reactor simulation is defined by user settings. Because developers can create their own
        settings, the user can control an ARMI simulation with arbitrary granularity in this way. In practice, settings
        common control things like: how many cycles a reactor is being modeled for, how many timesteps are to be modeled
        per time node, the verbosity of the logging of the run, and which modeling steps will be run.


    .. impl:: The operator shall advance the reactor through time.
        :id: I_ARMI_DB_TIME2
        :implements: R_ARMI_DB_TIME

        A major design feature of any scientific model is time evolution of the physical system. The operator is in
        charge of driving the reactor through time. It sets various parameters that define the temporal position of the
        reactor: cycle, node, timeNode, and time. This information is then stored in the output database.


    Attributes
    ----------
    cs : Settings
            Global settings that define the run.

    cycleNames : list of str
        The name of each cycle. Cycles without a name are `None`.

    stepLengths : list of list of float
        A two-tiered list, where primary indices correspond to cycle and
        secondary indices correspond to the length of each intra-cycle step (in days).

    cycleLengths : list of float
        The duration of each individual cycle in a run (in days). This is the entire cycle, from startup to startup and
        includes outage time.

    burnSteps : list of int
        The number of sub-cycles in each cycle.

    availabilityFactors : list of float
        The fraction of time in a cycle that the plant is producing power. Note that capacity factor is always less than
        or equal to this, depending on the power fraction achieved during each cycle. Note that this is not a two-tiered
        list like stepLengths or powerFractions, because each cycle can have only one availabilityFactor.

    powerFractions : list of list of float
        A two-tiered list, where primary indices correspond to cycles and secondary indices correspond to the fraction
        of full rated capacity that the plant achieves during that step of the cycle. Zero power fraction can indicate
        decay-only cycles.

    interfaces : list
        The Interface objects that will operate upon the reactor
    """

    inspector = settingsValidation.Inspector

    def __init__(self, cs):
        """
        Constructor for operator.

        Parameters
        ----------
        cs : Settings
            Global settings that define the run.

        Raises
        ------
        OSError
            If unable to create the FAST_PATH directory.
        """
        self.r = None
        self.cs = cs
        runLog.LOG.startLog(self.cs.caseTitle)
        self.timer = codeTiming.MasterTimer.getMasterTimer()
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
        self._convergenceSummary = None

        # Create the welcome headers for the case (case, input, machine, and some basic reactor information)
        reportingUtils.writeWelcomeHeaders(self, cs)

        self._initFastPath()

    @property
    def burnSteps(self):
        if not self._burnSteps:
            self._burnSteps = getBurnSteps(self.cs)
            if self._burnSteps == [] and self.cs["nCycles"] == 1:
                # it is possible for there to be one cycle with zero burn up, in which case burnSteps is an empty list
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
        """
        Calculate step lengths.

        .. impl:: Calculate step lengths from cycles and burn steps.
            :id: I_ARMI_FW_HISTORY
            :implements: R_ARMI_FW_HISTORY

            In all computational modeling of physical systems, it is necessary to break time into discrete chunks. In
            reactor modeling, it is common to first break the time a reactor is simulated for into the practical cycles
            the reactor runs. And then those cycles are broken down into smaller chunks called burn steps. The final
            step lengths this method returns is a two-tiered list, where primary indices correspond to the cycle and
            secondary indices correspond to the length of each intra-cycle step (in days).
        """
        if not self._stepLengths:
            self._stepLengths = getStepLengths(self.cs)
            if self._stepLengths == [] and self.cs["nCycles"] == 1:
                # it is possible for there to be one cycle with zero burn up, in which case stepLengths is an empty list
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
            self._checkReactorCycleAttrs({"availabilityFactors": self._availabilityFactors})
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
        Create the FAST_PATH directory for fast local operations.

        Notes
        -----
        The FAST_PATH was once created at import-time in order to support modules that use FAST_PATH without operators
        (e.g. Database). However, we decided to leave FAST_PATH as the CWD in INTERACTIVE mode, so this should not be a
        problem anymore, and we can safely move FAST_PATH creation back into the Operator.

        If the operator is being used interactively (e.g. at a prompt) we will still use a temporary local fast path (in
        case the user is working on a slow network path).
        """
        context.activateLocalFastPath()
        try:
            os.makedirs(context.getFastPath())
        except OSError:
            # If FAST_PATH exists already that generally should be an error because different processes will be stepping
            # on each other. The exception to this rule is in cases that instantiate multiple operators in one process
            # (e.g. unit tests that loadTestReactor). Since the FAST_PATH is set at import, these will use the same path
            # multiple times. We pass here for that reason.
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
                    "Current input: {}".format(name, self.cs["nCycles"], len(param), param)
                )

    def _consistentPowerFractionsAndStepLengths(self):
        """Check that the internally-resolved _powerFractions and _stepLengths have consistent shapes, if they exist."""
        if self._powerFractions and self._stepLengths:
            for cycleIdx in range(len(self._powerFractions)):
                if len(self._powerFractions[cycleIdx]) != len(self._stepLengths[cycleIdx]):
                    raise ValueError(
                        "The number of entries in lists for subcycle power fractions and sub-steps are inconsistent in "
                        f"cycle {cycleIdx}"
                    )

    @property
    def atEOL(self):
        """
        Return whether we are approaching EOL.

        For the standard operator, this will return true when the current cycle is the last cycle
        (cs["nCycles"] - 1). Other operators may need to impose different logic.
        """
        return self.r.p.cycle == self.cs["nCycles"] - 1

    def initializeInterfaces(self, r):
        """
        Attach the reactor to the operator and initialize all interfaces.

        This does not occur in `__init__` so that the ARMI operator can be initialized before a reactor is created,
        which is useful for summarizing the case information quickly.

        Parameters
        ----------
        r : Reactor
            The Reactor object to attach to this Operator.
        """
        self.r = r
        r.o = self
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
            runLog.error(r"{}\n{}\{}".format(exception_type, exception_value, stacktrace))
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
        """Main loop for a standard ARMI run. Steps through time interacting with the interfaces."""
        dbi = self.getInterface("database")
        if dbi.enabled():
            dbi.initDB()
        if self.cs["loadStyle"] != "fromInput" and self.cs["runType"] != RunTypes.SNAPSHOTS:
            self._onRestart()
        self.interactAllBOL()
        startingCycle = self.r.p.cycle  # may be starting at t != 0 in restarts
        for cycle in range(startingCycle, self.cs["nCycles"]):
            keepGoing = self._cycleLoop(cycle, startingCycle)
            if not keepGoing:
                break
        self.interactAllEOL()

    def _onRestart(self):
        startCycle = self.cs["startCycle"]
        startNode = self.cs["startNode"]
        prevTimeNode = getPreviousTimeNode(startCycle, startNode, self.cs)

        pm = getPluginManagerOrFail()

        pm.hook.prepRestart(o=self, startTime=(startCycle, startNode), previousTime=prevTimeNode)

        if startNode == 0:
            runLog.important("Calling `o.interactAllEOC` due to loading the last time node of the previous cycle.")
            self.interactAllEOC(self.r.p.cycle)

        # advance time time since we loaded the previous time step
        self.r.p.cycle = startCycle
        self.r.p.timeNode = startNode

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

        # read total core power from settings (power or powerDensity)
        basicPower = self.cs["power"] or (self.cs["powerDensity"] * self.r.core.getHMMass())

        for timeNode in range(startingNode, int(self.burnSteps[cycle])):
            self.r.core.p.power = self.powerFractions[cycle][timeNode] * basicPower
            self.r.p.capacityFactor = self.r.p.availabilityFactor * self.powerFractions[cycle][timeNode]
            self.r.p.stepLength = self.stepLengths[cycle][timeNode]

            self._timeNodeLoop(cycle, timeNode)
        else:  # do one last node at the end using the same power as the previous node
            timeNode = self.burnSteps[cycle]
            if self.burnSteps[cycle] == 0:
                # this is a zero-burnup case
                powFrac = 1
            else:
                powFrac = self.powerFractions[cycle][timeNode - 1]

            self.r.core.p.power = powFrac * basicPower
            self._timeNodeLoop(cycle, timeNode)

        self.interactAllEOC(self.r.p.cycle)

        return True

    def _timeNodeLoop(self, cycle, timeNode):
        """Run the portion of the main loop that happens each subcycle."""
        self.r.p.timeNode = timeNode
        if timeNode == 0:
            dt = 0
        else:
            dt = self.r.o.stepLengths[cycle][timeNode - 1] / units.DAYS_PER_YEAR
        self.r.p.time = self.r.p.time + dt

        self.interactAllEveryNode(cycle, timeNode)
        self._performTightCoupling(cycle, timeNode)

    def _performTightCoupling(self, cycle: int, timeNode: int, writeDB: bool = True):
        """If requested, perform tight coupling and write out database.

        Notes
        -----
        writeDB is False for OperatorSnapshots as the DB gets written at EOL.
        """
        if not self.couplingIsActive():
            # no coupling was requested
            return
        skipCycles = tuple(int(val) for val in self.cs[CONF_CYCLES_SKIP_TIGHT_COUPLING_INTERACTION])
        if cycle in skipCycles:
            runLog.warning(
                f"interactAllCoupled disabled this cycle ({self.r.p.cycle}) due to "
                "`cyclesSkipTightCouplingInteraction` setting."
            )
        else:
            self._convergenceSummary = collections.defaultdict(list)
            for coupledIteration in range(self.cs[CONF_TIGHT_COUPLING_MAX_ITERS]):
                self.r.core.p.coupledIteration = coupledIteration + 1
                converged = self.interactAllCoupled(coupledIteration)
                if converged:
                    runLog.important(f"Tight coupling iterations for c{cycle:02d}n{timeNode:02d} have converged!")
                    break
            if not converged:
                runLog.warning(
                    f"Tight coupling iterations for c{cycle:02d}n{timeNode:02d} have not converged!"
                    f" The maximum number of iterations, {self.cs[CONF_TIGHT_COUPLING_MAX_ITERS]}, was reached."
                )
        if writeDB:
            # database has not yet been written, so we need to write it.
            dbi = self.getInterface("database")
            dbi.writeDBEveryNode()

    def _interactAll(self, interactionName, activeInterfaces, *args):
        """
        Loop over the supplied activeInterfaces and perform the supplied interaction on each.

        Notes
        -----
        This is the base method for the other ``interactAll`` methods.
        """
        interactMethodName = "interact{}".format(interactionName)

        printMemUsage = self.cs["verbosity"] == "debug" and self.cs["debugMem"]

        halt = False

        cycleNodeTag = self._expandCycleAndTimeNodeArgs(interactionName)
        runLog.header("===========  Triggering {} Event ===========".format(interactionName + cycleNodeTag))

        for statePointIndex, interface in enumerate(activeInterfaces, start=1):
            self.printInterfaceSummary(interface, interactionName, statePointIndex)

            # maybe make this a context manager
            if printMemUsage:
                memBefore = memoryProfiler.PrintSystemMemoryUsageAction()
                memBefore.broadcast()
                memBefore.invoke(self, self.r, self.cs)

            interactionMessage = f"{interface.name}.{interactionName}"
            with self.timer.getTimer(interactionMessage):
                interactMethod = getattr(interface, interactMethodName)
                halt = halt or interactMethod(*args)

            if printMemUsage:
                memAfter = memoryProfiler.PrintSystemMemoryUsageAction()
                memAfter.broadcast()
                memAfter.invoke(self, self.r, self.cs)
                memAfter -= memBefore
                memAfter.printUsage("after {:25s} {:15s} interaction".format(interface.name, interactionName))

            # Allow inherited classes to clean up things after an interaction
            self._finalizeInteract()

        runLog.header("===========  Completed {} Event ===========\n".format(interactionName + cycleNodeTag))

        return halt

    def _finalizeInteract(self):
        """Member called after each interface has completed its interaction.

        Useful for cleaning up data.
        """
        pass

    def printInterfaceSummary(self, interface, interactionName, statePointIndex):
        """
        Log which interaction point is about to be executed.

        This looks better as multiple lines but it's a lot easier to grep as one line. We leverage newlines instead of
        long banners to save disk space.
        """
        nodeInfo = self._expandCycleAndTimeNodeArgs(interactionName)
        line = "=========== {:02d} - {:30s} {:15s} ===========".format(
            statePointIndex, interface.name, interactionName + nodeInfo
        )
        runLog.header(line)

    def _expandCycleAndTimeNodeArgs(self, interactionName):
        """Return text annotating information for current run event.

        Notes
        -----
        - Init, BOL, EOL: empty
        - Everynode: cycle, time node
        - BOC, EOC: cycle number
        - Coupled: cycle, time node, iteration number
        """
        if interactionName == "Coupled":
            cycleNodeInfo = (
                f" - timestep: cycle {self.r.p.cycle}, node {self.r.p.timeNode}, "
                f"year {'{0:.2f}'.format(self.r.p.time)} - iteration "
                f"{self.r.core.p.coupledIteration}"
            )
        elif interactionName in ("BOC", "EOC"):
            cycleNodeInfo = f" - timestep: cycle {self.r.p.cycle}"
            # - timestep: cycle 2
        elif interactionName in ("Init", "BOL", "EOL"):
            cycleNodeInfo = ""
        else:
            cycleNodeInfo = (
                f" - timestep: cycle {self.r.p.cycle}, node {self.r.p.timeNode}, year {'{0:.2f}'.format(self.r.p.time)}"
            )

        return cycleNodeInfo

    def interactAllInit(self):
        """Call interactInit on all interfaces in the stack after they are initialized."""
        self._interactAll("Init", self.getInterfaces())

    def interactAllBOL(self, excludedInterfaceNames=()):
        """
        Call interactBOL for all interfaces in the interface stack at beginning-of-life.

        All enabled or bolForce interfaces will be called excluding interfaces with excludedInterfaceNames.
        """
        activeInterfaces = self.getActiveInterfaces("BOL", excludedInterfaceNames)
        self._interactAll("BOL", activeInterfaces)

    def interactAllBOC(self, cycle):
        """Interact at beginning of cycle of all enabled interfaces."""
        activeInterfaces = self.getActiveInterfaces("BOC", cycle=cycle)
        return self._interactAll("BOC", activeInterfaces, cycle)

    def interactAllEveryNode(self, cycle, tn, excludedInterfaceNames=()):
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
        activeInterfaces = self.getActiveInterfaces("EveryNode", excludedInterfaceNames)
        self._interactAll("EveryNode", activeInterfaces, cycle, tn)

    def interactAllEOC(self, cycle, excludedInterfaceNames=()):
        """Interact end of cycle for all enabled interfaces."""
        self.r.p.time += self.r.p.cycleLength * (1 - self.r.p.availabilityFactor) / units.DAYS_PER_YEAR

        activeInterfaces = self.getActiveInterfaces("EOC", excludedInterfaceNames)
        self._interactAll("EOC", activeInterfaces, cycle)

    def interactAllEOL(self, excludedInterfaceNames=()):
        """
        Run interactEOL for all enabled interfaces.

        Notes
        -----
        If the interfaces are flagged to be reversed at EOL, they are separated from the main stack and appended at the
        end in reverse order. This allows, for example, an interface that must run first to also run last.
        """
        activeInterfaces = self.getActiveInterfaces("EOL", excludedInterfaceNames)
        self._interactAll("EOL", activeInterfaces)

    def interactAllCoupled(self, coupledIteration):
        """
        Run all interfaces that are involved in tight physics coupling.

        .. impl:: Physics coupling is driven from Operator.
            :id: I_ARMI_OPERATOR_PHYSICS1
            :implements: R_ARMI_OPERATOR_PHYSICS

            This method runs all the interfaces that are defined as part of the tight physics coupling of the reactor.
            Then it returns if the coupling has converged or not.

            Tight coupling implies the operator has split iterations between two or more physics solvers at the same
            solution point in simulated time. For example, a flux solution might be computed, then a temperature
            solution, and then another flux solution based on updated temperatures (which updates densities, dimensions,
            and Doppler).

            This is distinct from loose coupling, which simply uses the temperature values from the previous timestep in
            the current flux solution. It's also distinct from full coupling where all fields are solved simultaneously.
            ARMI supports tight and loose coupling.
        """
        activeInterfaces = self.getActiveInterfaces("Coupled")
        # Store the previous iteration values before calling interactAllCoupled for each interface.
        for interface in activeInterfaces:
            if interface.coupler is not None:
                interface.coupler.storePreviousIterationValue(interface.getTightCouplingValue())
        self._interactAll("Coupled", activeInterfaces, coupledIteration)

        return self._checkTightCouplingConvergence(activeInterfaces)

    def _checkTightCouplingConvergence(self, activeInterfaces: list):
        """Check if interfaces are converged.

        Parameters
        ----------
        activeInterfaces : list
            the list of active interfaces on the operator

        Notes
        -----
        This is split off from self.interactAllCoupled to accommodate testing.
        """
        # Summarize the coupled results and the convergence status.
        converged = []
        for interface in activeInterfaces:
            coupler = interface.coupler
            if coupler is not None:
                key = f"{interface.name}: {coupler.parameter}"
                converged.append(coupler.isConverged(interface.getTightCouplingValue()))
                self._convergenceSummary[key].append(coupler.eps)

        reportingUtils.writeTightCouplingConvergenceSummary(self._convergenceSummary)
        return all(converged)

    def interactAllError(self):
        """Interact when an error is raised by any other interface. Provides a wrap-up option on the way to a crash."""
        for i in self.interfaces:
            runLog.extra("Error-interacting with {0}".format(i.name))
            i.interactError()

    def createInterfaces(self):
        """
        Dynamically discover all available interfaces and call their factories, potentially adding them to the stack.

        An operator contains an ordered list of interfaces. These communicate between the core ARMI structure and
        auxiliary computational modules and/or external codes. At specified interaction points in a run, the list of
        interfaces is executed.

        Each interface optionally defines interaction "hooks" for each of the interaction points. The normal interaction
        points are BOL, BOC, every node, EOC, and EOL. If an interface defines an interactBOL method, that will run at
        BOL, and so on.

        The majority of ARMI capabilities lie within interfaces, and this architecture provides much of the flexibility
        of ARMI.

        See Also
        --------
        addInterface : Adds a particular interface to the interface stack.
        armi.interfaces.STACK_ORDER : A system to determine the required order of interfaces.
        armi.interfaces.getActiveInterfaceInfo : Collects the interface classes from relevant packages.
        """
        runLog.header("=========== Creating Interfaces ===========")
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
        index : int, optional. Will insert the interface at this index rather than appending it to the end of the list
        reverseAtEOL : bool, optional.
            The interactEOL hooks will run in reverse order if True. All interfaces with this flag will be run as a
            group after all other interfaces. This allows something to run first at BOL and last at EOL, etc.
        enabled : bool, optional
            If enabled, will run at all hooks. If not, won't run any (with possible exception at BOL, see bolForce).
            Whenever possible, Interfaces that are needed during runtime for some peripheral operation but not during
            the main loop should be instantiated by the part of the code that actually needs the interface.
        bolForce: bool, optional
            If true, will run at BOL hook even if disabled. This is often a sign that the interface in question should
            be ephemerally instantiated on demand rather than added to the interface stack at all.

        Raises
        ------
        RuntimeError
            If an interface of the same name or function is already attached to the Operator.
        """
        if self.getInterface(interface.name):
            raise RuntimeError(f"An interface with name {interface.name} is already attached.")

        iFunc = self.getInterface(function=interface.function)

        if iFunc:
            if issubclass(type(iFunc), type(interface)):
                runLog.info(
                    "Ignoring Interface {newFunc} because existing interface {old} already  more specific".format(
                        newFunc=interface, old=iFunc
                    )
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
                    "function is not supported.".format(interface, iFunc, interface.function)
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
        Order does not matter here because the interfaces added here are disabled and playing supporting role so it is
        not intended to run on the interface stack. They will be called by other interfaces.

        As mentioned in :py:meth:`addInterface`, it may be better to just instantiate utility code when its needed
        rather than rely on this system.
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
                        self.addInterface(klass(r=self.r, cs=self.cs), enabled=False, bolForce=True)
            if len(self.interfaces) == numInterfaces:
                break
        else:
            raise RuntimeError("Interface dependency resolution did not converge.")

    def removeAllInterfaces(self):
        """Removes all of the interfaces."""
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
            runLog.warning("Cannot remove interface {0} because it is not in the interface stack.".format(interface))
            return False

    def getInterface(self, name=None, function=None):
        """
        Returns a specific interface from the stack by its name or more generic function.

        Parameters
        ----------
        name : str, optional
            Interface name
        function : str
            Interface function (general, like 'globalFlux','th',etc.). This is useful when you need the ___ solver (e.g.
            globalFlux) but don't care which particular one is active (e.g. SERPENT vs. DIF3D)

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
                        "interfaces with name {} or function {} attached. ".format(name, function)
                    )

        return candidateI

    def interfaceIsActive(self, name):
        """True if named interface exists and is enabled.

        Notes
        -----
        This logic is significantly simpler that getActiveInterfaces. This logic only touches the enabled() flag, but
        doesn't take into account the case settings.
        """
        i = self.getInterface(name)
        return i and i.enabled()

    def getInterfaces(self):
        """
        Get list of interfaces in interface stack.

        .. impl:: An operator will expose an ordered list of interfaces.
            :id: I_ARMI_OPERATOR_INTERFACES
            :implements: R_ARMI_OPERATOR_INTERFACES

            This method returns an ordered list of instances of the Interface class. This list is useful because at any
            time node in the reactor simulation, these interfaces will be called in sequence to perform various types of
            calculations. It is important to note that this Operator instance has a list of Plugins, and each of those
            Plugins potentially defines multiple Interfaces. And these Interfaces define their own order, separate from
            the ordering of the Plugins.

        Notes
        -----
        Returns a copy so you can manipulate the list in an interface, like dependencies.
        """
        return self.interfaces[:]

    def getActiveInterfaces(
        self,
        interactState: str,
        excludedInterfaceNames: Tuple[str] = (),
        cycle: int = 0,
    ):
        """Retrieve the interfaces which are active for a given interaction state.

        Parameters
        ----------
        interactState: str
            A string dictating which interaction state the interfaces should be pulled for.
        excludedInterfaceNames: Tuple[str]
            A tuple of strings dictating which interfaces should be manually skipped.
        cycle: int
            The given cycle. 0 by default.

        Returns
        -------
        activeInterfaces: List[Interfaces]
            The interfaces deemed active for the given interactState.
        """
        # Validate the inputs
        if excludedInterfaceNames is None:
            excludedInterfaceNames = ()

        if interactState not in ("BOL", "BOC", "EveryNode", "EOC", "EOL", "Coupled"):
            raise ValueError(f"{interactState} is an unknown interaction state!")

        # Ensure the interface is enabled.
        enabled = lambda i: i.enabled()
        if interactState == "BOL":
            enabled = lambda i: i.enabled() or i.bolForce()

        # Ensure the name of the interface isn't in some exclusion list.
        nameCheck = lambda i: True
        if interactState in ("EveryNode", "EOC", "EOL"):
            nameCheck = lambda i: i.name not in excludedInterfaceNames
        elif interactState == "BOC" and cycle < self.cs[CONF_DEFERRED_INTERFACES_CYCLE]:
            nameCheck = lambda i: i.name not in self.cs[CONF_DEFERRED_INTERFACE_NAMES]
        elif interactState == "BOL":
            nameCheck = (
                lambda i: i.name not in self.cs[CONF_DEFERRED_INTERFACE_NAMES] and i.name not in excludedInterfaceNames
            )

        # Finally, find the active interfaces.
        activeInterfaces = [i for i in self.interfaces if enabled(i) and nameCheck(i)]

        # Special Case: At EOL we reverse the order of some interfaces.
        if interactState == "EOL":
            actInts = [ii for ii in activeInterfaces if not ii.reverseAtEOL]
            actInts.extend(reversed([ii for ii in activeInterfaces if ii.reverseAtEOL]))
            activeInterfaces = actInts

        return activeInterfaces

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
            for comp in self.r:
                comp.parent = None
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

    def _loadRestartData(self):
        """
        Read a restart.dat file which contains all the fuel management factorLists and cycle lengths.

        Notes
        -----
        This allows the ARMI to do the same shuffles that it did last time, assuming fuel management logic has not
        changed. Note, it would be better if the moves were just read from a table in the database.
        """
        restartName = self.cs.caseTitle + ".restart.dat"
        if not os.path.exists(restartName):
            return
        else:
            runLog.info(f"Loading restart data from {restartName}")

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
                            factorList = [float(item) for item in match.group(3).split(",")]
                        except ValueError:
                            factorList = match.group(3).split(",")
                    runLog.debug("loaded restart data for cycle %d" % float(match.group(1)))

                    self.restartData.append((float(match.group(1)), float(match.group(2)), factorList))
        runLog.info("loaded restart data for {0} cycles".format(len(self.restartData)))

    def loadState(self, cycle, timeNode, timeStepName="", fileName=None, updateMassFractions=None):
        """
        Convenience method reroute to the database interface state reload method.

        See Also
        --------
        armi.bookkeeping.db.loadOperator:
            A method for loading an operator given a database. loadOperator does not require an operator prior to
            loading the state of the reactor. loadState does, and therefore armi.init must be called which requires
            access to the blueprints, settings, and geometry files. These files are stored implicitly on the database,
            so loadOperator creates the reactor first, and then attaches it to the operator. loadState should be used if
            you are in the middle of an ARMI calculation and need load a different time step. If you are loading from a
            fresh ARMI session, either method is sufficient if you have access to all the input files.
        """
        dbi = self.getInterface("database")
        if not dbi:
            raise RuntimeError("Cannot load from snapshot without a database interface")

        if updateMassFractions is not None:
            runLog.warning("deprecated: updateMassFractions is no longer a valid option for loadState")

        dbi.loadState(cycle, timeNode, timeStepName, fileName)

    def snapshotRequest(self, cycle, node, iteration=None):
        """
        Process a snapshot request at this time.

        This copies various physics input and output files to a special folder that follow-on analysis be executed upon
        later.

        Notes
        -----
        This was originally used to produce MC2/DIF3D inputs for external parties (who didn't have ARMI) to review.
        Since then, the concept of snapshots has evolved with respect to the
        :py:class:`~armi.operators.snapshots.OperatorSnapshots`.
        """
        from armi.physics.neutronics.settings import CONF_LOADING_FILE

        runLog.info(f"Producing snapshot for cycle {cycle} node {node}")
        self.r.core.zones.summary()

        newFolder = f"snapShot{cycle}_{node}"
        if os.path.exists(newFolder):
            runLog.important(f"Deleting existing snapshot data in {newFolder}")
            pathTools.cleanPath(newFolder)  # careful with cleanPath!
            # give it a minute.
            time.sleep(1)

        if os.path.exists(newFolder):
            runLog.warning(f"Deleting existing snapshot data in {newFolder} failed")
        else:
            os.mkdir(newFolder)

        # Moving the cross section files is to a snapshot directory is a reasonable requirement, but these hard-coded
        # names are not desirable. This is legacy and should be updated to be more robust for users.
        for fileName in os.listdir("."):
            if "mcc" in fileName and re.search(r"[A-Z]AF?\d?.inp", fileName):
                base, ext = os.path.splitext(fileName)
                if iteration is not None:
                    newFile = "{0}_{1:03d}_{2:d}_{4}{3}".format(base, cycle, node, ext, iteration)
                else:
                    newFile = "{0}_{1:03d}_{2:d}{3}".format(base, cycle, node, ext)
                # add the cycle and timenode to the XS input file names so that a rx-coeff case that
                # runs in here won't overwrite them.
                pathTools.copyOrWarn(fileName, fileName, os.path.join(newFolder, newFile))
            if "rzmflx" in fileName:
                pathTools.copyOrWarn("rzmflx for snapshot", fileName, newFolder)

        fileNamePossibilities = [f"ISOTXS-c{cycle}n{node}", f"ISOTXS-c{cycle}"]
        if iteration is not None:
            fileNamePossibilities = [f"ISOTXS-c{cycle}n{node}i{iteration}"] + fileNamePossibilities

        for isoFName in fileNamePossibilities:
            if os.path.exists(isoFName):
                break
        pathTools.copyOrWarn("ISOTXS for snapshot", isoFName, pathTools.armiAbsPath(newFolder, "ISOTXS"))
        globalFluxLabel = GlobalFluxInterfaceUsingExecuters.getLabel(self.cs.caseTitle, cycle, node, iteration)
        globalFluxInput = globalFluxLabel + ".inp"
        globalFluxOutput = globalFluxLabel + ".out"
        pathTools.copyOrWarn("DIF3D input for snapshot", globalFluxInput, newFolder)
        pathTools.copyOrWarn("DIF3D output for snapshot", globalFluxOutput, newFolder)
        pathTools.copyOrWarn("Shuffle logic for snapshot", self.cs[CONF_SHUFFLE_LOGIC], newFolder)
        pathTools.copyOrWarn("Loading definition for snapshot", self.cs[CONF_LOADING_FILE], newFolder)

    @staticmethod
    def setStateToDefault(cs):
        """Update the state of ARMI to fit the kind of run this operator manages."""
        return cs.modified(newSettings={"runType": RunTypes.STANDARD})

    def couplingIsActive(self):
        """True if any kind of physics coupling is active."""
        return self.cs[CONF_TIGHT_COUPLING]
