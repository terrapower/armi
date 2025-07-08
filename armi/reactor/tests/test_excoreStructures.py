# Copyright 2024 TerraPower, LLC
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
"""Direct tests of the Excore Structures and Spent Fuel Pools."""

from unittest import TestCase
from unittest.mock import MagicMock

from armi.reactor import grids
from armi.reactor.composites import Composite
from armi.reactor.excoreStructure import ExcoreCollection, ExcoreStructure
from armi.reactor.reactors import Reactor
from armi.reactor.spentFuelPool import SpentFuelPool
from armi.reactor.tests.test_assemblies import makeTestAssembly


class TestExcoreStructure(TestCase):
    def test_constructor(self):
        evst1 = ExcoreStructure("evst1")
        self.assertEqual(evst1.name, "evst1")
        self.assertIsNone(evst1.parent)
        self.assertIsNone(evst1.spatialGrid)

        evst2 = ExcoreStructure("evst2", parent=evst1)
        self.assertEqual(evst2.name, "evst2")
        self.assertEqual(evst2.parent, evst1)
        self.assertIsNone(evst2.spatialGrid)

    def test_representation(self):
        evst7 = ExcoreStructure("evst7")
        rep = evst7.__repr__()
        self.assertIn("ExcoreStructure", rep)
        self.assertIn("evst7", rep)
        self.assertIn("id:", rep)

    def test_parentReactor(self):
        fr = Reactor("Reactor", MagicMock())
        evst3 = ExcoreStructure("evst3", parent=fr)
        self.assertEqual(evst3.r, fr)

    def test_add(self):
        # build an ex-core structure
        ivs = ExcoreStructure("ivs")
        ivs.spatialGrid = grids.CartesianGrid.fromRectangle(1.0, 1.0)

        # add one composite object and validate
        comp1 = Composite("thing1")
        loc = ivs.spatialGrid[(-5, -5, 0)]

        self.assertEqual(len(ivs.getChildren()), 0)
        ivs.add(comp1, loc)
        self.assertEqual(len(ivs.getChildren()), 1)

        # add another composite object and validate
        comp1 = Composite("thing2")
        loc = ivs.spatialGrid[(1, -4, 0)]

        ivs.add(comp1, loc)
        self.assertEqual(len(ivs.getChildren()), 2)


class TestSpentFuelPool(TestCase):
    def setUp(self):
        self.sfp = SpentFuelPool("sfp")
        self.sfp.spatialGrid = grids.CartesianGrid.fromRectangle(1.0, 1.0)

    def test_constructor(self):
        """Show that the spent fuel pool is a composite.

        .. test:: The spent fuel pool is a Composite structure.
            :id: T_ARMI_SFP0
            :tests: R_ARMI_SFP
        """
        self.assertEqual(self.sfp.name, "sfp")
        self.assertIsNone(self.sfp.parent)
        self.assertIsNone(self.sfp.numColumns)
        self.assertTrue(isinstance(self.sfp, Composite))
        self.assertTrue(isinstance(self.sfp, ExcoreStructure))
        self.assertTrue(isinstance(self.sfp.spatialGrid, grids.CartesianGrid))

    def test_representation(self):
        rep = self.sfp.__repr__()
        self.assertIn("SpentFuelPool", rep)
        self.assertIn("sfp", rep)
        self.assertIn("id:", rep)

    def test_addRemove(self):
        """Show that we can add and remove Assemblies from the spent fuel pool.

        .. test:: Show that we can add and remove Assemblies from the spent fuel pool.
            :id: T_ARMI_SFP1
            :tests: R_ARMI_SFP
        """
        self.assertEqual(len(self.sfp.getChildren()), 0)

        # add one assembly object and validate
        a0 = makeTestAssembly(1, 987, spatialGrid=self.sfp.spatialGrid)
        self.sfp.add(a0)
        self.assertEqual(len(self.sfp.getChildren()), 1)

        # add another assembly object and validate
        a1 = makeTestAssembly(1, 988, spatialGrid=self.sfp.spatialGrid)
        loc = self.sfp.spatialGrid[(1, -4, 0)]
        self.sfp.add(a1, loc)
        self.assertEqual(len(self.sfp.getChildren()), 2)

        # remove the first assembly we added and validate
        self.sfp.remove(a0)
        self.assertEqual(len(self.sfp.getChildren()), 1)

    def test_getAssembly(self):
        a0 = makeTestAssembly(1, 678, spatialGrid=self.sfp.spatialGrid)
        self.sfp.add(a0)

        aReturn = self.sfp.getAssembly("A0678")
        self.assertEqual(aReturn, a0)

    def test_updateNumberOfColumns(self):
        self.assertIsNone(self.sfp.numColumns)
        self.sfp._updateNumberOfColumns()
        self.assertEqual(self.sfp.numColumns, 10)

    def test_getNextLocation(self):
        self.sfp._updateNumberOfColumns()

        # test against an empty grid
        loc = self.sfp._getNextLocation()
        self.assertEqual(loc._i, 0)
        self.assertEqual(loc._j, 0)
        self.assertEqual(loc._k, 0)

        # test against a non-empty grid
        a0 = makeTestAssembly(1, 234, spatialGrid=self.sfp.spatialGrid)
        self.sfp.add(a0)

    def test_normalizeNames(self):
        # test against an empty grid
        self.assertEqual(self.sfp.normalizeNames(), 0)
        self.assertEqual(self.sfp.normalizeNames(17), 17)

        # test against a non-empty grid
        a0 = makeTestAssembly(1, 456, spatialGrid=self.sfp.spatialGrid)
        self.sfp.add(a0)
        self.assertEqual(self.sfp.normalizeNames(), 1)
        self.assertEqual(self.sfp.normalizeNames(17), 18)


class TestExcoreCollection(TestCase):
    def test_addLikeDict(self):
        sfp = SpentFuelPool("sfp")

        excore = ExcoreCollection()
        excore["sfp"] = sfp

        self.assertTrue(isinstance(excore["sfp"], SpentFuelPool))
        self.assertTrue(isinstance(excore.sfp, SpentFuelPool))

    def test_addLikeAttribute(self):
        ivs = ExcoreStructure("ivs")

        excore = ExcoreCollection()
        excore.ivs = ivs

        self.assertTrue(isinstance(excore["ivs"], ExcoreStructure))
        self.assertTrue(isinstance(excore.ivs, ExcoreStructure))
