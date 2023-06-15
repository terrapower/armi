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
"""
Tests for functions in textProcessors.py.
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import os
import pathlib
import unittest

import ruamel

from armi.utils import textProcessors

THIS_DIR = os.path.dirname(__file__)
RES_DIR = os.path.join(THIS_DIR, "resources")


class YamlIncludeTest(unittest.TestCase):
    def test_resolveIncludes(self):
        with open(os.path.join(RES_DIR, "root.yaml")) as f:
            resolved = textProcessors.resolveMarkupInclusions(
                f, root=pathlib.Path(RES_DIR)
            )

        # Make sure that there aren't any !include tags left in the converted stream
        anyIncludes = False
        for l in resolved:
            if "!include" in l:
                anyIncludes = True
        self.assertFalse(anyIncludes)

        # Re-parse the resolved stream, make sure that we included the stuff that we
        # want
        resolved.seek(0)
        data = ruamel.yaml.YAML().load(resolved)
        self.assertEqual(data["billy"]["children"][1]["full_name"], "Jennifer Person")
        self.assertEqual(
            data["billy"]["children"][1]["children"][0]["full_name"], "Elizabeth Person"
        )

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

    def test_findIncludes(self):
        includes = textProcessors.findYamlInclusions(
            pathlib.Path(RES_DIR) / "root.yaml"
        )
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

    @classmethod
    def setUpClass(cls):
        with open(cls._DUMMY_FILE_NAME, "w") as f:
            f.write(cls.textStream)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls._DUMMY_FILE_NAME):
            os.remove(cls._DUMMY_FILE_NAME)

    def test_readFile(self):
        with textProcessors.SequentialReader(self._DUMMY_FILE_NAME) as sr:
            self.assertTrue(sr.searchForText("FILE DATA"))
            self.assertFalse(sr.searchForText("This text isn't here."))

    def test_readFileWithPattern(self):
        with textProcessors.SequentialReader(self._DUMMY_FILE_NAME) as sr:
            self.assertTrue(sr.searchForPattern("(X\s+Y\s+\d+\.\d+)"))
            self.assertEqual(float(sr.line.split()[2]), 3.5)
