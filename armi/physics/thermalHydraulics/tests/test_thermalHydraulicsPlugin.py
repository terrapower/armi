# Copyright 2024 TerraPower, LLC
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

"""Unit tests for the thermal hydraulics plugin."""
from armi.physics import thermalHydraulics
from armi.physics.thermalHydraulics.settings import CONF_DO_TH, CONF_TH_KERNEL
from armi.settings import caseSettings
from armi.tests.test_plugins import TestPlugin


class TestThermalHydraulicsPlugin(TestPlugin):
    plugin = thermalHydraulics.ThermalHydraulicsPlugin

    def test_thermalHydraulicsSettingsLoaded(self):
        """Test that the thermal hydraulics case settings are loaded."""
        cs = caseSettings.Settings()

        self.assertIn(CONF_DO_TH, cs)
        self.assertIn(CONF_TH_KERNEL, cs)

    def test_thermalHydraulicsSettingsSet(self):
        """Test that the thermal hydraulics case settings are applied correctly."""
        cs = caseSettings.Settings()
        thKernelName = "testKernel"

        cs[CONF_DO_TH] = True
        cs[CONF_TH_KERNEL] = thKernelName

        self.assertTrue(cs[CONF_DO_TH])
        self.assertEqual(cs[CONF_TH_KERNEL], thKernelName)
