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

r"""Basic tests of the localization functionality
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import unittest

import six

import armi
from armi.tests import mockRunLogs
from armi.localization import count_calls, _message_counts
from armi.localization import info, info_once, important
from armi.localization import warn, warn_once, warn_when_root, warn_once_when_root


class DummyClass:
    def __init__(self):
        if six.PY3:
            self.counts = [
                mm
                for mm, _ in _message_counts.items()
                if "function DummyClass.exampleCountedMessageForInstances" in repr(mm)
            ]
            self.warns = [
                mm
                for mm, _ in _message_counts.items()
                if "function DummyClass.exampleWarnOnceMessageForInstances" in repr(mm)
            ]
            self.warns = [
                mm
                for mm, _ in _message_counts.items()
                if "function DummyClass.exampleWarnOnceWhenRootMessageForInstances"
                in repr(mm)
            ]
        else:
            self.counts = [
                mm
                for mm, _ in _message_counts.items()
                if "function exampleCountedMessageForInstances" in repr(mm)
            ]
            self.warns = [
                mm
                for mm, _ in _message_counts.items()
                if "function exampleWarnOnceMessageForInstances" in repr(mm)
            ]
            self.warns = [
                mm
                for mm, _ in _message_counts.items()
                if "function exampleWarnOnceWhenRootMessageForInstances" in repr(mm)
            ]

    @count_calls
    def exampleCountedMessageForInstances(self):
        return "countedMessageForInstances".format()

    @warn_once
    def exampleWarnOnceMessageForInstances(self):
        return "exampleWarnOnceMessageForInstances".format()

    @warn_once_when_root
    def exampleWarnOnceWhenRootMessageForInstances(self):
        return "exampleWarnOnceWhenRootMessageForInstances".format()


class LocalizationTests(unittest.TestCase):
    @info
    def exampleInfoMessage(self):
        return "output message"

    def test_info_decorator(self):
        with mockRunLogs.BufferLog() as mock:
            self.assertEqual("", mock._outputStream)
            for ii in range(1, 3):
                self.exampleInfoMessage()
                self.assertEqual("[info] output message\n" * ii, mock._outputStream)

    @info_once
    def exampleInfoOnceMessage(self):
        return "example single message"

    def test_single_message_only_prints_once(self):
        with mockRunLogs.BufferLog() as mock:
            self.assertEqual("", mock._outputStream)
            for _ in range(1, 3):
                self.exampleInfoOnceMessage()
                self.assertEqual("[info] example single message\n", mock._outputStream)

    @info_once
    def exampleOutputOnceMessageWithExtraArgs(self, hi, my, name=None, isJerry=False):
        return "{} {} {} {}".format(hi, my, name, isJerry)

    def test_single_message_with_args_prints_correctly(self):
        with mockRunLogs.BufferLog() as mock:
            self.assertEqual("", mock._outputStream)
            for _ in range(1, 3):
                self.exampleOutputOnceMessageWithExtraArgs("yo", "dawg")
                self.assertEqual("[info] yo dawg None False\n", mock._outputStream)

    @important
    def exampleImportantMessage(self):
        return "important message?"

    def test_important_decorator(self):
        with mockRunLogs.BufferLog() as mock:
            self.assertEqual("", mock._outputStream)
            for ii in range(1, 3):
                self.exampleImportantMessage()
                self.assertEqual("[impt] important message?\n" * ii, mock._outputStream)

    @count_calls
    def exampleCountedMessage(self):
        return "countedMessage".format()

    def test_message_counts_correctly(self):
        if six.PY3:
            keys = [
                mm
                for mm, cc in _message_counts.items()
                if "function LocalizationTests.exampleCountedMessage " in repr(mm)
            ]
        else:
            keys = [
                mm
                for mm, cc in _message_counts.items()
                if "function exampleCountedMessage " in repr(mm)
            ]

        self.assertEqual(1, len(keys))
        key = keys[0]
        for ii in range(1, 4):
            self.exampleCountedMessage()
            self.assertEqual(ii, _message_counts[key])

    def test_message_counts_correctly_with_multiple_instances(self):
        for ii in range(0, 4):
            mt = DummyClass()
            self.assertEqual(1, len(mt.counts))
            key = mt.counts[0]
            for mc in range(1, 4):
                mt.exampleCountedMessageForInstances()
                self.assertEqual(mc + 3 * ii, _message_counts[key])

    @warn
    def exampleWarnMessage(self):
        return "you're not tall enough to ride this elephant".format()

    def test_warn_decorator(self):
        with mockRunLogs.BufferLog() as mock:
            for ii in range(1, 4):
                self.exampleWarnMessage()
                self.assertEqual(
                    "[warn] you're not tall enough to ride this elephant\n" * ii,
                    mock._outputStream,
                )

    @warn_once
    def exampleWarnOnceMessage(self):
        return "single warning".format()

    def test_warn_once_decorator(self):
        with mockRunLogs.BufferLog() as mock:
            for _ in range(1, 4):
                self.exampleWarnOnceMessage()
                self.assertEqual("[warn] single warning\n", mock._outputStream)

    def test_warn_once_decorator_with_multiple_instances(self):
        with mockRunLogs.BufferLog() as mock:
            for _ in range(1, 4):
                mt = DummyClass()
                for _ in range(1, 4):
                    mt.exampleWarnOnceMessageForInstances()
                    self.assertEqual(
                        "[warn] exampleWarnOnceMessageForInstances\n",
                        mock._outputStream,
                    )

    @warn_when_root
    def exampleWarnWhenRootMessage(self):
        return "warning from root".format()

    def test_warn_when_root_decorator(self):
        with mockRunLogs.BufferLog() as mock:
            for ii in range(1, 4):
                self.exampleWarnWhenRootMessage()
                msg = "[warn] warning from root\n" * ii
                self.assertEqual(msg, mock._outputStream)
                armi.MPI_RANK = 1
                self.exampleWarnWhenRootMessage()
                self.assertEqual(msg, mock._outputStream)
                armi.MPI_RANK = 0

    @warn_once_when_root
    def exampleWarnOnceWhenRootMessage(self):
        return "single warning for da root!".format()

    def test_warn_once_when_root_decorator(self):
        msg = "[warn] single warning for da root!\n"
        with mockRunLogs.BufferLog() as mock:
            for _ in range(1, 4):
                self.exampleWarnOnceWhenRootMessage()
                self.assertEqual(msg, mock._outputStream)
                armi.MPI_RANK = 1
                self.exampleWarnOnceWhenRootMessage()
                self.assertEqual(msg, mock._outputStream)
                armi.MPI_RANK = 0

    def test_warn_once_when_root_decorator_with_multiple_instances(self):
        msg = "[warn] exampleWarnOnceWhenRootMessageForInstances\n"
        with mockRunLogs.BufferLog() as mock:
            for _ in range(1, 4):
                mt = DummyClass()
                for _ in range(1, 4):
                    mt.exampleWarnOnceWhenRootMessageForInstances()
                    self.assertEqual(msg, mock._outputStream)
                    armi.MPI_RANK = 1
                    self.exampleWarnOnceWhenRootMessage()
                    self.assertEqual(msg, mock._outputStream)
                    armi.MPI_RANK = 0


if __name__ == "__main__":
    unittest.main()
