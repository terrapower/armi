"""Unit test for Beryllium"""
import unittest

from armi.materials.be9 import Be9
from armi.materials.tests import test_materials


class Test_Be9(test_materials._Material_Test, unittest.TestCase):
    """Be tests"""

    MAT_CLASS = Be9

    def test_density(self):
        cur = self.mat.density(Tc=25)
        ref = 1.85
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)


if __name__ == "__main__":
    unittest.main()
