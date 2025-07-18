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
"""Tests for new settings system with plugin import."""

import copy
import io
import logging
import os
import unittest

import voluptuous as vol
from ruamel.yaml import YAML

from armi import configure, getApp, getPluginManagerOrFail, plugins, settings
from armi.physics.fuelCycle import FuelHandlerPlugin
from armi.physics.fuelCycle.settings import CONF_CIRCULAR_RING_ORDER, CONF_SHUFFLE_LOGIC
from armi.physics.neutronics.settings import CONF_NEUTRONICS_KERNEL
from armi.reactor.flags import Flags
from armi.settings import caseSettings, setting
from armi.settings.settingsValidation import Inspector, validateVersion
from armi.tests import ARMI_RUN_PATH, TEST_ROOT
from armi.utils import directoryChangers
from armi.utils.customExceptions import NonexistentSetting

THIS_DIR = os.path.dirname(__file__)


class DummySettingPlugin1(plugins.ArmiPlugin):
    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        """Define settings for the plugin."""
        return [
            setting.Setting(
                "extendableOption",
                default="DEFAULT",
                label="Neutronics Kernel",
                description="The neutronics / depletion solver for global flux solve.",
                enforcedOptions=True,
                options=["DEFAULT", "OTHER"],
            ),
            setting.Setting(
                "avocado",
                default=0,
                label="Avocados",
                description="Avocados are delicious.",
            ),
        ]


class DummySettingPlugin2(plugins.ArmiPlugin):
    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        """Define settings for the plugin."""
        return [
            setting.Option("PLUGIN", "extendableOption"),
            setting.Default("PLUGIN", "extendableOption"),
        ]


class PluginAddsOptions(plugins.ArmiPlugin):
    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        """Define settings for the plugin."""
        return [
            setting.Option("MCNP", CONF_NEUTRONICS_KERNEL),
            setting.Option("MCNP_Slab", CONF_NEUTRONICS_KERNEL),
        ]


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.cs = caseSettings.Settings()

    def test_updateEnvironmentSettingsFrom(self):
        envSettings = [
            "trace",
            "profile",
            "coverage",
            "branchVerbosity",
            "moduleVerbosity",
            "verbosity",
            "outputCacheLocation",
        ]
        self.assertEqual(self.cs.environmentSettings, envSettings)

        newEnv = {es: 9 for es in envSettings}
        newEnv["moduleVerbosity"] = {}
        self.cs.updateEnvironmentSettingsFrom(newEnv)
        self.assertEqual(self.cs["verbosity"], "9")

    def test_metaData(self):
        """Test we can get and set the important settings metadata.

        .. test:: Test getting and setting import settings metadata.
            :id: T_ARMI_SETTINGS_META
            :tests: R_ARMI_SETTINGS_META
        """
        # test get/set on caseTitle
        self.assertEqual(self.cs.caseTitle, "armi")
        testTitle = "test_metaData"
        self.cs.caseTitle = testTitle
        self.assertEqual(self.cs.caseTitle, testTitle)

        # test get/set on comment
        self.assertEqual(self.cs["comment"], "")
        testComment = "Comment: test_metaData"
        self.cs = self.cs.modified(newSettings={"comment": testComment})
        self.assertEqual(self.cs["comment"], testComment)

        # test get/set on version
        self.assertEqual(len(self.cs["versions"]), 0)
        self.cs = self.cs.modified(newSettings={"versions": {"something": 1.234}})

        d = self.cs["versions"]
        self.assertEqual(len(d), 1)
        self.assertEqual(d["something"], 1.234)


class TestAddingOptions(unittest.TestCase):
    def setUp(self):
        self.dc = directoryChangers.TemporaryDirectoryChanger()
        self.dc.__enter__()
        # load in the plugin with extra, added options
        self.pm = getPluginManagerOrFail()
        self.pm.register(PluginAddsOptions)

    def tearDown(self):
        self.dc.__exit__(None, None, None)
        self.pm.unregister(PluginAddsOptions)

    def test_addingOptions(self):
        # modify the default/text settings YAML file to include neutronicsKernel
        fin = os.path.join(TEST_ROOT, "armiRun.yaml")
        txt = open(fin, "r").read()
        txt = txt.replace("\n  nCycles:", "\n  neutronicsKernel: MCNP\n  nCycles:")
        fout = "test_addingOptions.yaml"
        open(fout, "w").write(txt)

        # this settings file should load fine, and test some basics
        cs = settings.Settings(fout)
        self.assertEqual(cs["burnSteps"], 2)
        self.assertEqual(cs[CONF_NEUTRONICS_KERNEL], "MCNP")


