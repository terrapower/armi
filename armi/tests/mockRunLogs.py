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
This module contains subclasses of the armi.runLog._RunLog class that can be used to determine
whether or not one of the specific methods were called. These should only be used in testing.
"""

import io
import sys
from logging import LogRecord

from armi import runLog


class BufferLog(runLog._RunLog):
    """Log which captures the output in attributes instead of emitting them.

    Used mostly in testing to ensure certain things get output, or to prevent any output from
    showing.
    """

    def __init__(self, *args, **kwargs):
        super(BufferLog, self).__init__(*args, **kwargs)
        self.originalLog = None
        self._outputStream = ""
        self._errStream = io.StringIO()
        self._deduplication = runLog.DeduplicationFilter()
        sys.stderr = self._errStream
        self.setVerbosity(0)

    def __enter__(self):
        self.originalLog = runLog.LOG
        runLog.LOG = self
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        runLog.LOG = self.originalLog

    def log(self, msgType, msg, single=False, label=None):
        """
        Add formatting to a message and handle its singleness, if applicable.

        This is a wrapper around logger.log() that does most of the work and is
        used by all message passers (e.g. info, warning, etc.).
        """
        # the message label is only used to determine unique for single-print warnings
        if label is None:
            label = msg

        # Skip writing the message if it is below the set verbosity
        msgVerbosity = self.logLevels[msgType][0]
        if msgVerbosity < self._verbosity:
            return

        # Skip writing the message if it is single-print warning
        record = LogRecord("BufferLog", msgVerbosity, "pathname", 1, msg, {}, ())
        record.label = label
        record.single = single
        if single and not self._deduplication.filter(record):
            return

        # Do the actual logging, but add that custom indenting first
        msg = self.logLevels[msgType][1] + str(msg) + "\n"
        self._outputStream += msg

    def clearSingleLogs(self):
        """Reset the single warned list so we get messages again."""
        self._deduplication.singleMessageCounts.clear()

    def getStdout(self):
        return self._outputStream

    def emptyStdout(self):
        self._outputStream = ""

    def getStderrValue(self):
        return self._errStream.getvalue()


class LogCounter(BufferLog):
    """This mock log is used to count the number of times a method was called.

    It can be used in testing to make sure a warning was issued, without checking the content of the message.
    """

    def __init__(self, *args, **kwargs):
        BufferLog.__init__(self)
        self.messageCounts = {msgType: 0 for msgType in self.logLevels.keys()}

    def log(self, msgType, *args, **kwargs):
        self.messageCounts[msgType] += 1
