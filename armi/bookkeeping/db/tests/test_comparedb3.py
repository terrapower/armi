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
import numpy as np

from armi.bookkeeping.db import database3
from armi.bookkeeping.db.compareDB3 import (
    _compareAuxData,
    _diffSimpleData,
    _diffSpecialData,
    compareDatabases,
    DiffResults,
    OutputWriter,
)
from armi.reactor.tests import test_reactors
from armi.tests import mockRunLogs, TEST_ROOT
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

        # create two DBs, identical but for file names
        dbs = []
        for i in range(2):
            # create the tests DB
            dbi = database3.DatabaseInterface(r, o.cs)
            dbi.initDB(fName=self._testMethodName + str(i) + ".h5")
            db = dbi.database

            # validate the file exists, and force it to be readable again
            b = h5py.File(db._fullPath, "r")
            self.assertEqual(list(b.keys()), ["inputs"])
            self.assertEqual(
                sorted(b["inputs"].keys()), ["blueprints", "geomFile", "settings"]
            )
            b.close()

            # append to lists
            dbs.append(db)

        # end-to-end validation that comparing a photocopy database works
        diffs = compareDatabases(dbs[0]._fullPath, dbs[1]._fullPath)
        self.assertEqual(len(diffs.diffs), 0)
        self.assertEqual(diffs.nDiffs(), 0)

    def test_compareDatabaseSim(self):
        """end-to-end test of compareDatabases() on very simlar databases"""
        # build two super-simple H5 files for testing
        o, r = test_reactors.loadTestReactor(TEST_ROOT)

        # create two DBs, identical but for file names
        dbs = []
        for nCycles in range(1, 3):
            # build some test data
            days = 100 * nCycles
            cycles = [
                {"step days": [days, days], "power fractions": [1, 0.5]}
            ] * nCycles
            cs = o.cs.modified(
                newSettings={
                    "nCycles": nCycles,
                    "cycles": cycles,
                    "reloadDBName": "something_fake.h5",
                }
            )

            # create the tests DB
            dbi = database3.DatabaseInterface(r, cs)
            dbi.initDB(fName=self._testMethodName + str(nCycles) + ".h5")
            db = dbi.database

            # populate the db with something
            for cycle, node in (
                (cycle, node) for cycle in range(nCycles + 1) for node in range(2)
            ):
                r.p.cycle = cycle
                r.p.timeNode = node
                r.p.cycleLength = days * 2
                db.writeToDB(r)

            # validate the file exists, and force it to be readable again
            b = h5py.File(db._fullPath, "r")
            dbKeys = sorted(b.keys())
            self.assertEqual(len(dbKeys), 2 * (nCycles + 1) + 1)
            self.assertIn("inputs", dbKeys)
            self.assertIn("c00n00", dbKeys)
            self.assertEqual(
                sorted(b["inputs"].keys()), ["blueprints", "geomFile", "settings"]
            )
            b.close()

            # append to lists
            dbs.append(db)

        # end-to-end validation that comparing a photocopy database works
        diffs = compareDatabases(dbs[0]._fullPath, dbs[1]._fullPath)
        self.assertEqual(len(diffs.diffs), 456)
        self.assertEqual(diffs.nDiffs(), 3)

    def test_diffSpecialData(self):
        dr = DiffResults(0.01)

        fileName = "test_diffSpecialData.txt"
        with OutputWriter(fileName) as out:
            # spin up one example H5 Dataset
            f1 = h5py.File("test_diffSpecialData1.hdf5", "w")
            a1 = np.arange(100, dtype="<f8")
            refData = f1.create_dataset("numberDensities", data=a1)
            refData.attrs["1"] = 1
            refData.attrs["2"] = 22
            refData.attrs["numDens"] = a1

            # spin up an identical example H5 Dataset
            f2 = h5py.File("test_diffSpecialData2.hdf5", "w")
            srcData = f2.create_dataset("numberDensities", data=a1)
            srcData.attrs["1"] = 1
            srcData.attrs["2"] = 22
            srcData.attrs["numDens"] = a1

            # there should be no difference
            _diffSpecialData(refData, srcData, out, dr)
            self.assertEqual(dr.nDiffs(), 0)

            # spin up a different size example H5 Dataset
            f3 = h5py.File("test_diffSpecialData3.hdf5", "w")
            a2 = np.arange(90, dtype="<f8")
            srcData3 = f3.create_dataset("numberDensities", data=a2)
            srcData3.attrs["1"] = 1
            srcData3.attrs["2"] = 22
            srcData3.attrs["numDens"] = a2

            # there should a logged error, but no diff
            with mockRunLogs.BufferLog() as mock:
                _diffSpecialData(refData, srcData3, out, dr)
                self.assertEqual(dr.nDiffs(), 0)
                self.assertIn("Special formatting parameters for", mock._outputStream)

    def test_diffSimpleData(self):
        dr = DiffResults(0.01)

        # spin up one example H5 Dataset
        f1 = h5py.File("test_diffSimpleData1.hdf5", "w")
        a1 = np.arange(100, dtype="<f8")
        refData = f1.create_dataset("numberDensities", data=a1)
        refData.attrs["1"] = 1
        refData.attrs["2"] = 22
        refData.attrs["numDens"] = a1

        # spin up an identical example H5 Dataset
        f2 = h5py.File("test_diffSimpleData2.hdf5", "w")
        srcData = f2.create_dataset("numberDensities", data=a1)
        srcData.attrs["1"] = 1
        srcData.attrs["2"] = 22
        srcData.attrs["numDens"] = a1

        # there should be no difference
        _diffSimpleData(refData, srcData, dr)
        self.assertEqual(dr.nDiffs(), 0)

        # spin up a different size example H5 Dataset
        f3 = h5py.File("test_diffSimpleData3.hdf5", "w")
        a2 = np.arange(90, dtype="<f8")
        srcData3 = f3.create_dataset("numberDensities", data=a2)
        srcData3.attrs["1"] = 1
        srcData3.attrs["2"] = 22
        srcData3.attrs["numDens"] = a2

        # there should be a small difference
        _diffSimpleData(refData, srcData3, dr)
        self.assertEqual(dr.nDiffs(), 3)

    def test_compareAuxData(self):
        dr = DiffResults(0.01)

        fileName = "test_diffSpecialData.txt"
        with OutputWriter(fileName) as out:
            # spin up one example H5 Dataset
            f1 = h5py.File("test_compareAuxData1.hdf5", "w")
            a1 = np.arange(100, dtype="<f8")
            refData = f1.create_group("numberDensities")
            refData.attrs["1"] = 1
            refData.attrs["2"] = 22
            refData.attrs["numDens"] = a1

            # spin up an identical example H5 Dataset
            f2 = h5py.File("test_compareAuxData2.hdf5", "w")
            srcData = f2.create_group("numberDensities")
            srcData.attrs["1"] = 1
            srcData.attrs["2"] = 22
            srcData.attrs["numDens"] = a1

            # there should be no difference
            _compareAuxData(out, refData, srcData, dr)
            self.assertEqual(dr.nDiffs(), 0)


if __name__ == "__main__":
    unittest.main()
