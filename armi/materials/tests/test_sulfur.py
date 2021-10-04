"""
Tests for sulfur.
"""

import unittest

from armi.materials.tests.test_materials import _Material_Test
from armi.materials.sulfur import Sulfur


class Sulfur_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = Sulfur

    def setUp(self):
        _Material_Test.setUp(self)
        self.mat = Sulfur()
        
        self.Sulfur_sulfur_density_frac = Sulfur()
        self.Sulfur_sulfur_density_frac.applyInputParams(sulfur_density_frac=0.5)

        self.Sulfur_TD_frac = Sulfur()
        self.Sulfur_TD_frac.applyInputParams(TD_frac=0.4)

        self.Sulfur_both = Sulfur()
        self.Sulfur_both.applyInputParams(sulfur_density_frac=0.5, TD_frac=0.4)

    def test_sulfur_density_frac(self):
        ref = self.mat.density(500)

        reduced = self.Sulfur_sulfur_density_frac.density(500)
        self.assertAlmostEqual(ref * 0.5, reduced)

        reduced = self.Sulfur_TD_frac.density(500)
        self.assertAlmostEqual(ref * 0.4, reduced)

        reduced = self.Sulfur_both.density(500)
        self.assertAlmostEqual(ref * 0.4, reduced)


if __name__ == "__main__":
    unittest.main()