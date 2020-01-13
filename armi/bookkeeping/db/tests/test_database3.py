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

import unittest
import os

import numpy
import numpy.testing
import h5py

from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT, ARMI_RUN_PATH

from armi.bookkeeping.db import database3 as database


class TestDatabase3(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(TEST_ROOT)
        self.db = database.Database3(self._testMethodName + ".h5", "w")
        self.db.open()
        self.stateRetainer = self.r.retainState().__enter__()

    def tearDown(self):
        self.db.close()
        self.stateRetainer.__exit__()

    def makeHistory(self):
        """
        Walk the reactor through a few time steps and write them to the db.
        """
        for cycle, node in ((cycle, node) for cycle in range(3) for node in range(3)):
            self.r.p.cycle = cycle
            self.r.p.timeNode = node
            # something that splitDatabase won't change, so that we can make sure that
            # the right data went to the right new groups/cycles
            self.r.p.cycleLength = cycle

            self.db.writeToDB(self.r)

    def _compareArrays(self, ref, src):
        """
        Compare two numpy arrays.

        Comparing numpy arrays that may have unsavory data (NaNs, Nones, jagged
        data, etc.) is really difficult. For now, convert to a list and compare
        element-by-element.
        """
        self.assertEqual(type(ref), type(src))
        if isinstance(ref, numpy.ndarray):
            ref = ref.tolist()
            src = src.tolist()

        for v1, v2 in zip(ref, src):
            # Entries may be None
            if isinstance(v1, numpy.ndarray):
                v1 = v1.tolist()
            if isinstance(v2, numpy.ndarray):
                v2 = v2.tolist()
            self.assertEqual(v1, v2)

    def _compareRoundTrip(self, data):
        """
        Make sure that data is unchanged by packing/unpacking.
        """
        packed, attrs = database.packSpecialData(data, "testing")
        roundTrip = database.unpackSpecialData(packed, attrs, "testing")
        self._compareArrays(data, roundTrip)

    def test_replaceNones(self):
        """
        This definitely needs some work.
        """
        data3 = numpy.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        data1 = numpy.array([1, 2, 3, 4, 5, 6, 7, 8])
        data1iNones = numpy.array([1, 2, None, 5, 6])
        data1fNones = numpy.array([None, 2.0, None, 5.0, 6.0])
        data2fNones = numpy.array([None, [[1.0, 2.0, 6.0], [2.0, 3.0, 4.0]]])
        dataJag = numpy.array([[[1, 2], [3, 4]], [[1, 2, 3], [4, 5, 6], [7, 8, 9]]])
        dataJagNones = numpy.array(
            [[[1, 2], [3, 4]], [[1], [1]], [[1, 2, 3], [4, 5, 6], [7, 8, 9]]]
        )
        dataDict = numpy.array(
            [{"bar": 2, "baz": 3}, {"foo": 4, "baz": 6}, {"foo": 7, "bar": 8}]
        )
        self._compareRoundTrip(data3)
        self._compareRoundTrip(data1)
        self._compareRoundTrip(data1iNones)
        self._compareRoundTrip(data1fNones)
        self._compareRoundTrip(data2fNones)
        self._compareRoundTrip(dataJag)
        self._compareRoundTrip(dataJagNones)
        self._compareRoundTrip(dataDict)

    def test_mergeHistory(self):
        self.makeHistory()

        # put some big data in an HDF5 attribute. This will exercise the code that pulls
        # such attributes into a formal dataset and a reference.
        self.r.p.cycle = 1
        self.r.p.timeNode = 0
        tnGroup = self.db.getH5Group(self.r)
        database._writeAttrs(
            tnGroup["layout/serialNum"], tnGroup, {"fakeBigData": numpy.eye(6400),
                "someString": "this isn't a reference to another dataset"}
        )

        db2 = database.Database3("restartDB.h5", "w")
        with db2:
            db2.mergeHistory(self.db, 2, 2)
            self.r.p.cycle = 1
            self.r.p.timeNode = 0
            tnGroup = db2.getH5Group(self.r)

            # this test is a little bit implementation-specific, but nice to be explicit
            self.assertEqual(tnGroup["layout/serialNum"].attrs["fakeBigData"],
                    "@/c01n00/attrs/0_fakeBigData")

            # actually exercise the _resolveAttrs function
            attrs = database._resolveAttrs(tnGroup["layout/serialNum"].attrs, tnGroup)
            self.assertTrue(numpy.array_equal(attrs["fakeBigData"], numpy.eye(6400)))

    def test_splitDatabase(self):
        self.makeHistory()

        self.db.splitDatabase(
            [(c, n) for c in (1, 2) for n in range(3)], "-all-iterations"
        )

        # Closing to copy back from fast path
        self.db.close()

        with h5py.File("test_splitDatabase.h5", "r") as newDb:
            self.assertTrue(newDb["c00n00/Reactor/cycle"][()] == 0)
            self.assertTrue(newDb["c00n00/Reactor/cycleLength"][()] == 1)
            self.assertTrue("c02n00" not in newDb)
            self.assertTrue(newDb.attrs["databaseVersion"] == database.DB_VERSION)


if __name__ == "__main__":
    import sys

    # sys.argv = ["", "TestDatabase3.test_splitDatabase"]
    unittest.main()
