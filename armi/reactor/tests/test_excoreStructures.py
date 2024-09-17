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

from armi.reactor.excoreStructure import ExcoreStructure
from armi.reactor.spentFuelPool import SpentFuelPool


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
        pass

    def test_add(self):
        pass


class TestSpentFuelPool(TestCase):
    def setUp(self):
        self.sfp = SpentFuelPool("sfp")

    def test_constructor(self):
        self.assertEqual(self.sfp.name, "sfp")
        self.assertIsNone(self.sfp.parent)
        self.assertIsNone(self.sfp.spatialGrid)
        self.assertIsNone(self.sfp.numColumns)

    def test_representation(self):
        rep = self.sfp.__repr__()
        self.assertIn("SpentFuelPool", rep)
        self.assertIn("sfp", rep)
        self.assertIn("id:", rep)

    def test_add(self):
        pass

    def test_getAssembly(self):
        pass

    def test_updateNumberOfColumns(self):
        pass

    def test_getNextLocation(self):
        pass

    def test_normalizeNames(self):
        pass
