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

from armi.settings import caseSettings


class TestSchema(unittest.TestCase):
    """Test that the implemented schema are doing what we think they are."""

    def setUp(self):
        self.cs = caseSettings.Settings()
        self.settings = {
            "nTasks": {
                "valid": 1,
                "invalid": -1,
                "error": RuntimeError,
            },
            "axialMeshRefinementFactor": {
                "valid": 1,
                "invalid": 0,
                "error": RuntimeError,
            },
            "minMeshSizeRatio": {
                "valid": 1,
                "invalid": 0,
                "error": RuntimeError,
            },
            "cycleLength": {
                "valid": 1,
                "invalid": -1,
                "error": RuntimeError,
            },
            "availabilityFactor": {
                "valid": 0,
                "invalid": -1,
                "error": RuntimeError,
            },
            "burnSteps": {
                "valid": 0,
                "invalid": -1,
                "error": RuntimeError,
            },
            "beta": {
                "valid": [0.5, 0.5],
                "invalid": [0.5, 2],
                "error": RuntimeError,
            },
            "decayConstants": {
                "valid": [1, 1],
                "invalid": [-1, 1],
                "error": RuntimeError,
            },
            "buGroups": {
                "valid": [1, 5],
                "invalid": [-1, 200],
                "error": RuntimeError,
            },
            "burnupPeakingFactor": {
                "valid": 0,
                "invalid": -1,
                "error": RuntimeError,
            },
            "startCycle": {
                "valid": 1,
                "invalid": -1,
                "error": RuntimeError,
            },
            "startNode": {
                "valid": 0,
                "invalid": -1,
                "error": RuntimeError,
            },
            "nCycles": {"valid": 1, "invalid": -1, "error": RuntimeError},
            "power": {"valid": 0, "invalid": -1, "error": RuntimeError},
            "skipCycles": {
                "valid": 0,
                "invalid": -1,
                "error": RuntimeError,
            },
            "targetK": {"valid": 1, "invalid": -1, "error": RuntimeError},
            "acceptableBlockAreaError": {
                "valid": 1,
                "invalid": 0,
                "error": RuntimeError,
            },
            "Tin": {"valid": -272, "invalid": -274, "error": RuntimeError},
            "Tout": {
                "valid": -272,
                "invalid": -274,
                "error": RuntimeError,
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
