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

These tests actually run a jupyter notebook that's in the documentation to build
a valid HDF5 file to load from as a test fixtures. Thus they take a little longer
than usual.
"""
import unittest
import os
import pathlib
import shutil

from armi.context import ROOT
from armi import init as armi_init
from armi import utils
from armi.bookkeeping import historyTracker
from armi.reactor import blocks
from armi.reactor.flags import Flags
from armi import settings
from armi.utils import directoryChangers
from armi.reactor import grids
from armi.cases import case
from armi.tests import ArmiTestHelper
from armi.bookkeeping.tests._constants import TUTORIAL_FILES

THIS_DIR = os.path.dirname(__file__)  # b/c tests don't run in this folder
TUTORIAL_DIR = os.path.join(ROOT, "tests", "tutorials")
CASE_TITLE = "anl-afci-177"


def runTutorialNotebook():
    import nbformat
    from nbconvert.preprocessors import ExecutePreprocessor

    with open("data_model.ipynb") as f:
        nb = nbformat.read(f, as_version=4)
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    ep.preprocess(nb, {})


class TestHistoryTracker(ArmiTestHelper):
    """History tracker tests that require a Reactor Model."""

    @classmethod
    def setUpClass(cls):
        # Not using a directory changer since it isn't important that we go back in the
        # first place, and we don't want to get tangled with the directory change below.
        # We need to be in the TUTORIAL_DIR in the first place so that for `filesToMove`
        # to work right.
        os.chdir(TUTORIAL_DIR)

        # Make sure to do this work in a temporary directory to avoid race conditions
        # when running tests in parallel with xdist.
        cls.dirChanger = directoryChangers.TemporaryDirectoryChanger(
            filesToMove=TUTORIAL_FILES
        )
        cls.dirChanger.__enter__()
        runTutorialNotebook()

        reloadCs = settings.Settings(f"{CASE_TITLE}.yaml")

        newSettings = {}
        newSettings["db"] = True
        newSettings["reloadDBName"] = pathlib.Path(f"{CASE_TITLE}.h5").absolute()
        newSettings["runType"] = "Snapshots"
        newSettings["loadStyle"] = "fromDB"
        newSettings["detailAssemLocationsBOL"] = ["001-001"]

        reloadCs = reloadCs.modified(newSettings=newSettings)
        reloadCs.caseTitle = "armiRun"

        o = armi_init(cs=reloadCs)
        cls.o = o

    @classmethod
    def tearDownClass(cls):
        cls.dirChanger.__exit__(None, None, None)

    def setUp(self):
        cs = settings.Settings(f"{CASE_TITLE}.yaml")
        newSettings = {}
        newSettings["db"] = True
        newSettings["reloadDBName"] = pathlib.Path(f"{CASE_TITLE}.h5").absolute()
        newSettings["loadStyle"] = "fromDB"
        newSettings["detailAssemLocationsBOL"] = ["001-001"]
        newSettings["startNode"] = 1
        cs = cs.modified(newSettings=newSettings)

        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()

        c = case.Case(cs)
        case2 = c.clone(title="armiRun")
        settings.setMasterCs(case2.cs)
        self.o = case2.initializeOperator()
        self.r = self.o.r

        self.o.getInterface("main").interactBOL()

        dbi = self.o.getInterface("database")
        # Get to the database state at the end of stack of time node 1.
        # The end of the interface stack is when history tracker tends to run.
        dbi.loadState(0, 1)

    def tearDown(self):
        self.o.getInterface("database").database.close()
        self.r = None
        self.o = None
        self.td.__exit__(None, None, None)

    def test_calcMGFluence(self):
        """
        This test confirms that mg flux has many groups when loaded with the history tracker.

        armi.bookeeping.db.hdf.hdfDB.readBlocksHistory requires
        historical_values[historical_indices] to be cast as a list to read more than the
        first energy group. This test shows that this behavior is preserved.
        """
        o = self.o
        b = o.r.core.childrenByLocator[o.r.core.spatialGrid[0, 0, 0]].getFirstBlock(
            Flags.FUEL
        )
        bVolume = b.getVolume()
        bName = b.name

        hti = o.getInterface("history")

        timesInYears = [
            duration or 1.0 for duration in hti.getTimeSteps()
        ]  # duration is None in this DB
        timeStepsToRead = [
            utils.getCycleNode(i, self.o.cs) for i in range(len(timesInYears))
        ]
        hti.preloadBlockHistoryVals([bName], ["mgFlux"], timeStepsToRead)

        mgFluence = None
        for ts, years in enumerate(timesInYears):
            cycle, node = utils.getCycleNode(ts, self.o.cs)
            # get coverage for getTimeStepNum by checking against getcycleNode
            testTS = utils.getTimeStepNum(cycle, node, self.o.cs)
            self.assertEqual(ts, testTS)
            mgFlux = (
                hti.getBlockHistoryVal(bName, "mgFlux", (cycle, node)) / bVolume
            )  #  b.p.mgFlux is vol integrated
            timeInSec = years * 365 * 24 * 3600
            if mgFluence is None:
                mgFluence = timeInSec * mgFlux
            else:
                mgFluence += timeInSec * mgFlux

        self.assertTrue(len(mgFluence) > 1, "mgFluence should have more than 1 group")

    def test_historyReport(self):
        """
        Test generation of history report.

        This does a swap for 5 timesteps:
        |       TS  0     1      2       3       4
        |LOC      (1,1) (2,1)  (3,1)   (4,1)   SFP
        """
        history = self.o.getInterface("history")
        history.interactBOL()
        history.interactEOL()
        testLoc = self.o.r.core.spatialGrid[0, 0, 0]
        testAssem = self.o.r.core.childrenByLocator[testLoc]
        # pylint:disable=protected-access
        fileName = history._getAssemHistoryFileName(testAssem)
        actualFilePath = os.path.join(THIS_DIR, fileName)
        expectedFileName = os.path.join(THIS_DIR, fileName.replace(".txt", "-ref.txt"))
        # copy from fast path so the file is retrievable.
        shutil.move(fileName, os.path.join(THIS_DIR, fileName))

        self.compareFilesLineByLine(expectedFileName, actualFilePath)
        # clean file created at interactEOL
        os.remove("armiRun.locationHistory.txt")


class TestHistoryTrackerNoModel(unittest.TestCase):
    """History tracker tests that do not require a Reactor Model."""

    def setUp(self):
        self.history = historyTracker.HistoryTrackerInterface(None, None)
        self._origCaseTitle = (
            self.history.cs.caseTitle
        )  # to avoid parallel test interference.
        self.history.cs.caseTitle = self._testMethodName + self._origCaseTitle

    def tearDown(self):
        self.history.cs.caseTitle = self._origCaseTitle

    def test_timestepFiltering(self):
        times = range(30)
        self.history.cs = self.history.cs.modified(newSettings={"burnSteps": 2})

        inputs = [
            {"boc": True},
            {"moc": True},
            {"eoc": True},
            {"boc": True, "eoc": True},
        ]
        results = [
            [0, 3, 6, 9, 12, 15, 18, 21, 24, 27],
            [1, 4, 7, 10, 13, 16, 19, 22, 25, 28],
            [2, 5, 8, 11, 14, 17, 20, 23, 26, 29],
            [0, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18, 20, 21, 23, 24, 26, 27, 29],
        ]
        for i, expectedResults in zip(inputs, results):
            runResults = self.history.filterTimeIndices(times, **i)
            self.assertEqual(runResults, expectedResults)

    def test_timestepFilteringWithGap(self):
        times = list(range(10)) + list(range(15, 20))
        self.history.cs = self.history.cs.modified(newSettings={"burnSteps": 2})

        runResults = self.history.filterTimeIndices(times, boc=True)
        self.assertEqual(runResults, [0, 3, 6, 9, 15, 18])

    def test_blockName(self):
        block = blocks.HexBlock("blockName")
        block.spatialLocator = grids.IndexLocation(0, 0, 7, None)
        self.assertEqual(
            self.history._getBlockHistoryFileName(
                block
            ),  # pylint:disable=protected-access
            "{}-blockName7-bHist.txt".format(self.history.cs.caseTitle),
        )


if __name__ == "__main__":
    # import sys;sys.argv = ["", "TestHistoryTracker.test_historyReport"]
    unittest.main()
