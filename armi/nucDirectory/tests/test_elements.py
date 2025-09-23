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
"""Tests for elements."""

import os
import unittest

from armi import nuclideBases
from armi.context import RES
from armi.nucDirectory.elements import Element, Elements
from armi.tests import mockRunLogs


class TestElement(unittest.TestCase):
    def setUp(self):
        self.elements = Elements()

    def test_elements_elementBulkProperties(self):
        numElements = len(self.elements.byZ)
        self.assertEqual(numElements, len(self.elements.byZ.values()))
        self.assertEqual(numElements, len(self.elements.byName))
        self.assertEqual(numElements, len(self.elements.bySymbol))

    def test_element_elementByNameReturnsElement(self):
        """Get elements by name.

        .. test:: Get elements by name.
            :id: T_ARMI_ND_ELEMENTS0
            :tests: R_ARMI_ND_ELEMENTS
        """
        for ee in self.elements.byZ.values():
            self.assertIs(ee, self.elements.byName[ee.name])

    def test_element_elementByZReturnsElement(self):
        """Get elements by Z.

        .. test:: Get elements by Z.
            :id: T_ARMI_ND_ELEMENTS1
            :tests: R_ARMI_ND_ELEMENTS
        """
        for ee in self.elements.byZ.values():
            self.assertIs(ee, self.elements.byZ[ee.z])

    def test_element_elementBySymbolReturnsElement(self):
        """Get elements by symbol.

        .. test:: Get elements by symbol.
            :id: T_ARMI_ND_ELEMENTS2
            :tests: R_ARMI_ND_ELEMENTS
        """
        for ee in self.elements.byZ.values():
            self.assertIs(ee, self.elements.bySymbol[ee.symbol])

    def test_element_addExistingElementFails(self):
        for ee in self.elements.byZ.values():
            with self.assertRaises(ValueError):
                self.elements.Element(ee.z, ee.symbol, ee.name, skipGlobal=True)

    def test_addedElementAppearsInElementList(self):
        self.assertNotIn("bacon", self.elements.byName)
        self.assertNotIn(999, self.elements.byZ)
        self.assertNotIn("BZ", self.elements.bySymbol)
        self.elements.addElement(Element(999, "BZ", "bacon", skipGlobal=True))
        self.assertIn("bacon", self.elements.byName)
        self.assertIn(999, self.elements.byZ)
        self.assertIn("BZ", self.elements.bySymbol)
        # re-initialize the elements
        with mockRunLogs.BufferLog():
            nuclideBases.destroyGlobalNuclides()
            nuclideBases.factory()
            # Ensure that the burn chain data is initialized after clearing
            # out the nuclide data and reinitializing it.
            nuclideBases.burnChainImposed = False
            with open(os.path.join(RES, "burn-chain.yaml"), "r") as burnChainStream:
                nuclideBases.imposeBurnChain(burnChainStream)

    def test_elementGetNatIsosOnlyRetrievesAbund(self):
        for ee in self.elements.byZ.values():
            if not ee.isNaturallyOccurring():
                continue

            for nuc in ee.getNaturalIsotopics():
                self.assertGreater(nuc.abundance, 0.0)
                self.assertGreater(nuc.a, 0)

    def test_elementIsNatOccurring(self):
        """
        Test isNaturallyOccurring method by manually testing all elements.

        Uses RIPL definitions of naturally occurring. Protactinium is debated as naturally occurring. Yeah it exists as
        a U235 decay product but it's kind of pseudo-natural.

        .. test:: Get elements by Z to show if they are naturally occurring.
            :id: T_ARMI_ND_ELEMENTS3
            :tests: R_ARMI_ND_ELEMENTS
        """
        for ee in self.elements.byZ.values():
            if ee.z == 43 or ee.z == 61 or 84 <= ee.z <= 89 or ee.z >= 93:
                self.assertFalse(ee.isNaturallyOccurring())
            else:
                nat = ee.isNaturallyOccurring()
                self.assertTrue(nat)

    def test_abundancesAddToOne(self):
        for ee in self.elements.byZ.values():
            if not ee.isNaturallyOccurring():
                continue

            totAbund = sum([iso.abundance for iso in ee.nuclides])
            self.assertAlmostEqual(
                totAbund,
                1.0,
                places=4,
            )

    def test_isHeavyMetal(self):
        """Get elements by Z.

        .. test:: Get elements by Z to show if they are heavy metals.
            :id: T_ARMI_ND_ELEMENTS4
            :tests: R_ARMI_ND_ELEMENTS
        """
        for ee in self.elements.byZ.values():
            if ee.z > 89:
                self.assertTrue(ee.isHeavyMetal())
            else:
                self.assertFalse(ee.isHeavyMetal())
