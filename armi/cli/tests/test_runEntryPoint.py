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
Test for run cli entry point
"""
# pylint: disable=protected-access,missing-function-docstring,missing-class-docstring
import sys
import unittest

from armi.__main__ import main
from armi.cli.checkInputs import CheckInputEntryPoint, ExpandBlueprints
from armi.cli.clone import CloneArmiRunCommandBatch, CloneSuiteCommand
from armi.cli.compareCases import CompareCases, CompareSuites
from armi.cli.copyDB import CopyDB
from armi.cli.database import ConvertDB, ExtractInputs, InjectInputs
from armi.cli.migrateInputs import MigrateInputs
from armi.cli.modify import ModifyCaseSettingsCommand
from armi.cli.reportsEntryPoint import ReportsEntryPoint
from armi.cli.run import RunEntryPoint
from armi.cli.runSuite import RunSuiteCommand


class TestCheckInputEntryPoint(unittest.TestCase):
    def test_checkInputEntryPointBasics(self):
        ci = CheckInputEntryPoint()
        ci.addOptions()
        ci.parse_args(["/path/to/fake.yaml"])

        self.assertEqual(ci.name, "check-input")
        self.assertEqual(ci.settingsArgument, "optional")


class TestCloneArmiRunCommandBatch(unittest.TestCase):
    def test_cloneArmiRunCommandBatchBasics(self):
        ca = CloneArmiRunCommandBatch()
        ca.addOptions()
        ca.parse_args(["--additional-files", "test"])

        self.assertEqual(ca.name, "clone-batch")
        self.assertEqual(ca.settingsArgument, "required")


class TestCloneSuiteCommand(unittest.TestCase):
    def test_cloneSuiteCommandBasics(self):
        cs = CloneSuiteCommand()
        cs.addOptions()
        cs.parse_args(["-d", "test"])

        self.assertEqual(cs.name, "clone-suite")


class TestCompareCases(unittest.TestCase):
    def test_compareCasesBasics(self):
        cc = CompareCases()
        cc.addOptions()
        cc.parse_args(["/path/to/fake1.h5", "/path/to/fake2.h5"])

        self.assertEqual(cc.name, "compare")
        self.assertIsNone(cc.args.timestepMatchup)
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
        self.assertIsNone(cdb.args.nodes)


class TestCopyDB(unittest.TestCase):
    def test_copyDBBasics(self):
        cdb = CopyDB()
        cdb.addOptions()
        cdb.parse_args(["cs_path", "/path/to/fake1.h5", "/path/to/fake2.h5"])

        self.assertEqual(cdb.name, "copy-db")
        self.assertEqual(cdb.args.csPath, "cs_path")
        self.assertEqual(cdb.args.srcDB, "/path/to/fake1.h5")
        self.assertEqual(cdb.args.tarDB, "/path/to/fake2.h5")


class TestExpandBlueprints(unittest.TestCase):
    def test_expandBlueprintsBasics(self):
        eb = ExpandBlueprints()
        eb.addOptions()
        eb.parse_args(["/path/to/fake.yaml"])

        self.assertEqual(eb.name, "expand-bp")
        self.assertEqual(eb.args.blueprints, "/path/to/fake.yaml")


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
        mcs.parse_args(["/path/to/fake.yaml"])

        self.assertEqual(mcs.name, "modify")
        self.assertEqual(mcs.args.patterns, ["/path/to/fake.yaml"])


class TestReportsEntryPoint(unittest.TestCase):
    def test_reportsEntryPointBasics(self):
        rep = ReportsEntryPoint()
        rep.addOptions()
        rep.parse_args(["-h5db", "/path/to/fake.yaml"])

        self.assertEqual(rep.name, "report")
        self.assertEqual(rep.settingsArgument, "optional")


class TestRunEntryPoint(unittest.TestCase):
    def test_runEntryPointBasics(self):
        rep = RunEntryPoint()
        rep.addOptions()
        rep.parse_args([])

        self.assertEqual(rep.name, "run")
        self.assertEqual(rep.settingsArgument, "required")

    def test_runCommand(self):
        """Ensure main entry point with no args completes."""
        with self.assertRaises(SystemExit) as excinfo:
            sys.argv = [""]  # have to override the pytest args
            main()
        self.assertEqual(excinfo.exception.code, 0)


class TestRunSuiteCommand(unittest.TestCase):
    def test_runSuiteCommandBasics(self):
        rs = RunSuiteCommand()
        rs.addOptions()
        rs.parse_args(["/path/to/fake.yaml"])

        self.assertEqual(rs.name, "run-suite")
        self.assertIsNone(rs.settingsArgument)


if __name__ == "__main__":
    unittest.main()
