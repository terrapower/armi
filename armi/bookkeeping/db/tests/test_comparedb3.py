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

import h5py

from armi.bookkeeping.db import database3
from armi.bookkeeping.db.compareDB3 import compareDatabases, DiffResults, OutputWriter
from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT
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

    def test_compareDatabaseDuplicate(self):
        """end-to-end test of compareDatabases() on a photocopy database"""
        # build two super-simple H5 files for testing
        o, r = test_reactors.loadTestReactor(TEST_ROOT)

        dbi = database3.DatabaseInterface(r, o.cs)
        dbi.initDB(fName=self._testMethodName + ".h5")
        db = dbi.database

        dbi2 = database3.DatabaseInterface(r, o.cs)
        dbi2.initDB(fName=self._testMethodName + "2.h5")
        db2 = dbi2.database

        # validate file 1 exists, and force it to be readable again
        b = h5py.File(db._fullPath, "r")
        self.assertEqual(list(b.keys()), ["inputs"])
        self.assertEqual(
            sorted(b["inputs"].keys()), ["blueprints", "geomFile", "settings"]
        )
        b.close()

        # validate file 2 exists, and force it to be readable again
        b2 = h5py.File(db2._fullPath, "r")
        self.assertEqual(list(b2.keys()), ["inputs"])
        self.assertEqual(
            sorted(b2["inputs"].keys()), ["blueprints", "geomFile", "settings"]
        )
        b2.close()

        # end-to-end validation that comparing a photocopy database works
        diffs = compareDatabases(db._fullPath, db2._fullPath)
        self.assertEqual(len(diffs.diffs), 0)


if __name__ == "__main__":
    unittest.main()
