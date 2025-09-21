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
"""Tests of the Database Interface."""

import os
import types
import unittest

import h5py
import numpy as np
from numpy.testing import assert_allclose, assert_equal

from armi import __version__ as version
from armi import interfaces, runLog, settings
from armi.bookkeeping.db.database import Database
from armi.bookkeeping.db.databaseInterface import DatabaseInterface
from armi.cases import case
from armi.context import PROJECT_ROOT
from armi.physics.neutronics.settings import CONF_LOADING_FILE
from armi.reactor import grids
from armi.reactor.flags import Flags
from armi.testing import loadTestReactor, reduceTestReactorRings
from armi.tests import TEST_ROOT
from armi.utils import directoryChangers


def getSimpleDBOperator(cs):
    """
    Return a very simple operator that covers most of the database interactions.

    Notes
    -----
    This reactor has only 1 assembly with 1 type of block.
    It's used to make the db unit tests run very quickly.
    """
    newSettings = {}
    newSettings[CONF_LOADING_FILE] = "smallestTestReactor/refSmallestReactor.yaml"
    newSettings["verbosity"] = "important"
    newSettings["db"] = True
    newSettings["runType"] = "Standard"
    newSettings["nCycles"] = 1
    cs = cs.modified(newSettings=newSettings)
    genDBCase = case.Case(cs)
    runLog.setVerbosity("info")

    o = genDBCase.initializeOperator()
    o.interfaces = [interface for interface in o.interfaces if interface.name in ["database", "main"]]

    return o, cs


class MockInterface(interfaces.Interface):
    name = "mockInterface"

    def __init__(self, r, cs, action=None):
        interfaces.Interface.__init__(self, r, cs)
        self.action = action

    def interactEveryNode(self, cycle, node):
        self.action(cycle, node)


class TestDatabaseInterfaceBOL(unittest.TestCase):
    """Test the DatabaseInterface class at the BOL."""

    def test_interactBOL(self):
        """This test is in its own class, because of temporary directory issues."""
        with directoryChangers.TemporaryDirectoryChanger():
            self.o, self.r = loadTestReactor(TEST_ROOT, inputFileName="smallestTestReactor/armiRunSmallest.yaml")
            self.dbi = DatabaseInterface(self.r, self.o.cs)

            dbName = f"{self._testMethodName}.h5"
            self.dbi.initDB(fName=dbName)
            self.db: Database = self.dbi.database
            self.stateRetainer = self.r.retainState().__enter__()
            self.assertIsNotNone(self.dbi._db)
            self.dbi.interactBOL()
            self.dbi.closeDB()
            self.dbi._db = None
            self.assertIsNone(self.dbi._db)

            if os.path.exists(dbName):
                os.remove(dbName)


