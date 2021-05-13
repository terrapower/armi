"""
Tests for graphite material
"""
import unittest

from armi.materials.graphite import Graphite
from armi.materials.tests import test_materials


class Graphite_TestCase(unittest.TestCase):
    MAT_CLASS = Graphite

    def setUp(self):
        self.mat = self.MAT_CLASS()

    def test_linearExpansionPercent(self):
        accuracy = 2

        cur = self.mat.linearExpansionPercent(330)
        ref = 0.013186
        self.assertAlmostEqual(cur, ref, accuracy)

        cur = self.mat.linearExpansionPercent(1500)
        ref = 0.748161
        self.assertAlmostEqual(cur, ref, accuracy)

        cur = self.mat.linearExpansionPercent(3000)
        ref = 2.149009
        self.assertAlmostEqual(cur, ref, accuracy)


if __name__ == "__main__":
    unittest.main()
