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

r"""
This module handles logging of console output (e.g. warnings, information, errors)
during an armi run.

The default way of using the ARMI runLog is:

.. code::

    import armi.runLog as runLog
    runLog.setVerbosity('debug')
    runLog.info('information here')
    runLog.error('extra error info here')
    raise SomeException  # runLog.error() implies that the code will crash!

"""
from __future__ import print_function
from glob import glob
import collections
import logging
import operator
import os
import sys
import time

from armi import context


class RunLog:
    """
    Handles all the logging
    For the parent process, things are allowed to print to stdout and stderr,
    but the stdout prints are formatted like log statements.
    For the child processes, everything is piped to log files.
    """

    STDERR_NAME = "{0}.{1:04d}.stderr"
    STDOUT_NAME = "{0}.{1:04d}.stdout"

    def __init__(self, mpiRank=0):
        """
        Build a log object

        Parameters
        ----------
        mpiRank : int
            If this is zero, we are in the parent process, otherwise child process.
            The default of 0 means we assume the parent process.
            This should not be adjusted after instantiation.

        """
        self._mpiRank = mpiRank
        self._verbosity = logging.INFO
        self._singleMessageCounts = collections.defaultdict(lambda: 0)
        self._singleWarningMessageCounts = collections.defaultdict(lambda: 0)
        self.initialErr = None
        self.logger = None
        self.stderrLogger = None
        self._logLevels = None
        self._whitespace = " " * 6

        self._setLogLevels()
        self._createLogDir()

    def _setLogLevels(self):
        """Here we fill the logLevels dict with custom strings that depend on the MPI rank"""
        # NOTE: use ordereddict so we can get right order of options in GUI
        _rank = "" if self._mpiRank == 0 else "-{:>03d}".format(self._mpiRank)
        self._logLevels = collections.OrderedDict(
            [
                ("debug", (logging.DEBUG, "[dbug{}] ".format(_rank))),
                ("extra", (15, "[xtra{}] ".format(_rank))),
                ("info", (logging.DEBUG, "[info{}] ".format(_rank))),
                ("important", (25, "[impt{}] ".format(_rank))),
                ("prompt", (27, "[prmt{}] ".format(_rank))),
                ("warning", (logging.WARNING, "[warn{}] ".format(_rank))),
                ("error", (logging.ERROR, "[err {}] ".format(_rank))),
                ("header", (100, "".format(_rank))),
            ]
        )
        self._whitespace = " " * len(max([l[1] for l in self._logLevels.values()]))

        # modify the logging module strings for printing
        for logValue, shortLogString in self._logLevels.values():
            logging.addLevelName(logValue, shortLogString)

    def log(self, msgType, msg, single=False, label=None):
        """
        Add formatting to a message and handle its singleness, if applicable.

        This is a wrapper around logger.log() that does most of the work and is
        used by all message passers (e.g. info, warning, etc.).
        """
        # Skip writing the message if it is below the set verbosity
        msgVerbosity = self._logLevels[msgType][0]
        if msgVerbosity < self._verbosity:
            return

        # the message label is only used to determine unique for single-print warnings
        if label is None:
            label = msg

        # Skip writing the message if it is single-print warning
        if single and self._msgHasAlreadyBeenEmitted(label, msgType):
            return

        # Do the actual logging, but add that custom indenting first
        msg = self._cleanMsg(msg)
        if self._mpiRank == 0:
            print(self._logLevels[msgType][1] + msg)
        else:
            self.logger.write(msgVerbosity, msg)

    def _cleanMsg(self, msg):
        """Messages need to be strings, and tabbed if multi-line"""
        return str(msg).rstrip().replace("\n", "\n" + self._whitespace)

    def _msgHasAlreadyBeenEmitted(self, label, msgType=""):
        """Return True if the count of the label is greater than 1."""
        if msgType in ("warning", "critical"):
            self._singleWarningMessageCounts[label] += 1
            if self._singleWarningMessageCounts[label] > 1:
                return True
        else:
            self._singleMessageCounts[label] += 1
            if self._singleMessageCounts[label] > 1:
                return True
        return False

    def clearSingleWarnings(self):
        """Reset the single warned list so we get messages again."""
        self._singleMessageCounts.clear()

    def warningReport(self):
        """Summarize all warnings for the run."""
        info("----- Final Warning Count --------")
        info("  {0:^10s}   {1:^25s}".format("COUNT", "LABEL"))

        # sort by labcollections.defaultdict(lambda: 1)
        for label, count in sorted(
            self._singleWarningMessageCounts.items(), key=operator.itemgetter(1)
        ):
            info("  {0:^10s}   {1:^25s}".format(str(count), str(label)))
        info("------------------------------------")

    def _getLogVerbosityRank(self, lvl):
        """Return integer verbosity rank given the string verbosity name."""
        level = lvl.strip().lower()
        if level not in self._logLevels:
            log_strs = list(self._logLevels.keys())
            raise KeyError(
                "{} is not a valid verbosity level. Choose from {}".format(
                    level, log_strs
                )
            )
        return self._logLevels[level][0]

    def setVerbosity(self, level):
        """
        Sets the minimum output verbosity for the logger.

        Any message with a higher verbosity than this will
        be emitted.

        Parameters
        ----------
        level : int or str
            The level to set the log output verbosity to.
            Valid numbers are 0-50 and valid strings are keys of _logLevels

        Examples
        --------
        >>> setVerbosity('debug') -> sets to 0
        >>> setVerbosity(0) -> sets to 0

        """
        if isinstance(level, str):
            self._verbosity = self._getLogVerbosityRank(level)
        elif isinstance(level, int):
            if level < 0 or level > 100:
                raise KeyError(
                    "Invalid verbosity rank {}. ".format(level)
                    + "It needs to be in the range [0, 100]."
                )
            self._verbosity = level
        else:
            raise TypeError("Invalid verbosity rank {}.".format(level))

        if self.logger is not None:
            self.logger.setLevel(self._verbosity)

    def getVerbosity(self):
        """Return the global runLog verbosity."""
        return self._verbosity

    def _restoreErrStream(self):
        """Set the system stderr back to its default (as it was when the run started)."""
        if self.initialErr is not None and self._mpiRank > 0:
            sys.stderr = self.initialErr

    def startLog(self, name):
        """Initialize the streams when parallel processing"""
        # set up the child loggers
        if self._mpiRank > 0:
            # init stdout handler
            filePath = os.path.join(
                "logs", RunLog.STDOUT_NAME.format(name, self._mpiRank)
            )
            fmt = "%(levelname)s%(message)s"
            self.logger = StreamToLogger("ARMI", filePath, self._verbosity, fmt)

            # init stderr handler
            filePath = os.path.join(
                "logs", RunLog.STDERR_NAME.format(name, self._mpiRank)
            )
            fmt = "%(message)s"
            self.stderrLogger = StreamToLogger(
                "ARMI_ERROR", filePath, logging.WARNING, fmt
            )

            # force the error logger onto stderr
            self.initialErr = sys.stderr
            sys.stderr = self.stderrLogger

    def _createLogDir(self):
        """A helper method to create the log directory"""
        # make the directory
        if not os.path.exists("logs"):
            try:
                os.makedirs("logs")
            except FileExistsError:
                pass

        # stall until it shows up in file system (SMB caching issue?)
        while not os.path.exists("logs"):
            time.sleep(0.1)

    def close(self):
        """End use of the log. Concatenate if needed and restore defaults"""
        if self._mpiRank == 0:
            try:
                self.concatenateLogs()
            except IOError as ee:
                warning("Failed to concatenate logs due to IOError.")
                error(ee)
        else:
            if self.stderrLogger:
                _ = [h.close() for h in self.stderrLogger.logger.handlers]
                self.stderrLogger = None
            if self.logger:
                _ = [h.close() for h in self.logger.logger.handlers]
                self.logger = None

        self._restoreErrStream()

    @staticmethod
    def concatenateLogs():
        """
        Concatenate the armi run logs and delete them.

        Should only ever be called by parent.
        """
        # find all the logging-module-based log files
        stdoutFiles = sorted(glob(os.path.join("logs", "*.stdout")))
        if not len(stdoutFiles):
            return

        info(
            "Concatenating {0} log files and standard error streams".format(
                len(stdoutFiles) + 1
            )
        )

        for stdoutName in stdoutFiles:
            # NOTE: If the log file name format changes, this will need to change.
            rank = filePath.split(".")[-2]

            # first, print the log messages for a child process
            with open(stdoutName, "r") as logFile:
                data = logFile.read()
                if data:
                    # only write if there's something to write
                    rankId = "\n{0} RANK {1:03d} STDOUT {2}\n".format(
                        "-" * 10, rank, "-" * 60
                    )
                    print(rankId)
                    print(data)
            try:
                os.remove(stdoutName)
            except OSError:
                warning("Could not delete {0}".format(stdoutName))

            # then print the stderr messages for that child process
            stderrName = stdouitName[:-3] + "err"
            if os.path.exists(stderrName):
                with open(stderrName) as logFile:
                    data = logFile.read()
                    if data:
                        # only write if there's something to write.
                        rankId = "\n{0} RANK {1:03d} STDERR {2}\n".format(
                            "-" * 10, rank, "-" * 60
                        )
                        print(rankId, file=sys.stderr)
                        print(data, file=sys.stderr)
                try:
                    os.remove(stderrName)
                except OSError:
                    warning("Could not delete {0}".format(stderrName))


