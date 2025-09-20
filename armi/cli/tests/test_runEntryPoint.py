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
"""Test for run cli entry point."""

import logging
import os
import sys
import unittest
from shutil import copyfile

from armi import runLog
from armi.__main__ import main
from armi.bookkeeping.db.databaseInterface import DatabaseInterface
from armi.bookkeeping.visualization.entryPoint import VisFileEntryPoint
from armi.cli.checkInputs import CheckInputEntryPoint, ExpandBlueprints
from armi.cli.clone import CloneArmiRunCommandBatch, CloneSuiteCommand
from armi.cli.compareCases import CompareCases, CompareSuites
from armi.cli.database import ExtractInputs, InjectInputs
from armi.cli.entryPoint import EntryPoint
from armi.cli.migrateInputs import MigrateInputs
from armi.cli.modify import ModifyCaseSettingsCommand
from armi.cli.reportsEntryPoint import ReportsEntryPoint
from armi.cli.run import RunEntryPoint
from armi.cli.runSuite import RunSuiteCommand
from armi.physics.neutronics.diffIsotxs import CompareIsotxsLibraries
from armi.testing import loadTestReactor, reduceTestReactorRings
from armi.tests import ARMI_RUN_PATH, TEST_ROOT, mockRunLogs
from armi.utils.directoryChangers import TemporaryDirectoryChanger
from armi.utils.dynamicImporter import getEntireFamilyTree


def buildTestDB(fileName, numNodes=1, numCycles=1):
    """This function builds a (super) simple test DB.

    Notes
    -----
    This needs to be run inside a temp directory.

    Parameters
    ----------
    fileName : str
        The file name (not path) we want for the ARMI test DB.
    numNodes : int, optional
        The number of nodes we want in the DB, default 1.
    numCycles : int, optional
        The number of cycles we want in the DB, default 1.

    Returns
    -------
    str
        Database file name.
    """
    o, r = loadTestReactor(
        TEST_ROOT,
        inputFileName="smallestTestReactor/armiRunSmallest.yaml",
    )

    # create the tests DB
    dbi = DatabaseInterface(r, o.cs)
    dbi.initDB(fName=f"{fileName}.h5")
    db = dbi.database

    # populate the db with something
    r.p.cycle = 0
    for node in range(abs(numNodes)):
        for cycle in range(abs(numCycles)):
            r.p.timeNode = node
            r.p.cycle = cycle
            r.p.cycleLength = 100
            db.writeToDB(r)

    db.close()
    return f"{fileName}.h5"


class TestInitializationEntryPoints(unittest.TestCase):
    def test_entryPointInitialization(self):
        """Tests the initialization of all subclasses of `EntryPoint`.

        .. test:: Test initialization of many basic CLIs.
            :id: T_ARMI_CLI_GEN0
            :tests: R_ARMI_CLI_GEN
        """
        entryPoints = getEntireFamilyTree(EntryPoint)

        # Comparing to a minimum number of entry points, in case more are added.
        self.assertGreater(len(entryPoints), 15)

        for e in entryPoints:
            entryPoint = e()
            entryPoint.addOptions()
            settingsArg = None
            if entryPoint.settingsArgument is not None:
                for a in entryPoint.parser._actions:
                    if "settings_file" in a.dest:
                        settingsArg = a
                        break
                self.assertIsNotNone(
                    settingsArg,
                    msg=(
                        f"A settings file argument was expected for {entryPoint}, "
                        "but does not exist. This is a error in the EntryPoint "
                        "implementation."
                    ),
                )


class TestCheckInputEntryPoint(unittest.TestCase):
    def test_checkInputEntryPointBasics(self):
        ci = CheckInputEntryPoint()
        ci.addOptions()
        ci.parse_args(["/path/to/fake.yaml", "-C"])

        self.assertEqual(ci.name, "check-input")
        self.assertEqual(ci.args.patterns, ["/path/to/fake.yaml"])
        self.assertEqual(ci.args.skip_checks, True)

    def test_checkInputEntryPointInvoke(self):
        """Test the "check inputs" entry point.

        .. test:: A working CLI child class, to validate inputs.
            :id: T_ARMI_CLI_GEN1
            :tests: R_ARMI_CLI_GEN
        """
        ci = CheckInputEntryPoint()
        ci.addOptions()
        ci.parse_args([ARMI_RUN_PATH])

        with mockRunLogs.BufferLog() as mock:
            runLog.LOG.startLog("test_checkInputEntryPointInvoke")
            runLog.LOG.setVerbosity(logging.INFO)
            self.assertEqual("", mock.getStdout())

            ci.invoke()

            self.assertIn(ARMI_RUN_PATH, mock.getStdout())
            self.assertIn("input is self consistent", mock.getStdout())


