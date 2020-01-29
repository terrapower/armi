# Copyright 2019 TerraPower, LLC
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

import unittest

from armi.utils.flags import Flag, auto


class ExampleFlag(Flag):
    FOO = auto()
    BAR = auto()
    BAZ = auto()


class TestFlag(unittest.TestCase):
    """
    Tests for the utility Flag class and cohorts.
    """

    def test_auto(self):
        """
        make sure that auto() works right, and that mixing it with explicit values
        doesnt lead to collision.
        """

        class F(Flag):
            foo = auto()
            bar = 1
            baz = auto()

        f = F(F.bar)
        self.assertEqual(int(f), 1)
        # check that baz got a higher number than foo. Not a guaranteed behavior/bit of
        # an implementation detail, but nice to know we understand what's happening
        # under the hood.
        self.assertTrue(int(F.baz) > int(F.foo))

    def test_extend(self):
        """Ensure the set of flags can be programmatically extended."""

        class F(Flag):
            foo = auto()
            bar = 1
            baz = auto()

        self.assertEqual(F.width(), 1)

        F.extend({"A": auto(), "B": 8, "C": auto(), "D": auto(), "E": auto()})

        self.assertEqual(int(F.B), 8)
        self.assertEqual(F.width(), 1)

        F.extend({"LAST": auto()})
        self.assertEqual(F.width(), 2)

        f = F.A | F.foo | F.C
        array = f.to_bytes()
        self.assertEqual(len(array), 2)

        f2 = F.from_bytes(array)
        self.assertEqual(f, f2)

    def test_collision(self):
        """
        Make sure that we catch value collisions
        """
        with self.assertRaises(AssertionError):

            class F(Flag):
                foo = 1
                bar = 1

    def test_bool(self):
        f = ExampleFlag()
        self.assertFalse(f)

    def test_inclusion(self):
        f = ExampleFlag.FOO | ExampleFlag.BAZ
        self.assertTrue(ExampleFlag.FOO in f)
        self.assertTrue(ExampleFlag.BAZ in f)
        self.assertFalse(ExampleFlag.BAR in f)

    def test_bitwise(self):
        """
        Make sure that bitwise operators work right
        """
        f = ExampleFlag.FOO | ExampleFlag.BAR
        self.assertTrue(f & ExampleFlag.FOO)
        self.assertTrue(f & ExampleFlag.BAR)
        self.assertFalse(f & ExampleFlag.BAZ)

        # mask off BAR
        f &= ExampleFlag.FOO
        self.assertEqual(f, ExampleFlag.FOO)

        # OR in BAZ
        f |= ExampleFlag.BAZ
        self.assertTrue(ExampleFlag.BAZ in f)

        # XOR them. Should turn off FOO, since they both have it
        f2 = ExampleFlag.FOO | ExampleFlag.BAR
        self.assertEqual(f2 ^ f, ExampleFlag.BAR | ExampleFlag.BAZ)

    def test_iteration(self):
        """
        we want to be able to iterate over set flags
        """
        f = ExampleFlag.FOO | ExampleFlag.BAZ
        flagsOn = [val for val in f]
        self.assertIn(ExampleFlag.FOO, flagsOn)
        self.assertIn(ExampleFlag.BAZ, flagsOn)
        self.assertNotIn(ExampleFlag.BAR, flagsOn)

    def test_hashable(self):
        f1 = ExampleFlag.FOO
        f2 = ExampleFlag.BAR
        self.assertNotEqual(hash(f1), hash(f2))

    def test_getitem(self):
        self.assertEqual(ExampleFlag["FOO"], ExampleFlag.FOO)
