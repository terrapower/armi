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
Tests for boron carbide
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import unittest

from armi.materials.b4c import B4C, DEFAULT_THEORETICAL_DENSITY_FRAC
from armi.materials.tests.test_materials import _Material_Test


class B4C_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = B4C

    def setUp(self):
        _Material_Test.setUp(self)
        self.mat = B4C()

    def test_theoretical_density(self):
        ref = self.mat.density(500)

        B4C_theoretical_density = B4C()
        B4C_theoretical_density.applyInputParams(theoretical_density=0.5)
        reduced = B4C_theoretical_density.density(500)
        self.assertAlmostEqual(ref * 0.5 / DEFAULT_THEORETICAL_DENSITY_FRAC, reduced)

        B4C_TD_frac = B4C()
        B4C_TD_frac.applyInputParams(TD_frac=0.4)
        reduced = B4C_TD_frac.density(500)
        self.assertAlmostEqual(ref * 0.4 / DEFAULT_THEORETICAL_DENSITY_FRAC, reduced)

        B4C_both = B4C()
        B4C_both.applyInputParams(theoretical_density=0.5, TD_frac=0.4)
        reduced = B4C_both.density(500)
        self.assertAlmostEqual(ref * 0.4 / DEFAULT_THEORETICAL_DENSITY_FRAC, reduced)

    def test_propertyValidTemperature(self):
        self.assertGreater(len(self.mat.propertyValidTemperature), 0)


if __name__ == "__main__":
    unittest.main()
