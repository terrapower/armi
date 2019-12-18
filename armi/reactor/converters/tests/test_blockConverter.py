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
import unittest
import os

import numpy

from armi.reactor.converters import blockConverters
from armi.reactor import components
from armi.reactor.flags import Flags
from armi.reactor.tests.test_blocks import loadTestBlock
from armi.reactor.tests.test_reactors import loadTestReactor, TEST_ROOT
from armi.utils import hexagon


class TestBlockConverter(unittest.TestCase):
    def test_dissolveWireIntoCoolant(self):
        self._test_dissolve(loadTestBlock(), "wire", "coolant")
        hotBlock = loadTestBlock(cold=False)
        self._test_dissolve(hotBlock, "wire", "coolant")
        hotBlock = self._perturbTemps(hotBlock, "wire", 127, 800)
        self._test_dissolve(hotBlock, "wire", "coolant")

    def test_dissolveLinerIntoClad(self):
        self._test_dissolve(loadTestBlock(), "outer liner", "clad")
        hotBlock = loadTestBlock(cold=False)
        self._test_dissolve(hotBlock, "outer liner", "clad")
        hotBlock = self._perturbTemps(hotBlock, "outer liner", 127, 800)
        self._test_dissolve(hotBlock, "outer liner", "clad")

    def _perturbTemps(self, block, cName, tCold, tHot):
        "Give the component different ref and hot temperatures than in test_Blocks."
        c = block.getComponent(Flags.fromString(cName))
        c.refTemp, c.refHot = tCold, tHot
        c.applyMaterialMassFracsToNumberDensities()
        c.setTemperature(tHot)
        return block

    def _test_dissolve(self, block, soluteName, solventName):
        converter = blockConverters.ComponentMerger(block, soluteName, solventName)
        convertedBlock = converter.convert()
        self.assertNotIn(soluteName, convertedBlock.getComponentNames())
        self._checkAreaAndComposition(block, convertedBlock)

    def test_build_NthRing(self):
        """Test building of one ring."""
        RING = 6
        block = loadTestBlock(cold=False)
        numPinsInRing = 30
        converter = blockConverters.HexComponentsToCylConverter(block)
        fuel, clad = _buildJoyoFuel()
        pinComponents = [fuel, clad]
        converter._buildFirstRing(pinComponents)
        converter.pinPitch = 0.76
        converter._buildNthRing(pinComponents, RING)
        components = converter.convertedBlock
        self.assertEqual(components[3].name.split()[0], components[-1].name.split()[0])
        self.assertAlmostEqual(
            clad.getNumberDensity("FE56"), components[1].getNumberDensity("FE56")
        )
        self.assertAlmostEqual(
            components[3].getArea() + components[-1].getArea(),
            clad.getArea() * numPinsInRing / clad.getDimension("mult"),
        )

    def test_convert(self):
        """Test conversion with no fuel driver."""
        block = (
            loadTestReactor(TEST_ROOT)[1]
            .core.getAssemblies(Flags.FUEL)[2]
            .getFirstBlock(Flags.FUEL)
        )
        area = block.getArea()
        converter = blockConverters.HexComponentsToCylConverter(block)
        converter.convert()
        self.assertAlmostEqual(area, converter.convertedBlock.getArea())
        self.assertAlmostEqual(area, block.getArea())

        for compType in [Flags.FUEL, Flags.CLAD, Flags.DUCT]:
            self.assertAlmostEqual(
                block.getComponent(compType).getArea(),
                sum(
                    [
                        component.getArea()
                        for component in converter.convertedBlock
                        if component.hasFlags(compType)
                    ]
                ),
            )

        self._checkAreaAndComposition(block, converter.convertedBlock)
        self._checkCiclesAreInContact(converter.convertedBlock)

    def test_convertHexWithFuelDriver(self):
        """Test conversion with fuel driver."""
        driverBlock = (
            loadTestReactor(TEST_ROOT)[1]
            .core.getAssemblies(Flags.FUEL)[2]
            .getFirstBlock(Flags.FUEL)
        )
        block = loadTestReactor(TEST_ROOT)[1].core.getFirstBlock(Flags.CONTROL)
        self._testConvertWithDriverRings(
            block,
            driverBlock,
            blockConverters.HexComponentsToCylConverter,
            hexagon.numPositionsInRing,
        )
        self._testConvertWithDriverRings(
            block,
            driverBlock,
            blockConverters.BlockAvgToCylConverter,
            hexagon.numPositionsInRing,
        )

    def test_convertCartesianLatticeWithFuelDriver(self):
        """Test conversion with fuel driver."""
        r = loadTestReactor(TEST_ROOT, inputFileName="zpprTest.yaml")[1]
        driverBlock = r.core.getAssemblies(Flags.FUEL)[2].getFirstBlock(Flags.FUEL)
        block = r.core.getAssemblies(Flags.FUEL)[2].getFirstBlock(Flags.BLANKET)
        converter = blockConverters.BlockAvgToCylConverter
        self._testConvertWithDriverRings(
            block, driverBlock, converter, lambda n: (n - 1) * 8
        )

    def _testConvertWithDriverRings(
        self, block, driverBlock, converterToTest, getNumInRing
    ):
        area = block.getArea()
        numExternalFuelRings = [1, 2, 3, 4]
        numBlocks = 1
        for externalRings in numExternalFuelRings:
            numBlocks += getNumInRing(externalRings + 1)
            converter = converterToTest(
                block, driverFuelBlock=driverBlock, numExternalRings=externalRings
            )
            convertedBlock = converter.convert()
            self.assertAlmostEqual(area * numBlocks, convertedBlock.getArea())
            self._checkCiclesAreInContact(convertedBlock)
            figureName = converter.plotConvertedBlock()
            os.remove(figureName)

            for c in list(reversed(convertedBlock))[:externalRings]:
                self.assertTrue(c.isFuel(), "c was {}".format(c.name))
                convertedBlock.remove(
                    c
                )  # remove external driver rings in preperation to check composition
            self._checkAreaAndComposition(block, convertedBlock)

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
                errorMessage += "\nnuc {} not equal. unmerged: {} merged: {}".format(
                    nucName, n1, n2
                )
        self.assertTrue(not errorMessage, errorMessage)
        bMass = block.getMass()
        self.assertAlmostEqual(bMass, convertedBlock.getMass())
        self.assertGreater(bMass, 0.0)  # verify it isn't empty

    def _checkCiclesAreInContact(self, convertedCircleBlock):
        numComponents = len(convertedCircleBlock)
        self.assertGreater(numComponents, 1)
        self.assertTrue(
            all(isinstance(c, components.Circle) for c in convertedCircleBlock)
        )

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
                    "previous component ({}) that had od {}".format(
                        c, thisID, lastComp, lastCompOD
                    ),
                )
            lastCompOD = thisOD
            lastComp = c


class TestToCircles(unittest.TestCase):
    def test_fromHex(self):
        actualRadii = blockConverters.radiiFromHexPitches([7.47, 7.85, 8.15])
        expected = [3.92203, 4.12154, 4.27906]
        self.assertTrue(numpy.allclose(expected, actualRadii, rtol=1e-5))

    def test_fromRingOfRods(self):
        # JOYO-LMFR-RESR-001, rev 1, Table A.2, 5th layer (ring 6)
        actualRadii = blockConverters.radiiFromRingOfRods(
            0.76 * 5, 6 * 5, [0.28, 0.315]
        )
        expected = [3.24034, 3.28553, 3.62584, 3.67104]
        self.assertTrue(numpy.allclose(expected, actualRadii, rtol=1e-5))


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
        name="fuel",
        material="HT9",
        Tinput=20.0,
        Thot=20.0,
        od=0.315 * 2,
        id=0.28 * 2,
        mult=91,
    )
    return fuel, clad


if __name__ == "__main__":
    #     import sys;sys.argv = ['', 'TestBlockConverter.test_convertHexWithFuelDriver']
    unittest.main()