# Here are all the module-level functions that should be used for most outputs.
# They use the Log object behind the scenes.
def raw(msg):
    """
    Print raw text without any special functionality.
    """
    LOG.log("header", msg, single=False, label=msg)


def extra(msg, single=False, label=None):
    LOG.log("extra", msg, single=single, label=label)


def debug(msg, single=False, label=None):
    LOG.log("debug", msg, single=single, label=label)


def info(msg, single=False, label=None):
    LOG.log("info", msg, single=single, label=label)


def important(msg, single=False, label=None):
    LOG.log("important", msg, single=single, label=label)


def warning(msg, single=False, label=None):
    LOG.log("warning", msg, single=single, label=label)


def error(msg, single=False, label=None):
    LOG.log("error", msg, single=single, label=label)


def header(msg, single=False, label=None):
    LOG.log("header", msg, single=single, label=label)


def warningReport():
    LOG.warningReport()


def setVerbosity(level):
    LOG.setVerbosity(level)


def getVerbosity():
    return LOG.getVerbosity()


# ---------------------------------------


class StreamToLogger:
    """
    File-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, name, filePath, level, fmt):
        self.name = name
        self.filePath = filePath
        self.level = level
        self.fmt = fmt

        # configure the logger
        self.logger = logging.getLogger(self.name)
        form = logging.Formatter(self.fmt)

        if self.filePath:
            h = logging.FileHandler(self.filePath)
        else:
            h = logging.StreamHandler()

        h.setFormatter(form)
        self.logger.addHandler(h)
        self.logger.setLevel(level)

    def write(self, level, message):
        """generic write method, as required by the standard streams"""
        self.logger.log(level, message)

    def flush(self):
        """generic flush method, as required by the standard streams"""
        pass


# ---------------------------------------


def logFactory():
    """Create the default logging object."""
    return RunLog(int(context.MPI_RANK))


LOG = logFactory()
