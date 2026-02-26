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
"""Tests for lithium."""

import unittest

from armi.materials.lithium import Lithium
from armi.materials.tests.test_materials import AbstractMaterialTest


class Lithium_TestCase(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = Lithium

    def setUp(self):
        AbstractMaterialTest.setUp(self)
        self.mat = Lithium()

        self.Lithium_LI_wt_frac = Lithium()
        self.Lithium_LI_wt_frac.applyInputParams(LI6_wt_frac=0.5)

        self.Lithium_LI6_wt_frac = Lithium()
        self.Lithium_LI6_wt_frac.applyInputParams(LI6_wt_frac=0.6)

        self.Lithium_both = Lithium()
        self.Lithium_both.applyInputParams(LI6_wt_frac=0.8)

    def test_Lithium_material_modifications(self):
        self.assertEqual(self.mat.getMassFrac("LI6"), 0.0759)
        self.assertAlmostEqual(self.Lithium_LI_wt_frac.getMassFrac("LI6"), 0.5, places=10)
        self.assertAlmostEqual(self.Lithium_LI6_wt_frac.getMassFrac("LI6"), 0.6, places=10)
        self.assertAlmostEqual(self.Lithium_both.getMassFrac("LI6"), 0.8, places=10)

    def test_pseudoDensity(self):
        ref = self.mat.pseudoDensity(Tc=100)
        self.assertAlmostEqual(ref, 0.512, delta=abs(ref * 0.001))

        ref = self.mat.pseudoDensity(Tc=200)
        self.assertAlmostEqual(ref, 0.512, delta=abs(ref * 0.001))

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

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)
