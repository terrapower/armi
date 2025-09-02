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
"""Tests for the Database class."""

import io
import os
import shutil
import subprocess
import unittest
from glob import glob
from unittest.mock import Mock, patch

import h5py
import numpy as np

from armi.bookkeeping.db import _getH5File, database, loadOperator
from armi.bookkeeping.db.database import Database
from armi.bookkeeping.db.databaseInterface import DatabaseInterface
from armi.bookkeeping.db.jaggedArray import JaggedArray
from armi.reactor import parameters
from armi.reactor.excoreStructure import ExcoreCollection, ExcoreStructure
from armi.reactor.reactors import Core, Reactor
from armi.reactor.spentFuelPool import SpentFuelPool
from armi.settings.fwSettings.globalSettings import (
    CONF_GROW_TO_FULL_CORE_AFTER_LOAD,
    CONF_SORT_REACTOR,
)
from armi.testing import loadTestReactor, reduceTestReactorRings
from armi.tests import TEST_ROOT, mockRunLogs
from armi.utils import getPreviousTimeNode, safeCopy
from armi.utils.directoryChangers import TemporaryDirectoryChanger

# determine if this is a parallel run, and git is installed
GIT_EXE = None
if shutil.which("git") is not None:
    GIT_EXE = "git"
elif shutil.which("git.exe") is not None:
    GIT_EXE = "git.exe"


