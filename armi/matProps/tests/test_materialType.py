# Copyright 2026 TerraPower, LLC
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

"""Tests the MaterialType class."""

import unittest

from armi.matProps.materialType import MaterialType


class TestMaterialType(unittest.TestCase):
    def test_fromString(self):
        mt = MaterialType.fromString("Fuel")
        self.assertEqual(mt._value, 1)

        mt = MaterialType.fromString("Metal")
        self.assertEqual(mt._value, 2)

        mt = MaterialType.fromString("Fluid")
        self.assertEqual(mt._value, 4)

    def test_repr(self):
        mt = MaterialType.fromString("Fuel")
        self.assertEqual(str(mt), "<MaterialType Fuel>")

        mt = MaterialType.fromString("Metal")
        self.assertEqual(str(mt), "<MaterialType Metal>")

        mt = MaterialType.fromString("Fluid")
        self.assertEqual(str(mt), "<MaterialType Fluid>")

    def test_equality(self):
        mt1 = MaterialType(1)
        mt11 = MaterialType(1)
        mt4 = MaterialType(4)

        self.assertTrue(mt1 == mt1)
        self.assertTrue(mt1 == mt11)
        self.assertFalse(mt1 == mt4)
        self.assertFalse(mt11 == mt4)

        self.assertTrue(mt1 == 1)
        self.assertTrue(mt11 == 1)
        self.assertFalse(mt1 == 4)
        self.assertFalse(mt11 == 4)

        with self.assertRaises(TypeError):
            self.assertTrue(mt1 == "1")
