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
"""Tests for the UserPlugin class."""

import copy
import os
import unittest

from armi import context, getApp, interfaces, plugins, utils
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.settings import caseSettings
from armi.tests import TEST_ROOT
from armi.utils import directoryChangers


class UserPluginFlags(plugins.UserPlugin):
    """Simple UserPlugin that defines a single, new flag."""

    @staticmethod
    @plugins.HOOKIMPL
    def defineFlags():
        """Function to provide new Flags definitions."""
        return {"SPECIAL": utils.flags.auto()}


class UserPluginFlags2(plugins.UserPlugin):
    """Simple UserPlugin that defines a single, new flag."""

    @staticmethod
    @plugins.HOOKIMPL
    def defineFlags():
        """Function to provide new Flags definitions."""
        return {"FLAG2": utils.flags.auto()}


class UserPluginFlags3(plugins.UserPlugin):
    """Simple UserPlugin that defines a single, new flag."""

    @staticmethod
    @plugins.HOOKIMPL
    def defineFlags():
        """Function to provide new Flags definitions."""
        return {"FLAG3": utils.flags.auto()}


# text-file version of a stand-alone Python file for a simple User Plugin
upFlags4 = """
from armi import plugins
from armi import utils

class UserPluginFlags4(plugins.UserPlugin):
    @staticmethod
    @plugins.HOOKIMPL
    def defineFlags():
        return {"FLAG4": utils.flags.auto()}
"""


class UserPluginBadDefinesSettings(plugins.UserPlugin):
    """This is invalid/bad because it implements defineSettings()."""

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        """Define settings for the plugin."""
        return [1, 2, 3]


class UserPluginBadDefineParameterRenames(plugins.UserPlugin):
    """This is invalid/bad because it implements defineParameterRenames()."""

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameterRenames():
        """Return a mapping from old parameter names to new parameter names."""
        return {"oldType": "type"}


class UserPluginOnProcessCoreLoading(plugins.UserPlugin):
    """
    This plugin flex-tests the onProcessCoreLoading() hook,
    and arbitrarily adds "1" to the height of every block,
    after the DB is loaded.
    """

    @staticmethod
    @plugins.HOOKIMPL
    def onProcessCoreLoading(core, cs, dbLoad):
        """Function to call whenever a Core object is newly built."""
        blocks = core.getBlocks(Flags.FUEL)
        for b in blocks:
            b.p.height += 1.0


class UpInterface(interfaces.Interface):
    """
    A mostly meaningless little test interface, just to prove that we can affect
    the reactor state from an interface inside a UserPlugin.
    """

    name = "UpInterface"

    def interactEveryNode(self, cycle, node):
        """Logic to be carried out at every time node in the simulation."""
        self.r.core.p.power += 100


class UserPluginWithInterface(plugins.UserPlugin):
    """A little test UserPlugin, just to show how to add an Interface through a UserPlugin."""

    @staticmethod
    @plugins.HOOKIMPL
    def exposeInterfaces(cs):
        """Function for exposing interface(s) to other code."""
        return [interfaces.InterfaceInfo(interfaces.STACK_ORDER.PREPROCESSING, UpInterface, {"enabled": True})]