class TestDatabase(unittest.TestCase):
    """Tests for the Database class that require a large, complicated reactor."""

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()
        self.o, self.r = loadTestReactor(TEST_ROOT, customSettings={"reloadDBName": "reloadingDB.h5"})
        reduceTestReactorRings(self.r, self.o.cs, maxNumRings=3)

        self.dbi = DatabaseInterface(self.r, self.o.cs)
        self.dbi.initDB(fName=self._testMethodName + ".h5")
        self.db: Database = self.dbi.database
        self.stateRetainer = self.r.retainState().__enter__()

        # used to test location-based history. see details below
        self.centralAssemSerialNums = []
        self.centralTopBlockSerialNums = []

    def tearDown(self):
        self.db.close()
        self.stateRetainer.__exit__()
        self.td.__exit__(None, None, None)

    def makeShuffleHistory(self):
        """Walk the reactor through a few time steps with some shuffling."""
        # Serial numbers *are not stable* (i.e., they can be different between test runs
        # due to parallelism and test run order). However, they are the simplest way to
        # check correctness of location-based history tracking. So we stash the serial
        # numbers at the location of interest so we can use them later to check our work.
        self.centralAssemSerialNums = []
        self.centralTopBlockSerialNums = []

        grid = self.r.core.spatialGrid

        t = 0
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
                # something that splitDatabase won't change, so that we can make sure
                # that the right data went to the right new groups/cycles
                self.r.p.cycleLength = cycle
                self.r.p.cycle = cycle
                self.r.p.timeNode = node
                t += 1.0
                self.r.p.time = t
                self.db.writeToDB(self.r)

        # add some more data that isn't written to the database to test the
        # DatabaseInterface API
        self.r.p.cycle = 2
        self.r.p.timeNode = 0
        self.r.p.cycleLength = cycle
        self.r.core[0].p.chargeTime = 2

        # add some fake missing parameter data to test allowMissing
        self.db.h5db["c00n00/Reactor/missingParam"] = "i don't exist"

    def test_load(self):
        """Load a reactor at different time steps, from the database.

        .. test:: Load the reactor from the database.
            :id: T_ARMI_DB_TIME1
            :tests: R_ARMI_DB_TIME
        """
        self.makeShuffleHistory()
        with self.assertRaises(KeyError):
            _r = self.db.load(0, 0)

        # Default load, should pass without error
        _r = self.db.load(0, 0, allowMissing=True)

        # Show that we can use negative indices to load
        r = self.db.load(0, -2, allowMissing=True)
        self.assertEqual(r.p.timeNode, 1)

        with self.assertRaises(ValueError):
            # makeShuffleHistory only populates 2 nodes, but the case settings defines 3, so we must check -4 before
            # getting an error
            self.db.load(0, -4, allowMissing=True)

        # show we can delete a specify H5 key.
        del self.db.h5db["c00n00/Reactor/missingParam"]
        _r = self.db.load(0, 0, allowMissing=False)

        # show we can delete an entire time now from the DB.
        del self.db[0, 0, ""]
        with self.assertRaises(KeyError):
            self.db.load(0, 0, allowMissing=False)

        # We should not be able to set the fileName if a file is open.
        with self.assertRaises(RuntimeError):
            self.db.fileName = "whatever.h5"

    def test_loadSortSetting(self):
        self.makeShuffleHistory()

        # default load, should pass without error
        r0 = self.db.load(0, 0, allowMissing=True)

        # test that the reactor loads differently, dependent on the setting
        cs = self.db.loadCS()
        cs = cs.modified(newSettings={CONF_SORT_REACTOR: False})
        r1 = self.db.load(0, 0, cs=cs, allowMissing=True)

        # the reactor / core should be the same size
        self.assertEqual(len(r0), len(r1))
        self.assertEqual(len(r0.core), len(r1.core))

    def test_history(self):
        self.makeShuffleHistory()

        grid = self.r.core.spatialGrid
        testAssem = self.r.core.childrenByLocator[grid[0, 0, 0]]
        testBlock = testAssem[-1]

        # Test assem
        hist = self.db.getHistoryByLocation(testAssem, params=["chargeTime", "serialNum"])
        expectedSn = {(c, n): self.centralAssemSerialNums[c] for c in range(2) for n in range(2)}
        self.assertEqual(expectedSn, hist["serialNum"])

        # test block
        hists = self.db.getHistoriesByLocation([testBlock], params=["serialNum"], timeSteps=[(0, 0), (1, 0)])
        expectedSn = {(c, 0): self.centralTopBlockSerialNums[c] for c in range(2)}
        self.assertEqual(expectedSn, hists[testBlock]["serialNum"])

        # can't mix blocks and assems, since they are different distance from core
        with self.assertRaises(ValueError):
            self.db.getHistoriesByLocation([testAssem, testBlock], params=["serialNum"])

        # if requested time step isn't written, return no content
        hist = self.dbi.getHistory(self.r.core[0], params=["chargeTime", "serialNum"], byLocation=True)
        self.assertIn((2, 0), hist["chargeTime"].keys())
        self.assertEqual(hist["chargeTime"][(2, 0)], 2)

        # test edge case: ancient DB file
        v = self.db._versionMinor
        self.db._versionMinor = 3
        with self.assertRaises(ValueError):
            self.db.getHistoriesByLocation([testBlock], params=["serialNum"], timeSteps=[(0, 0), (1, 0)])
        self.db._versionMinor = v

    def test_fullCoreOnDbLoad(self):
        """Test we can expand a reactor to full core when loading from DB via settings."""
        self.assertFalse(self.r.core.isFullCore)
        self.db.writeToDB(self.r)
        cs = self.db.loadCS()
        cs = cs.modified(newSettings={CONF_GROW_TO_FULL_CORE_AFTER_LOAD: True})
        r: Reactor = self.db.load(0, 0, cs=cs)
        self.assertTrue(r.core.isFullCore)

    def test_dontExpandIfFullCoreInDB(self):
        """Test that a full core reactor in the database is not expanded further."""
        self.assertFalse(self.r.core.isFullCore)
        self.db.writeToDB(self.r)
        cs = self.db.loadCS()
        cs = cs.modified(newSettings={CONF_GROW_TO_FULL_CORE_AFTER_LOAD: True})
        mockGrow = Mock()
        with (
            patch("armi.reactor.cores.Core.isFullCore", Mock(return_value=True)),
            patch("armi.reactor.cores.Core.growToFullCore", mockGrow),
        ):
            self.db.load(0, 0, cs=cs)
        mockGrow.assert_not_called()

    def test_getCycleNodeAtTime(self):
        self.makeShuffleHistory()
        self.db.close()

        # test that the math works correctly
        cycleNodes = Database.getCycleNodeAtTime(self.db.fileName, 0, 0.87, False)
        self.assertEqual(cycleNodes, ["c00n00"])

        cycleNodes = Database.getCycleNodeAtTime(self.db.fileName, 0.23, 1.2, False)
        self.assertEqual(cycleNodes, ["c00n00", "c00n01"])

        cycleNodes = Database.getCycleNodeAtTime(self.db.fileName, 0.001, 2.345, False)
        self.assertEqual(cycleNodes, ["c00n00", "c00n01", "c01n00"])

        cycleNodes = Database.getCycleNodeAtTime(self.db.fileName, 0, 3.123, False)
        self.assertEqual(cycleNodes, ["c00n00", "c00n01", "c01n00", "c01n01"])

        cycleNodes = Database.getCycleNodeAtTime(self.db.fileName, 0.123, 4.0, False)
        self.assertEqual(cycleNodes, ["c00n00", "c00n01", "c01n00", "c01n01"])

        # test some exceptions are correctly raised
        with self.assertRaises(AssertionError):
            Database.getCycleNodeAtTime(self.db.fileName, -1, 1, False)

        with self.assertRaises(AssertionError):
            Database.getCycleNodeAtTime(self.db.fileName, 3, 1, False)

        with self.assertRaises(ValueError):
            Database.getCycleNodeAtTime(self.db.fileName, 5, 6, False)

        with self.assertRaises(ValueError):
            Database.getCycleNodeAtTime(self.db.fileName, 1, 140, True)


