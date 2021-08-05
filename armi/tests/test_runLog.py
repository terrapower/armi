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

from io import StringIO
import logging
import os
import pytest
import shutil
import unittest

from armi import context, runLog


class TestRunLog(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        """This pytest fixture allows us to caption logging messages that pytest interupts"""
        self._caplog = caplog

    def test_setVerbosityFromInteger(self):
        """Test that the log verbosity can be set with an integer."""
        log = runLog._RunLog(1)  # pylint: disable=bare-except
        expectedStrVerbosity = "debug"
        verbosityRank = log._getLogVerbosityRank(expectedStrVerbosity)
        runLog.setVerbosity(verbosityRank)
        self.assertEqual(verbosityRank, runLog.getVerbosity())
        self.assertEqual(verbosityRank, logging.DEBUG)

    def test_setVerbosityFromString(self):
        """Test that the log verbosity can be set with a string."""
        log = runLog._RunLog(1)  # pylint: disable=bare-except
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

    def test_parentRunLogging(self):
        """A basic test of the logging of the parent runLog"""
        # init the _RunLog object
        log = runLog.LOG = runLog._RunLog(0)  # pylint: disable=bare-except
        log.startLog("test_parentRunLogging")
        context.createLogDir(0)

        # divert the logging to a stream, to make testing easier
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        log.logger.handlers = [handler]

        # log some things
        log.log("debug", "You shouldn't see this.", single=False, label=None)
        log.log("warning", "Hello, ", single=False, label=None)
        log.log("error", "world!", single=False, label=None)
        runLog.close()

        # test what was logged
        streamVal = stream.getvalue()
        self.assertIn("Hello", streamVal, msg=streamVal)
        self.assertIn("world", streamVal, msg=streamVal)

    def test_warningReport(self):
        """A simple test of the warning tracking and reporting logic"""
        # create the logger and do some logging
        log = runLog.LOG = runLog._RunLog(321)  # pylint: disable=bare-except
        log.startLog("test_warningReport")
        context.createLogDir(0)

        # divert the logging to a stream, to make testing easier
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        log.logger.handlers = [handler]

        # log some things
        log.setVerbosity(logging.INFO)
        log.log("warning", "test_warningReport", single=True, label=None)
        log.log("debug", "invisible due to log level", single=False, label=None)
        log.log("warning", "test_warningReport", single=True, label=None)
        log.log("error", "high level something", single=False, label=None)

        # test that the logging found some duplicate outputs
        dupsFilter = log.getDuplicatesFilter()
        self.assertTrue(dupsFilter is not None)
        warnings = dupsFilter.singleWarningMessageCounts
        self.assertGreater(len(warnings), 0)

        # run the warning report
        log.warningReport()

        # test what was logged
        streamVal = stream.getvalue()
        self.assertIn("test_warningReport", streamVal, msg=streamVal)
        self.assertIn("Final Warning Count", streamVal, msg=streamVal)
        self.assertEqual(streamVal.count("test_warningReport"), 2, msg=streamVal)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
