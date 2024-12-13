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
import itertools
import random
import typing
import unittest
from unittest import mock

from armi.reactor.assemblies import HexAssembly
from armi.reactor.cores import Core
from armi.reactor.flags import Flags
from armi.reactor.tests.test_reactors import loadTestReactor, TEST_ROOT
from armi.utils import directoryChangers


class HexCoreTests(unittest.TestCase):
    """Tests on a hex reactor core."""

    @classmethod
    def setUpClass(cls):
        cls.directoryChanger = directoryChangers.DirectoryChanger(TEST_ROOT)
        cls.directoryChanger.open()
        r = loadTestReactor(TEST_ROOT)[1]
        cls.core: Core = r.core

    def assertAllIs(
        self,
        actuals: typing.Iterable[typing.Any],
        expecteds: typing.Iterable[typing.Any],
        fill=None,
    ):
        """Assert that all items in two iterables are the same objects."""
        for actual, expected in itertools.zip_longest(
            actuals, expecteds, fillvalue=fill
        ):
            self.assertIs(actual, expected)

    @classmethod
    def tearDownClass(cls):
        cls.directoryChanger.close()

    def test_getAllAssem(self):
        """Test the ability to produce all assemblies."""
        expectedAll = list(self.core)
        actualAll = self.core.getAssemblies()
        self.assertAllIs(actualAll, expectedAll)

    def test_getAllAssemWithFlag(self):
        """Test the ability to produce assemblies with a flag."""
        for spec in (Flags.FUEL, Flags.CONTROL):
            expected = self.core.getChildrenWithFlags(spec)
            actual = self.core.getAssemblies(typeSpec=spec)
            for a in actual:
                self.assertIsInstance(a, HexAssembly)
                self.assertTrue(a.hasFlags(spec))
            self.assertAllIs(actual, expected)

    def test_getAssemsInZones(self):
        """Test the ability to produce assemblies in a zone."""
        # Grab a few assemblies and add their locations to those in the zones
        selection = random.choices(self.core.getAssemblies(), k=5)
        locations = [a.getLocation() for a in selection]
        fakeZones = ["hot", "cold"]
        with mock.patch.object(
            self.core.zones, "getZoneLocations", mock.Mock(return_value=locations)
        ):
            actuals = self.core.getAssemblies(zones=fakeZones)
        for a in actuals:
            self.assertIn(a.getLocation(), locations, msg=str(a))
