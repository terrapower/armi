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

import unittest
import io
import os

from ruamel.yaml import YAML

from armi.tests.test_plugins import TestPlugin
from armi.physics import neutronics
from armi.settings import caseSettings
from armi.physics.neutronics.const import CONF_CROSS_SECTION

XS_EXAMPLE = """AA:
    geometry: 0D
    criticalBuckling: true
    blockRepresentation: Median
BA:
    geometry: 1D slab
    criticalBuckling: false
    blockRepresentation: Median
"""


class Test_NeutronicsPlugin(TestPlugin):
    plugin = neutronics.NeutronicsPlugin

    def test_customSettingObjectIO(self):
        """Check specialized settings can build objects as values and write."""
        cs = caseSettings.Settings()
        yaml = YAML()
        inp = yaml.load(io.StringIO(XS_EXAMPLE))
        cs[CONF_CROSS_SECTION] = inp
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].geometry, "0D")
        fname = "test_setting_obj_io_.yaml"
        cs.writeToYamlFile(fname)
        os.remove(fname)

    def test_customSettingRoundTrip(self):
        """Check specialized settings can go back and forth."""
        cs = caseSettings.Settings()
        yaml = YAML()
        inp = yaml.load(io.StringIO(XS_EXAMPLE))
        cs[CONF_CROSS_SECTION] = inp
        cs[CONF_CROSS_SECTION] = cs[CONF_CROSS_SECTION]
        fname = "test_setting_obj_io_round.yaml"
        cs.writeToYamlFile(fname)
        os.remove(fname)


if __name__ == "__main__":
    unittest.main()
