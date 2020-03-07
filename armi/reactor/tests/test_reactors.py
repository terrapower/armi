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
import copy
import os
import unittest

from six.moves import cPickle
from numpy.testing import assert_allclose
import armi

from armi.materials import uZr

from armi import operators
from armi import runLog
from armi import settings
from armi import tests
from armi.reactor.flags import Flags
from armi.reactor import assemblies
from armi.reactor import blocks
from armi.reactor import grids
from armi.reactor import locations
from armi.reactor import reactors
from armi.reactor.components import Hexagon
from armi.reactor.converters import geometryConverters
from armi.tests import TEST_ROOT, ARMI_RUN_PATH
from armi.utils import directoryChangers
from armi.physics.neutronics import isotopicDepletion

TEST_REACTOR = None  # pickled string of test reactor (for fast caching)


def buildOperatorOfEmptyBlocks(customSettings=None):
    """
    Builds a operator w/ a reactor object with some assemblies and blocks, but all are empty

    Doesn't depend on inputs and loads quickly.
    """
    settings.setMasterCs(None)  # clear
    cs = settings.getMasterCs()  # fetch new
    cs["db"] = False  # stop use of database
    if customSettings is not None:
        cs.update(customSettings)
    r = tests.getEmptyHexReactor()
    o = operators.Operator(cs)
    o.initializeInterfaces(r)
    a = assemblies.HexAssembly("fuel")
    a.spatialGrid = grids.axialUnitGrid(1)
    b = blocks.HexBlock("TestBlock")
    b.setType("fuel")
    dims = {"Tinput": 600, "Thot": 600, "op": 16.0, "ip": 1.0, "mult": 1}
    c = Hexagon("fuel", uZr.UZr(), **dims)
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
        Path to the directory of the armiRun.yaml input file.

    customSettings : dict with str keys and values of any type
        For each key in customSettings, the cs which is loaded from the
        armiRun.yaml will be overwritten to the value given in customSettings
        for that key.

    Returns
    -------
    o : Operator
    r : Reactor
    """
    # TODO: it would be nice to have this be more stream-oriented. Juggling files is
    # devilishly difficult.
    global TEST_REACTOR
    isotopicDepletion.applyDefaultBurnChain()
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
        for settingKey, settingVal in customSettings.items():
            cs[settingKey] = settingVal

    if "verbosity" not in customSettings:
        runLog.setVerbosity("error")
    settings.setMasterCs(cs)
    cs["stationaryBlocks"] = []
    cs["nCycles"] = 3

    o = operators.factory(cs)
    r = reactors.loadFromCs(cs)
    o.initializeInterfaces(r)

    # put some stuff in the SFP too.
    for a in range(10):
        a = o.r.blueprints.constructAssem(o.r.core.geomType, o.cs, name="feed fuel")
        o.r.core.sfp.add(a)

    o.r.core.regenAssemblyLists()

    if isPickeledReactor:
        # cache it for fast load for other future tests
        # protocol=2 allows for classes with __slots__ but not __getstate__ to be pickled
        TEST_REACTOR = cPickle.dumps((o, o.r, assemblies.getAssemNum()), protocol=2)
    return o, o.r


class _ReactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # prepare the input files. This is important so the unit tests run from wherever
        # they need to run from.
        cls.directoryChanger = directoryChangers.DirectoryChanger(TEST_ROOT)
        cls.directoryChanger.open()

    @classmethod
    def tearDownClass(cls):
        cls.directoryChanger.close()


class ReactorTests(_ReactorTests):
    def setUp(self):
        self.o, self.r = loadTestReactor(self.directoryChanger.destination)

    def testWhichAssemblyIsIn(self):
        a = self.r.core.whichAssemblyIsIn(2, 1)
        loc = a.getLocationObject()  # pylint: disable=maybe-no-member
        self.assertEqual(loc.i1, 2)
        self.assertEqual(loc.i2, 1)

        # check ring capabilities
        allA = self.r.core.whichAssemblyIsIn(4)
        fuel = self.r.core.whichAssemblyIsIn(4, typeFlags=Flags.FUEL)
        nonFuel = self.r.core.whichAssemblyIsIn(4, excludeFlags=Flags.FUEL)

        self.assertGreater(len(allA), 0)
        self.assertGreater(len(fuel), 0)
        self.assertGreaterEqual(len(allA), len(fuel))
        self.assertLess(len(nonFuel), len(fuel))

        for a in fuel:
            self.assertTrue(a.hasFlags(Flags.FUEL))

    def testGetTotalParam(self):
        # verify that the block params are being read.
        val = self.r.core.getTotalBlockParam("power")
        val2 = self.r.core.getTotalBlockParam("power", addSymmetricPositions=True)
        self.assertEqual(val2 / self.r.core.powerMultiplier, val)

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

    def test_countBlocksOfType(self):
        numControlBlocks = self.r.core.countBlocksWithFlags([Flags.DUCT, Flags.CONTROL])

        self.assertEqual(numControlBlocks, 3)

        numControlBlocks = self.r.core.countBlocksWithFlags(
            [Flags.DUCT, Flags.CONTROL, Flags.FUEL], Flags.CONTROL
        )
        self.assertEqual(numControlBlocks, 3)

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

    def test_findNeighbors(self):

        a = self.r.core.whichAssemblyIsIn(1, 1)
        neighbs = self.r.core.findNeighbors(
            a, duplicateAssembliesOnReflectiveBoundary=True
        )
        locs = [a.getLocation() for a in neighbs]
        self.assertEqual(len(neighbs), 6)
        self.assertIn("A2001", locs)
        self.assertIn("A2002", locs)
        self.assertEqual(locs.count("A2001"), 3)

        a = self.r.core.whichAssemblyIsIn(1, 1)
        neighbs = self.r.core.findNeighbors(
            a, duplicateAssembliesOnReflectiveBoundary=True
        )
        locs = [a.getLocation() for a in neighbs]
        self.assertEqual(locs, ["A2001", "A2002"] * 3, 6)

        a = self.r.core.whichAssemblyIsIn(2, 2)

        neighbs = self.r.core.findNeighbors(
            a, duplicateAssembliesOnReflectiveBoundary=True
        )
        locs = [a.getLocation() for a in neighbs]
        self.assertEqual(len(neighbs), 6)
        self.assertEqual(locs, ["A3002", "A3003", "A3012", "A2001", "A1001", "A2001"])

        # try with edge assemblies
        # With edges, the neighbor is the one that's actually next to it.
        converter = geometryConverters.EdgeAssemblyChanger()
        converter.addEdgeAssemblies(self.r.core)
        a = self.r.core.whichAssemblyIsIn(2, 2)
        neighbs = self.r.core.findNeighbors(
            a, duplicateAssembliesOnReflectiveBoundary=True
        )
        locs = [a.getLocation() for a in neighbs]
        self.assertEqual(len(neighbs), 6)
        # in this case no locations that aren't actually in the core should be returned
        self.assertEqual(locs, ["A3002", "A3003", "A3004", "A2001", "A1001", "A2001"])
        converter.removeEdgeAssemblies(self.r.core)

        # try with full core
        self.r.core.growToFullCore(self.o.cs)
        a = self.r.core.whichAssemblyIsIn(3, 4)
        neighbs = self.r.core.findNeighbors(a)
        self.assertEqual(len(neighbs), 6)
        locs = [a.getLocation() for a in neighbs]
        for loc in ["A2002", "A2003", "A3003", "A3005", "A4005", "A4006"]:
            self.assertIn(loc, locs)

        a = self.r.core.whichAssemblyIsIn(2, 2)
        neighbs = self.r.core.findNeighbors(a)
        locs = [a.getLocation() for a in neighbs]
        for loc in ["A1001", "A2001", "A2003", "A3002", "A3003", "A3004"]:
            self.assertIn(loc, locs)

        # Try the duplicate option in full core as well
        a = self.r.core.whichAssemblyIsIn(2, 2)
        neighbs = self.r.core.findNeighbors(
            a, duplicateAssembliesOnReflectiveBoundary=True
        )
        locs = [a.getLocation() for a in neighbs]
        self.assertEqual(len(neighbs), 6)
        self.assertEqual(locs, ["A3002", "A3003", "A3004", "A2003", "A1001", "A2001"])

    def test_getAssembliesInCircularRing(self):
        expectedAssemsInRing = [5, 6, 8, 10, 12, 16, 14, 2]
        actualAssemsInRing = []
        for ring in range(1, self.r.core.getNumRings()):
            actualAssemsInRing.append(
                len(self.r.core.getAssembliesInCircularRing(ring))
            )
        self.assertSequenceEqual(actualAssemsInRing, expectedAssemsInRing)

    def test_getAssembliesInSquareOrHexRing(self):
        expectedAssemsInRing = [1, 2, 4, 6, 8, 10, 12, 14, 16]
        actualAssemsInRing = []
        for ring in range(1, self.r.core.getNumRings() + 1):
            actualAssemsInRing.append(
                len(self.r.core.getAssembliesInSquareOrHexRing(ring))
            )
        self.assertSequenceEqual(actualAssemsInRing, expectedAssemsInRing)

    def test_getAssembliesInSector(self):
        allAssems = self.r.core.getAssemblies()
        fullSector = self.r.core.getAssembliesInSector(0, 360)
        self.assertGreaterEqual(
            len(fullSector), len(allAssems)
        )  # could be > due to edge assems
        third = self.r.core.getAssembliesInSector(0, 30)
        self.assertAlmostEqual(
            25, len(third)
        )  # could solve this analytically based on test core size
        oneLine = self.r.core.getAssembliesInSector(0, 0.001)
        self.assertAlmostEqual(5, len(oneLine))  # same here

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

    def test_getNumAssembliesWithAllRingsFilledOut(self):
        nRings = self.r.core.getNumRings(indexBased=True)
        nAssmWithBlanks = self.r.core.getNumAssembliesWithAllRingsFilledOut(nRings)
        self.assertEqual(77, nAssmWithBlanks)

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
            loc = b.getLocationObject()
            if loc.i1 == 1 and loc.i2 == 1:
                self.assertEqual(sym, 3.0)
            else:
                self.assertEqual(sym, 1.0)

    def test_getAssembliesOnSymmetryLine(self):
        center = self.r.core.getAssembliesOnSymmetryLine(locations.BOUNDARY_CENTER)
        self.assertEqual(len(center), 1)
        upper = self.r.core.getAssembliesOnSymmetryLine(locations.BOUNDARY_120_DEGREES)
        self.assertEqual(len(upper), 0)
        lower = self.r.core.getAssembliesOnSymmetryLine(locations.BOUNDARY_0_DEGREES)
        self.assertGreater(len(lower), 1)

    def test_saveAllFlux(self):
        # need a lightweight library to indicate number of groups.
        class MockLib(object):
            numGroups = 5

        self.r.core.lib = MockLib()
        for b in self.r.core.getBlocks():
            b.p.mgFlux = range(5)
            b.p.adjMgFlux = range(5)
        self.r.core.saveAllFlux()
        os.remove("allFlux.txt")

    def test_getFuelBottomHeight(self):

        for a in self.r.core.getAssemblies(Flags.FUEL):
            if a[0].hasFlags(Flags.FUEL):
                a[0].setType("mud")
            a[1].setType("fuel")
        fuelBottomHeightRef = self.r.core.getFirstAssembly(Flags.FUEL)[0].getHeight()
        fuelBottomHeightInCm = self.r.core.getFuelBottomHeight()

        self.assertEqual(fuelBottomHeightInCm, fuelBottomHeightRef)

    def test_whichBlockIsAtCoords(self):

        b = self.r.core.whichBlockIsAtCoords(0, 0, 0)
        centralAssem = self.r.core.whichAssemblyIsIn(1, 1)
        self.assertEqual(b, centralAssem[0])
        b = self.r.core.whichBlockIsAtCoords(0, 0, 50)
        self.assertEqual(b.parent, centralAssem)
        self.assertNotEqual(b, centralAssem[0])

    def test_getGridBounds(self):
        (_minI, maxI), (_minJ, maxJ), (minK, maxK) = self.r.core.getBoundingIndices()
        self.assertEqual((maxI, maxJ), (8, 8))
        self.assertEqual((minK, maxK), (0, 0))

    def test_locations(self):
        a = self.r.core.whichAssemblyIsIn(3, 2)
        assert_allclose(a.spatialLocator.indices, [1, 1, 0])
        for bi, b in enumerate(a):
            assert_allclose(b.spatialLocator.getCompleteIndices(), [1, 1, bi])
        self.assertEqual(a.getLocation(), "A3002")
        loc = a.getLocationObject()
        self.assertEqual(str(loc), "A3002")
        self.assertEqual(a[0].getLocation(), "A3002A")

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
        self.assertIsNone(a.spatialLocator.grid)

        # confirm only attached to removed assem
        self.assertIs(bLoc, b.spatialLocator)  # block location does not change
        self.assertIs(a, b.parent)
        self.assertIs(a, b.spatialLocator.grid.armiObject)

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
        bol.axiallyExpand(0.05, fuelComp.getNuclides())
        aNew3 = self.r.core.createAssemblyOfType(aOld.getType(), 0.195)
        self.assertAlmostEqual(
            aNew3.getFirstBlock(Flags.FUEL).getUraniumMassEnrich(), 0.195
        )
        self.assertAlmostEqual(aNew3.getMass(), bol.getMass() / 3.0)


if __name__ == "__main__":
    import sys

    # sys.argv = ["", "ReactorTests.test_genAssembliesAddedThisCycle"]
    unittest.main()
