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

"""
Tests for the Snapshot Interface

These tests actually run a jupyter notebook that's in the documentation to build
a valid HDF5 file to load from as a test fixtures. Thus they take a little longer
than usual.
"""
# pylint: disable=abstract-method,no-self-use,unused-argument,missing-function-docstring,missing-class-docstring,import-outside-toplevel
import os
import pathlib
import shutil
import unittest

from armi.context import ROOT
from armi import init as armi_init
from armi import settings
from armi.utils import directoryChangers
from armi.cases import case
from armi.tests import ArmiTestHelper
from armi.bookkeeping.tests._constants import TUTORIAL_FILES

THIS_DIR = os.path.dirname(__file__)  # b/c tests don't run in this folder
BK_DIR = os.path.join(THIS_DIR, "..", "..", "bookkeeping", "tests")
TUTORIAL_DIR = os.path.join(ROOT, "tests", "tutorials")
CASE_TITLE = "anl-afci-177"


def runTutorialNotebook():
    import nbformat
    from nbconvert.preprocessors import ExecutePreprocessor

    with open("data_model.ipynb") as f:
        nb = nbformat.read(f, as_version=4)
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    ep.preprocess(nb, {})


class TestSOperatorSnapshots(ArmiTestHelper):
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
        """
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
        """
        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()

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

    def test_snapshotBasics(self):
        print(self.o)
        snap = self.o.getInterface("snapshot")
        print(snap)
        print(type(snap))
        # assert False

        """
        history = self.o.getInterface("history")
        history.interactBOL()
        history.interactEOL()
        testLoc = self.o.r.core.spatialGrid[0, 0, 0]
        testAssem = self.o.r.core.childrenByLocator[testLoc]
        # pylint:disable=protected-access
        fileName = history._getAssemHistoryFileName(testAssem)
        actualFilePath = os.path.join(BK_DIR, fileName)
        expectedFileName = os.path.join(BK_DIR, fileName.replace(".txt", "-ref.txt"))
        # copy from fast path so the file is retrievable.
        shutil.move(fileName, os.path.join(BK_DIR, fileName))

        self.compareFilesLineByLine(expectedFileName, actualFilePath)
        # clean file created at interactEOL
        os.remove("armiRun.locationHistory.txt")
        """


if __name__ == "__main__":
    unittest.main()