class TestDatabaseInterface(unittest.TestCase):
    """Tests for the DatabaseInterface class."""

    def setUp(self):
        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()
        self.o, self.r = loadTestReactor(TEST_ROOT, inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        self.dbi = DatabaseInterface(self.r, self.o.cs)
        self.dbi.initDB(fName=self._testMethodName + ".h5")
        self.db: Database = self.dbi.database
        self.stateRetainer = self.r.retainState().__enter__()

    def tearDown(self):
        self.db.close()
        self.stateRetainer.__exit__()
        self.td.__exit__(None, None, None)
        # test_interactBOL leaves behind some dirt (accessible after db close) that the
        # TempDirChanger is not catching
        bolDirt = [
            os.path.join(PROJECT_ROOT, "armiRun.h5"),
            os.path.join(PROJECT_ROOT, "armiRunSmallest.h5"),
        ]
        for dirt in bolDirt:
            if os.path.exists(dirt):
                os.remove(dirt)

    def test_distributable(self):
        self.assertEqual(self.dbi.distributable(), 4)
        self.dbi.interactDistributeState()
        self.assertEqual(self.dbi.distributable(), 4)

    def test_demonstrateWritingInteractions(self):
        """Test what nodes are written to the database during the interaction calls."""
        self.o.cs["burnSteps"] = 2  # make test insensitive to burn steps
        r = self.r

        # BOC/BOL doesn't write anything
        r.p.cycle, r.p.timeNode = 0, 0
        self.assertFalse(self.dbi.database.hasTimeStep(0, 0))
        self.dbi.interactBOL()
        self.assertFalse(self.dbi.database.hasTimeStep(0, 0))
        self.dbi.interactBOC(0)
        self.assertFalse(self.dbi.database.hasTimeStep(0, 0))

        # but the first time node does
        self.dbi.interactEveryNode(0, 0)
        self.assertTrue(self.dbi.database.hasTimeStep(0, 0))

        # EOC 0 shouldn't write, its written by last time node
        r.p.cycle, r.p.timeNode = 0, self.o.cs["burnSteps"]
        self.assertFalse(self.dbi.database.hasTimeStep(r.p.cycle, r.p.timeNode))
        self.dbi.interactEOC(r.p.cycle)
        self.assertFalse(self.dbi.database.hasTimeStep(r.p.cycle, r.p.timeNode))

        # The last node of the step should write though
        self.assertFalse(self.dbi.database.hasTimeStep(r.p.cycle, r.p.timeNode))
        self.dbi.interactEveryNode(r.p.cycle, r.p.timeNode)
        self.assertTrue(self.dbi.database.hasTimeStep(r.p.cycle, r.p.timeNode))

        # EOL should also write, but lets write last time node first
        r.p.cycle, r.p.timeNode = self.o.cs["nCycles"] - 1, self.o.cs["burnSteps"]
        self.assertFalse(self.dbi.database.hasTimeStep(r.p.cycle, r.p.timeNode))
        self.dbi.interactEveryNode(r.p.cycle, r.p.timeNode)
        self.assertTrue(self.dbi.database.hasTimeStep(r.p.cycle, r.p.timeNode))

        # now write EOL
        self.assertFalse(self.dbi.database.hasTimeStep(r.p.cycle, r.p.timeNode, "EOL"))
        self.dbi.interactEOL()  # this also saves and closes db

        # reopen db to show EOL is written
        with Database(self._testMethodName + ".h5", "r") as db:
            self.assertTrue(db.hasTimeStep(r.p.cycle, r.p.timeNode, "EOL"))
            # and confirm that last time node is still there/separate
            self.assertTrue(db.hasTimeStep(r.p.cycle, r.p.timeNode))

    def test_interactEveryNodeReturnTightCoupling(self):
        """Test that the DB is NOT written to if cs["tightCoupling"] = True."""
        self.o.cs["tightCoupling"] = True
        self.dbi.interactEveryNode(0, 0)
        self.assertFalse(self.dbi.database.hasTimeStep(0, 0))

    def test_timeNodeLoop_tightCoupling(self):
        """Test that database is written out after the coupling loop has completed."""
        # clear out interfaces (no need to run physics) but leave database
        self.o.interfaces = [self.dbi]
        self.o.cs["tightCoupling"] = True
        self.assertFalse(self.dbi._db.hasTimeStep(0, 0))
        self.o._timeNodeLoop(0, 0)
        self.assertTrue(self.dbi._db.hasTimeStep(0, 0))

    def test_syncDbAfterWrite(self):
        """
        Test to ensure that the fast-path database is copied to working
        directory at every time node when ``syncDbAfterWrite`` is ``True``.
        """
        r = self.r

        self.o.cs["syncDbAfterWrite"] = True
        self.o.cs["burnSteps"] = 2  # make test insensitive to burn steps

        self.dbi.interactBOL()
        self.assertFalse(os.path.exists(self.dbi.database.fileName))

        # Go through a few time nodes to ensure appending is working
        for timeNode in range(self.o.cs["burnSteps"]):
            r.p.cycle = 0
            r.p.timeNode = timeNode
            self.dbi.interactEveryNode(r.p.cycle, r.p.timeNode)

            # The file should have been copied to working directory
            self.assertTrue(os.path.exists(self.dbi.database.fileName))

            # The copied file should have the newest time node
            with Database(self.dbi.database.fileName, "r") as db:
                for tn in range(timeNode + 1):
                    self.assertTrue(db.hasTimeStep(r.p.cycle, tn))

            # The in-memory database should have been reloaded properly
            for tn in range(timeNode + 1):
                self.assertTrue(self.dbi.database.hasTimeStep(r.p.cycle, tn))

        # Make sure EOL runs smoothly
        self.dbi.interactEOL()
        self.assertTrue(os.path.exists(self.dbi.database.fileName))

    def test_noSyncDbAfterWrite(self):
        """
        Test to ensure that the fast-path database is NOT copied to working
        directory at every time node when ``syncDbAfterWrite`` is ``False``.
        """
        self.o.cs["syncDbAfterWrite"] = False

        self.dbi.interactBOL()
        self.assertFalse(os.path.exists(self.dbi.database.fileName))
        self.dbi.interactEveryNode(0, 0)
        self.assertFalse(os.path.exists(self.dbi.database.fileName))
        self.dbi.interactEOL()
        self.assertTrue(os.path.exists(self.dbi.database.fileName))

    def test_writeDBFromDBLoadSameDir(self):
        """
        Test to ensure that a reactor loaded from a database can be written to a
        working database file (one that has case settings and blueprints if applicable).
        """
        # Write this reactor to a database file.
        dbi = DatabaseInterface(self.r, self.o.cs)
        dbi.initDB(fName="testDB1.h5")
        db = dbi.database
        db.writeToDB(self.r)
        db.close()

        # Now load the db again
        with Database("testDB1.h5", "r") as db:
            cs2 = db.loadCS()
            r2 = db.load(0, 0, cs=cs2)

        # Now write this db to this folder
        dbi = DatabaseInterface(r2, cs2)
        dbi.initDB(fName="testDB2.h5")
        db = dbi.database
        db.writeToDB(r2)
        db.close()

        # Now load this db. It should load
        with Database("testDB2.h5", "r") as db:
            cs3 = db.loadCS()
            _ = db.load(0, 0, cs=cs3)

    def test_writeDBFromDBLoadDifDir(self):
        """
        Test to ensure that a reactor loaded from a database can be written to a
        working database file (one that has case settings and blueprints if applicable).

        The directory is changed between writing and loading.
        """
        # Write this reactor to a database file.
        dbi = DatabaseInterface(self.r, self.o.cs)
        dbi.initDB(fName="testDB1.h5")
        db = dbi.database
        db.writeToDB(self.r)
        db.close()

        # Let's move to a different folder
        os.makedirs("sub", exist_ok=True)
        os.chdir("sub")

        # Now load the db again
        with Database(os.path.join(os.pardir, "testDB1.h5"), "r") as db:
            cs2 = db.loadCS()
            r2 = db.load(0, 0, cs=cs2)

        # Now write this db to this folder
        dbi = DatabaseInterface(r2, cs2)
        dbi.initDB(fName="testDB2.h5")
        db = dbi.database
        db.writeToDB(r2)
        db.close()

        # Now load this db. It should load
        with Database("testDB2.h5", "r") as db:
            cs3 = db.loadCS()
            _ = db.load(0, 0, cs=cs3)


class TestDatabaseWriter(unittest.TestCase):
    def setUp(self):
        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()
        cs = settings.Settings(os.path.join(TEST_ROOT, "armiRun.yaml"))
        cs = cs.modified(newSettings={"power": 0.0, "powerDensity": 9e4})
        self.o, cs = getSimpleDBOperator(cs)
        self.r = self.o.r
        self.stateRetainer = self.r.retainState().__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)
        self.stateRetainer.__exit__()

    def test_writeSystemAttributes(self):
        """Test the writeSystemAttributes method.

        .. test:: Validate that we can directly write system attributes to a database file.
            :id: T_ARMI_DB_QA0
            :tests: R_ARMI_DB_QA
        """
        with h5py.File("test_writeSystemAttributes.h5", "w") as h5:
            Database.writeSystemAttributes(h5)

        with h5py.File("test_writeSystemAttributes.h5", "r") as h5:
            self.assertIn("user", h5.attrs)
            self.assertIn("python", h5.attrs)
            self.assertIn("armiLocation", h5.attrs)
            self.assertIn("startTime", h5.attrs)
            self.assertIn("machines", h5.attrs)
            self.assertIn("platform", h5.attrs)
            self.assertIn("hostname", h5.attrs)
            self.assertIn("platformRelease", h5.attrs)
            self.assertIn("platformVersion", h5.attrs)
            self.assertIn("platformArch", h5.attrs)

    def test_metaData_endSuccessfully(self):
        """Test databases have the correct metadata in them.

        .. test:: Validate that databases have system attributes written to them during the usual workflow.
            :id: T_ARMI_DB_QA1
            :tests: R_ARMI_DB_QA
        """
        # the power should start at zero
        self.assertEqual(self.r.core.p.power, 0)

        def goodMethod(cycle, node):
            pass

        self.o.interfaces.append(MockInterface(self.o.r, self.o.cs, goodMethod))
        with self.o:
            self.o.operate()

        self.assertEqual(0, self.r.p.cycle)
        self.assertEqual(2, self.r.p.timeNode)

        with h5py.File(self.o.cs.caseTitle + ".h5", "r") as h5:
            self.assertTrue(h5.attrs["successfulCompletion"])
            self.assertEqual(h5.attrs["version"], version)

            self.assertIn("caseTitle", h5.attrs)
            self.assertIn("settings", h5["inputs"])
            self.assertIn("blueprints", h5["inputs"])

            # validate system attributes
            self.assertIn("user", h5.attrs)
            self.assertIn("python", h5.attrs)
            self.assertIn("armiLocation", h5.attrs)
            self.assertIn("startTime", h5.attrs)
            self.assertIn("machines", h5.attrs)
            self.assertIn("platform", h5.attrs)
            self.assertIn("hostname", h5.attrs)
            self.assertIn("platformRelease", h5.attrs)
            self.assertIn("platformVersion", h5.attrs)
            self.assertIn("platformArch", h5.attrs)

        # after operating, the power will be greater than zero
        self.assertGreater(self.r.core.p.power, 1e9)

    def test_metaDataEndFail(self):
        def failMethod(cycle, node):
            if cycle == 0 and node == 1:
                raise Exception("forcing failure")

        self.o.interfaces.append(MockInterface(self.o.r, self.o.cs, failMethod))

        with self.assertRaises(Exception):
            with self.o:
                self.o.operate()

        self.assertEqual(0, self.r.p.cycle)
        self.assertEqual(1, self.r.p.timeNode)

        with h5py.File(self.o.cs.caseTitle + ".h5", "r") as h5:
            self.assertFalse(h5.attrs["successfulCompletion"])
            self.assertEqual(h5.attrs["version"], version)
            self.assertIn("caseTitle", h5.attrs)

    def test_getHistory(self):
        expectedFluxes0 = {}
        expectedFluxes7 = {}

        def setFluxAwesome(cycle, node):
            for bi, b in enumerate(self.r.core.iterBlocks()):
                b.p.flux = 1e6 * bi + 1e3 * cycle + node
                if bi == 0:
                    expectedFluxes0[cycle, node] = b.p.flux
                if bi == 7:
                    expectedFluxes7[cycle, node] = b.p.flux

        # use as attribute so it is accessible within getFluxAwesome
        self.called = False

        def getFluxAwesome(cycle, node):
            if cycle != 0 or node != 2:
                return

            b0 = next(self.r.core.iterBlocks())

            db = self.o.getInterface("database")._db

            # we are now in cycle 1, node 2 ... AFTER setFluxAwesome, but BEFORE writeToDB
            actualFluxes0 = db.getHistory(b0)["flux"]
            self.assertEqual(expectedFluxes0, actualFluxes0)
            self.called = True

        self.o.interfaces.insert(0, MockInterface(self.o.r, self.o.cs, setFluxAwesome))
        self.o.interfaces.insert(1, MockInterface(self.o.r, self.o.cs, getFluxAwesome))

        with self.o:
            self.o.operate()

        self.assertTrue(self.called)

    def test_getHistoryByLocation(self):
        def setFluxAwesome(cycle, node):
            for bi, b in enumerate(self.r.core.iterBlocks()):
                b.p.flux = 1e6 * bi + 1e3 * cycle + node

        def getFluxAwesome(cycle, node):
            if cycle != 1 or node != 2:
                return

            b = next(self.r.core.iterBlocks())

            db = self.o.getInterface("database").database

            # we are now in cycle 1, node 2 ... AFTER setFluxAwesome
            _fluxes = db.getHistory(b, params=["flux"])

        self.o.interfaces.append(MockInterface(self.o.r, self.o.cs, setFluxAwesome))
        self.o.interfaces.append(MockInterface(self.o.r, self.o.cs, getFluxAwesome))

        with self.o:
            self.o.operate()

        with h5py.File(self.o.cs.caseTitle + ".h5", "r") as h5:
            self.assertEqual(h5.attrs["version"], version)