class TestUserPlugins(unittest.TestCase):
    def setUp(self):
        """
        Manipulate the standard App. We can't just configure our own, since the
        pytest environment bleeds between tests.
        """
        self._backupApp = copy.deepcopy(getApp())

    def tearDown(self):
        """Restore the App to its original state."""
        import armi

        armi._app = self._backupApp
        context.APP_NAME = "armi"

    def test_userPluginsFlags(self):
        # a basic test that a UserPlugin is loaded
        app = getApp()

        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertNotIn("UserPluginFlags", pluginNames)

        app.pluginManager.register(UserPluginFlags)

        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertIn("UserPluginFlags", pluginNames)

        # we shouldn't be able to register the same plugin twice
        with self.assertRaises(ValueError):
            app.pluginManager.register(UserPluginFlags)

    def test_validateUserPluginLimitations(self):
        # this should NOT raise any errors
        _up = UserPluginFlags()

        # this should raise an error because it has a defineSettings() method
        with self.assertRaises(AssertionError):
            _bad0 = UserPluginBadDefinesSettings()

    def test_registerUserPlugins(self):
        app = getApp()

        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertNotIn("UserPluginFlags2", pluginNames)

        plugins = ["armi.tests.test_user_plugins.UserPluginFlags2"]
        app.registerUserPlugins(plugins)

        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertIn("UserPluginFlags2", pluginNames)
        self.assertIn("FLAG2", dir(Flags))

    def test_registerUserPluginsAbsPath(self):
        app = getApp()

        with directoryChangers.TemporaryDirectoryChanger():
            # write a simple UserPlugin to a simple Python file
            with open("plugin4.py", "w") as f:
                f.write(upFlags4)

            # register that plugin using an absolute path
            cwd = os.getcwd()
            plugins = [os.path.join(cwd, "plugin4.py") + ":UserPluginFlags4"]
            app.registerUserPlugins(plugins)

        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertIn("UserPluginFlags4", pluginNames)
        self.assertIn("FLAG4", dir(Flags))

    def test_registerUserPluginsFromSettings(self):
        app = getApp()
        cs = caseSettings.Settings().modified(
            caseTitle="test_registerUserPluginsFromSettings",
            newSettings={
                "userPlugins": ["armi.tests.test_user_plugins.UserPluginFlags3"],
            },
        )

        pNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertNotIn("UserPluginFlags3", pNames)

        cs.registerUserPlugins()

        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertIn("UserPluginFlags3", pluginNames)
        self.assertIn("FLAG3", dir(Flags))

    def test_userPluginOnProcessCoreLoading(self):
        """
        Test that a UserPlugin can affect the Reactor state,
        by implementing onProcessCoreLoading() to arbitrarily increase the
        height of all the blocks by 1.0.
        """
        # register the plugin
        app = getApp()
        name = "UserPluginOnProcessCoreLoading"

        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertNotIn(name, pluginNames)
        app.pluginManager.register(UserPluginOnProcessCoreLoading)

        # validate the plugins was registered
        pluginz = app.pluginManager.list_name_plugin()
        pluginNames = [p[0] for p in pluginz]
        self.assertIn(name, pluginNames)

        # grab the loaded plugin
        plug0 = [p[1] for p in pluginz if p[0] == name][0]

        # load a reactor and grab the fuel assemblies
        o, r = test_reactors.loadTestReactor(TEST_ROOT, inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        fuels = r.core.getBlocks(Flags.FUEL)

        # prove that our plugin affects the core in the desired way
        heights = [float(f.p.height) for f in fuels]
        plug0.onProcessCoreLoading(core=r.core, cs=o.cs, dbLoad=False)
        for i, height in enumerate(heights):
            self.assertEqual(fuels[i].p.height, height + 1.0)

    def test_userPluginWithInterfaces(self):
        """Test that UserPlugins can correctly inject an interface into the stack."""
        # register the plugin
        app = getApp()

        pNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertNotIn("UserPluginWithInterface", pNames)

        # register custom UserPlugin, that has an
        plugins = ["armi.tests.test_user_plugins.UserPluginWithInterface"]
        app.registerUserPlugins(plugins)

        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertIn("UserPluginWithInterface", pluginNames)

        # load a reactor and grab the fuel assemblieapps
        o, r = test_reactors.loadTestReactor(TEST_ROOT, inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        _fuels = r.core.getAssemblies(Flags.FUEL)

        # This is here because we have multiple tests altering the App()
        o.interfaces = []
        o.initializeInterfaces(r)

        app.pluginManager.hook.exposeInterfaces(cs=o.cs)

        # This test is not set up for a full run through all the interfaces, for
        # instance, there is not database prepped. So let's skip some interfaces.
        for skipIt in ["fuelhandler", "history"]:
            for i, interf in enumerate(o.interfaces):
                if skipIt in str(interf).lower():
                    o.interfaces = o.interfaces[:i] + o.interfaces[i + 1 :]
                    break

        # test that the core power goes up
        power0 = float(r.core.p.power)
        o.cs["nCycles"] = 2
        o.operate()
        self.assertGreater(r.core.p.power, power0)

    def test_registerRepeatedUserPlugins(self):
        app = getApp()

        # Test plugin registration with two userPlugins with the same name
        with directoryChangers.TemporaryDirectoryChanger():
            # write a simple UserPlugin to a simple Python file
            with open("plugin4.py", "w") as f:
                f.write(upFlags4)

            # register that plugin using an absolute path
            cwd = os.getcwd()
            plugins = [os.path.join(cwd, "plugin4.py") + ":UserPluginFlags4"] * 2
            app.registerUserPlugins(plugins)
        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertEqual(pluginNames.count("UserPluginFlags4"), 1)

        # Repeat test for other type of path
        cs = caseSettings.Settings().modified(
            caseTitle="test_registerUserPluginsFromSettings",
            newSettings={
                "userPlugins": [
                    "armi.tests.test_user_plugins.UserPluginFlags3",
                    "armi.tests.test_user_plugins.UserPluginFlags3",
                ],
            },
        )
        cs.registerUserPlugins()
        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertEqual(pluginNames.count("UserPluginFlags3"), 1)
