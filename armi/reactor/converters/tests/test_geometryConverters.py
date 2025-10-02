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

from numpy.testing import assert_allclose

from armi import runLog
from armi.reactor import blocks, geometry, grids
from armi.reactor.converters import geometryConverters, uniformMesh
from armi.reactor.flags import Flags
from armi.testing import loadTestReactor, reduceTestReactorRings
from armi.tests import TEST_ROOT, mockRunLogs
from armi.utils import directoryChangers, plotting

THIS_DIR = os.path.dirname(__file__)


class TestGeometryConverters(unittest.TestCase):
    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT)
        self.cs = self.o.cs

    def test_addRing(self):
        """Tests that ``addRing`` adds the correct number of fuel assemblies to the test reactor."""
        converter = geometryConverters.FuelAssemNumModifier(self.cs)
        converter.numFuelAssems = 7
        converter.ringsToAdd = 1 * ["radial shield"]
        converter.convert(self.r)

        numAssems = len(self.r.core)
        self.assertEqual(numAssems, 13)  # should end up with 6 reflector assemblies per 1/3rd Core
        locator = self.r.core.spatialGrid.getLocatorFromRingAndPos(4, 1)
        shieldtype = self.r.core.childrenByLocator[locator].getType()
        self.assertEqual(shieldtype, "radial shield")  # check that the right thing was added

        # one more test with an uneven number of rings
        converter.numFuelAssems = 8
        converter.convert(self.r)
        numAssems = len(self.r.core)
        self.assertEqual(numAssems, 19)  # should wind up with 11 reflector assemblies per 1/3rd core

    def test_setNumberOfFuelAssems(self):
        """Tests that ``setNumberOfFuelAssems`` properly changes the number of fuel assemblies."""
        # tests ability to add fuel assemblies
        converter = geometryConverters.FuelAssemNumModifier(self.cs)
        converter.numFuelAssems = 60
        converter.convert(self.r)
        numFuelAssems = 0
        for assem in self.r.core:
            if assem.hasFlags(Flags.FUEL):
                numFuelAssems += 1
        self.assertEqual(numFuelAssems, 60)

        # checks that existing fuel assemblies are preserved
        locator = self.r.core.spatialGrid.getLocatorFromRingAndPos(1, 1)
        fueltype = self.r.core.childrenByLocator[locator].getType()
        self.assertEqual(fueltype, "igniter fuel")

        # checks that existing control rods are preserved
        locator = self.r.core.spatialGrid.getLocatorFromRingAndPos(5, 1)
        controltype = self.r.core.childrenByLocator[locator].getType()
        self.assertEqual(controltype, "primary control")

        # checks that existing reflectors are overwritten with feed fuel
        locator = self.r.core.spatialGrid.getLocatorFromRingAndPos(9, 5)
        oldshieldtype = self.r.core.childrenByLocator[locator].getType()
        self.assertEqual(oldshieldtype, "feed fuel")

        # checks that outer assemblies are removed
        locator = self.r.core.spatialGrid.getLocatorFromRingAndPos(9, 1)
        with self.assertRaises(KeyError):
            _ = self.r.core.childrenByLocator[locator]

        # tests ability to remove fuel assemblies
        converter.numFuelAssems = 20
        converter.convert(self.r)
        numFuelAssems = 0
        for assem in self.r.core:
            if assem.hasFlags(Flags.FUEL):
                numFuelAssems += 1
        self.assertEqual(numFuelAssems, 20)

    def test_getAssembliesInSector(self):
        allAssems = self.r.core.getAssemblies()
        fullSector = geometryConverters.HexToRZConverter._getAssembliesInSector(self.r.core, 0, 360)
        self.assertGreaterEqual(len(fullSector), len(allAssems))  # could be > due to edge assems
        third = geometryConverters.HexToRZConverter._getAssembliesInSector(self.r.core, 0, 30)
        # could solve this analytically based on test core size
        self.assertAlmostEqual(25, len(third))
        oneLine = geometryConverters.HexToRZConverter._getAssembliesInSector(self.r.core, 0, 0.001)
        self.assertAlmostEqual(5, len(oneLine))  # same here


