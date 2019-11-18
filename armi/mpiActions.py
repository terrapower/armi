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
This module provides an abstract class to be used to implement "MPI actions."

MPI actions are tasks, activities, or work that can be executed on the worker nodes. The standard
workflow is essentially that the master node creates an :py:class:`~armi.mpiActions.MpiAction`,
sends it to the workers, and then both the master and the workers
:py:meth:`invoke() <armi.mpiActions.MpiAction.invoke>` together. For example:

.. list-table:: Sample MPI Action Workflow
   :widths: 5 60 35
   :header-rows: 1

   * - Step
     - Code
     - Notes
   * - 1
     - **master**: :py:class:`distributeState = DistributeStateAction() <armi.mpiActions.MpiAction>`

       **worker**: :code:`action = armi.MPI_COMM.bcast(None, root=0)`
     - **master**: Initializing a distribute state action.

       **worker**: Waiting for something to do, as determined by the master, this happens within the
       worker's :py:meth:`~armi.operators.MpiOperator.workerOperate`.
   * - 2
     - **master**: :code:`armi.MPI_COMM.bcast(distributeState, root=0)`

       **worker**: :code:`action = armi.MPI_COMM.bcast(None, root=0)`
     - **master**: Broadcasts a distribute state action to all the worker nodes

       **worker**: Receives the action from the master, which is a
       :py:class:`~armi.mpiActions.DistributeStateAction`.
   * - 3
     - **master**: :code:`distributeState.invoke(self.o, self.r, self.cs)`

       **worker**: :code:`action.invoke(self.o, self.r, self.cs)`
     - Both invoke the action, and are in sync. Any broadcast or receive within the action should
       also be synced up.

In order to create a new, custom MPI Action, inherit from :py:class:`~armi.mpiActions.MpiAction`,
and override the :py:meth:`~armi.mpiActions.MpiAction.invokeHook` method.