class TestCloneArmiRunCommandBatch(unittest.TestCase):
    def test_cloneArmiRunCommandBatchBasics(self):
        ca = CloneArmiRunCommandBatch()
        ca.addOptions()
        ca.parse_args(
            [
                ARMI_RUN_PATH,
                "--additional-files",
                "test",
                "--settingsWriteStyle",
                "full",
            ]
        )

        self.assertEqual(ca.name, "clone-batch")
        self.assertEqual(ca.settingsArgument, "required")
        self.assertEqual(ca.args.additional_files, ["test"])
        self.assertEqual(ca.args.settingsWriteStyle, "full")

    def test_cloneArmiRunCommandBatchInvokeShort(self):
        # Test short write style
        ca = CloneArmiRunCommandBatch()
        ca.addOptions()
        ca.parse_args([ARMI_RUN_PATH])

        with TemporaryDirectoryChanger():
            ca.invoke()

            self.assertEqual(ca.settingsArgument, "required")
            self.assertEqual(ca.args.settingsWriteStyle, "short")
            clonedYaml = "armiRun.yaml"
            self.assertTrue(os.path.exists(clonedYaml))
            # validate a setting that has a default value was removed
            txt = open(clonedYaml, "r").read()
            self.assertNotIn("availabilityFactor", txt)

    def test_cloneArmiRunCommandBatchInvokeMedium(self):
        """Test the "clone armi run" batch entry point, on medium detail.

        .. test:: A working CLI child class, to clone a run.
            :id: T_ARMI_CLI_GEN2
            :tests: R_ARMI_CLI_GEN
        """
        # Test medium write style
        ca = CloneArmiRunCommandBatch()
        ca.addOptions()
        ca.parse_args([ARMI_RUN_PATH, "--settingsWriteStyle", "medium"])

        with TemporaryDirectoryChanger():
            ca.invoke()

            self.assertEqual(ca.settingsArgument, "required")
            self.assertEqual(ca.args.settingsWriteStyle, "medium")
            clonedYaml = "armiRun.yaml"
            self.assertTrue(os.path.exists(clonedYaml))
            # validate a setting that has a  default value is still there
            txt = open(clonedYaml, "r").read()
            self.assertIn("availabilityFactor", txt)


class TestCloneSuiteCommand(unittest.TestCase):
    def test_cloneSuiteCommandBasics(self):
        cs = CloneSuiteCommand()
        cs.addOptions()
        cs.parse_args(["-d", "test", "--settingsWriteStyle", "medium"])

        self.assertEqual(cs.name, "clone-suite")
        self.assertEqual(cs.args.directory, "test")
        self.assertEqual(cs.args.settingsWriteStyle, "medium")


class TestCompareCases(unittest.TestCase):
    def test_compareCasesBasics(self):
        with TemporaryDirectoryChanger():
            cc = CompareCases()
            cc.addOptions()
            cc.parse_args(["/path/to/fake1.h5", "/path/to/fake2.h5"])

            self.assertEqual(cc.name, "compare")
            self.assertIsNone(cc.args.timestepCompare)
            self.assertIsNone(cc.args.weights)

            with self.assertRaises(ValueError):
                # The "fake" files do exist, so this should fail.
                cc.invoke()


class TestCompareSuites(unittest.TestCase):
    def test_compareSuitesBasics(self):
        with TemporaryDirectoryChanger():
            cs = CompareSuites()
            cs.addOptions()
            cs.parse_args(["/path/to/fake1.h5", "/path/to/fake2.h5", "-I"])

            self.assertEqual(cs.name, "compare-suites")
            self.assertEqual(cs.args.reference, "/path/to/fake1.h5")
            self.assertTrue(cs.args.skip_inspection)
            self.assertIsNone(cs.args.weights)


class TestExpandBlueprints(unittest.TestCase):
    def test_expandBlueprintsBasics(self):
        ebp = ExpandBlueprints()
        ebp.addOptions()
        ebp.parse_args(["/path/to/fake.yaml"])

        self.assertEqual(ebp.name, "expand-bp")
        self.assertEqual(ebp.args.blueprints, "/path/to/fake.yaml")

        # Since the file is fake, invoke() should exit early.
        with mockRunLogs.BufferLog() as mock:
            runLog.LOG.startLog("test_expandBlueprintsBasics")
            runLog.LOG.setVerbosity(logging.INFO)
            self.assertEqual("", mock.getStdout())
            ebp.invoke()
            self.assertIn("does not exist", mock.getStdout())


