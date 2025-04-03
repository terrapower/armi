# Copyright 2025 TerraPower, LLC
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
"""Tests for the plugin report tools."""
import unittest

from armi.bookkeeping.report.pluginReports import parametersReport, settingsReport
from armi.physics.fuelPerformance.plugin import FuelPerformancePlugin
from armi.plugins import ArmiPlugin
from armi.reactor.blocks import Block


class MockDummyFakeEmptyPlugin(ArmiPlugin):
    pass


class TestPluginReports(unittest.TestCase):
    def test_parametersReportDict(self):
        plugin = FuelPerformancePlugin()
        data = parametersReport(plugin, True)

        self.assertTrue(isinstance(data, dict))
        self.assertEqual(len(data.keys()), 1)
        self.assertIn(Block, data)
        self.assertEqual(len(data[Block]), 10)
        self.assertIn("fuelCladLocked", data[Block])
        self.assertIn("bondRemoved", data[Block])
        self.assertIn("cladWastage", data[Block])
        self.assertIn("description", data[Block]["gasPorosity"])
        self.assertIn("units", data[Block]["gasPorosity"])

    def test_parametersReportList(self):
        plugin = FuelPerformancePlugin()
        data = parametersReport(plugin, False)

        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 11)
        self.assertEqual(data[0][0], "param-type")
        self.assertEqual(data[1][0], Block)
        self.assertEqual(data[4][0], Block)
        self.assertEqual(data[7][0], Block)
        self.assertEqual(data[1][1], "fuelCladLocked")
        self.assertEqual(data[4][1], "cladWastage")
        self.assertEqual(data[7][1], "fpPeakFuelTemp")

    def test_settingsReportDict(self):
        plugin = FuelPerformancePlugin()
        data = settingsReport(plugin, True)

        self.assertTrue(isinstance(data, dict))
        self.assertEqual(len(data), 7)
        self.assertIn("bondRemoval", data)
        self.assertIn("fgRemoval", data)
        self.assertIn("options", data["claddingWastage"])
        self.assertIn("default", data["claddingStrain"])
        self.assertIn("description", data["fissionGasYieldFraction"])

    def test_settingsReportList(self):
        plugin = FuelPerformancePlugin()
        data = settingsReport(plugin, False)

        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 8)
        self.assertEqual(data[0][0], "name")
        self.assertEqual(data[1][0], "fuelPerformanceEngine")
        self.assertEqual(data[4][0], "bondRemoval")
        self.assertEqual(data[7][0], "claddingStrain")
        self.assertFalse(data[6][2])
        self.assertIsNone(data[7][3], None)

    def test_emptySettings(self):
        plugin = MockDummyFakeEmptyPlugin()
        self.assertEqual(len(settingsReport(plugin, False)), 0)
        self.assertEqual(len(settingsReport(plugin, True)), 0)

    def test_emptyParameters(self):
        plugin = MockDummyFakeEmptyPlugin()
        self.assertEqual(len(parametersReport(plugin, False)), 0)
        self.assertEqual(len(parametersReport(plugin, True)), 0)
