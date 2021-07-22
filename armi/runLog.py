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

You can interact with the logger in much the same way now by doing:

.. code::

    import logging
    runLog = logging.getLogger('whatever')

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


# global constants
_WHITE_SPACE = " " * 6
_ADD_LOG_METHOD_STR = """def {0}(self, message, *args, **kws):
    if self.isEnabledFor({1}):
        self._log({1}, message, args, **kws)
logging.Logger.{0} = {0}"""


class _RunLog:
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
        self.initialErr = None
        self._logLevels = None
        self.logger = logging.getLogger("NULL")
        self.logger.addHandler(logging.NullHandler())
        self.stderrLogger = logging.getLogger("NULL2")
        self.stderrLogger.addHandler(logging.NullHandler())

        self._setLogLevels()

    def _setLogLevels(self):
        """Here we fill the logLevels dict with custom strings that depend on the MPI rank"""
        # NOTE: use ordereddict so we can get right order of options in GUI
        _rank = "" if self._mpiRank == 0 else "-{:>03d}".format(self._mpiRank)
        self._logLevels = collections.OrderedDict(
            [
                ("debug", (logging.DEBUG, "[dbug{}] ".format(_rank))),
                ("extra", (15, "[xtra{}] ".format(_rank))),
                ("info", (logging.INFO, "[info{}] ".format(_rank))),
                ("important", (25, "[impt{}] ".format(_rank))),
                ("prompt", (27, "[prmt{}] ".format(_rank))),
                ("warning", (logging.WARNING, "[warn{}] ".format(_rank))),
                ("error", (logging.ERROR, "[err {}] ".format(_rank))),
                ("header", (100, "".format(_rank))),
            ]
        )
        global _WHITE_SPACE
        _WHITE_SPACE = " " * len(max([l[1] for l in self._logLevels.values()]))

        # modify the logging module strings for printing
        for longLogString, (logValue, shortLogString) in self._logLevels.items():
            # add the log string name (upper and lower) to logging module
            logging.addLevelName(logValue, shortLogString.upper())
            logging.addLevelName(logValue, shortLogString)

            # ensure that we add any custom logging levels as constants to the module, e.g. logging.HEADER
            try:
                getattr(logging, longLogString.upper())
            except AttributeError:
                setattr(logging, longLogString.upper(), logValue)

            # Add logging methods for our new custom levels: LOG.extra("message")
            try:
                getattr(logging, longLogString)
            except AttributeError:
                exec(_ADD_LOG_METHOD_STR.format(longLogString, logValue))

    def log(self, msgType, msg, single=False, label=None):
        """
        This is a wrapper around logger.log() that does most of the work and is
        used by all message passers (e.g. info, warning, etc.).

        In this situation, we do the mangling needed to get the log level to the correct number.
        And we do some custom string manipulation so we can handle de-duplicating warnings.
        """
        # Determine the log level: users can optionally pass in custom strings ("debug")
        msgLevel = msgType if isinstance(msgType, int) else self._logLevels[msgType][0]

        # If this is a special "don't duplicate me" string, we need to add that info to the msg temporarily
        msg = str(msg)

        # Do the actual logging
        self.logger.log(msgLevel, msg, single=single, label=label)

    def getDuplicatesFilter(self):
        """
        The top-level ARMI logger should have a no duplicates filter
        If it exists, find it.
        """
        if not self.logger or not isinstance(self.logger, logging.Logger):
            return None

        return self.logger.getDuplicatesFilter()

    def clearSingleWarnings(self):
        """Reset the single warned list so we get messages again."""
        dupsFilter = self.getDuplicatesFilter()
        if dupsFilter:
            dupsFilter.singleMessageCounts.clear()

    def warningReport(self):
        """Summarize all warnings for the run."""
        self.logger.warningReport()

    def _getLogVerbosityRank(self, level):
        """Return integer verbosity rank given the string verbosity name."""
        try:
            return self._logLevels[level][0]
        except KeyError:
            log_strs = list(self._logLevels.keys())
            raise KeyError(
                "{} is not a valid verbosity level: {}".format(level, log_strs)
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
            for h in self.logger.handlers:
                h.setLevel(self._verbosity)
            self.logger.setLevel(self._verbosity)

    def getVerbosity(self):
        """Return the global runLog verbosity."""
        return self._verbosity

    def _restoreStandardStreams(self):
        """Set the system stderr back to its default (as it was when the run started)."""
        if self.initialErr is not None and self._mpiRank > 0:
            sys.stderr = self.initialErr

    def startLog(self, name):
        """Initialize the streams when parallel processing"""
        self.logger = RunLogger("ARMI", mpiRank=self._mpiRank)

        if self._mpiRank != 0:
            # init stderr intercepting logging
            filePath = os.path.join(
                "logs", _RunLog.STDERR_NAME.format(name, self._mpiRank)
            )
            self.stderrLogger = logging.Logger("ARMI_ERROR")
            h = logging.FileHandler(filePath)
            fmt = "%(message)s"
            form = logging.Formatter(fmt)
            h.setFormatter(form)
            h.setLevel(logging.WARNING)
            self.stderrLogger.handlers = [h]
            self.stderrLogger.setLevel(logging.WARNING)

            # force the error logger onto stderr
            self.initialErr = sys.stderr
            sys.stderr = self.stderrLogger


def close():
    """End use of the log. Concatenate if needed and restore defaults"""
    if context.MPI_RANK == 0:
        try:
            concatenateLogs()
        except IOError as ee:
            warning("Failed to concatenate logs due to IOError.")
            error(ee)
    else:
        if LOG.stderrLogger:
            _ = [h.close() for h in LOG.stderrLogger.logger.handlers]
            LOG.stderrLogger = None
        if LOG.logger:
            _ = [h.close() for h in LOG.logger.logger.handlers]
            LOG.logger = None

    LOG._restoreStandardStreams()


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
        rank = int(stdoutName.split(".")[-2])

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
        stderrName = stdoutName[:-3] + "err"
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


class DeduplicationFilter(logging.Filter):
    """
    Important logging filter

    * allow users to turn off duplicate warnings
    * handles special indentation rules for our logs
    """

    def __init__(self, *args, **kwargs):
        super(DeduplicationFilter, self).__init__(*args, **kwargs)
        self.singleMessageCounts = {}
        self.singleWarningMessageCounts = {}

    def filter(self, record):
        # determine if this is a "do not duplicate" message
        msg = str(record.msg)
        single = getattr(record, "single", False)
        label = getattr(record, "label", msg)
        label = msg if label is None else label

        # If the message is set to "do not duplicate" we may filter it out
        if single:
            if record.levelno in (logging.WARNING, logging.CRITICAL):
                if label not in self.singleWarningMessageCounts:
                    self.singleWarningMessageCounts[label] = 1
                else:
                    self.singleWarningMessageCounts[label] += 1
                    return False
            else:
                if label not in self.singleMessageCounts:
                    self.singleMessageCounts[label] = 1
                else:
                    self.singleMessageCounts[label] += 1
                    return False

        # Handle some special string-mangling we want to do, for multi-line messages
        record.msg = msg.rstrip().replace("\n", "\n" + _WHITE_SPACE)
        return True


class RunLogger(logging.Logger):
    """Custom Logger to support:

    1. Giving users the option to de-duplicate warnings
    2. Piping stderr to a log file
    """

    FMT = "%(levelname)s%(message)s"

    def __init__(self, *args, **kwargs):
        # optionally, the user can pass in the MPI_RANK
        mpiRank = int(kwargs.pop("mpiRank", context.MPI_RANK))

        super(RunLogger, self).__init__(*args, **kwargs)
        self.allowStopDuplicates()

        if mpiRank == 0:
            h = logging.StreamHandler()
            h.setLevel(logging.INFO)
            self.setLevel(logging.INFO)
        else:
            filePath = os.path.join(
                "logs", _RunLog.STDOUT_NAME.format(args[0], mpiRank)
            )
            h = logging.FileHandler(filePath)
            h.setLevel(logging.WARNING)
            self.setLevel(logging.WARNING)

        form = logging.Formatter(RunLogger.FMT)
        h.setFormatter(form)
        self.addHandler(h)

    def log(self, msgType, msg, single=False, label=None):
        """
        This is a wrapper around logger.log() that does most of the work and is
        used by all message passers (e.g. info, warning, etc.).

        In this situation, we do the mangling needed to get the log level to the correct number.
        And we do some custom string manipulation so we can handle de-duplicating warnings.
        """
        # Determine the log level: users can optionally pass in custom strings ("debug")
        msgLevel = msgType if isinstance(msgType, int) else LOG._logLevels[msgType][0]

        # Do the actual logging
        super(RunLogger, self).log(
            msgLevel, str(msg), extra={"single": single, "label": label}
        )

    def _log(self, *args, **kwargs):
        """wrapper around the standard library Logger._log() method
        The primary goal here is to allow us to support the deduplication of warnings.
        NOTE: All of the *args and **kwargs logic here are mandatory, as the standard library implementation of this
        method has been changing the number of kwargs between Python v3.4 and v3.9.
        """
        # we need 'extra' as an output keyword, even if empty
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        # make sure to populate the single/label data for de-duplication
        if "single" not in kwargs["extra"]:
            msg = args[1]
            single = kwargs.pop("single", False)
            label = kwargs.pop("label", None)
            label = msg if label is None else label

            kwargs["extra"]["single"] = single
            kwargs["extra"]["label"] = label

        super(RunLogger, self)._log(*args, **kwargs)

    def allowStopDuplicates(self):
        """helper method to allow us to safely add the deduplication filter at any time"""
        for f in self.filters:
            if isinstance(f, DeduplicationFilter):
                return
        self.addFilter(DeduplicationFilter())

    def write(self, msg, **kwargs):
        """the redirect method that allows to do stderr piping"""
        self.error(msg)

    def flush(self, *args, **kwargs):
        """stub, purely to allow stderr piping"""
        pass

    def close(self):
        """helper method, to shutdown and delete a Logger"""
        self.handlers.clear()
        del self

    def getDuplicatesFilter(self):
        """This object should have a no-duplicates filter. If it exists, find it."""
        for f in self.filters:
            if isinstance(f, DeduplicationFilter):
                return f

        return None

    def warningReport(self):
        """Summarize all warnings for the run."""
        self.info("----- Final Warning Count --------")
        self.info("  {0:^10s}   {1:^25s}".format("COUNT", "LABEL"))

        # grab the no-duplicates filter, and exit early if it doesn't exist
        dupsFilter = self.getDuplicatesFilter()
        if dupsFilter is None:
            self.info("  {0:^10s}   {1:^25s}".format(str(0), str("None Found")))
            self.info("------------------------------------")
            return

        # sort by labcollections.defaultdict(lambda: 1)
        for label, count in sorted(
            dupsFilter.singleWarningMessageCounts.items(), key=operator.itemgetter(1)
        ):
            self.info("  {0:^10s}   {1:^25s}".format(str(count), str(label)))
        self.info("------------------------------------")

    def setVerbosity(self, intLevel):
        """A helper method to try to partially support the local, historical method of the same name"""
        self.setLevel(intLevel)


# Setting the default logging class to be ours
logging.RunLogger = RunLogger
logging.setLoggerClass(RunLogger)


# ---------------------------------------


def logFactory():
    """Create the default logging object."""
    return _RunLog(int(context.MPI_RANK))


LOG = logFactory()
