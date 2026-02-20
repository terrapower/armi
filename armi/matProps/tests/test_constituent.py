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

"""Basic tests of the Constituent class."""

import unittest

from armi.matProps.constituent import Constituent


class TestConstituent(unittest.TestCase):
    def test_errorHandling(self):
        c = Constituent("Fe", 10.0, 25.0, False)
        self.assertEqual(str(c), "<Constituent Fe min: 10.0 max: 25.0>")

        c = Constituent("Fe", 0.0, 99.0, True)
        self.assertEqual(str(c), "<Constituent Fe min: 0.0 max: 99.0 computed based on balance>")

        with self.assertRaises(ValueError):
            Constituent("Fe", -10.0, 25.0, False)

        with self.assertRaises(ValueError):
            Constituent("Fe", 50.0, 101.0, False)

        with self.assertRaises(ValueError):
            Constituent("Fe", 50.0, 1.0, False)

    def test_parseComposition(self):
        # test we fail correctly when providing invalid inputs
        with self.assertRaises(ValueError):
            Constituent.parseComposition({})

        with self.assertRaises(ValueError):
            node = {"Fe": (0.1, 0.25)}
            Constituent.parseComposition(node)

        # a simple Iron-only material
        node = {"Fe": "balance"}
        c = Constituent.parseComposition(node)
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0].maxValue, 100.0)
        self.assertTrue(c[0].isBalance)

        # a hypothetical steel-like material
        node = {"C": (0.0, 10.0), "Cr": (0.0, 1.0), "Fe": "balance"}
        c = Constituent.parseComposition(node)
        self.assertEqual(len(c), 3)
        self.assertEqual(c[0].maxValue, 10.0)
        self.assertFalse(c[0].isBalance)
        self.assertEqual(c[2].maxValue, 100.0)
        self.assertTrue(c[2].isBalance)
