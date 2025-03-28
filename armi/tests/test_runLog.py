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
"""Tests of the runLog tooling."""
import logging
import os
import unittest
from io import StringIO
from shutil import rmtree

from armi import runLog
from armi.tests import mockRunLogs
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestRunLog(unittest.TestCase):
    def test_setVerbosityFromInteger(self):
        """Test that the log verbosity can be set with an integer.

        .. test:: The run log verbosity can be configured with an integer.
            :id: T_ARMI_LOG0
            :tests: R_ARMI_LOG
        """
        log = runLog._RunLog(1)
        expectedStrVerbosity = "debug"
        verbosityRank = log.getLogVerbosityRank(expectedStrVerbosity)
        runLog.setVerbosity(verbosityRank)
        self.assertEqual(verbosityRank, runLog.getVerbosity())
        self.assertEqual(verbosityRank, logging.DEBUG)

    def test_setVerbosityFromString(self):
        """
        Test that the log verbosity can be set with a string.

        .. test:: The run log verbosity can be configured with a string.
            :id: T_ARMI_LOG1
            :tests: R_ARMI_LOG
        """
        log = runLog._RunLog(1)
        expectedStrVerbosity = "error"
        verbosityRank = log.getLogVerbosityRank(expectedStrVerbosity)
        runLog.setVerbosity(expectedStrVerbosity)
        self.assertEqual(verbosityRank, runLog.getVerbosity())
        self.assertEqual(verbosityRank, logging.ERROR)

    def test_verbosityOutOfRange(self):
        """Test that the log verbosity setting resets to a canonical value when it is out of range."""
        runLog.setVerbosity(-50)
        self.assertEqual(
            runLog.LOG.logger.level, min([v[0] for v in runLog.LOG.logLevels.values()])
        )

        runLog.setVerbosity(5000)
        self.assertEqual(
            runLog.LOG.logger.level, max([v[0] for v in runLog.LOG.logLevels.values()])
        )

    def test_invalidSetVerbosityByString(self):
        """Test that the log verbosity setting fails if the integer is invalid."""
        with self.assertRaises(KeyError):
            runLog.setVerbosity("taco")

        with self.assertRaises(TypeError):
            runLog.setVerbosity(["debug"])

    def test_parentRunLogging(self):
        """A basic test of the logging of the parent runLog."""
        # init the _RunLog object
        log = runLog.LOG = runLog._RunLog(0)
        log.startLog("test_parentRunLogging")
        runLog.createLogDir(0)
        log.setVerbosity(logging.INFO)

        # divert the logging to a stream, to make testing easier
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        log.logger.handlers = [handler]

        # log some things
        log.log("debug", "You shouldn't see this.", single=False, label=None)
        log.log("warning", "Hello, ", single=False, label=None)
        log.log("error", "world!", single=False, label=None)

        log.logger.flush()
        log.logger.close()
        runLog.close(99)

        # test what was logged
        streamVal = stream.getvalue()
        self.assertIn("Hello", streamVal, msg=streamVal)
        self.assertIn("world", streamVal, msg=streamVal)

    def test_getWhiteSpace(self):
        log = runLog._RunLog(0)
        space0 = len(log.getWhiteSpace(0))
        space1 = len(log.getWhiteSpace(1))
        space9 = len(log.getWhiteSpace(9))

        self.assertGreater(space1, space0)
        self.assertEqual(space1, space9)

    def test_warningReport(self):
        """A simple test of the warning tracking and reporting logic.

        .. test:: Generate a warning report after a simulation is complete.
            :id: T_ARMI_LOG2
            :tests: R_ARMI_LOG
        """
        # create the logger and do some logging
        log = runLog.LOG = runLog._RunLog(321)
        log.startLog("test_warningReport")
        runLog.createLogDir(0)

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
        self.assertIsNotNone(dupsFilter)
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
        self.assertNotIn("invisible", streamVal, msg=streamVal)
        self.assertEqual(streamVal.count("test_warningReport"), 2, msg=streamVal)

        # bonus check: edge case in duplicates filter
        backupLog, log.logger = log.logger, None
        self.assertIsNone(log.getDuplicatesFilter())
        log.logger = backupLog

    def test_warningReportInvalid(self):
        """A test of warningReport in an invalid situation.

        .. test:: Test an important edge case for a warning report.
            :id: T_ARMI_LOG3
            :tests: R_ARMI_LOG
        """
        # create the logger and do some logging
        testName = "test_warningReportInvalid"
        log = runLog.LOG = runLog._RunLog(323)
        log.startLog(testName)
        runLog.createLogDir(0)

        # divert the logging to a stream, to make testing easier
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        log.logger.handlers = [handler]

        # log some things
        log.setVerbosity(logging.INFO)
        log.log("warning", testName, single=True, label=None)
        log.log("debug", "invisible due to log level", single=False, label=None)
        log.log("warning", testName, single=True, label=None)
        log.log("error", "high level something", single=False, label=None)

        # test that the logging found some duplicate outputs
        def returnNone(*args, **kwargs):
            return None

        log.logger.getDuplicatesFilter = returnNone
        self.assertIsNone(log.logger.getDuplicatesFilter())

        # run the warning report
        log.warningReport()
        runLog.close(1)
        runLog.close(0)

        # test what was logged
        streamVal = stream.getvalue()
        self.assertIn(testName, streamVal, msg=streamVal)
        self.assertIn("None Found", streamVal, msg=streamVal)
        self.assertNotIn("invisible", streamVal, msg=streamVal)
        self.assertEqual(streamVal.count(testName), 1, msg=streamVal)

    def test_closeLogging(self):
        """A basic test of the close() functionality."""

        def validate_loggers(log):
            """Little test helper, to make sure our loggers still look right."""
            handlers = [str(h) for h in log.logger.handlers]
            self.assertEqual(len(handlers), 1, msg=",".join(handlers))

            stderrHandlers = [str(h) for h in log.stderrLogger.handlers]
            self.assertEqual(len(stderrHandlers), 1, msg=",".join(stderrHandlers))

        # init logger
        log = runLog.LOG = runLog._RunLog(777)
        validate_loggers(log)

        # start the logging for real
        log.startLog("test_closeLogging")
        runLog.createLogDir()
        validate_loggers(log)

        # close() and test that we have correctly nullified our loggers
        runLog.close(1)
        validate_loggers(log)

        # in a real run, the parent process would close() after all the children
        runLog.close(0)

    def test_setVerbosity(self):
        """Let's test the setVerbosity() method carefully.

        .. test:: The run log has configurable verbosity.
            :id: T_ARMI_LOG4
            :tests: R_ARMI_LOG

        .. test:: The run log can log to stream.
            :id: T_ARMI_LOG_IO0
            :tests: R_ARMI_LOG_IO
        """
        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock.getStdout())
            runLog.LOG.startLog("test_setVerbosity")
            runLog.LOG.setVerbosity(logging.INFO)

            # we should start at info level, and that should be working correctly
            self.assertEqual(runLog.LOG.getVerbosity(), logging.INFO)
            runLog.info("hi")
            self.assertIn("hi", mock.getStdout())
            mock.emptyStdout()

            runLog.debug("invisible")
            self.assertEqual("", mock.getStdout())

            # setVerbosity() to WARNING, and verify it is working
            runLog.LOG.setVerbosity(logging.WARNING)
            runLog.info("still invisible")
            self.assertEqual("", mock.getStdout())
            runLog.warning("visible")
            self.assertIn("visible", mock.getStdout())
            mock.emptyStdout()

            # setVerbosity() to DEBUG, and verify it is working
            runLog.LOG.setVerbosity(logging.DEBUG)
            runLog.debug("Visible")
            self.assertIn("Visible", mock.getStdout())
            mock.emptyStdout()

            # setVerbosity() to ERROR, and verify it is working
            runLog.LOG.setVerbosity(logging.ERROR)
            runLog.warning("Still Invisible")
            self.assertEqual("", mock.getStdout())
            runLog.error("Visible!")
            self.assertIn("Visible!", mock.getStdout())

            # we shouldn't be able to setVerbosity() to a non-canonical value (logging module defense)
            self.assertEqual(runLog.LOG.getVerbosity(), logging.ERROR)
            runLog.LOG.setVerbosity(logging.WARNING + 1)
            self.assertEqual(runLog.LOG.getVerbosity(), logging.WARNING)

    def test_setVerbosityBeforeStartLog(self):
        """The user/dev may accidentally call ``setVerbosity()`` before ``startLog()``,
        this should be mostly supportable. This is just an edge case.

        .. test:: Test that we support the user setting log verbosity BEFORE the logging starts.
            :id: T_ARMI_LOG5
            :tests: R_ARMI_LOG
        """
        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate, before debug logging
            self.assertEqual("", mock.getStdout())
            runLog.LOG.setVerbosity(logging.DEBUG)
            runLog.LOG.startLog("test_setVerbosityBeforeStartLog")

            # we should start at info level, and that should be working correctly
            self.assertEqual(runLog.LOG.getVerbosity(), logging.DEBUG)
            runLog.debug("hi")
            self.assertIn("hi", mock.getStdout())
            mock.emptyStdout()

            # we should start with a clean slate, before info logging
            self.assertEqual("", mock.getStdout())
            runLog.LOG.setVerbosity(logging.INFO)
            runLog.LOG.startLog("test_setVerbosityBeforeStartLog2")

            # we should start at info level, and that should be working correctly
            self.assertEqual(runLog.LOG.getVerbosity(), logging.INFO)
            runLog.debug("nope")
            runLog.info("hi")
            self.assertIn("hi", mock.getStdout())
            self.assertNotIn("nope", mock.getStdout())
            mock.emptyStdout()

    def test_callingStartLogMultipleTimes(self):
        """Calling startLog() multiple times will lead to multiple output files, but logging should still work."""
        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock.getStdout())
            runLog.LOG.startLog("test_callingStartLogMultipleTimes1")
            runLog.LOG.setVerbosity(logging.INFO)

            # we should start at info level, and that should be working correctly
            self.assertEqual(runLog.LOG.getVerbosity(), logging.INFO)
            runLog.info("hi1")
            self.assertIn("hi1", mock.getStdout())
            mock.emptyStdout()

            # call startLog() again
            runLog.LOG.startLog("test_callingStartLogMultipleTimes2")
            runLog.LOG.setVerbosity(logging.INFO)

            # we should start at info level, and that should be working correctly
            self.assertEqual(runLog.LOG.getVerbosity(), logging.INFO)
            runLog.info("hi2")
            self.assertIn("hi2", mock.getStdout())
            mock.emptyStdout()

            # call startLog() again
            runLog.LOG.startLog("test_callingStartLogMultipleTimes3")
            runLog.LOG.setVerbosity(logging.INFO)

            # we should start at info level, and that should be working correctly
            self.assertEqual(runLog.LOG.getVerbosity(), logging.INFO)
            runLog.info("hi3")
            self.assertIn("hi3", mock.getStdout())
            mock.emptyStdout()

            # call startLog() again, with a duplicate logger name
            runLog.LOG.startLog("test_callingStartLogMultipleTimes3")
            runLog.LOG.setVerbosity(logging.INFO)

            # we should start at info level, and that should be working correctly
            self.assertEqual(runLog.LOG.getVerbosity(), logging.INFO)
            runLog.info("hi333")
            self.assertIn("hi333", mock.getStdout())
            mock.emptyStdout()

    def test_concatenateLogs(self):
        """
        Simple test of the concat logs function.

        .. test:: The run log combines logs from different processes.
            :id: T_ARMI_LOG_MPI
            :tests: R_ARMI_LOG_MPI

        .. test:: The run log can log to file.
            :id: T_ARMI_LOG_IO1
            :tests: R_ARMI_LOG_IO
        """
        with TemporaryDirectoryChanger():
            # create the log dir
            logDir = "test_concatenateLogs"
            if os.path.exists(logDir):
                rmtree(logDir)
            runLog.createLogDir(logDir)

            # create as stdout file
            stdoutFile1 = os.path.join(
                logDir, "{}.runLogTest.0000.stdout".format(runLog.STDOUT_LOGGER_NAME)
            )
            with open(stdoutFile1, "w") as f:
                f.write("hello world\n")

            stdoutFile2 = os.path.join(
                logDir, "{}.runLogTest.0001.stdout".format(runLog.STDOUT_LOGGER_NAME)
            )
            with open(stdoutFile2, "w") as f:
                f.write("hello other world\n")

            # verify behavior for a corner case
            stdoutFile3 = os.path.join(
                logDir, "{}..0000.stdout".format(runLog.STDOUT_LOGGER_NAME)
            )
            with open(stdoutFile3, "w") as f:
                f.write("hello world again\n")

            self.assertTrue(os.path.exists(stdoutFile1))
            self.assertTrue(os.path.exists(stdoutFile2))
            self.assertTrue(os.path.exists(stdoutFile3))

            # create a stderr file
            stderrFile = os.path.join(
                logDir, "{}.runLogTest.0000.stderr".format(runLog.STDOUT_LOGGER_NAME)
            )
            with open(stderrFile, "w") as f:
                f.write("goodbye cruel world\n")

            self.assertTrue(os.path.exists(stderrFile))

            # concat logs
            runLog.concatenateLogs(logDir=logDir)

            # verify output
            combinedLogFile = os.path.join(logDir, "runLogTest-mpi.log")
            self.assertTrue(os.path.exists(combinedLogFile))
            self.assertFalse(os.path.exists(stdoutFile1))
            self.assertFalse(os.path.exists(stdoutFile2))
            self.assertFalse(os.path.exists(stdoutFile3))
            self.assertFalse(os.path.exists(stderrFile))

            # verify behavior for a corner case
            stdoutFile3 = os.path.join(
                logDir, "{}..0000.stdout".format(runLog.STDOUT_LOGGER_NAME)
            )
            with open(stdoutFile3, "w") as f:
                f.write("hello world again\n")
            # concat logs
            runLog.concatenateLogs(logDir=logDir)
            # verify output
            combinedLogFile = os.path.join(logDir, "armi-workers-mpi.log")
            self.assertTrue(os.path.exists(combinedLogFile))
            self.assertFalse(os.path.exists(stdoutFile3))

    def test_createLogDir(self):
        """Test the createLogDir() method.

        .. test:: Test that log directories can be created for logging output files.
            :id: T_ARMI_LOG6
            :tests: R_ARMI_LOG
        """
        with TemporaryDirectoryChanger():
            logDir = "test_createLogDir"
            self.assertFalse(os.path.exists(logDir))
            for _ in range(10):
                runLog.createLogDir(logDir)
                self.assertTrue(os.path.exists(logDir))


