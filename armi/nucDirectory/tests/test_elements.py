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

import unittest

from armi.nucDirectory.elements import ChemicalGroup, ChemicalPhase, Element
from armi.nucDirectory.nuclideBases import NuclideBases


class TestElements(unittest.TestCase):
    def setUp(self):
        self.nuclideBases = NuclideBases()
        self.elements = self.nuclideBases.elements

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
                self.elements.addElement(Element(ee.z, ee.symbol, ee.name, skipGlobal=True))

    def test_element_addedElementAppearsInElementList(self):
        self.assertNotIn("bacon", self.elements.byName)
        self.assertNotIn(999, self.elements.byZ)
        self.assertNotIn("BZ", self.elements.bySymbol)
        self.elements.addElement(Element(999, "BZ", "bacon", skipGlobal=True))
        self.assertIn("bacon", self.elements.byName)
        self.assertIn(999, self.elements.byZ)
        self.assertIn("BZ", self.elements.bySymbol)

    def test_elementGetNatrualIsotpicsOnlyRetrievesAbund(self):
        for ee in self.elements.byZ.values():
            if not ee.isNaturallyOccurring():
                continue

            for nuc in ee.getNaturalIsotopics():
                self.assertGreater(nuc.abundance, 0.0)
                self.assertGreater(nuc.a, 0)

    def test_element_isNaturallyOccurring(self):
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
                self.assertTrue(nat, msg=f"z = {ee.z}")

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

    def test_getElementsByChemicalPhase(self):
        liquids = self.elements.getElementsByChemicalPhase(ChemicalPhase.LIQUID)
        self.assertGreater(len(liquids), 1)

        gasses = self.elements.getElementsByChemicalPhase(ChemicalPhase.GAS)
        self.assertGreater(len(gasses), 10)

        solids = self.elements.getElementsByChemicalPhase(ChemicalPhase.SOLID)
        self.assertGreater(len(solids), 100)

    def test_getElementsByChemicalGroup(self):
        metals = self.elements.getElementsByChemicalGroup(ChemicalGroup.METALLOID)
        self.assertGreater(len(metals), 5)

        nonmetals = self.elements.getElementsByChemicalGroup(ChemicalGroup.NONMETAL)
        self.assertGreater(len(nonmetals), 5)

    def test_getName(self):
        name = self.elements.getName(z=2)
        self.assertEqual(name, "Helium")

        name = self.elements.getName(z=92)
        self.assertEqual(name, "Uranium")

        with self.assertRaises(KeyError):
            self.elements.getName(z=654)

        name = self.elements.getName(symbol="H")
        self.assertEqual(name, "Hydrogen")

        name = self.elements.getName(symbol="U")
        self.assertEqual(name, "Uranium")

        with self.assertRaises(KeyError):
            self.elements.getName(symbol="Boring")

    def test_getSymbol(self):
        symbol = self.elements.getSymbol(z=2)
        self.assertEqual(symbol, "HE")

        symbol = self.elements.getSymbol(z=92)
        self.assertEqual(symbol, "U")

        with self.assertRaises(KeyError):
            self.elements.getSymbol(z=654)

        symbol = self.elements.getSymbol(name="Hydrogen")
        self.assertEqual(symbol, "H")

        symbol = self.elements.getSymbol(name="Uranium")
        self.assertEqual(symbol, "U")

        with self.assertRaises(KeyError):
            self.elements.getSymbol(name="Boring")

    def test_getElementZ(self):
        z = self.elements.getElementZ(symbol="HE")
        self.assertEqual(z, 2)

        z = self.elements.getElementZ(symbol="U")
        self.assertEqual(z, 92)

        with self.assertRaises(KeyError):
            self.elements.getElementZ(symbol="XYZ")

        z = self.elements.getElementZ(name="Hydrogen")
        self.assertEqual(z, 1)

        z = self.elements.getElementZ(name="Uranium")
        self.assertEqual(z, 92)

        with self.assertRaises(KeyError):
            self.elements.getElementZ(name="Boring")
