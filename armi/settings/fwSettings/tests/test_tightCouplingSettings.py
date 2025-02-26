# Copyright 2023 TerraPower, LLC
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
Unit testing for tight coupling settings.

- The settings example below shows the intended use for these settings in
  an ARMI yaml input file.
- Note, for these to be recognized, they need to be prefixed with "tightCouplingSettings:".
"""

import io
import unittest

import voluptuous as vol
from ruamel.yaml import YAML

from armi.settings.fwSettings.tightCouplingSettings import (
    TightCouplingSettingDef,
    tightCouplingSettingsValidator,
)

TIGHT_COUPLING_SETTINGS_EXAMPLE = """
    globalFlux:
        parameter: keff
        convergence: 1e-05
    fuelPerformance:
        parameter: peakFuelTemperature
        convergence: 1e-02
    """


class TestTightCouplingSettings(unittest.TestCase):
    def test_validAssignments(self):
        """Tests that the tight coupling settings dictionary can be added to."""
        tc = {}
        tc["globalFlux"] = {"parameter": "keff", "convergence": 1e-05}
        tc["thermalHydraulics"] = {
            "parameter": "peakCladdingTemperature",
            "convergence": 1e-02,
        }
        tc = tightCouplingSettingsValidator(tc)
        self.assertEqual(tc["globalFlux"]["parameter"], "keff")
        self.assertEqual(tc["globalFlux"]["convergence"], 1e-05)
        self.assertEqual(tc["thermalHydraulics"]["parameter"], "peakCladdingTemperature")
        self.assertEqual(tc["thermalHydraulics"]["convergence"], 1e-02)

    def test_incompleteAssignment(self):
        """Tests that the tight coupling settings is rendered empty if a complete dictionary is not provided."""
        tc = {}
        tc["globalFlux"] = None
        tc = tightCouplingSettingsValidator(tc)
        self.assertNotIn("globalFlux", tc.keys())

        tc = {}
        tc["globalFlux"] = {}
        tc = tightCouplingSettingsValidator(tc)
        self.assertNotIn("globalFlux", tc.keys())

    def test_missingAssignments(self):
        """Tests failure if not all keys/value pairs are provided on initialization."""
        # Fails because `convergence` is not assigned at the same
        # time as the `parameter` assignment.
        with self.assertRaises(vol.MultipleInvalid):
            tc = {}
            tc["globalFlux"] = {"parameter": "keff"}
            tc = tightCouplingSettingsValidator(tc)

        # Fails because `parameter` is not assigned at the same
        # time as the `convergence` assignment.
        with self.assertRaises(vol.MultipleInvalid):
            tc = {}
            tc["globalFlux"] = {"convergence": 1e-08}
            tc = tightCouplingSettingsValidator(tc)

    def test_invalidArgumentTypes(self):
        """Tests failure when the values of the parameters do not match the expected schema."""
        # Fails because `parameter` value is required to be a string
        with self.assertRaises(vol.MultipleInvalid):
            tc = {}
            tc["globalFlux"] = {"parameter": 1.0}
            tc = tightCouplingSettingsValidator(tc)

        # Fails because `convergence` value is required to be something can be coerced into a float
        with self.assertRaises(vol.MultipleInvalid):
            tc = {}
            tc["globalFlux"] = {"convergence": "keff"}
            tc = tightCouplingSettingsValidator(tc)

    def test_extraAssignments(self):
        """
        Tests failure if additional keys are supplied that do not match the expected schema or
        if there are any typos in the expected keys.
        """
        # Fails because the `parameter` key is misspelled.
        with self.assertRaises(vol.MultipleInvalid):
            tc = {}
            tc["globalFlux"] = {"parameters": "keff", "convergence": 1e-05}
            tc = tightCouplingSettingsValidator(tc)

        # Fails because of the `extra` key.
        with self.assertRaises(vol.MultipleInvalid):
            tc = {}
            tc["globalFlux"] = {
                "parameter": "keff",
                "convergence": 1e-05,
                "extra": "fails",
            }
            tc = tightCouplingSettingsValidator(tc)

    def test_serializeSettingsException(self):
        """Ensure the TypeError in serializeTightCouplingSettings can be reached."""
        tc = ["globalFlux"]
        with self.assertRaises(TypeError) as cm:
            tc = tightCouplingSettingsValidator(tc)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_yamlIO(self):
        """Ensure we can read/write this custom setting object to yaml."""
        yaml = YAML()
        inp = yaml.load(io.StringIO(TIGHT_COUPLING_SETTINGS_EXAMPLE))
        tcd = TightCouplingSettingDef("TestSetting")
        tcd.setValue(inp)
        self.assertEqual(tcd.value["globalFlux"]["parameter"], "keff")
        outBuf = io.StringIO()
        output = tcd.dump()
        yaml.dump(output, outBuf)
        outBuf.seek(0)
        inp2 = yaml.load(outBuf)
        self.assertEqual(inp.keys(), inp2.keys())
