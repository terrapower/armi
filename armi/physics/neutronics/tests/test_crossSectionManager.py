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
Test the cross section manager.

:py:mod:`armi.physics.neutronics.crossSectionGroupManager`
"""
from io import BytesIO
import copy
import os
import unittest
from unittest.mock import MagicMock

from six.moves import cPickle

from armi import settings
from armi.physics.neutronics import crossSectionGroupManager
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.physics.neutronics.crossSectionGroupManager import (
    BlockCollection,
    FluxWeightedAverageBlockCollection,
)
from armi.physics.neutronics.crossSectionGroupManager import (
    MedianBlockCollection,
    AverageBlockCollection,
)
from armi.physics.neutronics.crossSectionGroupManager import CrossSectionGroupManager
from armi.physics.neutronics.fissionProductModel.tests import test_lumpedFissionProduct
from armi.physics.neutronics.settings import (
    CONF_XS_BLOCK_REPRESENTATION,
    CONF_LATTICE_PHYSICS_FREQUENCY,
)
from armi.reactor.blocks import HexBlock
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors, test_blocks
from armi.tests import TEST_ROOT
from armi.tests import mockRunLogs
from armi.utils import units
from armi.utils.directoryChangers import TemporaryDirectoryChanger


THIS_DIR = os.path.dirname(os.path.abspath(__file__))


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
    @classmethod
    def setUpClass(cls):
        fpFactory = test_lumpedFissionProduct.getDummyLFPFile()
        cls.blockList = makeBlocks(5)
        for bi, b in enumerate(cls.blockList):
            b.setType("fuel")
            b.p.percentBu = bi / 4.0 * 100
            b.setLumpedFissionProducts(fpFactory.createLFPsFromFile())
            # put some trace Fe-56 and Na-23 into the fuel
            # zero out all fuel nuclides except U-235 (for mass-weighting of component temperature)
            fuelComp = b.getComponent(Flags.FUEL)
            for nuc in fuelComp.getNuclides():
                b.setNumberDensity(nuc, 0.0)
            b.setNumberDensity("U235", bi)
            fuelComp.setNumberDensity("FE56", 1e-15)
            fuelComp.setNumberDensity("NA23", 1e-15)
            b.p.gasReleaseFraction = bi * 2 / 8.0
            for c in b:
                if c.hasFlags(Flags.FUEL):
                    c.temperatureInC = 600.0 + bi
                elif c.hasFlags([Flags.CLAD, Flags.DUCT, Flags.WIRE]):
                    c.temperatureInC = 500.0 + bi
                elif c.hasFlags([Flags.BOND, Flags.COOLANT, Flags.INTERCOOLANT]):
                    c.temperatureInC = 400.0 + bi

    def setUp(self):
        self.bc = AverageBlockCollection(
            self.blockList[0].r.blueprints.allNuclidesInProblem
        )
        self.bc.extend(self.blockList)
        self.bc.averageByComponent = True

    def test_performAverageByComponent(self):
        """Check the averageByComponent attribute."""
        self.bc._checkBlockSimilarity = MagicMock(return_value=True)
        self.assertTrue(self.bc._performAverageByComponent())
        self.bc.averageByComponent = False
        self.assertFalse(self.bc._performAverageByComponent())

    def test_checkBlockSimilarity(self):
        """Check the block similarity test."""
        self.assertTrue(self.bc._checkBlockSimilarity())
        self.bc.append(test_blocks.loadTestBlock())
        self.assertFalse(self.bc._checkBlockSimilarity())

    def test_createRepresentativeBlock(self):
        """Test creation of a representative block.

        .. test:: Create representative blocks using a volume-weighted averaging.
            :id: T_ARMI_XSGM_CREATE_REPR_BLOCKS0
            :tests: R_ARMI_XSGM_CREATE_REPR_BLOCKS
        """
        avgB = self.bc.createRepresentativeBlock()
        self.assertNotIn(avgB, self.bc)
        # (0 + 1 + 2 + 3 + 4) / 5 = 10/5 = 2.0
        self.assertAlmostEqual(avgB.getNumberDensity("U235"), 2.0)
        # (0 + 1/4 + 2/4 + 3/4 + 4/4) / 5 * 100.0 = 50.0
        self.assertEqual(avgB.p.percentBu, 50.0)

        # check that a new block collection of the representative block has right temperatures
        # this is required for Doppler coefficient calculations
        newBc = AverageBlockCollection(
            self.blockList[0].r.blueprints.allNuclidesInProblem
        )
        newBc.append(avgB)
        newBc.calcAvgNuclideTemperatures()
        self.assertAlmostEqual(newBc.avgNucTemperatures["U235"], 603.0)
        self.assertAlmostEqual(newBc.avgNucTemperatures["FE56"], 502.0)
        self.assertAlmostEqual(newBc.avgNucTemperatures["NA23"], 402.0)

    def test_createRepresentativeBlockDissimilar(self):
        """
        Test creation of a representative block from a collection with dissimilar blocks
        """
        uniqueBlock = test_blocks.loadTestBlock()
        uniqueBlock.p.percentBu = 50.0
        fpFactory = test_lumpedFissionProduct.getDummyLFPFile()
        uniqueBlock.setLumpedFissionProducts(fpFactory.createLFPsFromFile())
        uniqueBlock.setNumberDensity("U235", 2.0)
        uniqueBlock.p.gasReleaseFraction = 1.0
        for c in uniqueBlock:
            if c.hasFlags(Flags.FUEL):
                c.temperatureInC = 600.0
            elif c.hasFlags([Flags.CLAD, Flags.DUCT, Flags.WIRE]):
                c.temperatureInC = 500.0
            elif c.hasFlags([Flags.BOND, Flags.COOLANT, Flags.INTERCOOLANT]):
                c.temperatureInC = 400.0
        self.bc.append(uniqueBlock)

        with mockRunLogs.BufferLog() as mock:
            avgB = self.bc.createRepresentativeBlock()
            self.assertIn(
                "Non-matching block in AverageBlockCollection", mock.getStdout()
            )

        self.assertNotIn(avgB, self.bc)
        # (0 + 1 + 2 + 3 + 4 + 2) / 6.0 = 12/6 = 2.0
        self.assertAlmostEqual(avgB.getNumberDensity("U235"), 2.0)
        # (0 + 1/4 + 2/4 + 3/4 + 4/4) / 5 * 100.0 = 50.0
        self.assertAlmostEqual(avgB.p.percentBu, 50.0)

        # U35 has different average temperature because blocks have different U235 content
        newBc = AverageBlockCollection(
            self.blockList[0].r.blueprints.allNuclidesInProblem
        )
        newBc.append(avgB)
        newBc.calcAvgNuclideTemperatures()
        # temps expected to be proportional to volume-fraction weighted temperature
        # this is a non-physical result, but it demonstrates a problem that exists in the code
        # when dissimilar blocks are put together in a BlockCollection
        structureVolume = sum(
            c.getVolume()
            for c in avgB.getComponents([Flags.CLAD, Flags.DUCT, Flags.WIRE])
        )
        fuelVolume = avgB.getComponent(Flags.FUEL).getVolume()
        coolantVolume = sum(
            c.getVolume()
            for c in avgB.getComponents([Flags.BOND, Flags.COOLANT, Flags.INTERCOOLANT])
        )
        expectedIronTemp = (structureVolume * 500.0 + fuelVolume * 600.0) / (
            structureVolume + fuelVolume
        )
        expectedSodiumTemp = (coolantVolume * 400.0 + fuelVolume * 600.0) / (
            coolantVolume + fuelVolume
        )
        self.assertAlmostEqual(newBc.avgNucTemperatures["U235"], 600.0)
        self.assertAlmostEqual(newBc.avgNucTemperatures["FE56"], expectedIronTemp)
        self.assertAlmostEqual(newBc.avgNucTemperatures["NA23"], expectedSodiumTemp)


class TestComponentAveraging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fpFactory = test_lumpedFissionProduct.getDummyLFPFile()
        cls.blockList = makeBlocks(3)
        for bi, b in enumerate(cls.blockList):
            b.setType("fuel")
            b.setLumpedFissionProducts(fpFactory.createLFPsFromFile())
            # put some trace Fe-56 and Na-23 into the fuel
            # zero out all fuel nuclides except U-235 (for mass-weighting of component temperature)
            for nuc in b.getNuclides():
                b.setNumberDensity(nuc, 0.0)
            b.setNumberDensity("U235", bi)
            b.setNumberDensity("FE56", bi / 2.0)
            b.setNumberDensity("NA23", bi / 3.0)
            for c in b:
                if c.hasFlags(Flags.FUEL):
                    c.temperatureInC = 600.0 + bi
                elif c.hasFlags([Flags.CLAD, Flags.DUCT, Flags.WIRE]):
                    c.temperatureInC = 500.0 + bi
                elif c.hasFlags([Flags.BOND, Flags.COOLANT, Flags.INTERCOOLANT]):
                    c.temperatureInC = 400.0 + bi

    def setUp(self):
        self.bc = AverageBlockCollection(
            self.blockList[0].r.blueprints.allNuclidesInProblem
        )
        blockCopies = [copy.deepcopy(b) for b in self.blockList]
        self.bc.extend(blockCopies)

    def test_getAverageComponentNumberDensities(self):
        """
        Test component number density averaging
        """
        # becaue of the way densities are set up, the middle block (index 1 of 0-2) component densities are equivalent to the average
        b = self.bc[1]
        for compIndex, c in enumerate(b.getComponents()):
            avgDensities = self.bc._getAverageComponentNumberDensities(compIndex)
            compDensities = c.getNumberDensities()
            for nuc in c.getNuclides():
                self.assertAlmostEqual(
                    compDensities[nuc],
                    avgDensities[nuc],
                    msg=f"{nuc} density {compDensities[nuc]} not equal to {avgDensities[nuc]}!",
                )

    def test_getAverageComponentTemperature(self):
        """
        Test mass-weighted component temperature averaging
        """
        b = self.bc[0]
        massWeightedIncrease = 5.0 / 3.0
        baseTemps = [600, 400, 500, 500, 400, 500, 400]
        expectedTemps = [t + massWeightedIncrease for t in baseTemps]
        for compIndex, c in enumerate(b.getComponents()):
            avgTemp = self.bc._getAverageComponentTemperature(compIndex)
            self.assertAlmostEqual(
                expectedTemps[compIndex],
                avgTemp,
                msg=f"{c} avg temperature {avgTemp} not equal to expected {expectedTemps[compIndex]}!",
            )

    def test_getAverageComponentTemperatureVariedWeights(self):
        """
        Test mass-weighted component temperature averaging with variable weights
        """
        # make up a fake weighting with power param
        self.bc.weightingParam = "power"
        for i, b in enumerate(self.bc):
            b.p.power = i
        weightedIncrease = 1.8
        baseTemps = [600, 400, 500, 500, 400, 500, 400]
        expectedTemps = [t + weightedIncrease for t in baseTemps]
        for compIndex, c in enumerate(b.getComponents()):
            avgTemp = self.bc._getAverageComponentTemperature(compIndex)
            self.assertAlmostEqual(
                expectedTemps[compIndex],
                avgTemp,
                msg=f"{c} avg temperature {avgTemp} not equal to expected {expectedTemps[compIndex]}!",
            )

    def test_getAverageComponentTemperatureNoMass(self):
        """
        Test component temperature averaging when the components have no mass
        """
        for b in self.bc:
            for nuc in b.getNuclides():
                b.setNumberDensity(nuc, 0.0)

        unweightedIncrease = 1.0
        baseTemps = [600, 400, 500, 500, 400, 500, 400]
        expectedTemps = [t + unweightedIncrease for t in baseTemps]
        for compIndex, c in enumerate(b.getComponents()):
            avgTemp = self.bc._getAverageComponentTemperature(compIndex)
            self.assertAlmostEqual(
                expectedTemps[compIndex],
                avgTemp,
                msg=f"{c} avg temperature {avgTemp} not equal to expected {expectedTemps[compIndex]}!",
            )


class TestBlockCollectionComponentAverage(unittest.TestCase):
    r"""tests for ZPPR 1D XS gen cases."""

    def setUp(self):
        r"""
        First part of setup same as test_Cartesian.
        Second part of setup builds lists/dictionaries of expected values to compare to.
        has expected values for component isotopic atom density and component area.
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
        self.expectedBlockDensities = [
            expectedRepBlanketBlock,
            expectedRepFuelBlock,
            expectedRepFuelBlock,
        ]
        self.expectedAreas = [[1, 6, 1], [1, 2, 1, 4]]

    def test_ComponentAverageRepBlock(self):
        """Tests that the XS group manager calculates the expected component atom density
        and component area correctly.

        Order of components is also checked since in 1D cases the order of the components matters.
        """
        xsgm = self.o.getInterface("xsGroups")

        for _xsID, xsOpt in self.o.cs[CONF_CROSS_SECTION].items():
            self.assertEqual(xsOpt.blockRepresentation, None)

        xsgm.interactBOL()

        # Check that the correct defaults are propagated after the interactBOL
        # from the cross section group manager is called.
        for _xsID, xsOpt in self.o.cs[CONF_CROSS_SECTION].items():
            self.assertEqual(
                xsOpt.blockRepresentation, self.o.cs[CONF_XS_BLOCK_REPRESENTATION]
            )

        xsgm.createRepresentativeBlocks()
        representativeBlockList = list(xsgm.representativeBlocks.values())
        representativeBlockList.sort(key=lambda repB: repB.getMass() / repB.getVolume())

        assert len(representativeBlockList) == len(self.expectedBlockDensities)
        for b, componentDensities, areas in zip(
            representativeBlockList, self.expectedBlockDensities, self.expectedAreas
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


class TestBlockCollectionComponentAverage1DCylinder(unittest.TestCase):
    """tests for 1D cylinder XS gen cases."""

    def setUp(self):
        """First part of setup same as test_Cartesian.

        Second part of setup builds lists/dictionaries of expected values to compare to.
        has expected values for component isotopic atom density and component area.
        """
        self.o, self.r = test_reactors.loadTestReactor(TEST_ROOT)

        sodiumDensity = {"NA23": 0.022166571826233578}
        steelDensity = {
            "C": 0.0007685664978992269,
            "V": 0.0002718224847461385,
            "SI28": 0.0003789374369638149,
            "SI29": 1.924063709833714e-05,
            "SI30": 1.268328992580968e-05,
            "CR50": 0.0004532023742335746,
            "CR52": 0.008739556775111474,
            "CR53": 0.0009909955713678232,
            "CR54": 0.000246679773317009,
            "MN55": 0.0004200803669857142,
            "FE54": 0.004101496663229472,
            "FE56": 0.06438472483061823,
            "FE57": 0.0014869241111006412,
            "FE58": 0.00019788230265709334,
            "NI58": 0.0002944487657779742,
            "NI60": 0.00011342053328927859,
            "NI61": 4.930763373747379e-06,
            "NI62": 1.571788956157717e-05,
            "NI64": 4.005163933412346e-06,
            "MO92": 7.140180476114493e-05,
            "MO94": 4.4505841916481845e-05,
            "MO95": 7.659816252004227e-05,
            "MO96": 8.02548587207478e-05,
            "MO97": 4.594927462728666e-05,
            "MO98": 0.00011610009956095838,
            "MO100": 4.6334190016834624e-05,
            "W182": 3.663619370317025e-05,
            "W183": 1.9783544599711936e-05,
            "W184": 4.235973352562047e-05,
            "W186": 3.9304414603061506e-05,
        }
        linerAdjustment = 1.014188527784268
        cladDensity = {
            nuc: dens * linerAdjustment for nuc, dens in steelDensity.items()
        }
        fuelDensity = {
            "AM241": 2.3605999999999997e-05,
            "PU238": 3.7387e-06,
            "PU239": 0.0028603799999999996,
            "PU240": 0.000712945,
            "PU241": 9.823120000000004e-05,
            "PU242": 2.02221e-05,
            "U235": 0.00405533,
            "U238": 0.0134125,
        }
        self.expectedComponentDensities = [
            fuelDensity,
            sodiumDensity,
            cladDensity,
            steelDensity,
            sodiumDensity,
            steelDensity,
            sodiumDensity,
        ]
        self.expectedComponentAreas = [
            99.54797488948871,
            29.719913442616843,
            30.07759373476877,
            1.365897776727751,
            63.184097853691235,
            17.107013842808822,
            1.9717608091694139,
        ]

    def test_ComponentAverage1DCylinder(self):
        """Tests that the XS group manager calculates the expected component atom density
        and component area correctly.

        Order of components is also checked since in 1D cases the order of the components matters.

        .. test:: Create representative blocks using custom cylindrical averaging.
            :id: T_ARMI_XSGM_CREATE_REPR_BLOCKS1
            :tests: R_ARMI_XSGM_CREATE_REPR_BLOCKS
        """
        xsgm = self.o.getInterface("xsGroups")

        xsgm.interactBOL()

        # Check that the correct defaults are propagated after the interactBOL
        # from the cross section group manager is called.
        xsOpt = self.o.cs[CONF_CROSS_SECTION]["ZA"]
        self.assertEqual(xsOpt.blockRepresentation, "ComponentAverage1DCylinder")

        xsgm.createRepresentativeBlocks()
        xsgm.updateNuclideTemperatures()

        representativeBlockList = list(xsgm.representativeBlocks.values())
        representativeBlockList.sort(key=lambda repB: repB.getMass() / repB.getVolume())
        reprBlock = xsgm.representativeBlocks["ZA"]
        self.assertEqual(reprBlock.name, "1D_CYL_AVG_ZA")
        self.assertEqual(reprBlock.p.percentBu, 0.0)

        refTemps = {"fuel": 600.0, "coolant": 450.0, "structure": 462.4565}

        for c, compDensity, compArea in zip(
            reprBlock, self.expectedComponentDensities, self.expectedComponentAreas
        ):
            self.assertEqual(compArea, c.getArea())
            cNucs = c.getNuclides()
            for nuc in cNucs:
                self.assertAlmostEqual(
                    c.getNumberDensity(nuc), compDensity.get(nuc, 0.0)
                )
                if "fuel" in c.getType():
                    compTemp = refTemps["fuel"]
                elif any(sodium in c.getType() for sodium in ["bond", "coolant"]):
                    compTemp = refTemps["coolant"]
                else:
                    compTemp = refTemps["structure"]
                self.assertAlmostEqual(
                    compTemp,
                    xsgm.avgNucTemperatures["ZA"][nuc],
                    2,
                    f"{nuc} temperature does not match expected value of {compTemp}",
                )

    def test_checkComponentConsistency(self):
        xsgm = self.o.getInterface("xsGroups")
        xsgm.interactBOL()
        blockCollectionsByXsGroup = xsgm.makeCrossSectionGroups()

        blockCollection = blockCollectionsByXsGroup["ZA"]
        baseComponents = self.r.core.getFirstBlock(Flags.CONTROL).getComponents()
        densities = {
            "control": baseComponents[0].getNumberDensities(),
            "clad": baseComponents[2].getNumberDensities(),
            "coolant": baseComponents[4].getNumberDensities(),
        }
        controlComponent, cladComponent, coolantComponent = self._makeComponents(
            7, densities
        )

        # reference block
        refBlock = HexBlock("refBlock")
        refBlock.add(controlComponent)
        refBlock.add(cladComponent)
        refBlock.add(coolantComponent)

        # matching block
        matchingBlock = HexBlock("matchBlock")
        matchingBlock.add(controlComponent)
        matchingBlock.add(cladComponent)
        matchingBlock.add(coolantComponent)

        # unsorted block
        unsortedBlock = HexBlock("unsortedBlock")
        unsortedBlock.add(cladComponent)
        unsortedBlock.add(coolantComponent)
        unsortedBlock.add(controlComponent)

        # non-matching block length
        nonMatchingLengthBlock = HexBlock("blockLengthDiff")
        nonMatchingLengthBlock.add(controlComponent)
        nonMatchingLengthBlock.add(coolantComponent)

        # non-matching component multiplicity
        nonMatchingMultBlock = HexBlock("blockComponentDiff")
        control, clad, coolant = self._makeComponents(19, densities)
        nonMatchingMultBlock.add(control)
        nonMatchingMultBlock.add(clad)
        nonMatchingMultBlock.add(coolant)

        # different nuclides
        nucDiffBlock = HexBlock("blockNucDiff")
        mixedDensities = {
            "clad": baseComponents[0].getNumberDensities(),
            "coolant": baseComponents[2].getNumberDensities(),
            "control": baseComponents[4].getNumberDensities(),
        }
        control, clad, coolant = self._makeComponents(7, mixedDensities)
        nucDiffBlock.add(control)
        nucDiffBlock.add(clad)
        nucDiffBlock.add(coolant)

        # additional non-important nuclides
        negligibleNucDiffBlock = HexBlock("blockNegligibleNucDiff")
        negligibleNuc = {"N14": 1.0e-5}
        modControl = baseComponents[0].getNumberDensities()
        modClad = baseComponents[2].getNumberDensities()
        modCoolant = baseComponents[4].getNumberDensities()
        modControl.update(negligibleNuc)
        modClad.update(negligibleNuc)
        modCoolant.update(negligibleNuc)
        mixedDensities = {
            "control": modControl,
            "clad": modClad,
            "coolant": modCoolant,
        }
        control, clad, coolant = self._makeComponents(7, mixedDensities)
        negligibleNucDiffBlock.add(control)
        negligibleNucDiffBlock.add(clad)
        negligibleNucDiffBlock.add(coolant)

        blockCollection._checkComponentConsistency(refBlock, matchingBlock)
        blockCollection._checkComponentConsistency(refBlock, unsortedBlock)
        blockCollection._checkComponentConsistency(refBlock, negligibleNucDiffBlock)
        for b in (nonMatchingMultBlock, nonMatchingLengthBlock, nucDiffBlock):
            with self.assertRaises(ValueError):
                blockCollection._checkComponentConsistency(refBlock, b)

    def _makeComponents(self, multiplicity, densities):
        from armi.reactor import components

        baseComponents = self.r.core.getFirstBlock(Flags.CONTROL).getComponents()
        controlComponent = components.Circle(
            "control",
            baseComponents[0].material,
            20.0,
            20.0,
            id=0.0,
            od=0.6,
            mult=multiplicity,
        )
        cladComponent = components.Circle(
            "clad",
            baseComponents[2].material,
            20.0,
            20.0,
            id=0.6,
            od=0.7,
            mult=multiplicity,
        )
        coolantComponent = components.Circle(
            "coolant",
            baseComponents[4].material,
            20.0,
            20.0,
            id=0.7,
            od=0.8,
            mult=multiplicity,
        )

        controlComponent.setNumberDensities(densities["control"])
        cladComponent.setNumberDensities(densities["clad"])
        coolantComponent.setNumberDensities(densities["coolant"])

        return controlComponent, cladComponent, coolantComponent


class TestBlockCollectionFluxWeightedAverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fpFactory = test_lumpedFissionProduct.getDummyLFPFile()
        cls.blockList = makeBlocks(5)
        for bi, b in enumerate(cls.blockList):
            b.setType("fuel")
            b.p.percentBu = bi / 4.0 * 100
            b.setLumpedFissionProducts(fpFactory.createLFPsFromFile())
            b.setNumberDensity("U235", bi)
            b.p.gasReleaseFraction = bi * 2 / 8.0
            b.p.flux = bi + 1

    def setUp(self):
        self.bc = FluxWeightedAverageBlockCollection(
            self.blockList[0].r.blueprints.allNuclidesInProblem
        )
        self.bc.extend(self.blockList)

    def test_createRepresentativeBlock(self):
        self.bc[1].p.flux = 1e99  # only the 2nd block values should show up
        avgB = self.bc.createRepresentativeBlock()
        self.assertNotIn(avgB, self.bc)
        self.assertAlmostEqual(avgB.getNumberDensity("U235"), 1.0)
        self.assertEqual(avgB.p.percentBu, 25.0)

    def test_invalidWeights(self):
        self.bc[0].p.flux = 0.0
        with self.assertRaises(ValueError):
            self.bc.createRepresentativeBlock()


class TestCrossSectionGroupManager(unittest.TestCase):
    def setUp(self):
        cs = settings.Settings()
        self.blockList = makeBlocks(20)
        self.csm = CrossSectionGroupManager(self.blockList[0].r, cs)
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

    def test_calcWeightedBurnup(self):
        self.blockList[1].p.percentBu = 3.1
        self.blockList[2].p.percentBu = 10.0
        self.blockList[3].p.percentBu = 1.5
        for b in self.blockList[4:]:
            b.p.percentBu = 0.0
        self.csm._updateBurnupGroups(self.blockList)
        blockCollectionsByXsGroup = {}
        blockCollectionsByXsGroup = self.csm._addXsGroupsFromBlocks(
            blockCollectionsByXsGroup, self.blockList
        )
        ABcollection = blockCollectionsByXsGroup["AB"]
        self.assertEqual(
            blockCollectionsByXsGroup["AA"]._calcWeightedBurnup(), 1 / 12.0
        )
        self.assertEqual(
            ABcollection.getWeight(self.blockList[1]),
            ABcollection.getWeight(self.blockList[2]),
            "The two blocks in AB do not have the same weighting!",
        )
        self.assertEqual(ABcollection._calcWeightedBurnup(), 6.55)

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
        """Test that we can create the representative blocks for a reactor.

        .. test:: Build representative blocks for a reactor.
            :id: T_ARMI_XSGM_CREATE_XS_GROUPS
            :tests: R_ARMI_XSGM_CREATE_XS_GROUPS
        """
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
            origXSIDsFromNew,
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
        self.assertEqual(origXSIDsFromNew["BA"], "AA")

    def test_interactBOL(self):
        """Test `BOL` lattice physics update frequency.

        .. test:: The XSGM frequency depends on the LPI frequency at BOL.
            :id: T_ARMI_XSGM_FREQ0
            :tests: R_ARMI_XSGM_FREQ
        """
        self.blockList[0].r.p.timeNode = 0
        self.csm.cs[CONF_LATTICE_PHYSICS_FREQUENCY] = "BOL"
        self.csm.interactBOL()
        self.assertTrue(self.csm.representativeBlocks)

    def test_interactBOC(self):
        """Test `BOC` lattice physics update frequency.

        .. test:: The XSGM frequency depends on the LPI frequency at BOC.
            :id: T_ARMI_XSGM_FREQ1
            :tests: R_ARMI_XSGM_FREQ
        """
        self.blockList[0].r.p.timeNode = 0
        self.csm.cs[CONF_LATTICE_PHYSICS_FREQUENCY] = "BOC"
        self.csm.interactBOL()
        self.csm.interactBOC()
        self.assertTrue(self.csm.representativeBlocks)

    def test_interactEveryNode(self):
        """Test `everyNode` lattice physics update frequency.

        .. test:: The XSGM frequency depends on the LPI frequency at every time node.
            :id: T_ARMI_XSGM_FREQ2
            :tests: R_ARMI_XSGM_FREQ
        """
        self.csm.cs[CONF_LATTICE_PHYSICS_FREQUENCY] = "BOC"
        self.csm.interactBOL()
        self.csm.interactEveryNode()
        self.assertFalse(self.csm.representativeBlocks)
        self.csm.cs[CONF_LATTICE_PHYSICS_FREQUENCY] = "everyNode"
        self.csm.interactBOL()
        self.csm.interactEveryNode()
        self.assertTrue(self.csm.representativeBlocks)

    def test_interactFirstCoupledIteration(self):
        """Test `firstCoupledIteration` lattice physics update frequency.

        .. test:: The XSGM frequency depends on the LPI frequency during first coupled iteration.
            :id: T_ARMI_XSGM_FREQ3
            :tests: R_ARMI_XSGM_FREQ
        """
        self.csm.cs[CONF_LATTICE_PHYSICS_FREQUENCY] = "everyNode"
        self.csm.interactBOL()
        self.csm.interactCoupled(iteration=0)
        self.assertFalse(self.csm.representativeBlocks)
        self.csm.cs[CONF_LATTICE_PHYSICS_FREQUENCY] = "firstCoupledIteration"
        self.csm.interactBOL()
        self.csm.interactCoupled(iteration=0)
        self.assertTrue(self.csm.representativeBlocks)

    def test_interactAllCoupled(self):
        """Test `all` lattice physics update frequency.

        .. test:: The XSGM frequency depends on the LPI frequency during coupling.
            :id: T_ARMI_XSGM_FREQ4
            :tests: R_ARMI_XSGM_FREQ
        """
        self.csm.cs[CONF_LATTICE_PHYSICS_FREQUENCY] = "firstCoupledIteration"
        self.csm.interactBOL()
        self.csm.interactCoupled(iteration=1)
        self.assertFalse(self.csm.representativeBlocks)
        self.csm.cs[CONF_LATTICE_PHYSICS_FREQUENCY] = "all"
        self.csm.interactBOL()
        self.csm.interactCoupled(iteration=1)
        self.assertTrue(self.csm.representativeBlocks)

    def test_copyPregeneratedFiles(self):
        """
        Tests copying pre-generated cross section and flux files
        using reactor that is built from a case settings file.
        """
        o, r = test_reactors.loadTestReactor(TEST_ROOT)
        # Need to overwrite the relative paths with absolute
        o.cs[CONF_CROSS_SECTION]["XA"].xsFileLocation = [
            os.path.join(THIS_DIR, "ISOXA")
        ]
        o.cs[CONF_CROSS_SECTION]["YA"].fluxFileLocation = os.path.join(
            THIS_DIR, "rzmflxYA"
        )
        csm = CrossSectionGroupManager(r, o.cs)

        with TemporaryDirectoryChanger(root=THIS_DIR):
            csm._copyPregeneratedXSFile("XA")
            csm._copyPregeneratedFluxSolutionFile("YA")
            self.assertTrue(os.path.exists("ISOXA"))
            self.assertTrue(os.path.exists("rzmflxYA"))


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


def makeBlocks(howMany=20):
    _o, r = test_reactors.loadTestReactor(TEST_ROOT)
    return r.core.getBlocks(Flags.FUEL)[
        3 : howMany + 3
    ]  # shift y 3 to skip central assemblies 1/3 volume
