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
# limitations under the License.

import os
import unittest

import armi
from armi.cli import entryPoint
from armi.utils import directoryChangers
from armi import settings
from armi.settings import setting
from armi.localization import exceptions


class SettingsFailureTests(unittest.TestCase):
    def test_settingsObjSetting(self):
        sets = settings.Settings()
        with self.assertRaises(exceptions.NonexistentSetting):
            sets[
                "idontexist"
            ] = "this test should fail because no setting named idontexist should exist."

    def test_loadFromXmlFailsOnBadNames(self):
        ss = settings.Settings()
        with self.assertRaises(TypeError):
            ss.loadFromInputFile(None)
        with self.assertRaises(IOError):
            ss.loadFromInputFile("this-settings-file-does-not-exist.xml")


class SettingsWriterTests(unittest.TestCase):
    def setUp(self):
        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()
        self.init_mode = armi.CURRENT_MODE
        self.filepathXml = os.path.join(
            os.getcwd(), self._testMethodName + "test_setting_io.xml"
        )
        self.filepathYaml = os.path.join(
            os.getcwd(), self._testMethodName + "test_setting_io.yaml"
        )
        self.cs = settings.Settings()
        self.cs["nCycles"] = 55

    def tearDown(self):
        armi.Mode.setMode(self.init_mode)
        self.td.__exit__(None, None, None)

    def test_writeShorthand(self):
        """Setting output as a sparse file"""
        self.cs.writeToXMLFile(self.filepathXml, style="short")
        self.cs.loadFromInputFile(self.filepathXml)
        self.assertEqual(self.cs["nCycles"], 55)

    def test_writeYaml(self):
        self.cs.writeToYamlFile(self.filepathYaml)
        self.cs.loadFromInputFile(self.filepathYaml)
        self.assertEqual(self.cs["nCycles"], 55)


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

        with self.assertRaises(exceptions.StateError):
            self.cs.loadFromInputFile("somefile.xml")

