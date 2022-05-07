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
r"""
testing for reactors.py
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import copy
import os
import unittest

from six.moves import cPickle
from numpy.testing import assert_allclose, assert_equal

from armi import operators
from armi import runLog
from armi import settings
from armi import tests
from armi.materials import uZr
from armi.reactor.flags import Flags
from armi.reactor import assemblies
from armi.reactor import blocks
from armi.reactor import grids
from armi.reactor import geometry
from armi.reactor import reactors
from armi.reactor.components import Hexagon, Rectangle
from armi.reactor.converters import geometryConverters
from armi.tests import ARMI_RUN_PATH, mockRunLogs, TEST_ROOT
from armi.utils import directoryChangers
from armi.reactor.converters.axialExpansionChanger import AxialExpansionChanger

TEST_REACTOR = None  # pickled string of test reactor (for fast caching)


def buildOperatorOfEmptyHexBlocks(customSettings=None):
    """
    Builds a operator w/ a reactor object with some hex assemblies and blocks, but all are empty

    Doesn't depend on inputs and loads quickly.

    Params
    ------
    customSettings : dict
        Dictionary of off-default settings to update
    """
    settings.setMasterCs(None)  # clear
    cs = settings.getMasterCs()  # fetch new

    if customSettings is None:
        customSettings = {}

    customSettings["db"] = False  # stop use of database
    cs = cs.modified(newSettings=customSettings)
    settings.setMasterCs(cs)  # reset so everything matches master

    r = tests.getEmptyHexReactor()
    r.core.setOptionsFromCs(cs)
    o = operators.Operator(cs)
    o.initializeInterfaces(r)

    a = assemblies.HexAssembly("fuel")
    a.spatialGrid = grids.axialUnitGrid(1)
    b = blocks.HexBlock("TestBlock")
    b.setType("fuel")
    dims = {"Tinput": 600, "Thot": 600, "op": 16.0, "ip": 1, "mult": 1}
    c = Hexagon("fuel", uZr.UZr(), **dims)
    b.add(c)
    a.add(b)
    a.spatialLocator = r.core.spatialGrid[1, 0, 0]
    o.r.core.add(a)
    return o


def buildOperatorOfEmptyCartesianBlocks(customSettings=None):
    """
    Builds a operator w/ a reactor object with some Cartesian assemblies and blocks, but all are empty

    Doesn't depend on inputs and loads quickly.

    Params
    ------
    customSettings : dict
        Dictionary of off-default settings to update
    """
    settings.setMasterCs(None)  # clear
    cs = settings.getMasterCs()  # fetch new

    if customSettings is None:
        customSettings = {}

    customSettings["db"] = False  # stop use of database
    cs = cs.modified(newSettings=customSettings)
    settings.setMasterCs(cs)  # reset

    r = tests.getEmptyCartesianReactor()
    r.core.setOptionsFromCs(cs)
    o = operators.Operator(cs)
    o.initializeInterfaces(r)

    a = assemblies.CartesianAssembly("fuel")
    a.spatialGrid = grids.axialUnitGrid(1)
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
    return o


def loadTestReactor(
    inputFilePath=TEST_ROOT, customSettings=None, inputFileName="armiRun.yaml"
):
    r"""
    Loads a test reactor. Can be used in other test modules.

    Parameters
    ----------
    inputFilePath : str
        Path to the directory of the input file.

    customSettings : dict with str keys and values of any type
        For each key in customSettings, the cs which is loaded from the
        armiRun.yaml will be overwritten to the value given in customSettings
        for that key.

    inputFileName : str, default="armiRun.yaml"
        Name of the input file to run.

    Returns
    -------
    o : Operator
    r : Reactor
    """
    # TODO: it would be nice to have this be more stream-oriented. Juggling files is
    # devilishly difficult.
    global TEST_REACTOR
    fName = os.path.join(inputFilePath, inputFileName)
    customSettings = customSettings or {}
    isPickeledReactor = fName == ARMI_RUN_PATH and customSettings == {}
    assemblies.resetAssemNumCounter()

    if isPickeledReactor and TEST_REACTOR:
        # return test reactor only if no custom settings are needed.
        o, r, assemNum = cPickle.loads(TEST_REACTOR)
        assemblies.setAssemNumCounter(assemNum)
        settings.setMasterCs(o.cs)
        o.reattach(r, o.cs)
        return o, r

    cs = settings.Settings(fName=fName)

    # Overwrite settings if desired
    if customSettings:
        newSettings = {}
        for settingKey, settingVal in customSettings.items():
            newSettings[settingKey] = settingVal

        cs = cs.modified(newSettings=newSettings)

    if "verbosity" not in customSettings:
        runLog.setVerbosity("error")

    newSettings = {}
    newSettings["stationaryBlocks"] = []
    newSettings["nCycles"] = 3
    cs = cs.modified(newSettings=newSettings)
    settings.setMasterCs(cs)

    o = operators.factory(cs)
    r = reactors.loadFromCs(cs)
    o.initializeInterfaces(r)

    # put some stuff in the SFP too.
    for a in range(10):
        a = o.r.blueprints.constructAssem(o.cs, name="feed fuel")
        o.r.core.sfp.add(a)

    o.r.core.regenAssemblyLists()

    if isPickeledReactor:
        # cache it for fast load for other future tests
        # protocol=2 allows for classes with __slots__ but not __getstate__ to be pickled
        TEST_REACTOR = cPickle.dumps((o, o.r, assemblies.getAssemNum()), protocol=2)

    return o, o.r


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
        self.o, self.r = loadTestReactor(self.directoryChanger.destination)

    def test_getTotalParam(self):
        # verify that the block params are being read.
        val = self.r.core.getTotalBlockParam("power")
        val2 = self.r.core.getTotalBlockParam("power", addSymmetricPositions=True)
        self.assertEqual(val2 / self.r.core.powerMultiplier, val)

    def test_geomType(self):
        self.assertTrue(self.r.core.geomType == geometry.GeomType.HEX)

    def test_growToFullCore(self):
        nAssemThird = len(self.r.core)
        self.assertEqual(self.r.core.powerMultiplier, 3.0)
        self.assertFalse(self.r.core.isFullCore)
        self.r.core.growToFullCore(self.o.cs)
        aNums = []
        for a in self.r.core.getChildren():
            self.assertNotIn(a.getNum(), aNums)
            aNums.append(a.getNum())

        bNames = [b.getName() for b in self.r.core.getBlocks()]
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
        expectedNames = ["B0022-001", "B0043-002"]
        self.assertListEqual(expectedNames, actualNames)

    def test_getAllXsSuffixes(self):
        actualSuffixes = self.r.core.getAllXsSuffixes()
        expectedSuffixes = ["AA"]
        self.assertListEqual(expectedSuffixes, actualSuffixes)

    def test_countBlocksOfType(self):
        numControlBlocks = self.r.core.countBlocksWithFlags([Flags.DUCT, Flags.CONTROL])

        self.assertEqual(numControlBlocks, 3)

        numControlBlocks = self.r.core.countBlocksWithFlags(
            [Flags.DUCT, Flags.CONTROL, Flags.FUEL], Flags.CONTROL
        )
        self.assertEqual(numControlBlocks, 3)

    def test_countFuelAxialBlocks(self):
        """Tests that the users definition of fuel blocks is preserved.

        .. test:: Tests that the users definition of fuel blocks is preserved.
            :id: TEST_REACTOR_2
            :links: REQ_REACTOR
        """
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
        numMeshPoints = (
            len(self.r.core.p.axialMesh) - 2
        )  # -1 for typical reason, -1 more because mesh includes 0
        self.assertEqual(self.r.core.findAxialMeshIndexOf(0.0), 0)
        self.assertEqual(self.r.core.findAxialMeshIndexOf(0.1), 0)
        self.assertEqual(
            self.r.core.findAxialMeshIndexOf(self.r.core[0].getHeight()), numMeshPoints
        )
        self.assertEqual(
            self.r.core.findAxialMeshIndexOf(self.r.core[0].getHeight() - 0.1),
            numMeshPoints,
        )
        self.assertEqual(
            self.r.core.findAxialMeshIndexOf(self.r.core[0][0].getHeight() + 0.1), 1
        )

    def test_findAllAxialMeshPoints(self):
        mesh = self.r.core.findAllAxialMeshPoints(applySubMesh=False)

        self.assertEqual(mesh[0], 0)
        self.assertAlmostEqual(mesh[-1], self.r.core[0].getHeight())

        blockMesh = self.r.core.getFirstAssembly(Flags.FUEL).spatialGrid._bounds[2]
        assert_allclose(blockMesh, mesh)

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
        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(1, 1)
        a = self.r.core.childrenByLocator[loc]
        neighbs = self.r.core.findNeighbors(
            a, duplicateAssembliesOnReflectiveBoundary=True
        )
        locs = [a.spatialLocator.getRingPos() for a in neighbs]
        self.assertEqual(len(neighbs), 6)
        self.assertIn((2, 1), locs)
        self.assertIn((2, 2), locs)
        self.assertEqual(locs.count((2, 1)), 3)

        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(1, 1)
        a = self.r.core.childrenByLocator[loc]
        neighbs = self.r.core.findNeighbors(
            a, duplicateAssembliesOnReflectiveBoundary=True
        )
        locs = [a.spatialLocator.getRingPos() for a in neighbs]
        self.assertEqual(locs, [(2, 1), (2, 2)] * 3, 6)

        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(2, 2)
        a = self.r.core.childrenByLocator[loc]

        neighbs = self.r.core.findNeighbors(
            a, duplicateAssembliesOnReflectiveBoundary=True
        )
        locs = [a.spatialLocator.getRingPos() for a in neighbs]
        self.assertEqual(len(neighbs), 6)
        self.assertEqual(locs, [(3, 2), (3, 3), (3, 12), (2, 1), (1, 1), (2, 1)])

        # try with edge assemblies
        # With edges, the neighbor is the one that's actually next to it.
        converter = geometryConverters.EdgeAssemblyChanger()
        converter.addEdgeAssemblies(self.r.core)
        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(2, 2)
        a = self.r.core.childrenByLocator[loc]
        neighbs = self.r.core.findNeighbors(
            a, duplicateAssembliesOnReflectiveBoundary=True
        )
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
        neighbs = self.r.core.findNeighbors(
            a, duplicateAssembliesOnReflectiveBoundary=True
        )
        locs = [a.spatialLocator.getRingPos() for a in neighbs]
        self.assertEqual(len(neighbs), 6)
        self.assertEqual(locs, [(3, 2), (3, 3), (3, 4), (2, 3), (1, 1), (2, 1)])

    def test_getAssembliesInCircularRing(self):
        expectedAssemsInRing = [5, 6, 8, 10, 12, 16, 14, 2]
        actualAssemsInRing = []
        for ring in range(1, self.r.core.getNumRings()):
            actualAssemsInRing.append(
                len(self.r.core.getAssembliesInCircularRing(ring))
            )
        self.assertSequenceEqual(actualAssemsInRing, expectedAssemsInRing)

    def test_getAssembliesInHexRing(self):
        expectedAssemsInRing = [1, 2, 4, 6, 8, 10, 12, 14, 16]
        actualAssemsInRing = []
        for ring in range(1, self.r.core.getNumRings() + 1):
            actualAssemsInRing.append(
                len(self.r.core.getAssembliesInSquareOrHexRing(ring))
            )
        self.assertSequenceEqual(actualAssemsInRing, expectedAssemsInRing)

    def test_genAssembliesAddedThisCycle(self):
        allAssems = self.r.core.getAssemblies()
        self.assertTrue(
            all(
                a1 is a2
                for a1, a2 in zip(allAssems, self.r.core.genAssembliesAddedThisCycle())
            )
        )
        a = self.r.core.getAssemblies()[0]
        newA = copy.deepcopy(a)
        newA.name = None
        self.r.p.cycle = 1
        self.assertTrue(len(list(self.r.core.genAssembliesAddedThisCycle())) == 0)
        self.r.core.removeAssembly(a)
        self.r.core.add(newA)
        self.assertTrue(next(self.r.core.genAssembliesAddedThisCycle()) is newA)

    def test_getAssemblyPitch(self):
        self.assertEqual(self.r.core.getAssemblyPitch(), 16.75)

    def test_getNumAssembliesWithAllRingsFilledOut(self):
        nRings = self.r.core.getNumRings(indexBased=True)
        nAssmWithBlanks = self.r.core.getNumAssembliesWithAllRingsFilledOut(nRings)
        self.assertEqual(77, nAssmWithBlanks)

    def test_getAssembly(self):
        a1 = self.r.core.getAssemblyWithAssemNum(assemNum=10)
        a2 = self.r.core.getAssembly(locationString="005-023")
        a3 = self.r.core.getAssembly(assemblyName="A0010")
        self.assertEqual(a1, a2)
        self.assertEqual(a1, a3)

    def test_countAssemblies(self):
        """Tests that the users definition of assemblies is preserved.

        .. test:: Tests that the users definition of assembilies is preserved.
            :id: TEST_REACTOR_3
            :links: REQ_REACTOR
        """
        nFuel = self.r.core.countAssemblies(Flags.FUEL)
        self.assertEqual(2, nFuel)
        nFuel_r3 = self.r.core.countAssemblies(Flags.FUEL, ring=3)
        self.assertEqual(1, nFuel_r3)
        nFuel = self.r.core.countAssemblies(Flags.FUEL, fullCore=True)
        self.assertEqual(6, nFuel)

    def test_restoreReactor(self):
        aListLength = len(self.r.core.getAssemblies())
        converter = self.r.core.growToFullCore(self.o.cs)
        converter.restorePreviousGeometry(self.o.cs, self.r)
        self.assertEqual(aListLength, len(self.r.core.getAssemblies()))

    def test_differentNuclideModels(self):
        self.assertEqual(self.o.cs["xsKernel"], "MC2v3")
        _o2, r2 = loadTestReactor(customSettings={"xsKernel": "MC2v2"})

        self.assertNotEqual(
            set(self.r.blueprints.elementsToExpand), set(r2.blueprints.elementsToExpand)
        )

        for b2, b3 in zip(r2.core.getBlocks(), self.r.core.getBlocks()):
            for element in self.r.blueprints.elementsToExpand:
                # nucspec allows elemental mass to be computed
                mass2 = b2.getMass(element.symbol)
                mass3 = b3.getMass(element.symbol)
                assert_allclose(mass2, mass3)

                constituentNucs = [nn.name for nn in element.nuclideBases if nn.a > 0]
                nuclideLevelMass3 = b3.getMass(constituentNucs)
                assert_allclose(mass3, nuclideLevelMass3)

    def test_getDominantMaterial(self):
        dominantDuct = self.r.core.getDominantMaterial(Flags.DUCT)
        dominantFuel = self.r.core.getDominantMaterial(Flags.FUEL)
        dominantCool = self.r.core.getDominantMaterial(Flags.COOLANT)

        self.assertEqual(dominantDuct.getName(), "HT9")
        self.assertEqual(dominantFuel.getName(), "UZr")
        self.assertEqual(dominantCool.getName(), "Sodium")

        self.assertEqual(list(dominantCool.getNuclides()), ["NA23"])

    def test_getSymmetryFactor(self):
        for b in self.r.core.getBlocks():
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
        for b in self.r.core.getBlocks():
            b.p.mgFlux = range(5)
            b.p.adjMgFlux = range(5)
        self.r.core.saveAllFlux()
        os.remove("allFlux.txt")

    def test_getFluxVector(self):
        class MockLib:
            numGroups = 5

        self.r.core.lib = MockLib()
        for b in self.r.core.getBlocks():
            b.p.mgFlux = range(5)
            b.p.adjMgFlux = [i + 0.1 for i in range(5)]
            b.p.extSrc = [i + 0.2 for i in range(5)]
        mgFlux = self.r.core.getFluxVector(energyOrder=1)
        adjFlux = self.r.core.getFluxVector(adjoint=True)
        srcVec = self.r.core.getFluxVector(extSrc=True)
        fluxVol = self.r.core.getFluxVector(volumeIntegrated=True)
        expFlux = [i for i in range(5) for b in self.r.core.getBlocks()]
        expAdjFlux = [i + 0.1 for b in self.r.core.getBlocks() for i in range(5)]
        expSrcVec = [i + 0.2 for b in self.r.core.getBlocks() for i in range(5)]
        expFluxVol = list(range(5)) * len(self.r.core.getBlocks())
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
        (_minI, maxI), (_minJ, maxJ), (minK, maxK) = self.r.core.getBoundingIndices()
        self.assertEqual((maxI, maxJ), (8, 8))
        self.assertEqual((minK, maxK), (0, 0))

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
        mass2 = sum([b.getMass() for b in self.r.core.getBlocks()])
        assert_allclose(mass1, mass2)

    def test_isPickleable(self):
        loaded = cPickle.loads(cPickle.dumps(self.r))

        # ensure we didn't break the current reactor
        self.assertIs(self.r.core.spatialGrid.armiObject, self.r.core)

        # make sure that the loaded reactor and grid are aligned
        self.assertIs(loaded.core.spatialGrid.armiObject, loaded.core)
        self.assertTrue(
            all(
                isinstance(key, grids.LocationBase)
                for key in loaded.core.childrenByLocator.keys()
            )
        )
        loc = loaded.core.spatialGrid[0, 0, 0]
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
        a = self.r.core[-1]  # last assembly
        b = a[-1]  # use the last block in case we ever figure out stationary blocks
        aLoc = a.spatialLocator
        self.assertIsNotNone(aLoc.grid)
        bLoc = b.spatialLocator
        self.r.core.removeAssembly(a)
        self.assertNotEqual(aLoc, a.spatialLocator)
        self.assertEqual(a.spatialLocator.grid, self.r.core.sfp.spatialGrid)

        # confirm only attached to removed assem
        self.assertIs(bLoc, b.spatialLocator)  # block location does not change
        self.assertIs(a, b.parent)
        self.assertIs(a, b.spatialLocator.grid.armiObject)

    def test_removeAssembliesInRing(self):
        aLoc = [
            self.r.core.spatialGrid.getLocatorFromRingAndPos(3, i + 1)
            for i in range(12)
        ]
        assems = {
            i: self.r.core.childrenByLocator[loc]
            for i, loc in enumerate(aLoc)
            if loc in self.r.core.childrenByLocator
        }
        self.r.core.removeAssembliesInRing(3)
        for i, a in assems.items():
            self.assertNotEqual(aLoc[i], a.spatialLocator)
            self.assertEqual(a.spatialLocator.grid, self.r.core.sfp.spatialGrid)

    def test_createAssemblyOfType(self):
        """Test creation of new assemblies."""
        # basic creation
        aOld = self.r.core.getFirstAssembly(Flags.FUEL)
        aNew = self.r.core.createAssemblyOfType(aOld.getType())
        self.assertAlmostEqual(aOld.getMass(), aNew.getMass())

        # creation with modified enrichment
        aNew2 = self.r.core.createAssemblyOfType(aOld.getType(), 0.195)
        fuelBlock = aNew2.getFirstBlock(Flags.FUEL)
        self.assertAlmostEqual(fuelBlock.getUraniumMassEnrich(), 0.195)

        # creation with modified enrichment on an expanded BOL assem.
        fuelComp = fuelBlock.getComponent(Flags.FUEL)
        bol = self.r.blueprints.assemblies[aOld.getType()]
        changer = AxialExpansionChanger()
        changer.performPrescribedAxialExpansion(bol, [fuelComp], [0.05])
        aNew3 = self.r.core.createAssemblyOfType(aOld.getType(), 0.195)
        self.assertAlmostEqual(
            aNew3.getFirstBlock(Flags.FUEL).getUraniumMassEnrich(), 0.195
        )
        self.assertAlmostEqual(aNew3.getMass(), bol.getMass())

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

    def test_removeAllAssemblies(self):
        self.assertGreater(len(self.r.core.blocksByName), 100)
        self.assertGreater(len(self.r.core.assembliesByName), 12)

        self.r.core.removeAllAssemblies()

        self.assertEqual(0, len(self.r.core.blocksByName))
        self.assertEqual(0, len(self.r.core.assembliesByName))


class CartesianReactorTests(ReactorTests):
    def setUp(self):
        self.o = buildOperatorOfEmptyCartesianBlocks()
        self.r = self.o.r

    def test_getAssemblyPitch(self):
        # Cartesian pitch should have 2 dims since it could be a rectangle that is not square.
        assert_equal(self.r.core.getAssemblyPitch(), [10.0, 16.0])

    def test_getAssembliesInSquareRing(self, exclusions=[2]):
        expectedAssemsInRing = [1, 0]
        actualAssemsInRing = []
        for ring in range(1, self.r.core.getNumRings() + 1):
            actualAssemsInRing.append(
                len(self.r.core.getAssembliesInSquareOrHexRing(ring))
            )
        self.assertSequenceEqual(actualAssemsInRing, expectedAssemsInRing)

    def test_getNuclideCategoriesLogging(self):
        """Simplest possible test of the getNuclideCategories method and its logging"""
        log = mockRunLogs.BufferLog()

        # this strange namespace-stomping is used to the test to set the logger in reactors.Core
        from armi.reactor import reactors  # pylint: disable=import-outside-toplevel

        reactors.runLog = runLog
        runLog.LOG = log

        # run the actual method in question
        self.r.core.getNuclideCategories()
        messages = log.getStdoutValue()

        self.assertIn("Nuclide categorization", messages)
        self.assertIn("Structure", messages)


if __name__ == "__main__":
    # import sys;sys.argv = ["", "ReactorTests.test_genAssembliesAddedThisCycle"]
    unittest.main()
