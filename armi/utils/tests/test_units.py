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
"""Test armi.utils.units.py"""
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
