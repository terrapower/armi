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

r""" Tests for the Database3 class"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access,no-member,disallowed-name,invalid-name
import subprocess
import unittest

import h5py
import numpy

from armi.bookkeeping.db import _getH5File
from armi.bookkeeping.db import database3
from armi.bookkeeping.db.databaseInterface import DatabaseInterface
from armi.reactor import parameters
from armi.reactor.tests.test_reactors import loadTestReactor, reduceTestReactorRings
from armi.tests import TEST_ROOT
from armi.utils import getPreviousTimeNode
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestDatabase3(unittest.TestCase):
    r"""Tests for the Database3 class"""

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()
        self.o, self.r = loadTestReactor(
            TEST_ROOT, customSettings={"reloadDBName": "reloadingDB.h5"}
        )
        reduceTestReactorRings(self.r, self.o.cs, maxNumRings=3)

        self.dbi = DatabaseInterface(self.r, self.o.cs)
        self.dbi.initDB(fName=self._testMethodName + ".h5")
        self.db: database3.Database3 = self.dbi.database
        self.stateRetainer = self.r.retainState().__enter__()

        # used to test location-based history. see details below
        self.centralAssemSerialNums = []
        self.centralTopBlockSerialNums = []

    def tearDown(self):
        self.db.close()
        self.stateRetainer.__exit__()
        self.td.__exit__(None, None, None)

    def test_writeToDB(self):
        self.r.p.cycle = 0
        self.r.p.timeNode = 0
        self.r.p.cycleLength = 0

        # Adding some nonsense in, to test NoDefault params
        self.r.p.availabilityFactor = parameters.NoDefault

        # validate that the H5 file gets bigger after the write
        self.assertEqual(list(self.db.h5db.keys()), ["inputs"])
        self.db.writeToDB(self.r)
        self.assertEqual(sorted(self.db.h5db.keys()), ["c00n00", "inputs"])

        keys = [
            "Circle",
            "Core",
            "DerivedShape",
            "Helix",
            "HexAssembly",
            "HexBlock",
            "Hexagon",
            "Reactor",
            "layout",
        ]
        self.assertEqual(sorted(self.db.h5db["c00n00"].keys()), sorted(keys))

        # validate availabilityFactor did not make it into the H5 file
        rKeys = ["cycle", "cycleLength", "flags", "serialNum", "timeNode"]
        self.assertEqual(
            sorted(self.db.h5db["c00n00"]["Reactor"].keys()), sorted(rKeys)
        )

    def test_getH5File(self):
        with self.assertRaises(TypeError):
            _getH5File(None)

        h5 = _getH5File(self.db)
        self.assertEqual(type(h5), h5py.File)

    def makeHistory(self):
        """Walk the reactor through a few time steps and write them to the db."""
        for cycle, node in ((cycle, node) for cycle in range(2) for node in range(2)):
            self.r.p.cycle = cycle
            self.r.p.timeNode = node
            # something that splitDatabase won't change, so that we can make sure that
            # the right data went to the right new groups/cycles
            self.r.p.cycleLength = cycle

            self.db.writeToDB(self.r)

    def makeShuffleHistory(self):
        """Walk the reactor through a few time steps with some shuffling."""
        # Serial numbers *are not stable* (i.e., they can be different between test runs
        # due to parallelism and test run order). However, they are the simplest way to
        # check correctness of location-based history tracking. So we stash the serial
        # numbers at the location of interest so that we can use them later to check our
        # work.
        self.centralAssemSerialNums = []
        self.centralTopBlockSerialNums = []

        grid = self.r.core.spatialGrid

        for cycle in range(2):
            a1 = self.r.core.childrenByLocator[grid[cycle, 0, 0]]
            a2 = self.r.core.childrenByLocator[grid[0, 0, 0]]
            olda1Loc = a1.spatialLocator
            a1.moveTo(a2.spatialLocator)
            a2.moveTo(olda1Loc)
            c = self.r.core.childrenByLocator[grid[0, 0, 0]]
            self.centralAssemSerialNums.append(c.p.serialNum)
            self.centralTopBlockSerialNums.append(c[-1].p.serialNum)

            for node in range(2):
                self.r.p.cycle = cycle
                self.r.p.timeNode = node
                # something that splitDatabase won't change, so that we can make sure
                # that the right data went to the right new groups/cycles
                self.r.p.cycleLength = cycle

                self.db.writeToDB(self.r)

        # add some more data that isnt written to the database to test the
        # DatabaseInterface API
        self.r.p.cycle = 2
        self.r.p.timeNode = 0
        self.r.p.cycleLength = cycle
        self.r.core[0].p.chargeTime = 2

        # add some fake missing parameter data to test allowMissing
        self.db.h5db["c00n00/Reactor/missingParam"] = "i don't exist"

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
        """Make sure that data is unchanged by packing/unpacking."""
        packed, attrs = database3.packSpecialData(data, "testing")
        roundTrip = database3.unpackSpecialData(packed, attrs, "testing")
        self._compareArrays(data, roundTrip)

    def test_prepRestartRun(self):
        """
        This test is based on the armiRun.yaml case that is loaded during the `setUp`
        above. In that cs, `reloadDBName` is set to 'reloadingDB.h5', `startCycle` = 1,
        and `startNode` = 2. The nonexistent 'reloadingDB.h5' must first be
        created here for this test.
        """
        # first successfully call to prepRestartRun
        o, r = loadTestReactor(
            TEST_ROOT, customSettings={"reloadDBName": "reloadingDB.h5"}
        )
        cs = o.cs
        reduceTestReactorRings(r, cs, maxNumRings=3)

        ratedPower = cs["power"]
        startCycle = cs["startCycle"]
        startNode = cs["startNode"]
        cyclesSetting = [
            {"step days": [1000, 1000], "power fractions": [1, 1]},
            {"step days": [1000, 1000], "power fractions": [1, 1]},
            {"step days": [1000, 1000], "power fractions": [1, 1]},
        ]
        cycleP, nodeP = getPreviousTimeNode(startCycle, startNode, cs)
        cyclesSetting[cycleP]["power fractions"][nodeP] = 0.5
        numCycles = 2
        numNodes = 2
        cs = cs.modified(
            newSettings={
                "nCycles": numCycles,
                "cycles": cyclesSetting,
                "reloadDBName": "something_fake.h5",
            }
        )

        # create a db based on the cs
        dbi = DatabaseInterface(r, cs)
        dbi.initDB(fName="reloadingDB.h5")
        db = dbi.database

        # populate the db with some things
        for cycle, node in (
            (cycle, node) for cycle in range(numCycles) for node in range(numNodes)
        ):
            r.p.cycle = cycle
            r.p.timeNode = node
            r.p.cycleLength = sum(cyclesSetting[cycle]["step days"])
            r.core.p.power = ratedPower * cyclesSetting[cycle]["power fractions"][node]
            db.writeToDB(r)
        db.close()

        self.dbi.prepRestartRun()

        # prove that the reloaded reactor has the correct power
        self.assertEqual(self.o.r.p.cycle, cycleP)
        self.assertEqual(self.o.r.p.timeNode, nodeP)
        self.assertEqual(cyclesSetting[cycleP]["power fractions"][nodeP], 0.5)
        self.assertEqual(
            self.o.r.core.p.power,
            ratedPower * cyclesSetting[cycleP]["power fractions"][nodeP],
        )

        # now make the cycle histories clash and confirm that an error is thrown
        cs = cs.modified(
            newSettings={
                "cycles": [
                    {"step days": [666, 666], "power fractions": [1, 1]},
                    {"step days": [666, 666], "power fractions": [1, 1]},
                    {"step days": [666, 666], "power fractions": [1, 1]},
                ],
            }
        )

        # create a db based on the cs
        dbi = DatabaseInterface(r, cs)
        dbi.initDB(fName="reloadingDB.h5")
        db = dbi.database

        # populate the db with something
        for cycle, node in (
            (cycle, node) for cycle in range(numCycles) for node in range(numNodes)
        ):
            r.p.cycle = cycle
            r.p.timeNode = node
            r.p.cycleLength = 2000
            db.writeToDB(r)
        db.close()

        with self.assertRaises(ValueError):
            self.dbi.prepRestartRun()

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

    def test_load(self):
        self.makeShuffleHistory()
        with self.assertRaises(KeyError):
            _r = self.db.load(0, 0)

        _r = self.db.load(0, 0, allowMissing=True)

        # show that we can use negative indices to load
        r = self.db.load(0, -2, allowMissing=True)
        self.assertEqual(r.p.timeNode, 1)

        with self.assertRaises(ValueError):
            # makeShuffleHistory only populates 2 nodes, but the case settings
            # defines 3, so we must check -4 before getting an error
            self.db.load(0, -4, allowMissing=True)

        del self.db.h5db["c00n00/Reactor/missingParam"]
        _r = self.db.load(0, 0, allowMissing=False)

        # we shouldn't be able to set the fileName if a file is open
        with self.assertRaises(RuntimeError):
            self.db.fileName = "whatever.h5"

    def test_load_updateGlobalAssemNum(self):
        from armi.reactor import assemblies
        from armi.reactor.assemblies import resetAssemNumCounter

        self.makeHistory()

        resetAssemNumCounter()
        self.assertEqual(assemblies._assemNum, 0)

        r = self.db.load(0, 0, allowMissing=True, updateGlobalAssemNum=False)
        #  len(r.core.sfp) is zero but these nums are still reserved
        numSFPBlueprints = 4
        expectedNum = len(r.core) + numSFPBlueprints
        self.assertEqual(assemblies._assemNum, expectedNum)

        # now do the same call again and show that the global _assemNum keeps going up.
        # in db.load, rector objects are built in layout._initComps() so the global assem num
        # will continue to grow (in this case, double).
        self.db.load(0, 0, allowMissing=True, updateGlobalAssemNum=False)
        self.assertEqual(assemblies._assemNum, expectedNum * 2)

        # now load but set updateGlobalAssemNum=True and show that the global assem num
        # is updated and equal to self.r.p.maxAssemNum + 1 which is equal to the number of
        # assemblies in blueprints/core.
        r = self.db.load(0, 0, allowMissing=True, updateGlobalAssemNum=True)
        expected = len(self.r.core) + len(self.r.blueprints.assemblies.values())
        self.assertEqual(15, expected)

        # repeat the test above to show that subsequent db loads (with updateGlobalAssemNum=True)
        # do not continue to increase the global assem num.
        self.db.load(0, 0, allowMissing=True, updateGlobalAssemNum=True)
        self.assertEqual(15, expected)

    def test_history(self):
        self.makeShuffleHistory()

        grid = self.r.core.spatialGrid
        testAssem = self.r.core.childrenByLocator[grid[0, 0, 0]]
        testBlock = testAssem[-1]

        # Test assem
        hist = self.db.getHistoryByLocation(
            testAssem, params=["chargeTime", "serialNum"]
        )
        expectedSn = {
            (c, n): self.centralAssemSerialNums[c] for c in range(2) for n in range(2)
        }
        self.assertEqual(expectedSn, hist["serialNum"])

        # test block
        hists = self.db.getHistoriesByLocation(
            [testBlock], params=["serialNum"], timeSteps=[(0, 0), (1, 0)]
        )
        expectedSn = {(c, 0): self.centralTopBlockSerialNums[c] for c in range(2)}
        self.assertEqual(expectedSn, hists[testBlock]["serialNum"])

        # cant mix blocks and assems, since they are different distance from core
        with self.assertRaises(ValueError):
            self.db.getHistoriesByLocation([testAssem, testBlock], params=["serialNum"])

        # if requested time step isnt written, return no content
        hist = self.dbi.getHistory(
            self.r.core[0], params=["chargeTime", "serialNum"], byLocation=True
        )
        self.assertIn((2, 0), hist["chargeTime"].keys())
        self.assertEqual(hist["chargeTime"][(2, 0)], 2)

    def test_auxData(self):
        path = self.db.getAuxiliaryDataPath((2, 0), "test_stuff")
        self.assertEqual(path, "c02n00/test_stuff")

        with self.assertRaises(KeyError):
            self.db.genAuxiliaryData((-1, -1))

    # TODO: This should be expanded.
    def test_replaceNones(self):
        """Super basic test that we handle Nones correctly in database read/writes"""
        data3 = numpy.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        data1 = numpy.array([1, 2, 3, 4, 5, 6, 7, 8])
        data1iNones = numpy.array([1, 2, None, 5, 6])
        data1fNones = numpy.array([None, 2.0, None, 5.0, 6.0])
        data2fNones = numpy.array(
            [None, [[1.0, 2.0, 6.0], [2.0, 3.0, 4.0]]], dtype=object
        )
        dataJag = numpy.array(
            [[[1, 2], [3, 4]], [[1, 2, 3], [4, 5, 6], [7, 8, 9]]], dtype=object
        )
        dataJagNones = numpy.array(
            [[[1, 2], [3, 4]], [[1], [1]], [[1, 2, 3], [4, 5, 6], [7, 8, 9]]],
            dtype=object,
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
        # pylint: disable=protected-access
        self.makeHistory()

        # put some big data in an HDF5 attribute. This will exercise the code that pulls
        # such attributes into a formal dataset and a reference.
        self.r.p.cycle = 1
        self.r.p.timeNode = 0
        tnGroup = self.db.getH5Group(self.r)
        database3.Database3._writeAttrs(
            tnGroup["layout/serialNum"],
            tnGroup,
            {
                "fakeBigData": numpy.eye(6400),
                "someString": "this isn't a reference to another dataset",
            },
        )

        db_path = "restartDB.h5"
        db2 = database3.Database3(db_path, "w")
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

            # exercise the _resolveAttrs function
            attrs = database3.Database3._resolveAttrs(
                tnGroup["layout/serialNum"].attrs, tnGroup
            )
            self.assertTrue(numpy.array_equal(attrs["fakeBigData"], numpy.eye(6400)))

            keys = sorted(db2.keys())
            self.assertEqual(len(keys), 4)
            self.assertEqual(keys[:3], ["/c00n00", "/c00n01", "/c01n00"])

    def test_splitDatabase(self):
        self.makeHistory()

        self.db.splitDatabase(
            [(c, n) for c in (0, 1) for n in range(2)], "-all-iterations"
        )

        # Closing to copy back from fast path
        self.db.close()

        with h5py.File("test_splitDatabase.h5", "r") as newDb:
            self.assertEqual(newDb["c00n00/Reactor/cycle"][()], 0)
            self.assertEqual(newDb["c00n00/Reactor/cycleLength"][()][0], 0)
            self.assertNotIn("c03n00", newDb)
            self.assertEqual(newDb.attrs["databaseVersion"], database3.DB_VERSION)

            # validate that the min set of meta data keys exists
            meta_data_keys = [
                "appName",
                "armiLocation",
                "databaseVersion",
                "hostname",
                "localCommitHash",
                "machines",
                "platform",
                "platformArch",
                "platformRelease",
                "platformVersion",
                "pluginPaths",
                "python",
                "startTime",
                "successfulCompletion",
                "user",
                "version",
            ]
            for meta_key in meta_data_keys:
                self.assertIn(meta_key, newDb.attrs)
                self.assertIsNotNone(newDb.attrs[meta_key])

        # test an edge case - no DB to split
        with self.assertRaises(ValueError):
            self.db.h5db = None
            self.db.splitDatabase(
                [(c, n) for c in (0, 1) for n in range(2)], "-all-iterations"
            )

    def test_grabLocalCommitHash(self):
        """test of static method to grab a local commit hash with ARMI version"""
        # 1. test outside a Git repo
        localHash = database3.Database3.grabLocalCommitHash()
        self.assertEqual(localHash, "unknown")

        # 2. test inside an empty git repo
        code = subprocess.run(
            ["git", "init", "."],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        self.assertEqual(code, 0)
        localHash = database3.Database3.grabLocalCommitHash()
        self.assertEqual(localHash, "unknown")

        # 3. test inside a git repo with one tag
        # commit the empty repo
        code = subprocess.run(
            ["git", "commit", "--allow-empty", "-m", '"init"', "--author", '"sam <>"'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        if code == 128:
            # GitHub Actions blocks certain kinds of Git commands
            return

        # create a tag off our new commit
        code = subprocess.run(
            ["git", "tag", "thanks", "-m", '"you_rock"'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        self.assertEqual(code, 0)

        # test that we recover the correct commit hash
        localHash = database3.Database3.grabLocalCommitHash()
        self.assertEqual(localHash, "thanks")

        # delete the .git directory
        code = subprocess.run(
            ["git", "clean", "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode
        self.assertEqual(code, 0)
        code = subprocess.run(
            ["git", "clean", "-f", "-d"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        self.assertEqual(code, 0)

    def test_fileName(self):
        # test the file name getter
        self.assertEqual(str(self.db.fileName), "test_fileName.h5")

        # test the file name setter
        self.db.close()
        self.db.fileName = "thing.h5"
        self.assertEqual(str(self.db.fileName), "thing.h5")

    def test_readInputsFromDB(self):
        inputs = self.db.readInputsFromDB()
        self.assertEqual(len(inputs), 3)

        self.assertGreater(len(inputs[0]), 100)
        self.assertIn("metadata:", inputs[0])
        self.assertIn("settings:", inputs[0])

        self.assertEqual(len(inputs[1]), 0)

        self.assertGreater(len(inputs[2]), 100)
        self.assertIn("custom isotopics:", inputs[2])
        self.assertIn("blocks:", inputs[2])

    def test_deleting(self):
        self.assertEqual(type(self.db), database3.Database3)
        del self.db
        self.assertFalse(hasattr(self, "db"))
        self.db = self.dbi.database

    def test_open(self):
        with self.assertRaises(ValueError):
            self.db.open()

    def test_loadCS(self):
        cs = self.db.loadCS()
        self.assertEqual(cs["numProcessors"], 1)
        self.assertEqual(cs["nCycles"], 6)

    def test_loadBlueprints(self):
        bp = self.db.loadBlueprints()
        self.assertIsNone(bp.nuclideFlags)
        self.assertEqual(len(bp.assemblies), 0)


if __name__ == "__main__":
    unittest.main()
