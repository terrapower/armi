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

"""
Test the cross section manager

:py:mod:`armi.physics.neutronics.crossSectionGroupManager`
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access

import unittest
import copy
from io import BytesIO

from six.moves import cPickle

from armi import settings
from armi.utils import units
from armi.physics.neutronics import crossSectionGroupManager
from armi.physics.neutronics.crossSectionGroupManager import (
    BlockCollection,
    FluxWeightedAverageBlockCollection,
)
from armi.physics.neutronics.crossSectionGroupManager import (
    MedianBlockCollection,
    AverageBlockCollection,
)
from armi.physics.neutronics.crossSectionGroupManager import CrossSectionGroupManager
from armi.reactor.blocks import HexBlock
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT
from armi.physics.neutronics.fissionProductModel.tests import test_lumpedFissionProduct


class TestBlockCollection(unittest.TestCase):
    def setUp(self):
        self.blockList = makeBlocks()
        self.bc = BlockCollection(self.blockList[0].r.blueprints.allNuclidesInProblem)
        self.bc.extend(self.blockList)

    def test_add(self):
        self.bc.append("DummyBlock1")
        self.bc.extend(["DB2", "DB3"])
        self.assertIn("DummyBlock1", self.bc)
        self.assertIn("DB2", self.bc)
        self.assertIn("DB3", self.bc)

    def test_getBlocksInGroup(self):
        for b in self.blockList:
            self.assertIn(b, self.bc)

    def test_is_pickleable(self):
        self.bc.weightingParam = "test"
        buf = BytesIO()
        cPickle.dump(self.bc, buf)
        buf.seek(0)
        newBc = cPickle.load(buf)
        self.assertEqual(self.bc.weightingParam, newBc.weightingParam)


class TestBlockCollectionMedian(unittest.TestCase):
    def setUp(self):
        self.blockList = makeBlocks(5)
        for bi, b in enumerate(self.blockList):
            b.setType("fuel")
            b.p.percentBu = bi / 4.0 * 100
        self.blockList[0], self.blockList[2] = self.blockList[2], self.blockList[0]
        self.bc = MedianBlockCollection(
            self.blockList[0].r.blueprints.allNuclidesInProblem
        )
        self.bc.extend(self.blockList)

    def test_createRepresentativeBlock(self):

        avgB = self.bc.createRepresentativeBlock()
        self.assertAlmostEqual(avgB.p.percentBu, 50.0)


class TestBlockCollectionAverage(unittest.TestCase):
    def setUp(self):
        fpFactory = test_lumpedFissionProduct.getDummyLFPFile()
        self.blockList = makeBlocks(5)
        for bi, b in enumerate(self.blockList):
            b.setType("fuel")
            b.p.percentBu = bi / 4.0 * 100
            b.setLumpedFissionProducts(fpFactory.createLFPsFromFile())
            b.setNumberDensity("U235", bi)
            b.p.gasReleaseFraction = bi * 2 / 8.0
        self.bc = AverageBlockCollection(
            self.blockList[0].r.blueprints.allNuclidesInProblem
        )
        self.bc.extend(self.blockList)

    def test_createRepresentativeBlock(self):
        avgB = self.bc.createRepresentativeBlock()
        self.assertNotIn(avgB, self.bc)
        # 0 + 1/4 + 2/4 + 3/4 + 4/4 =
        # (0 + 1 + 2 + 3 + 4 ) / 5 = 10/5 = 2.0
        self.assertAlmostEqual(avgB.getNumberDensity("U235"), 2.0)
        lfps = avgB.getLumpedFissionProductCollection()
        lfp = list(lfps.values())[0]
        self.assertAlmostEqual(lfp.gasRemainingFrac, 0.5)


class TestBlockCollectionComponentAverage(unittest.TestCase):
    r"""
    tests for ZPPR 1D XS gen cases
    """

    def setUp(self):
        r"""
        First part of setup same as test_Cartesian.
        Second part of setup builds lists/dictionaries of expected values to compare to.
        has expected values for component isotopic atom density and component area
        """
        self.o, self.r = test_reactors.loadTestReactor(
            TEST_ROOT, inputFileName="zpprTest.yaml"
        )

        #                    ndrawer1  lenFuelTypeD1  ndrawer2  lenFuelTypeD2
        EuWeight = float(1 * 60 + 3 * 15)
        otherEUWeight = float(1 * 15 + 3 * 45)
        totalWeight = otherEUWeight + EuWeight
        otherEUWeight /= totalWeight
        EuWeight /= totalWeight
        expectedRepBlanketBlock = [
            {"U238": 0.045},  # DU
            {"NA23": 0.02},  # Na
            {"U238": 0.045},  # DU
        ]
        expectedRepFuelBlock = [
            {"U238": 0.045 * EuWeight + 0.045 * otherEUWeight},  # DU
            {
                "U235": 0.025 * EuWeight + 0.0125 * otherEUWeight,
                "U238": 0.02 * EuWeight + 0.01 * otherEUWeight,
            },
            {"NA23": 0.02},  # Na}
            {
                "FE54": 0.07 * 0.05845,
                "FE56": 0.07 * 0.91754,
                "FE57": 0.07 * 0.02119,
                "FE58": 0.07 * 0.00282,
            },  # Steel
        ]
        # later sorted by density so less massive block first
        self.expectedBlockDensites = [
            expectedRepBlanketBlock,
            expectedRepFuelBlock,
            expectedRepFuelBlock,
        ]
        self.expectedAreas = [[1, 6, 1], [1, 2, 1, 4]]

    def test_ComponentAverageRepBlock(self):
        r"""
        tests that the XS group manager calculates the expected component atom density
        and component area correctly. Order of components is also checked since in
        1D cases the order of the components matters.
        """
        xsgm = self.o.getInterface("xsGroups")

        for _xsID, xsOpt in self.o.cs["crossSectionControl"].items():
            self.assertEqual(xsOpt.blockRepresentation, None)

        xsgm.interactBOL()

        # Check that the correct defaults are propagated after the interactBOL
        # from the cross section group manager is called.
        for _xsID, xsOpt in self.o.cs["crossSectionControl"].items():
            self.assertEqual(
                xsOpt.blockRepresentation, self.o.cs["xsBlockRepresentation"]
            )

        xsgm.createRepresentativeBlocks()
        representativeBlockList = list(xsgm.representativeBlocks.values())
        representativeBlockList.sort(key=lambda repB: repB.getMass() / repB.getVolume())

        assert len(representativeBlockList) == len(self.expectedBlockDensites)
        for b, componentDensities, areas in zip(
            representativeBlockList, self.expectedBlockDensites, self.expectedAreas
        ):
            assert len(b) == len(componentDensities) and len(b) == len(areas)
            for c, compDensity, compArea in zip(b, componentDensities, areas):
                assert compArea == c.getArea()
                cNucs = c.getNuclides()
                assert len(cNucs) == len(compDensity), (cNucs, compDensity)
                for nuc in cNucs:
                    self.assertAlmostEqual(c.getNumberDensity(nuc), compDensity[nuc])

        assert "AC" in xsgm.representativeBlocks, (
            "Assemblies not in the core should still have XS groups"
            "see getUnrepresentedBlocks()"
        )


class TestBlockCollectionFluxWeightedAverage(unittest.TestCase):
    def setUp(self):
        fpFactory = test_lumpedFissionProduct.getDummyLFPFile()
        self.blockList = makeBlocks(5)
        for bi, b in enumerate(self.blockList):
            b.setType("fuel")
            b.p.percentBu = bi / 4.0 * 100
            b.setLumpedFissionProducts(fpFactory.createLFPsFromFile())
            b.setNumberDensity("U235", bi)
            b.p.gasReleaseFraction = bi * 2 / 8.0
            b.p.flux = bi + 1

        self.bc = FluxWeightedAverageBlockCollection(
            self.blockList[0].r.blueprints.allNuclidesInProblem
        )
        self.bc.extend(self.blockList)

    def test_createRepresentativeBlock(self):
        self.bc[1].p.flux = 1e99  # only the 2nd block values should show up
        avgB = self.bc.createRepresentativeBlock()
        self.assertNotIn(avgB, self.bc)
        self.assertAlmostEqual(avgB.getNumberDensity("U235"), 1.0)
        lfps = avgB.getLumpedFissionProductCollection()
        lfp = list(lfps.values())[0]
        self.assertAlmostEqual(lfp.gasRemainingFrac, 0.75)

    def test_invalidWeights(self):
        self.bc[0].p.flux = 0.0
        with self.assertRaises(ValueError):
            self.bc.createRepresentativeBlock()


class Test_CrossSectionGroupManager(unittest.TestCase):
    def setUp(self):
        self.blockList = makeBlocks(20)
        self.csm = CrossSectionGroupManager(self.blockList[0].r, None)
        for bi, b in enumerate(self.blockList):
            b.p.percentBu = bi / 19.0 * 100
        self.csm._setBuGroupBounds([3, 10, 30, 100])
        self.csm.interactBOL()

    def test_updateBurnupGroups(self):
        self.blockList[1].p.percentBu = 3.1
        self.blockList[2].p.percentBu = 10.0

        self.csm._updateBurnupGroups(self.blockList)

        self.assertEqual(self.blockList[0].p.buGroup, "A")
        self.assertEqual(self.blockList[1].p.buGroup, "B")
        self.assertEqual(self.blockList[2].p.buGroup, "B")
        self.assertEqual(self.blockList[-1].p.buGroup, "D")

    def test_setBuGroupBounds(self):
        self.assertAlmostEqual(self.csm._upperBuGroupBounds[2], 30.0)

        with self.assertRaises(ValueError):
            self.csm._setBuGroupBounds([3, 10, 300])

        with self.assertRaises(ValueError):
            self.csm._setBuGroupBounds([-5, 3, 10, 30.0])

        with self.assertRaises(ValueError):
            self.csm._setBuGroupBounds([1, 5, 3])

    def test_addXsGroupsFromBlocks(self):
        blockCollectionsByXsGroup = {}
        blockCollectionsByXsGroup = self.csm._addXsGroupsFromBlocks(
            blockCollectionsByXsGroup, self.blockList
        )
        self.assertEqual(len(blockCollectionsByXsGroup), 4)
        self.assertIn("AB", blockCollectionsByXsGroup)

    def test_getNextAvailableXsType(self):
        blockCollectionsByXsGroup = {}
        blockCollectionsByXsGroup = self.csm._addXsGroupsFromBlocks(
            blockCollectionsByXsGroup, self.blockList
        )
        xsType1, xsType2, xsType3 = self.csm.getNextAvailableXsTypes(3)
        self.assertEqual("B", xsType1)
        self.assertEqual("C", xsType2)
        self.assertEqual("D", xsType3)

    def test_getRepresentativeBlocks(self):
        _o, r = test_reactors.loadTestReactor(TEST_ROOT)
        self.csm.r = r

        # Assumption: All sodium in fuel blocks for this test is 450 C and this is the
        # expected sodium temperature.
        # These lines of code take the first sodium block and decrease the temperature of the block,
        # but change the atom density to approximately zero.
        # Checking later on the nuclide temperature of sodium is asserted to be still 450.
        # This perturbation proves that altering the temperature of an component with near zero atom density
        # does not affect the average temperature of the block collection.
        # This demonstrates that the temperatures of a block collection are atom weighted rather than just the
        # average temperature.
        regularFuel = r.core.getFirstBlock(Flags.FUEL, exact=True)
        intercoolant = regularFuel.getComponent(Flags.INTERCOOLANT)
        intercoolant.setTemperature(100)  # just above melting
        intercoolant.setNumberDensity("NA23", units.TRACE_NUMBER_DENSITY)

        self.csm.createRepresentativeBlocks()
        blocks = self.csm.representativeBlocks
        self.assertGreater(len(blocks), 0)

        # Test ability to get average nuclide temperature in block.
        u235 = self.csm.getNucTemperature("AA", "U235")
        fe = self.csm.getNucTemperature("AA", "FE56")
        na = self.csm.getNucTemperature("AA", "NA23")

        self.assertAlmostEqual(na, 450.0, msg="Na temp was {}, not 450".format(na))
        self.assertGreater(u235, fe)
        self.assertGreater(fe, na)
        self.assertTrue(0.0 < na < fe)
        # trace nuclides should also be at fuel temp.
        self.assertAlmostEqual(self.csm.getNucTemperature("AA", "LFP35"), u235)

        # Test that retrieving temperatures fails if a representative block for a given XS ID does not exist
        self.assertEqual(self.csm.getNucTemperature("Z", "U235"), None)

    def test_createRepresentativeBlocksUsingExistingBlocks(self):
        """
        Demonstrates that a new representative block can be generated from an existing representative block.

        Notes
        -----
        This tests that the XS ID of the new representative block is correct and that the compositions are identical
        between the original and the new representative blocks.
        """
        _o, r = test_reactors.loadTestReactor(TEST_ROOT)
        self.csm.createRepresentativeBlocks()
        unperturbedReprBlocks = copy.deepcopy(self.csm.representativeBlocks)
        self.assertNotIn("BA", unperturbedReprBlocks)
        block = r.core.getFirstBlock()
        blockXSID = block.getMicroSuffix()
        blockList = [block]
        (
            _bCollect,
            newRepresentativeBlocks,
        ) = self.csm.createRepresentativeBlocksUsingExistingBlocks(
            blockList, unperturbedReprBlocks
        )
        self.assertIn("BA", newRepresentativeBlocks)
        oldReprBlock = unperturbedReprBlocks[blockXSID]
        newReprBlock = newRepresentativeBlocks["BA"]
        self.assertEqual(newReprBlock.getMicroSuffix(), "BA")
        self.assertEqual(
            newReprBlock.getNumberDensities(), oldReprBlock.getNumberDensities()
        )


class TestXSNumberConverters(unittest.TestCase):
    def test_conversion(self):
        label = crossSectionGroupManager.getXSTypeLabelFromNumber(65)
        self.assertEqual(label, "A")
        num = crossSectionGroupManager.getXSTypeNumberFromLabel("A")
        self.assertEqual(num, 65)

    def test_conversion_2digit(self):
        label = crossSectionGroupManager.getXSTypeLabelFromNumber(6570)
        self.assertEqual(label, "AF")
        num = crossSectionGroupManager.getXSTypeNumberFromLabel("ZZ")
        self.assertEqual(num, 9090)


class MockReactor:
    def __init__(self):
        self.blueprints = MockBlueprints()
        self.spatialGrid = None


class MockBlueprints:
    # this is only needed for allNuclidesInProblem and attributes were acting funky, so this was made.
    def __getattribute__(self, *args, **kwargs):
        return ["U235", "U235", "FE", "NA23"]


class MockBlock(HexBlock):
    def __init__(self, name=None, cs=None):
        self.density = {}
        HexBlock.__init__(self, name or "MockBlock", cs or settings.getMasterCs())
        self.r = MockReactor()

    @property
    def r(self):
        return self._r

    @r.setter
    def r(self, r):
        self._r = r

    def getVolume(self, *args, **kwargs):
        return 1.0

    def getNuclideNumberDensities(self, nucNames):
        return [self.density.get(nucName, 0.0) for nucName in nucNames]

    def _getNdensHelper(self):
        return {nucName: density for nucName, density in self.density.items()}

    def setNumberDensity(self, key, val, *args, **kwargs):
        self.density[key] = val

    def getNuclides(self):
        return self.density.keys()


def makeBlocks(howMany=20):
    _o, r = test_reactors.loadTestReactor(TEST_ROOT)
    return r.core.getBlocks(Flags.FUEL)[
        3 : howMany + 3
    ]  # shift y 3 to skip central assemblies 1/3 volume


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test_CrossSectionGroupManager.test_createRepresentativeBlocksUsingExistingBlocks']
    unittest.main()
