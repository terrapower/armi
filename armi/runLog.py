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

.. note::
    We plan to reimplement this with the standard Python logging module. It was customized
    to add a few features in a HPC/MPI environment but we now think we can use the standard
    system.

"""
from __future__ import print_function
import sys
import os
import collections
import operator
import time

from six import StringIO

from armi import context
from armi.context import Mode
from armi import meta


# use ordereddict so we can get right order of options in GUI.
_logLevels = collections.OrderedDict(
    [
        ("debug", (0, "dbug")),
        ("extra", (10, "xtra")),
        ("info", (20, "info")),
        ("important", (25, "impt")),
        ("prompt", (27, "prmt")),
        ("warning", (30, "warn")),
        ("error", (50, "err ")),
        ("header", (100, "")),
    ]
)

_stderrName = "{0}.{1:04d}.stderr"
_stdoutName = "{0}.{1:04d}.stdout"


def getLogVerbosityLevels():
    """Return a list of the available log levels (e.g., debug, extra, etc.)."""
    return list(_logLevels.keys())


def getLogVerbosityRank(level):
    """Return integer verbosity rank given the string verbosity name."""
    if level not in getLogVerbosityLevels():
        raise KeyError(
            "{} is not a valid verbosity level. Choose from {}".format(
                level, getLogVerbosityLevels()
            )
        )
    return _logLevels[level][0]


def _checkLogVerbsityRank(rank):
    """Check that the verbosity rank is defined within the _logLevels and return it if it is."""
    validRanks = []
    for level in getLogVerbosityLevels():
        expectedRank = getLogVerbosityRank(level)
        validRanks.append(rank)
        if rank == expectedRank:
            return rank
    raise KeyError(
        "Invalid verbosity rank {}. Valid options are: {}".format(rank, validRanks)
    )


class Log:
    """
    Abstract class that ARMI code calls to be rendered to some kind of log.
    """

    def __init__(self, verbosity=50):  # pylint: disable=unused-argument
        """
        Build a log object

        Parameters
        ----------
        verbosity : int
            if a msg verbosity is > this, it will be  emitted.
            The default of 50 means only error messages will be emitted.
            This usually gets adjusted by user settings quickly after instantiation.

        """
        self._verbosity = verbosity
        self._singleMessageCounts = collections.defaultdict(lambda: 0)
        self._singleWarningMessageCounts = collections.defaultdict(lambda: 0)
        self._outputStream = None
        self._errStream = None
        # https://docs.python.org/2/library/sys.html says
        # to explicitly save these instead of relying upon __stdout__, etc.
        if context.MPI_RANK == 0:
            self.initialOut = sys.stdout
            self.initialErr = sys.stderr
        else:
            # Attach output streams to a null device until we open log files. We don't know what to
            # call them until we have processed some of the settings, and any errors encountered in
            # that should be encountered on the master process anyway.
            self.initialOut = open(os.devnull, "w")
            self.initialErr = open(os.devnull, "w")
        self.setStreams(self.initialOut, self.initialErr)
        self.name = "log"

    def _emit(self, msg):
        """
        send the raw message to the stream that you want it to go to.
        """
        raise NotImplementedError

    def flush(self):
        self._errStream.flush()
        self._outputStream.flush()

    def standardLogMsg(self, msgType, msg, single=False, label=None):
        """
        Add formatting to a message and handle its singleness, if applicable.

        This is a wrapper around _emit that does most of the work and is
        used by all message passers (e.g. info, warning, etc.).

        The MPI_RANK printout was removed because it's obvious in the stdout now.
        """
        if label is None:
            label = msg

        msgVerbosity, msgLabel = _logLevels[msgType]
        # Skip writing the message if it is below the set verbosity
        if msgVerbosity < self._verbosity:
            return

        if single:
            if self._msgHasAlreadyBeenEmitted(label, msgType):
                return

        # Set up the prefix for the line (e.g. [info], [info-001])
        if context.MPI_RANK == 0:
            prefixAdder = ""
        else:
            prefixAdder = "-{:>03d}".format(context.MPI_RANK)

        linePrefix = "[" + msgLabel + prefixAdder + "] " if msgLabel else msgLabel
        linePrefixSpacing = len(linePrefix) * " "

        # Write lines to the stream
        lines = str(msg).split("\n")
        for i, line in enumerate(lines):
            prefix = linePrefix if i == 0 else linePrefixSpacing
            self._emit("{}{}".format(prefix, line))

    def _msgHasAlreadyBeenEmitted(self, label, msgType=""):
        """Return True if the count of the label is greater than 1."""
        if msgType == "warning" or msgType == "critical":
            self._singleWarningMessageCounts[label] += 1
            if (
                self._singleWarningMessageCounts[label] > 1
            ):  # short circuit because error has changed
                return True
        else:
            self._singleMessageCounts[label] += 1
            if (
                self._singleMessageCounts[label] > 1
            ):  # short circuit because error has changed
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
            info("  {0:10d}   {1:<25s}".format(count, str(label)))
        info("------------------------------------")

    def setVerbosity(self, levelInput):
        """
        Sets the minimum output verbosity for the logger.

        Any message with a higher verbosity than this will
        be emitted.

        Parameters
        ----------
        levelInput : int or str
            The level to set the log output verbosity to.
            Valid numbers are 0-50 and valid strings are keys of _logLevels

        Examples
        --------
        >>> setVerbosity('debug') -> sets to 0
        >>> setVerbosity(0) -> sets to 0

        """
        self._verbosity = (
            getLogVerbosityRank(levelInput)
            if isinstance(levelInput, str)
            else _checkLogVerbsityRank(levelInput)
        )

    def getVerbosity(self):
        """Return the global runLog verbosity."""
        return self._verbosity

    def setStreams(self, stdout, stderr):
        """Set the stdout and stderr streams to any stream object."""
        sys.stdout = self._outputStream = stdout
        sys.stderr = self._errStream = stderr

    def _getStreams(self):
        return self._outputStream, self._errStream

    def _restoreStandardStreams(self):
        """Set the system stdout/stderr to their defaults (as they were when the run started)."""
        if sys.stdout == self._outputStream:
            sys.stdout = self.initialOut  # sys.__stdout__
            sys.stderr = self.initialErr  # sys.__stderr__


class PrintLog(Log):
    """Log that emits to stdout/stderr or file-based streams (for MPI workers) with print."""

    def startLog(self, name):
        """Initialize the streams when parallel processing"""
        if context.MPI_SIZE == 1:
            return
        if context.MPI_RANK == 0:
            self.name = name
            if not os.path.exists("logs"):
                os.makedirs("logs")
            # stall until it shows up in file system (SMB caching issue?)
            while not os.path.exists("logs"):
                time.sleep(0.5)

        context.MPI_COMM.barrier()

        if context.MPI_RANK > 0:
            self.name = os.path.join("logs", name)
            outputStream = open(_stdoutName.format(self.name, context.MPI_RANK), "w")
            errStream = open(_stderrName.format(self.name, context.MPI_RANK), "w")
            self.setStreams(outputStream, errStream)

    def close(self):
        """End use of the log. Concatenate if needed and restore defaults"""
        if context.MPI_RANK == 0 and context.MPI_SIZE > 1:
            try:
                self.concatenateLogs()
            except IOError as ee:
                warning("Failed to concatenate logs due to IOError.")
                error(ee)
        elif context.MPI_RANK > 0 and context.MPI_SIZE > 1:
            for fileObj in [self._outputStream, self._errStream]:
                fileObj.flush()
                fileObj.close()
        self._restoreStandardStreams()

    def _emit(self, msg):
        print(msg)

    def concatenateLogs(self):
        """
        Concatenate the armi run logs and delete them.

        Should only ever be called by master.
        """
        info("Concatenating {0} standard streams".format(context.MPI_SIZE))
        for rank in range(context.MPI_SIZE):
            if not rank:
                # skip log 0
                continue
            stdoutName = os.path.join("logs", _stdoutName.format(self.name, rank))
            stderrName = os.path.join("logs", _stderrName.format(self.name, rank))

            for streamName, stream, logName in zip(
                ["STDOUT", "STDERR"],
                [self._outputStream, self._errStream],
                [stdoutName, stderrName],
            ):
                with open(logName) as logFile:
                    data = logFile.read()
                if data:
                    # only write if there's something to write.
                    rankId = "\n{0} RANK {1:03d} {2} {3}\n".format(
                        "-" * 10, rank, streamName, "-" * 60
                    )
                    stream.write(rankId)
                    stream.write(data)
                try:
                    os.remove(logName)
                except OSError:
                    warning("Could not delete {0}".format(logName))


class PrintLogCombined(PrintLog):
    """
    Print log that doesn't break up into files
    """

    def startLog(self, name):
        pass

    def close(self):
        pass

    def concatenateLogs(self):
        pass


# Here are all the module-level functions that should be used for most outputs.
# They use the PrintLog object behind the scenes.
def raw(msg):
    """
    Print raw text without any special functionality.
    """
    LOG._emit(msg)  #  pylint: disable=protected-access


def extra(msg, single=False, label=None):
    LOG.standardLogMsg("extra", msg, single=single, label=label)


def debug(msg, single=False, label=None):
    LOG.standardLogMsg("debug", msg, single=single, label=label)


def info(msg, single=False, label=None):
    LOG.standardLogMsg("info", msg, single=single, label=label)


def important(msg, single=False, label=None):
    LOG.standardLogMsg("important", msg, single=single, label=label)


def warning(msg, single=False, label=None):
    LOG.standardLogMsg("warning", msg, single=single, label=label)


def error(msg, single=False, label=None):
    LOG.standardLogMsg("error", msg, single=single, label=label)


def header(msg, single=False, label=None):
    LOG.standardLogMsg("header", msg, single=single, label=label)


def flush():
    """Flush LOG's output in the err and output streams"""
    LOG.flush()


