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
        newSettings["nCycles"] = 1
        newSettings["burnSteps"] = 5
        newSettings["cycleLength"] = 365

        reloadCs = reloadCs.modified(newSettings=newSettings)
        reloadCs.caseTitle = "armiRun"

        o = armi_init(cs=reloadCs)
        cls.o = o

    @classmethod
    def tearDownClass(cls):
        cls.dirChanger.__exit__(None, None, None)

    def setUp(self):
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
        snap = self.o.getInterface("snapshot")
        snap.cs["dumpSnapshot"] = ["000000"]
        self.assertEqual(["000000"], snap.cs["dumpSnapshot"])

        self.assertEqual(self.o.r.p.cycle, 0)
        self.assertEqual(self.o.maxBurnSteps, 5)
        self.assertEqual(self.o.burnSteps, [5])
        self.assertEqual(snap.cs["nCycles"], 1)

        self.o.operate()

        self.assertEqual(self.o.r.p.cycle, 0)
        self.assertEqual(self.o.maxBurnSteps, 5)
        self.assertEqual(self.o.burnSteps, [5])
        self.assertEqual(snap.cs["nCycles"], 1)


if __name__ == "__main__":
    unittest.main()
