import pickle
import math
import unittest

from numpy import testing

from armi import materials, settings
from armi.nucDirectory import nuclideBases
from armi.reactor import blueprints
from armi.utils import units
from armi.materials.tests.test_materials import _Material_Test


class Sodium_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Sodium

    def test_density(self):
        cur = self.mat.density(300)
        ref = 0.941
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.density(1700)
        ref = 0.597
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_specificVolumeLiquid(self):
        cur = self.mat.specificVolumeLiquid(300)
        ref = 0.001062
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.specificVolumeLiquid(1700)
        ref = 0.001674
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_enthalpy(self):
        cur = self.mat.enthalpy(300)
        ref = 107518.523
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.enthalpy(1700)
        ref = 1959147.963
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_thermalConductivity(self):
        cur = self.mat.thermalConductivity(300)
        ref = 95.1776
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.thermalConductivity(1700)
        ref = 32.616
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_propertyValidTemperature(self):
        self.assertGreater(len(self.mat.propertyValidTemperature), 0)