class TestDatabaseSmaller(unittest.TestCase):
    """Tests for the Database class, that can use a smaller test reactor."""

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()
        self.o, self.r = loadTestReactor(
            TEST_ROOT,
            customSettings={"reloadDBName": "reloadingDB.h5"},
            inputFileName="smallestTestReactor/armiRunSmallest.yaml",
        )

        self.dbi = DatabaseInterface(self.r, self.o.cs)
        self.dbi.initDB(fName=self._testMethodName + ".h5")
        self.db: Database = self.dbi.database
        self.stateRetainer = self.r.retainState().__enter__()

    def tearDown(self):
        self.db.close()
        self.stateRetainer.__exit__()
        self.td.__exit__(None, None, None)

    def makeHistory(self):
        """Walk the reactor through a few time steps and write them to the db."""
        for cycle, node in ((cycle, node) for cycle in range(2) for node in range(2)):
            self.r.p.cycle = cycle
            self.r.p.timeNode = node
            # something that splitDatabase won't change, so that we can make sure that
            # the right data went to the right new groups/cycles
            self.r.p.cycleLength = cycle

            self.db.writeToDB(self.r)

    def test_loadOperator(self):
        self.makeHistory()
        self.db.close()
        # Write a bad setting to the DB
        with h5py.File(self.db.fileName, "r+") as hf:
            settingz = hf["inputs/settings"].asstr()[()]
            settingz += "  fakeTerminator: I'll be back"
            stream = io.StringIO(settingz)
            csString = stream.read()
            del hf["inputs/settings"]
            hf["inputs/settings"] = csString

        # Test with no complaints
        with mockRunLogs.BufferLog() as mock:
            _o = loadOperator(
                self._testMethodName + ".h5",
                0,
                0,
                allowMissing=True,
                handleInvalids=False,
            )
            self.assertNotIn("fakeTerminator", mock.getStdout())

        # Test with complaints
        with mockRunLogs.BufferLog() as mock:
            _o = loadOperator(
                self._testMethodName + ".h5",
                0,
                0,
                allowMissing=True,
                handleInvalids=True,
            )
            self.assertIn("Ignoring invalid settings", mock.getStdout())
            self.assertIn("fakeTerminator", mock.getStdout())

    def _compareArrays(self, ref, src):
        """
        Compare two numpy arrays.

        Comparing numpy arrays that may have unsavory data (NaNs, Nones, jagged
        data, etc.) is really difficult. For now, convert to a list and compare
        element-by-element.
        """
        self.assertEqual(type(ref), type(src))
        if isinstance(ref, np.ndarray):
            ref = ref.tolist()
            src = src.tolist()

        for v1, v2 in zip(ref, src):
            # Entries may be None
            if isinstance(v1, np.ndarray):
                v1 = v1.tolist()
            if isinstance(v2, np.ndarray):
                v2 = v2.tolist()
            self.assertEqual(v1, v2)

    def _compareRoundTrip(self, data):
        """Make sure that data is unchanged by packing/unpacking."""
        packed, attrs = database.packSpecialData(data, "testing")
        roundTrip = database.unpackSpecialData(packed, attrs, "testing")
        self._compareArrays(data, roundTrip)

    def test_getArrayShape(self):
        """Tests a helper method for ``_writeParams``."""
        base = [1, 2, 3, 4]
        self.assertEqual(Database._getArrayShape(base), (4,))
        self.assertEqual(Database._getArrayShape(tuple(base)), (4,))
        arr = np.array(base)
        self.assertEqual(Database._getArrayShape(arr), (4,))
        arr = np.array([base])
        self.assertEqual(Database._getArrayShape(arr), (1, 4))
        # not array type
        self.assertEqual(Database._getArrayShape(1), 1)
        self.assertEqual(Database._getArrayShape(None), 1)

    def test_writeToDB(self):
        """Test writing to the database.

        .. test:: Write a single time step of data to the database.
            :id: T_ARMI_DB_TIME0
            :tests: R_ARMI_DB_TIME
        """
        self.r.p.cycle = 0
        self.r.p.cycleLength = 1
        self.r.p.time = 0
        self.r.p.timeNode = 0

        # Adding some nonsense in, to test NoDefault params
        self.r.p.availabilityFactor = parameters.NoDefault

        # validate that the H5 file gets bigger after the write
        self.assertEqual(list(self.db.h5db.keys()), ["inputs"])
        self.db.writeToDB(self.r)
        self.assertEqual(sorted(self.db.h5db.keys()), ["c00n00", "inputs"])

        # check the keys for a single time step
        keys = [
            "Circle",
            "Core",
            "DerivedShape",
            "Helix",
            "HexAssembly",
            "HexBlock",
            "Hexagon",
            "Reactor",
            "SpentFuelPool",
            "layout",
        ]
        self.assertEqual(sorted(self.db.h5db["c00n00"].keys()), sorted(keys))

        # validate availabilityFactor did not make it into the H5 file, but the time parameters did
        rKeys = [
            "cycle",
            "cycleLength",
            "time",
            "timeNode",
        ]
        h5Keys = sorted(self.db.h5db["c00n00"]["Reactor"].keys())
        for rKey in rKeys:
            self.assertIn(rKey, h5Keys)

    def test_getH5File(self):
        """
        Get the h5 file for the database, because that file format is language-agnostic.

        .. test:: Show the database is H5-formatted.
            :id: T_ARMI_DB_H5
            :tests: R_ARMI_DB_H5
        """
        with self.assertRaises(TypeError):
            _getH5File(None)

        h5 = _getH5File(self.db)
        self.assertEqual(type(h5), h5py.File)

    def test_auxData(self):
        path = self.db.getAuxiliaryDataPath((2, 0), "test_stuff")
        self.assertEqual(path, "c02n00/test_stuff")

        with self.assertRaises(KeyError):
            self.db.genAuxiliaryData((-1, -1))

    def test_replaceNones(self):
        """Super basic test that we handle Nones correctly in database read/writes."""
        data3 = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        data1 = np.array([1, 2, 3, 4, 5, 6, 7, 8])
        data1iNones = np.array([1, 2, None, 5, 6])
        data1fNones = np.array([None, 2.0, None, 5.0, 6.0])
        data2fNones = np.array([None, [[1.0, 2.0, 6.0], [2.0, 3.0, 4.0]]], dtype=object)
        twoByTwo = np.array([[1, 2], [3, 4]])
        twoByOne = np.array([[1], [None]])
        threeByThree = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        dataJag = JaggedArray([twoByTwo, threeByThree], "testParam")
        dataJagNones = JaggedArray([twoByTwo, twoByOne, threeByThree], "testParam")
        dataDict = np.array([{"bar": 2, "baz": 3}, {"foo": 4, "baz": 6}, {"foo": 7, "bar": 8}])
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

        # put some big data in an HDF5 attribute. This will exercise the code that pulls such attributes into a formal
        # dataset and a reference.
        self.r.p.cycle = 1
        self.r.p.timeNode = 0
        tnGroup = self.db.getH5Group(self.r)
        randomText = "this isn't a reference to another dataset"
        Database._writeAttrs(
            tnGroup["layout/serialNum"],
            tnGroup,
            {
                "fakeBigData": np.eye(8),
                "someString": randomText,
            },
        )

        dbPath = "restartDB.h5"
        db2 = Database(dbPath, "w")
        with db2:
            db2.mergeHistory(self.db, 2, 2)
            self.r.p.cycle = 1
            self.r.p.timeNode = 0
            tnGroup = db2.getH5Group(self.r)

            # this test is a little bit implementation-specific, but nice to be explicit
            self.assertEqual(
                tnGroup["layout/serialNum"].attrs["someString"],
                randomText,
            )

            # exercise the _resolveAttrs function
            attrs = Database._resolveAttrs(tnGroup["layout/serialNum"].attrs, tnGroup)
            self.assertTrue(np.array_equal(attrs["fakeBigData"], np.eye(8)))

            keys = sorted(db2.keys())
            self.assertEqual(len(keys), 4)
            self.assertEqual(keys[:3], ["/c00n00", "/c00n01", "/c01n00"])

    def test_splitDatabase(self):
        self.makeHistory()

        self.db.splitDatabase([(c, n) for c in (0, 1) for n in range(2)], "-all-iterations")

        # Closing to copy back from fast path
        self.db.close()

        with h5py.File("test_splitDatabase.h5", "r") as newDb:
            self.assertEqual(newDb["c00n00/Reactor/cycle"][()], 0)
            self.assertEqual(newDb["c00n00/Reactor/cycleLength"][()][0], 0)
            self.assertNotIn("c03n00", newDb)
            self.assertEqual(newDb.attrs["databaseVersion"], database.DB_VERSION)

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
            self.db.splitDatabase([(c, n) for c in (0, 1) for n in range(2)], "-all-iterations")

    @unittest.skipIf(GIT_EXE is None, "This test needs Git.")
    def test_grabLocalCommitHash(self):
        """Test of static method to grab a local commit hash with ARMI version."""
        # 1. test outside a Git repo
        localHash = Database.grabLocalCommitHash()
        self.assertEqual(localHash, "unknown")

        # 2. test inside an empty git repo
        try:
            code = subprocess.run(
                ["git", "init", "."],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
        except FileNotFoundError:
            print("Skipping this test because it is being run outside a git repo.")
            return

        self.assertEqual(code, 0)
        localHash = Database.grabLocalCommitHash()
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
        localHash = Database.grabLocalCommitHash()
        self.assertEqual(localHash, "thanks")

        # delete the .git directory
        code = subprocess.run(["git", "clean", "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
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
        """Test that we can read inputs from the database.

        .. test:: Save and retrieve settings from the database.
            :id: T_ARMI_DB_CS
            :tests: R_ARMI_DB_CS

        .. test:: Save and retrieve blueprints from the database.
            :id: T_ARMI_DB_BP
            :tests: R_ARMI_DB_BP
        """
        inputs = self.db.readInputsFromDB()
        self.assertEqual(len(inputs), 2)

        # settings
        self.assertGreater(len(inputs[0]), 100)
        self.assertIn("settings:", inputs[0])

        # blueprints
        self.assertGreater(len(inputs[1]), 2400)
        self.assertIn("blocks:", inputs[1])

    def test_deleting(self):
        self.assertTrue(isinstance(self.db, Database))
        del self.db
        self.assertFalse(hasattr(self, "db"))
        self.db = self.dbi.database

    def test_open(self):
        self.assertTrue(self.db.isOpen())
        with self.assertRaises(ValueError):
            self.db.open()

    def test_loadCS(self):
        cs = self.db.loadCS()
        self.assertEqual(cs["nTasks"], 1)
        self.assertEqual(cs["nCycles"], 2)

    def test_loadBlueprints(self):
        bp = self.db.loadBlueprints()
        self.assertIsNone(bp.nuclideFlags)
        self.assertEqual(len(bp.assemblies), 0)

    def test_prepRestartRun(self):
        """
        This test is based on the armiRun.yaml case that is loaded during the `setUp`
        above. In that cs, `reloadDBName` is set to 'reloadingDB.h5', `startCycle` = 1,
        and `startNode` = 2. The nonexistent 'reloadingDB.h5' must first be
        created here for this test.

        .. test:: Runs can be restarted from a snapshot.
            :id: T_ARMI_SNAPSHOT_RESTART
            :tests: R_ARMI_SNAPSHOT_RESTART
        """
        # first successfully call to prepRestartRun
        o, r = loadTestReactor(TEST_ROOT, customSettings={"reloadDBName": "reloadingDB.h5"})
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
        for cycle, node in ((cycle, node) for cycle in range(numCycles) for node in range(numNodes)):
            r.p.cycle = cycle
            r.p.timeNode = node
            r.p.cycleLength = sum(cyclesSetting[cycle]["step days"])
            r.core.p.power = ratedPower * cyclesSetting[cycle]["power fractions"][node]
            db.writeToDB(r)
        self.assertTrue(db.isOpen())
        db.close()
        self.assertFalse(db.isOpen())

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
        for cycle, node in ((cycle, node) for cycle in range(numCycles) for node in range(numNodes)):
            r.p.cycle = cycle
            r.p.timeNode = node
            r.p.cycleLength = 2000
            db.writeToDB(r)
        self.assertTrue(db.isOpen())
        db.close()
        self.assertFalse(db.isOpen())

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

        self.assertEqual(database.Layout.computeAncestors(serialNums, numChildren), expected_1)
        self.assertEqual(database.Layout.computeAncestors(serialNums, numChildren, 2), expected_2)
        self.assertEqual(database.Layout.computeAncestors(serialNums, numChildren, 3), expected_3)


class TestWriteReadDatabase(unittest.TestCase):
    """Round-trip tests that we can write/read data to and from a Database."""

    SMALL_YAML = """!include refOneBlockReactor.yaml
systems:
    core:
        grid name: core
        origin:
            x: 0.0
            y: 0.0
            z: 0.0
    sfp:
        type: sfp
        grid name: sfp
        origin:
            x: 1000.0
            y: 1000.0
            z: 1000.0
    evst:
        type: excore
        grid name: evst
        origin:
            x: 2000.0
            y: 2000.0
            z: 2000.0
grids:
    core:
      geom: hex_corners_up
      lattice map: |
        IC
      symmetry: full
    evst:
      lattice pitch:
          x: 32.0
          y: 32.0
      geom: hex
      symmetry: full
"""

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

        # copy these test files over, so we can edit them
        thisDir = self.td.destination
        yamls = glob(os.path.join(TEST_ROOT, "smallestTestReactor", "*.yaml"))
        for yam in yamls:
            safeCopy(os.path.join(TEST_ROOT, "smallestTestReactor", yam), thisDir)

        # Add an EVST to this reactor
        with open("refSmallestReactor.yaml", "w") as f:
            f.write(self.SMALL_YAML)

        self.o, self.r = loadTestReactor(thisDir, inputFileName="armiRunSmallest.yaml")
        self.dbi = DatabaseInterface(self.r, self.o.cs)
        self.dbi.initDB(fName=f"{self._testMethodName}.h5")
        self.db: Database = self.dbi.database

    def tearDown(self):
        self.db.close()
        self.td.__exit__(None, None, None)

    def test_readWriteRoundTrip(self):
        """Test DB some round tripping, writing some data to a DB, then reading from it.

        In particular, we test some parameters on the reactor, core, and blocks. And we move an
        assembly from the core to an EVST between timenodes, and test that worked.
        """
        # put some data in the DB, for timenode 0
        self.r.p.cycle = 0
        self.r.p.timeNode = 0
        self.r.core.p.keff = 0.99
        b = self.r.core.getFirstBlock()
        b.p.power = 12345.6

        self.db.writeToDB(self.r)

        # put some data in the DB, for timenode 1
        self.r.p.timeNode = 1
        self.r.core.p.keff = 1.01

        # move the assembly from the core to the EVST
        a = self.r.core.getFirstAssembly()
        loc = self.r.excore.evst.spatialGrid[(0, 0, 0)]
        self.r.core.remove(a)
        self.r.excore.evst.add(a, loc)

        self.db.writeToDB(self.r)

        # close the DB
        self.db.close()

        # open the DB and verify, the first timenode
        with Database(self.db.fileName, "r") as db:
            r0 = db.load(0, 0, allowMissing=True)
            self.assertEqual(r0.p.cycle, 0)
            self.assertEqual(r0.p.timeNode, 0)
            self.assertEqual(r0.core.p.keff, 0.99)

            # check the types of the data model objects
            self.assertTrue(isinstance(r0, Reactor))
            self.assertTrue(isinstance(r0.core, Core))
            self.assertTrue(isinstance(r0.excore, ExcoreCollection))
            self.assertTrue(isinstance(r0.excore.evst, ExcoreStructure))
            self.assertTrue(isinstance(r0.excore.sfp, SpentFuelPool))

            # Prove our one special block is in the core
            self.assertEqual(len(r0.core.getChildren()), 1)
            b0 = r0.core.getFirstBlock()
            self.assertEqual(b0.p.power, 12345.6)

            # the ex-core structures should be empty
            self.assertEqual(len(r0.excore["sfp"].getChildren()), 0)
            self.assertEqual(len(r0.excore["evst"].getChildren()), 0)

        # open the DB and verify, the second timenode
        with Database(self.db.fileName, "r") as db:
            r1 = db.load(0, 1, allowMissing=True)
            self.assertEqual(r1.p.cycle, 0)
            self.assertEqual(r1.p.timeNode, 1)
            self.assertEqual(r1.core.p.keff, 1.01)

            # check the types of the data model objects
            self.assertTrue(isinstance(r1, Reactor))
            self.assertTrue(isinstance(r1.core, Core))
            self.assertTrue(isinstance(r1.excore, ExcoreCollection))
            self.assertTrue(isinstance(r1.excore.evst, ExcoreStructure))
            self.assertTrue(isinstance(r1.excore.sfp, SpentFuelPool))

            # Prove our one special block is NOT in the core, or the SFP
            self.assertEqual(len(r1.core.getChildren()), 0)
            self.assertEqual(len(r1.excore["sfp"].getChildren()), 0)
            self.assertEqual(len(r1.excore.sfp.getChildren()), 0)

            # Prove our one special block is in the EVST
            evst = r1.excore["evst"]
            self.assertEqual(len(evst.getChildren()), 1)
            b1 = evst.getChildren()[0].getChildren()[0]
            self.assertEqual(b1.p.power, 12345.6)

    def test_badData(self):
        # create a DB to be modified
        self.db.writeToDB(self.r)
        self.db.close()

        # modify the HDF5 file to corrupt a dataset
        with h5py.File(self.db.fileName, "r+") as hf:
            circleGroup = hf["c00n00"]["Circle"]
            circleMass = np.array(circleGroup["massHmBOL"][()])
            badData = circleMass[:-1]
            del circleGroup["massHmBOL"]
            circleGroup.create_dataset("massHmBOL", data=badData)

        with self.assertRaises(ValueError):
            with Database(self.db.fileName, "r") as db:
                _r = db.load(0, 0, allowMissing=True)


class TestSimplestDatabaseItems(unittest.TestCase):
    """The tests here are simple, direct tests of Database, that don't need a DatabaseInterface or Reactor."""

    def test_open(self):
        dbPath = "test_open.h5"
        db = Database(dbPath, "w")

        self.assertFalse(db.isOpen())
        db._permission = "mock"
        with self.assertRaises(ValueError):
            db.open()