class TestDatabaseReading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = directoryChangers.TemporaryDirectoryChanger()
        cls.td.__enter__()

        # The database writes the settings object to the DB rather than the original input file.
        # This allows settings to be changed in memory like this and survive for testing.
        newSettings = {"verbosity": "extra"}
        cls.nCycles = 2
        newSettings["nCycles"] = cls.nCycles
        newSettings["burnSteps"] = 2
        o, r = loadTestReactor(customSettings=newSettings)
        reduceTestReactorRings(r, o.cs, 3)

        o.interfaces = [i for i in o.interfaces if isinstance(i, (DatabaseInterface))]
        dbi = o.getInterface("database")
        dbi.enabled(True)
        dbi.initDB()  # Main Interface normally does this

        # update a few parameters
        def writeFlux(cycle, node):
            for bi, b in enumerate(o.r.core.iterBlocks()):
                b.p.flux = 1e6 * bi + cycle * 100 + node
                b.p.mgFlux = np.repeat(b.p.flux / 33, 33)

        o.interfaces.insert(0, MockInterface(o.r, o.cs, writeFlux))
        with o:
            o.operate()

        cls.cs = o.cs
        cls.bp = o.r.blueprints
        cls.dbName = o.cs.caseTitle + ".h5"

        # needed for test_readWritten
        cls.r = o.r

    @classmethod
    def tearDownClass(cls):
        cls.td.__exit__(None, None, None)
        del cls.r
        cls.r = None

    def _fullCoreSizeChecker(self, r):
        self.assertEqual(r.core.numRings, 3)
        self.assertEqual(r.p.cycle, 0)
        self.assertEqual(len(r.core.assembliesByName), 19)
        self.assertEqual(len(r.core.circularRingList), 0)
        self.assertEqual(len(r.core.blocksByName), 95)

    def test_loadReadOnly(self):
        with Database(self.dbName, "r") as db:
            r = db.loadReadOnly(0, 0)

            # now show we can no longer edit those parameters
            with self.assertRaises(RuntimeError):
                r.core.p.keff = 0.99

            b = r.core.getFirstBlock()
            with self.assertRaises(RuntimeError):
                b.p.power = 432.1

            for c in b:
                self.assertGreater(c.getVolume(), 0)

    def test_growToFullCore(self):
        with Database(self.dbName, "r") as db:
            r = db.load(0, 0, allowMissing=True)

        # test partial core values
        self.assertEqual(r.core.numRings, 3)
        self.assertEqual(r.p.cycle, 0)
        self.assertEqual(len(r.core.assembliesByName), 7)
        self.assertEqual(len(r.core.circularRingList), 0)
        self.assertEqual(len(r.core.blocksByName), 35)

        r.core.growToFullCore(None)
        self._fullCoreSizeChecker(r)

    def test_growToFullCoreWithCS(self):
        with Database(self.dbName, "r") as db:
            r = db.load(0, 0, allowMissing=True)

        r.core.growToFullCore(self.cs)
        self._fullCoreSizeChecker(r)

    def test_growToFullCoreFromFactory(self):
        from armi.bookkeeping.db import databaseFactory

        db = databaseFactory(self.dbName, "r")
        with db:
            r = db.load(0, 0, allowMissing=True)

        r.core.growToFullCore(None)
        self._fullCoreSizeChecker(r)

    def test_growToFullCoreFromFactoryWithCS(self):
        from armi.bookkeeping.db import databaseFactory

        db = databaseFactory(self.dbName, "r")
        with db:
            r = db.load(0, 0, allowMissing=True)

        r.core.growToFullCore(self.cs)
        self._fullCoreSizeChecker(r)

    def test_readWritten(self):
        with Database(self.dbName, "r") as db:
            r2 = db.load(0, 0, self.cs)

        for a1, a2 in zip(self.r.core, r2.core):
            # assemblies assign a name based on assemNum at initialization
            self.assertEqual(a1.name, a2.name)
            assert_equal(a1.spatialLocator.indices, a2.spatialLocator.indices)
            self.assertEqual(a1.p.assemNum, a2.p.assemNum)
            self.assertEqual(a1.p.serialNum, a2.p.serialNum)

            for b1, b2 in zip(a1, a2):
                # blocks assign a name based on assemNum at initialization
                self.assertEqual(b1.name, b2.name)
                assert_equal(b1.spatialLocator.indices, b2.spatialLocator.indices)
                self.assertEqual(b1.p.serialNum, b2.p.serialNum)

                for c1, c2 in zip(sorted(b1), sorted(b2)):
                    self.assertEqual(c1.name, c2.name)
                    if isinstance(c1.spatialLocator, grids.MultiIndexLocation):
                        assert_equal(
                            np.array(c1.spatialLocator.indices),
                            np.array(c2.spatialLocator.indices),
                        )
                    else:
                        assert_equal(c1.spatialLocator.indices, c2.spatialLocator.indices)
                    self.assertEqual(c1.p.serialNum, c2.p.serialNum)

                # volume is pretty difficult to get right. it relies upon linked dimensions
                v1 = b1.getVolume()
                v2 = b2.getVolume()
                assert_allclose(v1, v2)
                self.assertEqual(b1.p.serialNum, b2.p.serialNum)

            self.assertEqual(
                self.r.core.childrenByLocator[0, 0, 0].p.serialNum,
                r2.core.childrenByLocator[0, 0, 0].p.serialNum,
            )

    def test_readWithoutInputs(self):
        with Database(self.dbName, "r") as db:
            r2 = db.load(0, 0)

        for b1, b2 in zip(self.r.core.iterBlocks(), r2.core.iterBlocks()):
            for c1, c2 in zip(sorted(b1), sorted(b2)):
                self.assertEqual(c1.name, c2.name)

        for bi, b in enumerate(r2.core.iterBlocks()):
            assert_allclose(b.p.flux, 1e6 * bi)

    def test_variousTypesWork(self):
        with Database(self.dbName, "r") as db:
            r2 = db.load(1, 1)

        b1 = self.r.core.getFirstBlock(Flags.FUEL)
        b2 = r2.core.getFirstBlock(Flags.FUEL)

        self.assertIsInstance(b1.p.mgFlux, np.ndarray)
        self.assertIsInstance(b2.p.mgFlux, np.ndarray)
        assert_allclose(b1, b2)

        c1 = b1.getComponent(Flags.FUEL)
        c2 = b2.getComponent(Flags.FUEL)

        for i, v1 in enumerate(c1.p.numberDensities):
            self.assertAlmostEqual(v1, c2.p.numberDensities[i])

    def test_timesteps(self):
        with Database(self.dbName, "r") as db:
            # build time steps in the DB file
            timesteps = []
            for cycle in range(self.nCycles):
                for bStep in range(3):
                    timesteps.append(f"/c0{cycle}n0{bStep}")
            timesteps.append("/c01n02EOL")

            # verify the timesteps are correct, including the EOL
            self.assertEqual(list(db.keys()), timesteps)


