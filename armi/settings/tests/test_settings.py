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

import pickle
import os
import unittest

import six

import armi
from armi import settings
from armi.cli import entryPoint
from armi.localization import exceptions
from armi.settings import setting
from armi.settings import settingsIO
from armi.settings import settingsRules
from armi.tests import TEST_ROOT, ARMI_RUN_PATH


class MockEntryPoint(entryPoint.EntryPoint):
    name = "dummy"


class TestSettings(unittest.TestCase):
    """Test the functionality of Settings.py"""

    @classmethod
    def setUpClass(cls):
        cls.tS = settings.Settings()

    def setUp(self):
        self.tS.settings["fruitBasket"] = setting.ListSetting(
            "fruitBasket", {"type": "list", "default": ["apple", "banana", "orange"]}
        )

        self.resetPoint = self.tS.keys()

    def tearDown(self):
        for i in self.tS.keys():
            if i not in self.resetPoint:
                if i in self.tS.settings:
                    del self.tS.settings[i]

    def test_canPickleCS(self):
        self.tS["xsKernel"] = "MC2v3"
        result = pickle.loads(pickle.dumps(self.tS))
        self.assertEqual("MC2v3", result["xsKernel"])

    def test_userInputXML(self):
        """Asserts that the state of the settings object is altered by loading an input of XML as a
        means of user specifications.

        :ref:`REQbdb2e558-70b5-4ddb-aff9-d7a7b6d0e360`
        """
        mock = settings.Settings()
        mock.settings["newSetting"] = setting.FloatSetting(
            "newSetting",
            {
                "description": "Hola",
                "label": "hello",
                "type": "float",
                "default": "2.0",
            },
        )
        # make sure everything is as expected
        self.assertEqual(2.0, mock["newSetting"])

        # read "user input xml"
        xml = six.StringIO('<settings><newSetting value="17"/></settings>')
        reader = settingsIO.SettingsReader(mock)
        reader.readFromStream(xml, fmt=reader.SettingsInputFormat.XML)
        self.assertEqual(17.0, mock["newSetting"])

    def test_setSetting(self):
        self.tS["fruitBasket"] = ["apple", "banana", "orange"]
        self.assertEqual(self.tS["fruitBasket"], ["apple", "banana", "orange"])

    def test_getSetting(self):
        """Test the retrieval of existing and nonexisting settings

        """
        if "nonExistentSetting" in self.tS.settings:
            del self.tS["nonExistentSetting"]
        with self.assertRaises(exceptions.NonexistentSetting):
            self.tS["nonExistentSetting"]

        self.tS.settings["existingSetting"] = setting.BoolSetting(
            "existingSetting", {"type": "bool", "default": "False"}
        )

        self.tS["existingSetting"] = True
        self.assertIsNotNone(self.tS["existingSetting"])

    def checkSettingsMatch(self, set1, set2, defaults=False):
        """Asserts that all settings existing in two separate instances match"""
        for key in set1.settings.keys():
            wSetting = set1.settings[key]
            rSetting = set2.settings[key]
            if defaults:
                self.assertEqual(
                    wSetting.getDefaultAttributes(), rSetting.getDefaultAttributes()
                )
            else:
                self.assertEqual(
                    wSetting.getCustomAttributes(), rSetting.getCustomAttributes()
                )

    @unittest.skip(
        "settings are no longer pickleable, but MPI does not seem to use pickling..."
    )
    def test_pickling(self):
        """Tests the settings can be pickled

        """
        pickled_string = pickle.dumps(self.tS)
        loaded_pickle = pickle.loads(pickled_string)

        self.checkSettingsMatch(self.tS, loaded_pickle, defaults=True)

    def test_duplicate(self):
        """Tests the duplication function

        """
        origSettings = settings.Settings()
        dupSettings = origSettings.duplicate()
        self.checkSettingsMatch(origSettings, dupSettings, defaults=True)

    def test_validDefault(self):
        """Tests the settings for a default value on each setting

        :ref:`REQ7adc1f94-a423-46ca-9aff-e2276d07faa5`
        """
        cs = settings.Settings()
        for key in cs.settings.keys():
            cs[key]  # pylint: disable=pointless-statement

    def test_commandLineSetting(self):
        ep = MockEntryPoint()
        cs = ep.cs

        someSetting = setting.FloatSetting(
            "someSetting", {"type": "float", "default": "47.0"}
        )
        cs.settings[someSetting.name] = someSetting
        self.assertEqual(47.0, cs["someSetting"])

        ep.createOptionFromSetting(someSetting.name)
        ep.parse_args(["--someSetting", "92"])
        self.assertEqual(92.0, cs["someSetting"])
        self.assertEqual(92.0, someSetting.value)

    def test_cannotLoadSettingsAfterParsingCommandLineSetting(self):
        self.test_commandLineSetting()
        cs = settings.getMasterCs()
        with self.assertRaises(exceptions.StateError):
            cs.loadFromInputFile("somefile.xml")

    def test_loadFromXMLFileUpdatesCaseTitle(self):
        cs = settings.Settings(fName=ARMI_RUN_PATH)
        self.assertEqual(cs.caseTitle, "armiRun")

    def test_temporarilySet(self):
        self.tS.temporarilySet("eigenProb", False)
        self.assertEqual(self.tS["eigenProb"], False)
        self.tS.unsetTemporarySettings()
        self.assertEqual(self.tS["eigenProb"], True)


