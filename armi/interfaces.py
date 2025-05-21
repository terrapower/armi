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
Interfaces are objects of code that interact with ARMI. They read information off the state,
perform calculations (or run external codes), and then store the results back in the state.

Learn all about interfaces in :doc:`/developer/guide`

See Also
--------
armi.operators : Schedule calls to various interfaces
armi.plugins : Register various interfaces
"""
import copy
from typing import Dict, List, NamedTuple, Union

import numpy as np
from numpy.linalg import norm

from armi import getPluginManagerOrFail, runLog, settings, utils
from armi.reactor import parameters
from armi.utils import textProcessors


class STACK_ORDER:  # noqa: N801
    """
    Constants that help determine the order of modules in the interface stack.

    Each module defines an ``ORDER`` constant that specifies where in this order it should be placed
    in the Interface Stack.

    .. impl:: Define an ordered list of interfaces.
        :id: I_ARMI_OPERATOR_INTERFACES0
        :implements: R_ARMI_OPERATOR_INTERFACES

        At each time node during a simulation, an ordered collection of Interfaces are run (referred
        to as the interface stack). But ARMI does not force the order upon the analyst. Instead,
        each Interface registers where in that ordered list it belongs by giving itself an order
        number (which can be an integer or a decimal). This class defines a set of constants which
        can be imported and used by Interface developers to define that Interface's position in the
        stack.

        The constants defined are given names, based on common stack orderings in the ARMI
        ecosystem. But in the end, these are just constant values, and the names they are given are
        merely suggestions.

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