class TestExtractInputs(unittest.TestCase):
    def test_extractInputsBasics(self):
        with TemporaryDirectoryChanger() as newDir:
            # build test DB
            o, r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
            dbi = DatabaseInterface(r, o.cs)
            dbPath = os.path.join(newDir.destination, f"{self._testMethodName}.h5")
            dbi.initDB(fName=dbPath)
            db = dbi.database
            db.writeToDB(r)

            # init the CLI
            ei = ExtractInputs()
            ei.addOptions()
            ei.parse_args([dbPath])

            # test the CLI initialization
            self.assertEqual(ei.name, "extract-inputs")
            self.assertEqual(ei.args.output_base, dbPath[:-3])

            # run the CLI on a test DB, verify it worked via logging
            with mockRunLogs.BufferLog() as mock:
                runLog.LOG.startLog("test_extractInputsBasics")
                runLog.LOG.setVerbosity(logging.INFO)
                self.assertEqual("", mock.getStdout())
                ei.invoke()
                self.assertIn("Writing settings to", mock.getStdout())
                self.assertIn("Writing blueprints to", mock.getStdout())

            db.close()


class TestInjectInputs(unittest.TestCase):
    def test_injectInputsBasics(self):
        ii = InjectInputs()
        ii.addOptions()
        ii.parse_args(["/path/to/fake.h5"])

        self.assertEqual(ii.name, "inject-inputs")
        self.assertIsNone(ii.args.blueprints)

    def test_injectInputsInvokeIgnore(self):
        ii = InjectInputs()
        ii.addOptions()
        ii.parse_args(["/path/to/fake.h5"])

        with mockRunLogs.BufferLog() as mock:
            runLog.LOG.startLog("test_injectInputsInvokeIgnore")
            runLog.LOG.setVerbosity(logging.INFO)
            self.assertEqual("", mock.getStdout())
            ii.invoke()
            self.assertIn("No settings", mock.getStdout())

    def test_injectInputsInvokeNoData(self):
        with TemporaryDirectoryChanger():
            # init CLI
            ii = InjectInputs()
            ii.addOptions()

            bp = os.path.join(TEST_ROOT, "refSmallReactor.yaml")
            ii.parse_args(["/path/to/fake.h5", "--blueprints", bp])

            # invoke and check log
            with self.assertRaises(FileNotFoundError):
                # The "fake.h5" doesn't exist, so this should fail.
                ii.invoke()


class TestMigrateInputs(unittest.TestCase):
    def test_migrateInputsBasics(self):
        mi = MigrateInputs()
        mi.addOptions()
        mi.parse_args(["--settings-path", "cs_path"])

        self.assertEqual(mi.name, "migrate-inputs")
        self.assertEqual(mi.args.settings_path, "cs_path")


class TestModifyCaseSettingsCommand(unittest.TestCase):
    def test_modifyCaseSettingsCommandBasics(self):
        mcs = ModifyCaseSettingsCommand()
        mcs.addOptions()
        mcs.parse_args(["--rootDir", "/path/to/", "--settingsWriteStyle", "medium", "fake.yaml"])

        self.assertEqual(mcs.name, "modify")
        self.assertEqual(mcs.args.rootDir, "/path/to/")
        self.assertEqual(mcs.args.settingsWriteStyle, "medium")
        self.assertEqual(mcs.args.patterns, ["fake.yaml"])

    def test_modifyCaseSettingsCommandInvoke(self):
        mcs = ModifyCaseSettingsCommand()
        mcs.addOptions()

        with TemporaryDirectoryChanger():
            # copy over settings files
            for fileName in [
                "armiRun.yaml",
                "refSmallReactor.yaml",
                "refSmallReactorShuffleLogic.py",
            ]:
                copyfile(os.path.join(TEST_ROOT, fileName), fileName)

            # pass in --nTasks=333
            mcs.parse_args(["--nTasks=333", "--rootDir", ".", "armiRun.yaml"])

            # invoke the CLI
            mcs.invoke()

            # validate the change to nTasks was made
            txt = open("armiRun.yaml", "r").read()
            self.assertIn("nTasks: 333", txt)