class TestHexToRZConverter(unittest.TestCase):
    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT)
        reduceTestReactorRings(self.r, self.o.cs, 2)
        self.cs = self.o.cs

        runLog.setVerbosity("extra")
        self._expandReactor = False
        self._massScaleFactor = 1.0
        if not self._expandReactor:
            self._massScaleFactor = 3.0

    def tearDown(self):
        del self.o
        del self.cs
        del self.r

    def test_convert(self):
        """Test HexToRZConverter.convert().

        Notes
        -----
        Ensure the converted reactor has 1) nuclides and nuclide masses that match the
        original reactor, 2) for a given (r,z,theta) location the expected block type exists,
        3) the converted reactor has the right (r,z,theta) coordinates, and 4) the converted
        reactor blocks all have a single (homogenized) component.

        .. test:: Convert a 3D hex reactor core to an RZ-Theta core.
            :id: T_ARMI_CONV_3DHEX_TO_2DRZ
            :tests: R_ARMI_CONV_3DHEX_TO_2DRZ
        """
        # make the reactor smaller, because of a test parallelization edge case
        for ring in [9, 8, 7, 6, 5, 4, 3]:
            self.r.core.removeAssembliesInRing(ring, self.o.cs)

        converterSettings = {
            "radialConversionType": "Ring Compositions",
            "axialConversionType": "Axial Coordinates",
            "uniformThetaMesh": True,
            "thetaBins": 1,
            "axialMesh": [25, 50, 75, 100, 150, 175],
            "thetaMesh": [2 * math.pi],
        }

        expectedMassDict, expectedNuclideList = self._getExpectedData()
        geomConv = geometryConverters.HexToRZConverter(self.cs, converterSettings, expandReactor=self._expandReactor)
        geomConv.convert(self.r)
        newR = geomConv.convReactor

        self._checkBlockComponents(newR)
        self._checkNuclidesMatch(expectedNuclideList, newR)
        self._checkNuclideMasses(expectedMassDict, newR)
        self._checkBlockAtMeshPoint(geomConv)
        self._checkReactorMeshCoordinates(geomConv)
        _figs = geomConv.plotConvertedReactor()
        with directoryChangers.TemporaryDirectoryChanger():
            geomConv.plotConvertedReactor("fname")

        # bonus test: reset() works after converter has filled in values
        geomConv.reset()
        self.assertIsNone(geomConv.convReactor)
        self.assertIsNone(geomConv._radialMeshConversionType)
        self.assertIsNone(geomConv._axialMeshConversionType)
        self.assertIsNone(geomConv._currentRadialZoneType)
        self.assertEqual(geomConv._newBlockNum, 0)

    def _checkBlockAtMeshPoint(self, geomConv):
        b = plotting._getBlockAtMeshPoint(geomConv.convReactor, 0.0, 2.0 * math.pi, 0.0, 12.0, 50.0, 75.0)
        self.assertTrue(b.hasFlags(Flags.FUEL))

    def _checkReactorMeshCoordinates(self, geomConv):
        thetaMesh, radialMesh, axialMesh = plotting._getReactorMeshCoordinates(geomConv.convReactor)
        expectedThetaMesh = [math.pi * 2.0]
        expectedAxialMesh = [25.0, 50.0, 75.0, 100.0, 150.0, 175.0]
        expectedRadialMesh = [
            8.794379,
            23.26774,
        ]
        assert_allclose(expectedThetaMesh, thetaMesh)
        assert_allclose(expectedRadialMesh, radialMesh)
        assert_allclose(expectedAxialMesh, axialMesh)

    def _getExpectedData(self):
        """Retrieve the mass of all nuclides in the reactor prior to converting."""
        expectedMassDict = {}
        expectedNuclideList = self.r.blueprints.allNuclidesInProblem
        for nuclide in sorted(expectedNuclideList):
            expectedMassDict[nuclide] = self.r.core.getMass(nuclide)
        return expectedMassDict, expectedNuclideList

    def _checkBlockComponents(self, newR):
        for b in newR.core.iterBlocks():
            if len(b) != 1:
                raise ValueError("Block {} has {} components and should only have 1".format(b, len(b)))

    def _checkNuclidesMatch(self, expectedNuclideList, newR):
        """Check that the nuclide lists match before and after conversion."""
        actualNuclideList = newR.blueprints.allNuclidesInProblem
        if set(expectedNuclideList) != set(actualNuclideList):
            diffList = sorted(set(expectedNuclideList).difference(actualNuclideList))
            diffList += sorted(set(actualNuclideList).difference(expectedNuclideList))
            runLog.warning(diffList)
            raise ValueError(
                "{0} nuclides do not match between the original and converted reactor".format(len(diffList))
            )

    def _checkNuclideMasses(self, expectedMassDict, newR):
        """Check that all nuclide masses in the new reactor are equivalent to before the conversion."""
        massMismatchCount = 0
        for nuclide in expectedMassDict.keys():
            expectedMass = expectedMassDict[nuclide]
            actualMass = newR.core.getMass(nuclide) / self._massScaleFactor
            if round(abs(expectedMass - actualMass), 7) != 0.0:
                print("{:6s} {:10.2f} {:10.2f}".format(nuclide, expectedMass, actualMass))
                massMismatchCount += 1

        # Raise error if there are any inconsistent masses
        if massMismatchCount > 0:
            raise ValueError(
                "{0} nuclides have masses that are not consistent after the conversion".format(massMismatchCount)
            )

    def test_createHomogenizedRZTBlock(self):
        newBlock = blocks.ThRZBlock("testBlock", self.cs)
        a = self.r.core[0]
        converterSettings = {}
        geomConv = geometryConverters.HexToRZConverter(self.cs, converterSettings, expandReactor=self._expandReactor)
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
        """Use the related setup in the testFuelHandlers module."""
        self.o, self.r = loadTestReactor(TEST_ROOT)
        reduceTestReactorRings(self.r, self.o.cs, 3)

    def tearDown(self):
        del self.o
        del self.r

    def test_edgeAssemblies(self):
        """Sanity check on adding edge assemblies.

        .. test:: Test adding/removing assemblies from a reactor.
            :id: T_ARMI_ADD_EDGE_ASSEMS
            :tests: R_ARMI_ADD_EDGE_ASSEMS
        """

        def getAssemByRingPos(ringPos: tuple):
            for a in self.r.core:
                if a.spatialLocator.getRingPos() == ringPos:
                    return a
            return None

        numAssemsOrig = len(self.r.core)
        # assert that there is no assembly in the (3, 4) (ring, position).
        self.assertIsNone(getAssemByRingPos((3, 4)))
        # add the assembly
        converter = geometryConverters.EdgeAssemblyChanger()
        converter.addEdgeAssemblies(self.r.core)
        numAssemsWithEdgeAssem = len(self.r.core)
        # assert that there is an assembly in the (3, 4) (ring, position).
        self.assertIsNotNone(getAssemByRingPos((3, 4)))
        self.assertTrue(numAssemsWithEdgeAssem > numAssemsOrig)

        # try to add the assembly again (you can't)
        with mockRunLogs.BufferLog() as mock:
            converter.addEdgeAssemblies(self.r.core)
            self.assertIn("Skipping addition of edge assemblies", mock.getStdout())
            self.assertTrue(numAssemsWithEdgeAssem, len(self.r.core))

        # must be added after geom transform
        for b in self.o.r.core.iterBlocks():
            b.p.power = 1.0
        converter.scaleParamsRelatedToSymmetry(self.r.core)
        a = self.r.core.getAssembliesOnSymmetryLine(grids.BOUNDARY_0_DEGREES)[0]
        self.assertTrue(all(b.p.power == 2.0 for b in a), "Powers were not scaled")

        # remove the assembly that was added
        converter.removeEdgeAssemblies(self.r.core)
        self.assertIsNone(getAssemByRingPos((3, 4)))
        self.assertEqual(numAssemsOrig, len(self.r.core))


