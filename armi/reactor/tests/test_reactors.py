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
"""Testing for reactors.py."""

import copy
import logging
import os
import pickle
import unittest
from math import sqrt
from unittest.mock import patch

from numpy.testing import assert_allclose, assert_equal

from armi import operators, runLog, settings, tests
from armi.materials import uZr
from armi.physics.neutronics.settings import CONF_XS_KERNEL
from armi.reactor import assemblies, blocks, geometry, grids, reactors
from armi.reactor.components import Hexagon, Rectangle
from armi.reactor.composites import Composite
from armi.reactor.converters import geometryConverters
from armi.reactor.converters.axialExpansionChanger import AxialExpansionChanger
from armi.reactor.flags import Flags
from armi.reactor.spentFuelPool import SpentFuelPool
from armi.settings.fwSettings.globalSettings import (
    CONF_ASSEM_FLAGS_SKIP_AXIAL_EXP,
    CONF_SORT_REACTOR,
)
from armi.testing import loadTestReactor, reduceTestReactorRings  # noqa: F401
from armi.tests import TEST_ROOT, mockRunLogs
from armi.utils import directoryChangers

_THIS_DIR = os.path.dirname(__file__)


def buildOperatorOfEmptyHexBlocks(customSettings=None):
    """
    Builds a operator w/ a reactor object with some hex assemblies and blocks, but all are empty.

    Doesn't depend on inputs and loads quickly.

    Parameters
    ----------
    customSettings : dict
        Dictionary of off-default settings to update
    """
    cs = settings.Settings()  # fetch new
    if customSettings is None:
        customSettings = {}

    customSettings["db"] = False  # stop use of database
    cs = cs.modified(newSettings=customSettings)

    r = tests.getEmptyHexReactor()
    r.core.setOptionsFromCs(cs)
    o = operators.Operator(cs)
    o.initializeInterfaces(r)

    a = assemblies.HexAssembly("fuel")
    a.spatialGrid = grids.AxialGrid.fromNCells(1)
    b = blocks.HexBlock("TestBlock")
    b.setType("fuel")
    dims = {"Tinput": 600, "Thot": 600, "op": 16.0, "ip": 1, "mult": 1}
    c = Hexagon("fuel", uZr.UZr(), **dims)
    b.add(c)
    a.add(b)
    a.spatialLocator = r.core.spatialGrid[1, 0, 0]
    o.r.core.add(a)
    o.r.sort()
    return o


def buildOperatorOfEmptyCartesianBlocks(customSettings=None):
    """
    Builds a operator w/ a reactor object with some Cartesian assemblies and blocks, but all are empty.

    Doesn't depend on inputs and loads quickly.

    Parameters
    ----------
    customSettings : dict
        Off-default settings to update
    """
    cs = settings.Settings()  # fetch new
    if customSettings is None:
        customSettings = {}

    customSettings["db"] = False  # stop use of database
    cs = cs.modified(newSettings=customSettings)

    r = tests.getEmptyCartesianReactor()
    r.core.setOptionsFromCs(cs)
    o = operators.Operator(cs)
    o.initializeInterfaces(r)

    a = assemblies.CartesianAssembly("fuel")
    a.spatialGrid = grids.AxialGrid.fromNCells(1)
    b = blocks.CartesianBlock("TestBlock")
    b.setType("fuel")
    dims = {
        "Tinput": 600,
        "Thot": 600,
        "widthOuter": 16.0,
        "lengthOuter": 10.0,
        "widthInner": 1,
        "lengthInner": 1,
        "mult": 1,
    }
    c = Rectangle("fuel", uZr.UZr(), **dims)
    b.add(c)
    a.add(b)
    a.spatialLocator = r.core.spatialGrid[1, 0, 0]
    o.r.core.add(a)
    o.r.sort()
    return o


class ReactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # prepare the input files. This is important so the unit tests run from wherever
        # they need to run from.
        cls.directoryChanger = directoryChangers.DirectoryChanger(TEST_ROOT)
        cls.directoryChanger.open()

    @classmethod
    def tearDownClass(cls):
        cls.directoryChanger.close()