class MockFakeReportsEntryPoint(ReportsEntryPoint):
    name = "MockFakeReport"

    def invoke(self):
        return "mock fake"


class TestReportsEntryPoint(unittest.TestCase):
    def test_cleanArgs(self):
        rep = MockFakeReportsEntryPoint()
        result = rep.invoke()
        self.assertEqual(result, "mock fake")


class TestCompareIsotxsLibsEntryPoint(unittest.TestCase):
    def test_compareIsotxsLibsBasics(self):
        com = CompareIsotxsLibraries()
        com.addOptions()
        com.parse_args(["--fluxFile", "/path/to/fluxfile.txt", "reference", "comparisonFiles"])

        self.assertEqual(com.name, "diff-isotxs")
        self.assertIsNone(com.settingsArgument)

        with self.assertRaises(FileNotFoundError):
            # The provided files don't exist, so this should fail.
            com.invoke()


class TestRunEntryPoint(unittest.TestCase):
    def test_runEntryPointBasics(self):
        rep = RunEntryPoint()
        rep.addOptions()
        rep.parse_args([ARMI_RUN_PATH])

        self.assertEqual(rep.name, "run")
        self.assertEqual(rep.settingsArgument, "required")

    def test_runCommandHelp(self):
        """Ensure main entry point with no args completes."""
        with self.assertRaises(SystemExit) as excinfo:
            # have to override the pytest args
            sys.argv = [""]
            main()
        self.assertEqual(excinfo.exception.code, 0)

    def test_executeCommand(self):
        """Use executeCommand to call run.

        But we expect it to fail because we provide a fictional settings YAML.
        """
        with self.assertRaises(SystemExit) as excinfo:
            # override the pytest args
            sys.argv = ["run", "path/to/fake.yaml"]
            main()
        self.assertEqual(excinfo.exception.code, 1)


class TestRunSuiteCommand(unittest.TestCase):
    def test_runSuiteCommandBasics(self):
        rs = RunSuiteCommand()
        rs.addOptions()
        rs.parse_args(["/path/to/fake.yaml", "-l"])

        self.assertEqual(rs.name, "run-suite")
        self.assertIsNone(rs.settingsArgument)

        # test the invoke method
        with mockRunLogs.BufferLog() as mock:
            runLog.LOG.startLog("test_runSuiteCommandBasics")
            runLog.LOG.setVerbosity(logging.INFO)
            self.assertEqual("", mock.getStdout())
            rs.invoke()
            self.assertIn("Finding potential settings files", mock.getStdout())
            self.assertIn("Checking for valid settings", mock.getStdout())
            self.assertIn("Primary Log Verbosity", mock.getStdout())


class TestVisFileEntryPointCommand(unittest.TestCase):
    def test_visFileEntryPointBasics(self):
        with TemporaryDirectoryChanger() as newDir:
            # build test DB
            self.o, self.r = loadTestReactor(
                TEST_ROOT,
                customSettings={"reloadDBName": "reloadingDB.h5"},
                inputFileName="smallestTestReactor/armiRunSmallest.yaml",
            )
            reduceTestReactorRings(self.r, self.o.cs, maxNumRings=2)
            self.dbi = DatabaseInterface(self.r, self.o.cs)
            dbPath = os.path.join(newDir.destination, f"{self._testMethodName}.h5")
            self.dbi.initDB(fName=dbPath)
            self.db = self.dbi.database
            self.db.writeToDB(self.r)

            # create Viz entry point
            vf = VisFileEntryPoint()
            vf.addOptions()
            vf.parse_args([dbPath])

            self.assertEqual(vf.name, "vis-file")
            self.assertIsNone(vf.settingsArgument)

            # test the invoke method
            with mockRunLogs.BufferLog() as mock:
                runLog.LOG.startLog("test_visFileEntryPointBasics")
                runLog.LOG.setVerbosity(logging.INFO)
                self.assertEqual("", mock.getStdout())

                vf.invoke()

                desired = "Creating visualization file for cycle 0, time node 0..."
                self.assertIn(desired, mock.getStdout())

            # test the parse method (using the same DB to save time)
            vf = VisFileEntryPoint()
            vf.parse([dbPath])
            self.assertIsNone(vf.args.nodes)
            self.assertIsNone(vf.args.min_node)
            self.assertIsNone(vf.args.max_node)
            self.assertEqual(vf.args.output_name, "test_visFileEntryPointBasics")

            self.db.close()
