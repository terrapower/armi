# Copyright 2020 TerraPower, LLC
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
# limitations under the License0.
"""Testing the settingsIO."""
import datetime
import io
import os
import unittest

from armi import context, settings
from armi.cli import entryPoint
from armi.settings import setting, settingsIO
from armi.tests import TEST_ROOT
from armi.utils import directoryChangers
from armi.utils.customExceptions import (
    InvalidSettingsFileError,
    NonexistentSetting,
    SettingException,
)


class SettingsFailureTests(unittest.TestCase):
    def test_settingsObjSetting(self):
        sets = settings.Settings()
        with self.assertRaises(NonexistentSetting):
            sets[
                "idontexist"
            ] = "this test should fail because no setting named idontexist should exist."

    def test_loadFromYamlFailsOnBadNames(self):
        ss = settings.Settings()
        with self.assertRaises(TypeError):
            ss.loadFromInputFile(None)
        with self.assertRaises(IOError):
            ss.loadFromInputFile("this-settings-file-does-not-exist.yaml")

    def test_invalidFile(self):
        with self.assertRaises(InvalidSettingsFileError):
            cs = settings.caseSettings.Settings()
            reader = settingsIO.SettingsReader(cs)
            reader.readFromStream(io.StringIO("useless:\n    should_fail"))


class SettingsReaderTests(unittest.TestCase):
    def setUp(self):
        self.cs = settings.caseSettings.Settings()

    def test_basicSettingsReader(self):
        reader = settingsIO.SettingsReader(self.cs)

        self.assertEqual(reader["nTasks"], 1)
        self.assertEqual(reader["nCycles"], 1)

        self.assertFalse(getattr(reader, "filelessBP"))
        self.assertEqual(getattr(reader, "path"), "")

    def test_readFromFile(self):
        """Read settings from a (human-readable) YAML file.

        .. test:: Settings can be input from a human-readable text file.
            :id: T_ARMI_SETTINGS_IO_TXT0
            :tests: R_ARMI_SETTINGS_IO_TXT
        """
        with directoryChangers.TemporaryDirectoryChanger():
            inPath = os.path.join(TEST_ROOT, "armiRun.yaml")
            outPath = "test_readFromFile.yaml"

            txt = open(inPath, "r").read()
            verb = "branchVerbosity:"
            txt0, txt1 = txt.split(verb)
            newTxt = f"{txt0}{verb} fake\n  {verb}{txt1}"
            open(outPath, "w").write(newTxt)

            with self.assertRaises(InvalidSettingsFileError):
                settings.caseSettings.Settings(outPath)


class SettingsRenameTests(unittest.TestCase):
    testSettings = [
        setting.Setting(
            "testSetting1",
            default=None,
            oldNames=[("oSetting1", None), ("osetting1", datetime.date.today())],
            description="Just a unit test setting.",
        ),
        setting.Setting(
            "testSetting2",
            default=None,
            oldNames=[("oSetting2", None)],
            description="Just a unit test setting.",
        ),
        setting.Setting(
            "testSetting3",
            default=None,
            description="Just a unit test setting.",
        ),
    ]

    def test_rename(self):
        renamer = settingsIO.SettingRenamer(
            {setting.name: setting for setting in self.testSettings}
        )

        self.assertEqual(renamer.renameSetting("testSetting1"), ("testSetting1", False))
        self.assertEqual(renamer.renameSetting("oSetting1"), ("testSetting1", True))
        # this one is expired
        self.assertEqual(renamer.renameSetting("osetting1"), ("osetting1", False))
        self.assertEqual(renamer.renameSetting("oSetting2"), ("testSetting2", True))
        self.assertEqual(renamer.renameSetting("testSetting2"), ("testSetting2", False))
        self.assertEqual(renamer.renameSetting("testSetting3"), ("testSetting3", False))

        # No rename; let it through
        self.assertEqual(renamer.renameSetting("boo!"), ("boo!", False))

    def test_collidingRenames(self):
        settings = {
            setting.name: setting
            for setting in self.testSettings
            + [
                setting.Setting(
                    "someOtherSetting",
                    default=None,
                    oldNames=[("oSetting1", None)],
                    description="Just a unit test setting.",
                )
            ]
        }
        with self.assertRaises(SettingException):
            _ = settingsIO.SettingRenamer(settings)


class SettingsWriterTests(unittest.TestCase):
    def setUp(self):
        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()
        self.init_mode = context.CURRENT_MODE
        self.filepathYaml = os.path.join(
            os.getcwd(), self._testMethodName + "test_setting_io.yaml"
        )
        self.cs = settings.Settings()
        self.cs = self.cs.modified(newSettings={"nCycles": 55})

    def tearDown(self):
        context.Mode.setMode(self.init_mode)
        self.td.__exit__(None, None, None)

    def test_writeShort(self):
        """Setting output as a sparse file."""
        self.cs.writeToYamlFile(self.filepathYaml, style="short")
        self.cs.loadFromInputFile(self.filepathYaml)
        txt = open(self.filepathYaml, "r").read()
        self.assertIn("nCycles: 55", txt)
        self.assertNotIn("nTasks", txt)

    def test_writeMedium(self):
        """Setting output as a sparse file that only includes defaults if they are
        user-specified.
        """
        with open(self.filepathYaml, "w") as stream:
            # Specify a setting that is also a default
            self.cs.writeToYamlStream(stream, "medium", ["nTasks"])
        txt = open(self.filepathYaml, "r").read()
        self.assertIn("nCycles: 55", txt)
        self.assertIn("nTasks: 1", txt)

    def test_writeFull(self):
        """Setting output as a full, all defaults included file.

        .. test:: Settings can be output to a human-readable text file.
            :id: T_ARMI_SETTINGS_IO_TXT1
            :tests: R_ARMI_SETTINGS_IO_TXT
        """
        self.cs.writeToYamlFile(self.filepathYaml, style="full")
        txt = open(self.filepathYaml, "r").read()
        self.assertIn("nCycles: 55", txt)
        # check a default setting
        self.assertIn("nTasks: 1", txt)

    def test_writeYaml(self):
        self.cs.writeToYamlFile(self.filepathYaml)
        self.cs.loadFromInputFile(self.filepathYaml)
        self.assertEqual(self.cs["nCycles"], 55)

    def test_errorSettingsWriter(self):
        with self.assertRaises(ValueError):
            _ = settingsIO.SettingsWriter(self.cs, "wrong")


class MockEntryPoint(entryPoint.EntryPoint):
    name = "dummy"


class SettingArgsTests(unittest.TestCase):
    def setUp(self):
        self.cs = None

    def test_commandLineSetting(self):
        ep = MockEntryPoint()
        self.cs = cs = ep.cs

        self.assertEqual(cs["nCycles"], 1)
        ep.createOptionFromSetting("nCycles")
        ep.parse_args(["--nCycles", "5"])
        self.assertEqual(cs["nCycles"], 5)

    def test_cannotLoadSettingsAfterParsingCLI(self):
        self.test_commandLineSetting()

        with self.assertRaises(RuntimeError):
            self.cs.loadFromInputFile("somefile.yaml")
