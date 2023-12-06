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

"""Provides functionality for testing implementations of plugins."""
import unittest
from copy import deepcopy
from typing import Optional

import yamlize

from armi import context
from armi import getApp
from armi import interfaces
from armi import plugins
from armi import settings
from armi import utils
from armi.physics.neutronics import NeutronicsPlugin
from armi.reactor.blocks import Block
from armi.reactor.flags import Flags


class PluginFlags1(plugins.ArmiPlugin):
    """Simple Plugin that defines a single, new flag."""

    @staticmethod
    @plugins.HOOKIMPL
    def defineFlags():
        """Function to provide new Flags definitions."""
        return {"SUPER_FLAG": utils.flags.auto()}


class TestPluginRegistration(unittest.TestCase):
    def setUp(self):
        """
        Manipulate the standard App. We can't just configure our own, since the
        pytest environment bleeds between tests.
        """
        self._backupApp = deepcopy(getApp())

    def tearDown(self):
        """Restore the App to its original state."""
        import armi

        armi._app = self._backupApp
        context.APP_NAME = "armi"

    def test_defineFlags(self):
        """Define a new flag using the plugin defineFlags() method.

        .. test:: Define a new, unique flag through the plugin pathway.
            :id: T_ARMI_FLAG_EXTEND1
            :tests: R_ARMI_FLAG_EXTEND
        """
        app = getApp()

        # show the new plugin isn't loaded yet
        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertNotIn("PluginFlags1", pluginNames)

        # show the flag doesn't exist yet
        with self.assertRaises(AttributeError):
            Flags.SUPER_FLAG

        # load the plugin
        app.pluginManager.register(PluginFlags1)

        # show the new plugin is loaded now
        pluginNames = [p[0] for p in app.pluginManager.list_name_plugin()]
        self.assertIn("PluginFlags1", pluginNames)

        # force-register new flags from the new plugin
        app._pluginFlagsRegistered = False
        app.registerPluginFlags()

        # show the flag exists now
        self.assertEqual(type(Flags.SUPER_FLAG._value), int)


class TestPluginBasics(unittest.TestCase):
    def test_defineParameters(self):
        """Test that the default ARMI plugins are correctly defining parameters.

        .. test:: ARMI plugins define parameters, which appear on a new Block.
            :id: T_ARMI_PLUGIN_PARAMS
            :tests: R_ARMI_PLUGIN_PARAMS
        """
        # create a block
        b = Block("fuel", height=10.0)

        # unless a plugin has registerd a param, it doesn't exist
        with self.assertRaises(AttributeError):
            b.p.fakeParam

        # Check the default values of parameters defined by the neutronics plugin
        self.assertIsNone(b.p.axMesh)
        self.assertEqual(b.p.flux, 0)
        self.assertEqual(b.p.power, 0)
        self.assertEqual(b.p.pdens, 0)

        # Check the default values of parameters defined by the fuel peformance plugin
        self.assertEqual(b.p.gasPorosity, 0)
        self.assertEqual(b.p.liquidPorosity, 0)

    def test_exposeInterfaces(self):
        """Make sure that the exposeInterfaces hook is properly implemented.

        .. test:: Plugins can add interfaces to the interface stack.
            :id: T_ARMI_PLUGIN_INTERFACES
            :tests: R_ARMI_PLUGIN_INTERFACES
        """
        plugin = NeutronicsPlugin()

        cs = settings.Settings()
        results = plugin.exposeInterfaces(cs)

        # each plugin should return a list
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        for result in results:
            # Make sure all elements in the list satisfy the constraints of the hookspec
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 3)

            order, interface, kwargs = result

            self.assertIsInstance(order, (int, float))
            self.assertTrue(issubclass(interface, interfaces.Interface))
            self.assertIsInstance(kwargs, dict)


class TestPlugin(unittest.TestCase):
    """This contains some sanity tests that can be used by implementing plugins."""

    plugin: Optional[plugins.ArmiPlugin] = None

    def test_defineBlueprintsSections(self):
        """Make sure that the defineBlueprintsSections hook is properly implemented."""
        if self.plugin is None:
            return
        if not hasattr(self.plugin, "defineBlueprintsSections"):
            return

        results = self.plugin.defineBlueprintsSections()
        if results is None:
            return

        # each plugin should return a list
        self.assertIsInstance(results, (list, type(None)))

        for result in results:
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 3)
            self.assertIsInstance(result[0], str)
            self.assertIsInstance(result[1], yamlize.Attribute)
            self.assertTrue(callable(result[2]))

    def test_exposeInterfaces(self):
        """Make sure that the exposeInterfaces hook is properly implemented."""
        if self.plugin is None:
            return

        cs = settings.Settings()
        results = self.plugin.exposeInterfaces(cs)
        if results is None or not results:
            return

        # each plugin should return a list
        self.assertIsInstance(results, list)
        for result in results:
            # Make sure all elements in the list satisfy the constraints of the hookspec
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 3)

            order, interface, kwargs = result

            self.assertIsInstance(order, (int, float))
            self.assertTrue(issubclass(interface, interfaces.Interface))
            self.assertIsInstance(kwargs, dict)
