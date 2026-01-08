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
This module handles logging of console during a simulation.

The default way of calling and the global armi logger is to just import it:

.. code::

    from armi import runLog

You may want a logger specific to a single module, say to provide debug logging for only one module.
That functionality is provided by a global override of logging imports:

.. code::

    import logging
    runLog = logging.getLogger(__name__)

In either case, you can then log things the same way:

.. code::

    runLog.info('information here')
    runLog.error('extra error info here')
    raise SomeException  # runLog.error() implies that the code will crash!

Or change the log level the same way:

.. code::

    runLog.setVerbosity('debug')
"""

import collections
import logging
import operator
import os
import sys
import time
from glob import glob

from armi import context

# global constants
_ADD_LOG_METHOD_STR = """def {0}(self, message, *args, **kws):
    if self.isEnabledFor({1}):
        self._log({1}, message, args, **kws)
logging.Logger.{0} = {0}"""
OS_SECONDS_TIMEOUT = 2 * 60
SEP = "|"
STDERR_LOGGER_NAME = "ARMI_ERROR"
STDOUT_LOGGER_NAME = "ARMI"


class _RunLog:
    """
    Handles all the logging.

    For the parent process, things are allowed to print to stdout and stderr,
    but the stdout prints are formatted like log statements.
    For the child processes, everything is piped to log files.
    """

    STDERR_NAME = "{0}.{1:04d}.stderr"
    STDOUT_NAME = "{0}.{1:04d}.stdout"

    def __init__(self, mpiRank=0):
        """
        Build a log object.

        Parameters
        ----------
        mpiRank : int
            If this is zero, we are in the parent process, otherwise child process. This should not
            be adjusted after instantiation.
        """
        self._mpiRank = mpiRank
        self._verbosity = logging.INFO
        self.initialErr = None
        self.logLevels = None
        self._logLevelNumbers = []
        self.logger = None
        self.stderrLogger = None

        self.setNullLoggers()
        self._setLogLevels()

    def setNullLoggers(self):
        """Helper method to set both of our loggers to Null handlers."""
        self.logger = NullLogger("NULL")
        self.stderrLogger = NullLogger("NULL2", isStderr=True)

    @staticmethod
    def getLogLevels(mpiRank):
        """Helper method to build an important data object this class needs.

        Parameters
        ----------
        mpiRank : int
            If this is zero, we are in the parent process, otherwise child process. This should not
            be adjusted after instantiation.
        """
        rank = "" if mpiRank == 0 else f"-{mpiRank:>03d}"

        # NOTE: using ordereddict so we can get right order of options in GUI
        return collections.OrderedDict(
            [
                ("debug", (logging.DEBUG, f"[dbug{rank}] ")),
                ("extra", (15, f"[xtra{rank}] ")),
                ("info", (logging.INFO, f"[info{rank}] ")),
                ("important", (25, f"[impt{rank}] ")),
                ("prompt", (27, f"[prmt{rank}] ")),
                ("warning", (logging.WARNING, f"[warn{rank}] ")),
                ("error", (logging.ERROR, f"[err {rank}] ")),
                ("header", (100, f"{rank}")),
            ]
        )

    @staticmethod
    def getWhiteSpace(mpiRank):
        """Helper method to build the white space used to left-adjust the log lines.

        Parameters
        ----------
        mpiRank : int
            If this is zero, we are in the parent process, otherwise child process. This should not
            be adjusted after instantiation.
        """
        logLevels = _RunLog.getLogLevels(mpiRank)
        return " " * len(max([ll[1] for ll in logLevels.values()]))

    def _setLogLevels(self):
        """Here we fill the logLevels dict with custom strings that depend on the MPI rank."""
        self.logLevels = self.getLogLevels(self._mpiRank)
        self._logLevelNumbers = sorted([ll[0] for ll in self.logLevels.values()])

        # modify the logging module strings for printing
        for longLogString, (logValue, shortLogString) in self.logLevels.items():
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

    def log(self, msgType, msg, single=False, label=None, **kwargs):
        """
        This is a wrapper around logger.log() that does most of the work and is used by all message
        passers (e.g. info, warning, etc.).

        In this situation, we do the mangling needed to get the log level to the correct number.
        And we do some custom string manipulation so we can handle de-duplicating warnings.
        """
        # Determine the log level: users can optionally pass in custom strings ("debug")
        msgLevel = msgType if isinstance(msgType, int) else self.logLevels[msgType][0]

        # If this is a special "don't duplicate me" string, we need to add that info to the msg temporarily
        msg = str(msg)

        # Do the actual logging
        self.logger.log(msgLevel, msg, single=single, label=label)

    def getDuplicatesFilter(self):
        """If it exists, find the top-level ARMI logger 'should have a no duplicates' filter."""
        if not self.logger or not isinstance(self.logger, logging.Logger):
            return None

        return self.logger.getDuplicatesFilter()

    def clearSingleLogs(self):
        """Reset the list of de-duplicated warnings, so users can see those warnings again."""
        dupsFilter = self.getDuplicatesFilter()
        if dupsFilter:
            dupsFilter.singleMessageLabels.clear()

    def warningReport(self):
        """Summarize all warnings for the run."""
        self.logger.warningReport()

    def getLogVerbosityRank(self, level):
        """Return integer verbosity rank given the string verbosity name."""
        try:
            return self.logLevels[level][0]
        except KeyError:
            log_strs = list(self.logLevels.keys())
            raise KeyError(f"{level} is not a valid verbosity level: {log_strs}")

    def setVerbosity(self, level):
        """
        Sets the minimum output verbosity for the logger.

        Any message with a higher verbosity than this will be emitted.

        Parameters
        ----------
        level : int or str
            The level to set the log output verbosity to.
            Valid numbers are 0-50 and valid strings are keys of logLevels

        Examples
        --------
        >>> setVerbosity('debug') -> sets to 0
        >>> setVerbosity(0) -> sets to 0

        """
        # first, we have to get a valid integer from the input level
        if isinstance(level, str):
            self._verbosity = self.getLogVerbosityRank(level)
        elif isinstance(level, int):
            # The logging module does strange things if you set the log level to something other
            # than DEBUG, INFO, etc. So, if someone tries, we HAVE to set the log level at a
            # canonical value. Otherwise, nearly all log statements will be silently dropped.
            if level in self._logLevelNumbers:
                self._verbosity = level
            elif level < self._logLevelNumbers[0]:
                self._verbosity = self._logLevelNumbers[0]
            else:
                for i in range(len(self._logLevelNumbers) - 1, -1, -1):
                    if level >= self._logLevelNumbers[i]:
                        self._verbosity = self._logLevelNumbers[i]
                        break
        else:
            raise TypeError(f"Invalid verbosity rank {level}.")

        # Finally, set the log level
        if self.logger is not None:
            for handler in self.logger.handlers:
                handler.setLevel(self._verbosity)
            self.logger.setLevel(self._verbosity)

    def getVerbosity(self):
        """Return the global runLog verbosity."""
        return self._verbosity

    def restoreStandardStreams(self):
        """Set the system stderr back to its default (as it was when the run started)."""
        if self.initialErr is not None and self._mpiRank > 0:
            sys.stderr = self.initialErr

    def startLog(self, name):
        """Initialize the streams when parallel processing."""
        # open the main logger
        self.logger = logging.getLogger(STDOUT_LOGGER_NAME + SEP + name + SEP + str(self._mpiRank))

        # if there was a pre-existing _verbosity, use it now
        if self._verbosity != logging.INFO:
            self.setVerbosity(self._verbosity)

        if self._mpiRank != 0:
            # init stderr intercepting logging
            filePath = os.path.join(getLogDir(), _RunLog.STDERR_NAME.format(name, self._mpiRank))
            self.stderrLogger = logging.getLogger(STDERR_LOGGER_NAME)
            h = logging.FileHandler(filePath, delay=True)
            fmt = "%(message)s"
            form = logging.Formatter(fmt)
            h.setFormatter(form)
            h.setLevel(logging.WARNING)
            self.stderrLogger.handlers = [h]
            self.stderrLogger.setLevel(logging.WARNING)

            # force the error logger onto stderr
            self.initialErr = sys.stderr
            sys.stderr = self.stderrLogger


def getLogDir():
    """This returns a file path for the `logs` directory, first checking if the user set the ARMI_TEMP_ROOT_PATH
    environment variable.
    """
    if os.environ.get("ARMI_TEMP_ROOT_PATH"):
        return os.path.join(os.environ["ARMI_TEMP_ROOT_PATH"], "logs")
    else:
        return os.path.join(os.getcwd(), "logs")


def close(mpiRank=None):
    """End use of the log. Concatenate if needed and restore defaults."""
    mpiRank = context.MPI_RANK if mpiRank is None else mpiRank

    if mpiRank == 0:
        try:
            concatenateLogs()
        except IOError as ee:
            warning("Failed to concatenate logs due to IOError.")
            error(ee)
    else:
        if LOG.stderrLogger:
            _ = [h.close() for h in LOG.stderrLogger.handlers]
        if LOG.logger:
            _ = [h.close() for h in LOG.logger.handlers]

    LOG.setNullLoggers()
    LOG.restoreStandardStreams()


def concatenateLogs(logDir=None):
    """
    Concatenate the armi run logs and delete them.

    Should only ever be called by parent.

    .. impl:: Log files from different processes are combined.
        :id: I_ARMI_LOG_MPI
        :implements: R_ARMI_LOG_MPI

        The log files are plain text files. Since ARMI is frequently run in parallel, the situation
        arises where each ARMI process generates its own plain text log file. This function combines
        the separate log files, per process, into one log file.

        The files are written in numerical order, with the lead process stdout first then the lead
        process stderr. Then each other process is written to the combined file, in order, stdout
        then stderr. Finally, the original stdout and stderr files are deleted.
    """
    if logDir is None:
        logDir = getLogDir()

    # find all the logging-module-based log files
    stdoutFiles = sorted(glob(os.path.join(logDir, "*.stdout")))
    if not len(stdoutFiles):
        info("No log files found to concatenate.")
        return

    info(f"Concatenating {len(stdoutFiles)} log files")

    # default worker log name if none is found
    caseTitle = "armi-workers"
    for stdoutPath in stdoutFiles:
        stdoutFile = os.path.normpath(stdoutPath).split(os.sep)[-1]
        prefix = STDOUT_LOGGER_NAME + "."
        if stdoutFile[0 : len(prefix)] == prefix:
            candidate = stdoutFile.split(".")[-3]
            if len(candidate) > 0:
                caseTitle = candidate
                break

    combinedLogName = os.path.join(logDir, f"{caseTitle}-mpi.log")
    with open(combinedLogName, "w") as workerLog:
        workerLog.write("\n{0} CONCATENATED WORKER LOG FILES {1}\n".format("-" * 10, "-" * 10))

        for stdoutName in stdoutFiles:
            # NOTE: If the log file name format changes, this will need to change.
            rank = int(stdoutName.split(".")[-2])
            with open(stdoutName, "r") as logFile:
                data = logFile.read()
                # only write if there's something to write
                if data:
                    rankId = "\n{0} RANK {1:03d} STDOUT {2}\n".format("-" * 10, rank, "-" * 60)
                    if rank == 0:
                        print(rankId, file=sys.stdout)
                        print(data, file=sys.stdout)
                    else:
                        workerLog.write(rankId)
                        workerLog.write(data)
            try:
                os.remove(stdoutName)
            except OSError:
                warning(f"Could not delete {stdoutName}")

            # then print the stderr messages for that child process
            stderrName = stdoutName[:-3] + "err"
            if os.path.exists(stderrName):
                with open(stderrName) as logFile:
                    data = logFile.read()
                    if data:
                        # only write if there's something to write.
                        rankId = "\n{0} RANK {1:03d} STDERR {2}\n".format("-" * 10, rank, "-" * 60)
                        print(rankId, file=sys.stderr)
                        print(data, file=sys.stderr)
                try:
                    os.remove(stderrName)
                except OSError:
                    warning(f"Could not delete {stderrName}")


# Here are all the module-level functions that should be used for most outputs. They use the Log
# object behind the scenes.
def raw(msg):
    """Print raw text without any special functionality."""
    LOG.log("header", msg, single=False)


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


class DeduplicationFilter(logging.Filter):
    """
    Important logging filter.

    * allow users to turn off duplicate warnings
    * handles special indentation rules for our logs
    """

    def __init__(self, *args, **kwargs):
        logging.Filter.__init__(self, *args, **kwargs)
        self.singleMessageLabels = set()
        self.warningCounts = {}

    def filter(self, record):
        # determine if this is a "do not duplicate" message
        msg = str(record.msg)
        single = getattr(record, "single", False)

        # grab the label if it exist, otherwise use the message itself as the label
        label = getattr(record, "label", msg)
        label = msg if label is None else label

        # Track all warnings, for warning report
        if record.levelno in (logging.WARNING, logging.CRITICAL):
            if label not in self.warningCounts:
                self.warningCounts[label] = 1
            else:
                self.warningCounts[label] += 1
                if single:
                    return False

        # If the message is set to "do not duplicate" we may filter it out
        if single:
            # in sub-warning cases, hash the label, for faster lookup
            label = hash(label)
            if label not in self.singleMessageLabels:
                self.singleMessageLabels.add(label)
            else:
                return False

        # Handle some special string-mangling we want to do, for multi-line messages
        whiteSpace = _RunLog.getWhiteSpace(context.MPI_RANK)
        record.msg = msg.rstrip().replace("\n", "\n" + whiteSpace)
        return True


class RunLogger(logging.Logger):
    """Custom Logger to support our specific desires.

    1. Giving users the option to de-duplicate warnings
    2. Piping stderr to a log file

    .. impl:: A simulation-wide log, with user-specified verbosity.
        :id: I_ARMI_LOG
        :implements: R_ARMI_LOG

        Log statements are any text a user wants to record during a run. For instance, basic
        notifications of what is happening in the run, simple warnings, or hard errors. Every log
        message has an associated log level, controlled by the "verbosity" of the logging statement
        in the code. In the ARMI codebase, you can see many examples of logging:

        .. code-block:: python

            runLog.error("This sort of error might usually terminate the run.")
            runLog.warning("Users probably want to know.")
            runLog.info("This is the usual verbosity.")
            runLog.debug("This is only logged during a debug run.")

        The full list of logging levels is defined in ``_RunLog.getLogLevels()``, and the developer
        specifies the verbosity of a run via ``_RunLog.setVerbosity()``.

        At the end of the ARMI-based simulation, the analyst will have a full record of potentially
        interesting information they can use to understand their run.

    .. impl:: Logging is done to the screen and to file.
        :id: I_ARMI_LOG_IO
        :implements: R_ARMI_LOG_IO

        This logger makes it easy for users to add log statements to and ARMI application, and ARMI
        will control the flow of those log statements. In particular, ARMI overrides the normal
        Python logging tooling, to allow developers to pipe their log statements to both screen and
        file. This works for stdout and stderr.

        At any place in the ARMI application, developers can interject a plain text logging message,
        and when that code is hit during an ARMI simulation, the text will be piped to screen and a
        log file. By default, the ``logging`` module only logs to screen, but ARMI adds a
        ``FileHandler`` in the ``RunLog`` constructor and in ``_RunLog.startLog``.
    """

    FMT = "%(levelname)s%(message)s"

    def __init__(self, *args, **kwargs):
        # optionally, the user can pass in the MPI_RANK by putting it in the logger name after a separator string
        # args[0].split(SEP): 0 = "ARMI", 1 = caseTitle, 2 = MPI_RANK
        if SEP in args[0]:
            mpiRank = int(args[0].split(SEP)[-1].strip())
            args = (".".join(args[0].split(SEP)[0:2]),)
        else:
            mpiRank = context.MPI_RANK

        logging.Logger.__init__(self, *args, **kwargs)
        self.allowStopDuplicates()

        if mpiRank == 0:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)
            self.setLevel(logging.INFO)
        else:
            filePath = os.path.join(getLogDir(), _RunLog.STDOUT_NAME.format(args[0], mpiRank))
            handler = logging.FileHandler(filePath, delay=True)
            handler.setLevel(logging.WARNING)
            self.setLevel(logging.WARNING)

        form = logging.Formatter(RunLogger.FMT)
        handler.setFormatter(form)
        self.addHandler(handler)

    def log(self, msgType, msg, single=False, label=None, *args, **kwargs):
        """
        This is a wrapper around logger.log() that does most of the work.

        This is used by all message passers (e.g. info, warning, etc.). In this situation, we do the
        mangling needed to get the log level to the correct number. And we do some custom string
        manipulation so we can handle de-duplicating warnings.
        """
        # Determine the log level: users can optionally pass in custom strings ("debug")
        msgLevel = msgType if isinstance(msgType, int) else LOG.logLevels[msgType][0]

        # Do the actual logging
        logging.Logger.log(self, msgLevel, str(msg), extra={"single": single, "label": label})

    def _log(self, *args, **kwargs):
        """
        Wrapper around the standard library Logger._log() method.

        The primary goal here is to allow us to support the deduplication of warnings.

        Notes
        -----
        All of the ``*args`` and ``**kwargs`` logic here are mandatory, as the standard library
        implementation of this method changed the number of kwargs between Python v3.4 and v3.9.
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

        logging.Logger._log(self, *args, **kwargs)

    def allowStopDuplicates(self):
        """Helper method to allow us to safely add the deduplication filter at any time."""
        for f in self.filters:
            if isinstance(f, DeduplicationFilter):
                return
        self.addFilter(DeduplicationFilter())

    def write(self, msg, **kwargs):
        """The redirect method that allows to do stderr piping."""
        self.error(msg)

    def flush(self, *args, **kwargs):
        """Stub, purely to allow stderr piping."""
        pass

    def close(self):
        """Helper method, to shutdown and delete a Logger."""
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
        total = 0
        for label, count in sorted(dupsFilter.warningCounts.items(), key=operator.itemgetter(1), reverse=True):
            self.info(f"  {str(count):^10s}   {str(label):^25s}")
            total += count
        self.info("------------------------------------")

        # add a totals line
        self.info(f"  {str(total):^10s}   Total Number of Warnings")
        self.info("------------------------------------")

    def setVerbosity(self, intLevel):
        """A helper method to try to partially support the local, historical method of the same name."""
        self.setLevel(intLevel)


