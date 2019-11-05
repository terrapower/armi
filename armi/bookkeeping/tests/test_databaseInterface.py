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

import collections
import os
import unittest
import types

import h5py
import numpy
from numpy.testing import assert_allclose, assert_equal

import armi
from armi.reactor.flags import Flags
from armi import interfaces
from armi.bookkeeping.db.database3 import DatabaseInterface, Database3
from armi.bookkeeping.db import convertDatabase
from armi import settings
from armi.tests import TEST_ROOT
from armi.cases import case
from armi.utils import directoryChangers
from armi import runLog
from armi.reactor.tests import test_reactors


def getSimpleDBOperator(cs):
    """
    Return a very simple operator that covers most of the database interactions.

    Notes
    -----
    This reactor has only 1 assembly with 1 type of block.
    It's used to make the db unit tests run very quickly.
    """
    cs["loadingFile"] = "refOneBlockReactor.yaml"
    cs["verbosity"] = "important"
    cs["db"] = True
    cs["runType"] = "Standard"
    cs["geomFile"] = "geom1Assem.xml"
    cs["nCycles"] = 2
    genDBCase = case.Case(cs)
    settings.setMasterCs(cs)
    runLog.setVerbosity("info")

    o = genDBCase.initializeOperator()
    o.interfaces = [
        interface
        for interface in o.interfaces
        if interface.name in ["database", "main"]
    ]
    return o


class MockInterface(interfaces.Interface):
    name = "mockInterface"

    def __init__(self, r, cs, action=None):
        interfaces.Interface.__init__(self, r, cs)
        self.action = action

    def interactEveryNode(self, cycle, node):
        self.action(cycle, node)


class TestDatabaseWriter(unittest.TestCase):
    def setUp(self):

        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()
        cs = settings.Settings(os.path.join(TEST_ROOT, "armiRun.yaml"))
        self.o = getSimpleDBOperator(cs)
        self.r = self.o.r

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_metaData_endSuccessfully(self):
        def goodMethod(cycle, node):  # pylint: disable=unused-argument
            pass

        self.o.interfaces.append(MockInterface(self.o.r, self.o.cs, goodMethod))
        with self.o:
            self.o.operate()

        self.assertEqual(1, self.r.p.cycle)
        self.assertEqual(2, self.r.p.timeNode)

        with h5py.File(self.o.cs.caseTitle + ".h5", "r") as h5:
            self.assertTrue(h5.attrs["successfulCompletion"])
            self.assertEqual(h5.attrs["version"], armi.__version__)
            self.assertIn("user", h5.attrs)
            self.assertIn("python", h5.attrs)
            self.assertIn("armiLocation", h5.attrs)
            self.assertIn("startTime", h5.attrs)
            self.assertIn("machines", h5.attrs)
            self.assertIn("caseTitle", h5.attrs)

            self.assertIn("geomFile", h5["inputs"])
            self.assertIn("settings", h5["inputs"])
            self.assertIn("blueprints", h5["inputs"])

    def test_metaData_endFail(self):
        def failMethod(cycle, node):  # pylint: disable=unused-argument
            if cycle == 1 and node == 1:
                raise Exception("forcing failure")

        self.o.interfaces.append(MockInterface(self.o.r, self.o.cs, failMethod))

        with self.assertRaises(Exception):
            with self.o:
                self.o.operate()

        self.assertEqual(1, self.r.p.cycle)
        self.assertEqual(1, self.r.p.timeNode)

        with h5py.File(self.o.cs.caseTitle + ".h5", "r") as h5:
            self.assertFalse(h5.attrs["successfulCompletion"])
            self.assertEqual(h5.attrs["version"], armi.__version__)
            self.assertIn("caseTitle", h5.attrs)

    @unittest.skip(
        "This test needs to be rewritten to support the new Database implementation."
    )
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
            if cycle != 2 or node != 3:
                return

            blocks = self.r.core.getBlocks()
            b0 = blocks[0]
            b7 = blocks[7]  # lucky number 7

            db = self.o.getInterface("database").db

            # we are now in cycle 2, node 3 ... AFTER setFluxAwesome, but BEFORE writeToDB
            # lets get the 3rd block ... whatever that is
            actualFluxes0 = db.getHistory(b0)["flux"]
            actualFluxes7 = db.getHistory(b7)["flux"]
            self.assertEqual(expectedFluxes0, actualFluxes0)
            self.assertEqual(expectedFluxes7, actualFluxes7)
            self.called = True

        self.o.interfaces.insert(0, MockInterface(self.o.r, self.o.cs, setFluxAwesome))
        self.o.interfaces.insert(1, MockInterface(self.o.r, self.o.cs, getFluxAwesome))

        with self.o:
            self.o.operate()

        self.assertTrue(self.called)

    @unittest.skip("TBD")
    def test_getHistoryByLocation(self):
        def setFluxAwesome(cycle, node):  # pylint: disable=unused-argument
            for bi, b in enumerate(self.r.core.getBlocks()):
                b.p.flux = 1e6 * bi + 1e3 * cycle + node

        def getFluxAwesome(cycle, node):  # pylint: disable=unused-argument
            if cycle != 2 or node != 3:
                return

            db = self.o.getInterface("database").database

            # we are now in cycle 2, node 3 ... AFTER setFluxAwesome
            # lets get the 3rd block ... whatever that is
            fluxes = db.getHistory(b, params=["flux"])

        self.o.interfaces.append(MockInterface(self.o.r, self.o.cs, setFluxAwesome))
        self.o.interfaces.append(MockInterface(self.o.r, self.o.cs, getFluxAwesome))

        with self.o:
            self.o.operate()

        with h5py.File(self.o.cs.caseTitle + ".h5", "r") as h5:
            self.assertFalse(h5.attrs["successfulCompletion"])
            self.assertEqual(h5.attrs["version"], armi.__version__)


