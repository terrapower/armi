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
import pickle
import unittest

from armi.reactor import flags


class TestFlags(unittest.TestCase):
    """Tests for flags system."""

    def test_fromString(self):
        self._help_fromString(flags.Flags.fromStringIgnoreErrors)
        self.assertEqual(flags.Flags.fromStringIgnoreErrors("invalid"), flags.Flags(0))

    def test_fromStringWithNumbers(self):
        # testing pure numbers
        self.assertEqual(flags.Flags.fromStringIgnoreErrors("1"), flags.Flags(0))
        self.assertEqual(flags.Flags.fromStringIgnoreErrors("7"), flags.Flags(0))

        # testing fuel naming logic
        self.assertEqual(flags.Flags.fromStringIgnoreErrors("Fuel1"), flags.Flags.FUEL)
        self.assertEqual(
            flags.Flags.fromStringIgnoreErrors("Fuel123"), flags.Flags.FUEL
        )
        self.assertEqual(flags.Flags.fromStringIgnoreErrors("fuel 1"), flags.Flags.FUEL)
        self.assertEqual(
            flags.Flags.fromStringIgnoreErrors("fuel 123"), flags.Flags.FUEL
        )

    def test_flagsDefinedWithNumbers(self):
        """Test that if we DEFINE flags with numbers in them, those are treated as exceptions."""
        # define flags TYPE1 and TYPE1B (arbitrary example)
        flags.Flags.extend({"TYPE1": flags.auto(), "TYPE1B": flags.auto()})

        # verify that these flags are correctly found
        self.assertEqual(flags.Flags["TYPE1"], flags.Flags.TYPE1)
        self.assertEqual(flags.Flags["TYPE1B"], flags.Flags.TYPE1B)
        self.assertEqual(flags.Flags.fromStringIgnoreErrors("type1"), flags.Flags.TYPE1)
        self.assertEqual(
            flags.Flags.fromStringIgnoreErrors("Type1b"), flags.Flags.TYPE1B
        )

        # the more complicated situation where our exceptions are mixed with the usual flag logic
        self.assertEqual(
            flags.Flags.fromString("type1 fuel"), flags.Flags.TYPE1 | flags.Flags.FUEL
        )

        self.assertEqual(
            flags.Flags.fromString("type1 fuel 123 bond"),
            flags.Flags.TYPE1 | flags.Flags.FUEL | flags.Flags.BOND,
        )

        self.assertEqual(
            flags.Flags.fromString("type1 fuel123 bond"),
            flags.Flags.TYPE1 | flags.Flags.FUEL | flags.Flags.BOND,
        )

    def test_flagsToAndFromString(self):
        """
        Convert flag to and from string for serialization.

        .. test:: Convert flag to a string.
            :id: T_ARMI_FLAG_TO_STR
            :tests: R_ARMI_FLAG_TO_STR
        """
        f = flags.Flags.FUEL
        self.assertEqual(flags.Flags.toString(f), "FUEL")
        self.assertEqual(f, flags.Flags.fromString("FUEL"))

    def test_toStringAlphabetical(self):
        """Ensure that, for multiple flags, toString() returns them in alphabetical order."""
        flagz = flags.Flags.AXIAL | flags.Flags.LOWER
        self.assertEqual(flags.Flags.toString(flagz), "AXIAL LOWER")

        flagz = flags.Flags.LOWER | flags.Flags.AXIAL
        self.assertEqual(flags.Flags.toString(flagz), "AXIAL LOWER")

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
        # test the more strict GRID conversion, which can cause collisions with GRID_PLATE
        self.assertEqual(
            flags.Flags.fromStringIgnoreErrors("grid_plate"), flags.Flags.GRID_PLATE
        )
        # test that "nozzle" is not consumed in the conversion, leaving behind "inlet_"
        # and leading to an error. Interesting thing here is that if the IgnoreErrors
        # variant is used, this works out fine since the "inlet_" is ignored and
        # "nozzle" -> INLET_NOZZLE.
        self.assertEqual(
            flags.Flags.fromString("inlet_nozzle"), flags.Flags.INLET_NOZZLE
        )

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
        for conv, flag in flags._CONVERSIONS.items():
            # the conversions are specified as RE patterns, so we need to do a little
            # work to get them into something that can serve as candidate input (i.e. a
            # string that the pattern would match). Since we are only using \b and \s+,
            # this is pretty straightforward. If any more complicated patterns work
            # their way in there, this will need to become more sophisticated. One might
            # be tempted to bake the plain-text versions of the conversions in the
            # collection in the flags module, but this is pretty much only needed for
            # testing, so that wouldn't be appropriate.
            exampleInput = conv.pattern.replace(r"\b", "")
            exampleInput = exampleInput.replace(r"\s+", " ")
            self.assertEqual(flags.Flags.fromString(exampleInput), flag)

    def test_convertsStringsWithNonFlags(self):
        # Useful for verifying block / assembly names convert to Flags.
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
