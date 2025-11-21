# Copyright 2020 TerraPower, LLC
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
"""Tests for functions in textProcessors.py."""

import logging
import os
import pathlib
import unittest
from io import StringIO

import ruamel

from armi import runLog
from armi.testing import TESTING_ROOT
from armi.tests import mockRunLogs
from armi.utils import textProcessors
from armi.utils.directoryChangers import TemporaryDirectoryChanger

THIS_DIR = os.path.dirname(__file__)
RES_DIR = os.path.join(THIS_DIR, "resources")


class TestTextProcessor(unittest.TestCase):
    """Test Text processor."""

    def setUp(self):
        godivaSettings = os.path.join(TESTING_ROOT, "reactors", "godiva", "godiva.armi.unittest.yaml")
        self.tp = textProcessors.TextProcessor(godivaSettings)

    def test_fsearch(self):
        """Test fsearch in re mode."""
        line = self.tp.fsearch("nTasks")
        self.assertIn("36", line)
        self.assertEqual(self.tp.fsearch("nTasks"), "")

    def test_fsearchText(self):
        """Test fsearch in text mode."""
        line = self.tp.fsearch("nTasks", textFlag=True)
        self.assertIn("36", line)
        self.assertEqual(self.tp.fsearch("nTasks"), "")


class YamlIncludeTest(unittest.TestCase):
    def test_resolveIncludes(self):
        with open(os.path.join(RES_DIR, "root.yaml")) as f:
            resolved = textProcessors.resolveMarkupInclusions(f, root=pathlib.Path(RES_DIR))

        # Make sure that there aren't any !include tags left in the converted stream
        anyIncludes = False
        for l in resolved:
            if "!include" in l:
                anyIncludes = True
        self.assertFalse(anyIncludes)

        # Re-parse the resolved stream, make sure that we included the stuff that we want
        resolved.seek(0)
        data = ruamel.yaml.YAML().load(resolved)
        self.assertEqual(data["billy"]["children"][1]["full_name"], "Jennifer Person")
        self.assertEqual(data["billy"]["children"][1]["children"][0]["full_name"], "Elizabeth Person")

        # Check that we preserved other round-trip data
        resolved.seek(0)
        commentFound = False
        anchorFound = False
        for l in resolved:
            if l.strip() == "# some comment in includeA":
                commentFound = True
            if "*bobby" in l:
                anchorFound = True

        self.assertTrue(commentFound)
        self.assertTrue(anchorFound)

    def test_resolveIncludes_StringIO(self):
        """Tests that resolveMarkupInclusions handles StringIO input."""
        yaml = ruamel.yaml.YAML()
        with open(os.path.join(RES_DIR, "root.yaml")) as f:
            loadedYaml = yaml.load(f)
        stringIO = StringIO()
        yaml.dump(loadedYaml, stringIO)
        resolved = textProcessors.resolveMarkupInclusions(src=stringIO, root=pathlib.Path(RES_DIR))
        with open(os.path.join(RES_DIR, "root.yaml")) as f:
            expected = textProcessors.resolveMarkupInclusions(f, root=pathlib.Path(RES_DIR))
        # strip it because one method gives an extra newline we don't care about
        self.assertEqual(resolved.getvalue().strip(), expected.getvalue().strip())

    def test_findIncludes(self):
        includes = textProcessors.findYamlInclusions(pathlib.Path(RES_DIR) / "root.yaml")
        for i, _mark in includes:
            self.assertTrue((RES_DIR / i).exists())

        self.assertEqual(len(includes), 2)


class SequentialReaderTests(unittest.TestCase):
    textStream = """This is an example test stream.
This has multiple lines in it and below it contains a set of data that
can be found using a regular expression pattern.
FILE DATA
X  Y  3.5
X  Y  4.2
X  Y  0.0"""

    _DUMMY_FILE_NAME = "DUMMY.txt"

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

        with open(self._DUMMY_FILE_NAME, "w") as f:
            f.write(self.textStream)

    def tearDown(self):
        if os.path.exists(self._DUMMY_FILE_NAME):
            try:
                os.remove(self._DUMMY_FILE_NAME)
            except OSError:
                pass

        self.td.__exit__(None, None, None)

    def test_readFile(self):
        with textProcessors.SequentialReader(self._DUMMY_FILE_NAME) as sr:
            self.assertTrue(sr.searchForText("FILE DATA"))
            self.assertFalse(sr.searchForText("This text isn't here."))

    def test_readFileWithPattern(self):
        with textProcessors.SequentialReader(self._DUMMY_FILE_NAME) as sr:
            self.assertTrue(sr.searchForPattern(r"(X\s+Y\s+\d+\.\d+)"))
            self.assertEqual(float(sr.line.split()[2]), 3.5)

    def test_issueWarningOnFindingText(self):
        with textProcessors.SequentialReader(self._DUMMY_FILE_NAME) as sr:
            warningMsg = "Oh no"
            sr.issueWarningOnFindingText("example test stream", warningMsg)

            with mockRunLogs.BufferLog() as mock:
                runLog.LOG.startLog("test_issueWarningOnFindingText")
                runLog.LOG.setVerbosity(logging.WARNING)
                self.assertEqual("", mock.getStdout())
                self.assertTrue(sr.searchForPattern("example test stream"))
                self.assertIn(warningMsg, mock.getStdout())

                self.assertFalse(sr.searchForPattern("Killer Tomatoes"))

    def test_raiseErrorOnFindingText(self):
        with textProcessors.SequentialReader(self._DUMMY_FILE_NAME) as sr:
            sr.raiseErrorOnFindingText("example test stream", IOError)

            with self.assertRaises(IOError):
                self.assertTrue(sr.searchForPattern("example test stream"))

    def test_consumeLine(self):
        with textProcessors.SequentialReader(self._DUMMY_FILE_NAME) as sr:
            sr.line = "hi"
            sr.match = 1
            sr.consumeLine()
            self.assertEqual(len(sr.line), 0)
            self.assertIsNone(sr.match)
