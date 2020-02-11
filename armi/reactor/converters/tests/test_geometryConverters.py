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

"""Module to test geometry converters."""
import math
import os
import unittest

from armi import runLog
from armi import settings
from armi.utils import pathTools
from armi.reactor import blocks
from armi.reactor import geometry
from armi.tests import TEST_ROOT
from armi.nucDirectory import nuclideBases
from armi.reactor.converters import geometryConverters
from armi.reactor.tests.test_reactors import loadTestReactor
from armi.reactor.flags import Flags
from armi.reactor import locations


THIS_DIR = pathTools.armiAbsDirFromName(__name__)


class TestGeometryConverters(unittest.TestCase):
    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT)
        self.cs = settings.getMasterCs()

    def test_addRing(self):
        r"""
        Tests that the addRing method adds the correct number of fuel assemblies to the test reactor
        """
        converter = geometryConverters.FuelAssemNumModifier(self.cs)
        converter.numFuelAssems = 7
        converter.ringsToAdd = 1 * ["radial shield"]
        converter.convert(self.r)

        numAssems = len(self.r.core.getAssemblies())
        self.assertEqual(
            numAssems, 13
        )  # should wind up with 6 reflector assemblies per 1/3rd core
        shieldtype = self.r.core.getAssemblyWithStringLocation("A4001").getType()
        self.assertEqual(
            shieldtype, "radial shield"
        )  # check that the right thing was added

        # one more test with an uneven number of rings
        converter.numFuelAssems = 8
        converter.convert(self.r)
        numAssems = len(self.r.core.getAssemblies())
        self.assertEqual(
            numAssems, 19
        )  # should wind up with 11 reflector assemblies per 1/3rd core

    def test_setNumberOfFuelAssems(self):
        r"""
        Tests that the setNumberOfFuelAssems method properly changes the number of fuel assemblies.
        """

        # tests ability to add fuel assemblies
        converter = geometryConverters.FuelAssemNumModifier(self.cs)
        converter.numFuelAssems = 60
        converter.convert(self.r)
        numFuelAssems = 0
        for assem in self.r.core.getAssemblies():
            if assem.hasFlags(Flags.FUEL):
                numFuelAssems += 1
        self.assertEqual(numFuelAssems, 60)

        # checks that existing fuel assemblies are preserved
        fueltype = self.r.core.getAssemblyWithStringLocation("A1001").getType()
        self.assertEqual(fueltype, "igniter fuel")

        # checks that existing control rods are preserved
        controltype = self.r.core.getAssemblyWithStringLocation("A5001").getType()
        self.assertEqual(controltype, "primary control")

        # checks that existing reflectors are overwritten with feed fuel
        oldshieldtype = self.r.core.getAssemblyWithStringLocation("A9005").getType()
        self.assertEqual(oldshieldtype, "feed fuel")

        # checks that outer assemblies are removed
        outerassem = self.r.core.getAssemblyWithStringLocation("A9001")
        self.assertEqual(outerassem, None)

        # tests ability to remove fuel assemblies
        converter.numFuelAssems = 20
        converter.convert(self.r)
        numFuelAssems = 0
        for assem in self.r.core.getAssemblies():
            if assem.hasFlags(Flags.FUEL):
                numFuelAssems += 1
        self.assertEqual(numFuelAssems, 20)


class TestHexToRZConverter(unittest.TestCase):
    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT)
        self.cs = settings.getMasterCs()
        runLog.setVerbosity("extra")
        self._expandReactor = False
        self._massScaleFactor = 1.0
        if not self._expandReactor:
            self._massScaleFactor = 3.0

    def tearDown(self):
        del self.o
        del self.cs
        del self.r

    def testConvert(self):
        converterSettings = {
            "radialConversionType": "Ring Compositions",
            "axialConversionType": "Axial Coordinates",
            "uniformThetaMesh": True,
            "thetaBins": 1,
            "axialMesh": [50, 100, 150, 175],
            "thetaMesh": [2 * math.pi],
            "hexRingGeometryConversion": False,
        }

        expectedMassDict, expectedNuclideList = self._getExpectedData()
        geomConv = geometryConverters.HexToRZConverter(
            self.cs, converterSettings, expandReactor=self._expandReactor
        )
        geomConv.convert(self.r)
        newR = geomConv.convReactor

        self._checkBlockComponents(newR)
        self._checkNuclidesMatch(expectedNuclideList, newR)
        self._checkNuclideMasses(expectedMassDict, newR)

    def _getExpectedData(self):
        """Retrieve the mass of all nuclides in the reactor prior to converting."""
        expectedMassDict = {}
        expectedNuclideList = self.r.blueprints.allNuclidesInProblem
        for nuclide in sorted(expectedNuclideList):
            expectedMassDict[nuclide] = self.r.core.getMass(nuclide)
        return expectedMassDict, expectedNuclideList

    def _checkBlockComponents(self, newR):
        for b in newR.core.getBlocks():
            if len(b) != 1:
                raise ValueError(
                    "Block {} has {} components and should only have 1".format(
                        b, len(b)
                    )
                )

    def _checkNuclidesMatch(self, expectedNuclideList, newR):
        """Check that the nuclide lists match before and after conversion"""
        actualNuclideList = newR.blueprints.allNuclidesInProblem
        if set(expectedNuclideList) != set(actualNuclideList):
            diffList = sorted(set(expectedNuclideList).difference(actualNuclideList))
            diffList += sorted(set(actualNuclideList).difference(expectedNuclideList))
            runLog.warning(diffList)
            raise ValueError(
                "{0} nuclides do not match between the original and converted reactor".format(
                    len(diffList)
                )
            )

    def _checkNuclideMasses(self, expectedMassDict, newR):
        """Check that all nuclide masses in the new reactor are equivalent to before the conversion"""
        massMismatchCount = 0
        for nuclide in expectedMassDict.keys():
            expectedMass = expectedMassDict[nuclide]
            actualMass = newR.core.getMass(nuclide) / self._massScaleFactor
            if round(abs(expectedMass - actualMass), 7) != 0.0:
                print(
                    "{:6s} {:10.2f} {:10.2f}".format(nuclide, expectedMass, actualMass)
                )
                massMismatchCount += 1

        # Raise error if there are any inconsistent masses
        if massMismatchCount > 0:
            raise ValueError(
                "{0} nuclides have masses that are not consistent after the conversion".format(
                    massMismatchCount
                )
            )

    def test_createHomogenizedRZTBlock(self):
        newBlock = blocks.ThRZBlock("testBlock", self.cs)
        a = self.r.core[0]
        converterSettings = {}
        geomConv = geometryConverters.HexToRZConverter(
            self.cs, converterSettings, expandReactor=self._expandReactor
        )
        volumeExpected = a.getVolume()
        (
            _atoms,
            _newBlockType,
            _newBlockTemp,
            newBlockVol,
        ) = geomConv.createHomogenizedRZTBlock(newBlock, 0, a.getHeight(), [a])

        # The volume of the radialZone and the radialThetaZone should be equal for RZ geometry
        self.assertAlmostEqual(volumeExpected, newBlockVol)


