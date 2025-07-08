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

"""Test block conversions."""

import math
import os
import unittest

import numpy as np

from armi.physics.neutronics.isotopicDepletion.isotopicDepletionInterface import (
    isDepletable,
)
from armi.reactor import blocks, components, grids
from armi.reactor.converters import blockConverters
from armi.reactor.flags import Flags
from armi.reactor.tests.test_blocks import buildLinkedFuelBlock, loadTestBlock
from armi.testing import TEST_ROOT, loadTestReactor
from armi.utils import hexagon
from armi.utils.directoryChangers import TemporaryDirectoryChanger


def buildSimpleFuelBlockNegativeArea():
    """
    Return a simple block containing fuel, clad, duct, and coolant.

    The block has a negative-area gap between fuel and cladding for testing.
    """
    b = blocks.HexBlock("fuel", height=10.0)

    fuelDims = {"Tinput": 25, "Thot": 600, "od": 0.76, "id": 0.00, "mult": 127.0}
    cladDims = {"Tinput": 25, "Thot": 600, "od": 0.80, "id": 0.76, "mult": 127.0}
    ductDims = {"Tinput": 25, "Thot": 600, "op": 16, "ip": 15.3, "mult": 1.0}
    intercoolantDims = {
        "Tinput": 400,
        "Thot": 400,
        "op": 17.0,
        "ip": ductDims["op"],
        "mult": 1.0,
    }
    coolDims = {"Tinput": 25.0, "Thot": 400}

    fuel = components.Circle("fuel", "UZr", **fuelDims)
    clad = components.Circle("clad", "HT9", **cladDims)
    gapDims = {
        "Tinput": 25,
        "Thot": 600,
        "od": "clad.id",
        "id": "fuel.od",
        "mult": 127.0,
    }
    gapDims["components"] = {"fuel": fuel, "clad": clad}
    gap = components.Circle("gap", "Void", **gapDims)
    duct = components.Hexagon("duct", "HT9", **ductDims)
    coolant = components.DerivedShape("coolant", "Sodium", **coolDims)
    intercoolant = components.Hexagon("intercoolant", "Sodium", **intercoolantDims)

    b.add(fuel)
    b.add(gap)
    b.add(clad)
    b.add(duct)
    b.add(coolant)
    b.add(intercoolant)

    b.getVolumeFractions()

    return b


def buildSimpleFuelBlockNegativeAreaBond():
    """
    Return a simple block containing fuel, clad, duct, and coolant.

    The block has a negative-area bond between fuel and cladding for testing.
    """
    b = blocks.HexBlock("fuel", height=10.0)

    fuelDims = {"Tinput": 25, "Thot": 600, "od": 0.76, "id": 0.00, "mult": 127.0}
    cladDims = {"Tinput": 25, "Thot": 600, "od": 0.80, "id": 0.76, "mult": 127.0}
    ductDims = {"Tinput": 25, "Thot": 600, "op": 16, "ip": 15.3, "mult": 1.0}
    intercoolantDims = {
        "Tinput": 400,
        "Thot": 400,
        "op": 17.0,
        "ip": ductDims["op"],
        "mult": 1.0,
    }
    coolDims = {"Tinput": 25.0, "Thot": 400}

    fuel = components.Circle("fuel", "UZr", **fuelDims)
    clad = components.Circle("clad", "HT9", **cladDims)
    bondDims = {
        "Tinput": 25,
        "Thot": 600,
        "od": "clad.id",
        "id": "fuel.od",
        "mult": 127.0,
    }
    bondDims["components"] = {"fuel": fuel, "clad": clad}
    bond = components.Circle("bond", "Sodium", **bondDims)
    duct = components.Hexagon("duct", "HT9", **ductDims)
    coolant = components.DerivedShape("coolant", "Sodium", **coolDims)
    intercoolant = components.Hexagon("intercoolant", "Sodium", **intercoolantDims)

    b.add(fuel)
    b.add(bond)
    b.add(clad)
    b.add(duct)
    b.add(coolant)
    b.add(intercoolant)

    b.getVolumeFractions()

    return b


