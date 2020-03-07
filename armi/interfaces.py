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

r"""
Interfaces are objects of code that interact with ARMI. They read information off the state,
perform calculations (or run external codes), and then store the results back in the state.

Learn all about interfaces in :doc:`/developer/guide`

See Also
--------
armi.operators : Schedule calls to various interfaces

armi.plugins : Register various interfaces

"""
import copy
from typing import Union
from typing import NamedTuple
from typing import List
from typing import Dict
from abc import ABCMeta, abstractmethod

import armi
from armi import settings
from armi import utils
from armi.utils import textProcessors
from armi.reactor import parameters


class STACK_ORDER(object):  # pylint: disable=invalid-name, too-few-public-methods
    """
    Constants that help determine the order of modules in the interface stack.

    Each module specifies an ``ORDER`` constant that specifies where in this order it
    should be placed in the Interface Stack.

    Notes
    -----
    Originally, the ordering was accomplished with a very large if/else construct in ``createInterfaces``.
    This made more modular by moving the add/activate logic into each module and replacing the if/else with
    just a large hard-coded list of modules in order that could possibly be added. That hard-coded
    list presented ``ImportError`` problems when building various subset distributions of ARMI so this ordering
    mechanism was created to replace it, allowing the modules to define their required order internally.

    Future improvements may include simply defining what information is required to perform a calculation
    and figuring out the ordering from that. It's complex because in coupled simulations, everything
    depends on everything.

    See Also
    --------
    armi.operators.operator.Operator.createInterfaces
    armi.physics.neutronics.globalFlux.globalFluxInterface.ORDER

    """

    BEFORE = -0.1
    AFTER = 0.1
    PREPROCESSING = 1.0
    FUEL_MANAGEMENT = PREPROCESSING + 1
    DEPLETION = FUEL_MANAGEMENT + 1
    FUEL_PERFORMANCE = DEPLETION + 1
    CROSS_SECTIONS = FUEL_PERFORMANCE + 1
    CRITICAL_CONTROL = CROSS_SECTIONS + 1
    FLUX = CRITICAL_CONTROL + 1
    THERMAL_HYDRAULICS = FLUX + 1
    REACTIVITY_COEFFS = THERMAL_HYDRAULICS + 1
    TRANSIENT = REACTIVITY_COEFFS + 1
    BOOKKEEPING = TRANSIENT + 1
    POSTPROCESSING = BOOKKEEPING + 1


