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
Test for run cli entry point.
"""
# pylint: disable=protected-access,missing-function-docstring,missing-class-docstring
from shutil import copyfile
import os
import sys
import unittest

from armi.__main__ import main
from armi.cli.entryPoint import EntryPoint
from armi.bookkeeping.visualization.entryPoint import VisFileEntryPoint
from armi.cli.checkInputs import CheckInputEntryPoint, ExpandBlueprints
from armi.cli.clone import CloneArmiRunCommandBatch, CloneSuiteCommand
from armi.cli.compareCases import CompareCases, CompareSuites
from armi.cli.database import ConvertDB, ExtractInputs, InjectInputs
from armi.cli.migrateInputs import MigrateInputs
from armi.cli.modify import ModifyCaseSettingsCommand
from armi.cli.reportsEntryPoint import ReportsEntryPoint
from armi.cli.run import RunEntryPoint
from armi.cli.runSuite import RunSuiteCommand
from armi.physics.neutronics.diffIsotxs import CompareIsotxsLibraries
from armi.tests import mockRunLogs, TEST_ROOT, ARMI_RUN_PATH
from armi.utils.directoryChangers import TemporaryDirectoryChanger
from armi.utils.dynamicImporter import getEntireFamilyTree


class TestInitializationEntryPoints(unittest.TestCase):
    def test_entryPointInitialization(self):
        """Tests the initialization of all subclasses of `EntryPoint`."""
        entryPoints = getEntireFamilyTree(EntryPoint)

        # Note that this is a hard coded number that should be incremented
        # if a new ARMI framework entry point is added. This is a bit hacky,
        # but will help demonstrate that entry point classes can be initialized
        # and the `addOptions` and public API is tested.
        self.assertEqual(len(entryPoints), 18)

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
                        f"but does not exist. This is a error in the EntryPoint "
                        f"implementation."
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
        self.assertEqual(ci.args.generate_design_summary, False)

    def test_checkInputEntryPointInvoke(self):
        ci = CheckInputEntryPoint()
        ci.addOptions()
        ci.parse_args([ARMI_RUN_PATH])

        with mockRunLogs.BufferLog() as mock:
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
        cc = CompareCases()
        cc.addOptions()
        cc.parse_args(["/path/to/fake1.h5", "/path/to/fake2.h5"])

        self.assertEqual(cc.name, "compare")
        self.assertIsNone(cc.args.timestepCompare)
        self.assertIsNone(cc.args.weights)


class TestCompareSuites(unittest.TestCase):
    def test_compareSuitesBasics(self):
        cs = CompareSuites()
        cs.addOptions()
        cs.parse_args(["/path/to/fake1.h5", "/path/to/fake2.h5"])

        self.assertEqual(cs.name, "compare-suites")
        self.assertEqual(cs.args.reference, "/path/to/fake1.h5")
        self.assertIsNone(cs.args.weights)


class TestConvertDB(unittest.TestCase):
    def test_convertDbBasics(self):
        cdb = ConvertDB()
        cdb.addOptions()
        cdb.parse_args(["/path/to/fake.h5"])

        self.assertEqual(cdb.name, "convert-db")
        self.assertEqual(cdb.args.output_version, "3")
        self.assertIsNone(cdb.args.nodes)

        # Since the file is fake, invoke() should exit early.
        with mockRunLogs.BufferLog() as mock:
            cdb.args.nodes = [1, 2, 3]
            with self.assertRaises(ValueError):
                cdb.invoke()
            self.assertIn("Converting the", mock.getStdout())

    def test_convertDbOutputVersion(self):
        cdb = ConvertDB()
        cdb.addOptions()
        cdb.parse_args(["/path/to/fake.h5", "--output-version", "XtView"])
        self.assertEqual(cdb.args.output_version, "2")

    def test_convertDbOutputNodes(self):
        cdb = ConvertDB()
        cdb.addOptions()
        cdb.parse_args(["/path/to/fake.h5", "--nodes", "(1,2)"])
        self.assertEqual(cdb.args.nodes, [(1, 2)])


class TestExpandBlueprints(unittest.TestCase):
    def test_expandBlueprintsBasics(self):
        ebp = ExpandBlueprints()
        ebp.addOptions()
        ebp.parse_args(["/path/to/fake.yaml"])

        self.assertEqual(ebp.name, "expand-bp")
        self.assertEqual(ebp.args.blueprints, "/path/to/fake.yaml")

        # Since the file is fake, invoke() should exit early.
        with mockRunLogs.BufferLog() as mock:
            self.assertEqual("", mock.getStdout())
            ebp.invoke()
            self.assertIn("does not exist", mock.getStdout())


class TestExtractInputs(unittest.TestCase):
    def test_extractInputsBasics(self):
        ei = ExtractInputs()
        ei.addOptions()
        ei.parse_args(["/path/to/fake.h5"])

        self.assertEqual(ei.name, "extract-inputs")
        self.assertEqual(ei.args.output_base, "/path/to/fake")


class TestInjectInputs(unittest.TestCase):
    def test_injectInputsBasics(self):
        ii = InjectInputs()
        ii.addOptions()
        ii.parse_args(["/path/to/fake.h5"])

        self.assertEqual(ii.name, "inject-inputs")
        self.assertIsNone(ii.args.blueprints)


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
        mcs.parse_args(
            ["--rootDir", "/path/to/", "--settingsWriteStyle", "medium", "fake.yaml"]
        )

        self.assertEqual(mcs.name, "modify")
        self.assertEqual(mcs.args.rootDir, "/path/to/")
        self.assertEqual(mcs.args.settingsWriteStyle, "medium")
        self.assertEqual(mcs.args.patterns, ["fake.yaml"])

    def test_modifyCaseSettingsCommandInvoke(self):
        mcs = ModifyCaseSettingsCommand()
        mcs.addOptions()

        with TemporaryDirectoryChanger():
            # copy over settings files
            for fileName in ["armiRun.yaml", "refSmallReactor.yaml"]:
                copyfile(os.path.join(TEST_ROOT, fileName), fileName)

            # pass in --numProcessors=333
            mcs.parse_args(["--numProcessors=333", "--rootDir", ".", "armiRun.yaml"])

            # invoke the CLI
            mcs.invoke()

            # validate the change to numProcessors was made
            txt = open("armiRun.yaml", "r").read()
            self.assertIn("numProcessors: 333", txt)


class TestReportsEntryPoint(unittest.TestCase):
    def test_reportsEntryPointBasics(self):
        rep = ReportsEntryPoint()
        rep.addOptions()
        rep.parse_args(["-h5db", "/path/to/fake.yaml"])

        self.assertEqual(rep.name, "report")
        self.assertEqual(rep.settingsArgument, "optional")


class TestCompareIsotxsLibsEntryPoint(unittest.TestCase):
    def test_compareIsotxsLibsBasics(self):
        com = CompareIsotxsLibraries()
        com.addOptions()
        com.parse_args(
            ["--fluxFile", "/path/to/fluxfile.txt", "reference", "comparisonFiles"]
        )

        self.assertEqual(com.name, "diff-isotxs")
        self.assertIsNone(com.settingsArgument)


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
        rs.parse_args(["/path/to/fake.yaml"])

        self.assertEqual(rs.name, "run-suite")
        self.assertIsNone(rs.settingsArgument)


class TestVisFileEntryPointCommand(unittest.TestCase):
    def test_visFileEntryPointBasics(self):
        vf = VisFileEntryPoint()
        vf.addOptions()
        vf.parse_args(["/path/to/fake.h5"])

        self.assertEqual(vf.name, "vis-file")
        self.assertIsNone(vf.settingsArgument)