class TestSetting(unittest.TestCase):
    """Test the functionality of Setting.py

    """

    def test_settingGeneric(self):
        """Individual setting test

        Should probe the creation of a setting and retention of the default attributes

        """
        key = "generic"
        attrib = {
            "type": "int",
            "default": "0",
            "description": "testbanana",
            "label": "banana",
            "ignored": "bananaNanana",
        }  # this attribute should do absolutely nothing

        # s = setting.Setting(attrib)
        s = setting.Setting.factory(key, attrib)

        self.assertIsInstance(s, setting.IntSetting)

        self.assertEqual(s.underlyingType, int)
        self.assertEqual(s.value, 0)
        self.assertEqual(s.default, 0)
        self.assertEqual(s.description, "testbanana")
        self.assertEqual(s.label, "banana")

    def test_settingBool(self):
        """Probes the creation, value change on a valid or invalid input and default value retention
        on Boolean type settings

        :ref:`REQ798b2869-ab59-4164-911c-0a26b3f9b037`
        """
        attribValues = {"type": "bool", "default": True}
        attribStrings = {"type": "bool", "default": "True"}
        sStrings = setting.BoolSetting("bugtester", attribStrings)
        sValues = setting.BoolSetting("bugtester", attribValues)

        self.assertEqual(
            True, sStrings.value, "The setting object does not have the correct value"
        )
        self.assertEqual(
            True, sValues.value, "The setting object does not have the correct value"
        )

        sStrings.setValue("False")
        sValues.setValue(False)
        self.assertEqual(
            False,
            sStrings.value,
            "The setting object does not have the correct value after setting",
        )
        self.assertEqual(
            False,
            sValues.value,
            "The setting object does not have the correct value after setting",
        )

        self.assertEqual(
            True,
            sStrings.default,
            "The setting object does not have the correct default value",
        )

        sValues.setValue(None)
        self.assertEqual(sValues.value, False)

        # --------- malicious input ----------
        attrib = {"type": "bool", "default": "blueberry"}

        with self.assertRaises(ValueError):
            setting.BoolSetting("bugMaker", attrib)

    def test_settingInt(self):
        """Probes the creation, value change on a valid or invalid input and default value retention
        on Integer type settings

        :ref:`REQ798b2869-ab59-4164-911c-0a26b3f9b037`
        """
        attribStrings = {"type": "int", "default": "5"}
        attribValues = {"type": "int", "default": 5}
        sStrings = setting.IntSetting("bugtester", attribStrings)
        sValues = setting.IntSetting("bugtester", attribValues)

        self.assertEqual(
            5, sStrings.value, "The setting object does not have the correct value"
        )
        self.assertEqual(
            5, sValues.value, "The setting object does not have the correct value"
        )

        sStrings.setValue("10")
        sValues.setValue(10)
        self.assertEqual(
            10,
            sStrings.value,
            "The setting object does not have the correct value after setting",
        )
        self.assertEqual(
            10,
            sValues.value,
            "The setting object does not have the correct value after setting",
        )

        sValues.setValue(1000000000000)  # that has to be a long, right?
        self.assertEqual(
            1000000000000,
            sValues.value,
            "The setting object does not have the correct long value",
        )

        self.assertEqual(
            5,
            sStrings.default,
            "The setting object does not have the correct default value",
        )

        sValues.setValue(None)
        self.assertEqual(sValues.value, 0)

        # --------- malicious input ----------
        attrib = {"type": "int", "default": "blueberry", "max": 5, "min": 1.0}

        with self.assertRaises(ValueError):
            setting.IntSetting("bugMaker", attrib)

        # should be out of range
        attrib["value"] = "6"
        with self.assertRaises(ValueError):
            setting.IntSetting("bugMaker", attrib)
        attrib["value"] = 0.5
        with self.assertRaises(ValueError):
            setting.IntSetting("bugMaker", attrib)
        attrib["value"] = 0
        with self.assertRaises(ValueError):
            setting.IntSetting("bugMaker", attrib)
        attrib["default"] = 3
        setting.IntSetting("bugMaker", attrib)

    def test_settingFloat(self):
        """Probes the creation, value change on a valid or invalid input and default value retention
        on Float type settings

        :ref:`REQ798b2869-ab59-4164-911c-0a26b3f9b037`
        """
        attribStrings = {"type": "float", "default": "5.0"}
        attribValues = {"type": "float", "default": 5.0}

        sStrings = setting.FloatSetting("bugtester", attribStrings)
        sValues = setting.FloatSetting("bugtester", attribValues)
        self.assertEqual(
            5.0, sStrings.value, "The setting object does not have the correct value"
        )
        self.assertEqual(
            5.0, sValues.value, "The setting object does not have the correct value"
        )

        sStrings.setValue("10.0")
        sValues.setValue(10.0)
        self.assertEqual(
            10.0,
            sStrings.value,
            "The setting object does not have the correct value after setting",
        )
        self.assertEqual(
            10.0,
            sValues.value,
            "The setting object does not have the correct value after setting",
        )

        self.assertEqual(
            5.0,
            sStrings.default,
            "The setting object does not have the correct default value",
        )

        sValues.setValue(None)
        self.assertEqual(sValues.value, 0.0)

        # --------- malicious input ----------
        attrib = {"type": "float", "default": "blueberry", "max": 5, "min": 1.0}

        attrib["default"] = "6"
        with self.assertRaises(ValueError):
            setting.FloatSetting("bugMaker", attrib)
        attrib["default"] = 0.5
        with self.assertRaises(ValueError):
            setting.FloatSetting("bugMaker", attrib)
        attrib["default"] = 0
        with self.assertRaises(ValueError):
            setting.FloatSetting("bugMaker", attrib)
        attrib["default"] = 3
        setting.FloatSetting("bugMaker", attrib)

    def test_settingStr(self):
        """Probes the creation, value change on a valid or invalid input and default value retention
        on String type settings

        :ref:`REQ798b2869-ab59-4164-911c-0a26b3f9b037`
        """
        attribStrings = {
            "type": "str",
            "default": "banana",
            "options": ["coconut", "apple", "banana"],
            "enforcedOptions": True,
        }
        attribValues = {
            "type": "str",
            "default": "5",
            "options": ["3", "20"],
            "enforcedOptions": False,
        }

        sStrings = setting.StrSetting("bugtester", attribStrings)
        sValues = setting.StrSetting("bugtester", attribValues)
        self.assertEqual(
            "banana",
            sStrings.value,
            "The setting object does not have the correct value",
        )
        self.assertEqual(
            "5", sValues.value, "The setting object does not have the correct value"
        )

        sStrings.setValue("apple")
        sValues.setValue("10")
        self.assertEqual(
            "apple",
            sStrings.value,
            "The setting object does not have the correct value after setting",
        )
        self.assertEqual(
            "10",
            sValues.value,
            "The setting object does not have the correct value after setting",
        )

        self.assertEqual(
            "banana",
            sStrings.default,
            "The setting object does not have the correct default value",
        )

        sValues.setValue(None)
        self.assertIsNone(sValues.value)

        # --------- malicious input ----------
        attrib = {
            "type": "str",
            "default": "blueberry",
            "options": "['coconut', 'banana', 'pineapple']",
            "enforcedOptions": "True",
        }

        with self.assertRaises(ValueError):
            setting.StrSetting("bugMaker", attrib)

    def test_settingPath(self):
        """Probes the creation, value change on a valid or invalid input and default value retention
        on Path type settings
        """
        attribStrings = {"type": "path", "default": "banana.txt", "relativeTo": "RES"}

        sStrings = setting.PathSetting("bugtester", attribStrings)
        self.assertEqual(
            os.path.join(armi.RES, "banana.txt"),
            sStrings.value,
            "The setting object does not have the correct value",
        )

        sStrings.setValue("apple.jpg")
        self.assertEqual(
            os.path.join(armi.RES, "apple.jpg"),
            sStrings.value,
            "The setting object does not have the correct value",
        )

        sStrings.setValue(None)
        self.assertIsNone(sStrings.value)

        # --------- malicious input ----------
        attrib = {"type": "path", "default": "blueberry", "mustExist": "True"}

        with self.assertRaises(ValueError):
            setting.PathSetting("bugMaker", attrib)

    def test_relativeToSettingPath(self):
        """Test the relative to functionality with and without a valid path"""
        fileName = "banana.txt"
        remoteFileLocation = os.path.join(TEST_ROOT, fileName)
        relativeAttribStrings = {
            "type": "path",
            "default": fileName,
            "relativeTo": "RES",
        }
        directAttribStrings = {
            "type": "path",
            "default": remoteFileLocation,
            "relativeTo": "RES",
        }
        sStrings = setting.PathSetting("relativePathTest", relativeAttribStrings)
        self.assertEqual(sStrings.value, os.path.join(armi.RES, fileName))
        with open(remoteFileLocation, "w") as f:
            f.write(
                "Temporary file to test that when a valid path is provided the setting will be directed to "
                "the input path rather than using the default relativeTo path."
            )
        sStrings = setting.PathSetting("directPathTest", directAttribStrings)
        self.assertEqual(sStrings.value, remoteFileLocation)
        os.remove(remoteFileLocation)

    def test_settingList(self):
        """Probes the creation, value change on a valid or invalid input and default value retention
        on List type settings

        :ref:`REQ798b2869-ab59-4164-911c-0a26b3f9b037`
        """
        attribStrings = {"type": "list", "default": "['5','6','4','5','7']"}
        attribValues = {
            "type": "list",
            "default": "['5','6',4,5,7]",
            "containedType": "int",
        }

        sStrings = setting.ListSetting("bugtester", attribStrings)
        sValues = setting.ListSetting("bugtester", attribValues)
        self.assertEqual(
            ["5", "6", "4", "5", "7"],
            sStrings.value,
            "The setting object does not have the correct value",
        )
        self.assertEqual(
            [5, 6, 4, 5, 7],
            sValues.value,
            "The setting object does not have the correct value",
        )

        sStrings.setValue("['10']")
        sValues.setValue([10])
        self.assertEqual(
            ["10"],
            sStrings.value,
            "The setting object does not have the correct value after setting",
        )
        self.assertEqual(
            [10],
            sValues.value,
            "The setting object does not have the correct value after setting",
        )

        attribNew = {"type": "list", "default": "['5','6','4','5','7']"}
        sNew = setting.ListSetting("bugtester", attribNew)
        sNew.setValue("['custom,14,14']")
        self.assertEqual(["custom,14,14"], sNew.value, "Parsing issues")

        self.assertEqual(
            ["5", "6", "4", "5", "7"],
            sStrings.default,
            "The setting object does not have the correct default value",
        )

        sValues.setValue([int(v) for v in ["5", "6", "7", "8", "9"]])
        self.assertEqual([5, 6, 7, 8, 9], sValues.value)

        attribNew = {"type": "list", "default": "['5','6','4','5','7']"}
        sNew = setting.ListSetting("bugMaker", attribNew)
        sNew.setValue("['custom,14,14']")
        self.assertIsInstance(sNew, setting.ListSetting)
        self.assertEqual(["custom,14,14"], sNew.value, "Parsing issues")

        sValues.setValue(None)
        self.assertEqual(sValues.value, [])

        with self.assertRaises(ValueError):
            sValues.setValue("0.2")

        # --------- malicious input ----------
        attrib = {
            "type": "list",
            "default": "['5','6','banana','5','7']",
            "containedType": "float",
        }

        with self.assertRaises(ValueError):
            setting.ListSetting("bugMaker", attrib)

        attrib["value"] = ["5", 5, True, False, {}]
        del attrib["containedType"]
        setting.ListSetting("bugMaker", attrib)