class Interface(object):
    """
    The eponymous Interface between the ARMI Reactor model and modules that operate upon it.

    This defines the operator's contract for interacting with the ARMI reactor model.
    It is expected that interact* methods are defined as appropriate for the physics modeling.

    Interface instances are gathered into an interface stack in
    :py:meth:`armi.operators.operator.Operator.createInterfaces`.
    """

    # pylint: disable=too-many-instance-attributes,too-many-public-methods

    # list containing interfaceClass
    @classmethod
    def getDependencies(cls, cs):  # pylint: disable=unused-argument
        return []

    @classmethod
    def getInputFiles(cls, cs):  # pylint: disable=unused-argument
        """
        Return a MergeableDict containing files that should be considered "input"
        """
        return utils.MergeableDict()

    name: Union[str, None] = None
    """
    The name of the interface. This is undefined for the base class, and must be
    overridden by any concrete class that extends this one.
    """

    function = None
    """
    The function performed by an Interface. This is not required be be defined
    by implementations of Interface, but is used to form categories of
    interfaces.
    """

    class Distribute(object):  # pylint: disable=too-few-public-methods
        """Enum-like return flag for behavior on interface broadcasting with MPI."""

        DUPLICATE = 1
        NEW = 2
        SKIP = 4

    def __init__(self, r, cs):
        r"""
        Construct an interface.

        The ``r`` and ``cs`` arguments are required, but may be ``None``, where
        appropriate for the specific ``Interface`` implementation.

        Parameters
        ----------
        r : Reactor
            A reactor to attach to
        cs : Settings
            Settings object to use

        Raises
        ------
        RuntimeError
            Interfaces derived from Interface must define their name
        """
        if self.name is None:
            raise RuntimeError(
                "Interfaces derived from Interface must define "
                "their name ({}).".format(type(self).__name__)
            )
        self._enabled = True
        self.reverseAtEOL = False
        self._bolForce = False  # override disabled flag in interactBOL if true.
        self.cs = settings.getMasterCs() if cs is None else cs
        self.r = r
        self.o = r.o if r else None

    def __repr__(self):
        return "<Interface {0}>".format(self.name)

    def _checkSettings(self):
        """
        Raises an exception if interface settings requirements are not met
        """
        pass

    def nameContains(self, name):
        return name in str(self.name)

    def distributable(self):
        """
        Return true if this can be MPI broadcast.

        Notes
        -----
        Cases where this isn't possible include the database interface,
        where the SQL driver cannot be distributed.

        """
        return self.Distribute.DUPLICATE

    def preDistributeState(self):  # pylint: disable=no-self-use
        """
        Prepare for distribute state by returning all non-distributable attributes

        Examples
        --------
        return {'neutronsPerFission',self.neutronsPerFission}
        """
        return {}

    def postDistributeState(self, toRestore):  # pylint: disable=no-self-use
        """
        Restore non-distributable attributes after a distributeState
        """
        pass

    def attachReactor(self, o, r):
        """
        Set this interfaces' reactor to the reactor passed in and sets default settings

        Parameters
        ----------
        r : Reactor object
            The reactor to attach
        quiet : bool, optional
            If true, don't print out the message while attaching

        Notes
        -----
        This runs on all worker nodes as well as the master.
        """
        self.r = r
        self.cs = o.cs
        self.o = o

    def detachReactor(self):
        """Delete the callbacks to reactor or operator. Useful when pickling, MPI sending, etc. to save memory."""
        self.o = None
        self.r = None
        self.cs = None

    def duplicate(self):
        """
        Duplicate this interface without duplicating some of the large attributes (like the entire reactor).

        Makes a copy of interface with detached reactor/operator/settings so that it can be attached to an operator
        at a later point in time.

        Returns
        -------
        Interface
            The deepcopy of this interface with detached reactor/operator/settings

        """

        # temporarily remove references to the interface.  They will be reattached later
        o = self.o
        self.o = None

        r = self.r
        self.r = None

        cs = self.cs
        self.cs = None

        # a new sterile copy of the interface.
        # With no record of operators, reactors, or cs, it can be added easily to a new operator
        newI = copy.deepcopy(self)

        # reattach current interface information
        self.o = o
        self.r = r
        self.cs = cs

        return newI

    def getHistoryParams(self):  # pylint: disable=no-self-use
        """
        Add these params to the history tracker for designated assemblies.

        The assembly will get a print out of these params vs. time at EOL.
        """
        return []

    def getInterface(self, *args, **kwargs):
        return self.o.getInterface(*args, **kwargs) if self.o else None

    def updateAssemblyLevelParams(
        self, a, excludedBlockTypes=None
    ):  # pylint-disable=no-self-use
        """
        Called during loads from snapshots.

        Allows block params to go derive the assembly-level params (such as massFlow).
        """
        pass

    def interactInit(self):
        """
        Interacts immediately after the interfaces are created.

        Notes
        -----
        BOL interactions on other interfaces will not have occurred here.
        """
        self._checkSettings()

    def interactBOL(self):
        """Called at the Beginning-of-Life of a run, before any cycles start."""
        if self._enabled:
            self._initializeParams()

    def _initializeParams(self):
        """
        Assign the parameters for active interfaces so that they will be in the database.

        Notes
        -----
        Parameters with defaults are not written to the database until they have been assigned SINCE_ANYTHING.
        This is done to reduce database size, so that we don't write parameters to the DB that are related to
        interfaces that are not not active.
        """
        for paramDef in parameters.ALL_DEFINITIONS.inCategory(self.name):
            if paramDef.default not in (None, parameters.NoDefault):
                paramDef.assigned = parameters.SINCE_ANYTHING

    def interactEOL(self):
        """Called at End-of-Life, after all cycles are complete."""
        pass

    def interactBOC(self, cycle=None):
        """Called at the beginning of each cycle."""
        pass

    def interactEOC(self, cycle=None):
        """Called at the end of each cycle."""
        pass

    def interactEveryNode(self, cycle, node):
        """Called at each time node/subcycle of every cycle."""
        pass

    def interactCoupled(self, iteration):
        """Called repeatedly at each time node/subcycle when tight physics couping is active."""
        pass

    def interactError(self):
        """Called if an error occurs."""
        pass

    def interactDistributeState(self):
        """Called after this interface is copied to a different (non-master) MPI node."""
        pass

    def isRequestedDetailPoint(self, cycle=None, node=None):
        """
        Determine if this interface should interact at this reactor state (cycle/node).

        Notes
        -----
        By default, detail points are either during the requested snapshots,
        if any exist, or all cycles and nodes if none exist.

        This is useful for peripheral interfaces (CR Worth, perturbation theory, transients)
        that may or may not be requested during a standard run.

        If both cycle and node are None, this returns True

        Parameters
        ----------
        cycle : int
            The cycle number (or None to only consider node)
        node : int
            The timenode (BOC, MOC, EOC, etc.).

        Returns
        -------
        bool
            Whether or not this is a detail point.

        """
        from armi.bookkeeping import snapshotInterface  # avoid cyclic import

        if cycle is None and node is None:
            return True
        if not self.cs["dumpSnapshot"]:
            return True

        for cnStamp in self.cs["dumpSnapshot"]:
            ci, ni = snapshotInterface.extractCycleNodeFromStamp(cnStamp)
            if cycle is None and ni == node:
                # case where only node counts (like in equilibrium cases)
                return True
            if ci == cycle and ni == node:
                return True

        return False

    def workerOperate(self, _cmd):  # pylint: disable=no-self-use
        """
        Receive an MPI command and do MPI work on worker nodes.

        Returns
        -------
        bool
            True if this interface handled the incoming command. False otherwise.
        """
        return False

    def enabled(self, flag=None):  # pylint: disable=inconsistent-return-statements
        """
        Mechanism to allow interfaces to be attached but not running at the interaction points.

        Must be implemented on the individual interface level hooks.
        If given no arguments, returns status of enabled
        If arguments, sets enabled to that flag. (True or False)
        """
        if flag is None:
            return self._enabled
        elif isinstance(flag, bool):
            self._enabled = flag
        else:
            raise ValueError("Non-bool passed to assign {}.enable().".format(self))

    def bolForce(self, flag=None):  # pylint: disable=inconsistent-return-statements
        """
        Run interactBOL even if this interface is disabled.

        Parameters
        ----------
        flag : boolean, optional
            Will set the bolForce flag to this boolean

        Returns
        -------
        bool
            true if should run at BOL. No return if you pass an input.
        """
        if flag is None:
            return self._bolForce
        self._bolForce = flag

    def writeInput(self, inName):
        """Write input file(s)."""
        raise NotImplementedError()

    def readOutput(self, outName):
        """Read output file(s)."""
        raise NotImplementedError()

    @staticmethod
    def specifyInputs(cs) -> Dict[str, List[str]]:  # pylint: disable=unused-argument
        """
        Return a collection of file names that are considered input files.

        This is a static method (i.e. is not called on a particular instance of the
        class), since it should not require an Interface to actually be constructed.
        This would require constructing a reactor object, which is expensive.

        The files returned by an implementation of this method are those that one would
        want copied to a remote location when cloning a Case or CaseSuite to a remote
        location.

        Note
        ----
        This existed before the advent of ARMI plugins. Perhaps it can be better served
        as a plugin hook. Potential future work.

        Parameters
        ----------
        cs : CaseSettings
            The case settings for a particular Case
        """
        return {}

    def updatePhysicsCouplingControl(self):
        """Adjusts physics coupling settings depending on current state of run."""
        pass


