import pickle
import math
import unittest

from numpy import testing

from armi import materials, settings
from armi.nucDirectory import nuclideBases
from armi.reactor import blueprints
from armi.utils import units
from armi.materials.tests.test_materials import _Material_Test


class MOX_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.MOX

    def test_density(self):
        cur = self.mat.density3(333)
        ref = 10.926
        delta = ref * 0.0001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_getMassFracPuO2(self):
        ref = 0.176067
        self.assertAlmostEqual(self.mat.getMassFracPuO2(), ref, delta=ref * 0.001)

    def test_getMolFracPuO2(self):
        ref = 0.209
        self.assertAlmostEqual(self.mat.getMolFracPuO2(), ref, delta=ref * 0.001)

    def test_getMolFracPuO2(self):
        ref = 2996.788765
        self.assertAlmostEqual(self.mat.meltingPoint(), ref, delta=ref * 0.001)

    def test_applyInputParams(self):
        massFracNameList = [
            "AM241",
            "O16",
            "PU238",
            "PU239",
            "PU240",
            "PU241",
            "PU242",
            "U235",
            "U238",
        ]
        massFracRefValList = [
            0.000998,
            0.118643,
            0.000156,
            0.119839,
            0.029999,
            0.00415,
            0.000858,
            0.166759,
            0.558597,
        ]

        self.mat.applyInputParams()

        for name, frac in zip(massFracNameList, massFracRefValList):
            cur = self.mat.massFrac[name]
            self.assertEqual(cur, frac)
