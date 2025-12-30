# Copyright 2021 TerraPower, LLC
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
Tests for featurest that need MPI, and thus require special testing.

These tests will be generally ignored by pytest if you are trying to run
them in an environment without MPI installed.

To run these tests from the commandline, install MPI, mpi4py, and do:

mpiexec -n 2 python -m pytest armi/tests/test_mpiFeatures.py
or
mpiexec.exe -n 2 python -m pytest armi/tests/test_mpiFeatures.py
"""

import os
import shutil
import unittest
from unittest.mock import patch

from armi import context, mpiActions, settings
from armi.interfaces import Interface
from armi.mpiActions import DistributeStateAction
from armi.operators import OperatorMPI
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.reactor import blueprints, reactors
from armi.reactor.parameters import parameterDefinitions
from armi.reactor.tests import test_reactors
from armi.tests import ARMI_RUN_PATH, TEST_ROOT, mockRunLogs
from armi.utils import pathTools
from armi.utils.directoryChangers import TemporaryDirectoryChanger

# determine if this is a parallel run, and MPI is installed
MPI_EXE = None
if shutil.which("mpiexec.exe") is not None:
    MPI_EXE = "mpiexec.exe"
elif shutil.which("mpiexec") is not None:
    MPI_EXE = "mpiexec"

MPI_COMM = context.MPI_COMM


class FailingInterface1(Interface):
    """utility classes to make sure the logging system fails properly."""

    name = "failer"

    def interactEveryNode(self, cycle, node):
        raise RuntimeError("Failing interface failure")


class FailingInterface2(Interface):
    """utility class to make sure the logging system fails properly."""

    name = "failer"

    def interactEveryNode(self, cycle, node):
        raise RuntimeError("Failing interface critical failure")


class FailingInterface3(Interface):
    """fails on worker operate."""

    name = "failer"

    def fail(self):
        raise RuntimeError("Failing interface critical worker failure")

    def interactEveryNode(self, c, n):
        context.MPI_COMM.bcast("fail", root=0)

    def workerOperate(self, cmd):
        if cmd == "fail":
            self.fail()
            return True
        return False


class MockInterface(Interface):
    name = "mockInterface"

    def interactInit(self):
        pass


class MpiOperatorTests(unittest.TestCase):
    """Testing the MPI parallelization operator."""

    def setUp(self):
        self.old_op, self.r = test_reactors.loadTestReactor(
            TEST_ROOT, inputFileName="smallestTestReactor/armiRunSmallest.yaml"
        )
        self.o = OperatorMPI(cs=self.old_op.cs)
        self.o.r = self.r

    @patch("armi.operators.Operator.operate")
    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_basicOperatorMPI(self, mockOpMpi):
        """Test we can drive a parallel operator.

        .. test:: Run a parallel operator.
            :id: T_ARMI_OPERATOR_MPI0
            :tests: R_ARMI_OPERATOR_MPI
        """
        with mockRunLogs.BufferLog() as mock:
            self.o.operate()
            self.assertIn("OperatorMPI.operate", mock.getStdout())

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_primaryException(self):
        """Test a custom interface that only fails on the main process.

        .. test:: Run a parallel operator that fails online on the main process.
            :id: T_ARMI_OPERATOR_MPI1
            :tests: R_ARMI_OPERATOR_MPI
        """
        self.o.removeAllInterfaces()
        failer = FailingInterface1(self.o.r, self.o.cs)
        self.o.addInterface(failer)

        if context.MPI_RANK == 0:
            self.assertRaises(RuntimeError, self.o.operate)
        else:
            self.o.operate()

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_primaryCritical(self):
        self.o.removeAllInterfaces()
        failer = FailingInterface2(self.o.r, self.o.cs)
        self.o.addInterface(failer)

        if context.MPI_RANK == 0:
            self.assertRaises(Exception, self.o.operate)
        else:
            self.o.operate()

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_finalizeInteract(self):
        """Test to make sure workers are reset after interface interactions."""
        # Add a random number of interfaces
        interface = MockInterface(self.o.r, self.o.cs)
        self.o.addInterface(interface)

        with mockRunLogs.BufferLog() as mock:
            if context.MPI_RANK == 0:
                self.o.interactAllInit()
                context.MPI_COMM.bcast("quit", root=0)
                context.MPI_COMM.bcast("finished", root=0)
            else:
                self.o.workerOperate()

            logMessage = "Workers have been reset." if context.MPI_RANK == 0 else "Workers are being reset."
            numCalls = len([line for line in mock.getStdout().splitlines() if logMessage in line])
            self.assertGreaterEqual(numCalls, 1)


# these two must be defined up here so that they can be pickled
class BcastAction1(mpiActions.MpiAction):
    def invokeHook(self):
        nItems = 50
        results = [None] * nItems
        for objIndex in range(nItems):
            if objIndex % context.MPI_SIZE == context.MPI_RANK:
                results[objIndex] = objIndex

        allResults = self.gather(results)

        if allResults:
            return [allResults[ai % context.MPI_SIZE][ai] for ai in range(nItems)]
        else:
            return []


class BcastAction2(mpiActions.MpiAction):
    def invokeHook(self):
        results = []
        for num in self.mpiIter(range(50)):
            results.append(num)

        allResults = self.gather(results)
        if allResults:
            return self.mpiFlatten(allResults)
        else:
            return []


class MpiDistributeStateTests(unittest.TestCase):
    def setUp(self):
        self.cs = settings.Settings(fName=ARMI_RUN_PATH)
        bp = blueprints.loadFromCs(self.cs)

        self.o = OperatorMPI(self.cs)
        self.o.r = reactors.factory(self.cs, bp)
        self.action = DistributeStateAction()
        self.action.o = self.o
        self.action.r = self.o.r

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_distributeSettings(self):
        """Under normal circumstances, we would not test "private" methods;
        however, distributeState is quite complicated.
        """
        self.action._distributeSettings()
        if context.MPI_RANK == 0:
            self.assertEqual(self.cs, self.action.o.cs)
        else:
            self.assertNotEqual(self.cs, self.action.o.cs)
            original = {ss.name: ss.value for ss in self.cs.values()}
            current = {ss.name: ss.value for ss in self.action.o.cs.values()}
            # remove values that are *expected to be* different...
            # CONF_CROSS_SECTION is removed because unittest is being mean about
            # comparing dicts...
            for key in ["stationaryBlockFlags", "verbosity", CONF_CROSS_SECTION]:
                if key in original:
                    del original[key]
                if key in current:
                    del current[key]

            for key in original.keys():
                self.assertEqual(original[key], current[key])

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_distributeReactor(self):
        """Under normal circumstances, we would not test "private" methods;
        however, distributeState is quite complicated.
        """
        original_reactor = self.action.r
        self.action._distributeReactor(self.cs)
        if context.MPI_RANK == 0:
            self.assertEqual(original_reactor, self.action.r)
        else:
            self.assertNotEqual(original_reactor, self.action.r)
        self.assertIsNone(self.action.r.core.lib)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_distributeInterfaces(self):
        """Under normal circumstances, we would not test "private" methods;
        however, distributeState is quite complicated.
        """
        original_interfaces = self.o.interfaces
        self.action._distributeInterfaces()
        if context.MPI_RANK == 0:
            self.assertEqual(original_interfaces, self.o.interfaces)
        else:
            self.assertEqual(original_interfaces, self.o.interfaces)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_distributeState(self):
        original_reactor = self.o.r
        original_lib = self.o.r.core.lib
        original_interfaces = self.o.interfaces
        original_bolassems = self.o.r.blueprints.assemblies
        self.action.invokeHook()

        if context.MPI_RANK == 0:
            self.assertEqual(self.cs, self.o.cs)
            self.assertEqual(original_reactor, self.o.r)
            self.assertEqual(original_interfaces, self.o.interfaces)
            self.assertDictEqual(original_bolassems, self.o.r.blueprints.assemblies)
            self.assertEqual(original_lib, self.o.r.core.lib)
        else:
            self.assertNotEqual(self.cs, self.o.cs)
            self.assertNotEqual(original_reactor, self.o.r)
            self.assertNotEqual(original_bolassems, self.o.r.blueprints.assemblies)
            self.assertEqual(original_interfaces, self.o.interfaces)
            self.assertEqual(original_lib, self.o.r.core.lib)

        for pDef in parameterDefinitions.ALL_DEFINITIONS:
            self.assertFalse(pDef.assigned & parameterDefinitions.SINCE_LAST_DISTRIBUTE_STATE)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_compileResults(self):
        action1 = BcastAction1()
        context.MPI_COMM.bcast(action1)
        results1 = action1.invoke(None, None, None)

        action2 = BcastAction2()
        context.MPI_COMM.bcast(action2)
        results2 = action2.invoke(None, None, None)
        self.assertEqual(results1, results2)


class MpiPathToolsTests(unittest.TestCase):
    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_cleanPathMpi(self):
        """Simple tests of cleanPath(), in the MPI scenario."""
        with TemporaryDirectoryChanger():
            # TEST 0: File is not safe to delete, due to due not being a temp dir or under FAST_PATH
            filePath0 = "test0_cleanPathNoMpi"
            open(filePath0, "w").write("something")
            self.assertTrue(os.path.exists(filePath0))
            with self.assertRaises(Exception):
                pathTools.cleanPath(filePath0, mpiRank=context.MPI_RANK)
            MPI_COMM.barrier()

            # TEST 1: Delete a single file under FAST_PATH
            filePath1 = os.path.join(context.getFastPath(), "test1_cleanPathNoMpi")
            open(filePath1, "w").write("something")
            self.assertTrue(os.path.exists(filePath1))
            pathTools.cleanPath(filePath1, mpiRank=context.MPI_RANK)
            MPI_COMM.barrier()
            self.assertFalse(os.path.exists(filePath1))

            # TEST 2: Delete an empty directory under FAST_PATH
            dir2 = os.path.join(context.getFastPath(), "gimmeonereason")
            os.mkdir(dir2)
            self.assertTrue(os.path.exists(dir2))
            pathTools.cleanPath(dir2, mpiRank=context.MPI_RANK)
            MPI_COMM.barrier()
            self.assertFalse(os.path.exists(dir2))

            # TEST 3: Delete an empty directory with tempDir=True
            dir3 = "tostayhere"
            os.mkdir(dir3)
            self.assertTrue(os.path.exists(dir3))
            pathTools.cleanPath(dir3, mpiRank=context.MPI_RANK, tempDir=True)
            MPI_COMM.barrier()
            self.assertFalse(os.path.exists(dir3))

            # TEST 3: Delete a directory with two files inside with tempDir=True
            dir4 = "andilldirrightbackaround"
            os.mkdir(dir4)
            open(os.path.join(dir4, "file1.txt"), "w").write("something1")
            open(os.path.join(dir4, "file2.txt"), "w").write("something2")
            self.assertTrue(os.path.exists(dir4))
            self.assertTrue(os.path.exists(os.path.join(dir4, "file1.txt")))
            self.assertTrue(os.path.exists(os.path.join(dir4, "file2.txt")))
            pathTools.cleanPath(dir4, mpiRank=context.MPI_RANK, tempDir=True)
            MPI_COMM.barrier()
            self.assertFalse(os.path.exists(dir4))


class TestContextMpi(unittest.TestCase):
    """Parallel tests for the Context module."""

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_rank(self):
        self.assertGreater(context.MPI_RANK, -1)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_nonNoneData(self):
        self.assertGreater(len(context.APP_DATA), 0)
        self.assertGreater(len(context.DOC), 0)
        self.assertGreater(len(context.getFastPath()), 0)
        self.assertGreater(len(context.PROJECT_ROOT), 0)
        self.assertGreater(len(context.RES), 0)
        self.assertGreater(len(context.ROOT), 0)
        self.assertGreater(len(context.USER), 0)
