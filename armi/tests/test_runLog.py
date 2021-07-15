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

import logging
import os
import pytest
import sys
import unittest

from armi import context, runLog


class TestRunLog(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        """This pytest fixture allows us to caption logging messages that pytest interupts"""
        self._caplog = caplog

    def test_setVerbosityFromInteger(self):
        """Test that the log verbosity can be set with an integer."""
        log = runLog.RunLog(1)
        expectedStrVerbosity = "debug"
        verbosityRank = log._getLogVerbosityRank(expectedStrVerbosity)
        runLog.setVerbosity(verbosityRank)
        self.assertEqual(verbosityRank, runLog.getVerbosity())
        self.assertEqual(verbosityRank, logging.DEBUG)

    def test_setVerbosityFromString(self):
        """Test that the log verbosity can be set with a string."""
        log = runLog.RunLog(1)
        expectedStrVerbosity = "error"
        verbosityRank = log._getLogVerbosityRank(expectedStrVerbosity)
        runLog.setVerbosity(expectedStrVerbosity)
        self.assertEqual(verbosityRank, runLog.getVerbosity())
        self.assertEqual(verbosityRank, logging.ERROR)

    def test_invalidSetVerbosityByRank(self):
        """Test that the log verbosity setting fails if the integer is invalid."""
        with self.assertRaises(KeyError):
            runLog.setVerbosity(5000)

    def test_invalidSetVerbosityByString(self):
        """Test that the log verbosity setting fails if the integer is invalid."""
        with self.assertRaises(KeyError):
            runLog.setVerbosity("taco")

    def test_createLogDir(self):
        """Test the createLogDir() method"""
        log = runLog.RunLog(1)
        log._createLogDir()
        self.assertTrue(os.path.exists("logs"))

    @unittest.skipIf(context.MPI_COMM is None, "MPI libraries are not installed.")
    def test_caplogBasicRunLogging(self):
        """A basic test of the logging of the child runLog"""
        with self._caplog.at_level(logging.WARNING):
            runLog.setVerbosity("info")
            log = runLog.RunLog(1)
            log._createLogDir()
            log.startLog("test_caplogBasicChildRunLog")
            log.log("debug", "You shouldn't see this.", single=False, label=None)
            log.log("warning", "Hello, ", single=False, label=None)
            log.log("error", "world!", single=False, label=None)
            log.close()

        messages = [r.message for r in self._caplog.records]
        self.assertGreater(len(messages), 0)
        self.assertIn("Hello", messages[0])
        self.assertIn("world", messages[1])

    @unittest.skipIf(context.MPI_COMM is None, "MPI libraries are not installed.")
    def test_warningReport(self):
        """A simple test of the warning tracking and reporting logic"""
        with self._caplog.at_level(logging.INFO):
            runLog.setVerbosity("info")
            log = runLog.RunLog(1)
            log.startLog("test_warningReport")
            log.log("warning", "hello", single=True, label=None)
            log.log("debug", "invisible due to log level", single=False, label=None)
            log.log("warning", "hello", single=True, label=None)
            log.log("error", "invisible due to log level", single=False, label=None)
            self.assertEqual(
                len(log._singleWarningMessageCounts), 1
            )  # pylint: disable=protected-access
            log.warningReport()
            log.close()

        messages = [r.message for r in self._caplog.records]
        self.assertEqual(len(messages), 2)
        self.assertIn("hello", messages[0])


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
