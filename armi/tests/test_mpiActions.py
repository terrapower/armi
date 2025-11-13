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
"""Tests for MPI actions."""

import unittest
from collections import defaultdict
from unittest.mock import patch

from armi import context
from armi.mpiActions import (
    DistributeStateAction,
    DistributionAction,
    MpiAction,
    _disableForExclusiveTasks,
    _makeQueue,
    runActions,
    runBatchedActions,
)
from armi.reactor.tests import test_reactors
from armi.tests import mockRunLogs
from armi.utils import iterables


class MockMpiComm:
    """Mock MPI Communication library."""

    def allgather(self, name):
        return ["1", "2", "3", "4"]

    def bcast(self, data, root=0):
        return defaultdict(int)

    def Get_rank(self):
        return 1

    def Get_size(self):
        return 4

    def scatter(self, actions, root=0):
        return None

    def Split(self, num):
        return self


class MockMpiAction(MpiAction):
    """Mock MPI Action, to simplify tests."""

    runActionExclusive = False

    def __init__(self, broadcastResult: int = 3, invokeResult: int = 7):
        self.broadcastResult = broadcastResult
        self.invokeResult = invokeResult

    def broadcast(self, obj=None):
        return self.broadcastResult

    def invoke(self, o, r, cs):
        return self.invokeResult


@unittest.skipUnless(context.MPI_RANK == 0, "test only on root node")
class MpiIterTests(unittest.TestCase):
    def setUp(self):
        """Save MPI size on entry."""
        self._mpiSize = context.MPI_SIZE
        self.action = MpiAction()

    def tearDown(self):
        """Restore MPI rank and size on exit."""
        context.MPI_SIZE = self._mpiSize
        context.MPI_RANK = 0

    def test_parallel(self):
        self.action.serial = False
        self.assertTrue(self.action.parallel)

        self.action.serial = True
        self.assertFalse(self.action.parallel)

    def test_serialGather(self):
        self.action.serial = True
        self.assertEqual(len(self.action.gather()), 1)

    def test_mpiIter(self):
        allObjs = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        distObjs = [[0, 1, 2], [3, 4, 5], [6, 7], [8, 9], [10, 11]]

        context.MPI_SIZE = 5
        for rank in range(context.MPI_SIZE):
            context.MPI_RANK = rank
            myObjs = list(self.action.mpiIter(allObjs))
            self.assertEqual(myObjs, distObjs[rank])

    def _distributeObjects(self, allObjs, numProcs):
        context.MPI_SIZE = numProcs
        objs = []
        for context.MPI_RANK in range(context.MPI_SIZE):
            objs.append(list(self.action.mpiIter(allObjs)))
        return objs

    def test_perfectBalancing(self):
        """Test load balancing when numProcs divides numObjects.

        In this case, all processes should get the same number of objects.
        """
        numObjs, numProcs = 25, 5
        allObjs = list(range(numObjs))
        objs = self._distributeObjects(allObjs, numProcs)
        counts = [len(o) for o in objs]
        imbalance = max(counts) - min(counts)

        # ensure we haven't missed any objects
        self.assertEqual(iterables.flatten(objs), allObjs)

        # check imbalance
        self.assertEqual(imbalance, 0)

    def test_excessProcesses(self):
        """Test load balancing when numProcs exceeds numObjects.

        In this case, some processes should receive a single object and the rest should receive no objects.
        """
        numObjs, numProcs = 5, 25
        allObjs = list(range(numObjs))
        objs = self._distributeObjects(allObjs, numProcs)
        counts = [len(o) for o in objs]
        imbalance = max(counts) - min(counts)

        # ensure we haven't missed any objects
        self.assertEqual(iterables.flatten(objs), allObjs)

        # check imbalance
        self.assertLessEqual(imbalance, 1)

    def test_typicalBalancing(self):
        """Test load balancing for typical case (numProcs < numObjs).

        In this case, the total imbalance should be 1 (except for the perfectly balanced case).
        """
        numObjs, numProcs = 25, 6
        allObjs = list(range(numObjs))
        objs = self._distributeObjects(allObjs, numProcs)

        # typical case (more objects than processes)
        counts = [len(o) for o in objs]
        imbalance = max(counts) - min(counts)
        self.assertLessEqual(imbalance, 1)
        self.assertEqual(iterables.flatten(objs), allObjs)

    @patch("armi.context.MPI_COMM", MockMpiComm())
    @patch("armi.context.MPI_SIZE", 4)
    def test_runActionsDistributionAction(self):
        o, r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")

        act = DistributionAction([self.action])
        results = runActions(o, r, o.cs, [act])
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0])

        o.cs["verbosity"] = "debug"
        res = act.invokeHook()
        self.assertIsNone(res)

    @patch("armi.context.MPI_COMM", MockMpiComm())
    @patch("armi.context.MPI_SIZE", 4)
    @patch("armi.context.MPI_NODENAMES", ["node0", "node0", "node1", "node1"])
    @patch("armi.context.MPI_DISTRIBUTABLE", True)
    def test_runBatchedActions(self):
        o, r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")

        actionsByNode = {
            "node0": [MockMpiAction(invokeResult=1)],
            "node1": [MockMpiAction(invokeResult=5), MockMpiAction(invokeResult=11)],
        }

        # run in serial
        with mockRunLogs.BufferLog() as mock:
            results = runBatchedActions(o, r, o.cs, actionsByNode, serial=True)
            self.assertIn("Running 3 MPI actions in serial", mock.getStdout())
        self.assertEqual(len(results), 3)
        self.assertListEqual(results, [1, 5, 11])

        # run in parallel
        with mockRunLogs.BufferLog() as mock:
            results = runBatchedActions(o, r, o.cs, actionsByNode)
            self.assertIn("Running 3 MPI actions in parallel over 2 nodes.", mock.getStdout())
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0])

    @patch("armi.context.MPI_COMM", MockMpiComm())
    @patch("armi.context.MPI_SIZE", 4)
    @patch("armi.context.MPI_NODENAMES", ["node0", "node0", "node1", "node1"])
    @patch("armi.context.MPI_DISTRIBUTABLE", True)
    def test_runBatchedActionsOverload(self):
        """Test that an error is thrown if the number of tasks exceeds number of ranks."""
        o, r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")

        actionsByNode = {
            "node0": [MockMpiAction()],
            "node1": [MockMpiAction(), MockMpiAction(), MockMpiAction()],
        }

        # run in parallel
        with mockRunLogs.BufferLog() as mock:
            with self.assertRaises(ValueError):
                runBatchedActions(o, r, o.cs, actionsByNode)
            self.assertIn("There are more actions (3) than ranks available (2) on node1!", mock.getStdout())

    @patch("armi.context.MPI_COMM", MockMpiComm())
    @patch("armi.context.MPI_SIZE", 4)
    def test_runActionsDistributeStateAction(self):
        o, r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")

        act = DistributeStateAction([self.action])
        results = runActions(o, r, o.cs, [act])
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0])

    @patch("armi.context.MPI_COMM", MockMpiComm())
    @patch("armi.context.MPI_SIZE", 4)
    @patch("armi.context.MPI_DISTRIBUTABLE", True)
    def test_runActionsDistStateActionParallel(self):
        o, r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")

        act = DistributeStateAction([self.action])
        results = runActions(o, r, o.cs, [act])
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0])

    def test_invokeAsMaster(self):
        """Verify that calling invokeAsMaster calls invoke."""
        self.assertEqual(7, MockMpiAction.invokeAsMaster(1, 2, 3))


