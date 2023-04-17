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
"""
Tests for sulfur.
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import unittest

from armi.materials.tests.test_materials import _Material_Test
from armi.materials.sulfur import Sulfur


class Sulfur_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = Sulfur

    def setUp(self):
        _Material_Test.setUp(self)
        self.mat = Sulfur()

        self.Sulfur_sulfur_density_frac = Sulfur()
        self.Sulfur_sulfur_density_frac.applyInputParams(sulfur_density_frac=0.5)

        self.Sulfur_TD_frac = Sulfur()
        self.Sulfur_TD_frac.applyInputParams(TD_frac=0.4)

        self.Sulfur_both = Sulfur()
        self.Sulfur_both.applyInputParams(sulfur_density_frac=0.5, TD_frac=0.4)

    def test_sulfur_density_frac(self):
        ref = self.mat.pseudoDensity(500)

        reduced = self.Sulfur_sulfur_density_frac.pseudoDensity(500)
        self.assertAlmostEqual(ref * 0.5, reduced)

        reduced = self.Sulfur_TD_frac.pseudoDensity(500)
        self.assertAlmostEqual(ref * 0.4, reduced)

        reduced = self.Sulfur_both.pseudoDensity(500)
        self.assertAlmostEqual(ref * 0.4, reduced)

    def test_propertyValidTemperature(self):
        self.assertGreater(len(self.mat.propertyValidTemperature), 0)


if __name__ == "__main__":
    unittest.main()
