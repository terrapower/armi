"""
Tests for graphite material
"""
import unittest


from armi.materials.graphite import Graphite
from armi.materials.tests import test_materials


class Graphite_TestCase(test_materials._Material_Test, unittest.TestCase):
    MAT_CLASS = Graphite


if __name__ == "__main__":
    unittest.main()