class TestThirdCoreHexToFullCoreChanger(unittest.TestCase):
    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT)
        reduceTestReactorRings(self.r, self.o.cs, 3)

        # initialize the block powers to a uniform power profile, accounting for
        # the loaded reactor being 1/3 core
        numBlocksInFullCore = 0
        for a in self.r.core:
            if a.getLocation() == "001-001":
                for b in a:
                    numBlocksInFullCore += 1
            else:
                for b in a:
                    # account for the 1/3 symmetry
                    numBlocksInFullCore += 3
        for a in self.r.core:
            if a.getLocation() == "001-001":
                for b in a:
                    b.p["power"] = self.o.cs["power"] / numBlocksInFullCore / 3
            else:
                for b in a:
                    b.p["power"] = self.o.cs["power"] / numBlocksInFullCore

    def tearDown(self):
        del self.o
        del self.r

    def test_growToFullCoreFromThirdCore(self):
        """Test that a hex core can be converted from a third core to a full core geometry.

        .. test:: Convert a third-core to a full-core geometry and then restore it.
            :id: T_ARMI_THIRD_TO_FULL_CORE0
            :tests: R_ARMI_THIRD_TO_FULL_CORE
        """

        def getLTAAssems():
            aList = []
            for a in self.r.core:
                if a.getType == "lta fuel":
                    aList.append(a)
            return aList

        # Check the initialization of the third core model
        self.assertFalse(self.r.core.isFullCore)
        self.assertEqual(
            self.r.core.symmetry,
            geometry.SymmetryType(geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC),
        )
        initialNumBlocks = len(self.r.core.getBlocks())
        assems = getLTAAssems()
        expectedLoc = [(3, 2)]
        for i, a in enumerate(assems):
            self.assertEqual(a.spatialLocator.getRingPos(), expectedLoc[i])
        self.assertAlmostEqual(self.r.core.getTotalBlockParam("power"), self.o.cs["power"] / 3, places=5)
        self.assertGreater(
            self.r.core.getTotalBlockParam("power", calcBasedOnFullObj=True),
            self.o.cs["power"] / 3,
        )

        # Perform reactor conversion
        changer = geometryConverters.ThirdCoreHexToFullCoreChanger(self.o.cs)
        changer.convert(self.r)

        # Check the full core conversion is successful
        self.assertTrue(self.r.core.isFullCore)
        self.assertGreater(len(self.r.core.getBlocks()), initialNumBlocks)
        self.assertEqual(self.r.core.symmetry.domain, geometry.DomainType.FULL_CORE)
        assems = getLTAAssems()
        expectedLoc = [(3, 2), (3, 6), (3, 10)]
        for i, a in enumerate(assems):
            self.assertEqual(a.spatialLocator.getRingPos(), expectedLoc[i])

        # ensure that block power is handled correctly
        self.assertAlmostEqual(self.r.core.getTotalBlockParam("power"), self.o.cs["power"], places=5)
        self.assertAlmostEqual(
            self.r.core.getTotalBlockParam("power", calcBasedOnFullObj=True),
            self.o.cs["power"],
            places=5,
        )

        # Check that the geometry can be restored to a third core
        changer.restorePreviousGeometry(self.r)
        self.assertEqual(initialNumBlocks, len(self.r.core.getBlocks()))
        self.assertEqual(
            self.r.core.symmetry,
            geometry.SymmetryType(geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC),
        )
        self.assertFalse(self.r.core.isFullCore)
        self.assertAlmostEqual(self.r.core.getTotalBlockParam("power"), self.o.cs["power"] / 3, places=5)
        assems = getLTAAssems()
        expectedLoc = [(3, 2)]
        for i, a in enumerate(assems):
            self.assertEqual(a.spatialLocator.getRingPos(), expectedLoc[i])

    def test_initNewFullReactor(self):
        """Test that initNewReactor will growToFullCore if necessary."""
        # Perform reactor conversion
        changer = geometryConverters.ThirdCoreHexToFullCoreChanger(self.o.cs)
        changer.convert(self.r)

        converter = uniformMesh.NeutronicsUniformMeshConverter(self.o.cs)
        newR = converter.initNewReactor(self.r, self.o.cs)

        # Check the full core conversion is successful
        self.assertTrue(self.r.core.isFullCore)
        self.assertTrue(newR.core.isFullCore)
        self.assertEqual(newR.core.symmetry.domain, geometry.DomainType.FULL_CORE)

    def test_skipGrowToFullCoreWhenAlreadyFullCore(self):
        """Test that hex core is not modified when third core to full core changer is called on an
        already full core geometry.

        .. test: Convert a one-third core to full core and restore back to one-third core.
            :id: T_ARMI_THIRD_TO_FULL_CORE2
            :tests: R_ARMI_THIRD_TO_FULL_CORE
        """
        # Check the initialization of the third core model and convert to a full core
        self.assertFalse(self.r.core.isFullCore)
        self.assertEqual(
            self.r.core.symmetry,
            geometry.SymmetryType(geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC),
        )
        numBlocksThirdCore = len(self.r.core.getBlocks())
        # convert the third core to full core
        changer = geometryConverters.ThirdCoreHexToFullCoreChanger(self.o.cs)
        with mockRunLogs.BufferLog() as mock:
            changer.convert(self.r)
            self.assertIn("Expanding to full core geometry", mock.getStdout())
        numBlocksFullCore = len(self.r.core.getBlocks())
        self.assertEqual(self.r.core.symmetry.domain, geometry.DomainType.FULL_CORE)
        # try to convert to full core again (it shouldn't do anything)
        with mockRunLogs.BufferLog() as mock:
            changer.convert(self.r)
            self.assertIn(
                "Detected that full core reactor already exists. Cannot expand.",
                mock.getStdout(),
            )
        self.assertEqual(self.r.core.symmetry.domain, geometry.DomainType.FULL_CORE)
        self.assertEqual(numBlocksFullCore, len(self.r.core.getBlocks()))
        # restore back to 1/3 core
        with mockRunLogs.BufferLog() as mock:
            changer.restorePreviousGeometry(self.r)
            self.assertIn("revert from full to 1/3 core", mock.getStdout())
        self.assertEqual(numBlocksThirdCore, len(self.r.core.getBlocks()))
        self.assertEqual(
            self.r.core.symmetry,
            geometry.SymmetryType(geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC),
        )
