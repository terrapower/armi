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

"""Tests for the composite pattern."""

import unittest

from armi.nucDirectory import thermalScattering as ts


class TestThermalScattering(unittest.TestCase):
    def test_dataValidity(self):
        """Ensure that over time the raw thermal scattering data in ARMI remains valid."""
        for key, val in ts.BY_NAME_AND_COMPOUND.items():
            # nuclide name must be a non-empty string
            self.assertIsInstance(key[0], str)
            self.assertGreater(len(key[0]), 0)

            if key[1] is not None:
                # compound CAN be None, but otherwise must be a non-empty string
                self.assertIsInstance(key[1], str)
                self.assertGreater(len(key[1]), 0)

            # ENDF/B-VIII label must be a non-empty string
            self.assertIsInstance(val[0], str)
            self.assertGreater(len(val[0]), 0)

            # ACE label must be a non-empty string
            self.assertIsInstance(val[1], str)
            self.assertGreater(len(val[1]), 0)

    def test_fromNameCompInvalid(self):
        """If the name/compound inputs aren't valid, we should get a ValueError."""
        with self.assertRaises(ValueError):
            ts.fromNameAndCompound("hi", "mom")

        with self.assertRaises(ValueError):
            ts.fromNameAndCompound("C", None)

        with self.assertRaises(ValueError):
            ts.fromNameAndCompound("O", None)

        with self.assertRaises(ValueError):
            ts.fromNameAndCompound("FE56", "FE56")

    def test_fromNameCompSpotCheck(self):
        """Spot check some examples that should work."""
        tsl = ts.fromNameAndCompound("FE56", None)
        self.assertIsInstance(tsl, ts.ThermalScatteringLabels)
        self.assertEqual(tsl.endf8Label, "tsl-026_Fe_056.endf")
        self.assertEqual(tsl.aceLabel, "fe-56")

        tsl = ts.fromNameAndCompound("H", ts.H2O)
        self.assertIsInstance(tsl, ts.ThermalScatteringLabels)
        self.assertEqual(tsl.endf8Label, "tsl-HinH2O.endf")
        self.assertEqual(tsl.aceLabel, "h-h2o")

        tsl = ts.fromNameAndCompound("O", ts.D2O)
        self.assertIsInstance(tsl, ts.ThermalScatteringLabels)
        self.assertEqual(tsl.endf8Label, f"tsl-Oin{ts.D2O}.endf")
        self.assertEqual(tsl.aceLabel, "o-d2o")

        tsl = ts.fromNameAndCompound("U", ts.UO2)
        self.assertIsInstance(tsl, ts.ThermalScatteringLabels)
        self.assertEqual(tsl.endf8Label, "tsl-UinUO2.endf")
        self.assertEqual(tsl.aceLabel, "u-uo2")
