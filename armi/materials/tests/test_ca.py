import pickle
import math
import unittest

from numpy import testing

from armi import materials, settings
from armi.nucDirectory import nuclideBases
from armi.reactor import blueprints
from armi.utils import units
from armi.materials.tests.test_materials import _Material_Test


class Californium_TestCase(_Material_Test, unittest.TestCase):

    MAT_CLASS = materials.Californium

    def test_density(self):
        ref = 15.1

        cur = self.mat.density(923)
        self.assertEqual(cur, ref)

        cur = self.mat.density(1390)
        self.assertEqual(cur, ref)

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)

    def test_porosities(self):
        self.mat.parent = None
        self.assertEqual(self.mat.liquidPorosity, 0.0)
        self.assertEqual(self.mat.gasPorosity, 0.0)