class TestBadName(unittest.TestCase):
    def test_badDBName(self):
        cs = settings.Settings(os.path.join(TEST_ROOT, "armiRun.yaml"))
        cs = cs.modified(newSettings={"reloadDBName": "aRmIRuN.h5"})

        dbi = DatabaseInterface(None, cs)
        with self.assertRaises(ValueError):
            # an error should be raised when the database loaded from
            # has the same name as the run to avoid overwriting.
            dbi.initDB()


class TestStandardFollowOn(unittest.TestCase):
    """Tests related to doing restart runs (loading from DB with Standard operator)."""

    def _getOperatorThatChangesVariables(self, cs):
        """
        Return an operator that advances time so that restart runs can be tested.

        Notes
        -----
        Ensures that parameters are consistent between Standard runs and restart runs.
        """
        o, cs = getSimpleDBOperator(cs)

        mock = MockInterface(o.r, o.cs, None)

        def interactEveryNode(self, cycle, node):
            # Could use just += 1 but this will show more errors since it is less
            # susceptible to cancellation of errors off by one.
            self.r.p.time += self.r.p.timeNode + 1

        # Magic to change the method only on this instance of the class.
        mock.interactEveryNode = types.MethodType(interactEveryNode, mock)

        # insert 1 before the database interface so that changes are written to db.
        o.interfaces.insert(1, mock)
        return o

    def test_standardRestart(self):
        self.td = directoryChangers.TemporaryDirectoryChanger()
        with self.td:
            # make DB to load from
            o = self._getOperatorThatChangesVariables(settings.Settings(os.path.join(TEST_ROOT, "armiRun.yaml")))
            with o:
                o.operate()
                firstEndTime = o.r.p.time
                self.assertNotEqual(firstEndTime, 0, "Time should have advanced by the end of the run.")

            # run standard restart case
            loadDB = "loadFrom.h5"
            os.rename("armiRun.h5", loadDB)
            cs = settings.Settings(os.path.join(TEST_ROOT, "armiRun.yaml"))
            newSettings = {}
            newSettings["loadStyle"] = "fromDB"
            newSettings["reloadDBName"] = loadDB
            newSettings["startCycle"] = 0
            newSettings["startNode"] = 1
            cs = cs.modified(newSettings=newSettings)
            o = self._getOperatorThatChangesVariables(cs)

            # the interact BOL has historically failed due to trying to write inputs
            # which are already in the DB from the _mergeStandardRunDB call
            with o:
                o.operate()
                self.assertEqual(
                    firstEndTime,
                    o.r.p.time,
                    "End time should have been the same for the restart run.\n"
                    "First end time: {},\nSecond End time: {}".format(firstEndTime, o.r.p.time),
                )
