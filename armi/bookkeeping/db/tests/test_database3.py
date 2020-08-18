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

import numpy
import h5py

from armi.bookkeeping.db import database3
from armi.reactor import grids
from armi.reactor.tests import test_reactors

from armi.tests import TEST_ROOT


class TestDatabase3(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(TEST_ROOT)
        cs = self.o.cs

        self.dbi = database3.DatabaseInterface(self.r, cs)
        self.dbi.initDB(fName=self._testMethodName + ".h5")
        self.db: db.Database3 = self.dbi.database
        self.stateRetainer = self.r.retainState().__enter__()

        # used to test location-based history. see details below
        self.centralAssemSerialNums = []
        self.centralTopBlockSerialNums = []

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

    def makeShuffleHistory(self):
        """
        Walk the reactor through a few time steps with some shuffling.
        """
        # Serial numbers *are not stable* (i.e., they can be different between test runs
        # due to parallelism and test run order). However, they are the simplest way to
        # check correctness of location-based history tracking. So we stash the serial
        # numbers at the location of interest so that we can use them later to check our
        # work.
        self.centralAssemSerialNums = []
        self.centralTopBlockSerialNums = []

        grid = self.r.core.spatialGrid
        for cycle in range(3):
            a1 = self.r.core.childrenByLocator[grid[cycle, 0, 0]]
            a2 = self.r.core.childrenByLocator[grid[0, 0, 0]]
            olda1Loc = a1.spatialLocator
            a1.moveTo(a2.spatialLocator)
            a2.moveTo(olda1Loc)
            c = self.r.core.childrenByLocator[grid[0, 0, 0]]
            self.centralAssemSerialNums.append(c.p.serialNum)
            self.centralTopBlockSerialNums.append(c[-1].p.serialNum)

            for node in range(3):
                self.r.p.cycle = cycle
                self.r.p.timeNode = node
                # something that splitDatabase won't change, so that we can make sure
                # that the right data went to the right new groups/cycles
                self.r.p.cycleLength = cycle

                self.db.writeToDB(self.r)
        # add some more data that isnt written to the database to test the
        # DatabaseInterface API
        self.r.p.cycle = 3
        self.r.p.timeNode = 0
        self.r.p.cycleLength = cycle
        self.r.core[0].p.chargeTime = 3

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
        packed, attrs = database3.packSpecialData(data, "testing")
        roundTrip = database3.unpackSpecialData(packed, attrs, "testing")
        self._compareArrays(data, roundTrip)

    def test_computeParents(self):
        # The below arrays represent a tree structure like this:
        #                 71 -----------------------.
        #                 |                          \
        #                12--.-----.------.          72
        #               / |  \      \      \
        #             22 30  4---.   6      18-.
        #            / |  |  | \  \        / |  \
        #           8 17  2 32 52 62      1  9  10
        #
        # This should cover a handful of corner cases
        numChildren = [2, 5, 2, 0, 0, 1, 0, 3, 0, 0, 0, 0, 3, 0, 0, 0, 0]
        serialNums = [71, 12, 22, 8, 17, 30, 2, 4, 32, 53, 62, 6, 18, 1, 9, 10, 72]

        expected_1 = [None, 71, 12, 22, 22, 12, 30, 12, 4, 4, 4, 12, 12, 18, 18, 18, 71]
        expected_2 = [
            None,
            None,
            71,
            12,
            12,
            71,
            12,
            71,
            12,
            12,
            12,
            71,
            71,
            12,
            12,
            12,
            None,
        ]
        expected_3 = [
            None,
            None,
            None,
            71,
            71,
            None,
            71,
            None,
            71,
            71,
            71,
            None,
            None,
            71,
            71,
            71,
            None,
        ]

        self.assertEqual(
            database3.Layout.computeAncestors(serialNums, numChildren), expected_1
        )
        self.assertEqual(
            database3.Layout.computeAncestors(serialNums, numChildren, 2), expected_2
        )
        self.assertEqual(
            database3.Layout.computeAncestors(serialNums, numChildren, 3), expected_3
        )

    def test_history(self) -> None:
        self.makeShuffleHistory()

        grid = self.r.core.spatialGrid
        testAssem = self.r.core.childrenByLocator[grid[0, 0, 0]]
        testBlock = testAssem[-1]

        # Test assem
        hist = self.db.getHistoryByLocation(
            testAssem, params=["chargeTime", "serialNum"]
        )
        expectedSn = {
            (c, n): self.centralAssemSerialNums[c] for c in range(3) for n in range(3)
        }
        self.assertEqual(expectedSn, hist["serialNum"])

        # test block
        hists = self.db.getHistoriesByLocation(
            [testBlock], params=["serialNum"], timeSteps=[(0, 0), (1, 0), (2, 0)]
        )
        expectedSn = {(c, 0): self.centralTopBlockSerialNums[c] for c in range(3)}
        self.assertEqual(expectedSn, hists[testBlock]["serialNum"])

        # cant mix blocks and assems, since they are different distance from core
        with self.assertRaises(ValueError):
            self.db.getHistoriesByLocation([testAssem, testBlock], params=["serialNum"])

        # if requested time step isnt written, return no content
        hist = self.dbi.getHistory(
            self.r.core[0], params=["chargeTime", "serialNum"], byLocation=True
        )
        self.assertIn((3, 0), hist["chargeTime"].keys())
        self.assertEqual(hist["chargeTime"][(3, 0)], 3)

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
        database3._writeAttrs(
            tnGroup["layout/serialNum"],
            tnGroup,
            {
                "fakeBigData": numpy.eye(6400),
                "someString": "this isn't a reference to another dataset",
            },
        )

        db2 = database3.Database3("restartDB.h5", "w")
        with db2:
            db2.mergeHistory(self.db, 2, 2)
            self.r.p.cycle = 1
            self.r.p.timeNode = 0
            tnGroup = db2.getH5Group(self.r)

            # this test is a little bit implementation-specific, but nice to be explicit
            self.assertEqual(
                tnGroup["layout/serialNum"].attrs["fakeBigData"],
                "@/c01n00/attrs/0_fakeBigData",
            )

            # actually exercise the _resolveAttrs function
            attrs = database3._resolveAttrs(tnGroup["layout/serialNum"].attrs, tnGroup)
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
            self.assertTrue(newDb.attrs["databaseVersion"] == database3.DB_VERSION)


class Test_LocationPacking(unittest.TestCase):
    def test_locationPacking(self):
        # pylint: disable=protected-access
        loc1 = grids.IndexLocation(1, 2, 3, None)
        loc2 = grids.CoordinateLocation(4.0, 5.0, 6.0, None)
        loc3 = grids.MultiIndexLocation(None)
        loc3.append(grids.IndexLocation(7, 8, 9, None))
        loc3.append(grids.IndexLocation(10, 11, 12, None))

        locs = [loc1, loc2, loc3]
        tp, data = database3._packLocations(locs)

        self.assertEqual(tp[0], database3.LOC_INDEX)
        self.assertEqual(tp[1], database3.LOC_COORD)
        self.assertEqual(tp[2], database3.LOC_MULTI + "2")

        unpackedData = database3._unpackLocations(tp, data)

        self.assertEqual(unpackedData[0], (1, 2, 3))
        self.assertEqual(unpackedData[1], (4.0, 5.0, 6.0))
        self.assertEqual(unpackedData[2], (7, 8, 9))


if __name__ == "__main__":
    import sys

    # sys.argv = ["", "TestDatabase3.test_splitDatabase"]
    unittest.main()
