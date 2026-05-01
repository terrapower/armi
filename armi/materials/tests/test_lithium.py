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
"""Tests for liquid Lithium."""

import unittest

from armi.materials import Lithium
from armi.materials.tests.test_materials import AbstractMaterialTest


class LithiumTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = Lithium

    def setUp(self):
        AbstractMaterialTest.setUp(self)
        self.mat = Lithium()

    def test_liAbundance(self):
        self.assertGreaterEqual(self.mat.getMassFrac("LI6"), 0.019)
        self.assertLessEqual(self.mat.getMassFrac("LI6"), 0.078)
        self.assertGreater(self.mat.getMassFrac("LI7"), 0.90)

    def test_lithiumMatMods(self):
        li5 = Lithium()
        li5.applyInputParams(LI6_wt_frac=0.5)

        li6 = Lithium()
        li6.applyInputParams(LI6_wt_frac=0.6)

        li8 = Lithium()
        li8.applyInputParams(LI6_wt_frac=0.8)

        self.assertAlmostEqual(li5.getMassFrac("LI6"), 0.5, places=10)
        self.assertAlmostEqual(li6.getMassFrac("LI6"), 0.6, places=10)
        self.assertAlmostEqual(li8.getMassFrac("LI6"), 0.8, places=10)

    def test_pseudoDensity(self):
        ref = self.mat.pseudoDensity(Tc=200)
        self.assertAlmostEqual(ref, 0.512, delta=abs(ref * 0.001))

        ref = self.mat.pseudoDensity(Tc=500)
        self.assertAlmostEqual(ref, 0.512, delta=abs(ref * 0.001))

    def test_boilingPoint(self):
        ref = self.mat.T_boil(T=300)  # Celcius
        cur = 1341.85
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

    def test_heatCapacity(self):
        ref = self.mat.heatCapacity(Tc=200)
        cur = 3570.0
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

        ref = self.mat.heatCapacity(Tc=500)
        cur = 3570.0
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))