class TestRunLogger(unittest.TestCase):
    def setUp(self):
        self.rl = runLog.RunLogger("ARMI|things_and_stuff|0")

    def test_getDuplicatesFilter(self):
        df = self.rl.getDuplicatesFilter()
        self.assertEqual(type(df), runLog.DeduplicationFilter)

        self.rl.filters = []
        self.assertIsNone(self.rl.getDuplicatesFilter())

    def test_allowStopDuplicates(self):
        # the usual case, where the DeduplicateFilter already exists
        self.assertEqual(len(self.rl.filters), 1)
        self.rl.allowStopDuplicates()
        self.assertEqual(len(self.rl.filters), 1)

        # the unusual case, where the DeduplicateFilter isn't there
        self.rl.filters = []
        self.assertEqual(len(self.rl.filters), 0)
        self.rl.allowStopDuplicates()
        self.assertEqual(len(self.rl.filters), 1)

    def test_write(self):
        """Test that we can write text to the logger output stream.

        .. test:: Write logging text to the logging stream and/or file.
            :id: T_ARMI_LOG7
            :tests: R_ARMI_LOG
        """
        # divert the logging to a stream, to make testing easier
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        self.rl.handlers = [handler]

        # log some things
        testName = "test_write"
        self.rl.write(testName)

        # test what was logged
        streamVal = stream.getvalue()
        self.assertIn(testName, streamVal, msg=streamVal)
