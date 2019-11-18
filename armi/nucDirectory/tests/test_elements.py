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

from armi.nucDirectory import nuclideBases  # required to init natural isotopics
from armi.nucDirectory import elements
from armi.tests import mockRunLogs


class TestElement(unittest.TestCase):

    # TODO: this thing needs to be investigated since it breaks the bound of 3000 so often
    # probably because it opens a file?
    def test_factory(self):
        with mockRunLogs.BufferLog():
            elements.factory()

    def test_elements_elementBulkProperties(self):
        numElements = 118
        self.assertEqual(
            sum(range(1, numElements + 1)), sum([ee.z for ee in elements.byZ.values()])
        )
        self.assertEqual(numElements, len(elements.byZ.values()))
        self.assertEqual(numElements, len(elements.byName))
        self.assertEqual(numElements, len(elements.bySymbol))
        self.assertEqual(numElements, len(elements.byZ))

    def test_element_elementByNameReturnsElement(self):
        for ee in elements.byZ.values():
            self.assertIs(ee, elements.byName[ee.name])

    def test_element_elementByZReturnsElement(self):
        for ee in elements.byZ.values():
            self.assertIs(ee, elements.byZ[ee.z])

    def test_element_elementBySymbolReturnsElement(self):
        for ee in elements.byZ.values():
            self.assertIs(ee, elements.bySymbol[ee.symbol])

    def test_element_addExistingElementFails(self):
        for ee in elements.byZ.values():
            with self.assertRaises(Exception):
                elements.Element(ee.z, ee.symbol, ee.name)

    def test_element_addedElementAppearsInElementList(self):
        self.assertFalse("bacon" in elements.byName)
        self.assertFalse(999 in elements.byZ)
        self.assertFalse("BZ" in elements.bySymbol)
        elements.Element(999, "BZ", "bacon")
        self.assertTrue("bacon" in elements.byName)
        self.assertTrue(999 in elements.byZ)
        self.assertTrue("BZ" in elements.bySymbol)
        # re-initialize the elements
        with mockRunLogs.BufferLog():
            elements.destroy()
            elements.factory()

    def test_element_isNaturallyOccurring(self):
        """
        Test isNaturallyOccurring method by manually testing all elements.

        Uses RIPL definitions of naturally occurring. Protactinium is debated as naturally
        occurring. Yeah it exists as a U235 decay product but it's kind of pseudo-natural.
        """
        for ee in elements.byZ.values():
            if ee.z == 43 or ee.z == 61 or 84 <= ee.z <= 89 or ee.z == 91 or ee.z >= 93:
                self.assertFalse(ee.isNaturallyOccurring())
            else:
                nat = ee.isNaturallyOccurring()
                self.assertTrue(nat)

    def test_abundancesAddToOne(self):
        for ee in elements.byZ.values():
            if not ee.isNaturallyOccurring():
                continue
            totAbund = sum(iso.abundance for iso in ee.nuclideBases)
            maxDeviationInRIPL = 0.000030021  # Ca sums to 1.0003002
            self.assertAlmostEqual(
                totAbund,
                1.0,
                delta=maxDeviationInRIPL,
                msg="{} had a total abundance of {}".format(ee, totAbund),
            )


if __name__ == "__main__":
    #     import sys;sys.argv = ['', 'TestElement.test_abundancesAddToOne']
    unittest.main()
