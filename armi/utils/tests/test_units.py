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
"""Test armi.utils.units.py."""

import unittest

from armi.utils import units


class TestUnits(unittest.TestCase):
    def test_getTc(self):
        self.assertAlmostEqual(units.getTc(Tc=200), 200.0)
        self.assertAlmostEqual(units.getTc(Tk=300), 26.85)

        ## error if no argument provided
        with self.assertRaisesRegex(ValueError, "Tc=None and Tk=None"):
            units.getTc()

        ## error if two arguments provided even if those arguments are "falsy"
        with self.assertRaisesRegex(ValueError, "Tc=0 and Tk=0"):
            units.getTc(Tc=0, Tk=0)

        with self.assertRaisesRegex(ValueError, "Tc=0 and Tk=200"):
            units.getTc(Tc=0, Tk=200)

    def test_getTk(self):
        self.assertAlmostEqual(units.getTk(Tc=200), 473.15)
        self.assertAlmostEqual(units.getTk(Tk=300), 300.00)

        ## error if no argument provided
        with self.assertRaisesRegex(ValueError, "Tc=None and Tk=None"):
            units.getTk()

        ## error if two arguments provided even if those arguments are "falsy"
        with self.assertRaisesRegex(ValueError, "Tc=0 and Tk=0"):
            units.getTk(Tc=0, Tk=0)

        with self.assertRaisesRegex(ValueError, "Tc=0 and Tk=200"):
            units.getTk(Tc=0, Tk=200)

    def test_getTf(self):
        # 0 C = 32 F
        self.assertAlmostEqual(units.getTf(Tc=0), 32.0)
        self.assertAlmostEqual(units.getTf(Tk=273.15), 32.0)

        # 100 C = 212 F
        self.assertAlmostEqual(units.getTf(Tc=100), 212.0)
        self.assertAlmostEqual(units.getTf(Tk=373.15), 212.0)

        # -40 C = -40 F
        self.assertAlmostEqual(units.getTf(Tc=-40), -40)

        ## error if no argument provided
        with self.assertRaisesRegex(ValueError, "Tc=None and Tk=None"):
            units.getTf()

        ## error if two arguments provided even if those arguments are "falsy"
        with self.assertRaisesRegex(ValueError, "Tc=0 and Tk=0"):
            units.getTf(Tc=0, Tk=0)

        with self.assertRaisesRegex(ValueError, "Tc=0 and Tk=200"):
            units.getTf(Tc=0, Tk=200)

    def test_pressure_converter(self):
        """Converter Pascals to Pascals should just be a pass-through."""
        for val in [0.0, -99.141, 123, 3.14159, -2.51212e-12]:
            self.assertEqual(val, units.PRESSURE_CONVERTERS["Pa"](val))

    def test_getTmev(self):
        val = units.getTmev(Tc=45.0)
        self.assertAlmostEqual(val, 2.74160430306e-08)

        val = units.getTmev(Tc=145.0)
        self.assertAlmostEqual(val, 3.60333754306e-08)

        val = units.getTmev(Tk=445.0)
        self.assertAlmostEqual(val, 3.8347129180000004e-08)

    def test_getTemperature(self):
        val = units.getTemperature(Tc=42, tempUnits="Tc")
        self.assertEqual(val, 42)

        val = units.getTemperature(Tk=42, tempUnits="Tk")
        self.assertEqual(val, 42)

        val = units.getTemperature(Tc=42, tempUnits="Tk")
        self.assertAlmostEqual(val, 315.15)

        val = units.getTemperature(Tk=42, tempUnits="Tc")
        self.assertAlmostEqual(val, -231.15)

        with self.assertRaises(ValueError):
            units.getTemperature(Tc=42)

    def test_convertXtoPascal(self):
        val = units.convertMmhgToPascal(11.1)
        self.assertAlmostEqual(val, 1479.8782894736883)

        val = units.convertBarToPascal(2.2)
        self.assertAlmostEqual(val, 220000)

        val = units.convertAtmToPascal(3.1)
        self.assertAlmostEqual(val, 314107.5)

    def test_sanitizeAngle(self):
        val = units.sanitizeAngle(0)
        self.assertEqual(val, 0)

        val = units.sanitizeAngle(1.01)
        self.assertEqual(val, 1.01)

        val = units.sanitizeAngle(-6)
        self.assertAlmostEqual(val, 0.28318530717958623)

        val = units.sanitizeAngle(9)
        self.assertAlmostEqual(val, 2.7168146928204138)

    def test_getXYLineParameters(self):
        a, b, c, d = units.getXYLineParameters(0)
        self.assertEqual(a, 0.0)
        self.assertEqual(b, 1.0)
        self.assertEqual(c, 0.0)
        self.assertEqual(d, 0.0)

        a, b, c, d = units.getXYLineParameters(1, 0.1, 0.2)
        self.assertEqual(a, 1)
        self.assertEqual(b, 0)
        self.assertEqual(c, 0)
        self.assertEqual(d, 0.1)