def prompt(statement, question, *options):
    """ "Prompt the user for some information."""
    from armi.localization import exceptions

    if context.CURRENT_MODE == Mode.GUI:
        # avoid hard dependency on wx
        import wx  # pylint: disable=import-error

        msg = statement + "\n\n\n" + question
        if len(msg) < 300:
            style = wx.CENTER
            for opt in options:
                style |= getattr(wx, opt)
            dlg = wx.MessageDialog(None, msg, style=style)
        else:
            # for shame. Might make sense to move the styles stuff back into the
            # Framework
            from tparmi.gui.styles import dialogues

            dlg = dialogues.ScrolledMessageDialog(None, msg, "Prompt")
        response = dlg.ShowModal()
        dlg.Destroy()
        if response == wx.ID_CANCEL:
            raise exceptions.RunLogPromptCancel("Manual cancellation of GUI prompt")
        return response in [wx.ID_OK, wx.ID_YES]

    elif context.CURRENT_MODE == Mode.INTERACTIVE:
        response = ""
        responses = [
            opt for opt in options if opt in ["YES_NO", "YES", "NO", "CANCEL", "OK"]
        ]

        if "YES_NO" in responses:
            index = responses.index("YES_NO")
            responses[index] = "NO"
            responses.insert(index, "YES")

        if not any(responses):
            raise RuntimeError("No suitable responses in {}".format(responses))

        # highly requested shorthand responses
        if "YES" in responses:
            responses.append("Y")
        if "NO" in responses:
            responses.append("N")

        while response not in responses:
            LOG.standardLogMsg("prompt", statement)
            LOG.standardLogMsg(
                "prompt", "{} ({}): ".format(question, ", ".join(responses))
            )
            response = sys.stdin.readline().strip().upper()

        if response == "CANCEL":
            raise exceptions.RunLogPromptCancel(
                "Manual cancellation of interactive prompt"
            )

        return response in ["YES", "Y", "OK"]

    else:
        raise exceptions.RunLogPromptUnresolvable(
            "Incorrect CURRENT_MODE for prompting user: {}".format(context.CURRENT_MODE)
        )


def warningReport():
    LOG.warningReport()


def setVerbosity(level):
    # convenience function
    LOG.setVerbosity(level)


def getVerbosity():
    return LOG.getVerbosity()


# ---------------------------------------


def logFactory():
    """Create the default logging object."""
    if context.MPI_RANK == 0:
        verbosity = _logLevels["info"][0]
    else:
        verbosity = _logLevels["warning"][0]
    return PrintLog(verbosity)


LOG = logFactory()

# Copyright 2009-2019 TerraPower, LLC
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