class TightCoupler:
    """
    Data structure that defines tight coupling attributes that are implemented
    within an Interface and called upon when ``interactAllCoupled`` is called.

    .. impl:: The TightCoupler defines the convergence criteria for physics coupling.
        :id: I_ARMI_OPERATOR_PHYSICS0
        :implements: R_ARMI_OPERATOR_PHYSICS

        During a simulation, the developers of an ARMI application frequently want to
        iterate on some physical calculation until that calculation has converged to
        within some small tolerance. This is typically done to solve the nonlinear
        dependence of different physical properties of the reactor, like fuel
        performance. However, what parameter is being tightly coupled is configurable
        by the developer.

        This class provides a way to calculate if a single parameter has converged
        based on some convergence tolerance. The user provides the parameter,
        tolerance, and a maximum number of iterations to define a basic convergence
        calculation. If in the ``isConverged`` method the parameter has not converged,
        the number of iterations is incremented, and this class will wait, presuming
        another iteration is forthcoming.

    Parameters
    ----------
    param : str
        The name of a parameter defined in the ARMI Reactor model.

    tolerance : float
        Defines the allowable error between the current and previous parameter values
        to determine if the selected coupling parameter has converged.

    maxIters : int
        Maximum number of tight coupling iterations allowed
    """

    _SUPPORTED_TYPES = [float, int, list, np.ndarray]

    def __init__(self, param, tolerance, maxIters):
        self.parameter = param
        self.tolerance = tolerance
        self.maxIters = maxIters
        self._numIters = 0
        self._previousIterationValue = None
        self.eps = np.inf

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}, Parameter: {self.parameter}, Convergence Criteria: "
            + f"{self.tolerance}, Maximum Coupled Iterations: {self.maxIters}>"
        )

    def storePreviousIterationValue(self, val: _SUPPORTED_TYPES):
        """
        Stores the previous iteration value of the given parameter.

        Parameters
        ----------
        val : _SUPPORTED_TYPES
            the value to store. Is commonly equal to interface.getTightCouplingValue()

        Raises
        ------
        TypeError
            Checks the type of the val against ``_SUPPORTED_TYPES`` before storing.
            If invalid, a TypeError is raised.
        """
        if type(val) not in self._SUPPORTED_TYPES:
            raise TypeError(
                f"{val} supplied has type {type(val)} which is not supported in {self}. "
                f"Supported types: {self._SUPPORTED_TYPES}"
            )
        self._previousIterationValue = val

    def isConverged(self, val: _SUPPORTED_TYPES) -> bool:
        """
        Return boolean indicating if the convergence criteria between the current and previous
        iteration values are met.

        Parameters
        ----------
        val : _SUPPORTED_TYPES
            The most recent value for computing convergence criteria. Is commonly equal to
            interface.getTightCouplingValue()

        Returns
        -------
        boolean
            True (False) interface is (not) converged

        Notes
        -----
        - On convergence, this class is automatically reset to its initial condition to avoid
          retaining or holding a stale state. Calling this method will increment a counter that when
          exceeded will clear the state. A warning will be reported if the state is cleared prior to
          the convergence criteria being met.
        - For computing convergence of arrays, only up to 2D is allowed. 3D arrays would arise from
          considering component level parameters. However, converging on component level parameters
          is not supported at this time.

        Raises
        ------
        ValueError
            If the previous iteration value has not been assigned. The
            ``storePreviousIterationValue`` method must be called first.
        RuntimeError
            Only support calculating norms for up to 2D arrays.
        """
        if self._previousIterationValue is None:
            raise ValueError(
                f"Cannot check convergence of {self} with no previous iteration value set. "
                "Set using `storePreviousIterationValue` first."
            )

        previous = self._previousIterationValue

        # calculate convergence of val and previous
        if isinstance(val, (int, float)):
            self.eps = abs(val - previous)
        else:
            dim = self.getListDimension(val)
            if dim == 1:  # 1D array
                self.eps = norm(np.subtract(val, previous), ord=2)
            elif dim == 2:  # 2D array
                epsVec = []
                for old, new in zip(previous, val):
                    epsVec.append(norm(np.subtract(old, new), ord=2))
                self.eps = norm(epsVec, ord=np.inf)
            else:
                raise RuntimeError(
                    "Currently only support up to 2D arrays for calculating convergence of arrays."
                )

        # Check if convergence is satisfied. If so, or if reached max number of iters, then reset
        # the number of iterations
        converged = self.eps < self.tolerance
        if converged:
            self._numIters = 0
        else:
            self._numIters += 1
            if self._numIters == self.maxIters:
                runLog.warning(
                    f"Maximum number of iterations for {self.parameter} reached without convergence!"
                    f"Prescribed convergence criteria is {self.tolerance}."
                )
                self._numIters = 0

        return converged

    @staticmethod
    def getListDimension(listToCheck: list, dim: int = 1) -> int:
        """Return the dimension of a python list.

        Parameters
        ----------
        listToCheck: list
            the supplied python list to have its dimension returned
        dim: int, optional
            the dimension of the list

        Returns
        -------
        dim, int
            the dimension of the list. Typically 1, 2, or 3 but can be arbitrary order, N.
        """
        for v in listToCheck:
            if isinstance(v, list):
                dim += 1
                dim = TightCoupler.getListDimension(v, dim)
            break
        return dim


