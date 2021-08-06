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
import unittest

from armi import context, runLog
from armi.tests import mockRunLogs


class TestRunLog(unittest.TestCase):
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
        runLog.setVerbosity(5000)
        self.assertEqual(
            runLog.LOG.logger.level, max([v[0] for v in runLog.LOG._logLevels.values()])
        )

    def test_invalidSetVerbosityByString(self):
        """Test that the log verbosity setting fails if the integer is invalid."""
        with self.assertRaises(KeyError):
            runLog.setVerbosity("taco")

    def test_parentRunLogging(self):
        """A basic test of the logging of the parent runLog"""
        # init the _RunLog object
        log = runLog.LOG = runLog._RunLog(0)  # pylint: disable=protected-access
        log.startLog("test_parentRunLogging")
        context.createLogDir(0)
        log.setVerbosity(logging.INFO)

        # divert the logging to a stream, to make testing easier
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        log.logger.handlers = [handler]

        # log some things
        log.log("debug", "You shouldn't see this.", single=False, label=None)
        log.log("warning", "Hello, ", single=False, label=None)
        log.log("error", "world!", single=False, label=None)
        runLog.close(99)

        # test what was logged
        streamVal = stream.getvalue()
        self.assertIn("Hello", streamVal, msg=streamVal)
        self.assertIn("world", streamVal, msg=streamVal)

    def test_warningReport(self):
        """A simple test of the warning tracking and reporting logic"""
        # create the logger and do some logging
        log = runLog.LOG = runLog._RunLog(321)  # pylint: disable=protected-access
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
        runLog.close(1)
        runLog.close(0)

        # test what was logged
        streamVal = stream.getvalue()
        self.assertIn("test_warningReport", streamVal, msg=streamVal)
        self.assertIn("Final Warning Count", streamVal, msg=streamVal)
        self.assertEqual(streamVal.count("test_warningReport"), 2, msg=streamVal)

    def test_closeLogging(self):
        """A basic test of the close() functionality"""

        def validate_loggers(log):
            """little test helper, to make sure our loggers still look right"""
            handlers = [str(h) for h in log.logger.handlers]
            self.assertEqual(len(handlers), 1, msg=",".join(handlers))

            stderrHandlers = [str(h) for h in log.stderrLogger.handlers]
            self.assertEqual(len(stderrHandlers), 1, msg=",".join(stderrHandlers))

        # init logger
        log = runLog.LOG = runLog._RunLog(777)  # pylint: disable=protected-access
        validate_loggers(log)

        # start the logging for real
        log.startLog("test_closeLogging")
        context.createLogDir(0)
        validate_loggers(log)

        # close() and test that we have correctly nullified our loggers
        runLog.close(1)
        validate_loggers(log)

        # in a real run, the parent process would close() after all the children
        runLog.close(0)

    def test_setVerbosity(self):
        """Let's test the setVerbosity() method carefully"""
        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock._outputStream)  # pylint: disable=protected-access
            runLog.LOG.startLog("test_setVerbosity")
            runLog.LOG.setVerbosity(logging.INFO)

            # we should start at info level, and that should be working correctly
            self.assertEqual(runLog.LOG.getVerbosity(), logging.INFO)
            runLog.info("hi")
            self.assertIn("hi", mock._outputStream)
            mock._outputStream = ""

            runLog.debug("invisible")
            self.assertEqual("", mock._outputStream)

            # if we use setVerbosity() to change the log level, it should work
            runLog.LOG.setVerbosity(logging.WARNING)

            runLog.info("still invisible")
            self.assertEqual("", mock._outputStream)

            runLog.warning("visible")
            self.assertIn("visible", mock._outputStream)

            # we shouldn't be able to setVerbosity() to a non-canonical value (logging module defense)
            self.assertEqual(runLog.LOG.getVerbosity(), logging.WARNING)
            runLog.LOG.setVerbosity(logging.WARNING + 1)
            self.assertEqual(runLog.LOG.getVerbosity(), logging.WARNING)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
