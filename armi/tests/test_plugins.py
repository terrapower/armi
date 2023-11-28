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
from typing import Optional

import yamlize

from armi import getPluginManagerOrFail
from armi import interfaces
from armi import plugins
from armi import settings
from armi.physics.neutronics import NeutronicsPlugin
from armi.reactor import parameters
from armi.reactor.blocks import Block, HexBlock
from armi.reactor.parameters import ParamLocation
from armi.reactor.parameters.parameterCollections import collectPluginParameters
from armi.utils import units


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
