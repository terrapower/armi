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

"""Tests for memoryProfiler."""
import logging
import unittest
from unittest.mock import MagicMock, patch

from armi import runLog
from armi.bookkeeping import memoryProfiler
from armi.bookkeeping.memoryProfiler import (
    getCurrentMemoryUsage,
    getTotalJobMemory,
)
from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT, mockRunLogs


class TestMemoryProfiler(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(
            TEST_ROOT,
            {"debugMem": True},
            inputFileName="smallestTestReactor/armiRunSmallest.yaml",
        )
        self.memPro: memoryProfiler.MemoryProfiler = self.o.getInterface(
            "memoryProfiler"
        )

    def tearDown(self):
        self.o.removeInterface(self.memPro)

    def test_fullBreakdown(self):
        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock.getStdout())
            runLog.LOG.startLog("test_fullBreakdown")
            runLog.LOG.setVerbosity(logging.INFO)

            # we should start at info level, and that should be working correctly
            self.assertEqual(runLog.LOG.getVerbosity(), logging.INFO)
            self.memPro._printFullMemoryBreakdown(reportSize=False)

            # do some basic testing
            self.assertTrue(mock.getStdout().count("UNIQUE_INSTANCE_COUNT") > 10)
            self.assertIn("garbage", mock.getStdout())

    def test_displayMemoryUsage(self):
        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock.getStdout())
            runLog.LOG.startLog("test_displayMemUsage")
            runLog.LOG.setVerbosity(logging.INFO)

            # we should start at info level, and that should be working correctly
            self.assertEqual(runLog.LOG.getVerbosity(), logging.INFO)
            self.memPro.displayMemoryUsage(1)

            # do some basic testing
            self.assertIn("End Memory Usage Report", mock.getStdout())

    def test_printFullMemoryBreakdown(self):
        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock.getStdout())
            runLog.LOG.startLog("test_displayMemUsage")
            runLog.LOG.setVerbosity(logging.INFO)

            # we should start at info level, and that should be working correctly
            self.assertEqual(runLog.LOG.getVerbosity(), logging.INFO)
            self.memPro._printFullMemoryBreakdown(reportSize=True)

            # do some basic testing
            self.assertIn("UNIQUE_INSTANCE_COUNT", mock.getStdout())
            self.assertIn(" MB", mock.getStdout())

    def test_getReferrers(self):
        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock.getStdout())
            testName = "test_getReferrers"
            runLog.LOG.startLog(testName)
            runLog.LOG.setVerbosity(logging.DEBUG)

            # grab the referrers
            self.memPro.getReferrers(self.r)
            memLog = mock.getStdout()

        # test the results
        self.assertGreater(memLog.count("ref for"), 10)
        self.assertLess(memLog.count("ref for"), 50)
        self.assertIn(testName, memLog)
        self.assertIn("Reactor", memLog)
        self.assertIn("core", memLog)

    def test_checkForDuplicateObjectsOnArmiModel(self):
        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock.getStdout())
            testName = "test_checkForDuplicateObjectsOnArmiModel"
            runLog.LOG.startLog(testName)
            runLog.LOG.setVerbosity(logging.IMPORTANT)

            # check for duplicates
            with self.assertRaises(RuntimeError):
                self.memPro.checkForDuplicateObjectsOnArmiModel("cs", self.r.core)

            # validate the outputs are as we expect
            self.assertIn(
                "There are 2 unique objects stored as `.cs`", mock.getStdout()
            )
            self.assertIn("Expected id", mock.getStdout())
            self.assertIn("Expected object", mock.getStdout())
            self.assertIn("These types of objects", mock.getStdout())
            self.assertIn("MemoryProfiler", mock.getStdout())
            self.assertIn("MainInterface", mock.getStdout())

    def test_profileMemoryUsageAction(self):
        pmua = memoryProfiler.ProfileMemoryUsageAction("timeDesc")
        self.assertEqual(pmua.timeDescription, "timeDesc")

    @patch("psutil.virtual_memory")
    @patch("armi.bookkeeping.memoryProfiler.cpu_count")
    def test_getTotalJobMemory(self, mockCpuCount, mockVMem):
        """Use an example node with 50 GB of total physical memory and 10 CPUs."""
        mockCpuCount.return_value = 10
        vMem = MagicMock()
        vMem.total = (1024**3) * 50
        mockVMem.return_value = vMem

        expectedArrangement = {
            (10, 1): 50,
            (1, 10): 50,
            (2, 5): 50,
            (3, 3): 45,
            (4, 1): 20,
            (2, 4): 40,
            (5, 2): 50,
        }
        for compReq, jobMemory in expectedArrangement.items():
            # compReq[0] is nTasks and compReq[1] is cpusPerTask
            self.assertEqual(getTotalJobMemory(compReq[0], compReq[1]), jobMemory)

    @patch("armi.bookkeeping.memoryProfiler.PrintSystemMemoryUsageAction")
    @patch("armi.bookkeeping.memoryProfiler.SystemAndProcessMemoryUsage")
    def test_getCurrentMemoryUsage(
        self, mockSysAndProcMemUse, mockPrintSysMemUseAction
    ):
        """Mock the memory usage across 3 different processes and that the total usage is as expected (6 MB)."""
        self._setMemUseMock(mockPrintSysMemUseAction)
        self.assertAlmostEqual(getCurrentMemoryUsage(), 6 * 1024)

    @patch("armi.bookkeeping.memoryProfiler.PrintSystemMemoryUsageAction")
    @patch("armi.bookkeeping.memoryProfiler.SystemAndProcessMemoryUsage")
    @patch("psutil.virtual_memory")
    @patch("armi.bookkeeping.memoryProfiler.cpu_count")
    def test_printCurrentMemoryState(
        self, mockCpuCount, mockVMem, mock1, mockPrintSysMemUseAction
    ):
        """Use an example node with 50 GB of total physical memory and 10 CPUs while using 6 GB."""
        mockCpuCount.return_value = 10
        vMem = MagicMock()
        vMem.total = (1024**3) * 50
        mockVMem.return_value = vMem
        self._setMemUseMock(mockPrintSysMemUseAction)
        with mockRunLogs.BufferLog() as mockLogs:
            self.memPro.cs = {"cpusPerTask": 1, "nTasks": 10}
            self.memPro.printCurrentMemoryState()
            stdOut = mockLogs.getStdout()
            self.assertIn("Currently using 6.0 GB of memory.", stdOut)
            self.assertIn("There is 44.0 GB of memory left.", stdOut)
            self.assertIn("There is a total allocation of 50.0 GB", stdOut)
            # Try another for funzies where we only use half the available resources on the node
            mockLogs.emptyStdout()
            self.memPro.cs = {"cpusPerTask": 5, "nTasks": 1}
            self.memPro.printCurrentMemoryState()
            stdOut = mockLogs.getStdout()
            self.assertIn("Currently using 6.0 GB of memory.", stdOut)
            self.assertIn("There is 19.0 GB of memory left.", stdOut)
            self.assertIn("There is a total allocation of 25.0 GB", stdOut)

    def test_printCurrentMemoryState_noSetting(self):
        """Test that the try/except works as it should."""
        expectedStr = (
            "To view memory consumed, remaining available, and total allocated for a case, "
            "add the setting 'cpusPerTask' to your application."
        )
        with mockRunLogs.BufferLog() as mockLogs:
            self.memPro.printCurrentMemoryState()
            self.assertIn(expectedStr, mockLogs.getStdout())

    def _setMemUseMock(self, mockPrintSysMemUseAction):
        class mockMemUse:
            def __init__(self, mem: float):
                self.processVirtualMemoryInMB = mem

        instance = mockPrintSysMemUseAction.return_value
        instance.gather.return_value = [
            mockMemUse(1 * 1024),
            mockMemUse(2 * 1024),
            mockMemUse(3 * 1024),
        ]


class KlassCounterTests(unittest.TestCase):
    def get_containers(self):
        container1 = [1, 2, 3, 4, 5, 6, 7, 2.0]
        container2 = ("a", "b", container1, None)
        container3 = {
            "yo": container2,
            "yo1": container1,
            ("t1", "t2"): True,
            "yeah": [],
            "nope": {},
        }

        return container3

    def test_expandContainer(self):
        container = self.get_containers()

        counter = memoryProfiler.KlassCounter(False)
        counter.countObjects(container)

        self.assertEqual(counter.count, 24)
        self.assertEqual(counter[list].count, 2)
        self.assertEqual(counter[dict].count, 2)
        self.assertEqual(counter[tuple].count, 2)
        self.assertEqual(counter[int].count, 7)

    def test_countHandlesRecursion(self):
        container = self.get_containers()
        container1 = container["yo1"]
        container1.append(container1)

        counter = memoryProfiler.KlassCounter(False)
        counter.countObjects(container)

        # despite it now being recursive ... we get the same counts
        self.assertEqual(counter.count, 24)
        self.assertEqual(counter[list].count, 2)
        self.assertEqual(counter[dict].count, 2)
        self.assertEqual(counter[tuple].count, 2)
        self.assertEqual(counter[int].count, 7)