class Interface:
    """
    The eponymous Interface between the ARMI reactor data model and the Plugins.

    .. impl:: The interface shall allow code execution at important operational points in time.
        :id: I_ARMI_INTERFACE
        :implements: R_ARMI_INTERFACE

        The Interface class defines a number methods with names like ``interact***``.
        These methods are called in order at each time node. This allows for an
        individual Plugin defining multiple interfaces to insert code at the start
        or end of a particular time node or cycle during reactor simulation. In this
        fashion, the Plugins and thus the Operator control when their code is run.

        The end goal of all this work is to allow the Plugins to carefully tune
        when and how they interact with the reactor data model.

        Interface instances are gathered into an interface stack in
        :py:meth:`armi.operators.operator.Operator.createInterfaces`.
    """

    # list containing interfaceClass
    @classmethod
    def getDependencies(cls, cs):
        return []

    @classmethod
    def getInputFiles(cls, cs):
        """Return a MergeableDict containing files that should be considered "input"."""
        return utils.MergeableDict()

    name: Union[str, None] = None
    """
    The name of the interface. This is undefined for the base class, and must be overridden by any
    concrete class that extends this one.
    """

    function = None
    """
    The function performed by an Interface. This is not required be be defined by implementations of
    Interface, but is used to form categories of interfaces.
    """

    class Distribute:
        """Enum-like return flag for behavior on interface broadcasting with MPI."""

        DUPLICATE = 1
        NEW = 2
        SKIP = 4

    def __init__(self, r, cs):
        """
        Construct an interface.

        The ``r`` and ``cs`` arguments are required, but may be ``None``, where appropriate for the
        specific ``Interface`` implementation.

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
        self.cs = cs
        self.r = r
        self.o = r.o if r else None
        self.coupler = _setTightCouplerByInterfaceFunction(self, cs)

    def __repr__(self):
        return "<Interface {0}>".format(self.name)

    def _checkSettings(self):
        """Raises an exception if interface settings requirements are not met."""
        pass

    def nameContains(self, name):
        return name in str(self.name)

    def distributable(self):
        """
        Return true if this can be MPI broadcast.

        Notes
        -----
        Cases where this isn't possible include the database interface, where the SQL driver cannot
        be distributed.
        """
        return self.Distribute.DUPLICATE

    def preDistributeState(self):
        """
        Prepare for distribute state by returning all non-distributable attributes.

        Examples
        --------
        >>> return {'neutronsPerFission',self.neutronsPerFission}
        """
        return {}

    def postDistributeState(self, toRestore):
        """Restore non-distributable attributes after a distributeState."""
        pass

    def attachReactor(self, o, r):
        """
        Set this interfaces' reactor to the reactor passed in and sets default settings.

        Parameters
        ----------
        r : Reactor object
            The reactor to attach
        quiet : bool, optional
            If true, don't print out the message while attaching

        Notes
        -----
        This runs on all worker nodes as well as the primary.
        """
        self.r = r
        self.cs = o.cs
        self.o = o

    def detachReactor(self):
        """Delete the callbacks to reactor or operator. Useful when pickling, MPI sending, etc. to
        save memory.
        """
        self.o = None
        self.r = None
        self.cs = None

    def duplicate(self):
        """
        Duplicate this interface without duplicating some of the large attributes (like the entire
        reactor).

        Makes a copy of interface with detached reactor/operator/settings so that it can be attached
        to an operator at a later point in time.

        Returns
        -------
        Interface
            The deepcopy of this interface with detached reactor/operator/settings
        """
        # temporarily remove references to the interface.  They will be reattached later.
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

    def getHistoryParams(self):
        """
        Add these params to the history tracker for designated assemblies.

        The assembly will get a print out of these params vs. time at EOL.
        """
        return []

    def getInterface(self, *args, **kwargs):
        return self.o.getInterface(*args, **kwargs) if self.o else None

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
        Parameters with defaults are not written to the database until they have been assigned
        SINCE_ANYTHING. This is done to reduce database size, so that we don't write parameters to
        the DB that are related to interfaces that are not not active.
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
        """Called repeatedly at each time node/subcycle when tight physics coupling is active."""
        pass

    def getTightCouplingValue(self):
        """Abstract method to retrieve the value in which tight coupling will converge on."""
        pass

    def interactError(self):
        """Called if an error occurs."""
        pass

    def interactDistributeState(self):
        """Called after this interface is copied to a different (non-primary) MPI node."""
        pass

    def isRequestedDetailPoint(self, cycle=None, node=None):
        """
        Determine if this interface should interact at this reactor state (cycle/node).

        Notes
        -----
        By default, detail points are either during the requested snapshots, if any exist, or all
        cycles and nodes if none exist.

        This is useful for peripheral interfaces (CR Worth, perturbation theory, transients) that
        may or may not be requested during a standard run.

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

    def workerOperate(self, _cmd):
        """
        Receive an MPI command and do MPI work on worker nodes.

        Returns
        -------
        bool
            True if this interface handled the incoming command. False otherwise.
        """
        return False

    def enabled(self, flag=None):
        """
        Mechanism to allow interfaces to be attached but not running at the interaction points.

        Must be implemented on the individual interface level hooks. If given no arguments, returns
        status of enabled. If arguments, sets enabled to that flag. (True or False)

        Notes
        -----
        These ``return`` statements are inconsistent, but not wrong.
        """
        if flag is None:
            return self._enabled
        elif isinstance(flag, bool):
            self._enabled = flag
        else:
            raise ValueError("Non-bool passed to assign {}.enable().".format(self))

    def bolForce(self, flag=None):
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

        Notes
        -----
        These ``return`` statements are inconsistent, but not wrong.
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
    def specifyInputs(cs) -> Dict[Union[str, settings.Setting], List[str]]:
        """
        Return a collection of file names that are considered input files.

        This is a static method (i.e. is not called on a particular instance of the class), since it
        should not require an Interface to actually be constructed. This would require constructing
        a reactor object, which is expensive.

        The files returned by an implementation should be those that one would want copied to a
        target location when cloning a Case or CaseSuite. These can be absolute paths, relative
        paths, or glob patterns that will be interpolated relative to the input directory. Absolute
        paths will not be copied anywhere.

        The returned dictionary will enable the source Settings object to be updated to the new file
        location. While the dictionary keys are recommended to be Setting objects, the name of the
        setting as a string, e.g., "shuffleLogic", is still interpreted. If the string name does not
        point to a valid setting then this will lead to a failure.

        Note
        ----
        This existed before the advent of ARMI plugins. Perhaps it can be better served as a plugin
        hook. Potential future work.

        See Also
        --------
        armi.cases.Case.clone() : Main user of this interface.

        Parameters
        ----------
        cs : Settings
            The case settings for a particular Case
        """
        return {}

    def updatePhysicsCouplingControl(self):
        """Adjusts physics coupling settings depending on current state of run."""
        pass