"""
import collections
import gc
import timeit
import math

from six.moves import cPickle
import tabulate

import armi
from armi import runLog
from armi import settings
from armi import interfaces
from armi.reactor import reactors
from armi.reactor import assemblies
from armi import utils
from armi.utils import iterables


class MpiAction(object):
    """Base of all MPI actions.

    MPI Actions are tasks that can be executed without needing lots of other
    information. When a worker node sits in it's main loop, and receives an MPI Action, it will
    simply call :py:meth:`~armi.mpiActions.MpiAction.invoke`.
    """

    def __init__(self):
        self.o = None
        self.r = None
        self.cs = None
        self.serial = False

    @property
    def parallel(self):
        return not self.serial

    @classmethod
    def invokeAsMaster(cls, o, r, cs):
        """Simplified method to call from the master process.

        This can be used in place of:

            someInstance = MpiAction()
            someInstance = COMM_WORLD.bcast(someInstance, root=0)
            someInstance.invoke(o, r, cs)

        Interestingly, the code above can be used in two ways:

        1. Both the master and worker can call the above code at the same time, or
        2. the master can run the above code, which will be handled by the worker's main loop.

        Option number 2 is the most common usage.

        .. warning:: This method will not work if the constructor (i.e. :code:`__init__`) requires
            additional arguments. Since the method body is so simple, it is strong discouraged to
            add a :code:`*args` or :code:`**kwargs` arguments to this method.

        Parameters
        ----------
        o : :py:class:`armi.operators.Operator`
            If an operator is not necessary, supply :code:`None`.
        r : :py:class:`armi.operators.Reactor`
            If a reactor is not necessary, supply :code:`None`.
        """

        instance = cls()
        instance.broadcast()
        return instance.invoke(o, r, cs)

    def _mpiOperationHelper(self, obj, mpiFunction):
        """
        Strips off the operator, reactor, cs from the mpiAction before
        """
        if obj is None or obj is self:
            # prevent sending o, r, and cs, they should be handled appropriately by the other nodes
            # reattach with finally
            obj = self
            o, r, cs = self.o, self.r, self.cs
            self.o = self.r = self.cs = None
        try:
            return mpiFunction(obj, root=0)
        except (cPickle.PicklingError) as error:
            runLog.error("Failed to {} {}.".format(mpiFunction.__name__, obj))
            runLog.error(error)
            raise
        finally:
            if obj is self:
                self.o, self.r, self.cs = o, r, cs

    def broadcast(self, obj=None):
        """
        A wrapper around ``bcast``, on the master node can be run with an equals sign, so that it
        can be consistent within both master and worker nodes.

        Parameters
        ----------
        obj :
            This is any object that can be broadcast, if it is None, then it will broadcast itself,
            which triggers it to run on the workers (assuming the workers are in the worker main loop.

        See Also
        --------
        armi.operators.operator.OperatorMPI.workerOperate : receives this on the workers and calls ``invoke``

        Notes
        -----
        The standard ``bcast`` method creates a new instance even for the root process. Consequently,
        when passing an object, references can be broken to the original object. Therefore, this
        method, returns the original object when called by the master node, or the broadcasted
        object when called on the worker nodes.
        """
        if self.serial:
            return obj if obj is not None else self
        if armi.MPI_SIZE > 1:
            result = self._mpiOperationHelper(obj, armi.MPI_COMM.bcast)
        # the following if-branch prevents the creation of duplicate objects on the master node
        # if the object is large with lots of links, it is prudent to call gc.collect()
        if obj is None and armi.MPI_RANK == 0:
            return self
        elif armi.MPI_RANK == 0:
            return obj
        else:
            return result

    def gather(self, obj=None):
        """A wrapper around ``MPI_COMM.gather``.

        Parameters
        ----------
        obj :
            This is any object that can be gathered, if it is None, then it will gather itself.

        Notes
        -----
        The returned list will contain a reference to the original gathered object, without making a copy of it.
        """
        if self.serial:
            return [obj if obj is not None else self]
        if armi.MPI_SIZE > 1:
            result = self._mpiOperationHelper(obj, armi.MPI_COMM.gather)
            if armi.MPI_RANK == 0:
                # this cannot be result[0] = obj or self, because 0.0, 0, [] all eval to False
                if obj is None:
                    result[0] = self
                else:
                    result[0] = obj
            else:
                result = []
        else:
            result = [obj if obj is not None else self]
        return result

    def invoke(self, o, r, cs):
        """
        This method is called by worker nodes, and passed the worker node's operator, reactor and
        settings file.

        Parameters
        ----------
        o : :py:class:`armi.operators.Operator`
            the operator for this process
        r : :py:class:`armi.reactor.reactors.Reactor`
            the reactor represented in this process
        cs : :py:class:`armi.settings.caseSettings.Settings`
            the case settings

        Returns
        -------
        result : object
            result from invokeHook
        """
        self.o = o
        self.r = r
        self.cs = cs
        return self.invokeHook()

    def mpiFlatten(self, allCPUResults):
        """
        Flatten results to the same order they were in before making a list of mpiIter results.

        See Also
        --------
        mpiIter : used for distributing objects/tasks
        """
        return iterables.flatten(allCPUResults)

    def mpiIter(self, objectsForAllCoresToIter):
        """
        Generate the subset of objects one node is responsible for in MPI.

        Notes
        -----
        Each CPU will get similar number of objects. E.G. if there are 12 objects and 5
        CPUs, the first 2 CPUs will get 3 objects and the last 3 CPUS will get 2.

        Parameters
        ----------
        objectsForAllCoresToIter: list
            List of all objects that need to have an MPI calculation performed on.
            Note, that since len() is needed this method cannot accept a generator.

        See Also
        --------
        mpiFlatten : used for collecting results
        """
        ntasks = len(objectsForAllCoresToIter)
        numLocalObjects, deficit = divmod(ntasks, armi.MPI_SIZE)
        if armi.MPI_RANK < deficit:
            numLocalObjects += 1
            first = armi.MPI_RANK * numLocalObjects
        else:
            first = armi.MPI_RANK * numLocalObjects + deficit

        for objIndex in range(first, first + numLocalObjects):
            yield objectsForAllCoresToIter[objIndex]

    def invokeHook(self):
        """This method must be overridden in sub-clases.

        This method is called by worker nodes, and has access to the worker node's operator,
        reactor, and settings (through :code:`self.o`, :code:`self.r`, and :code:`self.cs`).
        It must return a boolean value of :code:`True` or :code:`False`, otherwise the worker node
        will raise an exception and terminate execution.

        Returns
        -------
        result : object
            Dependent on implementation
        """
        raise NotImplementedError()


def runActions(o, r, cs, actions, numPerNode=None, serial=False):
    """Run a series of MpiActions in parallel, or in series if :code:`serial=True`.

    Notes
    -----
    The number of actions DOES NOT need to match :code:`armi.MPI_SIZE`.

    Calling this method may invoke MPI Split which will change the MPI_SIZE during the action. This allows someone to
    call MPI operations without being blocked by tasks which are not doing the same thing.
    """
    if not armi.MPI_DISTRIBUTABLE or serial:
        return runActionsInSerial(o, r, cs, actions)

    useForComputation = [True] * armi.MPI_SIZE
    if numPerNode != None:
        if numPerNode < 1:
            raise ValueError("numPerNode must be >= 1")
        numThisNode = {nodeName: 0 for nodeName in armi.MPI_NODENAMES}
        for rank, nodeName in enumerate(armi.MPI_NODENAMES):
            useForComputation[rank] = numThisNode[nodeName] < numPerNode
            numThisNode[nodeName] += 1
    numBatches = int(
        math.ceil(
            len(actions) / float(len([rank for rank in useForComputation if rank]))
        )
    )
    runLog.extra(
        "Running {} MPI actions in parallel over {} batches".format(
            len(actions), numBatches
        )
    )

    queue = list(actions)  # create a new list.. we will use as a queue
    results = []
    batchNum = 0
    while queue:
        actionsThisRound = []
        for useRank in useForComputation:
            actionsThisRound.append(queue.pop(0) if useRank and queue else None)
        realActions = [
            (armi.MPI_NODENAMES[rank], rank, act)
            for rank, act in enumerate(actionsThisRound)
            if act is not None
        ]
        batchNum += 1
        runLog.extra(
            "Distributing {} MPI actions for parallel processing (batch {} of {}):\n{}".format(
                len(realActions),
                batchNum,
                numBatches,
                tabulate.tabulate(realActions, headers=["Nodename", "Rank", "Action"]),
            )
        )
        distrib = DistributionAction(actionsThisRound)
        distrib.broadcast()
        results.append(distrib.invoke(o, r, cs))
    return results


def runActionsInSerial(o, r, cs, actions):
    """Run a series of MpiActions in serial.

    Notes
    -----
    This will set the `MpiAction.serial` attribute to :code:`True`, and the `MpiAction.broadcast` and `MpiAction.gather`
    methods will basically just return the value being supplied.
    """
    results = []
    runLog.extra("Running {} MPI actions in serial".format(len(actions)))
    numActions = len(actions)
    for aa, action in enumerate(actions):
        action.serial = True
        runLog.extra("Running action {} of {}: {}".format(aa + 1, numActions, action))
        results.append(action.invoke(o, r, cs))
        action.serial = False  # return to original state
    return results


class DistributionAction(MpiAction):
    """
    This MpiAction scatters the workload of multiple actions to available resources.

    Notes
    -----
    This currently only works from the root (of COMM_WORLD). Eventually, it would be nice to make
    it possible for sub-tasks to manage their own communicators and spawn their own work within some
    sub-communicator.

    This performs an MPI Split operation and takes over the armi.MPI_COMM and associated varaibles.
    For this reason, it is possible that when someone thinks they have distributed information to all
    nodes, it may only be a subset that was necessary to perform the number of actions needed by this
    DsitributionAction.
    """

    def __init__(self, actions):
        MpiAction.__init__(self)
        self._actions = actions

    def __reduce__(self):
        """Reduce prevents from unnecessary actions to others, after all we only want to scatter.

        Consequently, the worker nodes _actions will be None.
        """
        return DistributionAction, (None,)

    def invokeHook(self):
        """
        Overrides invokeHook to distribute work amongst available resources as requested.

        Notes
        =====
        Two things about this method make it non-recursiv
        """
        canDistribute = armi.MPI_DISTRIBUTABLE
        mpiComm = armi.MPI_COMM
        mpiRank = armi.MPI_RANK
        mpiSize = armi.MPI_SIZE
        mpiNodeNames = armi.MPI_NODENAMES

        if self.cs["verbosity"] == "debug" and mpiRank == 0:
            runLog.debug("Printing diagnostics for MPI actions!")
            objectCountDict = collections.defaultdict(int)
            for debugAction in self._actions:
                utils.classesInHierarchy(debugAction, objectCountDict)
                for objekt, count in objectCountDict.items():
                    runLog.debug(
                        "There are {} {} in MPI action {}".format(
                            count, objekt, debugAction
                        )
                    )

        try:
            action = mpiComm.scatter(self._actions, root=0)
            # create a new communicator that only has these specific dudes running
            armi.MPI_DISTRIBUTABLE = False
            hasAction = action is not None
            armi.MPI_COMM = mpiComm.Split(int(hasAction))
            armi.MPI_RANK = armi.MPI_COMM.Get_rank()
            armi.MPI_SIZE = armi.MPI_COMM.Get_size()
            armi.MPI_NODENAMES = armi.MPI_COMM.allgather(armi.MPI_NODENAME)
            if hasAction:
                return action.invoke(self.o, self.r, self.cs)
        finally:
            # restore the global variables
            armi.MPI_DISTRIBUTABLE = canDistribute
            armi.MPI_COMM = mpiComm
            armi.MPI_RANK = mpiRank
            armi.MPI_SIZE = mpiSize
            armi.MPI_NODENAMES = mpiNodeNames


class MpiActionError(Exception):
    """Exception class raised when error conditions occur during an MpiAction."""


class DistributeStateAction(MpiAction):
    def __init__(self, skipInterfaces=False):
        MpiAction.__init__(self)
        self._skipInterfaces = skipInterfaces

    def invokeHook(self):
        r"""Sync up all nodes with the reactor, the cs, and the interfaces.

        Notes
        -----
        This is run by all workers and the master any time the code needs to sync all processors.

        """

        if armi.MPI_SIZE <= 1:
            runLog.extra("Not distributing state because there is only one processor")
            return
        # Detach phase:
        # The Reactor and the interfaces have links to the Operator, which contains Un-MPI-able objects
        # like the MPI Comm and the SQL database connections.
        runLog.info("Distributing State")
        start = timeit.default_timer()
        try:
            cs = self._distributeSettings()

            self._distributeReactor(cs)

            if self._skipInterfaces:
                self.o.reattach(self.r, cs)  # may be redundant?
            else:
                self._distributeInterfaces()

            # lastly, make sure the reactor knows it is up to date
            # the operator/interface attachment may invalidate some of the cache, but since
            # all the underlying data is the same, ultimately all state should be (initially) the
            # same.
            # XXX: this is an indication we need to revamp either how the operator attachment works
            # or how the interfaces are distributed.
            self.r.core._markSynchronized()  # pylint: disable=protected-access

        except (cPickle.PicklingError, TypeError) as error:
            runLog.error("Failed to transmit on distribute state root MPI bcast")
            runLog.error(error)
            # workers are still waiting for a reactor object
            if armi.MPI_RANK == 0:
                _diagnosePickleError(self.o)
                armi.MPI_COMM.bcast("quit")  # try to get the workers to quit.

            raise

        if armi.MPI_RANK != 0:
            self.r.core.regenAssemblyLists()  # pylint: disable=no-member

        # check to make sure that everything has been properly reattached
        if self.r.core.getFirstBlock().r is not self.r:  # pylint: disable=no-member
            raise RuntimeError("Block.r is not self.r. Reattach the blocks!")

        beforeCollection = timeit.default_timer()

        # force collection; we've just created a bunch of objects that don't need to be used again.
        runLog.debug("Forcing garbage collection.")
        gc.collect()

        stop = timeit.default_timer()
        runLog.extra(
            "Distributed state in {}s, garbage collection took {}s".format(
                beforeCollection - start, stop - beforeCollection
            )
        )

    def _distributeSettings(self):
        if armi.MPI_RANK == 0:
            runLog.debug("Sending the settings object")
        self.cs = cs = self.broadcast(self.o.cs)
        if isinstance(cs, settings.Settings):
            runLog.setVerbosity(
                cs["verbosity"] if armi.MPI_RANK == 0 else cs["branchVerbosity"]
            )
            runLog.debug("Received settings object")
        else:
            raise RuntimeError("Failed to transmit settings, received: {}".format(cs))

        if armi.MPI_RANK != 0:
            settings.setMasterCs(cs)
            self.o.cs = cs
        return cs

    def _distributeReactor(self, cs):
        runLog.debug("Sending the Reactor object")
        r = self.broadcast(self.r)

        if isinstance(r, reactors.Reactor):
            runLog.debug("Received reactor")
        else:
            raise RuntimeError("Failed to transmit reactor, received: {}".format(r))

        if armi.MPI_RANK == 0:
            # on the master node this unfortunately created a __deepcopy__ of the reactor, delete it
            del r
        else:
            # maintain original reactor object on master
            self.r = r
            self.o.r = r

        self.r.o = self.o

        runLog.debug(
            "The reactor has {} assemblies".format(len(self.r.core.getAssemblies()))
        )
        numAssemblies = self.broadcast(assemblies.getAssemNum())
        assemblies.setAssemNumCounter(numAssemblies)
        # attach here so any interface actions use a properly-setup reactor.
        self.o.reattach(self.r, cs)  # sets r and cs

    def _distributeInterfaces(self):
        """
        Distribute the interfaces to all MPI nodes.

        Interface copy description
        Since interfaces store information that can influence a calculation, it is important
        in branch searches to make sure that no information is carried forward from these
        runs on either the master node or the workers.  However, there are interfaces that
        cannot be distributed, making this a challenge.  To solve this problem, any interface
        that cannot be distributed is simply re-initialized.  If any information needs to be
        given to the worker nodes on a non-distributable interface, additional function definitions
        (and likely soul searching as to why needed distributable information is on a
        non-distributable interface) are required to pass the information around.

        See Also
        --------
        armi.interfaces.Interface.preDistributeState : runs on master before DS
        armi.interfaces.Interface.postDistributeState : runs on master after DS
        armi.interfaces.Interface.interactDistributeState : runs on workers after DS

        """
        if armi.MPI_RANK == 0:
            # These run on the master node. (Worker nodes run sychronized code below)
            toRestore = {}
            for i in self.o.getInterfaces():
                if i.distributable() == interfaces.Interface.Distribute.DUPLICATE:
                    runLog.debug("detaching interface {0}".format(i.name))
                    i.detachReactor()
                    toRestore[i] = i.preDistributeState()

            # Verify that the interface stacks are identical.
            runLog.debug("Sending the interface names and flags")
            _dumIList = self.broadcast(
                [(i.name, i.distributable()) for i in self.o.getInterfaces()]
            )

            # transmit interfaces
            for i in self.o.getInterfaces():
                # avoid sending things that don't pickle, like the database.
                if i.distributable() == interfaces.Interface.Distribute.DUPLICATE:
                    runLog.debug("Sending the interface {0}".format(i))
                    _idum = self.broadcast(i)  # don't send the reactor or operator
                    i.postDistributeState(toRestore[i])
                    i.attachReactor(self.o, self.r)
        else:
            # These run on the worker nodes.
            # verify identical interface stack
            # This list is (interfaceName, distributable) tuples)
            interfaceList = self.broadcast(None)
            for iName, distributable in interfaceList:
                iOld = self.o.getInterface(iName)
                if distributable == interfaces.Interface.Distribute.DUPLICATE:
                    # expect a transmission of the interface as a whole.
                    runLog.debug("Receiving new {0}".format(iName))
                    iNew = self.broadcast(None)
                    runLog.debug("Received {0}".format(iNew))
                    if iNew == "quit":
                        return True  # signal the operator to break.
                    self.o.removeInterface(iOld)
                    self.o.addInterface(iNew)
                    iNew.interactDistributeState()  # pylint: disable=no-member
                elif distributable == interfaces.Interface.Distribute.NEW:
                    runLog.debug("Initializing new interface {0}".format(iName))
                    # make a fresh instance of the non-transmittable interface.
                    self.o.removeInterface(iOld)
                    iNew = iOld.__class__(self.r, self.cs)
                    if not iNew:
                        for i in self.o.getInterfaces():
                            runLog.warning(i)
                        raise RuntimeError(
                            "Non-distributable interface {0} exists on the master MPI process "
                            "but not on the workers. "
                            "Cannot distribute state.".format(iName)
                        )
                    self.o.addInterface(iNew)
                    iNew.interactInit()
                    iNew.interactBOL()
                else:
                    runLog.debug("Skipping broadcast of interface {0}".format(iName))
                    if iOld:
                        iOld.interactDistributeState()


def _diagnosePickleError(o):
    r"""
    Scans through various parts of the reactor to identify which part cannot be pickled.

    Notes
    -----
    So, you're having a pickle error and you don't know why. This method will help you
    find the problem. It doesn't always catch everything, but it does help.

    We also find that modifying the Python library as documented here tells us which
    object can't be pickled by printing it out.

    """
    checker = utils.tryPickleOnAllContents3
    runLog.info("-------- Pickle Error Detection -------")
    runLog.info(
        "For reference, the operator is {0} and the reactor is {1}\n"
        "Watch for other reactors or operators, and think about where they came from.".format(
            o, o.r
        )
    )
    runLog.info("Scanning the Reactor for pickle errors")
    checker(o.r, verbose=True)

    runLog.info("Scanning All assemblies for pickle errors")
    for a in o.r.core.getAssemblies(includeAll=True):  # pylint: disable=no-member
        checker(a, ignore=["blockStack"])

    runLog.info("Scanning all blocks for pickle errors")
    for b in o.r.core.getBlocks(includeAll=True):  # pylint: disable=no-member
        checker(b, ignore=["parentAssembly", "r"])

    runLog.info("Scanning blocks by name for pickle errors")
    for _bName, b in o.r.core.blocksByName.items():  # pylint: disable=no-member
        checker(b, ignore=["parentAssembly", "r"])

    runLog.info("Scanning the ISOTXS library for pickle errors")
    checker(o.r.core.lib)  # pylint: disable=no-member

    for interface in o.getInterfaces():
        runLog.info("Scanning {} for pickle errors".format(interface))
        checker(interface)