class NullLogger(RunLogger):
    """This is really just a placeholder for logging before or after the span of a normal armi run.

    It will forward all logging to stdout/stderr, as you'd normally expect.
    But it will preserve the formatting and duplication tools of the armi library.
    """

    def __init__(self, name, isStderr=False):
        RunLogger.__init__(self, name)
        if isStderr:
            self.handlers = [logging.StreamHandler(sys.stderr)]
        else:
            self.handlers = [logging.StreamHandler(sys.stdout)]

    def addHandler(self, *args, **kwargs):
        """Ensure this STAYS a null logger."""
        pass


# Setting the default logging class to be ours
logging.RunLogger = RunLogger
logging.setLoggerClass(RunLogger)


def createLogDir(logDir: str = None) -> None:
    """A helper method to create the log directory."""
    # the usual case is the user does not pass in a log dir path, so we use the global one
    if logDir is None:
        logDir = getLogDir()

    # create the directory
    if not os.path.exists(logDir):
        try:
            os.makedirs(logDir)
        except FileExistsError:
            # If we hit this race condition, we still win.
            return

    # potentially, wait for directory to be created
    secondsWait = 0.5
    loopCounter = 0
    while not os.path.exists(logDir):
        loopCounter += 1
        if loopCounter > (OS_SECONDS_TIMEOUT / secondsWait):
            raise OSError(f"Was unable to create the log directory: {logDir}")

        time.sleep(secondsWait)


if not os.path.exists(getLogDir()):
    createLogDir(getLogDir())


def logFactory():
    """Create the default logging object."""
    return _RunLog(int(context.MPI_RANK))


LOG = logFactory()