class InputWriter:
    """Use to write input files of external codes."""

    def __init__(self, r=None, externalCodeInterface=None, cs=None):
        self.externalCodeInterface = externalCodeInterface
        self.eci = externalCodeInterface
        self.r = r
        self.cs = cs

    def getInterface(self, name):
        """Get another interface by name."""
        if self.externalCodeInterface:
            return self.externalCodeInterface.getInterface(name)
        return None

    def write(self, fName):
        """Write the input file."""
        raise NotImplementedError


class OutputReader:
    """
    A generic representation of a particular module's output.

    Attributes
    ----------
    success : bool
        False by default, set to True if the run is considered
        to have completed without error.

    Notes
    -----
    Should ideally not require r, eci, and fname arguments and would rather just have an
    apply(reactor) method.
    """

    def __init__(self, r=None, externalCodeInterface=None, fName=None, cs=None):
        self.externalCodeInterface = externalCodeInterface
        self.eci = self.externalCodeInterface
        self.r = r
        self.cs = cs
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


def _setTightCouplerByInterfaceFunction(interfaceClass, cs):
    """
    Return an instance of a ``TightCoupler`` class or ``None``.

    Parameters
    ----------
    interfaceClass : Interface
        Interface class that a ``TightCoupler`` object will be added to.

    cs : Settings
        Case settings that are parsed to determine if tight coupling is enabled
        globally and if both a target parameter and convergence criteria defined.
    """
    # No tight coupling if there is no function for the Interface defined.
    if interfaceClass.function is None:
        return None

    if not cs["tightCoupling"] or (
        interfaceClass.function not in cs["tightCouplingSettings"]
    ):
        return None

    parameter = cs["tightCouplingSettings"][interfaceClass.function]["parameter"]
    tolerance = cs["tightCouplingSettings"][interfaceClass.function]["convergence"]
    maxIters = cs["tightCouplingMaxNumIters"]

    return TightCoupler(parameter, tolerance, maxIters)


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
    cs : Settings
        The case settings that activate relevant Interfaces
    """
    interfaceInfo = []
    for info in getPluginManagerOrFail().hook.exposeInterfaces(cs=cs):
        interfaceInfo += info

    interfaceInfo = [
        (iInfo.interfaceCls, iInfo.kwargs)
        for iInfo in sorted(interfaceInfo, key=lambda x: x.order)
    ]

    return interfaceInfo


def isInterfaceActive(klass, cs):
    """Return True if the Interface klass is active."""
    return any(issubclass(k, klass) for k, _kwargs in getActiveInterfaceInfo(cs))


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