class TestBlockConverter(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_dissolveWireIntoCoolant(self):
        """
        Test dissolving wire into coolant.

        .. test:: Homogenize one component into another.
            :id: T_ARMI_BLOCKCONV0
            :tests: R_ARMI_BLOCKCONV
        """
        self._test_dissolve(loadTestBlock(), "wire", "coolant")
        hotBlock = loadTestBlock(cold=False)
        self._test_dissolve(hotBlock, "wire", "coolant")
        hotBlock = self._perturbTemps(hotBlock, "wire", 127, 800)
        self._test_dissolve(hotBlock, "wire", "coolant")

    def test_dissolveLinerIntoClad(self):
        """
        Test dissolving liner into clad.

        .. test:: Homogenize one component into another.
            :id: T_ARMI_BLOCKCONV1
            :tests: R_ARMI_BLOCKCONV
        """
        self._test_dissolve(loadTestBlock(), "outer liner", "clad")
        hotBlock = loadTestBlock(cold=False)
        self._test_dissolve(hotBlock, "outer liner", "clad")
        hotBlock = self._perturbTemps(hotBlock, "outer liner", 127, 800)
        self._test_dissolve(hotBlock, "outer liner", "clad")

    def test_dissolveBondIntoClad(self):
        """
        Test dissolving linked bond into coolant.

        .. test:: Homogenize a linked component into another.
            :id: T_ARMI_BLOCKCONV2
            :tests: R_ARMI_BLOCKCONV
        """
        self._test_dissolve(buildLinkedFuelBlock(), "bond", "clad")

    def _perturbTemps(self, block, cName, tCold, tHot):
        """Give the component different ref and hot temperatures than in test_Blocks."""
        c = block.getComponent(Flags.fromString(cName))
        c.refTemp, c.refHot = tCold, tHot
        c.setTemperature(tHot)
        return block

    def _test_dissolve(self, block, soluteName, solventName):
        converter = blockConverters.ComponentMerger(block, soluteName, solventName)
        convertedBlock = converter.convert()
        self.assertNotIn(soluteName, convertedBlock.getComponentNames())
        self._checkAreaAndComposition(block, convertedBlock)

    def test_dissolveMultiple(self):
        """Test dissolving multiple components into another."""
        self._test_dissolve_multi(loadTestBlock(), ["wire", "clad"], "coolant")
        self._test_dissolve_multi(loadTestBlock(), ["inner liner", "outer liner"], "clad")

    def test_dissolveZeroArea(self):
        """Test dissolving a zero-area component into another."""
        self._test_dissolve(loadTestBlock(), "gap2", "outer liner")

    def test_dissolveIntoZeroArea(self):
        """Test dissolving a component into a zero-area solvent (raises ValueError)."""
        with self.assertRaises(ValueError):
            self._test_dissolve(loadTestBlock(), "outer liner", "gap2")

    def test_dissolveNegativeArea(self):
        """Test dissolving a zero-area gap component into another."""
        self._test_dissolve(buildSimpleFuelBlockNegativeArea(), "gap", "clad")

    def test_dissolveNegativeArea(self):
        """Test dissolving a zero-area non-gap component into another."""
        with self.assertRaises(ValueError):
            self._test_dissolve(buildSimpleFuelBlockNegativeAreaBond(), "bond", "clad")

    def test_dissolveIntoNegativeArea(self):
        """Test dissolving a zero-area component into another."""
        with self.assertRaises(ValueError):
            self._test_dissolve(buildSimpleFuelBlockNegativeArea(), "clad", "gap")

    def _test_dissolve_multi(self, block, soluteNames, solventName):
        converter = blockConverters.MultipleComponentMerger(block, soluteNames, solventName)
        convertedBlock = converter.convert()
        for soluteName in soluteNames:
            self.assertNotIn(soluteName, convertedBlock.getComponentNames())
        self._checkAreaAndComposition(block, convertedBlock)

    def test_build_NthRing(self):
        """Test building of one ring."""
        RING = 6
        block = loadTestBlock(cold=False)
        block.spatialGrid = grids.HexGrid.fromPitch(1.0)

        numPinsInRing = 30
        converter = blockConverters.HexComponentsToCylConverter(block)
        fuel, clad = _buildJoyoFuel()
        pinComponents = [fuel, clad]
        converter._buildFirstRing(pinComponents)
        converter.pinPitch = 0.76
        converter._buildNthRing(pinComponents, RING)
        components = converter.convertedBlock
        self.assertEqual(components[3].name.split()[0], components[-1].name.split()[0])
        self.assertAlmostEqual(clad.getNumberDensity("FE56"), components[1].getNumberDensity("FE56"))
        self.assertAlmostEqual(
            components[3].getArea() + components[-1].getArea(),
            clad.getArea() * numPinsInRing / clad.getDimension("mult"),
        )

    def test_buildInsideDuct(self):
        """Test building inside the duct."""
        block = loadTestBlock(cold=False)
        block.spatialGrid = grids.HexGrid.fromPitch(1.0)
        converter = blockConverters.HexComponentsToCylConverter(block)
        converter._buildInsideDuct()
        insideBlock = converter.convertedBlock
        ductIP = block.getComponent(Flags.DUCT).getDimension("ip")
        bondMass = block.getComponent(Flags.BOND).getMass("NA")
        coolantMass = block.getComponent(Flags.COOLANT).getMass("NA")
        self.assertAlmostEqual(insideBlock.getMass("U235"), block.getMass("U235"))
        self.assertAlmostEqual(insideBlock.getMass("NA"), bondMass + coolantMass)
        self.assertAlmostEqual(insideBlock.getArea(), ductIP**2 * math.sqrt(3) / 2)

    def test_convert(self):
        """Test conversion with no fuel driver.

        .. test:: Convert hex blocks to cylindrical blocks.
            :id:  T_ARMI_BLOCKCONV_HEX_TO_CYL1
            :tests: R_ARMI_BLOCKCONV_HEX_TO_CYL
        """
        block = loadTestReactor(TEST_ROOT)[1].core.getAssemblies(Flags.FUEL)[2].getFirstBlock(Flags.FUEL)
        block.spatialGrid = grids.HexGrid.fromPitch(1.0)

        converter = blockConverters.HexComponentsToCylConverter(block)
        converter.convert()

        for compType in [Flags.FUEL, Flags.CLAD, Flags.DUCT]:
            self.assertAlmostEqual(
                block.getComponent(compType).getArea(),
                sum([component.getArea() for component in converter.convertedBlock if component.hasFlags(compType)]),
            )
            for c in converter.convertedBlock.getComponents(compType):
                self.assertEqual(block.getComponent(compType).temperatureInC, c.temperatureInC)

        self.assertEqual(block.getHeight(), converter.convertedBlock.getHeight())
        self._checkAreaAndComposition(block, converter.convertedBlock)
        self._checkCiclesAreInContact(converter.convertedBlock)

    def test_convertHexWithFuelDriver(self):
        """Test conversion with fuel driver.

        .. test:: Convert hex blocks to cylindrical blocks.
            :id:  T_ARMI_BLOCKCONV_HEX_TO_CYL0
            :tests: R_ARMI_BLOCKCONV_HEX_TO_CYL
        """
        driverBlock = loadTestReactor(TEST_ROOT)[1].core.getAssemblies(Flags.FUEL)[2].getFirstBlock(Flags.FUEL)

        block = loadTestReactor(TEST_ROOT)[1].core.getFirstBlock(Flags.CONTROL)
        control = block.getComponent(Flags.CONTROL)

        # add depletable flag to see if it is carried
        control.p.flags |= Flags.DEPLETABLE

        driverBlock.spatialGrid = None
        block.spatialGrid = grids.HexGrid.fromPitch(1.0)

        convertedWithoutDriver = self._testConvertWithDriverRings(
            block,
            driverBlock,
            blockConverters.HexComponentsToCylConverter,
            hexagon.numPositionsInRing,
        )

        self.assertEqual(5, len([c for c in convertedWithoutDriver if isDepletable(c)]))
        self.assertEqual(5, len([c for c in convertedWithoutDriver if c.hasFlags(Flags.CONTROL)]))
        self.assertEqual(9, len([c for c in convertedWithoutDriver if c.hasFlags(Flags.CLAD)]))

        # This should fail because a spatial grid is required
        # on the block.
        driverBlock.spatialGrid = None
        block.spatialGrid = None
        with self.assertRaises(ValueError):
            self._testConvertWithDriverRings(
                block,
                driverBlock,
                blockConverters.HexComponentsToCylConverter,
                hexagon.numPositionsInRing,
            )

        # The ``BlockAvgToCylConverter`` should work
        # without any spatial grid defined because it
        # assumes the grid based on the block type.
        driverBlock.spatialGrid = None
        block.spatialGrid = None

        convertedWithoutDriver = self._testConvertWithDriverRings(
            block,
            driverBlock,
            blockConverters.BlockAvgToCylConverter,
            hexagon.numPositionsInRing,
        )
        # block went to 1 component
        self.assertEqual(1, len([c for c in convertedWithoutDriver]))

    def test_convertHexWithFuelDrOnNegCompAreaBlock(self):
        """
        Tests the conversion of a control block with linked components, where a component contains a
        negative area due to thermal expansion.
        """
        driverBlock = loadTestReactor(TEST_ROOT)[1].core.getAssemblies(Flags.FUEL)[2].getFirstBlock(Flags.FUEL)

        block = buildControlBlockWithLinkedNegativeAreaComponent()
        areas = [c.getArea() for c in block]

        # Check that a negative area component exists.
        self.assertLess(min(areas), 0.0)

        driverBlock.spatialGrid = None
        block.spatialGrid = grids.HexGrid.fromPitch(1.0)

        converter = blockConverters.HexComponentsToCylConverter(block, driverFuelBlock=driverBlock, numExternalRings=2)
        convertedBlock = converter.convert()
        # The area is increased because the negative area components are
        # removed.
        self.assertGreater(convertedBlock.getArea(), block.getArea())

    def test_convertCartesianLatticeWithFuelDriver(self):
        """Test conversion with fuel driver."""
        r = loadTestReactor(TEST_ROOT, inputFileName="zpprTest.yaml")[1]
        driverBlock = r.core.getAssemblies(Flags.FUEL)[2].getFirstBlock(Flags.FUEL)
        block = r.core.getAssemblies(Flags.FUEL)[2].getFirstBlock(Flags.BLANKET)

        driverBlock.spatialGrid = grids.CartesianGrid.fromRectangle(1.0, 1.0)
        block.spatialGrid = grids.CartesianGrid.fromRectangle(1.0, 1.0)

        converter = blockConverters.BlockAvgToCylConverter
        self._testConvertWithDriverRings(block, driverBlock, converter, lambda n: (n - 1) * 8)

    def _testConvertWithDriverRings(self, block, driverBlock, converterToTest, getNumInRing):
        area = block.getArea()
        numExternalFuelRings = [1, 2, 3, 4]
        numBlocks = 1
        for externalRings in numExternalFuelRings:
            numBlocks += getNumInRing(externalRings + 1)
            converter = converterToTest(block, driverFuelBlock=driverBlock, numExternalRings=externalRings)
            convertedBlock = converter.convert()
            self.assertAlmostEqual(area * numBlocks, convertedBlock.getArea())
            self._checkCiclesAreInContact(convertedBlock)
            plotFile = "convertedBlock_{0}.svg".format(externalRings)
            converter.plotConvertedBlock(fName=plotFile)
            os.remove(plotFile)

            for c in list(reversed(convertedBlock))[:externalRings]:
                self.assertTrue(c.isFuel(), "c was {}".format(c.name))
                # remove external driver rings in preparation to check composition
                convertedBlock.remove(c)
            convBlockWithoutDriver = convertedBlock
            self._checkAreaAndComposition(block, convBlockWithoutDriver)

        return convBlockWithoutDriver

    def _checkAreaAndComposition(self, block, convertedBlock):
        self.assertAlmostEqual(block.getArea(), convertedBlock.getArea())
        unmergedNucs = block.getNumberDensities()
        convDens = convertedBlock.getNumberDensities()
        errorMessage = ""
        nucs = set(unmergedNucs) | set(convDens)
        for nucName in nucs:
            n1, n2 = unmergedNucs[nucName], convDens[nucName]
            try:
                self.assertAlmostEqual(n1, n2)
            except AssertionError:
                errorMessage += "\nnuc {} not equal. unmerged: {} merged: {}".format(nucName, n1, n2)
        self.assertTrue(not errorMessage, errorMessage)
        bMass = block.getMass()
        self.assertAlmostEqual(bMass, convertedBlock.getMass())
        self.assertGreater(bMass, 0.0)  # verify it isn't empty

    def _checkCiclesAreInContact(self, convertedCircleBlock):
        numComponents = len(convertedCircleBlock)
        self.assertGreater(numComponents, 1)
        self.assertTrue(all(isinstance(c, components.Circle) for c in convertedCircleBlock))

        lastCompOD = None
        lastComp = None
        for c in sorted(convertedCircleBlock):
            thisID = c.getDimension("id")
            thisOD = c.getDimension("od")
            if lastCompOD is None:
                self.assertTrue(
                    thisID == 0,
                    "The inner component {} should have an ID of zero".format(c),
                )
            else:
                self.assertTrue(
                    thisID == lastCompOD,
                    "The component {} with id {} was not in contact with the "
                    "previous component ({}) that had od {}".format(c, thisID, lastComp, lastCompOD),
                )
            lastCompOD = thisOD
            lastComp = c


class TestToCircles(unittest.TestCase):
    def test_fromHex(self):
        actualRadii = blockConverters.radiiFromHexPitches([7.47, 7.85, 8.15])
        expected = [3.92203, 4.12154, 4.27906]
        self.assertTrue(np.allclose(expected, actualRadii, rtol=1e-5))

    def test_fromRingOfRods(self):
        # JOYO-LMFR-RESR-001, rev 1, Table A.2, 5th layer (ring 6)
        actualRadii = blockConverters.radiiFromRingOfRods(0.76 * 5, 6 * 5, [0.28, 0.315])
        expected = [3.24034, 3.28553, 3.62584, 3.67104]
        self.assertTrue(np.allclose(expected, actualRadii, rtol=1e-5))


def _buildJoyoFuel():
    """Build some JOYO components."""
    fuel = components.Circle(
        name="fuel",
        material="UO2",
        Tinput=20.0,
        Thot=20.0,
        od=0.28 * 2,
        id=0.0,
        mult=91,
    )
    clad = components.Circle(
        name="clad",
        material="HT9",
        Tinput=20.0,
        Thot=20.0,
        od=0.315 * 2,
        id=0.28 * 2,
        mult=91,
    )
    return fuel, clad


def buildControlBlockWithLinkedNegativeAreaComponent():
    """
    Return a block that contains a bond component that resolves to a negative area once the fuel and
    clad thermal expansion have occurred.
    """
    b = blocks.HexBlock("control", height=10.0)

    controlDims = {"Tinput": 25.0, "Thot": 600, "od": 0.77, "id": 0.00, "mult": 127.0}
    bondDims = {
        "Tinput": 600,
        "Thot": 600,
        "od": "clad.id",
        "id": "control.od",
        "mult": 127.0,
    }
    cladDims = {"Tinput": 25.0, "Thot": 450, "od": 0.80, "id": 0.77, "mult": 127.0}
    wireDims = {
        "Tinput": 25.0,
        "Thot": 450,
        "od": 0.1,
        "id": 0.0,
        "mult": 127.0,
        "axialPitch": 30.0,
        "helixDiameter": 0.9,
    }
    ductDims = {"Tinput": 25.0, "Thot": 400, "op": 16, "ip": 15.3, "mult": 1.0}
    intercoolantDims = {
        "Tinput": 400,
        "Thot": 400,
        "op": 17.0,
        "ip": ductDims["op"],
        "mult": 1.0,
    }
    coolDims = {"Tinput": 25.0, "Thot": 400}

    control = components.Circle("control", "UZr", **controlDims)
    clad = components.Circle("clad", "HT9", **cladDims)
    # This sets up the linking of the bond to the fuel and the clad components.
    bond = components.Circle("bond", "Sodium", components={"control": control, "clad": clad}, **bondDims)
    wire = components.Helix("wire", "HT9", **wireDims)
    duct = components.Hexagon("duct", "HT9", **ductDims)
    coolant = components.DerivedShape("coolant", "Sodium", **coolDims)
    intercoolant = components.Hexagon("intercoolant", "Sodium", **intercoolantDims)

    b.add(control)
    b.add(bond)
    b.add(clad)
    b.add(wire)
    b.add(duct)
    b.add(coolant)
    b.add(intercoolant)

    return b