class TestEdgeAssemblyChanger(unittest.TestCase):
    def setUp(self):
        r"""
        Use the related setup in the testFuelHandlers module
        """
        self.o, self.r = loadTestReactor(TEST_ROOT)

    def tearDown(self):
        del self.o
        del self.r

    def test_edgeAssemblies(self):
        r"""
        Sanity check on adding edge assemblies.
        """
        converter = geometryConverters.EdgeAssemblyChanger()
        converter.addEdgeAssemblies(self.r.core)

        # must be added after geom transform
        for b in self.o.r.core.getBlocks():
            b.p.power = 1.0

        numAssems = len(self.r.core.getAssemblies())
        converter.scaleParamsRelatedToSymmetry(self.r)

        a = self.r.core.getAssembliesOnSymmetryLine(locations.BOUNDARY_0_DEGREES)[0]
        self.assertTrue(all(b.p.power == 2.0 for b in a), "Powers were not scaled")

        converter.removeEdgeAssemblies(self.r.core)
        self.assertTrue(numAssems > len(self.r.core.getAssemblies()))
        converter.addEdgeAssemblies(self.r.core)
        self.assertTrue(numAssems == len(self.r.core.getAssemblies()))
        # make sure it can be called twice.
        converter.addEdgeAssemblies(self.r.core)
        self.assertTrue(numAssems == len(self.r.core.getAssemblies()))


class TestThirdCoreHexToFullCoreChanger(unittest.TestCase):
    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT)

    def tearDown(self):
        del self.o
        del self.r

    def test_growToFullCoreFromThirdCore(self):
        """Test that a hex core can be converted from a third core to a full core geometry."""
        # Check the initialization of the third core model
        self.assertFalse(self.r.core.isFullCore)
        self.assertEqual(self.r.core.symmetry, geometry.THIRD_CORE + geometry.PERIODIC)
        initialNumBlocks = len(self.r.core.getBlocks())
        # Perform reactor conversion
        changer = geometryConverters.ThirdCoreHexToFullCoreChanger(self.o.cs)
        changer.convert(self.r)
        # Check the full core conversion is successful
        self.assertGreater(len(self.r.core.getBlocks()), initialNumBlocks)
        self.assertEqual(self.r.core.symmetry, geometry.FULL_CORE)
        # Check that the geometry can be restored to a third core
        changer.restorePreviousGeometry(self.o.cs, self.r)
        self.assertEqual(initialNumBlocks, len(self.r.core.getBlocks()))
        self.assertEqual(self.r.core.symmetry, geometry.THIRD_CORE + geometry.PERIODIC)

    def test_skipGrowToFullCoreWhenAlreadyFullCore(self):
        """Test that hex core is not modified when third core to full core changer is called on an already full core geometry."""
        # Check the initialization of the third core model and convert to a full core
        self.assertFalse(self.r.core.isFullCore)
        self.assertEqual(self.r.core.symmetry, geometry.THIRD_CORE + geometry.PERIODIC)
        changer = geometryConverters.ThirdCoreHexToFullCoreChanger(self.o.cs)
        changer.convert(self.r)
        # Check that the changer does not affect the full core model on converting and restoring
        initialNumBlocks = len(self.r.core.getBlocks())
        self.assertEqual(self.r.core.symmetry, geometry.FULL_CORE)
        changer = geometryConverters.ThirdCoreHexToFullCoreChanger(self.o.cs)
        changer.convert(self.r)
        self.assertEqual(self.r.core.symmetry, geometry.FULL_CORE)
        self.assertEqual(initialNumBlocks, len(self.r.core.getBlocks()))
        changer.restorePreviousGeometry(self.o.cs, self.r)
        self.assertEqual(initialNumBlocks, len(self.r.core.getBlocks()))
        self.assertEqual(self.r.core.symmetry, geometry.FULL_CORE)


if __name__ == "__main__":
    import sys
    import armi

    armi.configure()
    # sys.argv = ["", "TestEdgeAssemblyChanger"]
    unittest.main()
