"""
Tests for boron carbide.
"""

import unittest

from armi.materials.tests.test_materials import _Material_Test
from armi.materials.b4c import B4C
from armi.materials.b4c import DEFAULT_THEORETICAL_DENSITY_FRAC


class B4C_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = B4C

    def setUp(self):
        _Material_Test.setUp(self)
        self.mat = B4C()

        self.B4C_theoretical_density = B4C()
        self.B4C_theoretical_density.applyInputParams(theoretical_density=0.5)

        self.B4C_TD_frac = B4C()
        self.B4C_TD_frac.applyInputParams(TD_frac=0.4)

        self.B4C_both = B4C()
        self.B4C_both.applyInputParams(theoretical_density=0.5, TD_frac=0.4)

    def test_theoretical_density(self):
        ref = self.mat.density(500)

        reduced = self.B4C_theoretical_density.density(500)
        self.assertAlmostEqual(ref * 0.5 / DEFAULT_THEORETICAL_DENSITY_FRAC, reduced)

        reduced = self.B4C_TD_frac.density(500)
        self.assertAlmostEqual(ref * 0.4 / DEFAULT_THEORETICAL_DENSITY_FRAC, reduced)

        reduced = self.B4C_both.density(500)
        self.assertAlmostEqual(ref * 0.4 / DEFAULT_THEORETICAL_DENSITY_FRAC, reduced)


if __name__ == "__main__":
    unittest.main()
