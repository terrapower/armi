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
"""Tests for elements.

Notes
-----
These are tests of the old global nuclide logic. ARMI is currently transitioning away from such global data, so these
tests are semi-duplicate and will only be preserved as long as global nulides are.
"""

import os
import unittest

from armi import nuclideBases
from armi.context import RES
from armi.nucDirectory import elements
from armi.tests import mockRunLogs


class TestElement(unittest.TestCase):
    def test_elements_elementBulkProperties(self):
        numElements = len(elements.byZ)
        self.assertEqual(numElements, len(elements.byZ.values()))
        self.assertEqual(numElements, len(elements.byName))
        self.assertEqual(numElements, len(elements.bySymbol))

    def test_element_elementByNameReturnsElement(self):
        """Get elements by name."""
        for ee in elements.byZ.values():
            self.assertIs(ee, elements.byName[ee.name])

    def test_element_elementByZReturnsElement(self):
        """Get elements by Z."""
        for ee in elements.byZ.values():
            self.assertIs(ee, elements.byZ[ee.z])

    def test_element_elementBySymbolReturnsElement(self):
        """Get elements by symbol."""
        for ee in elements.byZ.values():
            self.assertIs(ee, elements.bySymbol[ee.symbol])

    def test_element_addExistingElementFails(self):
        for ee in elements.byZ.values():
            with self.assertRaises(ValueError):
                elements.Element(ee.z, ee.symbol, ee.name)

    def test_element_addedElementAppearsInElementList(self):
        self.assertNotIn("bacon", elements.byName)
        self.assertNotIn(999, elements.byZ)
        self.assertNotIn("BZ", elements.bySymbol)
        elements.Element(999, "BZ", "bacon")
        self.assertIn("bacon", elements.byName)
        self.assertIn(999, elements.byZ)
        self.assertIn("BZ", elements.bySymbol)
        # re-initialize the elements
        with mockRunLogs.BufferLog():
            nuclideBases.destroyGlobalNuclides()
            nuclideBases.factory()
            # Ensure that the burn chain data is initialized after clearing
            # out the nuclide data and reinitializing it.
            nuclideBases.burnChainImposed = False
            with open(os.path.join(RES, "burn-chain.yaml"), "r") as burnChainStream:
                nuclideBases.imposeBurnChain(burnChainStream)

    def test_elementGetNatrualIsotpicsOnlyRetrievesAbund(self):
        for ee in elements.byZ.values():
            if not ee.isNaturallyOccurring():
                continue
            for nuc in ee.getNaturalIsotopics():
                self.assertGreater(nuc.abundance, 0.0)
                self.assertGreater(nuc.a, 0)

    def test_element_isNaturallyOccurring(self):
        """
        Test isNaturallyOccurring method by manually testing all elements.

        Uses RIPL definitions of naturally occurring. Protactinium is debated as naturally
        occurring. Yeah it exists as a U235 decay product but it's kind of pseudo-natural.
        """
        for ee in elements.byZ.values():
            if ee.z == 43 or ee.z == 61 or 84 <= ee.z <= 89 or ee.z >= 93:
                self.assertFalse(ee.isNaturallyOccurring())
            else:
                nat = ee.isNaturallyOccurring()
                self.assertTrue(nat)

    def test_abundancesAddToOne(self):
        for ee in elements.byZ.values():
            if not ee.isNaturallyOccurring():
                continue
            totAbund = sum([iso.abundance for iso in ee.nuclides])
            self.assertAlmostEqual(
                totAbund,
                1.0,
                places=4,
            )

    def test_isHeavyMetal(self):
        """Get elements by Z."""
        for ee in elements.byZ.values():
            if ee.z > 89:
                self.assertTrue(ee.isHeavyMetal())
            else:
                self.assertFalse(ee.isHeavyMetal())
