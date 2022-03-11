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

"""Tests for the framework settings"""
import unittest

import voluptuous as vol

import armi
from armi.settings import caseSettings


class TestSchema(unittest.TestCase):
    """Test that the implemented schema are doing what we think they are."""

    def setUp(self):
        self.cs = caseSettings.Settings()
        self.settings = {
            "numProcessors": {
                "valid": 1,
                "invalid": -1,
                "error": vol.error.RangeInvalid,
            },
            "axialMeshRefinementFactor": {
                "valid": 1,
                "invalid": 0,
                "error": vol.error.RangeInvalid,
            },
            "minMeshSizeRatio": {
                "valid": 1,
                "invalid": 0,
                "error": vol.error.RangeInvalid,
            },
            "cycleLength": {"valid": 0, "invalid": -1, "error": vol.error.RangeInvalid},
            "availabilityFactor": {
                "valid": 0,
                "invalid": -1,
                "error": vol.error.RangeInvalid,
            },
            "burnSteps": {"valid": 0, "invalid": -1, "error": vol.error.RangeInvalid},
            "beta": {
                "valid": [0.5, 0.5],
                "invalid": [0.5, 2],
                "error": vol.error.AnyInvalid,
            },
            "decayConstants": {
                "valid": [1, 1],
                "invalid": [0, 1],
                "error": vol.error.AnyInvalid,
            },
            "decayConstants": {
                "valid": [1, 1],
                "invalid": (1, 1),
                "error": vol.error.AnyInvalid,
            },
            "buGroups": {
                "valid": [1, 5],
                "invalid": [-1, 200],
                "error": vol.error.MultipleInvalid,
            },
            "burnupPeakingFactor": {
                "valid": 0,
                "invalid": -1,
                "error": vol.error.RangeInvalid,
            },
            "startCycle": {"valid": 1, "invalid": -1, "error": vol.error.RangeInvalid},
            "startNode": {"valid": 0, "invalid": -1, "error": vol.error.RangeInvalid},
            "lowPowerRegionFraction": {
                "valid": 0.5,
                "invalid": 2,
                "error": vol.error.RangeInvalid,
            },
            "mpiTasksPerNode": {
                "valid": 0,
                "invalid": -1,
                "error": vol.error.RangeInvalid,
            },
            "nCycles": {"valid": 1, "invalid": -1, "error": vol.error.RangeInvalid},
            "numCoupledIterations": {
                "valid": 0,
                "invalid": -1,
                "error": vol.error.RangeInvalid,
            },
            "power": {"valid": 0, "invalid": -1, "error": vol.error.RangeInvalid},
            "skipCycles": {"valid": 0, "invalid": -1, "error": vol.error.RangeInvalid},
            "targetK": {"valid": 1, "invalid": -1, "error": vol.error.RangeInvalid},
            "acceptableBlockAreaError": {
                "valid": 1,
                "invalid": 0,
                "error": vol.error.RangeInvalid,
            },
            "independentVariables": {
                "valid": [("length", "two"), ("length", "two")],
                "invalid": [("too", "many", "entries")],
                "error": vol.error.MultipleInvalid,
            },
            "Tin": {"valid": -272, "invalid": -274, "error": vol.error.RangeInvalid},
            "Tout": {"valid": -272, "invalid": -274, "error": vol.error.RangeInvalid},
            "dbStorageAfterCycle": {
                "valid": 0,
                "invalid": -1,
                "error": vol.error.RangeInvalid,
            },
            "timelineInclusionCutoff": {
                "valid": 1,
                "invalid": 105,
                "error": vol.error.RangeInvalid,
            },
        }

    def test_schema(self):
        # first test that a valid case goes through without error
        for setting in self.settings.keys():
            validOption = self.settings[setting]["valid"]
            self.cs = self.cs.modified(newSettings={setting: validOption})

            invalidOption = self.settings[setting]["invalid"]
            expectedError = self.settings[setting]["error"]
            with self.assertRaises(expectedError):
                self.cs = self.cs.modified(newSettings={setting: invalidOption})


if __name__ == "__main__":
    unittest.main()
