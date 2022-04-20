# Copyright 2021 TerraPower, LLC
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

"""Tests for the compareDB3 module"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import unittest

from armi.bookkeeping.db.compareDB3 import DiffResults, OutputWriter
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestCompareDB3(unittest.TestCase):
    """Tests for the compareDB3 module"""

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_outputWriter(self):
        fileName = "test_outputWriter.txt"
        with OutputWriter(fileName) as out:
            out.writeln("Rubber Baby Buggy Bumpers")

        txt = open(fileName, "r").read()
        self.assertIn("Rubber", txt)

    def test_diffResultsBasic(self):
        # init an instance of the class
        dr = DiffResults(0.01)
        self.assertEqual(len(dr._columns), 0)
        self.assertEqual(len(dr._structureDiffs), 0)
        self.assertEqual(len(dr.diffs), 0)

        # simple test of addDiff
        dr.addDiff("thing", "what", 123.4, 122.2345, 555)
        self.assertEqual(len(dr._columns), 0)
        self.assertEqual(len(dr._structureDiffs), 0)
        self.assertEqual(len(dr.diffs), 3)
        self.assertEqual(dr.diffs["thing/what mean(abs(diff))"][0], 123.4)
        self.assertEqual(dr.diffs["thing/what mean(diff)"][0], 122.2345)
        self.assertEqual(dr.diffs["thing/what max(abs(diff))"][0], 555)

        # simple test of addTimeStep
        dr.addTimeStep("timeStep")
        self.assertEqual(dr._structureDiffs[0], 0)
        self.assertEqual(dr._columns[0], "timeStep")

        # simple test of addStructureDiffs
        dr.addStructureDiffs(7)
        self.assertEqual(len(dr._structureDiffs), 1)
        self.assertEqual(dr._structureDiffs[0], 7)

        # simple test of _getDefault
        self.assertEqual(len(dr._getDefault()), 0)

        # simple test of nDiffs
        self.assertEqual(dr.nDiffs(), 10)


if __name__ == "__main__":
    unittest.main()