class TestSettings2(unittest.TestCase):
    def setUp(self):
        # We are going to be messing with the plugin manager, which is global ARMI
        # state, so we back it up and restore the original when we are done.
        self._backupApp = copy.copy(getApp())

    def tearDown(self):
        configure(self._backupApp, permissive=True)

    def test_schemaChecksType(self):
        newSettings = FuelHandlerPlugin.defineSettings()

        good_input = io.StringIO(
            """
assemblyRotationAlgorithm: buReducingAssemblyRotation
shuffleLogic: {}
""".format(__file__)
        )

        bad_input = io.StringIO(
            """
assemblyRotationAlgorithm: buReducingAssemblyRotatoin
"""
        )

        yaml = YAML(typ="rt")

        inp = yaml.load(good_input)
        for inputSetting, inputVal in inp.items():
            settin = [s for s in newSettings if s.name == inputSetting][0]
            settin.schema(inputVal)

        inp = yaml.load(bad_input)
        for inputSetting, inputVal in inp.items():
            with self.assertRaises(vol.error.MultipleInvalid):
                settin = [s for s in newSettings if s.name == inputSetting][0]
                settin.schema(inputVal)

    def test_listsMutable(self):
        listSetting = setting.Setting("aList", default=[], label="Dummy list", description="whatever")

        listSetting.value = [1, 2, 3]
        self.assertEqual([1, 2, 3], listSetting.value)

        listSetting.value[-1] = 4
        self.assertEqual([1, 2, 4], listSetting.value)

    def test_listCoercion(self):
        """Make sure list setting values get coerced right."""
        listSetting = setting.Setting("aList", default=[0.2, 5], label="Dummy list", description="whatever")
        listSetting.value = [1, 2, 3]
        self.assertEqual(listSetting.value, [1.0, 2.0, 3.0])
        self.assertTrue(isinstance(listSetting.value[0], float))

    def test_typeDetection(self):
        """Ensure some of the type inference operations work."""
        listSetting = setting.Setting(
            "aList",
            default=[],
            label="label",
            description="desc",
            schema=vol.Schema([float]),
        )
        self.assertEqual(listSetting.containedType, float)
        listSetting = setting.Setting(
            "aList",
            default=[],
            label="label",
            description="desc",
            schema=vol.Schema([vol.Coerce(float)]),
        )
        self.assertEqual(listSetting.containedType, float)

    def test_csWorks(self):
        """Ensure plugin settings become available and have defaults."""
        a = settings.Settings()
        self.assertEqual(a[CONF_CIRCULAR_RING_ORDER], "angle")

    def test_pluginValidatorsAreDiscovered(self):
        cs = caseSettings.Settings()
        cs = cs.modified(
            caseTitle="test_pluginValidatorsAreDiscovered",
            newSettings={
                CONF_SHUFFLE_LOGIC: "nothere",
                "cycleLengths": [3, 4, 5, 6, 9],
                "powerFractions": [0.2, 0.2, 0.2, 0.2, 0.2],
            },
        )

        inspector = Inspector(cs)
        self.assertTrue(any(["Shuffling will not occur" in query.statement for query in inspector.queries]))

    def test_pluginSettings(self):
        """Test settings change depending on what plugins are registered.

        .. test:: Registering a plugin can change what settings exist.
            :id: T_ARMI_PLUGIN_SETTINGS
            :tests: R_ARMI_PLUGIN_SETTINGS
        """
        pm = getPluginManagerOrFail()
        pm.register(DummySettingPlugin1)
        # We have a setting; this should be fine
        cs = caseSettings.Settings()

        self.assertEqual(cs["extendableOption"], "DEFAULT")
        self.assertEqual(cs["avocado"], 0)
        # We shouldn't have any settings from the other plugin, so this should be an
        # error.
        with self.assertRaises(vol.error.MultipleInvalid):
            newSettings = {"extendableOption": "PLUGIN"}
            cs = cs.modified(newSettings=newSettings)

        pm.register(DummySettingPlugin2)
        cs = caseSettings.Settings()
        self.assertEqual(cs["extendableOption"], "PLUGIN")
        # Now we should have the option from plugin 2; make sure that works
        cs = cs.modified(newSettings=newSettings)
        cs["extendableOption"] = "PLUGIN"
        self.assertIn("extendableOption", cs.keys())
        pm.unregister(DummySettingPlugin2)
        pm.unregister(DummySettingPlugin1)

        # Now try the same, but adding the plugins in a different order. This is to make
        # sure that it doesn't matter if the Setting or its Options come first
        pm.register(DummySettingPlugin2)
        pm.register(DummySettingPlugin1)
        cs = caseSettings.Settings()
        self.assertEqual(cs["extendableOption"], "PLUGIN")
        self.assertEqual(cs["avocado"], 0)

    def test_default(self):
        """
        Make sure default updating mechanism works.

        .. test:: The setting default is mandatory.
            :id: T_ARMI_SETTINGS_DEFAULTS
            :tests: R_ARMI_SETTINGS_DEFAULTS
        """
        a = setting.Setting("testsetting", 0, description="whatever")
        newDefault = setting.Default(5, "testsetting")
        a.changeDefault(newDefault)
        self.assertEqual(a.value, 5)

    def test_getSettingsSetByUser(self):
        cs = caseSettings.Settings()
        settingsList = cs.getSettingsSetByUser(ARMI_RUN_PATH)
        # This test is dependent on the current setup of armiRun.yaml, which includes
        # some default settings values
        for sett in ["availabilityFactor", "db"]:
            self.assertIn(sett, settingsList)
        self.assertNotIn("nTasks", settingsList)

    def test_setModuleVerbosities(self):
        # init settings and use them to set module-level logging levels
        cs = caseSettings.Settings()
        newSettings = {"moduleVerbosity": {"test_setModuleVerbosities": "debug"}}
        cs = cs.modified(newSettings=newSettings)

        # set the logger once, and check it is was set
        cs.setModuleVerbosities()
        logger = logging.getLogger("test_setModuleVerbosities")
        self.assertEqual(logger.level, 10)

        # try to set the logger again, without forcing it
        newSettings = {"moduleVerbosity": {"test_setModuleVerbosities": "error"}}
        cs = cs.modified(newSettings=newSettings)
        cs.setModuleVerbosities()
        self.assertEqual(logger.level, 10)

        # try to set the logger again, with force=True
        cs.setModuleVerbosities(force=True)
        self.assertEqual(logger.level, 40)

    def test_getFailures(self):
        """Make sure the correct error is thrown when getting a nonexistent setting."""
        cs = caseSettings.Settings()

        with self.assertRaises(NonexistentSetting):
            cs.getSetting("missingFake")

        with self.assertRaises(NonexistentSetting):
            _ = cs["missingFake"]

    def test_settingIsOkayToGrab(self):
        cs = caseSettings.Settings()
        newSettings = {"cycles": [{"cumulative days": [1]}]}
        cs = cs.modified(newSettings=newSettings)

        with self.assertRaises(ValueError):
            _ = cs["cycleLength"]

    def test_modified(self):
        """Prove that using the modified() method does not mutate the original object."""
        # init settings
        cs = caseSettings.Settings()

        # prove this setting doesn't exist
        with self.assertRaises(NonexistentSetting):
            cs.getSetting("extendableOption")

        # ensure that defaults in getSetting works
        val = cs.getSetting("extendableOption", 789)
        self.assertEqual(val, 789)

        # prove the new settings object has the new setting
        cs2 = cs.modified(newSettings={"extendableOption": "PLUGIN"})
        self.assertEqual(cs2["extendableOption"], "PLUGIN")

        # prove modified() didn't alter the original object
        with self.assertRaises(NonexistentSetting):
            cs.getSetting("extendableOption")

        # prove that successive applications of "modified" don't fail
        cs3 = cs2.modified(newSettings={"numberofGenericParams": 7})
        _cs4 = cs3.modified(newSettings={"somethingElse": 123})

    def test_copySetting(self):
        """Ensure that when we copy a Setting() object, the result is sound.

        Notes
        -----
        In particular, self.schema and self._customSchema on a Setting object are
        removed by Setting.__getstate__, and that has been a problem in the past.
        """
        # get a baseline: show how the Setting object looks to start
        s1 = setting.Setting("testCopy", 765, description="whatever")
        self.assertEqual(s1.name, "testCopy")
        self.assertEqual(s1._value, 765)
        self.assertTrue(hasattr(s1, "schema"))
        self.assertTrue(hasattr(s1, "_customSchema"))

        # show that copy(Setting) is working correctly
        s2 = copy.copy(s1)
        self.assertEqual(s2._value, 765)
        self.assertEqual(s2.name, "testCopy")
        self.assertTrue(hasattr(s2, "schema"))
        self.assertTrue(hasattr(s2, "_customSchema"))

    def test_copySettingNotDefault(self):
        """Ensure that when we copy a Setting() object, the result is sound
        when the Setting value is set to a non-default value.
        """
        # get a baseline: show how the Setting object looks to start
        s1 = setting.Setting("testCopy", 765, description="whatever")
        s1.value = 999
        self.assertEqual(s1.name, "testCopy")
        self.assertEqual(s1._value, 999)
        self.assertTrue(hasattr(s1, "schema"))
        self.assertTrue(hasattr(s1, "_customSchema"))

        # show that copy(Setting) is working correctly
        s2 = copy.copy(s1)
        self.assertEqual(s2._value, 999)
        self.assertEqual(s2.name, "testCopy")
        self.assertTrue(hasattr(s2, "schema"))
        self.assertTrue(hasattr(s2, "_customSchema"))

    def test_empty(self):
        cs = caseSettings.Settings()
        cs = cs.modified(newSettings={"buGroups": []})
        self.assertEqual(cs["buGroups"], [])


