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
Tests for memoryProfiler.
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import logging
import unittest

from armi import runLog
from armi.bookkeeping import memoryProfiler
from armi.reactor.tests import test_reactors
from armi.tests import mockRunLogs, TEST_ROOT


class TestMemoryProfiler(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(TEST_ROOT, {"debugMem": True})
        self.memPro = self.o.getInterface("memoryProfiler")

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
