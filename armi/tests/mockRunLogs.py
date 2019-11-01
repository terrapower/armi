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
This module contains subclasses of the armi.runLog.Log class that can be used to determine whether or not
one of the specific methods were called. These should only be used in testing.
"""

import six

from armi import runLog


class BufferLog(runLog.PrintLog):
    r"""Log which captures the output in attributes instead of emitting them

    Used mostly in testing to ensure certain things get output, or to prevent any output
    from showing.
    """

    def __init__(self, *args, **kwargs):
        runLog.PrintLog.__init__(self, *args, **kwargs)
        self.originalLog = None
        outputStream = six.StringIO()
        errStream = six.StringIO()
        self.setStreams(outputStream, errStream)
        self.setVerbosity(0)

    def __enter__(self):
        self.originalLog = runLog.LOG
        runLog.LOG = self
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        runLog.LOG = self.originalLog
        runLog.LOG.setStreams(runLog.LOG._outputStream, runLog.LOG._errStream)

    def getStdoutValue(self):
        return self._outputStream.getvalue()

    def getStderrValue(self):
        return self._errStream.getvalue()


class LogCounter(BufferLog):
    """This mock log is used to count the number of times a method was called.

    It can be used in testing to make sure a warning was issued, without checking the content of the message.
    """

    def __init__(self, *args, **kwargs):
        BufferLog.__init__(self)
        self.messageCounts = {msgType: 0 for msgType in runLog.getLogVerbosityLevels()}

    def standardLogMsg(self, msgType, *args, **kwargs):
        self.messageCounts[msgType] += 1