class QueueActionsTests(unittest.TestCase):
    def test_disableForExclusiveTasks(self):
        num = 5
        actionsThisRound = [MpiAction() for _ in range(num - 1)]
        actionsThisRound.append(None)
        useForComputation = [True] * num
        exclusiveIndices = [1, 3]
        for i in exclusiveIndices:
            actionsThisRound[i].runActionExclusive = True

        useForComputation = _disableForExclusiveTasks(actionsThisRound, useForComputation)
        for i in range(num):
            if i in exclusiveIndices:
                # won't be used for computation in future round
                self.assertFalse(useForComputation[i])
            else:
                self.assertTrue(useForComputation[i])

    def test_makeQueue(self):
        num = 5
        actions = [MpiAction() for _ in range(num)]
        for i, action in enumerate(actions):
            action.runActionExclusive = True
            action.priority = 10 - i  # make it reverse so it actually has to sort
        useForComputation = [True] * (num - 1)
        queue, numBatches = _makeQueue(actions, useForComputation)
        self.assertEqual(numBatches, 2)
        self.assertEqual(len(queue), len(actions))

        lastPriority = -999
        for action in queue:
            # check that when more exclusive than cpus they go to non-exclusive
            self.assertFalse(action.runActionExclusive)
            self.assertGreaterEqual(action.priority, lastPriority)
            lastPriority = action.priority

        exclusiveIndices = [1, 3]
        for i in exclusiveIndices:
            actions[i].runActionExclusive = True
        useForComputation = [True] * (num - 2)
        queue, numBatches = _makeQueue(actions, useForComputation)
        # 3 batches since 2 are exclusive and 3 left over tasks
        self.assertEqual(numBatches, 3)
        # check that they remain exclusive
        for i in exclusiveIndices:
            self.assertTrue(actions[i].runActionExclusive)

        lastPriority = -999
        foundFirstNonExclusive = False
        for action in queue:
            if not action.runActionExclusive:
                foundFirstNonExclusive = True
                # priority order resets for non-exclusive
                lastPriority = -999

            if foundFirstNonExclusive:
                # all after the first nonExclusive should be non-exclusive
                self.assertFalse(action.runActionExclusive)
            self.assertGreaterEqual(action.priority, lastPriority)
            lastPriority = action.priority
