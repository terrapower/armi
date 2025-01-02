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
"""Basic tests of the custom exceptions."""
import unittest

from armi.tests import mockRunLogs
from armi.utils.customExceptions import important, info, warn, warn_when_root


class CustomExceptionTests(unittest.TestCase):
    @info
    def exampleInfoMessage(self):
        return "output message"

    def test_info_decorator(self):
        with mockRunLogs.BufferLog() as mock:
            self.assertEqual("", mock.getStdout())
            for ii in range(1, 3):
                self.exampleInfoMessage()
                self.assertEqual("[info] output message\n" * ii, mock.getStdout())

    @important
    def exampleImportantMessage(self):
        return "important message?"

    def test_important_decorator(self):
        with mockRunLogs.BufferLog() as mock:
            self.assertEqual("", mock.getStdout())
            for ii in range(1, 3):
                self.exampleImportantMessage()
                self.assertEqual("[impt] important message?\n" * ii, mock.getStdout())

    @warn
    def exampleWarnMessage(self):
        return "you're not tall enough to ride this elephant".format()

    def test_warn_decorator(self):
        with mockRunLogs.BufferLog() as mock:
            for ii in range(1, 4):
                self.exampleWarnMessage()
                self.assertEqual(
                    "[warn] you're not tall enough to ride this elephant\n" * ii,
                    mock.getStdout(),
                )

    @warn_when_root
    def exampleWarnWhenRootMessage(self):
        return "warning from root".format()

    def test_warn_when_root_decorator(self):
        import armi

        with mockRunLogs.BufferLog() as mock:
            for ii in range(1, 4):
                self.exampleWarnWhenRootMessage()
                msg = "[warn] warning from root\n" * ii
                self.assertEqual(msg, mock.getStdout())
                armi.MPI_RANK = 1
                self.exampleWarnWhenRootMessage()
                self.assertEqual(msg, mock.getStdout())
                armi.MPI_RANK = 0
