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

"""
Tests for the history tracker interface.

These tests actually run a jupyter notebook that is in the documentation to build a valid HDF5 file to load from as a
test fixtures. Thus they take a little longer than usual.
"""

import os
import shutil

import numpy as np

from armi import init as armi_init
from armi import settings, utils
from armi.reactor.flags import Flags
from armi.tests import TEST_ROOT, ArmiTestHelper
from armi.utils.directoryChangers import TemporaryDirectoryChanger

THIS_DIR = os.path.dirname(__file__)  # because tests do not run in this folder
TEST_FILE = os.path.join(TEST_ROOT, "smallestTestReactor", "armiRunSmallest.yaml")


class TestHistoryTracker(ArmiTestHelper):
    """History tracker tests that require a Reactor Model."""

    @classmethod
    def setUpClass(cls):
        cls.dirChanger = TemporaryDirectoryChanger()
        cls.dirChanger.__enter__()

        # modify the input settings for our tests
        dbPath = os.path.join(cls.dirChanger.destination, "armiRunSmallest.h5")
        reloadPath = os.path.join(cls.dirChanger.destination, "armiRunSmallestReload.h5")
        cs = settings.Settings(TEST_FILE)
        newSettings = {}
        newSettings["db"] = True
        newSettings["nCycles"] = 1
        newSettings["detailAssemLocationsBOL"] = ["001-001"]
        newSettings["loadStyle"] = "fromDB"
        newSettings["reloadDBName"] = reloadPath
        newSettings["startNode"] = 1
        newSettings["verbosity"] = "error"
        cs = cs.modified(newSettings=newSettings)

        # build the ARMI operator (and Reactor)
        o = armi_init(fName=TEST_FILE, cs=cs)

        def _setFakePower(core):
            peakPower = 1e6
            mgFluxBase = np.arange(5)
            for a in core:
                for b in a:
                    vol = b.getVolume()
                    fuelFlag = 10 if b.isFuel() else 1.0
                    b.p.power = peakPower * fuelFlag
                    b.p.pdens = b.p.power / vol
                    b.p.mgFlux = mgFluxBase * b.p.pdens

        # put some test power values on the Reactor object
        _setFakePower(o.r.core)

        # write some data to the DB
        dbi = o.getInterface("database")
        dbi.initDB(fName=dbPath)
        dbi.database.writeToDB(o.r)
        o.r.p.timeNode += 1
        dbi.database.writeToDB(o.r)

        cls.o = o
        cls.r = o.r

    @classmethod
    def tearDownClass(cls):
        cls.dirChanger.__exit__(None, None, None)
        try:
            cls.o.getInterface("database").database.close()
        except FileNotFoundError:
            pass
        cls.r = None
        cls.o = None

    def test_calcMGFluence(self):
        """
        This test confirms that mg flux has many groups when loaded with the history tracker.

        .. test:: Demonstrate that a parameter stored at differing time nodes can be recovered.
            :id: T_ARMI_HIST_TRACK0
            :tests: R_ARMI_HIST_TRACK
        """
        o = self.o
        b = o.r.core.childrenByLocator[o.r.core.spatialGrid[0, 0, 0]].getFirstBlock(Flags.FUEL)
        bVolume = b.getVolume()
        bName = b.name

        # duration is None in this DB
        hti = o.getInterface("history")
        timesInYears = [duration or 1.0 for duration in hti.getTimeSteps()]
        timeStepsToRead = [utils.getCycleNodeFromCumulativeNode(i, self.o.cs) for i in range(len(timesInYears))]
        hti.preloadBlockHistoryVals([bName], ["mgFlux"], timeStepsToRead)

        mgFluence = None
        for ts, years in enumerate(timesInYears):
            cycle, node = utils.getCycleNodeFromCumulativeNode(ts, self.o.cs)
            mgFlux = hti.getBlockHistoryVal(bName, "mgFlux", (cycle, node))
            mgFlux /= bVolume
            timeInSec = years * 365 * 24 * 3600
            if mgFluence is None:
                mgFluence = timeInSec * mgFlux
            else:
                mgFluence += timeInSec * mgFlux

        self.assertGreater(len(mgFluence), 1, "mgFluence should have more than 1 group")

        # test that unloadBlockHistoryVals() is working
        self.assertIsNotNone(hti._preloadedBlockHistory)
        hti.unloadBlockHistoryVals()
        self.assertIsNone(hti._preloadedBlockHistory)

    def test_historyParameters(self):
        """Retrieve various parameters from the history.

        .. test:: Demonstrate that various parameters stored at differing time nodes can be recovered.
            :id: T_ARMI_HIST_TRACK1
            :tests: R_ARMI_HIST_TRACK
        """
        o = self.o
        b = o.r.core.childrenByLocator[o.r.core.spatialGrid[0, 0, 0]].getFirstBlock(Flags.FUEL)
        b.getVolume()
        bName = b.name

        # duration is None in this DB
        hti = o.getInterface("history")
        timesInYears = [duration or 1.0 for duration in hti.getTimeSteps()]
        timeStepsToRead = [utils.getCycleNodeFromCumulativeNode(i, self.o.cs) for i in range(len(timesInYears))]
        hti.preloadBlockHistoryVals([bName], ["power"], timeStepsToRead)

        # read some parameters
        params = {}
        for param in ["height", "pdens", "power"]:
            params[param] = []
            for ts, years in enumerate(timesInYears):
                cycle, node = utils.getCycleNodeFromCumulativeNode(ts, self.o.cs)
                params[param].append(hti.getBlockHistoryVal(bName, param, (cycle, node)))

        # verify the height parameter doesn't change over time
        self.assertGreater(params["height"][0], 0)
        self.assertEqual(params["height"][0], params["height"][1])

        # verify the power parameter is retrievable from the history
        refPower = 1000000.0
        self.assertEqual(o.cs["power"], refPower)
        self.assertAlmostEqual(params["power"][0], refPower * 10.0, delta=0.1)

        # verify the power density parameter is retrievable from the history
        refDens = 1636.4803548458785
        self.assertAlmostEqual(params["pdens"][0], refDens, delta=0.001)
        self.assertAlmostEqual(params["pdens"][0], params["pdens"][1])

        # test that unloadBlockHistoryVals() is working
        self.assertIsNotNone(hti._preloadedBlockHistory)
        hti.unloadBlockHistoryVals()
        self.assertIsNone(hti._preloadedBlockHistory)

    def test_historyReport(self):
        """
        Test generation of history report.

        This does a swap for 5 timesteps::

            |       TS  0     1      2       3       4
            |LOC      (1,1) (2,1)  (3,1)   (4,1)   SFP
        """
        history = self.o.getInterface("history")
        history.interactBOL()
        history.interactEOL()
        testLoc = self.o.r.core.spatialGrid[0, 0, 0]
        testAssem = self.o.r.core.childrenByLocator[testLoc]
        fileName = history._getAssemHistoryFileName(testAssem)
        actualFilePath = os.path.join(THIS_DIR, fileName)
        expectedFileName = os.path.join(THIS_DIR, fileName.replace(".txt", "-ref.txt"))
        # copy from fast path so the file is retrievable.
        shutil.move(fileName, os.path.join(THIS_DIR, fileName))
        self.compareFilesLineByLine(expectedFileName, actualFilePath)

        # test that detailAssemblyNames() is working
        self.assertEqual(len(history.detailAssemblyNames), 1)
        history.addAllDetailedAssems()
        self.assertEqual(len(history.detailAssemblyNames), 1)

    def test_getAssemHistories(self):
        """Get the histories for all blocks in detailed assemblies."""
        history = self.o.getInterface("history")
        history.interactBOL()
        assemList = history.getDetailAssemblies()
        params = history.getTrackedParams()
        assemHistories = history.getAssemHistories(assemList)
        for a in assemList:
            for b in history.nonStationaryBlocks(a):
                self.assertIn(b, assemHistories)
                for param in params:
                    self.assertIn(param, assemHistories[b])

    def test_getBlockInAssembly(self):
        history = self.o.getInterface("history")
        aFuel = self.o.r.core.getFirstAssembly(Flags.FUEL)

        b = history._getBlockInAssembly(aFuel)
        self.assertGreater(b.p.height, 1.0)
        self.assertEqual(b.getType(), "fuel")

        with self.assertRaises(AttributeError):
            aShield = self.o.r.core.getFirstAssembly(Flags.SHIELD)
            history._getBlockInAssembly(aShield)