class InputWriter(object):
    """Use to write input files of external codes."""

    def __init__(self, r=None, externalCodeInterface=None, cs=None):
        self.externalCodeInterface = externalCodeInterface
        self.eci = externalCodeInterface
        self.r = r
        self.cs = cs or settings.getMasterCs()

    def getInterface(self, name):
        """Get another interface by name."""
        if self.externalCodeInterface:
            return self.externalCodeInterface.getInterface(name)
        return None

    def write(self, fName):
        """Write the input file."""
        raise NotImplementedError


class OutputReader(object):
    """
    A generic representation of a particular module's output.
    
    Attributes
    ----------
    success : bool
        False by default, set to True if the run is considered
        to have completed without error.
        
    Notes
    -----
    Should ideally not require r, eci, and fname arguments
    and would rather just have an apply(reactor) method.
    
    """

    def __init__(self, r=None, externalCodeInterface=None, fName=None):
        self.externalCodeInterface = externalCodeInterface
        self.eci = self.externalCodeInterface
        self.r = r
        self.cs = settings.getMasterCs()
        if fName:
            self.output = textProcessors.TextProcessor(fName)
        else:
            self.output = None
        self.fName = fName
        self.success = False

    def getInterface(self, name):
        """Get another interface by name."""
        if self.externalCodeInterface:
            return self.externalCodeInterface.getInterface(name)
        return None

    def read(self, fileName):
        """Read the output file."""
        raise NotImplementedError

    def apply(self, reactor):
        """
        Apply the output back to a reactor state.
        
        This provides a generic interface for the output data of anything
        to be applied to a reactor state. The application could involve
        reading text or binary output or simply parameters to appropriate
        values in some other data structure.
        """
        raise NotImplementedError()


