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
r""" Tests of the Database Interface"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-method-argument,import-outside-toplevel
import os
import types
import unittest

import h5py
import numpy
from numpy.testing import assert_allclose, assert_equal

from armi import __version__ as version
from armi import interfaces
from armi import runLog
from armi import settings
from armi.bookkeeping.db.database3 import Database3
from armi.bookkeeping.db.databaseInterface import DatabaseInterface
from armi.cases import case
from armi.reactor import grids
from armi.reactor.flags import Flags
from armi.reactor.tests.test_reactors import loadTestReactor, reduceTestReactorRings
from armi.settings.fwSettings.databaseSettings import CONF_FORCE_DB_PARAMS
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
    newSettings["loadingFile"] = "refOneBlockReactor.yaml"
    newSettings["verbosity"] = "important"
    newSettings["db"] = True
    newSettings["runType"] = "Standard"
    newSettings["geomFile"] = "geom1Assem.xml"
    newSettings["nCycles"] = 1
    newSettings[CONF_FORCE_DB_PARAMS] = ["baseBu"]
    cs = cs.modified(newSettings=newSettings)
    genDBCase = case.Case(cs)
    settings.setMasterCs(cs)
    runLog.setVerbosity("info")

    o = genDBCase.initializeOperator()
    o.interfaces = [
        interface
        for interface in o.interfaces
        if interface.name in ["database", "main"]
    ]

    return o, cs


class MockInterface(interfaces.Interface):
    name = "mockInterface"

    def __init__(self, r, cs, action=None):
        interfaces.Interface.__init__(self, r, cs)
        self.action = action

    def interactEveryNode(self, cycle, node):
        self.r.core.getFirstBlock().p.baseBu = 5.0
        self.action(cycle, node)


class TestDatabaseInterface(unittest.TestCase):
    r"""Tests for the DatabaseInterface class"""

    def setUp(self):
        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()
        self.o, self.r = loadTestReactor(TEST_ROOT)

        self.dbi = DatabaseInterface(self.r, self.o.cs)
        self.dbi.initDB(fName=self._testMethodName + ".h5")
        self.db: db.Database3 = self.dbi.database
        self.stateRetainer = self.r.retainState().__enter__()

    def tearDown(self):
        self.db.close()
        self.stateRetainer.__exit__()
        self.td.__exit__(None, None, None)

    def test_interactEveryNodeReturn(self):
        """test that the DB is NOT written to if cs["numCoupledIterations"] != 0"""
        self.o.cs["numCoupledIterations"] = 1
        self.dbi.interactEveryNode(0, 0)
        self.assertFalse(self.dbi.database.hasTimeStep(0, 0))

    def test_interactBOL(self):
        self.assertIsNotNone(self.dbi._db)
        self.dbi.interactBOL()

        self.dbi._db = None
        self.assertIsNone(self.dbi._db)
        self.dbi.interactBOL()
        self.assertIsNotNone(self.dbi._db)

    def test_distributable(self):
        self.assertEqual(self.dbi.distributable(), 4)
        self.dbi.interactDistributeState()
        self.assertEqual(self.dbi.distributable(), 4)

    def test_timeNodeLoop_numCoupledIterations(self):
        """test that database is written out after the coupling loop has completed"""
        # clear out interfaces (no need to run physics) but leave database
        self.o.interfaces = [self.dbi]
        self.o.cs["numCoupledIterations"] = 1
        self.assertFalse(self.dbi._db.hasTimeStep(0, 0))
        self.o._timeNodeLoop(0, 0)
        self.assertTrue(self.dbi._db.hasTimeStep(0, 0))


class TestDatabaseWriter(unittest.TestCase):
    def setUp(self):
        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()
        cs = settings.Settings(os.path.join(TEST_ROOT, "armiRun.yaml"))
        self.o, cs = getSimpleDBOperator(cs)
        self.r = self.o.r

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_metaData_endSuccessfully(self):
        def goodMethod(cycle, node):  # pylint: disable=unused-argument
            pass

        self.o.interfaces.append(MockInterface(self.o.r, self.o.cs, goodMethod))
        with self.o:
            self.o.operate()

        self.assertEqual(0, self.r.p.cycle)
        self.assertEqual(2, self.r.p.timeNode)

        with h5py.File(self.o.cs.caseTitle + ".h5", "r") as h5:
            self.assertTrue(h5.attrs["successfulCompletion"])
            self.assertEqual(h5.attrs["version"], version)
            self.assertIn("user", h5.attrs)
            self.assertIn("python", h5.attrs)
            self.assertIn("armiLocation", h5.attrs)
            self.assertIn("startTime", h5.attrs)
            self.assertIn("machines", h5.attrs)
            self.assertIn("caseTitle", h5.attrs)
            self.assertIn("geomFile", h5["inputs"])
            self.assertIn("settings", h5["inputs"])
            self.assertIn("blueprints", h5["inputs"])
            self.assertIn("baseBu", h5["c00n02/HexBlock"])

    def test_metaDataEndFail(self):
        def failMethod(cycle, node):  # pylint: disable=unused-argument
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

        def setFluxAwesome(cycle, node):  # pylint: disable=unused-argument
            for bi, b in enumerate(self.r.core.getBlocks()):
                b.p.flux = 1e6 * bi + 1e3 * cycle + node
                if bi == 0:
                    expectedFluxes0[cycle, node] = b.p.flux
                if bi == 7:
                    expectedFluxes7[cycle, node] = b.p.flux

        # use as attribute so it is accessible within getFluxAwesome
        self.called = False

        def getFluxAwesome(cycle, node):  # pylint: disable=unused-argument
            if cycle != 0 or node != 2:
                return

            blocks = self.r.core.getBlocks()
            b0 = blocks[0]

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
        def setFluxAwesome(cycle, node):  # pylint: disable=unused-argument
            for bi, b in enumerate(self.r.core.getBlocks()):
                b.p.flux = 1e6 * bi + 1e3 * cycle + node

        def getFluxAwesome(cycle, node):  # pylint: disable=unused-argument
            if cycle != 1 or node != 2:
                return

            blocks = self.r.core.getBlocks()
            b = blocks[0]

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

        # The database writes the settings object to the DB rather
        # than the original input file. This allows settings to be
        # changed in memory like this and survive for testing.
        newSettings = {"verbosity": "extra"}
        newSettings["nCycles"] = 2
        newSettings["burnSteps"] = 2
        o, r = loadTestReactor(customSettings=newSettings)
        reduceTestReactorRings(r, o.cs, 3)

        settings.setMasterCs(o.cs)

        o.interfaces = [i for i in o.interfaces if isinstance(i, (DatabaseInterface))]
        dbi = o.getInterface("database")
        dbi.enabled(True)
        dbi.initDB()  # Main Interface normally does this

        # update a few parameters
        def writeFlux(cycle, node):
            for bi, b in enumerate(o.r.core.getBlocks()):
                b.p.flux = 1e6 * bi + cycle * 100 + node
                b.p.mgFlux = numpy.repeat(b.p.flux / 33, 33)

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
        """TODO"""
        self.assertEqual(r.core.numRings, 3)
        self.assertEqual(r.p.cycle, 0)
        self.assertEqual(len(r.core.assembliesByName), 19)
        self.assertEqual(len(r.core.circularRingList), 0)
        self.assertEqual(len(r.core.blocksByName), 95)

    def test_growToFullCore(self):
        with Database3(self.dbName, "r") as db:
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
        with Database3(self.dbName, "r") as db:
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
        with Database3(self.dbName, "r") as db:
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
                            numpy.array(c1.spatialLocator.indices),
                            numpy.array(c2.spatialLocator.indices),
                        )
                    else:
                        assert_equal(
                            c1.spatialLocator.indices, c2.spatialLocator.indices
                        )
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
        with Database3(self.dbName, "r") as db:
            r2 = db.load(0, 0)

        for b1, b2 in zip(self.r.core.getBlocks(), r2.core.getBlocks()):
            for c1, c2 in zip(sorted(b1), sorted(b2)):
                self.assertEqual(c1.name, c2.name)

        for bi, b in enumerate(r2.core.getBlocks()):
            assert_allclose(b.p.flux, 1e6 * bi)

    def test_variousTypesWork(self):
        with Database3(self.dbName, "r") as db:
            r2 = db.load(1, 1)

        b1 = self.r.core.getFirstBlock(Flags.FUEL)
        b2 = r2.core.getFirstBlock(Flags.FUEL)

        self.assertIsInstance(b1.p.mgFlux, numpy.ndarray)
        self.assertIsInstance(b2.p.mgFlux, numpy.ndarray)
        assert_allclose(b1, b2)

        c1 = b1.getComponent(Flags.FUEL)
        c2 = b2.getComponent(Flags.FUEL)

        self.assertIsInstance(c1.p.numberDensities, dict)
        self.assertIsInstance(c2.p.numberDensities, dict)
        keys1 = set(c1.p.numberDensities.keys())
        keys2 = set(c2.p.numberDensities.keys())
        self.assertEqual(keys1, keys2)

        numDensVec1, numDensVec2 = [], []
        for k in keys1:
            numDensVec1.append(c1.p.numberDensities[k])
            numDensVec2.append(c2.p.numberDensities[k])

        assert_allclose(numDensVec1, numDensVec2)


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
        Ensures that parameters are consistant between Standard runs and restart runs.
        """
        o, cs = getSimpleDBOperator(cs)

        mock = MockInterface(o.r, o.cs, None)

        # pylint: disable=unused-argument
        def interactEveryNode(self, cycle, node):
            # Could use just += 1 but this will show more errors since it is less
            # suseptable to cancelation of errors off by one.
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
            o = self._getOperatorThatChangesVariables(
                settings.Settings(os.path.join(TEST_ROOT, "armiRun.yaml"))
            )
            with o:
                o.operate()
                firstEndTime = o.r.p.time
                self.assertNotEqual(
                    firstEndTime, 0, "Time should have advanced by the end of the run."
                )

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
                    "First end time: {},\nSecond End time: {}".format(
                        firstEndTime, o.r.p.time
                    ),
                )


if __name__ == "__main__":
    unittest.main()
