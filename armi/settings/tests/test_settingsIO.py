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
""" Testing the settingsIO """
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access

import datetime
import io
import os
import unittest

from armi import context
from armi import settings
from armi.cli import entryPoint
from armi.settings import setting
from armi.settings import settingsIO
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
            reader.readFromStream(
                io.StringIO("useless:\n    should_fail"),
                fmt=settingsIO.SettingsReader.SettingsInputFormat.YAML,
            )


class SettingsReaderTests(unittest.TestCase):
    def setUp(self):
        self.cs = settings.caseSettings.Settings()

    def test_basicSettingsReader(self):
        reader = settingsIO.SettingsReader(self.cs)

        self.assertEqual(reader["numProcessors"], 1)
        self.assertEqual(reader["nCycles"], 1)

        self.assertFalse(getattr(reader, "filelessBP"))
        self.assertEqual(getattr(reader, "path"), "")


class SettingsRenameTests(unittest.TestCase):
    testSettings = [
        setting.Setting(
            "testSetting1",
            default=None,
            oldNames=[("oSetting1", None), ("osetting1", datetime.date.today())],
        ),
        setting.Setting("testSetting2", default=None, oldNames=[("oSetting2", None)]),
        setting.Setting("testSetting3", default=None),
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
                    "someOtherSetting", default=None, oldNames=[("oSetting1", None)]
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

    def test_writeShorthand(self):
        """Setting output as a sparse file"""
        self.cs.writeToYamlFile(self.filepathYaml, style="short")
        self.cs.loadFromInputFile(self.filepathYaml)
        self.assertEqual(self.cs["nCycles"], 55)

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

    def test_cannotLoadSettingsAfterParsingCommandLineSetting(self):
        self.test_commandLineSetting()

        with self.assertRaises(RuntimeError):
            self.cs.loadFromInputFile("somefile.yaml")