class SettingsFailureTests(unittest.TestCase):
    def test_settingsObjSetting(self):
        sets = settings.Settings()
        with self.assertRaises(exceptions.NonexistentSetting):
            sets[
                "idontexist"
            ] = "this test should fail because no setting named idontexist should exist."

    def test_malformedCreation(self):
        """Setting creation test

        Tests that a few unsupported types properly fail to create

        """
        s = settings.Settings()

        key = "bugMaker"
        attrib = {"type": "tuple", "default": 5.0, "description": "d", "label": "l"}

        with self.assertRaises(TypeError):
            s.settings[key] = setting.Setting.factory(key, attrib)
        attrib["type"] = tuple
        with self.assertRaises(TypeError):
            s.settings[key] = setting.Setting.factory(key, attrib)

        attrib["type"] = "dict"
        with self.assertRaises(TypeError):
            s.settings[key] = setting.Setting.factory(key, attrib)
        attrib["type"] = dict
        with self.assertRaises(TypeError):
            s.settings[key] = setting.Setting.factory(key, attrib)

    def test_loadFromXmlFailsOnBadNames(self):
        ss = settings.Settings()
        with self.assertRaises(TypeError):
            ss.loadFromInputFile(None)
        with self.assertRaises(IOError):
            ss.loadFromInputFile("this-settings-file-does-not-exist.xml")


