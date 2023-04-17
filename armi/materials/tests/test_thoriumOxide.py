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
"""
Tests for ThO2
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import unittest

from armi.materials.tests.test_materials import _Material_Test
from armi.materials.thoriumOxide import ThoriumOxide


class ThoriumOxide_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = ThoriumOxide

    def setUp(self):
        _Material_Test.setUp(self)
        self.mat = ThoriumOxide()

        self.ThoriumOxide_TD_frac = ThoriumOxide()
        self.ThoriumOxide_TD_frac.applyInputParams(TD_frac=0.4)

    def test_theoretical_pseudoDensity(self):
        ref = self.mat.pseudoDensity(500)

        reduced = self.ThoriumOxide_TD_frac.pseudoDensity(500)
        self.assertAlmostEqual(ref * 0.4, reduced)

    def test_linearExpansionPercent(self):
        self.assertAlmostEqual(self.mat.linearExpansionPercent(Tk=500), 0.195334)

    def test_propertyValidTemperature(self):
        self.assertGreater(len(self.mat.propertyValidTemperature), 0)


if __name__ == "__main__":
    unittest.main()
