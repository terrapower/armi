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
Tests for lithium.
"""

import unittest

from armi.materials.tests.test_materials import _Material_Test
from armi.materials.lithium import Lithium
from armi.nucDirectory import nuclideBases as nb


class Lithium_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = Lithium
    defaultMassFrac = nb.byName["LI6"].abundance

    def setUp(self):
        _Material_Test.setUp(self)
        self.mat = Lithium()

        self.Lithium_LI_wt_frac = Lithium()
        self.Lithium_LI_wt_frac.applyInputParams(LI_wt_frac=0.5)

        self.Lithium_LI6_wt_frac = Lithium()
        self.Lithium_LI6_wt_frac.applyInputParams(LI6_wt_frac=0.6)

        self.Lithium_both = Lithium()
        self.Lithium_both.applyInputParams(LI_wt_frac=0.7, LI6_wt_frac=0.8)

    def test_Lithium_material_modifications(self):
        self.assertEqual(self.mat.getMassFrac("LI6"), self.defaultMassFrac)

        self.assertEqual(self.Lithium_LI_wt_frac.getMassFrac("LI6"), 0.5)

        self.assertEqual(self.Lithium_LI6_wt_frac.getMassFrac("LI6"), 0.6)

        self.assertEqual(self.Lithium_both.getMassFrac("LI6"), 0.8)

    def test_density(self):
        ref = self.mat.density(Tc=100)
        cur = 0.512
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

        ref = self.mat.density(Tc=200)
        cur = 0.512
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

    def test_meltingPoint(self):
        ref = self.mat.meltingPoint()
        cur = 453.69
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

    def test_boilingPoint(self):
        ref = self.mat.boilingPoint()
        cur = 1615.0
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

    def test_heatCapacity(self):
        ref = self.mat.heatCapacity(Tc=100)
        cur = 3570.0
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

        ref = self.mat.heatCapacity(Tc=200)
        cur = 3570.0
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))


if __name__ == "__main__":
    unittest.main()