def getActiveInterfaceInfo(cs):
    """
    Return a list containing information for all of the Interface classes that are present.

    This creates a list of tuples, each containing an Interface subclass and appropriate
    kwargs for adding them to an Operator stack, given case settings. There should be
    entries for all Interface classes that are returned from implementations of the
    describeInterfaces() function in modules present in the passed list of packages. The
    list is sorted by the ORDER specified by the module in which the specific Interfaces
    are described.

    Parameters
    ----------
    cs : CaseSettings
        The case settings that activate relevant Interfaces
    """
    interfaceInfo = []
    # pylint: disable = no-member
    for info in armi.getPluginManagerOrFail().hook.exposeInterfaces(cs=cs):
        interfaceInfo += info

    interfaceInfo = [
        (iInfo.interfaceCls, iInfo.kwargs)
        for iInfo in sorted(interfaceInfo, key=lambda x: x.order)
    ]

    return interfaceInfo


def isInterfaceActive(klass, cs):
    """Return True if the Interface klass is active."""
    for k, _kwargs in getActiveInterfaceInfo(cs):
        if issubclass(k, klass):
            return True
    return False


class InterfaceInfo(NamedTuple):
    """
    Data structure with interface info.

    Notes
    -----
    If kwargs is an empty dictionary, defaults from
    ``armi.operators.operator.Operator.addInterface`` will be applied.

    See Also
    --------
    armi.operators.operator.Operator.createInterfaces : where these ultimately
        activate various interfaces.
    """

    order: int
    interfaceCls: Interface
    kwargs: dict


class InterfaceFactory(metaclass=ABCMeta):
    """Base class for choosing ARMI Interfaces."""

    def __init__(self, cs):
        self.cs = cs

    @abstractmethod
    def getInterfaceInfo(self):
        """
        Return a list of Interface info

        Returns
        -------
        classData
            list of InterfaceInfo structs

        """
        pass
