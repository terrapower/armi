# Copyright 2021 TerraPower, LLC
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
"""
Tests for generic fuel performance executers
"""
import unittest

from armi.physics.fuelPerformance.executers import (
    CONF_BOND_REMOVAL,
    FuelPerformanceOptions,
)
from armi.settings.caseSettings import Settings


class TestFuelPerformanceOptions(unittest.TestCase):
    def test_fuelPerformanceOptions(self):
        fpo = FuelPerformanceOptions("test_fuelPerformanceOptions")
        self.assertEqual(fpo.label, "test_fuelPerformanceOptions")

        cs = Settings()
        fpo.fromUserSettings(cs)
        self.assertEqual(fpo.bondRemoval, cs[CONF_BOND_REMOVAL])


if __name__ == "__main__":
    unittest.main()
