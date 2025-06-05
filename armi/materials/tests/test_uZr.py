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

"""Tests for simplified UZr material."""

import pickle
from unittest import TestCase

from armi.materials.uZr import UZr


class UZR_TestCase(TestCase):
    MAT_CLASS = UZr

    def setUp(self):
        self.mat = self.MAT_CLASS()

    def test_isPicklable(self):
        """Test that materials are picklable so we can do MPI communication of state.

        .. test:: Test the material base class has temp-dependent thermal conductivity curves.
            :id: T_ARMI_MAT_PROPERTIES0
            :tests: R_ARMI_MAT_PROPERTIES
        """
        stream = pickle.dumps(self.mat)
        mat = pickle.loads(stream)

        # check a property that is sometimes interpolated.
        self.assertEqual(self.mat.thermalConductivity(500), mat.thermalConductivity(500))

    def test_TD(self):
        """Test the material theoretical density."""
        self.assertEqual(self.mat.getTD(), self.mat.theoreticalDensityFrac)

        self.mat.clearCache()
        self.mat._setCache("dummy", 666)
        self.assertEqual(self.mat.cached, {"dummy": 666})
        self.mat.adjustTD(0.5)
        self.assertEqual(0.5, self.mat.theoreticalDensityFrac)
        self.assertEqual(self.mat.cached, {})

    def test_duplicate(self):
        """Test the material duplication.

        .. test:: Materials shall calc mass fracs at init.
            :id: T_ARMI_MAT_FRACS5
            :tests: R_ARMI_MAT_FRACS
        """
        mat = self.mat.duplicate()

        self.assertEqual(len(mat.massFrac), len(self.mat.massFrac))
        for key in self.mat.massFrac:
            self.assertEqual(mat.massFrac[key], self.mat.massFrac[key])

        self.assertEqual(mat.parent, self.mat.parent)
        self.assertEqual(mat.refDens, self.mat.refDens)
        self.assertEqual(mat.theoreticalDensityFrac, self.mat.theoreticalDensityFrac)

    def test_cache(self):
        """Test the material cache."""
        self.mat.clearCache()
        self.assertEqual(len(self.mat.cached), 0)

        self.mat._setCache("Emmy", "Noether")
        self.assertEqual(len(self.mat.cached), 1)

        val = self.mat._getCached("Emmy")
        self.assertEqual(val, "Noether")

    def test_densityKgM3(self):
        """Test the density for kg/m^3.

        .. test:: Test the material base class has temp-dependent density.
            :id: T_ARMI_MAT_PROPERTIES2
            :tests: R_ARMI_MAT_PROPERTIES
        """
        dens = self.mat.density(500)
        densKgM3 = self.mat.densityKgM3(500)
        self.assertEqual(dens * 1000.0, densKgM3)

    def test_pseudoDensityKgM3(self):
        """Test the pseudo density for kg/m^3.

        .. test:: Test the material base class has temp-dependent 2D density.
            :id: T_ARMI_MAT_PROPERTIES3
            :tests: R_ARMI_MAT_PROPERTIES
        """
        dens = self.mat.pseudoDensity(500)
        densKgM3 = self.mat.pseudoDensityKgM3(500)
        self.assertEqual(dens * 1000.0, densKgM3)

    def test_density(self):
        """Test that all materials produce a zero density from density.

        .. test:: Test the material base class has temp-dependent density.
            :id: T_ARMI_MAT_PROPERTIES1
            :tests: R_ARMI_MAT_PROPERTIES
        """
        self.assertNotEqual(self.mat.density(500), 0)

        cur = self.mat.density(400)
        ref = 15.94
        delta = ref * 0.01
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)