class HexReactorTests(ReactorTests):
    def setUp(self):
        self.o, self.r = loadTestReactor(self.directoryChanger.destination, customSettings={"trackAssems": True})

    def test_coreSfp(self):
        """The reactor object includes a core and an SFP.

        .. test:: The reactor object is a composite.
            :id: T_ARMI_R
            :tests: R_ARMI_R
        """
        self.assertTrue(isinstance(self.r.core, reactors.Core))
        self.assertTrue(isinstance(self.r.excore["sfp"], SpentFuelPool))

        self.assertTrue(isinstance(self.r, Composite))
        self.assertTrue(isinstance(self.r.core, Composite))
        self.assertTrue(isinstance(self.r.excore["sfp"], Composite))

    def test_factorySortSetting(self):
        """Create a core object from an input yaml."""
        # get a sorted Reactor (the default)
        cs = settings.Settings(fName="armiRun.yaml")
        r0 = reactors.loadFromCs(cs)

        # get an unsorted Reactor (for whatever reason)
        customSettings = {CONF_SORT_REACTOR: False}
        cs = cs.modified(newSettings=customSettings)
        r1 = reactors.loadFromCs(cs)

        # the reactor / core should be the same size
        self.assertEqual(len(r0), len(r1))
        self.assertEqual(len(r0.core), len(r1.core))

        # the reactor / core should be in a different order
        a0 = [a.name for a in r0.core]
        a1 = [a.name for a in r1.core]
        self.assertNotEqual(a0, a1)

        # The reactor object is a Composite
        self.assertTrue(isinstance(r0.core, Composite))

    def test_getSetParameters(self):
        """
        This test works through multiple levels of the hierarchy to test ability to
        modify parameters at different levels.

        .. test:: Parameters are accessible throughout the armi tree.
            :id: T_ARMI_PARAM1
            :tests: R_ARMI_PARAM

        .. test:: Ensure there is a setting for total core power.
            :id: T_ARMI_SETTINGS_POWER0
            :tests: R_ARMI_SETTINGS_POWER
        """
        # Test at reactor level
        self.assertEqual(self.r.p.cycle, 0)
        self.assertEqual(self.r.p.availabilityFactor, 1.0)

        # Test at core level
        core = self.r.core
        self.assertGreater(core.p.power, -1)

        core.p.power = 123
        self.assertEqual(core.p.power, 123)

        # Test at assembly level
        assembly = core.getFirstAssembly()
        self.assertGreater(assembly.p.crRodLength, -1)

        assembly.p.crRodLength = 234
        self.assertEqual(assembly.p.crRodLength, 234)

        # Test at block level
        block = core.getFirstBlock()
        self.assertGreater(block.p.THTfuelCL, -1)

        block.p.THTfuelCL = 57
        self.assertEqual(block.p.THTfuelCL, 57)

        # Test at component level
        component = block[0]
        self.assertEqual(component.p.temperatureInC, 450.0)

    def test_sortChildren(self):
        self.assertEqual(next(self.r.core.__iter__()), self.r.core[0])
        self.assertEqual(self.r.core._children, sorted(self.r.core._children))

    def test_sortAssemByRing(self):
        """Demonstrate ring/pos sorting."""
        self.r.core.sortAssemsByRing()
        self.assertEqual((1, 1), self.r.core[0].spatialLocator.getRingPos())
        currentRing = -1
        currentPos = -1
        for a in self.r.core:
            ring, pos = a.spatialLocator.getRingPos()
            self.assertGreaterEqual(ring, currentRing)
            if ring > currentRing:
                ring = currentRing
                currentPos = -1
            self.assertGreater(pos, currentPos)
            currentPos = pos

    def test_getTotalParam(self):
        # verify that the block params are being read.
        val = self.r.core.getTotalBlockParam("power")
        val2 = self.r.core.getTotalBlockParam("power", addSymmetricPositions=True)
        self.assertEqual(val2 / self.r.core.powerMultiplier, val)

        with self.assertRaises(ValueError):
            self.r.core.getTotalBlockParam(generationNum=1)

    def test_geomType(self):
        self.assertEqual(self.r.core.geomType, geometry.GeomType.HEX)

    def test_growToFullCore(self):
        nAssemThird = len(self.r.core)
        self.assertEqual(self.r.core.powerMultiplier, 3.0)
        self.assertFalse(self.r.core.isFullCore)
        self.r.core.growToFullCore(self.o.cs)
        aNums = []
        for a in self.r.core:
            self.assertNotIn(a.getNum(), aNums)
            aNums.append(a.getNum())

        bNames = [b.getName() for b in self.r.core.iterBlocks()]
        for bName in bNames:
            self.assertEqual(bNames.count(bName), 1)
        self.assertEqual(self.r.core.powerMultiplier, 1.0)
        self.assertTrue(self.r.core.isFullCore)
        nAssemFull = len(self.r.core)
        self.assertEqual(nAssemFull, (nAssemThird - 1) * 3 + 1)

    def test_getBlocksByIndices(self):
        indices = [(1, 1, 1), (3, 2, 2)]
        actualBlocks = self.r.core.getBlocksByIndices(indices)
        actualNames = [b.getName() for b in actualBlocks]
        expectedNames = ["B0014-001", "B0035-002"]
        self.assertListEqual(expectedNames, actualNames)

    def test_getAllXsSuffixes(self):
        actualSuffixes = self.r.core.getAllXsSuffixes()
        expectedSuffixes = ["AA"]
        self.assertListEqual(expectedSuffixes, actualSuffixes)

    def test_genBlocksByLocName(self):
        self.r.core.genBlocksByLocName()
        self.assertGreater(len(self.r.core.blocksByLocName), 300)
        self.assertIn("009-009-004", self.r.core.blocksByLocName)

    def test_setPitchUniform(self):
        self.r.core.setPitchUniform(0.0)
        for b in self.r.core.iterBlocks():
            self.assertEqual(b.getPitch(), 0.0)

    def test_countBlocksOfType(self):
        numControlBlocks = self.r.core.countBlocksWithFlags([Flags.DUCT, Flags.CONTROL])

        self.assertEqual(numControlBlocks, 3)

        numControlBlocks = self.r.core.countBlocksWithFlags([Flags.DUCT, Flags.CONTROL, Flags.FUEL], Flags.CONTROL)
        self.assertEqual(numControlBlocks, 3)

    def test_normalizeNames(self):
        # these are the correct, normalized names
        numAssems = 73
        a = self.r.core.getFirstAssembly()
        correctNames = [a.makeNameFromAssemNum(n) for n in range(numAssems)]

        # validate the reactor is what we think now
        self.assertEqual(len(self.r.core), numAssems)
        currentNames = [a.getName() for a in self.r.core]
        self.assertNotEqual(correctNames, currentNames)

        # validate that we can normalize the names correctly once
        self.r.normalizeNames()
        currentNames = [a.getName() for a in self.r.core]
        self.assertEqual(correctNames, currentNames)

        # validate that repeated applications of this method are stable
        for _ in range(3):
            self.r.normalizeNames()
            currentNames = [a.getName() for a in self.r.core]
            self.assertEqual(correctNames, currentNames)

    def test_setB10VolOnCreation(self):
        """Test the setting of b.p.initialB10ComponentVol."""
        for controlBlock in self.r.core.iterBlocks(Flags.CONTROL):
            controlComps = [c for c in controlBlock if c.getNumberDensity("B10") > 0]
            self.assertEqual(len(controlComps), 1)
            controlComp = controlComps[0]

            startingVol = controlBlock.p.initialB10ComponentVol
            self.assertGreater(startingVol, 0)
            self.assertAlmostEqual(controlComp.getArea(cold=True) * controlBlock.getHeight(), startingVol)

            # input temp is same as hot temp, so change input temp to test that behavior
            controlComp.inputTemperatureInC = 30

            # somewhat non-sensical since its hot, not cold but we just want to check the ratio
            controlBlock.setB10VolParam(True)

            self.assertGreater(startingVol, controlBlock.p.initialB10ComponentVol)

            self.assertAlmostEqual(
                startingVol / controlComp.getThermalExpansionFactor(),
                controlBlock.p.initialB10ComponentVol,
            )

    def test_countFuelAxialBlocks(self):
        """Tests that the users definition of fuel blocks is preserved."""
        numFuelBlocks = self.r.core.countFuelAxialBlocks()
        self.assertEqual(numFuelBlocks, 3)

    def test_getFirstFuelBlockAxialNode(self):
        firstFuelBlock = self.r.core.getFirstFuelBlockAxialNode()
        self.assertEqual(firstFuelBlock, 1)

    def test_getMaxAssembliesInHexRing(self):
        maxAssems = self.r.core.getMaxAssembliesInHexRing(3)
        self.assertEqual(maxAssems, 4)

    def test_getMaxNumPins(self):
        numPins = self.r.core.getMaxNumPins()
        self.assertEqual(169, numPins)

    def test_addMultipleCores(self):
        """Test the catch that a reactor can only have one core."""
        with self.assertRaises(RuntimeError):
            self.r.add(self.r.core)

    def test_getReactor(self):
        """The Core object can return its Reactor parent; test that getter."""
        self.assertTrue(isinstance(self.r.core.r, reactors.Reactor))

        self.r.core.parent = None
        self.assertIsNone(self.r.core.r)

    def test_addMoreNodes(self):
        originalMesh = self.r.core.p.axialMesh
        bigMesh = list(originalMesh)
        bigMesh[2] = 30.0
        smallMesh = originalMesh[0:2] + [40.0, 47.0] + originalMesh[2:]
        newMesh1, originalMeshGood = self.r.core.addMoreNodes(originalMesh)
        newMesh2, bigMeshGood = self.r.core.addMoreNodes(bigMesh)
        newMesh3, smallMeshGood = self.r.core.addMoreNodes(smallMesh)
        expectedMesh = [0.0, 25.0, 50.0, 75.0, 100.0, 118.75, 137.5, 156.25, 175.0]
        expectedBigMesh = [
            0.0,
            25.0,
            30.0,
            36.75,
            75.0,
            100.0,
            118.75,
            137.5,
            156.25,
            175.0,
        ]
        expectedSmallMesh = [
            0.0,
            25.0,
            40.0,
            47.0,
            50.0,
            53.75,
            75.0,
            100.0,
            118.75,
            137.5,
            156.25,
            175.0,
        ]
        self.assertListEqual(expectedMesh, newMesh1)
        self.assertListEqual(expectedBigMesh, newMesh2)
        self.assertListEqual(expectedSmallMesh, newMesh3)
        self.assertTrue(originalMeshGood)
        self.assertFalse(bigMeshGood)
        self.assertFalse(smallMeshGood)

    def test_findAxialMeshIndexOf(self):
        numMeshPoints = len(self.r.core.p.axialMesh) - 2  # -1 for typical reason, -1 more because mesh includes 0
        self.assertEqual(self.r.core.findAxialMeshIndexOf(0.0), 0)
        self.assertEqual(self.r.core.findAxialMeshIndexOf(0.1), 0)
        self.assertEqual(self.r.core.findAxialMeshIndexOf(self.r.core[0].getHeight()), numMeshPoints)
        self.assertEqual(
            self.r.core.findAxialMeshIndexOf(self.r.core[0].getHeight() - 0.1),
            numMeshPoints,
        )
        self.assertEqual(self.r.core.findAxialMeshIndexOf(self.r.core[0][0].getHeight() + 0.1), 1)

    def test_findAllAxialMeshPoints(self):
        mesh = self.r.core.findAllAxialMeshPoints(applySubMesh=False)

        self.assertEqual(mesh[0], 0)
        self.assertAlmostEqual(mesh[-1], self.r.core[0].getHeight())

        blockMesh = self.r.core.getFirstAssembly(Flags.FUEL).spatialGrid._bounds[2]
        assert_allclose(blockMesh, mesh)

    def test_findAllAxialMeshPoints_wSubmesh(self):
        referenceMesh = [0.0, 25.0, 50.0, 75.0, 100.0, 118.75, 137.5, 156.25, 175.0]
        mesh = self.r.core.findAllAxialMeshPoints(assems=[self.r.core.getFirstAssembly(Flags.FUEL)], applySubMesh=True)
        self.assertListEqual(referenceMesh, mesh)

    def test_findAllAziMeshPoints(self):
        aziPoints = self.r.core.findAllAziMeshPoints()
        expectedPoints = [
            -50.7707392969,
            -36.2648137835,
            -21.7588882701,
            -7.2529627567,
            7.2529627567,
            21.7588882701,
            36.2648137835,
            50.7707392969,
            65.2766648103,
            79.7825903236,
            94.288515837,
            108.7944413504,
            123.3003668638,
        ]
        assert_allclose(expectedPoints, aziPoints)

    def test_findAllRadMeshPoints(self):
        radPoints = self.r.core.findAllRadMeshPoints()
        expectedPoints = [
            -12.5625,
            -4.1875,
            4.1875,
            12.5625,
            20.9375,
            29.3125,
            37.6875,
            46.0625,
            54.4375,
            62.8125,
            71.1875,
            79.5625,
            87.9375,
            96.3125,
            104.6875,
            113.0625,
            121.4375,
            129.8125,
            138.1875,
            146.5625,
        ]
        assert_allclose(expectedPoints, radPoints)

    def test_findNeighbors(self):
        """
        Find neighbors of a given assembly.

        .. test:: Retrieve neighboring assemblies of a given assembly.
            :id: T_ARMI_R_FIND_NEIGHBORS
            :tests: R_ARMI_R_FIND_NEIGHBORS
        """
        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(1, 1)
        a = self.r.core.childrenByLocator[loc]
        neighbs = self.r.core.findNeighbors(a, duplicateAssembliesOnReflectiveBoundary=True)
        locs = [a.spatialLocator.getRingPos() for a in neighbs]
        self.assertEqual(len(neighbs), 6)
        self.assertIn((2, 1), locs)
        self.assertIn((2, 2), locs)
        self.assertEqual(locs.count((2, 1)), 3)

        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(1, 1)
        a = self.r.core.childrenByLocator[loc]
        neighbs = self.r.core.findNeighbors(a, duplicateAssembliesOnReflectiveBoundary=True)
        locs = [a.spatialLocator.getRingPos() for a in neighbs]
        self.assertEqual(locs, [(2, 1), (2, 2)] * 3, 6)

        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(2, 2)
        a = self.r.core.childrenByLocator[loc]

        neighbs = self.r.core.findNeighbors(a, duplicateAssembliesOnReflectiveBoundary=True)
        locs = [a.spatialLocator.getRingPos() for a in neighbs]
        self.assertEqual(len(neighbs), 6)
        self.assertEqual(locs, [(3, 2), (3, 3), (3, 12), (2, 1), (1, 1), (2, 1)])

        # try with edge assemblies
        # With edges, the neighbor is the one that's actually next to it.
        converter = geometryConverters.EdgeAssemblyChanger()
        converter.addEdgeAssemblies(self.r.core)
        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(2, 2)
        a = self.r.core.childrenByLocator[loc]
        neighbs = self.r.core.findNeighbors(a, duplicateAssembliesOnReflectiveBoundary=True)
        locs = [a.spatialLocator.getRingPos() for a in neighbs]
        self.assertEqual(len(neighbs), 6)
        # in this case no locations that aren't actually in the core should be returned
        self.assertEqual(locs, [(3, 2), (3, 3), (3, 4), (2, 1), (1, 1), (2, 1)])
        converter.removeEdgeAssemblies(self.r.core)

        # try with full core
        self.r.core.growToFullCore(self.o.cs)
        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(3, 4)
        a = self.r.core.childrenByLocator[loc]
        neighbs = self.r.core.findNeighbors(a)
        self.assertEqual(len(neighbs), 6)
        locs = [a.spatialLocator.getRingPos() for a in neighbs]
        for loc in [(2, 2), (2, 3), (3, 3), (3, 5), (4, 5), (4, 6)]:
            self.assertIn(loc, locs)

        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(2, 2)
        a = self.r.core.childrenByLocator[loc]
        neighbs = self.r.core.findNeighbors(a)
        locs = [a.spatialLocator.getRingPos() for a in neighbs]
        for loc in [(1, 1), (2, 1), (2, 3), (3, 2), (3, 3), (3, 4)]:
            self.assertIn(loc, locs)

        # Try the duplicate option in full core as well
        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(2, 2)
        a = self.r.core.childrenByLocator[loc]
        neighbs = self.r.core.findNeighbors(a, duplicateAssembliesOnReflectiveBoundary=True)
        locs = [a.spatialLocator.getRingPos() for a in neighbs]
        self.assertEqual(len(neighbs), 6)
        self.assertEqual(locs, [(3, 2), (3, 3), (3, 4), (2, 3), (1, 1), (2, 1)])

    def test_getAssembliesInCircularRing(self):
        expectedAssemsInRing = [5, 6, 8, 10, 12, 16, 14, 2]
        actualAssemsInRing = []
        for ring in range(1, self.r.core.getNumRings()):
            actualAssemsInRing.append(len(self.r.core.getAssembliesInCircularRing(ring)))
        self.assertSequenceEqual(actualAssemsInRing, expectedAssemsInRing)

    def test_getAssembliesInHexRing(self):
        expectedAssemsInRing = [1, 2, 4, 6, 8, 10, 12, 14, 16]
        actualAssemsInRing = []
        for ring in range(1, self.r.core.getNumRings() + 1):
            actualAssemsInRing.append(len(self.r.core.getAssembliesInSquareOrHexRing(ring)))
        self.assertSequenceEqual(actualAssemsInRing, expectedAssemsInRing)

    def test_genAssembliesAddedThisCycle(self):
        allAssems = self.r.core.getAssemblies()
        self.assertTrue(all(a1 is a2 for a1, a2 in zip(allAssems, self.r.core.genAssembliesAddedThisCycle())))
        a = self.r.core.getFirstAssembly()
        newA = copy.deepcopy(a)
        newA.name = None
        self.r.p.cycle = 1
        self.assertEqual(len(list(self.r.core.genAssembliesAddedThisCycle())), 0)
        self.r.core.removeAssembly(a)
        self.r.core.add(newA)
        self.assertEqual(next(self.r.core.genAssembliesAddedThisCycle()), newA)

    def test_getAssemblyPitch(self):
        self.assertEqual(self.r.core.getAssemblyPitch(), 16.75)

    def test_getNumAssembliesWithAllRingsFilledOut(self):
        nRings = self.r.core.getNumRings(indexBased=True)
        nAssmWithBlanks = self.r.core.getNumAssembliesWithAllRingsFilledOut(nRings)
        self.assertEqual(77, nAssmWithBlanks)

    @patch("armi.reactor.reactors.Core.powerMultiplier", 1)
    def test_getNumAssembliesWithAllRingsFilledOutBipass(self):
        nAssems = self.r.core.getNumAssembliesWithAllRingsFilledOut(3)
        self.assertEqual(19, nAssems)

    def test_getNumEnergyGroups(self):
        # this Core doesn't have a loaded ISOTXS library, so this test is minimally useful
        with self.assertRaises(AttributeError):
            self.r.core.getNumEnergyGroups()

    def test_getMinimumPercentFluxInFuel(self):
        # there is no flux in the test reactor YET, so this test is minimally useful
        with self.assertRaises(ZeroDivisionError):
            _targetRing, _fluxFraction = self.r.core.getMinimumPercentFluxInFuel()

    def test_getAssemblyWithLoc(self):
        """
        Get assembly by location, in a couple different ways to ensure they all work.

        .. test:: Get assembly by location.
            :id: T_ARMI_R_GET_ASSEM0
            :tests: R_ARMI_R_GET_ASSEM
        """
        a0 = self.r.core.getAssemblyWithStringLocation("003-001")
        a1 = self.r.core.getAssemblyWithAssemNum(assemNum=10)
        a2 = self.r.core.getAssembly(locationString="003-001")

        self.assertEqual(a0, a2)
        self.assertEqual(a1, a2)
        self.assertEqual(a1.getLocation(), "003-001")

    def test_getAssemblyWithName(self):
        """Test getting an assembly by name.

        .. test:: Get assembly by name.
            :id: T_ARMI_R_GET_ASSEM1
            :tests: R_ARMI_R_GET_ASSEM
        """
        a1 = self.r.core.getAssemblyWithAssemNum(assemNum=10)
        a2 = self.r.core.getAssembly(assemblyName="A0010")

        self.assertEqual(a1, a2)
        self.assertEqual(a1.name, "A0010")

    def test_getAssemblies(self):
        """Basic test of getAssemblies, with and without including the SFP.

        .. test:: The spent fuel pool is a Composite structure.
            :id: T_ARMI_SFP2
            :tests: R_ARMI_SFP
        """
        # where are we starting
        numCoreStart = len(self.r.core)
        numTotalStart = len(self.r.core.getAssemblies(includeSFP=True))

        # remove one assembly and confirm behavior
        for i in range(1, 5):
            self.r.core.removeAssembly(self.r.core.getFirstAssembly())
            self.assertEqual(len(self.r.core), numCoreStart - i)
            self.assertEqual(len(self.r.core.getAssemblies(includeSFP=True)), numTotalStart)

    def test_restoreReactor(self):
        """Restore a reactor after growing it from third to full core.

        .. test:: Convert a third-core to a full-core geometry and then restore it.
            :id: T_ARMI_THIRD_TO_FULL_CORE1
            :tests: R_ARMI_THIRD_TO_FULL_CORE
        """
        numOfAssembliesOneThird = len(self.r.core)
        self.assertFalse(self.r.core.isFullCore)
        self.assertEqual(
            self.r.core.symmetry,
            geometry.SymmetryType(geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC),
        )
        # grow to full core
        converter = self.r.core.growToFullCore(self.o.cs)
        self.assertTrue(self.r.core.isFullCore)
        self.assertGreater(len(self.r.core), numOfAssembliesOneThird)
        self.assertEqual(self.r.core.symmetry.domain, geometry.DomainType.FULL_CORE)
        # restore back to 1/3 core
        converter.restorePreviousGeometry(self.r)
        self.assertEqual(numOfAssembliesOneThird, len(self.r.core))
        self.assertEqual(
            self.r.core.symmetry,
            geometry.SymmetryType(geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC),
        )
        self.assertFalse(self.r.core.isFullCore)
        self.assertEqual(numOfAssembliesOneThird, len(self.r.core))
        self.assertEqual(
            self.r.core.symmetry,
            geometry.SymmetryType(geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC),
        )

    def test_differentNuclideModels(self):
        self.assertEqual(self.o.cs[CONF_XS_KERNEL], "MC2v3")
        _o2, r2 = loadTestReactor(customSettings={CONF_XS_KERNEL: "MC2v2"})

        self.assertNotEqual(set(self.r.blueprints.elementsToExpand), set(r2.blueprints.elementsToExpand))

        for b2, b3 in zip(r2.core.iterBlocks(), self.r.core.iterBlocks()):
            for element in self.r.blueprints.elementsToExpand:
                # nucspec allows elemental mass to be computed
                mass2 = b2.getMass(element.symbol)
                mass3 = b3.getMass(element.symbol)
                assert_allclose(mass2, mass3)

                constituentNucs = [nn.name for nn in element.nuclides if nn.a > 0]
                nuclideLevelMass3 = b3.getMass(constituentNucs)
                assert_allclose(mass3, nuclideLevelMass3)

    def test_getDominantMaterial(self):
        dominantDuct = self.r.core.getDominantMaterial(Flags.DUCT)
        dominantFuel = self.r.core.getDominantMaterial(Flags.FUEL)
        dominantCool = self.r.core.getDominantMaterial(Flags.COOLANT)

        self.assertEqual(dominantDuct.getName(), "HT9")
        self.assertEqual(dominantFuel.getName(), "UZr")
        self.assertEqual(dominantCool.getName(), "Sodium")

    def test_getSymmetryFactor(self):
        """
        Test getSymmetryFactor().

        .. test:: Get the core symmetry.
            :id: T_ARMI_R_SYMM
            :tests: R_ARMI_R_SYMM
        """
        for b in self.r.core.iterBlocks():
            sym = b.getSymmetryFactor()
            i, j, _ = b.spatialLocator.getCompleteIndices()
            if i == 0 and j == 0:
                self.assertEqual(sym, 3.0)
            else:
                self.assertEqual(sym, 1.0)

    def test_getAssembliesOnSymmetryLine(self):
        center = self.r.core.getAssembliesOnSymmetryLine(grids.BOUNDARY_CENTER)
        self.assertEqual(len(center), 1)
        upper = self.r.core.getAssembliesOnSymmetryLine(grids.BOUNDARY_120_DEGREES)
        self.assertEqual(len(upper), 0)
        lower = self.r.core.getAssembliesOnSymmetryLine(grids.BOUNDARY_0_DEGREES)
        self.assertGreater(len(lower), 1)

    def test_saveAllFlux(self):
        # need a lightweight library to indicate number of groups.
        class MockLib:
            numGroups = 5

        self.r.core.lib = MockLib()
        for b in self.r.core.iterBlocks():
            b.p.mgFlux = range(5)
            b.p.adjMgFlux = range(5)

        with directoryChangers.TemporaryDirectoryChanger(root=_THIS_DIR):
            self.r.core.saveAllFlux()

    def test_getFluxVector(self):
        class MockLib:
            numGroups = 5

        self.r.core.lib = MockLib()
        for b in self.r.core.iterBlocks():
            b.p.mgFlux = range(5)
            b.p.adjMgFlux = [i + 0.1 for i in range(5)]
            b.p.extSrc = [i + 0.2 for i in range(5)]
        mgFlux = self.r.core.getFluxVector(energyOrder=1)
        adjFlux = self.r.core.getFluxVector(adjoint=True)
        srcVec = self.r.core.getFluxVector(extSrc=True)
        fluxVol = self.r.core.getFluxVector(volumeIntegrated=True)
        blocks = self.r.core.getBlocks()
        expFlux = [i for i in range(5) for _ in blocks]
        expAdjFlux = [i + 0.1 for _ in blocks for i in range(5)]
        expSrcVec = [i + 0.2 for _ in blocks for i in range(5)]
        expFluxVol = list(range(5)) * len(blocks)
        assert_allclose(expFlux, mgFlux)
        assert_allclose(expAdjFlux, adjFlux)
        assert_allclose(expSrcVec, srcVec)
        assert_allclose(expFluxVol, fluxVol)

    def test_getFuelBottomHeight(self):
        for a in self.r.core.getAssemblies(Flags.FUEL):
            if a[0].hasFlags(Flags.FUEL):
                a[0].setType("mud")
            a[1].setType("fuel")
        fuelBottomHeightRef = self.r.core.getFirstAssembly(Flags.FUEL)[0].getHeight()
        fuelBottomHeightInCm = self.r.core.getFuelBottomHeight()

        self.assertEqual(fuelBottomHeightInCm, fuelBottomHeightRef)

    def test_getGridBounds(self):
        """Test getGridBounds() works on different scales.

        .. test:: Test that assembly grids nest inside core grids.
            :id: T_ARMI_GRID_NEST
            :tests: R_ARMI_GRID_NEST
        """
        (minI, maxI), (minJ, maxJ), (_minK, _maxK) = self.r.core.getBoundingIndices()
        self.assertEqual((minI, maxI), (-3, 8))
        self.assertEqual((minJ, maxJ), (-4, 8))

        randomBlock = self.r.core.getFirstAssembly()
        (minI, maxI), (minJ, maxJ), (_minK, _maxK) = randomBlock.getBoundingIndices()
        self.assertEqual((minI, maxI), (8, 8))
        self.assertEqual((minJ, maxJ), (-4, -4))

    def test_locations(self):
        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(3, 2)
        a = self.r.core.childrenByLocator[loc]
        assert_allclose(a.spatialLocator.indices, [1, 1, 0])
        for bi, b in enumerate(a):
            assert_allclose(b.spatialLocator.getCompleteIndices(), [1, 1, bi])
        self.assertEqual(a.getLocation(), "003-002")
        self.assertEqual(a[0].getLocation(), "003-002-000")

    def test_getMass(self):
        # If these are not in agreement check on block symmetry factor being applied to volumes
        mass1 = self.r.core.getMass()
        mass2 = sum([b.getMass() for b in self.r.core.iterBlocks()])
        assert_allclose(mass1, mass2)

    def test_isPickleable(self):
        loaded = pickle.loads(pickle.dumps(self.r))

        # ensure we didn't break the current reactor
        self.assertIs(self.r.core.spatialGrid.armiObject, self.r.core)

        # make sure that the loaded reactor and grid are aligned
        self.assertIs(loaded.core.spatialGrid.armiObject, loaded.core)
        self.assertTrue(all(isinstance(key, grids.LocationBase) for key in loaded.core.childrenByLocator.keys()))
        loc = loaded.core.spatialGrid[0, 0, 0]
        loaded.core.sortAssemsByRing()
        self.r.core.sortAssemsByRing()
        self.assertIs(loc.grid, loaded.core.spatialGrid)
        self.assertEqual(loaded.core.childrenByLocator[loc], loaded.core[0])

        allIDs = set()

        def checkAdd(comp):
            self.assertNotIn(id(comp), allIDs)
            self.assertNotIn(id(comp.p), allIDs)
            allIDs.add(id(comp))
            allIDs.add(id(comp.p))

        # check a few locations to be equivalent
        for a0, a1 in zip(self.r.core, loaded.core):
            self.assertEqual(str(a0.getLocation()), str(a1.getLocation()))
            self.assertIs(a0.spatialLocator.grid, self.r.core.spatialGrid)
            self.assertIs(a1.spatialLocator.grid, loaded.core.spatialGrid)
            checkAdd(a0)
            checkAdd(a1)
            for b0, b1 in zip(a0, a1):
                self.assertIs(b0.spatialLocator.grid, a0.spatialGrid)
                self.assertIs(b1.spatialLocator.grid, a1.spatialGrid)
                self.assertEqual(str(b0.getLocation()), str(b1.getLocation()))
                self.assertEqual(b0.getSymmetryFactor(), b1.getSymmetryFactor())
                self.assertEqual(b0.getHMMoles(), b1.getHMMoles())
                checkAdd(b0)
                checkAdd(b1)

    def test_removeAssembly(self):
        """Test the removeAssembly method.

        In particular, the Settings here set trackAssems to True, so when an Assembly is removed
        from the Core, it shows up in the SFP.
        """
        a = self.r.core[-1]  # last assembly
        b = a[-1]  # use the last block in case we ever figure out stationary blocks
        aLoc = a.spatialLocator
        self.assertIsNotNone(aLoc.grid)
        bLoc = b.spatialLocator
        self.r.core.removeAssembly(a)
        self.assertNotEqual(aLoc, a.spatialLocator)

        # confirm the Assembly is now in the SFP
        self.assertEqual(a.spatialLocator.grid, self.r.excore["sfp"].spatialGrid)

        # confirm only attached to removed assem
        self.assertIs(bLoc, b.spatialLocator)  # block location does not change
        self.assertIs(a, b.parent)
        self.assertIs(a, b.spatialLocator.grid.armiObject)

    def test_removeAssemblyNoSfp(self):
        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock.getStdout())
            runLog.LOG.startLog("test_removeAssemblyNoSfp")
            runLog.LOG.setVerbosity(logging.INFO)

            a = self.r.core[-1]  # last assembly
            aLoc = a.spatialLocator
            self.assertIsNotNone(aLoc.grid)
            self.r.excore["sfp"] = None
            del self.r.excore["sfp"]
            self.r.core.removeAssembly(a)

            self.assertIn("No Spent Fuel Pool", mock.getStdout())

    def test_removeAssembliesInRing(self):
        aLoc = [self.r.core.spatialGrid.getLocatorFromRingAndPos(3, i + 1) for i in range(12)]
        assems = {
            i: self.r.core.childrenByLocator[loc] for i, loc in enumerate(aLoc) if loc in self.r.core.childrenByLocator
        }
        self.r.core.removeAssembliesInRing(3, self.o.cs)
        for i, a in assems.items():
            self.assertNotEqual(aLoc[i], a.spatialLocator)
            self.assertEqual(a.spatialLocator.grid, self.r.excore["sfp"].spatialGrid)

    def test_removeAssembliesInRingByCount(self):
        """Tests retrieving ring numbers and removing a ring."""
        self.assertEqual(self.r.core.getNumRings(), 9)
        self.r.core.removeAssembliesInRing(9, self.o.cs)
        self.assertEqual(self.r.core.getNumRings(), 8)

    def test_getNumRings(self):
        self.assertEqual(len(self.r.core.circularRingList), 0)
        self.assertEqual(self.r.core.getNumRings(indexBased=True), 9)
        self.assertEqual(self.r.core.getNumRings(indexBased=False), 9)

        self.r.core.circularRingList = {1, 2, 3}
        self.assertEqual(len(self.r.core.circularRingList), 3)
        self.assertEqual(self.r.core.getNumRings(indexBased=True), 9)
        self.assertEqual(self.r.core.getNumRings(indexBased=False), 3)

    @patch("armi.reactor.reactors.Core.getAssemblies")
    def test_whenNoAssemblies(self, mockGetAssemblies):
        """Test various edge cases when there are no assemblies."""
        mockGetAssemblies.return_value = []

        self.assertEqual(self.r.core.countBlocksWithFlags(Flags.FUEL), 0)
        self.assertEqual(self.r.core.countFuelAxialBlocks(), 0)
        self.assertGreater(self.r.core.getFirstFuelBlockAxialNode(), 9e9)

    def test_removeAssembliesInRingHex(self):
        """
        Since the test reactor is hex, we need to use the overrideCircularRingMode option
        to remove assemblies from it.
        """
        self.assertEqual(self.r.core.getNumRings(), 9)
        for ringNum in range(6, 10):
            self.r.core.removeAssembliesInRing(ringNum, self.o.cs, overrideCircularRingMode=True)
        self.assertEqual(self.r.core.getNumRings(), 5)

    def test_getNozzleTypes(self):
        nozzleTypes = self.r.core.getNozzleTypes()
        expectedTypes = ["Inner", "Outer", "lta", "Default"]
        for nozzle in expectedTypes:
            self.assertIn(nozzle, nozzleTypes)

    def test_createAssemblyOfType(self):
        """Test creation of new assemblies."""
        # basic creation
        aOld = self.r.core.getFirstAssembly(Flags.FUEL)
        aNew = self.r.core.createAssemblyOfType(aOld.getType(), cs=self.o.cs)
        self.assertAlmostEqual(aOld.getMass(), aNew.getMass())

        # test axial mesh alignment
        aNewMesh = aNew.getAxialMesh()
        for i, meshValue in enumerate(aNewMesh):
            self.assertAlmostEqual(meshValue, self.r.core.p.referenceBlockAxialMesh[i + 1])  # use i+1 to skip 0.0

        # creation with modified enrichment
        aNew2 = self.r.core.createAssemblyOfType(aOld.getType(), 0.195, self.o.cs)
        fuelBlock = aNew2.getFirstBlock(Flags.FUEL)
        self.assertAlmostEqual(fuelBlock.getUraniumMassEnrich(), 0.195)

        # creation with modified enrichment on an expanded BOL assem.
        fuelComp = fuelBlock.getComponent(Flags.FUEL)
        bol = self.r.blueprints.assemblies[aOld.getType()]
        changer = AxialExpansionChanger()
        changer.performPrescribedAxialExpansion(bol, [fuelComp], [0.05])
        aNew3 = self.r.core.createAssemblyOfType(aOld.getType(), 0.195, self.o.cs)
        self.assertAlmostEqual(aNew3.getFirstBlock(Flags.FUEL).getUraniumMassEnrich(), 0.195)
        self.assertAlmostEqual(aNew3.getMass(), bol.getMass())

    def test_createFreshFeed(self):
        # basic creation
        aOld = self.r.core.getFirstAssembly(Flags.FEED)
        aNew = self.r.core.createFreshFeed(cs=self.o.cs)
        self.assertAlmostEqual(aOld.getMass(), aNew.getMass())

    def test_createAssemblyOfTypeExpandedCore(self):
        """Test creation of new assemblies in an expanded core."""
        # change the mesh of inner blocks
        mesh = self.r.core.p.referenceBlockAxialMesh[1:]
        lastIndex = len(mesh) - 1
        mesh = [val + 5 for val in mesh]
        mesh[0] -= 5
        mesh[lastIndex] -= 5

        # expand the core
        self.r.core.p.referenceBlockAxialMesh = [0] + mesh
        for a in self.r.core:
            a.setBlockMesh(mesh)
        aType = self.r.core.getFirstAssembly(Flags.FUEL).getType()

        # demonstrate we can still create assemblies
        self.assertTrue(self.r.core.createAssemblyOfType(aType, cs=self.o.cs))

    def test_getAvgTemp(self):
        t0 = self.r.core.getAvgTemp([Flags.CLAD, Flags.WIRE, Flags.DUCT])
        self.assertAlmostEqual(t0, 459.267, delta=0.01)

        t1 = self.r.core.getAvgTemp([Flags.CLAD, Flags.FUEL])
        self.assertAlmostEqual(t1, 545.043, delta=0.01)

        t2 = self.r.core.getAvgTemp([Flags.CLAD, Flags.WIRE, Flags.DUCT, Flags.FUEL])
        self.assertAlmostEqual(t2, 521.95269, delta=0.01)

    def test_getScalarEvolution(self):
        self.r.core.scalarVals["fake"] = 123
        x = self.r.core.getScalarEvolution("fake")
        self.assertEqual(x, 123)

    def test_ifMissingSpatialGrid(self):
        self.r.core.spatialGrid = None

        with self.assertRaises(ValueError):
            self.r.core.symmetry

        with self.assertRaises(ValueError):
            self.r.core.geomType

    def test_pinCoordsAllBlocks(self):
        """Make sure all blocks can get pin coords."""
        for b in self.r.core.iterBlocks():
            coords = b.getPinCoordinates()
            self.assertGreater(len(coords), -1)

    def test_nonUniformAssems(self):
        o, r = loadTestReactor(customSettings={"nonUniformAssemFlags": ["primary control"]})
        a = o.r.core.getFirstAssembly(Flags.FUEL)
        self.assertTrue(all(b.p.topIndex != 0 for b in a[1:]))
        a = o.r.core.getFirstAssembly(Flags.PRIMARY)
        self.assertTrue(all(b.p.topIndex == 0 for b in a))
        originalHeights = [b.p.height for b in a]
        differntMesh = [val + 2 for val in r.core.p.referenceBlockAxialMesh]
        # won't change because nonUnfiform assem doesn't conform to reference mesh
        a.setBlockMesh(differntMesh)
        heights = [b.p.height for b in a]
        self.assertEqual(originalHeights, heights)

    def test_applyThermalExpansion_CoreConstruct(self):
        r"""Test that assemblies in core are correctly expanded.

        Notes
        -----
        - all assertions skip the first block as it has no $\Delta T$ and does not expand
        """
        originalAssems = self.r.core.getAssemblies()
        # stash original axial mesh info
        oldRefBlockAxialMesh = self.r.core.p.referenceBlockAxialMesh
        oldAxialMesh = self.r.core.p.axialMesh

        nonEqualParameters = ["heightBOL", "molesHmBOL", "massHmBOL"]
        equalParameters = ["smearDensity", "nHMAtBOL", "enrichmentBOL"]

        o, coldHeightR = loadTestReactor(
            self.directoryChanger.destination,
            customSettings={
                "inputHeightsConsideredHot": False,
                "assemFlagsToSkipAxialExpansion": ["feed fuel"],
            },
        )
        aToSkip = list(Flags.fromStringIgnoreErrors(t) for t in o.cs[CONF_ASSEM_FLAGS_SKIP_AXIAL_EXP])

        for i, val in enumerate(oldRefBlockAxialMesh[1:]):
            self.assertNotEqual(val, coldHeightR.core.p.referenceBlockAxialMesh[i])
        for i, val in enumerate(oldAxialMesh[1:]):
            self.assertNotEqual(val, coldHeightR.core.p.axialMesh[i])

        coldHeightAssems = coldHeightR.core.getAssemblies()
        for a, coldHeightA in zip(originalAssems, coldHeightAssems):
            if a.hasFlags(Flags.CONTROL) or any(a.hasFlags(aFlags) for aFlags in aToSkip):
                continue
            for b, coldHeightB in zip(a[1:], coldHeightA[1:]):
                for param in nonEqualParameters:
                    p, coldHeightP = b.p[param], coldHeightB.p[param]
                    if p and coldHeightP:
                        self.assertNotEqual(p, coldHeightP, f"{param} {p} {coldHeightP}")
                    else:
                        self.assertAlmostEqual(p, coldHeightP)
                for param in equalParameters:
                    p, coldHeightP = b.p[param], coldHeightB.p[param]
                    self.assertAlmostEqual(p, coldHeightP)

    def test_updateBlockBOLHeights_DBLoad(self):
        r"""Test that blueprints assemblies are expanded in DB load.

        Notes
        -----
        All assertions skip the first block as it has no $\Delta T$ and does not expand.
        """
        originalAssems = sorted(a for a in self.r.blueprints.assemblies.values())
        nonEqualParameters = ["heightBOL", "molesHmBOL", "massHmBOL"]
        equalParameters = ["smearDensity", "nHMAtBOL", "enrichmentBOL"]

        _o, coldHeightR = loadTestReactor(
            self.directoryChanger.destination,
            customSettings={"inputHeightsConsideredHot": False},
        )
        coldHeightAssems = sorted(a for a in coldHeightR.blueprints.assemblies.values())
        for a, coldHeightA in zip(originalAssems, coldHeightAssems):
            if not a.hasFlags(Flags.CONTROL):
                for b, coldHeightB in zip(a[1:], coldHeightA[1:]):
                    for param in nonEqualParameters:
                        p, coldHeightP = b.p[param], coldHeightB.p[param]
                        if p and coldHeightP:
                            self.assertNotEqual(p, coldHeightP)
                        else:
                            self.assertAlmostEqual(p, coldHeightP)
                    for param in equalParameters:
                        p, coldHeightP = b.p[param], coldHeightB.p[param]
                        self.assertAlmostEqual(p, coldHeightP)

    def test_buildManualZones(self):
        # define some manual zones in the settings
        newSettings = {}
        newSettings["zoneDefinitions"] = [
            "ring-1: 001-001",
            "ring-2: 002-001, 002-002",
            "ring-3: 003-001, 003-002, 003-003",
        ]
        cs = self.o.cs.modified(newSettings=newSettings)
        self.r.core.buildManualZones(cs)

        zonez = self.r.core.zones
        self.assertEqual(len(list(zonez)), 3)
        self.assertIn("002-001", zonez["ring-2"])
        self.assertIn("003-002", zonez["ring-3"])

    def test_buildManualZonesEmpty(self):
        # ensure there are no zone definitions in the settings
        newSettings = {}
        newSettings["zoneDefinitions"] = []
        cs = self.o.cs.modified(newSettings=newSettings)

        # verify that buildZones behaves well when no zones are defined
        self.r.core.buildManualZones(cs)
        self.assertEqual(len(list(self.r.core.zones)), 0)

    def test_getNuclideCategories(self):
        """Test that nuclides are categorized correctly."""
        self.r.core.getNuclideCategories()
        self.assertIn("coolant", self.r.core._nuclideCategories)
        self.assertIn("structure", self.r.core._nuclideCategories)
        self.assertIn("fuel", self.r.core._nuclideCategories)
        self.assertEqual(self.r.core._nuclideCategories["coolant"], set(["NA23"]))
        self.assertIn("FE56", self.r.core._nuclideCategories["structure"])
        self.assertIn("U235", self.r.core._nuclideCategories["fuel"])

    def test_setPowerIfNecessary(self):
        self.assertAlmostEqual(self.r.core.p.power, 0)
        self.assertAlmostEqual(self.r.core.p.powerDensity, 0)

        # to start, this method shouldn't do anything
        self.r.core.setPowerIfNecessary()
        self.assertAlmostEqual(self.r.core.p.power, 0)

        # take the powerDensity when needed
        self.r.core.p.power = 0
        self.r.core.p.powerDensity = 1e9
        mass = self.r.core.getHMMass()
        self.r.core.setPowerIfNecessary()
        self.assertAlmostEqual(self.r.core.p.power, 1e9 * mass)

        # don't take the powerDensity when not needed
        self.r.core.p.power = 3e9
        self.r.core.p.powerDensity = 2e9
        self.r.core.setPowerIfNecessary()
        self.assertAlmostEqual(self.r.core.p.power, 3e9)

    def test_findAllMeshPoints(self):
        """Test findAllMeshPoints().

        .. test:: Test that the reactor can calculate its core block mesh.
            :id: T_ARMI_R_MESH
            :tests: R_ARMI_R_MESH
        """
        # lets do some basic sanity checking of the meshpoints
        x, y, z = self.r.core.findAllMeshPoints()

        # no two meshpoints should be the same, and they should all be monotonically increasing
        for xx in range(1, len(x)):
            self.assertGreater(x[xx], x[xx - 1], msg=f"x={xx}")

        for yy in range(1, len(y)):
            self.assertGreater(y[yy], y[yy - 1], msg=f"y={yy}")

        for zz in range(1, len(z)):
            self.assertGreater(z[zz], z[zz - 1], msg=f"z={zz}")

        # the z-index should start at zero (the bottom)
        self.assertEqual(z[0], 0)

        # ensure the X and Y mesh spacing is correct (for a hex core)
        pitch = self.r.core.spatialGrid.pitch

        xPitch = sqrt(3) * pitch / 2
        for xx in range(1, len(x)):
            self.assertAlmostEqual(x[xx] - x[xx - 1], xPitch, delta=0.0001)

        yPitch = pitch / 2
        for yy in range(1, len(y)):
            self.assertAlmostEqual(y[yy] - y[yy - 1], yPitch, delta=0.001)


