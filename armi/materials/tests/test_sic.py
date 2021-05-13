"""Test for SiC"""
import unittest

from armi.materials.siC import SiC
from armi.materials.tests import test_materials


class Test_SiC(test_materials._Material_Test, unittest.TestCase):
    """SiC tests"""

    MAT_CLASS = SiC

    def test_density(self):
        cur = self.mat.density(Tc=25)
        ref = 3.159
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_meltingPoint(self):
        cur = self.mat.meltingPoint()
        ref = 3003
        delta = ref * 0.0001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_heatCapacity(self):
        delta = 0.0001

        cur = self.mat.heatCapacity(300)
        ref = 982.20789
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.heatCapacity(1500)
        ref = 1330.27867
        self.assertAlmostEqual(cur, ref, delta=delta)


if __name__ == "__main__":
    unittest.main()
