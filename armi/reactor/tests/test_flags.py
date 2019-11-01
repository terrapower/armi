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

"""Tests for flags."""
import unittest
import pickle

from armi.reactor import flags


class TestFlags(unittest.TestCase):
    """Tests for flags system."""

    def test_fromString(self):
        self._help_fromString(flags.Flags.fromStringIgnoreErrors)
        self.assertEqual(flags.Flags.fromStringIgnoreErrors("invalid"), flags.Flags(0))

    def test_toString(self):
        f = flags.Flags.FUEL
        self.assertEqual(flags.Flags.toString(f), "FUEL")

    def test_fromStringStrict(self):
        self._help_fromString(flags.Flags.fromString)
        with self.assertRaises(flags.InvalidFlagsError):
            flags.Flags.fromString("invalid")
        with self.assertRaises(flags.InvalidFlagsError):
            flags.Flags.fromString("fuel invalid")

    def _help_fromString(self, method):
        self.assertEqual(method("bond"), flags.Flags.BOND)
        self.assertEqual(method("bond1"), flags.Flags.BOND)
        self.assertEqual(method("bond 2"), flags.Flags.BOND)
        self.assertEqual(method("fuel test"), flags.Flags.FUEL | flags.Flags.TEST)

    def test_lookup(self):
        """Make sure lookup table is working."""
        self.assertEqual(
            flags.Flags.fromString("GAP1"), flags.Flags.GAP | flags.Flags.A
        )
        self.assertEqual(
            flags.Flags.fromString("handLing sOcket"), flags.Flags.HANDLING_SOCKET
        )
        # order in CONVERSIONS can matter for multi word flags.
        # tests that order is good.
        for conv, flag in flags.CONVERSIONS.items():
            if len(conv.split()) > 1:
                self.assertEqual(flags.Flags.fromString(conv), flag)

    def test_convertsStringsWithNonFlags(self):
        # Useful for varifying block / assembly names convert to Flags.
        self.assertEqual(
            flags.Flags.fromStringIgnoreErrors("banana bond banana"), flags.Flags.BOND
        )
        self.assertEqual(
            flags.Flags.fromStringIgnoreErrors("banana socket"),
            flags.Flags.HANDLING_SOCKET,
        )
        self.assertEqual(
            flags.Flags.fromStringIgnoreErrors("grid plate banana"),
            flags.Flags.GRID_PLATE,
        )
        self.assertEqual(
            flags.Flags.fromStringIgnoreErrors("handling socket socket"),
            flags.Flags.HANDLING_SOCKET,
        )

    def test_defaultIsFalse(self):
        self.assertFalse(flags.Flags(0))

    def test_isPickleable(self):
        """Must be pickleable to use syncMpiState."""
        stream = pickle.dumps(flags.Flags.BOND | flags.Flags.A)
        flag = pickle.loads(stream)
        self.assertEqual(flag, flags.Flags.BOND | flags.Flags.A)


if __name__ == "__main__":
    unittest.main()
