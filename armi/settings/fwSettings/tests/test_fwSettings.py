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

"""Tests for the framework settings."""

import unittest

import voluptuous as vol

from armi.settings import caseSettings


class TestSchema(unittest.TestCase):
    """Test that the implemented schema are doing what we think they are."""

    def setUp(self):
        self.cs = caseSettings.Settings()
        self.settings = {
            "nTasks": {
                "valid": 1,
                "invalid": -1,
                "error": vol.error.Invalid,
            },
            "axialMeshRefinementFactor": {
                "valid": 1,
                "invalid": 0,
                "error": vol.error.Invalid,
            },
            "minMeshSizeRatio": {
                "valid": 1,
                "invalid": 0,
                "error": vol.error.Invalid,
            },
            "cycleLength": {
                "valid": 1,
                "invalid": -1,
                "error": vol.error.Invalid,
            },
            "availabilityFactor": {
                "valid": 0,
                "invalid": -1,
                "error": vol.error.Invalid,
            },
            "burnSteps": {
                "valid": 0,
                "invalid": -1,
                "error": vol.error.Invalid,
            },
            "beta": {
                "valid": [0.5, 0.5],
                "invalid": [0.5, 2],
                "error": vol.error.Invalid,
            },
            "decayConstants": {
                "valid": [1, 1],
                "invalid": [-1, 1],
                "error": vol.error.Invalid,
            },
            "buGroups": {
                "valid": [1, 5],
                "invalid": [-1, 200],
                "error": vol.error.Invalid,
            },
            "burnupPeakingFactor": {
                "valid": 0,
                "invalid": -1,
                "error": vol.error.Invalid,
            },
            "startCycle": {
                "valid": 1,
                "invalid": -1,
                "error": vol.error.Invalid,
            },
            "startNode": {
                "valid": 0,
                "invalid": -1,
                "error": vol.error.Invalid,
            },
            "nCycles": {"valid": 1, "invalid": -1, "error": vol.error.Invalid},
            "power": {"valid": 0, "invalid": -1, "error": vol.error.Invalid},
            "skipCycles": {
                "valid": 0,
                "invalid": -1,
                "error": vol.error.Invalid,
            },
            "targetK": {"valid": 1, "invalid": -1, "error": vol.error.Invalid},
            "acceptableBlockAreaError": {
                "valid": 1,
                "invalid": 0,
                "error": vol.error.Invalid,
            },
            "Tin": {"valid": -272, "invalid": -274, "error": vol.error.Invalid},
            "Tout": {
                "valid": -272,
                "invalid": -274,
                "error": vol.error.Invalid,
            },
        }

    def test_schema(self):
        # first test that a valid case goes through without error
        for settingName, settingVal in self.settings.items():
            validOption = settingVal["valid"]
            self.cs = self.cs.modified(newSettings={settingName: validOption})

            invalidOption = settingVal["invalid"]
            expectedError = settingVal["error"]
            with self.assertRaises(expectedError):
                self.cs = self.cs.modified(newSettings={settingName: invalidOption})