class SettingsReaderTests(unittest.TestCase):
    def setUp(self):
        self.init_mode = armi.CURRENT_MODE

    def tearDown(self):
        armi.Mode.setMode(self.init_mode)

    def test_conversions(self):
        """Tests that settings convert based on a set of rules before being created

        :ref:`REQfbefba64-3de7-4aea-b155-102c7b375722`
        """
        mock = settings.Settings()
        mock.settings["newSetting"] = setting.FloatSetting(
            "newSetting",
            {
                "description": "Hola",
                "label": "hello",
                "type": "float",
                "default": "2.0",
            },
        )
        # make sure everything is as expected
        self.assertEqual(2.0, mock["newSetting"])

        # read some settings, and see that everything makes sense
        xml = six.StringIO('<settings><deprecated value="17"/></settings>')
        reader = settingsIO.SettingsReader(mock)

        # add a rename
        settingsRules.RENAMES["deprecated"] = "newSetting"

        reader.readFromStream(xml, fmt=reader.SettingsInputFormat.XML)
        self.assertEqual(17.0, mock["newSetting"])
        del settingsRules.RENAMES["deprecated"]

        # read settings
        xml2 = six.StringIO('<settings><newSetting value="92"/></settings>')
        reader2 = settingsIO.SettingsReader(mock)
        reader2.readFromStream(xml2, fmt=reader.SettingsInputFormat.XML)
        self.assertEqual(92.0, mock["newSetting"])

    def test_enforcements(self):
        mock = settings.Settings()

        xml = six.StringIO(
            '<settings-definitions><okaySetting type="int" default="17"/></settings-definitions>'
        )
        reader = settingsIO.SettingsDefinitionReader(mock)

        # put 'okaySetting' into the mock settings object
        reader.readFromStream(xml, fmt=reader.SettingsInputFormat.XML)

        self.assertEqual(mock["okaySetting"], 17)

        # we'll allow ARMI to run while ignoring old settings, but will issue warnings.
        xml = six.StringIO('<settings><OOGLYBOOGLY value="18"/></settings>')
        reader = settingsIO.SettingsReader(mock)
        reader.readFromStream(xml, fmt=reader.SettingsInputFormat.XML)
        with self.assertRaises(exceptions.NonexistentSetting):
            mock["OOGLYBOOGLY"]

        settingsRules.RENAMES["OOGLYBOOGLY"] = "okaySetting"
        xml = six.StringIO('<settings><OOGLYBOOGLY value="18"/></settings>')
        reader = settingsIO.SettingsReader(mock)
        reader.readFromStream(xml, fmt=reader.SettingsInputFormat.XML)

        self.assertEqual(mock["okaySetting"], 18)

    def test_noSharedName(self):
        """Tests that settings can't have the same name

        :ref:`REQ78f4a816-4dff-4525-82d9-7e0620943eaa`
        """
        mock = settings.Settings()

        xml = six.StringIO(
            '<settings-definitions><okaySetting type="int" default="17"/>'
            '<OKAYSetting type="int" default="27"/></settings-definitions>'
        )
        with self.assertRaises(exceptions.SettingNameCollision):
            reader = settingsIO.SettingsDefinitionReader(mock)
            reader.readFromStream(xml, fmt=reader.SettingsInputFormat.XML)

    def test_noAmbiguous(self):
        """Tests that settings need essentially full definitions

        :ref:`REQ32335060-e995-4ef8-a818-aaba4e8d1f85`
        """
        mock = settings.Settings()

        xml = six.StringIO(
            '<settings-definitions><badSetting default="17"/>' "</settings-definitions>"
        )
        with self.assertRaises(exceptions.SettingException):
            reader = settingsIO.SettingsDefinitionReader(mock)
            reader.readFromStream(xml, fmt=reader.SettingsInputFormat.XML)

    def test_basicRules(self):
        """Tests that settings need some basic rule following behavior

        :ref:`REQd9e90f54-1add-43b4-943a-bbccaf34c7dc`
        """
        mock = settings.Settings()

        xml = six.StringIO(
            '<settings-definitions><banana type="int" default="17" min="2" max="20"/>'
            "</settings-definitions>"
        )
        reader = settingsIO.SettingsDefinitionReader(mock)
        reader.readFromStream(xml, fmt=reader.SettingsInputFormat.XML)

        with self.assertRaises(ValueError):
            mock["banana"] = "spicy"
        with self.assertRaises(ValueError):
            mock["banana"] = 1
        with self.assertRaises(ValueError):
            mock["banana"] = 25

        mock["banana"] = 2
        mock["banana"] = 12
        mock["banana"] = 20

    def test_settingsVersioning(self):
        """Tests the version protection and run-stops in settings

        :ref:`REQb03e7fc0-754b-46b1-8400-238622e5ba0c`
        """
        mock = settings.Settings()
        xml = six.StringIO(
            '<?xml version="1.0" ?><settings version="beepboop"><okayDokay value="2" /></settings>'
        )

        with self.assertRaises(exceptions.SettingException):
            reader = settingsIO.SettingsDefinitionReader(mock)
            reader.readFromStream(xml, fmt=reader.SettingsInputFormat.XML)

    def test_multipleDefinedSettingsFails(self):
        """
        If someone defines a setting twice, that should crash.

        :ref:`REQ82a55fe7-cd0e-4588-9f5b-fb266b8d6637`
        """
        mock = settings.Settings()
        erroneousSettings = six.StringIO(
            '<settings><neutronicsKernel value="VARIANT"/>'
            '<neutronicsKernel value="MCNP"/></settings>'
        )
        with self.assertRaises(exceptions.SettingException):
            reader = settingsIO.SettingsReader(mock)
            reader.readFromStream(erroneousSettings, fmt=reader.SettingsInputFormat.XML)


class SettingsWriterTests(unittest.TestCase):
    def setUp(self):
        self.init_mode = armi.CURRENT_MODE
        self.filepath = os.path.join(
            os.getcwd(), self._testMethodName + "test_setting_io.xml"
        )
        self.filepathYaml = os.path.join(
            os.getcwd(), self._testMethodName + "test_setting_io.yaml"
        )
        self.cs = settings.Settings()
        self.cs["nCycles"] = 55

    def tearDown(self):
        if os.path.exists(self.filepath):
            os.remove(self.filepath)
        armi.Mode.setMode(self.init_mode)

    def test_writeShorthand(self):
        """Setting output as a sparse file"""
        self.cs.writeToXMLFile(self.filepath, style="short")
        self.cs.loadFromInputFile(self.filepath)

    def test_writeAll(self):
        """Setting output as a fully defined file"""
        self.cs.writeToXMLFile(self.filepath, style="full")
        self.cs.loadFromInputFile(self.filepath)

    def test_writeYaml(self):
        self.cs.writeToYamlFile(self.filepathYaml)
        self.cs.loadFromInputFile(self.filepathYaml)
        self.assertEqual(self.cs["nCycles"], 55)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'TestSetting.test_relativeToSettingPath']
    unittest.main()
