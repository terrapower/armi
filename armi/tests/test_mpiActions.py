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
"""Tests for MPI actions"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access

import unittest

from armi.mpiActions import (
    _diagnosePickleError,
    DistributeStateAction,
    DistributionAction,
    MpiAction,
    runActions,
    _disableForExclusiveTasks,
    _makeQueue,
)
from armi import context
from armi.reactor.tests import test_reactors
from armi.tests import mockRunLogs
from armi.tests import TEST_ROOT
from armi.utils import iterables


@unittest.skipUnless(context.MPI_RANK == 0, "test only on root node")
class MpiIterTests(unittest.TestCase):
    def setUp(self):
        """save MPI size on entry"""
        self._mpiSize = context.MPI_SIZE
        self.action = MpiAction()

    def tearDown(self):
        """restore MPI rank and size on exit"""
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
        """Test load balancing when numProcs divides numObjects

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
        """Test load balancing when numProcs exceeds numObjects

        In this case, some processes should receive a single object and the
        rest should receive no objects
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
        """Test load balancing for typical case (numProcs < numObjs)

        In this case, the total imbalance should be 1 (except for the perfectly
        balanced case).
        """
        numObjs, numProcs = 25, 6
        allObjs = list(range(numObjs))
        objs = self._distributeObjects(allObjs, numProcs)

        # typical case (more objects than processes)
        counts = [len(o) for o in objs]
        imbalance = max(counts) - min(counts)
        self.assertLessEqual(imbalance, 1)
        self.assertEqual(iterables.flatten(objs), allObjs)

    def test_runActionsDistributionAction(self):
        numObjs, numProcs = 25, 5
        allObjs = list(range(numObjs))
        objs = self._distributeObjects(allObjs, numProcs)

        o, r = test_reactors.loadTestReactor(TEST_ROOT)

        act = DistributionAction([self.action])
        act.invokeHook = passer
        results = runActions(objs, r, o.cs, [act])
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0])

    def test_runActionsDistributeStateAction(self):
        numObjs, numProcs = 25, 5
        allObjs = list(range(numObjs))
        objs = self._distributeObjects(allObjs, numProcs)

        o, r = test_reactors.loadTestReactor(TEST_ROOT)
        act = DistributeStateAction([self.action])

        act.invokeHook = passer
        results = runActions(objs, r, o.cs, [act])
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0])

    def test_diagnosePickleErrorTestReactor(self):
        """Run _diagnosePickleError() on the test reactor.
        We expect this to run all the way through the pickle diagnoser,
        because the test reactor should be easily picklable.
        """
        o, _ = test_reactors.loadTestReactor(TEST_ROOT)

        with mockRunLogs.BufferLog() as mock:
            self.assertEqual("", mock.getStdout())

            # Run the diagnosis on the test reactor
            _diagnosePickleError(o)

            # Hopefully, the test reactor can be pickled, and we get no errors
            self.assertIn("Pickle Error Detection", mock.getStdout())
            self.assertIn("Scanning the Reactor", mock.getStdout())
            self.assertIn("Scanning all assemblies", mock.getStdout())
            self.assertIn("Scanning all blocks", mock.getStdout())
            self.assertIn("Scanning blocks by name", mock.getStdout())
            self.assertIn("Scanning the ISOTXS library", mock.getStdout())


class QueueActionsTests(unittest.TestCase):
    def test_disableForExclusiveTasks(self):
        num = 5
        actionsThisRound = [MpiAction() for _ in range(num - 1)]
        actionsThisRound.append(None)
        useForComputation = [True] * num
        exclusiveIndices = [1, 3]
        for i in exclusiveIndices:
            actionsThisRound[i].runActionExclusive = True

        useForComputation = _disableForExclusiveTasks(
            actionsThisRound, useForComputation
        )
        for i in range(num):
            if i in exclusiveIndices:
                # wont be used for computation in future round
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


def passer():
    """helper function, to do nothing, for unit tests"""
    pass


if __name__ == "__main__":
    unittest.main()
