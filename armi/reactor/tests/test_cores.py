# Copyright 2025 TerraPower, LLC
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
from unittest.mock import patch

from armi.nuclearDataIO.xsLibraries import IsotxsLibrary
from armi.reactor.assemblies import HexAssembly
from armi.reactor.blocks import Block
from armi.reactor.cores import Core
from armi.reactor.flags import Flags
from armi.reactor.tests.test_reactors import TEST_ROOT, loadTestReactor
from armi.tests import ISOAA_PATH
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
        for actual, expected in itertools.zip_longest(actuals, expecteds, fillvalue=fill):
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

    def test_getAssembliesWithFlags(self):
        aa = self.core.getAssembliesWithFlags(Flags.BOOSTER)
        self.assertEqual(len(aa), 0)

        aa = self.core.getAssembliesWithFlags(Flags.FUEL)
        self.assertTrue(20 < len(aa) < 100)

        aa = self.core.getAssembliesWithFlags(Flags.CONTROL)
        self.assertTrue(1 < len(aa) < 10)

    def test_getAssemsInZones(self):
        """Test the ability to produce assemblies in a zone."""
        # Grab a few assemblies and add their locations to those in the zones
        selection = random.choices(self.core.getAssemblies(), k=5)
        locations = [a.getLocation() for a in selection]
        fakeZones = ["hot", "cold"]
        with mock.patch.object(self.core.zones, "getZoneLocations", mock.Mock(return_value=locations)):
            actuals = self.core.getAssemblies(zones=fakeZones)
        for a in actuals:
            self.assertIn(a.getLocation(), locations, msg=str(a))

    def test_getBlocks(self):
        """Test the ability to get all blocks in the core."""
        blocks = []
        for a in self.core:
            blocks.extend(a)
        actual = self.core.iterBlocks()
        self.assertAllIs(actual, blocks)

    def test_getBlocksWithFlag(self):
        """Test the ability to get all blocks with a flag in the core."""
        blocks = []
        for a in self.core:
            blocks.extend(filter(lambda b: b.hasFlags(Flags.FUEL), a))
        actual = self.core.getBlocks(Flags.FUEL)
        self.assertAllIs(actual, blocks)

    def test_traverseAllBlocks(self):
        """Test the ability to iterate over all blocks in the core."""
        blocks = []
        for a in self.core:
            blocks.extend(a)
        actual = self.core.iterBlocks()
        self.assertAllIs(actual, blocks)

    def test_traverseAllBlocksWithFlag(self):
        """Test the ability to traverse blocks in the core with a flag."""
        blocks: list[Block] = []
        for a in self.core:
            blocks.extend(a)
        for spec in (Flags.FUEL, Flags.CONTROL, Flags.FUEL | Flags.CONTROL):
            expected = list(filter(lambda b: b.hasFlags(spec), blocks))
            actual = self.core.iterBlocks(spec)
            self.assertAllIs(actual, expected)
            # Fake the flag check with hasFlags as predicate
            actual = self.core.iterBlocks(predicate=lambda b: b.hasFlags(spec))
            self.assertAllIs(actual, expected)

    def test_traverseBlocksWithPredicate(self):
        """Test the ability to traverse blocks that meet some criteria with a flag."""
        fuelBlocks: list[Block] = []
        for a in self.core:
            fuelBlocks.extend(filter(lambda b: b.hasFlags(Flags.FUEL), a))
        # Make some contrived condition to exclude some blocks
        meanElevation = sum(b.p.z for b in fuelBlocks) / len(fuelBlocks)
        checker = lambda b: b.p.z >= meanElevation
        expected = list(filter(checker, fuelBlocks))
        actual = self.core.iterBlocks(Flags.FUEL, predicate=checker)
        self.assertAllIs(actual, expected)

    @patch("armi.nuclearDataIO.getExpectedISOTXSFileName")
    def test_lib(self, mockFileName):
        # the default case will look something like this
        mockFileName.return_value = "ISOTXS-c0n0"
        self.assertIsNone(self.core.lib)
        self.assertFalse(self.core.hasLib())

        # we can inject some mock data, and retrieve it
        mockFileName.return_value = ISOAA_PATH
        self.assertTrue(isinstance(self.core.lib, IsotxsLibrary))
        self.assertTrue(self.core.hasLib())

    def test_getAssembliesInRing(self):
        assems = self.core.getAssembliesInRing(0)
        self.assertEqual(len(assems), 0)

        assems = self.core.getAssembliesInRing(1)
        self.assertEqual(len(assems), 1)
        self.assertIsInstance(assems[0], HexAssembly)

    def test_getAssembliesInSquareOrHexRing(self):
        assems = self.core.getAssembliesInSquareOrHexRing(0)
        self.assertEqual(len(assems), 0)

        assems = self.core.getAssembliesInSquareOrHexRing(1)
        self.assertEqual(len(assems), 1)
        self.assertIsInstance(assems[0], HexAssembly)

    def test_getAssembliesInCircularRing(self):
        assems = self.core.getAssembliesInCircularRing(0)
        self.assertEqual(len(assems), 0)

        assems = self.core.getAssembliesInCircularRing(1)
        self.assertEqual(len(assems), 5)
        self.assertIsInstance(assems[0], HexAssembly)

    def test_getBlockByName(self):
        with self.assertRaises(KeyError):
            self.core.getBlockByName("badName")

        b = self.core.getBlockByName("B0004-000")
        self.assertIsInstance(b, Block)

    def test_getFirstBlock(self):
        b = self.core.getFirstBlock()
        self.assertIsInstance(b, Block)

    def test_getFirstAssembly(self):
        a = self.core.getFirstAssembly()
        self.assertIsInstance(a, HexAssembly)
