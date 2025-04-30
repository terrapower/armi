# Copyright 2022 TerraPower, LLC
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

"""Tests for operator snapshots."""
import unittest
from pathlib import Path
from unittest.mock import Mock

from armi import settings
from armi.bookkeeping.db.databaseInterface import DatabaseInterface
from armi.operators import getOperatorClassFromSettings
from armi.operators.runTypes import RunTypes
from armi.operators.snapshots import OperatorSnapshots
from armi.tests import TEST_ROOT
from armi.testing import loadTestReactor, reduceTestReactorRings


class TestOperatorSnapshots(unittest.TestCase):
    def setUp(self):
        newSettings = {}
        newSettings["db"] = True
        newSettings["runType"] = "Standard"
        newSettings["verbosity"] = "important"
        newSettings["branchVerbosity"] = "important"
        newSettings["nCycles"] = 1
        newSettings["dumpSnapshot"] = ["000000", "008000", "016005"]
        o1, self.r = loadTestReactor(
            customSettings=newSettings,
            inputFileName="smallestTestReactor/armiRunSmallest.yaml",
        )
        self.o = OperatorSnapshots(o1.cs)
        self.o.r = self.r

        # mock a Database Interface
        self.dbi = DatabaseInterface(self.r, o1.cs)
        self.dbi.loadState = lambda c, n: None
        self.dbi.writeDBEveryNode = lambda: None
        self.dbi.closeDB = lambda: None

    def test_atEOL(self):
        self.assertFalse(self.o.atEOL)

    def test_setStateToDefault(self):
        cs0 = self.o.cs.modified(newSettings={"runType": RunTypes.SNAPSHOTS})
        self.assertEqual(cs0["runType"], RunTypes.SNAPSHOTS)
        cs = self.o.setStateToDefault(cs0)
        self.assertEqual(cs["runType"], RunTypes.STANDARD)

    def test_mainOperate(self):
        # Mock some tooling that we aren't testing
        self.o.interactBOL = lambda: None
        self.o.getInterface = (
            lambda s: self.dbi if s == "database" else super().getInterface(s)
        )

        self.assertEqual(self.r.core.p.power, 0.0)
        self.o._mainOperate()
        self.assertEqual(self.r.core.p.power, 1000000.0)

    def test_createInterfaces(self):
        self.assertEqual(len(self.o.interfaces), 0)
        self.o.createInterfaces()

        # If someone adds an interface, we don't want this test to break, so let's do >6
        self.assertGreater(len(self.o.interfaces), 6)

    def test_createInterfacesDisabled(self):
        self.assertEqual(len(self.o.interfaces), 0)
        allInterfaces = [
            "main",
            "fissionProducts",
            "xsGroups",
            "fuelHandler",
            "history",
            "database",
            "memoryProfiler",
            "snapshot",
        ]
        for i in allInterfaces:
            self.o.disabledInterfaces.append(i)
        self.o.createInterfaces()

        # If someone adds an interface, we don't want this test to break, so let's do >6
        self.assertGreater(len(self.o.interfaces), 6)
        for i in self.o.interfaces:
            self.assertFalse(i.enabled())


class TestOperatorSnapshotsSettings(unittest.TestCase):
    def test_getOperatorClassFromSettings(self):
        cs = settings.Settings()
        cs = cs.modified(newSettings={"runType": RunTypes.SNAPSHOTS})
        clazz = getOperatorClassFromSettings(cs)
        self.assertEqual(clazz, OperatorSnapshots)


class TestOperatorSnapshotFullCoreExpansion(unittest.TestCase):
    """Test that a snapshot operator can do full core analysis with a 1/3 core DB."""

    DB_PATH = Path("test_operator_snapshot_full_core_expansion.h5")

    @classmethod
    def setUpClass(cls):
        o, cls.symmetricReactor = loadTestReactor(TEST_ROOT)
        reduceTestReactorRings(cls.symmetricReactor, o.cs, maxNumRings=2)
        dbi: DatabaseInterface = next(
            filter(lambda i: isinstance(i, DatabaseInterface), o.interfaces)
        )
        dbi.initDB(cls.DB_PATH)
        dbi.writeDBEveryNode()
        dbi.closeDB()

        cls.snapshotSettings: settings.Settings = o.cs.modified(
            newSettings={
                "runType": RunTypes.SNAPSHOTS,
                "reloadDBName": str(cls.DB_PATH),
            }
        )

    def test_fullCoreFromThirdCore(self):
        self.assertFalse(self.symmetricReactor.core.isFullCore)
        cs = self.snapshotSettings.modified(
            newSettings={"growToFullCoreOnLoad": True, "dumpSnapshot": ["0000"]}
        )
        o = getOperatorClassFromSettings(cs)(cs)
        self.assertIsInstance(o, OperatorSnapshots)
        o.r = self.symmetricReactor
        # Just want Database interface not history tracker not reporting not etc.
        o.addInterface(DatabaseInterface(o.r, o.cs))
        # Mock interactAllBOC so we don't do iteract every nodes
        # We just want to trigger the re-attachment of the loaded reactor
        o.interactAllBOC = Mock(return_value=True)
        o.operate()
        self.assertTrue(o.r.core.isFullCore)

    @classmethod
    def tearDownClass(cls):
        cls.DB_PATH.unlink()