class TestSettingsUtils(unittest.TestCase):
    """Tests for utility functions."""

    def setUp(self):
        self.dc = directoryChangers.TemporaryDirectoryChanger()
        self.dc.__enter__()

        # Create a little case suite on the fly. Whipping it up from defaults should be
        # more evergreen than committing settings files as a test resource
        cs = caseSettings.Settings()
        cs.writeToYamlFile("settings1.yaml")
        cs.writeToYamlFile("settings2.yaml")
        with open("notSettings.yaml", "w") as f:
            f.write("some: other\nyaml: file\n")
        os.mkdir("subdir")
        cs.writeToYamlFile("subdir/settings3.yaml")
        cs.writeToYamlFile("subdir/skipSettings.yaml")

    def tearDown(self):
        self.dc.__exit__(None, None, None)

    def test_recursiveScan(self):
        loadedSettings = settings.recursivelyLoadSettingsFiles(".", ["*.yaml"], ignorePatterns=["skip*"])
        names = {cs.caseTitle for cs in loadedSettings}
        self.assertIn("settings1", names)
        self.assertIn("settings2", names)
        self.assertIn("settings3", names)
        self.assertNotIn("skipSettings", names)

        loadedSettings = settings.recursivelyLoadSettingsFiles(
            ".", ["*.yaml"], recursive=False, ignorePatterns=["skip*"]
        )
        names = {cs.caseTitle for cs in loadedSettings}
        self.assertIn("settings1", names)
        self.assertIn("settings2", names)
        self.assertNotIn("settings3", names)

    def test_prompt(self):
        selection = settings.promptForSettingsFile(1)
        self.assertEqual(selection, "settings1.yaml")