class TestDatabaseReading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = directoryChangers.TemporaryDirectoryChanger()
        cls.td.__enter__()
        o, _r = test_reactors.loadTestReactor(customSettings={"verbosity": "extra"})
        # The database writes the settings object to the DB rather
        # than the original input file. This allows settings to be
        # changed in memory like this and survive for testing.
        o.cs["nCycles"] = 2
        o.cs["burnSteps"] = 3
        settings.setMasterCs(o.cs)
        o.cs["db"] = True

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

    def test_readWritten(self):

        with Database3(self.dbName, "r") as db:
            r2 = db.load(0, 0, self.cs, self.bp)

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

        with Database3(self.dbName, "r") as db:
            r2 = db.load(0, 0)

        for b1, b2 in zip(self.r.core.getBlocks(), r2.core.getBlocks()):
            for c1, c2 in zip(sorted(b1), sorted(b2)):
                self.assertEqual(c1.name, c2.name)

        for bi, b in enumerate(r2.core.getBlocks()):
            assert_allclose(b.p.flux, 1e6 * bi)

    def test_variousTypesWork(self):
        with Database3(self.dbName, "r") as db:
            r2 = db.load(1, 3)

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

    def test_convertDatabase(self):
        convertDatabase(self.dbName, outputVersion="2")
        with h5py.File("-converted".join(os.path.splitext(self.dbName)), "r") as newDB:
            self.assertIn("Materials", newDB)
            self.assertIn("Geometry", newDB)
            for i in range((self.cs["burnSteps"] + 1) * self.cs["nCycles"]):
                self.assertIn(
                    str(i),
                    newDB,
                    msg=f"{str(i)} not found in {newDB}, which has {newDB.keys()}",
                )


class TestBadName(unittest.TestCase):
    def test_badDBName(self):
        cs = settings.Settings(os.path.join(TEST_ROOT, "armiRun.yaml"))
        cs["reloadDBName"] = "aRmIRuN.h5"  # weird casing to confirm robust checking
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
        o = getSimpleDBOperator(cs)

        mock = MockInterface(o.r, o.cs, None)

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
            cs["loadStyle"] = "fromDB"
            cs["reloadDBName"] = loadDB
            cs["startCycle"] = 1
            cs["startNode"] = 1
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
    import sys

    # sys.argv = ["", "TestStandardFollowOn.test_standardRestart"]
    unittest.main()