class CartesianReactorTests(ReactorTests):
    def setUp(self):
        self.o = buildOperatorOfEmptyCartesianBlocks()
        self.r = self.o.r

    def test_add(self):
        a = self.r.core.getFirstAssembly()
        numA = len(a)
        a.add(blocks.CartesianBlock("test cart block"))
        self.assertEqual(len(a), numA + 1)

        with self.assertRaises(TypeError):
            a.add(blocks.HexBlock("test hex block"))

    def test_getAssemblyPitch(self):
        # Cartesian pitch should have 2 dims since it could be a rectangle that is not square.
        assert_equal(self.r.core.getAssemblyPitch(), [10.0, 16.0])

    def test_getAssembliesInSquareRing(self, exclusions=[2]):
        expectedAssemsInRing = [1, 0]
        actualAssemsInRing = []
        for ring in range(1, self.r.core.getNumRings() + 1):
            actualAssemsInRing.append(len(self.r.core.getAssembliesInSquareOrHexRing(ring)))
        self.assertSequenceEqual(actualAssemsInRing, expectedAssemsInRing)

    def test_getNuclideCategoriesLogging(self):
        """Simplest possible test of the getNuclideCategories method and its logging."""
        log = mockRunLogs.BufferLog()

        # this strange namespace-stomping is used to the test to set the logger in reactors.Core
        from armi.reactor import reactors

        reactors.runLog = runLog
        runLog.LOG = log

        # run the actual method in question
        self.r.core.getNuclideCategories()
        messages = log.getStdout()

        self.assertIn("Nuclide categorization", messages)
        self.assertIn("Structure", messages)


class CartesianReactorNeighborTests(ReactorTests):
    def setUp(self):
        self.r = loadTestReactor(TEST_ROOT, inputFileName="zpprTest.yaml")[1]

    def test_findNeighborsCartesian(self):
        """Find neighbors of a given assembly in a Cartesian grid."""
        loc = self.r.core.spatialGrid[1, 1, 0]
        a = self.r.core.childrenByLocator[loc]
        neighbs = self.r.core.findNeighbors(a)
        locs = [tuple(a.spatialLocator.indices[:2]) for a in neighbs]
        self.assertEqual(len(neighbs), 4)
        self.assertIn((2, 1), locs)
        self.assertIn((1, 2), locs)
        self.assertIn((0, 1), locs)
        self.assertIn((1, 0), locs)

        # try with edge assembly
        loc = self.r.core.spatialGrid[0, 0, 0]
        a = self.r.core.childrenByLocator[loc]
        neighbs = self.r.core.findNeighbors(a, showBlanks=False)
        locs = [tuple(a.spatialLocator.indices[:2]) for a in neighbs]
        self.assertEqual(len(neighbs), 2)
        # in this case no locations that aren't actually in the core should be returned
        self.assertIn((1, 0), locs)
        self.assertIn((0, 1), locs)
