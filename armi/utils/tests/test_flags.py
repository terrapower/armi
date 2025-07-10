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
"""Testing flags.py."""

import unittest

from armi.reactor.composites import FlagSerializer
from armi.utils.flags import Flag, auto


class ExampleFlag(Flag):
    FOO = auto()
    BAR = auto()
    BAZ = auto()


class TestFlag(unittest.TestCase):
    """Tests for the utility Flag class and cohorts."""

    def test_auto(self):
        """
        Make sure that auto() works right, and that mixing it with explicit values
        doesn't lead to collision.
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

    def test_collision_extension(self):
        """Ensure the set of flags cannot be programmatically extended if duplicate created.

        .. test:: Set of flags are extensible without loss of uniqueness.
            :id: T_ARMI_FLAG_EXTEND0
            :tests: R_ARMI_FLAG_EXTEND
        """

        class F(Flag):
            foo = auto()
            bar = 1
            baz = auto()

        F.extend({"a": auto()})
        F.extend({"b": 1})

    def test_collision_creation(self):
        """Make sure that we catch value collisions upon creation.

        .. test:: No two flags have equivalence.
            :id: T_ARMI_FLAG_DEFINE
            :tests: R_ARMI_FLAG_DEFINE
        """
        with self.assertRaises(AssertionError):

            class F(Flag):
                foo = 1
                bar = 1

        class D(Flag):
            foo = auto()
            bar = auto()
            baz = auto()

        self.assertEqual(D.foo._value, 1)
        self.assertEqual(D.bar._value, 2)
        self.assertEqual(D.baz._value, 4)

    def test_bool(self):
        f = ExampleFlag()
        self.assertFalse(f)

    def test_inclusion(self):
        f = ExampleFlag.FOO | ExampleFlag.BAZ
        self.assertIn(ExampleFlag.FOO, f)
        self.assertIn(ExampleFlag.BAZ, f)
        self.assertNotIn(ExampleFlag.BAR, f)

    def test_bitwise(self):
        """Make sure that bitwise operators work right."""
        f = ExampleFlag.FOO | ExampleFlag.BAR
        self.assertTrue(f & ExampleFlag.FOO)
        self.assertTrue(f & ExampleFlag.BAR)
        self.assertFalse(f & ExampleFlag.BAZ)

        # mask off BAR
        f &= ExampleFlag.FOO
        self.assertEqual(f, ExampleFlag.FOO)

        # OR in BAZ
        f |= ExampleFlag.BAZ
        self.assertIn(ExampleFlag.BAZ, f)

        # XOR them. Should turn off FOO, since they both have it
        f2 = ExampleFlag.FOO | ExampleFlag.BAR
        self.assertEqual(f2 ^ f, ExampleFlag.BAR | ExampleFlag.BAZ)

    def test_iteration(self):
        """We want to be able to iterate over set flags."""
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

    def test_duplicateFlags(self):
        """Show that duplicate flags can be added and silently ignored."""

        class F(Flag):
            @classmethod
            def len(cls):
                return len(cls._nameToValue)

        F.extend({"FLAG0": auto()})
        for i in range(1, 12):
            F.extend({f"FLAG{i}": auto()})
            num = F.len()
            F.extend({f"FLAG{i - 1}": auto()})
            self.assertEqual(F.len(), num)

            # While the next two lines do not assert anything, these lines used to raise an error.
            # So these lines remain as proof against that error in the future.
            ff = getattr(F, f"FLAG{i}")
            FlagSerializer._packImpl(
                [
                    ff,
                ],
                F,
            )
            self.assertEqual(F.len(), num)

    def test_soManyFlags(self):
        """Show that many flags can be added without issue."""

        class F(Flag):
            @classmethod
            def len(cls):
                return len(cls._nameToValue)

        for i in range(1, 100):
            num = F.len()
            flagName = f"FLAG{i}"
            F.extend({flagName: auto()})
            self.assertEqual(F.len(), num + 1)

            flag = getattr(F, flagName)
            flag.to_bytes()
            self.assertEqual(F.len(), num + 1)