class TestFlagListSetting(unittest.TestCase):
    def test_flagListSetting(self):
        """Test that a list of strings can be converted to a list of flags and back."""
        flagsAsStringList = ["DUCT", "FUEL", "CLAD"]
        flagsAsFlagList = [Flags.DUCT, Flags.FUEL, Flags.CLAD]

        fs = setting.FlagListSetting(name="testFlagSetting", default=[], description="whatever")
        # Set the value as a list of strings first
        fs.value = flagsAsStringList
        self.assertEqual(fs.value, flagsAsFlagList)
        self.assertEqual(fs.dump(), flagsAsStringList)

        # Set the value as a list of flags
        fs.value = flagsAsFlagList
        self.assertEqual(fs.value, flagsAsFlagList)
        self.assertEqual(fs.dump(), flagsAsStringList)

    def test_invalidFlagListTypeError(self):
        """Test raising a TypeError when a list is not provided."""
        fs = setting.FlagListSetting(name="testFlagSetting", default=[], description="whatever")
        with self.assertRaises(TypeError):
            fs.value = "DUCT"


class TestSettingsValidationUtils(unittest.TestCase):
    def test_validateVersion(self):
        # controlled version, and true
        self.assertTrue(validateVersion("1.22.3", "1.22.3"))
        self.assertTrue(validateVersion("1.3.102", "1.3.102"))
        self.assertTrue(validateVersion("1.2.3", "1.2"))
        self.assertTrue(validateVersion("1.2.37", "1.2"))
        self.assertTrue(validateVersion("13.7.3", "13.7"))
        self.assertTrue(validateVersion("1.22.310", "1"))

        # uncontrolled version is always true
        self.assertTrue(validateVersion("4.2.0", "uncontrolled"))

        # controlled versions and false
        self.assertFalse(validateVersion("11.2.3", "11.2.4"))
        self.assertFalse(validateVersion("1.2.3", "3.2.1"))
        self.assertFalse(validateVersion("11.2.3", "2.2"))

        # examples of various errors
        with self.assertRaises(ValueError):
            validateVersion("1.2.a", "1.20.3")

        with self.assertRaises(ValueError):
            validateVersion("nope", "7")

        with self.assertRaises(ValueError):
            validateVersion("1.2.3", "zzz")
