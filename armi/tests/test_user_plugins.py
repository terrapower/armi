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
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import copy
import unittest

import pluggy

from armi import context
from armi import getApp
from armi import getPluginManagerOrFail
from armi import plugins
from armi import utils
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.settings import caseSettings
from armi.tests import TEST_ROOT


HOOKSPEC = pluggy.HookspecMarker("armi")


class UserPluginFlags(plugins.UserPlugin):
    """Simple UserPlugin that defines a single, new flag."""

    def defineFlags():
        return {"SPECIAL": utils.flags.auto()}


class UserPluginBadDefinesSettings(plugins.UserPlugin):
    """This is invalid/bad because it implements defineSettings()"""

    def defineSettings():
        return [1, 2, 3]


class UserPluginBadDefineParameterRenames(plugins.UserPlugin):
    """This is invalid/bad because it implements defineParameterRenames()"""

    def defineParameterRenames():
        self.danger = "danger"


class UserPluginOnProcessCoreLoading(plugins.UserPlugin):
    """
    This plugin flex-tests the onProcessCoreLoading() hook.
    NOTE: This plugin affects the core in a non-physical way.
    """

    @staticmethod
    @HOOKSPEC
    def onProcessCoreLoading(core, cs):
        fuels = core.getAssemblies(Flags.FUEL)
        fuels[0].p.buLimit = fuels[0].p.buLimit + 1000


class TestUserPlugins(unittest.TestCase):
    def setUp(self):
        """
        Manipulate the standard App. We can't just configure our own, since the
        pytest environment bleeds between tests.
        """
        self._backupApp = copy.deepcopy(getApp())

    def tearDown(self):
        """Restore the App to its original state"""
        import armi

        armi._app = self._backupApp
        context.APP_NAME = "armi"

    def test_userPluginsFlags(self):
        # a basic test that a UserPlugin is loaded
        app = getApp()
        count = app.pluginManager.counter
        app.pluginManager.register(UserPluginFlags)
        self.assertEqual(app.pluginManager.counter, count + 1)

        # we shouldn't be able to register the same plugin twice
        with self.assertRaises(ValueError):
            app.pluginManager.register(UserPluginFlags)

    def test_validateUserPluginLimitations(self):
        # this should NOT raise any errors
        up = UserPluginFlags()

        # this should raise an error because it has a defineSettings() method
        with self.assertRaises(AssertionError):
            bad0 = UserPluginBadDefinesSettings()

        # overriding defineParameterRenames() is correctly fixed
        bad1 = UserPluginBadDefineParameterRenames()
        self.assertFalse(hasattr(bad1, "danger"))

    def test_registerUserPlugins(self):
        app = getApp()
        count = app.pluginManager.counter
        plugins = ["armi.tests.test_user_plugins.UserPluginFlags"]
        app.registerUserPlugins(plugins)
        self.assertEqual(app.pluginManager.counter, count + 1)

        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertIn("UserPluginFlags", pluginNames)

    def test_registerUserPluginsFromSettings(self):
        app = getApp()
        cs = caseSettings.Settings().modified(
            caseTitle="test_registerUserPluginsFromSettings",
            newSettings={
                "userPlugins": ["armi.tests.test_user_plugins.UserPluginFlags"],
            },
        )
        count = app.pluginManager.counter
        cs.registerUserPlugins()
        self.assertEqual(app.pluginManager.counter, count + 1)

    def test_userPluginOnProcessCoreLoading(self):
        """
        Test that a UserPlugin can affect the Reactor state,
        by implementing onProcessCoreLoading().
        """
        # register the plugin
        app = getApp()
        count = app.pluginManager.counter
        app.pluginManager.register(UserPluginOnProcessCoreLoading)
        self.assertEqual(app.pluginManager.counter, count + 1)

        # validate the plugins was registered
        plguinz = app.pluginManager.list_name_plugin()
        pluginNames = [p[0] for p in pluginz]
        name = "UserPluginOnProcessCoreLoading"
        self.assertIn(name, pluginNames)

        # grab the loaded plugin
        plug0 = [p[1] for p in pluginz if p[0] == name][0]

        # load a reactor and grab the fuel assemblies
        o, r = test_reactors.loadTestReactor(TEST_ROOT)
        fuels = r.core.getAssemblies(Flags.FUEL)

        # prove that our plugin affects the core in the desired way
        sumBuLimits = sum(f.p.buLimit for f in fuels)
        plug0.onProcessCoreLoading(core=r.core, cs=o.cs)
        self.assertEqual(sum(f.p.buLimit for f in fuels), sumBuLimits + 1000)
