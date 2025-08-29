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
"""Tests blocks.py."""

import copy
import io
import math
import os
import shutil
import unittest
from glob import glob
from unittest.mock import MagicMock, patch

import numpy as np
from numpy.testing import assert_allclose, assert_array_equal

from armi import materials, runLog, settings, tests
from armi.nucDirectory import nucDir, nuclideBases
from armi.nuclearDataIO import xsCollections
from armi.nuclearDataIO.cccc import isotxs
from armi.physics.neutronics import GAMMA, NEUTRON
from armi.physics.neutronics.settings import (
    CONF_LOADING_FILE,
    CONF_XS_KERNEL,
)
from armi.reactor import blocks, blueprints, components, geometry, grids
from armi.reactor.components import basicShapes, complexShapes
from armi.reactor.flags import Flags
from armi.reactor.tests.test_assemblies import makeTestAssembly
from armi.testing import loadTestReactor
from armi.testing.singleMixedAssembly import buildMixedPinAssembly
from armi.tests import ISOAA_PATH, TEST_ROOT
from armi.utils import densityTools, hexagon, units
from armi.utils.directoryChangers import TemporaryDirectoryChanger
from armi.utils.units import (
    ASCII_LETTER_A,
    ASCII_LETTER_Z,
    MOLES_PER_CC_TO_ATOMS_PER_BARN_CM,
    ASCII_LETTER_a,
)

NUM_PINS_IN_TEST_BLOCK = 217


def buildSimpleFuelBlock():
    """Return a simple hex block containing fuel, clad, duct, and coolant."""
    b = blocks.HexBlock("fuel", height=10.0)

    fuelDims = {"Tinput": 25.0, "Thot": 600, "od": 0.76, "id": 0.00, "mult": 127.0}
    cladDims = {"Tinput": 25.0, "Thot": 450, "od": 0.80, "id": 0.77, "mult": 127.0}
    ductDims = {"Tinput": 25.0, "Thot": 400, "op": 16, "ip": 15.3, "mult": 1.0}
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
    duct = components.Hexagon("duct", "HT9", **ductDims)
    coolant = components.DerivedShape("coolant", "Sodium", **coolDims)
    intercoolant = components.Hexagon("intercoolant", "Sodium", **intercoolantDims)

    b.add(fuel)
    b.add(clad)
    b.add(duct)
    b.add(coolant)
    b.add(intercoolant)

    return b


def buildLinkedFuelBlock():
    """Return a simple hex block containing linked bond."""
    b = blocks.HexBlock("fuel", height=10.0)

    fuelDims = {"Tinput": 25.0, "Thot": 600, "od": 0.76, "id": 0.00, "mult": 127.0}
    bondDims = {
        "Tinput": 25.0,
        "Thot": 450,
        "od": "clad.id",
        "id": "fuel.od",
        "mult": 127.0,
    }
    cladDims = {"Tinput": 25.0, "Thot": 450, "od": 0.80, "id": 0.77, "mult": 127.0}
    ductDims = {"Tinput": 25.0, "Thot": 400, "op": 16, "ip": 15.3, "mult": 1.0}
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
    bondDims["components"] = {"clad": clad, "fuel": fuel}
    bond = components.Circle("bond", "HT9", **bondDims)
    duct = components.Hexagon("duct", "HT9", **ductDims)
    coolant = components.DerivedShape("coolant", "Sodium", **coolDims)
    intercoolant = components.Hexagon("intercoolant", "Sodium", **intercoolantDims)

    b.add(fuel)
    b.add(bond)
    b.add(clad)
    b.add(duct)
    b.add(coolant)
    b.add(intercoolant)

    return b


def loadTestBlock(cold=True, depletable=False) -> blocks.HexBlock:
    """Build an annular test block for evaluating unit tests."""
    caseSetting = settings.Settings()
    caseSetting[CONF_XS_KERNEL] = "MC2v2"
    runLog.setVerbosity("error")
    caseSetting["nCycles"] = 1
    r = tests.getEmptyHexReactor()

    assemNum = 3
    block = blocks.HexBlock("TestHexBlock")
    block.setType("defaultType")
    block.p.nPins = NUM_PINS_IN_TEST_BLOCK
    assembly = makeTestAssembly(assemNum, 1, r=r)

    # NOTE: temperatures are supposed to be in C
    coldTemp = 25.0
    hotTempCoolant = 430.0
    hotTempStructure = 25.0 if cold else hotTempCoolant
    hotTempFuel = 25.0 if cold else 600.0

    fuelDims = {
        "Tinput": coldTemp,
        "Thot": hotTempFuel,
        "od": 0.84,
        "id": 0.6,
        "mult": NUM_PINS_IN_TEST_BLOCK,
    }
    fuel = components.Circle("fuel", "UZr", **fuelDims)
    if depletable:
        fuel.p.flags = Flags.fromString("fuel depletable")

    bondDims = {
        "Tinput": coldTemp,
        "Thot": hotTempCoolant,
        "od": "fuel.id",
        "id": 0.3,
        "mult": NUM_PINS_IN_TEST_BLOCK,
    }
    bondDims["components"] = {"fuel": fuel}
    bond = components.Circle("bond", "Sodium", **bondDims)

    annularVoidDims = {
        "Tinput": hotTempStructure,
        "Thot": hotTempStructure,
        "od": "bond.id",
        "id": 0.0,
        "mult": NUM_PINS_IN_TEST_BLOCK,
    }
    annularVoidDims["components"] = {"bond": bond}
    annularVoid = components.Circle("annular void", "Void", **annularVoidDims)

    innerLinerDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "od": 0.90,
        "id": 0.85,
        "mult": NUM_PINS_IN_TEST_BLOCK,
    }
    innerLiner = components.Circle("inner liner", "Graphite", **innerLinerDims)

    fuelLinerGapDims = {
        "Tinput": hotTempStructure,
        "Thot": hotTempStructure,
        "od": "inner liner.id",
        "id": "fuel.od",
        "mult": NUM_PINS_IN_TEST_BLOCK,
    }
    fuelLinerGapDims["components"] = {"inner liner": innerLiner, "fuel": fuel}
    fuelLinerGap = components.Circle("gap1", "Void", **fuelLinerGapDims)

    outerLinerDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "od": 0.95,
        "id": 0.90,
        "mult": NUM_PINS_IN_TEST_BLOCK,
    }
    outerLiner = components.Circle("outer liner", "HT9", **outerLinerDims)

    linerLinerGapDims = {
        "Tinput": hotTempStructure,
        "Thot": hotTempStructure,
        "od": "outer liner.id",
        "id": "inner liner.od",
        "mult": NUM_PINS_IN_TEST_BLOCK,
    }
    linerLinerGapDims["components"] = {
        "outer liner": outerLiner,
        "inner liner": innerLiner,
    }
    linerLinerGap = components.Circle("gap2", "Void", **linerLinerGapDims)

    claddingDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "od": 1.05,
        "id": 0.95,
        "mult": NUM_PINS_IN_TEST_BLOCK,
    }
    cladding = components.Circle("clad", "HT9", **claddingDims)
    if depletable:
        cladding.p.flags = Flags.fromString("clad depletable")

    linerCladGapDims = {
        "Tinput": hotTempStructure,
        "Thot": hotTempStructure,
        "od": "clad.id",
        "id": "outer liner.od",
        "mult": NUM_PINS_IN_TEST_BLOCK,
    }
    linerCladGapDims["components"] = {"clad": cladding, "outer liner": outerLiner}
    linerCladGap = components.Circle("gap3", "Void", **linerCladGapDims)

    wireDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "od": 0.1,
        "id": 0.0,
        "axialPitch": 30.0,
        "helixDiameter": 1.1,
        "mult": NUM_PINS_IN_TEST_BLOCK,
    }
    wire = components.Helix("wire", "HT9", **wireDims)
    if depletable:
        wire.p.flags = Flags.fromString("wire depletable")

    coolantDims = {"Tinput": hotTempCoolant, "Thot": hotTempCoolant}
    coolant = components.DerivedShape("coolant", "Sodium", **coolantDims)

    ductDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "ip": 16.6,
        "op": 17.3,
        "mult": 1,
    }
    duct = components.Hexagon("duct", "HT9", **ductDims)
    if depletable:
        duct.p.flags = Flags.fromString("duct depletable")

    interDims = {
        "Tinput": hotTempCoolant,
        "Thot": hotTempCoolant,
        "op": 17.8,
        "ip": "duct.op",
        "mult": 1,
    }
    interDims["components"] = {"duct": duct}
    interSodium = components.Hexagon("interCoolant", "Sodium", **interDims)

    block.add(annularVoid)
    block.add(bond)
    block.add(fuel)
    block.add(fuelLinerGap)
    block.add(innerLiner)
    block.add(linerLinerGap)
    block.add(outerLiner)
    block.add(linerCladGap)
    block.add(cladding)

    block.add(wire)
    block.add(coolant)
    block.add(duct)
    block.add(interSodium)

    block.setHeight(16.0)

    block.autoCreateSpatialGrids(r.core.spatialGrid)
    assembly.add(block)
    r.core.add(assembly)
    return block


def applyDummyData(block):
    """Add some dummy data to a block for physics-like tests."""
    # typical SFR-ish flux in 1/cm^2/s
    flux = [
        161720716762.12997,
        2288219224332.647,
        11068159130271.139,
        26473095948525.742,
        45590249703180.945,
        78780459664094.23,
        143729928505629.06,
        224219073208464.06,
        229677567456769.22,
        267303906113313.16,
        220996878365852.22,
        169895433093246.28,
        126750484612975.31,
        143215138794766.53,
        74813432842005.5,
        32130372366225.85,
        21556243034771.582,
        6297567411518.368,
        22365198294698.45,
        12211256796917.86,
        5236367197121.363,
        1490736020048.7847,
        1369603135573.731,
        285579041041.55945,
        73955783965.98692,
        55003146502.73623,
        18564831886.20426,
        4955747691.052108,
        3584030491.076041,
        884015567.3986057,
        4298964991.043116,
        1348809158.0353086,
        601494405.293505,
    ]
    xslib = isotxs.readBinary(ISOAA_PATH)
    # Slight hack here because the test block was created by hand rather than via blueprints and so
    # elemental expansion of isotopics did not occur. But, the ISOTXS library being used did go
    # through an isotopic expansion, so we map nuclides here.
    xslib._nuclides["NAAA"] = xslib._nuclides["NA23AA"]
    xslib._nuclides["WAA"] = xslib._nuclides["W184AA"]
    xslib._nuclides["MNAA"] = xslib._nuclides["MN55AA"]
    block.p.mgFlux = flux
    block.core.lib = xslib


def getComponentData(component):
    density = 0.0
    for nuc in component.getNuclides():
        density += (
            component.getNumberDensity(nuc) * nucDir.getAtomicWeight(nuc) / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
        )
    volume = component.getVolume()
    mass = component.getMass()
    return component, density, volume, mass


class TestDetailedNDensUpdate(unittest.TestCase):
    def test_updateDetailedNdens(self):
        from armi.reactor.blueprints.tests.test_blockBlueprints import FULL_BP

        cs = settings.Settings()
        with io.StringIO(FULL_BP) as stream:
            bps = blueprints.Blueprints.load(stream)
            bps._prepConstruction(cs)
            self.r = tests.getEmptyHexReactor()
            self.r.blueprints = bps
            a = makeTestAssembly(numBlocks=1, assemNum=0)
            a.add(buildSimpleFuelBlock())
            self.r.core.add(a)

        # get first block in assembly with 'fuel' key
        block = self.r.core[0][0]
        # get nuclides in first component in block
        adjList = block[0].getNuclides()
        block.p.detailedNDens = np.array([1.0])
        block.p.pdensDecay = 1.0
        block._updateDetailedNdens(frac=0.5, adjustList=adjList)
        self.assertEqual(block.p.pdensDecay, 0.5)
        self.assertEqual(block.p.detailedNDens, np.array([0.5]))


class TestValidateSFPSpatialGrids(unittest.TestCase):
    def test_noSFPExists(self):
        """Validate the spatial grid for a new SFP is None if it was not provided."""
        # copy the inputs, so we can modify them
        with TemporaryDirectoryChanger() as newDir:
            oldDir = os.path.join(TEST_ROOT, "smallestTestReactor")
            newDir2 = os.path.join(newDir.destination, "smallestTestReactor")
            shutil.copytree(oldDir, newDir2)

            # cut out the SFP grid in the input file
            testFile = os.path.join(newDir2, "refSmallestReactor.yaml")
            txt = open(testFile, "r").read()
            txt = txt.split("symmetry: full")[0]
            open(testFile, "w").write(txt)

            # verify there is no spatial grid defined
            _o, r = loadTestReactor(newDir2, inputFileName="armiRunSmallest.yaml")
            self.assertIsNone(r.excore.sfp.spatialGrid)

    def test_SFPSpatialGridExists(self):
        """Validate the spatial grid for a new SFP is not None if it was provided."""
        _o, r = loadTestReactor(
            os.path.join(TEST_ROOT, "smallestTestReactor"),
            inputFileName="armiRunSmallest.yaml",
        )
        self.assertIsNotNone(r.excore.sfp.spatialGrid)

    def test_orientationBOL(self):
        _o, r = loadTestReactor(
            os.path.join(TEST_ROOT, "smallestTestReactor"),
            inputFileName="armiRunSmallest.yaml",
        )

        # Test the null-case; these should all be zero.
        for a in r.core.iterChildren():
            self.assertIsNone(a.p.orientation)


class Block_TestCase(unittest.TestCase):
    def setUp(self):
        self.block = loadTestBlock()
        self._hotBlock = loadTestBlock(cold=False)
        self._deplBlock = loadTestBlock(depletable=True)

    def test_getSmearDensity(self):
        cur = self.block.getSmearDensity()
        ref = (self.block.getDim(Flags.FUEL, "od") ** 2 - self.block.getDim(Flags.FUEL, "id") ** 2) / self.block.getDim(
            Flags.LINER, "id"
        ) ** 2
        places = 10
        self.assertAlmostEqual(cur, ref, places=places)

        # test with liner instead of clad
        ref = (self.block.getDim(Flags.FUEL, "od") ** 2 - self.block.getDim(Flags.FUEL, "id") ** 2) / self.block.getDim(
            Flags.LINER, "id"
        ) ** 2
        cur = self.block.getSmearDensity()
        self.assertAlmostEqual(
            cur,
            ref,
            places=places,
            msg="Incorrect getSmearDensity with liner. Got {0}. Should be {1}".format(cur, ref),
        )

        # test with annular fuel.
        fuelDims = {
            "Tinput": 273.0,
            "Thot": 273.0,
            "od": 0.87,
            "id": 0.2,
            "mult": 271.0,
        }
        self.fuelComponent = components.Circle("fuel", "UZr", **fuelDims)

        ref = (self.block.getDim(Flags.FUEL, "od") ** 2 - self.block.getDim(Flags.FUEL, "id") ** 2) / self.block.getDim(
            Flags.LINER, "id"
        ) ** 2
        cur = self.block.getSmearDensity()
        self.assertAlmostEqual(
            cur,
            ref,
            places=places,
            msg="Incorrect getSmearDensity with annular fuel. Got {0}. Should be {1}".format(cur, ref),
        )

    def test_getSmearDensityMultipleLiner(self):
        numLiners = sum(1 for c in self.block if "liner" in c.name and "gap" not in c.name)
        self.assertEqual(
            numLiners,
            2,
            "self.block needs at least 2 liners for this test to be functional.",
        )
        cur = self.block.getSmearDensity()
        ref = (self.block.getDim(Flags.FUEL, "od") ** 2 - self.block.getDim(Flags.FUEL, "id") ** 2) / self.block.getDim(
            Flags.INNER | Flags.LINER, "id"
        ) ** 2
        self.assertAlmostEqual(cur, ref, places=10)

    def test_getSmearDensityEdgeCases(self):
        # show smear density is not computed for non-fuel blocks
        b0 = blocks.Block("DummyReflectorBlock")
        self.assertEqual(b0.getSmearDensity(), 0.0)

        # show smear density is only defined for pinned fuel blocks
        b1 = blocks.HexBlock("TestFuelHexBlock")
        b1.setType("fuel")
        b1.p.nPins = 0
        fuel = components.Circle("fuel", "UZr", Tinput=25.0, Thot=25.0, od=0.84, id=0.6, mult=0)
        b1.add(fuel)
        self.assertEqual(b1.getSmearDensity(), 0.0)

    def test_computeSmearDensity(self):
        # test the null case
        smearDensity = blocks.Block.computeSmearDensity(123.4, [], True)
        self.assertEqual(smearDensity, 0.0)

        smearDensity = blocks.Block.computeSmearDensity(123.4, [], False)
        self.assertEqual(smearDensity, 0.0)

        # test one circle component
        circles = self.block.getComponentsOfShape(components.Circle)
        smearDensity = blocks.Block.computeSmearDensity(123.4, [circles[0]], True)
        self.assertEqual(smearDensity, 0.0)

        # use the test block
        clads = set(self.block.getComponents(Flags.CLAD)).intersection(set(circles))
        cladID = np.mean([clad.getDimension("id", cold=True) for clad in clads])
        sortedCircles = self.block.getSortedComponentsInsideOfComponent(circles.pop())

        fuelCompArea = sum(f.getArea(cold=True) for f in self.block.getComponents(Flags.FUEL))
        innerCladdingArea = math.pi * (cladID**2) / 4.0 * self.block.getNumComponents(Flags.FUEL)
        unmovableCompArea = sum(
            c.getArea(cold=True)
            for c in sortedCircles
            if not c.isFuel() and not c.hasFlags([Flags.SLUG, Flags.DUMMY]) and c.containsSolidMaterial()
        )

        refSmearDensity = fuelCompArea / (innerCladdingArea - unmovableCompArea)
        smearDensity = blocks.Block.computeSmearDensity(153.81433981516477, sortedCircles, True)
        self.assertAlmostEqual(smearDensity, refSmearDensity, places=10)

    def test_timeNodeParams(self):
        self.block.p["buRate", 3] = 0.1
        self.assertEqual(0.1, self.block.p[("buRate", 3)])

    def test_getType(self):
        ref = "plenum pin"
        self.block.setType(ref)
        cur = self.block.getType()
        self.assertEqual(cur, ref)
        self.assertTrue(self.block.hasFlags(Flags.PLENUM))
        self.assertTrue(self.block.hasFlags(Flags.PLENUM | Flags.PIN))
        self.assertTrue(self.block.hasFlags(Flags.PLENUM | Flags.PIN, exact=True))
        self.assertFalse(self.block.hasFlags(Flags.PLENUM, exact=True))

    def test_hasFlags(self):
        self.block.setType("feed fuel")

        cur = self.block.hasFlags(Flags.FEED | Flags.FUEL)
        self.assertTrue(cur)

        cur = self.block.hasFlags(Flags.PLENUM)
        self.assertFalse(cur)

    def test_setType(self):
        self.block.setType("igniter fuel")

        self.assertEqual("igniter fuel", self.block.getType())
        self.assertTrue(self.block.hasFlags(Flags.IGNITER | Flags.FUEL))

        self.block.adjustUEnrich(0.0001)
        self.block.setType("feed fuel")

        self.assertTrue(self.block.hasFlags(Flags.FEED | Flags.FUEL))
        self.assertTrue(self.block.hasFlags(Flags.FUEL))
        self.assertFalse(self.block.hasFlags(Flags.IGNITER | Flags.FUEL))

    def test_duplicate(self):
        Block2 = blocks.Block.createHomogenizedCopy(self.block)
        originalComponents = self.block.getComponents()
        newComponents = Block2.getComponents()
        for c1, c2 in zip(originalComponents, newComponents):
            self.assertEqual(c1.getName(), c2.getName())
            a1, a2 = c1.getArea(), c2.getArea()
            self.assertIsNot(c1, c2)
            self.assertAlmostEqual(
                a1,
                a2,
                msg="The area of {0}={1} but the area of {2} in the copy={3}".format(c1, a1, c2, a2),
            )
            for key in c2.DIMENSION_NAMES:
                dim = c2.p[key]
                if isinstance(dim, tuple):
                    self.assertNotIn(dim[0], originalComponents)
                    self.assertIn(dim[0], newComponents)

        ref = self.block.getMass()
        cur = Block2.getMass()
        places = 6
        self.assertAlmostEqual(ref, cur, places=places)

        ref = self.block.getArea()
        cur = Block2.getArea()
        places = 6
        self.assertAlmostEqual(ref, cur, places=places)

        ref = self.block.getHeight()
        cur = Block2.getHeight()
        places = 6
        self.assertAlmostEqual(ref, cur, places=places)

        self.assertEqual(self.block.p.flags, Block2.p.flags)

    def test_homogenizedMixture(self):
        """
        Confirms homogenized blocks have correct properties.

        .. test:: Homogenize the compositions of a block.
            :id: T_ARMI_BLOCK_HOMOG
            :tests: R_ARMI_BLOCK_HOMOG
        """
        args = [False, True]  # pinSpatialLocator argument
        expectedShapes = [
            [basicShapes.Hexagon],
            [basicShapes.Hexagon, basicShapes.Circle],
        ]

        for arg, shapes in zip(args, expectedShapes):
            homogBlock = self.block.createHomogenizedCopy(pinSpatialLocators=arg)
            for shapeType in shapes:
                for c in homogBlock.getComponents():
                    if isinstance(c, shapeType):
                        print(c)
                        break
                else:
                    # didn't find the homogenized hex in the block copy
                    self.assertTrue(False, f"{self.block} does not have a {shapeType} component!")
            if arg:
                # check that homogenized block has correct pin coordinates
                self.assertEqual(self.block.getNumPins(), homogBlock.getNumPins())
                self.assertEqual(self.block.p.nPins, homogBlock.p.nPins)
                pinCoords = self.block.getPinCoordinates()
                homogPinCoords = homogBlock.getPinCoordinates()
                for refXYZ, homogXYZ in zip(list(pinCoords), list(homogPinCoords)):
                    self.assertListEqual(list(refXYZ), list(homogXYZ))

            cur = homogBlock.getMass()
            self.assertAlmostEqual(self.block.getMass(), homogBlock.getMass())

            self.assertEqual(homogBlock.getType(), self.block.getType())
            self.assertEqual(homogBlock.p.flags, self.block.p.flags)
            self.assertEqual(homogBlock.macros, self.block.macros)
            self.assertEqual(homogBlock._lumpedFissionProducts, self.block._lumpedFissionProducts)

            ref = self.block.getArea()
            cur = homogBlock.getArea()
            places = 6
            self.assertAlmostEqual(ref, cur, places=places)

            ref = self.block.getHeight()
            cur = homogBlock.getHeight()
            places = 6
            self.assertAlmostEqual(ref, cur, places=places)

    def test_getXsType(self):
        self.cs = settings.Settings()
        newSettings = {CONF_LOADING_FILE: os.path.join(TEST_ROOT, "refSmallReactor.yaml")}
        self.cs = self.cs.modified(newSettings=newSettings)

        self.block.p.xsType = "B"
        cur = self.block.p.xsType
        ref = "B"
        self.assertEqual(cur, ref)

        _oldBuGroups = self.cs["buGroups"]
        newSettings = {"buGroups": [100]}
        self.cs = self.cs.modified(newSettings=newSettings)

        self.block.p.xsType = "BB"
        cur = self.block.p.xsType
        ref = "BB"
        self.assertEqual(cur, ref)

    def test_27b_setEnvGroup(self):
        type_ = "A"
        self.block.p.envGroup = type_
        cur = self.block.p.envGroupNum
        ref = ord(type_) - ASCII_LETTER_A
        self.assertEqual(cur, ref)

        typeNumber = 25  # this is Z due to 0 based numbers
        self.block.p.envGroupNum = typeNumber
        cur = self.block.p.envGroup
        ref = chr(typeNumber + ASCII_LETTER_A)
        self.assertEqual(cur, ref)
        self.assertEqual(cur, "Z")

        before_a = ASCII_LETTER_a - 1
        type_ = "a"
        self.block.p.envGroup = type_
        cur = self.block.p.envGroupNum
        ref = ord(type_) - (before_a) + (ASCII_LETTER_Z - ASCII_LETTER_A)
        self.assertEqual(cur, ref)

        typeNumber = 26  # this is a due to 0 based numbers
        self.block.p.envGroupNum = typeNumber
        cur = self.block.p.envGroup
        self.assertEqual(cur, "a")

        type_ = "z"
        self.block.p.envGroup = type_
        cur = self.block.p.envGroupNum
        ref = ord(type_) - before_a + (ASCII_LETTER_Z - ASCII_LETTER_A)
        self.assertEqual(cur, ref)

        typeNumber = 26 * 2 - 1  # 2x letters in alpha with 0 based index
        self.block.p.envGroupNum = typeNumber
        cur = self.block.p.envGroup
        ref = chr((typeNumber - 26) + ASCII_LETTER_a)
        self.assertEqual(cur, ref)
        self.assertEqual(cur, "z")

    def test_setZeroHeight(self):
        """Test that demonstrates that a block's height can be set to zero."""
        b = buildSimpleFuelBlock()

        # Check for a DerivedShape component
        self.assertEqual(len([c for c in b if c.__class__ is components.DerivedShape]), 1)
        m1 = b.getMass()
        v1 = b.getVolume()
        a1 = b.getArea()
        nd1 = copy.deepcopy(b.getNumberDensities())
        h1 = b.getHeight()
        self.assertNotEqual(h1, 0.0)

        # Set height to 0.0
        b.setHeight(0.0)
        m2 = b.getMass()
        v2 = b.getVolume()
        a2 = b.getArea()
        nd2 = copy.deepcopy(b.getNumberDensities())
        h2 = b.getHeight()

        self.assertEqual(m2, 0.0)
        self.assertEqual(v2, 0.0)
        self.assertEqual(h2, 0.0)
        self.assertAlmostEqual(a2, a1)
        for nuc, ndens in nd2.items():
            self.assertEqual(ndens, 0.0, msg=(f"Number density of {nuc} is expected to be zero."))

        # Set height back to the original height
        b.setHeight(h1)
        m3 = b.getMass()
        v3 = b.getVolume()
        a3 = b.getArea()
        nd3 = copy.deepcopy(b.getNumberDensities())
        h3 = b.getHeight()

        self.assertAlmostEqual(m3, m1)
        self.assertAlmostEqual(v3, v1)
        self.assertAlmostEqual(a3, a1)
        self.assertEqual(h3, h1)

        for nuc in nd3.keys():
            self.assertAlmostEqual(nd3[nuc], nd1[nuc])

    def test_getVolumeFractionsWithZeroHeight(self):
        """Tests that the component fractions are the same with a zero height block."""
        b = buildSimpleFuelBlock()

        h1 = b.getHeight()
        originalVolFracs = b.getVolumeFractions()
        for _c, vf in originalVolFracs:
            self.assertNotEqual(vf, 0.0)

        b.setHeight(0.0)
        volFracs = b.getVolumeFractions()
        for (_c, vf1), (_c, vf2) in zip(volFracs, originalVolFracs):
            self.assertAlmostEqual(vf1, vf2)

        b.setHeight(h1)
        volFracs = b.getVolumeFractions()
        for (_c, vf1), (_c, vf2) in zip(volFracs, originalVolFracs):
            self.assertAlmostEqual(vf1, vf2)

    def test_getVolumeFractionWithoutParent(self):
        """Tests that the volume fraction of a block with no parent is zero."""
        b = buildSimpleFuelBlock()
        self.assertIsNone(b.parent)
        with self.assertRaises(ValueError):
            b.getVolumeFraction()

    def test_clearDensity(self):
        self.block.clearNumberDensities()

        for nuc in self.block.getNuclides():
            cur = self.block.getNumberDensity(nuc)
            ref = 0.0
            places = 5
            self.assertAlmostEqual(cur, ref, places=places)

    def test_getNumberDensity(self):
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "ZR": 0.00709003962772,
        }

        self.block.setNumberDensities(refDict)

        for nucKey, nucItem in refDict.items():
            cur = self.block.getNumberDensity(nucKey)
            ref = nucItem
            places = 6
            self.assertAlmostEqual(ref, cur, places=places)

    def test_getMasses(self):
        masses = sorted(self.block.getMasses())
        self.assertEqual(len(masses), 13)
        self.assertEqual(masses[0], "C")

    def test_removeMass(self):
        mass0 = self.block.getMass("U238")
        self.assertGreater(mass0, 0.1)
        self.block.removeMass("U238", 0.1)
        mass1 = self.block.getMass("U238")
        self.assertGreater(mass1, 0)
        self.assertGreater(mass0, mass1)

    def test_setNumberDensity(self):
        ref = 0.05
        self.block.setNumberDensity("U235", ref)

        cur = self.block.getNumberDensity("U235")
        places = 5
        self.assertAlmostEqual(cur, ref, places=places)

    def test_setNumberDensities(self):
        """Make sure we can set multiple number densities at once."""
        b = self.block
        b.setNumberDensity("NA", 0.5)
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W": 1.09115150103e-05,
            "ZR": 0.00709003962772,
        }

        b.setNumberDensities(refDict)

        for nucKey, nucItem in refDict.items():
            cur = self.block.getNumberDensity(nucKey)
            ref = nucItem
            places = 6
            self.assertAlmostEqual(cur, ref, places=places)

        # make sure U235 stayed fully contained in the fuel component
        fuelC = b.getComponent(Flags.FUEL)
        self.assertAlmostEqual(
            b.getNumberDensity("U235"),
            fuelC.getNumberDensity("U235") * fuelC.getVolumeFraction(),
        )

        # make sure other vals were zeroed out
        self.assertAlmostEqual(b.getNumberDensity("NA23"), 0.0)

    def test_getMass(self):
        self.block.setHeight(100.0)

        nucName = "U235"
        d = self.block.getNumberDensity(nucName)
        v = self.block.getVolume()
        A = nucDir.getAtomicWeight(nucName)

        ref = d * v * A / MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
        cur = self.block.getMass(nucName)

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_setMass(self):
        self.block.setHeight(100.0)

        mass = 100.0
        nuc = "U238"
        self.block.setMass(nuc, mass)

        cur = self.block.getMass(nuc)
        ref = mass
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

        cur = self.block.getNumberDensity(nuc)
        v = self.block.getVolume()
        A = nucDir.getAtomicWeight(nuc)
        ref = MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * mass / (v * A)

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getTotalMass(self):
        self.block.setHeight(100.0)

        self.block.clearNumberDensities()
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "ZR": 0.00709003962772,
        }
        self.block.setNumberDensities(refDict)

        cur = self.block.getMass()

        tot = 0.0
        for nucName, nucItem in refDict.items():
            d = nucItem
            A = nucDir.getAtomicWeight(nucName)
            tot += d * A

        v = self.block.getVolume()
        ref = tot * v / MOLES_PER_CC_TO_ATOMS_PER_BARN_CM

        places = 9
        self.assertAlmostEqual(cur, ref, places=places)

    def test_replaceBlockWithBlock(self):
        """Tests conservation of mass flag in replaceBlockWithBlock."""
        block = self.block
        ductBlock = block.__class__("duct")
        ductBlock.add(block.getComponent(Flags.COOLANT, exact=True))
        ductBlock.add(block.getComponent(Flags.DUCT, exact=True))
        ductBlock.add(block.getComponent(Flags.INTERCOOLANT, exact=True))

        # get reference data
        refLoc = block.spatialLocator
        refName = block.name
        refHeight = block.p.height
        ductBlock.p.height = 99 * block.p.height

        self.assertGreater(len(block), 3)

        block.replaceBlockWithBlock(ductBlock)

        self.assertEqual(block.spatialLocator, refLoc)
        self.assertEqual(refName, block.name)
        self.assertEqual(3, len(block))
        self.assertEqual(block.p.height, refHeight)

    def test_getWettedPerimeterDepletable(self):
        # calculate the reference value
        wire = self._deplBlock.getComponent(Flags.WIRE)
        correctionFactor = np.hypot(
            1.0,
            math.pi * wire.getDimension("helixDiameter") / wire.getDimension("axialPitch"),
        )
        wireDiam = wire.getDimension("od") * correctionFactor

        ipDim = self.block.getDim(Flags.DUCT, "ip")
        odDim = self.block.getDim(Flags.CLAD, "od")
        mult = self.block.getDim(Flags.CLAD, "mult")
        ref = math.pi * (odDim + wireDiam) * mult + 6 * ipDim / math.sqrt(3)

        # test getWettedPerimeter
        cur = self._deplBlock.getWettedPerimeter()
        self.assertAlmostEqual(cur, ref)

    def test_getWettedPerimeter(self):
        # calculate the reference value
        wire = self.block.getComponent(Flags.WIRE)
        correctionFactor = np.hypot(
            1.0,
            math.pi * wire.getDimension("helixDiameter") / wire.getDimension("axialPitch"),
        )
        wireDiam = wire.getDimension("od") * correctionFactor

        ipDim = self.block.getDim(Flags.DUCT, "ip")
        odDim = self.block.getDim(Flags.CLAD, "od")
        mult = self.block.getDim(Flags.CLAD, "mult")
        ref = math.pi * (odDim + wireDiam) * mult + 6 * ipDim / math.sqrt(3)

        # test getWettedPerimeter
        cur = self.block.getWettedPerimeter()
        self.assertAlmostEqual(cur, ref)

    def test_getWettedPerimeterCircularInnerDuct(self):
        """Calculate the wetted perimeter for a HexBlock with circular inner duct."""
        # build a test block with a Hex inner duct
        fuelDims = {"Tinput": 400, "Thot": 400, "od": 0.76, "id": 0.00, "mult": 127.0}
        cladDims = {"Tinput": 400, "Thot": 400, "od": 0.80, "id": 0.77, "mult": 127.0}
        ductDims = {"Tinput": 400, "Thot": 400, "od": 16, "id": 15.3, "mult": 1.0}
        intercoolantDims = {
            "Tinput": 400,
            "Thot": 400,
            "od": 17.0,
            "id": ductDims["od"],
            "mult": 1.0,
        }

        fuel = components.Circle("fuel", "UZr", **fuelDims)
        clad = components.Circle("clad", "HT9", **cladDims)
        duct = components.Circle("inner duct", "HT9", **ductDims)
        intercoolant = components.Circle("intercoolant", "Sodium", **intercoolantDims)

        b = blocks.HexBlock("fuel", height=10.0)
        b.add(fuel)
        b.add(clad)
        b.add(duct)
        b.add(intercoolant)

        # calculate the reference value
        ref = (ductDims["id"] + ductDims["od"]) * math.pi
        ref += b.getNumPins() * cladDims["od"] * math.pi

        # test getWettedPerimeter
        cur = b.getWettedPerimeter()
        self.assertAlmostEqual(cur, ref)

    def test_getWettedPerimeterHexInnerDuct(self):
        """Calculate the wetted perimeter for a HexBlock with hexagonal inner duct."""
        # build a test block with a Hex inner duct
        fuelDims = {"Tinput": 400, "Thot": 400, "od": 0.76, "id": 0.00, "mult": 127.0}
        cladDims = {"Tinput": 400, "Thot": 400, "od": 0.80, "id": 0.77, "mult": 127.0}
        ductDims = {"Tinput": 400, "Thot": 400, "op": 16, "ip": 15.3, "mult": 1.0}
        intercoolantDims = {
            "Tinput": 400,
            "Thot": 400,
            "op": 17.0,
            "ip": ductDims["op"],
            "mult": 1.0,
        }

        fuel = components.Circle("fuel", "UZr", **fuelDims)
        clad = components.Circle("clad", "HT9", **cladDims)
        duct = components.Hexagon("inner duct", "HT9", **ductDims)
        intercoolant = components.Hexagon("intercoolant", "Sodium", **intercoolantDims)

        b = blocks.HexBlock("fuel", height=10.0)
        b.add(fuel)
        b.add(clad)
        b.add(duct)
        b.add(intercoolant)

        # calculate the reference value
        ref = 6 * (ductDims["ip"] + ductDims["op"]) / math.sqrt(3)
        ref += b.getNumPins() * cladDims["od"] * math.pi

        # test getWettedPerimeter
        cur = b.getWettedPerimeter()
        self.assertAlmostEqual(cur, ref)

    def test_getWettedPerimeterMultiPins(self):
        assembly = buildMixedPinAssembly()
        block = assembly.getFirstBlock(Flags.FUEL)
        # calculate the reference value
        wires = block.getComponents(Flags.WIRE)
        clads = block.getComponents(Flags.CLAD)
        ref = 0
        for wire in wires:
            mult = wire.getDimension("mult")
            correctionFactor = np.hypot(
                1.0,
                math.pi * wire.getDimension("helixDiameter") / wire.getDimension("axialPitch"),
            )
            wireDiam = wire.getDimension("od") * correctionFactor
            ref += math.pi * wireDiam * mult
        ref += sum(math.pi * clad.getDimension("od") * clad.getDimension("mult") for clad in clads)

        ipDim = block.getDim(Flags.DUCT, "ip")
        ref += 6 * ipDim / math.sqrt(3)

        # test getWettedPerimeter
        cur = block.getWettedPerimeter()
        self.assertAlmostEqual(cur, ref)

    def test_getFlowAreaPerPin(self):
        area = self.block.getComponent(Flags.COOLANT).getArea()
        nPins = self.block.getNumPins()
        cur = self.block.getFlowAreaPerPin()
        ref = area / nPins
        self.assertAlmostEqual(cur, ref)

    def test_getFlowArea(self):
        """Test Block.getFlowArea() for a Block with just coolant."""
        ref = self.block.getComponent(Flags.COOLANT).getArea()
        cur = self.block.getFlowArea()
        self.assertAlmostEqual(cur, ref)

    def test_getFlowAreaInterDuctCoolant(self):
        """Test Block.getFlowArea() for a Block with coolant and interductcoolant."""
        # build a test block with a Hex inter duct collant
        fuelDims = {"Tinput": 400, "Thot": 400, "od": 0.76, "id": 0.00, "mult": 127.0}
        ductDims = {"Tinput": 400, "Thot": 400, "op": 16, "ip": 15.3, "mult": 1.0}
        coolDims = {"Tinput": 400, "Thot": 400}
        iCoolantDims = {"Tinput": 400, "Thot": 400, "op": 17.0, "ip": 16, "mult": 1.0}

        fuel = components.Circle("fuel", "UZr", **fuelDims)
        duct = components.Hexagon("inner duct", "HT9", **ductDims)
        coolant = components.DerivedShape("coolant", "Sodium", **coolDims)
        iCoolant = components.Hexagon("interductcoolant", "Sodium", **iCoolantDims)

        b = blocks.HexBlock("fuel", height=10.0)
        b.add(fuel)
        b.add(coolant)
        b.add(duct)
        b.add(iCoolant)

        ref = b.getComponent(Flags.COOLANT).getArea()
        ref += b.getComponent(Flags.INTERDUCTCOOLANT).getArea()
        cur = b.getFlowArea()
        self.assertAlmostEqual(cur, ref)

    def test_getHydraulicDiameter(self):
        cur = self.block.getHydraulicDiameter()
        ref = 4.0 * self.block.getFlowArea() / self.block.getWettedPerimeter()
        self.assertAlmostEqual(cur, ref)

    def test_adjustUEnrich(self):
        self.block.setHeight(100.0)

        ref = 0.25
        self.block.adjustUEnrich(ref)

        cur = self.block.getComponent(Flags.FUEL).getEnrichment()
        places = 5
        self.assertAlmostEqual(cur, ref, places=places)

    def test_setLocation(self):
        """
        Retrieve a blocks location.

        .. test:: Location of a block is retrievable.
            :id: T_ARMI_BLOCK_POSI0
            :tests: R_ARMI_BLOCK_POSI
        """
        b = self.block
        # a bit obvious, but location is a property now...
        i, j = grids.HexGrid.getIndicesFromRingAndPos(2, 3)
        b.spatialLocator = b.core.spatialGrid[i, j, 0]
        self.assertEqual(b.getLocation(), "002-003-000")
        self.assertEqual(0, b.spatialLocator.k)
        self.assertEqual(b.getSymmetryFactor(), 1.0)

        # now if we don't specify axial, it will move to the new xy, location and have original z index
        i, j = grids.HexGrid.getIndicesFromRingAndPos(4, 4)
        b.spatialLocator = b.core.spatialGrid[i, j, 0]
        self.assertEqual(0, b.spatialLocator.k)
        self.assertEqual(b.getSymmetryFactor(), 1.0)

        # center blocks have a different symmetry factor for 1/3rd core
        for symmetry, powerMult in (
            (geometry.FULL_CORE, 1),
            (
                geometry.SymmetryType(geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC),
                3,
            ),
        ):
            self.block.core.symmetry = geometry.SymmetryType.fromAny(symmetry)
            i, j = grids.HexGrid.getIndicesFromRingAndPos(1, 1)
            b.spatialLocator = b.core.spatialGrid[i, j, 0]
            self.assertEqual(0, b.spatialLocator.k)
            self.assertEqual(b.getSymmetryFactor(), powerMult)

    def test_setBuLimitInfo(self):
        self.block.adjustUEnrich(0.1)
        self.block.setType("igniter fuel")

        self.block.setBuLimitInfo()

        cur = self.block.p.buLimit
        ref = 0.0
        self.assertEqual(cur, ref)

    def test_getTotalNDens(self):
        self.block.setType("fuel")

        self.block.clearNumberDensities()
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "ZR": 0.00709003962772,
        }
        self.block.setNumberDensities(refDict)

        cur = self.block.getTotalNDens()

        tot = 0.0
        for nucName in refDict.keys():
            ndens = self.block.getNumberDensity(nucName)
            tot += ndens

        ref = tot
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getHMDens(self):
        self.block.setType("fuel")
        self.block.clearNumberDensities()
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "ZR": 0.00709003962772,
        }
        self.block.setNumberDensities(refDict)

        cur = self.block.getHMDens()

        hmDens = 0.0
        for nuclide in refDict.keys():
            if nucDir.isHeavyMetal(nuclide):
                # then nuclide is a HM
                hmDens += self.block.getNumberDensity(nuclide)

        ref = hmDens

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getFissileMassEnrich(self):
        fuelDims = {"Tinput": 273.0, "Thot": 273.0, "od": 0.76, "id": 0.0, "mult": 1.0}
        self.fuelComponent = components.Circle("fuel", "UZr", **fuelDims)
        self.block.add(self.fuelComponent)
        self.block.setHeight(100.0)

        self.block.clearNumberDensities()
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "ZR": 0.00709003962772,
        }
        self.block.setNumberDensities(refDict)

        cur = self.block.getFissileMassEnrich()

        ref = self.block.getFissileMass() / self.block.getHMMass()
        places = 4
        self.assertAlmostEqual(cur, ref, places=places)
        self.block.remove(self.fuelComponent)

    def test_getMicroSuffix(self):
        self.assertEqual(self.block.getMicroSuffix(), "AA")

        self.block.p.xsType = "Z"
        self.assertEqual(self.block.getMicroSuffix(), "ZA")

        self.block.p.xsType = "RS"
        self.assertEqual(self.block.getMicroSuffix(), "RS")

        self.block.p.envGroup = "X"
        self.block.p.xsType = "AB"
        with self.assertRaises(ValueError):
            self.block.getMicroSuffix()

    def test_getUraniumMassEnrich(self):
        self.block.adjustUEnrich(0.25)

        ref = 0.25

        self.block.adjustUEnrich(ref)
        cur = self.block.getUraniumMassEnrich()

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getUraniumNumEnrich(self):
        self.block.adjustUEnrich(0.25)

        cur = self.block.getUraniumNumEnrich()

        u8 = self.block.getNumberDensity("U238")
        u5 = self.block.getNumberDensity("U235")
        ref = u5 / (u8 + u5)

        self.assertAlmostEqual(cur, ref, places=6)

        # test the zero edge case
        self.block.adjustUEnrich(0)
        cur = self.block.getUraniumNumEnrich()
        self.assertEqual(cur, 0.0)

    def test_getNumberOfAtoms(self):
        self.block.clearNumberDensities()
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "ZR": 0.00709003962772,
        }
        self.block.setNumberDensities(refDict)

        nucName = "U238"
        moles = self.block.getNumberOfAtoms(nucName) / units.AVOGADROS_NUMBER  # about 158 moles
        refMoles = refDict["U238"] * self.block.getVolume() / (units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM)
        self.assertAlmostEqual(moles, refMoles)

    def test_getPu(self):
        fuel = self.block.getComponent(Flags.FUEL)
        vFrac = fuel.getVolumeFraction()
        refDict = {
            "AM241": 2.695633500634074e-05,
            "U238": 0.015278429635341755,
            "O16": 0.04829586365251901,
            "U235": 0.004619446966056436,
            "PU239": 0.0032640382635406515,
            "PU238": 4.266845903720035e-06,
            "PU240": 0.000813669265183342,
            "PU241": 0.00011209296581262849,
            "PU242": 2.3078961257395204e-05,
        }
        fuel.setNumberDensities({nuc: v / vFrac for nuc, v in refDict.items()})

        # test moles
        cur = self.block.getPuMoles()
        ndens = 0.0
        for nucName in refDict.keys():
            if nucName in ["PU238", "PU239", "PU240", "PU241", "PU242"]:
                ndens += self.block.getNumberDensity(nucName)
        ref = ndens / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * self.block.getVolume() * self.block.getSymmetryFactor()
        self.assertAlmostEqual(cur, ref, places=6)

    def test_adjustDensity(self):
        u235Dens = 0.003
        u238Dens = 0.010
        self.block.setNumberDensity("U235", u235Dens)
        self.block.setNumberDensity("U238", u238Dens)
        mass1 = self.block.getMass(["U235", "U238"])
        densAdj = 0.9
        nucList = ["U235", "U238"]
        massDiff = self.block.adjustDensity(densAdj, nucList, returnMass=True)
        mass2 = self.block.getMass(["U235", "U238"])

        cur = self.block.getNumberDensity("U235")
        ref = densAdj * u235Dens
        self.assertAlmostEqual(cur, ref, places=9)

        cur = self.block.getNumberDensity("U238")
        ref = densAdj * u238Dens
        self.assertAlmostEqual(cur, ref, places=9)

        self.assertAlmostEqual(mass2 - mass1, massDiff)

    @patch.object(blocks.HexBlock, "getSymmetryFactor")
    def test_getMgFlux(self, mock_sf):
        # calculate Mg Flux with a Symmetry Factor of 3
        mock_sf.return_value = 3
        neutronFlux = 1.0
        gammaFlux = 2.0
        self.block.p.mgFlux = np.full(5, neutronFlux)
        self.block.p.mgFluxGamma = np.full(4, gammaFlux)
        fuel = self.block.getComponent(Flags.FUEL)
        blockVol = self.block.getVolume()
        fuelVol = fuel.getVolume()
        # compute volume fraction of component; need symmetry factor
        volFrac = fuelVol / blockVol / self.block.getSymmetryFactor()
        neutronFluxInt = fuel.getIntegratedMgFlux()
        gammaFluxInt = fuel.getIntegratedMgFlux(gamma=True)
        # getIntegratedMgFlux should be scaled by the component volume fraction
        np.testing.assert_almost_equal(neutronFluxInt, np.full(5, neutronFlux * volFrac))
        np.testing.assert_almost_equal(gammaFluxInt, np.full(4, gammaFlux * volFrac))

        # getMgFlux should return regular, non-integrated flux
        neutronMgFlux = fuel.getMgFlux()
        gammaMgFlux = fuel.getMgFlux(gamma=True)
        np.testing.assert_almost_equal(neutronMgFlux, np.full(5, neutronFlux / blockVol))
        np.testing.assert_almost_equal(gammaMgFlux, np.full(4, gammaFlux / blockVol))

        # calculate Mg Flux with a Symmetry Factor of 1
        mock_sf.return_value = 1
        self.block.p.mgFlux = np.full(5, neutronFlux)
        self.block.p.mgFluxGamma = np.full(4, gammaFlux)
        fuel = self.block.getComponent(Flags.FUEL)
        blockVol = self.block.getVolume()
        fuelVol = fuel.getVolume()
        volFrac = fuelVol / blockVol / self.block.getSymmetryFactor()
        neutronFluxInt = fuel.getIntegratedMgFlux()
        gammaFluxInt = fuel.getIntegratedMgFlux(gamma=True)
        # getIntegratedMgFlux should be scaled by the component volume fraction
        np.testing.assert_almost_equal(neutronFluxInt, np.full(5, neutronFlux * volFrac))
        np.testing.assert_almost_equal(gammaFluxInt, np.full(4, gammaFlux * volFrac))

        # getMgFlux should return regular, non-integrated flux
        neutronMgFlux = fuel.getMgFlux()
        gammaMgFlux = fuel.getMgFlux(gamma=True)
        np.testing.assert_almost_equal(neutronMgFlux, np.full(5, neutronFlux / blockVol))
        np.testing.assert_almost_equal(gammaMgFlux, np.full(4, gammaFlux / blockVol))

    @patch.object(blocks.HexBlock, "getSymmetryFactor")
    def test_completeInitialLoading(self, mock_sf):
        """Ensure that some BOL block and component params are populated properly.

        Notes
        -----
        - When checking component-level BOL params, puFrac is skipped due to 1) there's no Pu in the block, and 2)
          getPuMoles is functionally identical to getHMMoles (just limits nuclides from heavy metal to just Pu).
        - getSymmetryFactor is mocked to return 3. This indicates that the block is in the center-most assembly.
          Providing this mock ensures that symmetry factors are tested as well (otherwise it's just a factor of 1
          and it is a less robust test).
        """
        mock_sf.return_value = 3
        area = self.block.getArea()
        height = 2.0
        self.block.setHeight(height)

        self.block.clearNumberDensities()
        self.block.setNumberDensities(
            {
                "U238": 0.018518936996911595,
                "ZR": 0.006040713762820692,
                "U235": 0.0023444806416701184,
                "NA23": 0.009810163826158255,
            }
        )

        self.block.completeInitialLoading()

        sf = self.block.getSymmetryFactor()
        cur = self.block.p.molesHmBOL
        ref = self.block.getHMDens() / MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * height * area
        self.assertAlmostEqual(cur, ref, places=12)

        totalHMMass = 0.0
        for c in self.block:
            nucs = c.getNuclides()
            hmNucs = [nuc for nuc in nucs if nucDir.isHeavyMetal(nuc)]
            hmNDens = {hmNuc: c.getNumberDensity(hmNuc) for hmNuc in hmNucs}
            # use sf to account for only a 1/sf portion of the component being in the block
            hmMass = densityTools.calculateMassDensity(hmNDens) * c.getVolume() / sf
            totalHMMass += hmMass
            if hmMass:
                self.assertAlmostEqual(c.p.massHmBOL, hmMass, places=12)
                self.assertAlmostEqual(
                    c.p.molesHmBOL,
                    sum(ndens for ndens in hmNDens.values()) / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * c.getVolume(),
                    places=12,
                )
            else:
                self.assertEqual(c.p.massHmBOL, 0.0)
                self.assertEqual(c.p.molesHmBOL, 0.0)

        self.assertAlmostEqual(self.block.p.massHmBOL, totalHMMass)

    def test_add(self):
        numComps = len(self.block.getComponents())

        fuelDims = {"Tinput": 25.0, "Thot": 600, "od": 0.76, "id": 0.00, "mult": 127.0}

        newComp = components.Circle("fuel", "UZr", **fuelDims)
        self.block.add(newComp)
        self.assertEqual(numComps + 1, len(self.block.getComponents()))

        self.assertIn(newComp, self.block.getComponents())
        self.block.remove(newComp)

    def test_hasComponents(self):
        self.assertTrue(self.block.hasComponents([Flags.FUEL, Flags.CLAD]))
        self.assertTrue(self.block.hasComponents(Flags.FUEL))
        self.assertFalse(self.block.hasComponents([Flags.FUEL, Flags.CLAD, Flags.DUMMY]))

    def test_getComponentNames(self):
        cur = self.block.getComponentNames()
        ref = set(
            [
                "annular void",
                "bond",
                "fuel",
                "gap1",
                "inner liner",
                "gap2",
                "outer liner",
                "gap3",
                "clad",
                "wire",
                "coolant",
                "duct",
                "interCoolant",
            ]
        )
        self.assertEqual(cur, ref)

    def test_getComponents(self):
        cur = self.block.getComponents(Flags.FUEL)
        self.assertEqual(len(cur), 1)

        comps = self.block.getComponents(Flags.FUEL) + self.block.getComponents(Flags.CLAD)
        self.assertEqual(len(comps), 2)

        inter = self.block.getComponents(Flags.INTERCOOLANT)
        self.assertEqual(len(inter), 1)

        inter = self.block.getComponents(Flags.INTERCOOLANT, exact=True)  # case insensitive
        self.assertEqual(inter, [self.block.getComponent(Flags.INTERCOOLANT)])

        cool = self.block.getComponents(Flags.COOLANT, exact=True)
        self.assertEqual(len(cool), 1)

    def test_getComponent(self):
        cur = self.block.getComponent(Flags.FUEL)
        self.assertIsInstance(cur, components.Component)

        inter = self.block.getComponent(Flags.INTERCOOLANT)
        self.assertIsInstance(inter, components.Component)

        with self.assertRaises(KeyError):
            # this really isn't the responsibility of block, more of Flags, but until this refactor
            # is over...
            inter = self.block.getComponent(Flags.fromString("intercoolantlala"), exact=True)

        cool = self.block.getComponent(Flags.COOLANT, exact=True)
        self.assertIsInstance(cool, components.Component)

    def test_getComponentsOfShape(self):
        ref = [
            "annular void",
            "bond",
            "fuel",
            "gap1",
            "inner liner",
            "gap2",
            "outer liner",
            "gap3",
            "clad",
        ]
        cur = [c.name for c in self.block.getComponentsOfShape(components.Circle)]
        self.assertEqual(sorted(ref), sorted(cur))

    def test_getComponentsOfMaterial(self):
        cur = self.block.getComponentsOfMaterial(materials.UZr())
        ref = self.block.getComponent(Flags.FUEL)
        self.assertEqual(cur[0], ref)

        self.assertEqual(
            self.block.getComponentsOfMaterial(materials.HT9()),
            [
                self.block.getComponent(Flags.OUTER | Flags.LINER),
                self.block.getComponent(Flags.CLAD),
                self.block.getComponent(Flags.WIRE),
                self.block.getComponent(Flags.DUCT),
            ],
        )

        # test edge case
        cur = self.block.getComponentsOfMaterial(None, "UZr")
        self.assertEqual(cur[0], ref)

    def test_getComponentByName(self):
        """Test children by name."""
        self.assertIsNone(self.block.getComponentByName("not the droid you are looking for"))
        self.assertIsNotNone(self.block.getComponentByName("annular void"))

    def test_getSortedComponentsInsideOfComponentClad(self):
        """Test that components can be sorted within a block and returned in the correct order.

        For an arbitrary example: a clad component.
        """
        expected = [
            self.block.getComponentByName(c)
            for c in [
                "annular void",
                "bond",
                "fuel",
                "gap1",
                "inner liner",
                "gap2",
                "outer liner",
                "gap3",
            ]
        ]
        clad = self.block.getComponent(Flags.CLAD)
        actual = self.block.getSortedComponentsInsideOfComponent(clad)
        self.assertListEqual(actual, expected)

    def test_getSortedComponentsInsideOfComponentDuct(self):
        """Test that components can be sorted within a block and returned in the correct order.

        For an arbitrary example: a duct.
        """
        expected = [
            self.block.getComponentByName(c)
            for c in [
                "annular void",
                "bond",
                "fuel",
                "gap1",
                "inner liner",
                "gap2",
                "outer liner",
                "gap3",
                "clad",
                "wire",
                "coolant",
            ]
        ]
        clad = self.block.getComponent(Flags.DUCT)
        actual = self.block.getSortedComponentsInsideOfComponent(clad)
        self.assertListEqual(actual, expected)

    def test_getNumComponents(self):
        cur = self.block.getNumComponents(Flags.FUEL)
        ref = self.block.getDim(Flags.FUEL, "mult")
        self.assertEqual(cur, ref)

        self.assertEqual(ref, self.block.getNumComponents(Flags.CLAD))

        self.assertEqual(1, self.block.getNumComponents(Flags.DUCT))

    def test_getNumPins(self):
        """Test that we can get the number of pins from various blocks.

        .. test:: Retrieve the number of pins from various blocks.
            :id: T_ARMI_BLOCK_NPINS
            :tests: R_ARMI_BLOCK_NPINS
        """
        cur = self.block.getNumPins()
        ref = self.block.getDim(Flags.FUEL, "mult")
        self.assertEqual(cur, ref)

        emptyBlock = blocks.HexBlock("empty")
        self.assertEqual(emptyBlock.getNumPins(), 0)

        holedRectangle = complexShapes.HoledRectangle("holedRectangle", "HT9", 1, 1, 0.5, 1.0, 1.0)
        holedRectangle.setType("component", flags=Flags.CONTROL)
        emptyBlock.add(holedRectangle)
        self.assertEqual(emptyBlock.getNumPins(), 0)

        hexagon = basicShapes.Hexagon("hexagon", "HT9", 1, 1, 1)
        hexagon.setType("component", flags=Flags.SHIELD)
        emptyBlock.add(hexagon)
        self.assertEqual(emptyBlock.getNumPins(), 0)

        pins = basicShapes.Circle("circle", "HT9", 1, 1, 1, 0, 8)
        pins.setType("component", flags=Flags.PLENUM)
        emptyBlock.add(pins)
        self.assertEqual(emptyBlock.getNumPins(), 8)

    def test_setLinPowByPin(self):
        numPins = self.block.getNumPins()
        neutronPower = [10.0 * i for i in range(numPins)]
        gammaPower = [1.0 * i for i in range(numPins)]
        totalPower = [x + y for x, y in zip(neutronPower, gammaPower)]

        totalPowerKey = "linPowByPin"
        neutronPowerKey = f"linPowByPin{NEUTRON}"
        gammaPowerKey = f"linPowByPin{GAMMA}"

        # Try setting gamma power too early and then reset
        with self.assertRaises(UnboundLocalError) as context:
            self.block.setPinPowers(
                gammaPower,
                powerKeySuffix=GAMMA,
            )
        errorMsg = f"Neutron power has not been set yet. Cannot set total power for {self.block}."
        self.assertTrue(errorMsg in str(context.exception))
        self.block.p[gammaPowerKey] = None

        # Test with no powerKeySuffix
        self.block.setPinPowers(neutronPower)
        assert_allclose(self.block.p[totalPowerKey], np.array(neutronPower))
        self.assertIsNone(self.block.p[neutronPowerKey])
        self.assertIsNone(self.block.p[gammaPowerKey])

        # Test with neutron powers
        self.block.setPinPowers(
            neutronPower,
            powerKeySuffix=NEUTRON,
        )
        assert_allclose(self.block.p[totalPowerKey], np.array(neutronPower))
        assert_allclose(self.block.p[neutronPowerKey], np.array(neutronPower))
        self.assertIsNone(self.block.p[gammaPowerKey])

        # Test with gamma powers
        self.block.setPinPowers(
            gammaPower,
            powerKeySuffix=GAMMA,
        )
        assert_allclose(self.block.p[totalPowerKey], np.array(totalPower))
        assert_allclose(self.block.p[neutronPowerKey], np.array(neutronPower))
        assert_allclose(self.block.p[gammaPowerKey], np.array(gammaPower))

    def test_getComponentAreaFrac(self):
        def calcFracManually(names):
            tFrac = 0.0
            for n in names:
                for c, frac in fracs:
                    if c.getName() == n:
                        tFrac += frac
            return tFrac

        self.block.setHeight(2.0)

        refList = [Flags.BOND, Flags.COOLANT]
        cur = self.block.getComponentAreaFrac(refList)
        fracs = self.block.getVolumeFractions()

        ref = calcFracManually(("bond", "coolant"))
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

        # allow inexact for things like fuel1, fuel2 or clad vs. cladding
        val = self.block.getComponentAreaFrac([Flags.COOLANT, Flags.INTERCOOLANT])
        ref = calcFracManually(["coolant", "interCoolant"])
        refWrong = calcFracManually(
            ["coolant", "interCoolant", "clad"]
        )  # can't use 'clad' b/c ``calcFracManually`` is exact only
        self.assertAlmostEqual(ref, val)
        self.assertNotAlmostEqual(refWrong, val)

    def test_100_getPinPitch(self):
        cur = self.block.getPinPitch()
        ref = self.block.getDim(Flags.CLAD, "od") + self.block.getDim(Flags.WIRE, "od")
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_101_getPitch(self):
        cur = self.block.getPitch(returnComp=True)
        ref = (
            self.block.getDim(Flags.INTERCOOLANT, "op"),
            self.block.getComponent(Flags.INTERCOOLANT),
        )
        self.assertEqual(cur, ref)

        newb = copy.deepcopy(self.block)
        p1, c1 = self.block.getPitch(returnComp=True)
        p2, c2 = newb.getPitch(returnComp=True)

        self.assertNotEqual(c1, c2)
        self.assertEqual(newb.getLargestComponent("op"), c2)
        self.assertEqual(p1, p2)

    def test_102_setPitch(self):
        pitch = 17.5
        self.block.setPitch(pitch)
        cur = self.block.getPitch()
        self.assertEqual(cur, pitch)
        self.assertEqual(self.block.getComponent(Flags.INTERCOOLANT).getDimension("op"), pitch)

    def test_106_getAreaFractions(self):
        cur = self.block.getVolumeFractions()
        tot = 0.0
        areas = []
        for c in self.block.iterComponents():
            a = c.getArea()
            tot += a
            areas.append((c, a))
        fracs = {}
        for c, a in areas:
            fracs[c.getName()] = a / tot

        places = 6
        for c, a in cur:
            self.assertAlmostEqual(a, fracs[c.getName()], places=places)

        self.assertAlmostEqual(sum(fracs.values()), sum([a for c, a in cur]))

    def test_expandElementalToIsotopics(self):
        """Tests the expand to elementals capability."""
        initialN = {}
        initialM = {}
        elementals = [nuclideBases.byName[nn] for nn in ["FE", "CR", "SI", "V", "MO"]]
        for elemental in elementals:
            initialN[elemental] = self.block.getNumberDensity(elemental.name)  # homogenized
            initialM[elemental] = self.block.getMass(elemental.name)

        for elemental in elementals:
            self.block.expandElementalToIsotopics(elemental)
            newDens = 0.0
            newMass = 0.0
            for natNuc in elemental.getNaturalIsotopics():
                newDens += self.block.getNumberDensity(natNuc.name)
                newMass += self.block.getMass(natNuc.name)

            self.assertAlmostEqual(
                initialN[elemental],
                newDens,
                msg="Isotopic {2} ndens does not add up to {0}. It adds to {1}".format(
                    initialN[elemental], newDens, elemental
                ),
            )
            self.assertAlmostEqual(
                initialM[elemental],
                newMass,
                msg="Isotopic {2} mass does not add up to {0} g. It adds to {1}".format(
                    initialM[elemental], newMass, elemental
                ),
            )

    def test_expandAllElementalsToIsotopics(self):
        """Tests the expand all elementals simlutaneously capability."""
        initialN = {}
        initialM = {}
        elementals = [nuclideBases.byName[nn] for nn in ["FE", "CR", "SI", "V", "MO"]]
        for elemental in elementals:
            initialN[elemental] = self.block.getNumberDensity(elemental.name)  # homogenized
            initialM[elemental] = self.block.getMass(elemental.name)

        self.block.expandAllElementalsToIsotopics()

        for elemental in elementals:
            newDens = 0.0
            newMass = 0.0
            for natNuc in elemental.getNaturalIsotopics():
                newDens += self.block.getNumberDensity(natNuc.name)
                newMass += self.block.getMass(natNuc.name)

            self.assertAlmostEqual(
                initialN[elemental],
                newDens,
                msg="Isotopic {2} ndens does not add up to {0}. It adds to {1}".format(
                    initialN[elemental], newDens, elemental
                ),
            )
            self.assertAlmostEqual(
                initialM[elemental],
                newMass,
                msg="Isotopic {2} mass does not add up to {0} g. It adds to {1}".format(
                    initialM[elemental], newMass, elemental
                ),
            )

    def test_setPitch(self):
        """
        Checks consistency after adjusting pitch.

        Needed to verify fix to Issue #165.
        """
        b = self.block
        moles1 = b.p.molesHmBOL
        b.setPitch(17.5)
        moles2 = b.p.molesHmBOL
        self.assertAlmostEqual(moles1, moles2)
        b.setPitch(20.0)
        moles3 = b.p.molesHmBOL
        self.assertAlmostEqual(moles2, moles3)

    def test_setImportantParams(self):
        """Confirm that important block parameters can be set and get."""
        # Test ability to set and get flux
        applyDummyData(self.block)
        self.assertEqual(self.block.p.mgFlux[0], 161720716762.12997)
        self.assertEqual(self.block.p.mgFlux[-1], 601494405.293505)

        # Test ability to set and get number density
        fuel = self.block.getComponent(Flags.FUEL)

        u235_dens = fuel.getNumberDensity("U235")
        self.assertEqual(u235_dens, 0.003695461770836022)

        fuel.setNumberDensity("U235", 0.5)
        u235_dens = fuel.getNumberDensity("U235")
        self.assertEqual(u235_dens, 0.5)

        # TH parameter test
        self.assertEqual(0, self.block.p.THmassFlowRate)
        self.block.p.THmassFlowRate = 10
        self.assertEqual(10, self.block.p.THmassFlowRate)

    def test_getMfp(self):
        """Test mean free path."""
        applyDummyData(self.block)
        # These are unverified numbers, just the result of this calculation.
        mfp, mfpAbs, diffusionLength = self.block.getMfp()
        # no point testing these number to high accuracy.
        assert_allclose(3.9, mfp, rtol=0.1)
        assert_allclose(235.0, mfpAbs, rtol=0.1)
        assert_allclose(17.0, diffusionLength, rtol=0.1)

    def test_consistentMassDensVolBetweenColdBlockAndComp(self):
        block = self.block
        expectedData = []
        actualData = []
        for c in block:
            expectedData.append(getComponentData(c))
            actualData.append((c, c.density(), c.getVolume(), c.density() * c.getVolume()))

        for expected, actual in zip(expectedData, actualData):
            msg = (
                "Data (component, density, volume, mass) for component {} does not match. "
                "Expected: {}, Actual: {}".format(expected[0], expected, actual)
            )
            for expectedVal, actualVal in zip(expected, actual):
                self.assertAlmostEqual(expectedVal, actualVal, msg=msg)

    def test_consistentMassDensVolBetweenHotBlockAndComp(self):
        block = self._hotBlock
        expectedData = []
        actualData = []
        for c in block:
            expectedData.append(getComponentData(c))
            actualData.append((c, c.density(), c.getVolume(), c.density() * c.getVolume()))

        for expected, actual in zip(expectedData, actualData):
            msg = (
                "Data (component, density, volume, mass) for component {} does not match. "
                "Expected: {}, Actual: {}".format(expected[0], expected, actual)
            )
            for expectedVal, actualVal in zip(expected, actual):
                self.assertAlmostEqual(expectedVal, actualVal, msg=msg)

    def test_consistentAreaWithOverlappingComp(self):
        """
        Test that negative gap areas correctly account for area overlapping upon thermal expansion.

        Notes
        -----
        This test calculates a reference coolant area by subtracting the areas of the intercoolant,
        duct, wire wrap, and pins from the total hex block area. The area of the pins is calculated
        using only the outer radius of the clad. This avoids the use of negative areas as
        implemented in Block.getVolumeFractions. Na-23 mass will not be conserved as when duct/clad
        expands sodium is evacuated.

        See Also
        --------
        armi.reactor.blocks.Block.getVolumeFractions
        """
        numFE56 = self.block.getNumberOfAtoms("FE56")
        numU235 = self.block.getNumberOfAtoms("U235")
        for c in self.block:
            c.setTemperature(800)
        hasNegativeArea = any(c.getArea() < 0 for c in self.block)
        self.assertTrue(hasNegativeArea)
        self.block.getVolumeFractions()  # sets coolant area
        self._testDimensionsAreLinked()  # linked dimensions are needed for this test to work

        blockPitch = self.block.getPitch()
        self.assertAlmostEqual(blockPitch, self.block.getComponent(Flags.INTERCOOLANT).getDimension("op"))
        totalHexArea = blockPitch**2 * math.sqrt(3) / 2.0

        clad = self.block.getComponent(Flags.CLAD)
        pinArea = math.pi / 4.0 * clad.getDimension("od") ** 2 * clad.getDimension("mult")
        ref = (
            totalHexArea
            - self.block.getComponent(Flags.INTERCOOLANT).getArea()
            - self.block.getComponent(Flags.DUCT).getArea()
            - self.block.getComponent(Flags.WIRE).getArea()
            - pinArea
        )

        self.assertAlmostEqual(totalHexArea, self.block.getArea())
        self.assertAlmostEqual(ref, self.block.getComponent(Flags.COOLANT).getArea())

        self.assertTrue(np.allclose(numFE56, self.block.getNumberOfAtoms("FE56")))
        self.assertTrue(np.allclose(numU235, self.block.getNumberOfAtoms("U235")))

    def _testDimensionsAreLinked(self):
        prevC = None
        for c in self.block.getComponentsOfShape(components.Circle):
            if prevC:
                self.assertAlmostEqual(prevC.getDimension("od"), c.getDimension("id"))
            prevC = c
        self.assertAlmostEqual(
            self.block.getComponent(Flags.DUCT).getDimension("op"),
            self.block.getComponent(Flags.INTERCOOLANT).getDimension("ip"),
        )

    def test_pinMgFluxes(self):
        """Test setting/getting of pin-wise multigroup fluxes."""
        self.assertIsNone(self.block.p.pinMgFluxes)
        self.assertIsNone(self.block.p.pinMgFluxesAdj)
        self.assertIsNone(self.block.p.pinMgFluxesGamma)

        nFlux = np.random.rand(10, 33)
        aFlux = np.random.random(nFlux.shape)
        gFlux = np.random.random(nFlux.shape)

        self.block.setPinMgFluxes(nFlux)
        assert_array_equal(self.block.p.pinMgFluxes, nFlux)
        self.assertIsNone(self.block.p.pinMgFluxesAdj)
        self.assertIsNone(self.block.p.pinMgFluxesGamma)

        self.block.setPinMgFluxes(aFlux, adjoint=True)
        assert_array_equal(self.block.p.pinMgFluxesAdj, aFlux)
        # Make sure we didn't modify anything else
        assert_array_equal(self.block.p.pinMgFluxes, nFlux)
        self.assertIsNone(self.block.p.pinMgFluxesGamma)

        self.block.setPinMgFluxes(gFlux, gamma=True)
        assert_array_equal(self.block.p.pinMgFluxesGamma, gFlux)
        assert_array_equal(self.block.p.pinMgFluxesAdj, aFlux)
        assert_array_equal(self.block.p.pinMgFluxes, nFlux)

    def test_getComponentsInLinkedOrder(self):
        comps = self.block.getComponentsInLinkedOrder()
        self.assertEqual(len(comps), len(self.block))

        comps.pop(0)
        with self.assertRaises(RuntimeError):
            _ = self.block.getComponentsInLinkedOrder(comps)

    def test_mergeWithBlock(self):
        fuel1 = self.block.getComponent(Flags.FUEL)
        fuel1.setNumberDensity("CM246", 0.0)
        block2 = loadTestBlock()
        fuel2 = block2.getComponent(Flags.FUEL)
        fuel2.setNumberDensity("CM246", 0.02)
        self.assertEqual(self.block.getNumberDensity("CM246"), 0.0)
        self.block.mergeWithBlock(block2, 0.1)
        self.assertGreater(self.block.getNumberDensity("CM246"), 0.0)
        self.assertLess(self.block.getNumberDensity("CM246"), 0.02)

    def test_getDimensions(self):
        dims = self.block.getDimensions("od")
        self.assertIn(self.block.getComponent(Flags.FUEL).p.od, dims)

    def test_getPlenumPin(self):
        pin = self.block.getPlenumPin()
        self.assertIsNone(pin)

    def test_hasPinPitch(self):
        hasPitch = self.block.hasPinPitch()
        self.assertTrue(hasPitch)

    def test_getReactionRates(self):
        block = blocks.HexBlock("HexBlock")
        block.setType("defaultType")
        comp = basicShapes.Hexagon("hexagon", "MOX", 1, 1, 1)
        block.add(comp)
        block.setHeight(1)
        block.p.xsType = "A"

        r = tests.getEmptyHexReactor()
        assembly = makeTestAssembly(1, 1, r=r)
        assembly.add(block)
        r.core.add(assembly)
        r.core.lib = isotxs.readBinary(ISOAA_PATH)
        block.p.mgFlux = 1

        self.assertAlmostEqual(
            block.getReactionRates("PU239")["nG"],
            block.getNumberDensity("PU239") * sum(r.core.lib["PU39AA"].micros.nGamma),
        )

        # the key is invalid, so should get back all zeros
        self.assertEqual(
            block.getReactionRates("PU39"),
            {"nG": 0, "nF": 0, "n2n": 0, "nA": 0, "nP": 0, "n3n": 0},
        )

    def test_getComponentsThatAreLinkedTo(self):
        c = self.block.getFirstComponent(Flags.FUEL)
        linked = self.block.getComponentsThatAreLinkedTo(c, "id")
        self.assertEqual(linked[0][1], "od")

        c = self.block.getFirstComponent(Flags.CLAD)
        linked = self.block.getComponentsThatAreLinkedTo(c, "id")
        self.assertEqual(linked[0][1], "od")

        c = self.block.getFirstComponent(Flags.DUCT)
        linked = self.block.getComponentsThatAreLinkedTo(c, "ip")
        self.assertEqual(len(linked), 0)


class BlockInputHeightsTests(unittest.TestCase):
    def test_foundReactor(self):
        """Test the input height is pullable from blueprints."""
        r = loadTestReactor()[1]
        msg = "Input height from blueprints differs. Did a blueprint get updated and not this test?"

        # Grab a block from an assembly, so long as we have the height
        assem = r.core.getFirstAssembly(Flags.IGNITER | Flags.FUEL)
        lowerB = assem[0]
        self.assertEqual(
            lowerB.getInputHeight(),
            25,
            msg=msg,
        )
        # Grab another block just for good measure
        midBlock = assem[2]
        self.assertEqual(
            midBlock.getInputHeight(),
            25,
            msg=msg,
        )
        # Top block has a different height. Make sure we don't just
        # return 25 all the time
        topBlock = assem[4]
        self.assertEqual(topBlock.getInputHeight(), 75, msg=msg)

    def test_noBlueprints(self):
        """Verify an error is raised if there are no blueprints."""
        b = buildSimpleFuelBlock()
        with self.assertRaisesRegex(AttributeError, "No ancestor.*blueprints"):
            b.getInputHeight()


class BlockEnergyDepositionConstants(unittest.TestCase):
    """Tests the energy deposition methods.

    MagicMocks xsCollections.compute*Constants() -- we're not testing those methods specifically
    so just make sure they're hit
    """

    @classmethod
    def setUpClass(cls):
        cls.block = loadTestBlock()

    def setUp(self):
        self.block.core.lib = MagicMock()

    @patch.object(xsCollections, "computeFissionEnergyGenerationConstants")
    @patch.object(xsCollections, "computeCaptureEnergyGenerationConstants")
    def test_getTotalEnergyGenerationConstants(self, mock_capture, mock_fission):
        """Mock both xsCollections methods so you get complete coverage."""
        _x = self.block.getTotalEnergyGenerationConstants()
        self.assertEqual(mock_fission.call_count, 1)
        self.assertEqual(mock_capture.call_count, 1)

    @patch.object(xsCollections, "computeFissionEnergyGenerationConstants")
    def test_getFissionEnergyDepositionConstants(self, mock_method):
        """Test RuntimeError and that it gets to the deposition constant call."""
        # make sure xsCollections.compute* gets hit
        _x = self.block.getFissionEnergyGenerationConstants()
        self.assertEqual(mock_method.call_count, 1)
        # set core.lib to None and get RuntimeError
        self.block.core.lib = None
        with self.assertRaises(RuntimeError):
            # fails because this test reactor does not have a cross-section library
            _x = self.block.getFissionEnergyGenerationConstants()

    @patch.object(xsCollections, "computeCaptureEnergyGenerationConstants")
    def test_getCaptureEnergyGenerationConstants(self, mock_method):
        """Test RuntimeError and that it gets to the deposition constant call."""
        # make sure xsCollections.compute* gets hit
        _x = self.block.getCaptureEnergyGenerationConstants()
        self.assertEqual(mock_method.call_count, 1)
        # set core.lib to None and get RuntimeError
        self.block.core.lib = None
        with self.assertRaises(RuntimeError):
            # fails because this test reactor does not have a cross-section library
            _x = self.block.getCaptureEnergyGenerationConstants()

    @patch.object(xsCollections, "computeNeutronEnergyDepositionConstants")
    def test_getNeutronEnergyDepositionConstants(self, mock_method):
        """Test RuntimeError and that it gets to the deposition constant call."""
        # make sure xsCollections.compute* gets hit
        _x = self.block.getNeutronEnergyDepositionConstants()
        self.assertEqual(mock_method.call_count, 1)
        # set core.lib to None and get RuntimeError
        self.block.core.lib = None
        with self.assertRaises(RuntimeError):
            _x = self.block.getNeutronEnergyDepositionConstants()

    @patch.object(xsCollections, "computeGammaEnergyDepositionConstants")
    def test_getGammaEnergyDepositionConstants(self, mock_method):
        """Test RuntimeError and that it gets to the deposition constant call."""
        # make sure xsCollections.compute* gets hit
        _x = self.block.getGammaEnergyDepositionConstants()
        self.assertEqual(mock_method.call_count, 1)
        # set core.lib to None and get RuntimeError
        self.block.core.lib = None
        with self.assertRaises(RuntimeError):
            # fails because this test reactor does not have a cross-section library
            _x = self.block.getGammaEnergyDepositionConstants()


class TestNegativeVolume(unittest.TestCase):
    def test_negativeVolume(self):
        """Build a Block with WAY too many fuel pins & show that the derived volume is negative."""
        block = blocks.HexBlock("TestHexBlock")

        coldTemp = 20
        hotTemp = 200

        fuelDims = {
            "Tinput": coldTemp,
            "Thot": hotTemp,
            "od": 0.84,
            "id": 0.6,
            "mult": 1000.0,  # pack in too many fuels
        }
        fuel = components.Circle("fuel", "UZr", **fuelDims)

        coolantDims = {"Tinput": hotTemp, "Thot": hotTemp}
        coolant = components.DerivedShape("coolant", "Sodium", **coolantDims)

        interDims = {
            "Tinput": hotTemp,
            "Thot": hotTemp,
            "op": 17.8,
            "ip": 17.3,
            "mult": 1.0,
        }
        interSodium = components.Hexagon("interCoolant", "Sodium", **interDims)

        block.add(fuel)
        block.add(coolant)
        block.add(interSodium)
        block.setHeight(16.0)
        with self.assertRaises(ValueError):
            block.getVolumeFractions()


class HexBlock_TestCase(unittest.TestCase):
    def setUp(self):
        self.hexBlock = blocks.HexBlock("TestHexBlock")
        hexDims = {"Tinput": 273.0, "Thot": 273.0, "op": 70.6, "ip": 70.0, "mult": 1.0}
        self.hexComponent = components.Hexagon("duct", "UZr", **hexDims)
        self.hexBlock.add(self.hexComponent)
        self.hexBlock.add(components.Circle("clad", "HT9", Tinput=273.0, Thot=273.0, od=0.1, mult=169.0))
        self.hexBlock.add(components.Circle("wire", "HT9", Tinput=273.0, Thot=273.0, od=0.01, mult=169.0))
        self.hexBlock.add(components.DerivedShape("coolant", "Sodium", Tinput=273.0, Thot=273.0))
        self.r = tests.getEmptyHexReactor()
        self.hexBlock.autoCreateSpatialGrids(self.r.core.spatialGrid)
        a = makeTestAssembly(1, 1)
        a.add(self.hexBlock)
        loc1 = self.r.core.spatialGrid[0, 1, 0]
        self.r.core.add(a, loc1)

    def test_getArea(self):
        """Test that we can correctly calculate the area of a hexagonal block.

        .. test:: Users can create blocks that have the correct hexagonal area.
            :id: T_ARMI_BLOCK_HEX0
            :tests: R_ARMI_BLOCK_HEX
        """
        # Test for various outer and inner pitches for HexBlocks with hex holes
        for op in (20.0, 20.4, 20.1234, 25.001):
            for ip in (0.0, 5.0001, 7.123, 10.0):
                # generate a block with a different outer pitch
                hBlock = blocks.HexBlock("TestAreaHexBlock")
                hexDims = {
                    "Tinput": 273.0,
                    "Thot": 273.0,
                    "op": op,
                    "ip": ip,
                    "mult": 1.0,
                }
                hComponent = components.Hexagon("duct", "UZr", **hexDims)
                hBlock.add(hComponent)

                # verify the area of the hexagon (with a hex hole) is correct
                cur = hBlock.getArea()
                ref = math.sqrt(3) / 2.0 * op**2
                ref -= math.sqrt(3) / 2.0 * ip**2
                self.assertAlmostEqual(cur, ref, places=6, msg=str(op))

    def test_component_type(self):
        """
        Test that a hex block has the proper "hexagon" __name__.

        .. test:: Users can create blocks with a hexagonal shape.
            :id: T_ARMI_BLOCK_HEX1
            :tests: R_ARMI_BLOCK_HEX
        """
        pitch_comp_type = self.hexBlock.PITCH_COMPONENT_TYPE[0]
        self.assertEqual(pitch_comp_type.__name__, "Hexagon")

    def test_coords(self):
        """
        Test that coordinates are retrievable from a block.

        .. test:: Coordinates of a block are queryable.
            :id: T_ARMI_BLOCK_POSI1
            :tests: R_ARMI_BLOCK_POSI
        """
        core = self.hexBlock.core
        a = self.hexBlock.parent
        loc1 = core.spatialGrid[0, 1, 0]
        a.spatialLocator = loc1
        x0, y0 = self.hexBlock.coords()
        a.spatialLocator = core.spatialGrid[0, -1, 0]  # symmetric
        x2, y2 = self.hexBlock.coords()
        a.spatialLocator = loc1
        self.hexBlock.p.displacementX = 0.01
        self.hexBlock.p.displacementY = 0.02
        x1, y1 = self.hexBlock.coords()

        # make sure displacements are working
        self.assertAlmostEqual(x1 - x0, 1.0)
        self.assertAlmostEqual(y1 - y0, 2.0)

        # make sure location symmetry is working
        self.assertAlmostEqual(x0, -x2)
        self.assertAlmostEqual(y0, -y2)

    def test_getNumPins(self):
        self.assertEqual(self.hexBlock.getNumPins(), 169)

    def test_block_dims(self):
        """Tests that the block class can provide basic dimensionality information about itself."""
        self.assertAlmostEqual(4316.582, self.hexBlock.getVolume(), 3)
        self.assertAlmostEqual(70.6, self.hexBlock.getPitch(), 1)
        self.assertAlmostEqual(4316.582, self.hexBlock.getMaxArea(), 3)

        self.assertEqual(70, self.hexBlock.getDuctIP())
        self.assertEqual(70.6, self.hexBlock.getDuctOP())

        self.assertAlmostEqual(34.273, self.hexBlock.getPinToDuctGap(), 3)
        self.assertEqual(0.11, self.hexBlock.getPinPitch())
        self.assertAlmostEqual(300.889, self.hexBlock.getWettedPerimeter(), 3)
        self.assertAlmostEqual(4242.184, self.hexBlock.getFlowArea(), 3)
        self.assertAlmostEqual(56.395, self.hexBlock.getHydraulicDiameter(), 3)

    def test_symmetryFactor(self):
        # full hex
        self.hexBlock.spatialLocator = self.hexBlock.core.spatialGrid[2, 0, 0]
        self.hexBlock.clearCache()
        self.assertEqual(1.0, self.hexBlock.getSymmetryFactor())
        a0 = self.hexBlock.getArea()
        v0 = self.hexBlock.getVolume()
        m0 = self.hexBlock.getMass()

        # 1/3 symmetric
        self.hexBlock.spatialLocator = self.hexBlock.core.spatialGrid[0, 0, 0]
        self.hexBlock.clearCache()
        self.assertEqual(3.0, self.hexBlock.getSymmetryFactor())
        self.assertEqual(a0 / 3.0, self.hexBlock.getArea())
        self.assertEqual(v0 / 3.0, self.hexBlock.getVolume())
        self.assertAlmostEqual(m0 / 3.0, self.hexBlock.getMass())

    def test_retainState(self):
        """Ensure retainState restores params and spatialGrids."""
        self.hexBlock.spatialGrid = grids.HexGrid.fromPitch(1.0)
        self.hexBlock.setType("intercoolant")
        with self.hexBlock.retainState():
            self.hexBlock.setType("fuel")
            self.hexBlock.spatialGrid.changePitch(2.0)
        self.assertAlmostEqual(self.hexBlock.spatialGrid.pitch, 1.0)
        self.assertTrue(self.hexBlock.hasFlags(Flags.INTERCOOLANT))

    def test_getPinLocations(self):
        """Test pin locations can be obtained."""
        locs = set(self.hexBlock.getPinLocations())
        nPins = self.hexBlock.getNumPins()
        self.assertEqual(len(locs), nPins)
        for l in locs:
            self.assertIs(l.grid, self.hexBlock.spatialGrid)

        # Check all clad components are represented
        for c in self.hexBlock.getChildrenWithFlags(Flags.CLAD):
            if isinstance(c.spatialLocator, grids.MultiIndexLocation):
                for l in c.spatialLocator:
                    locs.remove(l)
            else:
                locs.remove(c.spatialLocator)
        self.assertFalse(
            locs,
            msg="Some clad locations were not found but returned by getPinLocations",
        )

    def test_getPinCoordsAndLocsAgree(self):
        """Ensure consistency in ordering of pin locations and coordinates."""
        locs = self.hexBlock.getPinLocations()
        coords = self.hexBlock.getPinCoordinates()
        self.assertEqual(len(locs), len(coords))
        for loc, coord in zip(locs, coords):
            convertedCoords = loc.getLocalCoordinates()
            np.testing.assert_array_equal(coord, convertedCoords, err_msg=f"{loc=}")

    def test_getPinCoords(self):
        blockPitch = self.hexBlock.getPitch()
        pinPitch = self.hexBlock.getPinPitch()
        nPins = self.hexBlock.getNumPins()
        side = hexagon.side(blockPitch)
        xyz = self.hexBlock.getPinCoordinates()
        x, y, z = xyz.T

        # these two pins should be side by side
        self.assertTrue(self.hexBlock.spatialGrid.cornersUp)
        self.assertAlmostEqual(y[1], y[2])
        self.assertAlmostEqual(x[1], -x[2])
        self.assertEqual(len(xyz), self.hexBlock.getNumPins())

        # ensure all pins are within the proper bounds of a
        # flats-up oriented hex block
        self.assertLess(max(y), blockPitch / 2.0)
        self.assertGreater(min(y), -blockPitch / 2.0)
        self.assertLess(max(x), side)
        self.assertGreater(min(x), -side)

        # center pin should be at 0
        mags = x * x + y * y
        minIndex = mags.argmin()
        cx = x[minIndex]
        cy = y[minIndex]
        self.assertAlmostEqual(cx, 0.0)
        self.assertAlmostEqual(cy, 0.0)

        # extreme pin should be at proper radius
        cornerMag = mags.max()
        nRings = hexagon.numRingsToHoldNumCells(nPins) - 1
        self.assertAlmostEqual(math.sqrt(cornerMag), nRings * pinPitch)

        # all z coords equal to zero
        np.testing.assert_equal(z, 0)

    def test_getPitchHomogeneousBlock(self):
        """
        Demonstrate how to communicate pitch on a hex block with unshaped components.

        Notes
        -----
        This assumes there are 3 materials in the homogeneous block, one with half the area
        fraction, and 2 with 1/4 each.
        """
        desiredPitch = 14.0
        hexTotalArea = hexagon.area(desiredPitch)

        compArgs = {"Tinput": 273.0, "Thot": 273.0}
        areaFractions = [0.5, 0.25, 0.25]
        materials = ["HT9", "UZr", "Sodium"]

        # There are 2 ways to do this, the first is to pick a component to be the pitch defining
        # component, and given it the shape of a hexagon to define the pitch. The hexagon outer
        # pitch (op) is defined by the pitch of the block/assembly. The ip is defined by whatever
        # thickness is necessary to have the desired area fraction. The second way is shown in the
        # second half of this test.
        hexBlock = blocks.HexBlock("TestHexBlock")

        hexComponentArea = areaFractions[0] * hexTotalArea

        # Picking 1st material to use for the hex component here, but really the choice is
        # arbitrary. area grows quadratically with op
        ipNeededForCorrectArea = desiredPitch * areaFractions[0] ** 0.5
        self.assertEqual(hexComponentArea, hexTotalArea - hexagon.area(ipNeededForCorrectArea))

        hexArgs = {"op": desiredPitch, "ip": ipNeededForCorrectArea, "mult": 1.0}
        hexArgs.update(compArgs)
        pitchDefiningComponent = components.Hexagon("pitchComp", materials[0], **hexArgs)
        hexBlock.add(pitchDefiningComponent)

        # hex component is added, now add the rest as unshaped.
        for aFrac, material in zip(areaFractions[1:], materials[1:]):
            unshapedArgs = {"area": hexTotalArea * aFrac}
            unshapedArgs.update(compArgs)
            name = f"unshaped {material}"
            comp = components.UnshapedComponent(name, material, **unshapedArgs)
            hexBlock.add(comp)

        self.assertEqual(desiredPitch, hexBlock.getPitch())
        self.assertAlmostEqual(hexTotalArea, hexBlock.getMaxArea())
        self.assertAlmostEqual(sum(c.getArea() for c in hexBlock), hexTotalArea)

        # For this second way, we will simply define the 3 components as unshaped, with  the desired
        # area fractions, and make a 4th component that is an infinitely thin hexagon with the the
        # desired pitch. The downside of this method is that now the block has a fourth component
        # with no volume.
        hexBlock = blocks.HexBlock("TestHexBlock")
        for aFrac, material in zip(areaFractions, materials):
            unshapedArgs = {"area": hexTotalArea * aFrac}
            unshapedArgs.update(compArgs)
            name = f"unshaped {material}"
            comp = components.UnshapedComponent(name, material, **unshapedArgs)
            hexBlock.add(comp)

        # We haven't set a pitch defining component this time so set it now with 0 area.
        pitchDefiningComponent = components.Hexagon(
            "pitchComp", "Void", op=desiredPitch, ip=desiredPitch, mult=1, **compArgs
        )
        hexBlock.add(pitchDefiningComponent)
        self.assertEqual(desiredPitch, hexBlock.getPitch())
        self.assertAlmostEqual(hexTotalArea, hexBlock.getMaxArea())
        self.assertAlmostEqual(sum(c.getArea() for c in hexBlock), hexTotalArea)

    def test_getDuctPitch(self):
        ductIP = self.hexBlock.getDuctIP()
        self.assertAlmostEqual(70.0, ductIP)
        ductOP = self.hexBlock.getDuctOP()
        self.assertAlmostEqual(70.6, ductOP)

    def test_getPinCenterFlatToFlat(self):
        nRings = hexagon.numRingsToHoldNumCells(self.hexBlock.getNumPins())
        pinPitch = self.hexBlock.getPinPitch()
        pinCenterCornerToCorner = 2 * (nRings - 1) * pinPitch
        pinCenterFlatToFlat = math.sqrt(3.0) / 2.0 * pinCenterCornerToCorner
        f2f = self.hexBlock.getPinCenterFlatToFlat()
        self.assertAlmostEqual(pinCenterFlatToFlat, f2f)

    def test_gridCreation(self):
        """Create a grid for a block, and show that it can handle components with multiplicity > 1.

        .. test:: Grids can handle components with multiplicity > 1.
            :id: T_ARMI_GRID_MULT
            :tests: R_ARMI_GRID_MULT
        """
        b = self.hexBlock
        # The block should have a spatial grid at construction,
        # since it has mults = 1 or 169 from setup
        b.autoCreateSpatialGrids(self.r.core.spatialGrid)
        self.assertIsNotNone(b.spatialGrid)
        for c in b:
            if c.getDimension("mult", cold=True) == 169:
                # Then it's spatialLocator must be of size 169
                locations = c.spatialLocator
                self.assertEqual(type(locations), grids.MultiIndexLocation)

                mult = 0
                uniqueLocations = set()
                for loc in locations:
                    mult = mult + 1

                    # test for the uniqueness of the locations (since mult > 1)
                    if loc not in uniqueLocations:
                        uniqueLocations.add(loc)
                    else:
                        self.assertTrue(False, msg="Duplicate location found!")

                self.assertEqual(mult, 169)

    def test_gridNumPinsAndLocations(self):
        b = blocks.HexBlock("fuel", height=10.0)

        fuelDims = {"Tinput": 25.0, "Thot": 600, "od": 0.76, "id": 0.00, "mult": 168.0}
        cladDims = {"Tinput": 25.0, "Thot": 450, "od": 0.80, "id": 0.77, "mult": 168.0}
        ductDims = {"Tinput": 25.0, "Thot": 400, "op": 16, "ip": 15.3, "mult": 1.0}
        wireDims = {
            "Tinput": 25.0,
            "Thot": 600,
            "od": 0.1,
            "id": 0.0,
            "axialPitch": 30.0,
            "helixDiameter": 0.9,
            "mult": 168.0,
        }
        wire = components.Helix("wire", "HT9", **wireDims)
        fuel = components.Circle("fuel", "UZr", **fuelDims)
        clad = components.Circle("clad", "HT9", **cladDims)
        duct = components.Hexagon("duct", "HT9", **ductDims)
        b.add(fuel)
        b.add(clad)
        b.add(duct)
        b.add(wire)
        with self.assertRaises(ValueError):
            b.autoCreateSpatialGrids(self.r.core.spatialGrid)
        self.assertIsNone(b.spatialGrid)

    def test_gridNotCreatedMultipleMultiplicities(self):
        wireDims = {
            "Tinput": 200,
            "Thot": 200,
            "od": 0.1,
            "id": 0.0,
            "axialPitch": 30.0,
            "helixDiameter": 1.1,
            "mult": 21.0,
        }
        # add a wire only some places in the block, so grid should not be created.
        wire = components.Helix("wire", "HT9", **wireDims)
        self.hexBlock.add(wire)
        self.hexBlock.spatialGrid = None  # clear existing
        self.hexBlock.autoCreateSpatialGrids(self.r.core.spatialGrid)
        self.assertIsNone(self.hexBlock.spatialGrid)

    def test_assignPinIndicesToFullGrid(self):
        """Ensure we can assign pin indices to fuel if it occupies the entire spatial grid."""
        b = blocks.HexBlock("fuel")
        fuel = components.Circle(
            "fuel",
            "UZr",
            Tinput=25.0,
            Thot=600.0,
            od=0.76,
            mult=169,
        )
        b.add(fuel)

        clad = components.Circle(
            "clad",
            "HT9",
            Tinput=25.0,
            Thot=450.0,
            id=0.77,
            od=0.80,
            mult=169,
        )
        b.add(clad)

        wire = components.Helix(
            "wire", "HT9", Tinput=25.0, Thot=600, id=0, od=0.1, axialPitch=30, helixDiameter=0.9, mult=169
        )
        b.add(wire)

        duct = components.Hexagon("duct", "HT9", Tinput=25.0, Thot=400, ip=15.3, op=16, mult=1)
        b.add(duct)

        b.autoCreateSpatialGrids(self.r.core.spatialGrid)
        self.assertIsNotNone(b.spatialGrid)

        b.assignPinIndices()
        self.assertIsNotNone(fuel.p.pinIndices)
        indices = fuel.getPinIndices()
        self.assertIsNotNone(indices)
        np.testing.assert_allclose(indices, np.arange(169, dtype=int))


class MultiPinIndicesTests(unittest.TestCase):
    BP_STR = """
blocks:
    fuel: &fuel_block
        grid name: fuel grid
        fuel 1: &fuel_def
            shape: Circle
            # Use void material because we don't need nuclides, just components with flags
            material: Void
            od: 0.68
            Tinput: 25
            Thot: 600
            latticeIDs: [1]
            flags: primary fuel
        clad 1: &clad_def
            shape: Circle
            material: Void
            id: 0.7
            od: 0.71
            Tinput: 600
            Thot: 450
            latticeIDs: [1]
        fuel 2:
            <<: *fuel_def
            latticeIDs: [2]
            flags: secondary fuel
        clad 2:
            <<: *clad_def
            latticeIDs: [2]
        duct:
            shape: Hexagon
            material: Void
            Tinput: 25
            Thot: 450
            ip: 15.3
            op: 16
assemblies:
    fuel:
        specifier: F
        blocks: [*fuel_block]
        height: [10]
        axial mesh points: [1]
        xs types: [A]
grids:
    fuel grid:
        geom: hex_corners_up
        symmetry: full
        # Kind of a convoluted map but helps test a lot of edge conditions
        lattice map: |
            - - -  1 1 1 1
              - - 1 1 1 1 1
               - 1 1 2 2 1 1
                1 1 2 1 2 1 1
                 1 1 2 2 1 1
                  1 1 1 1 1
                   1 2 1 1
nuclide flags:

"""

    @classmethod
    def setUpClass(cls):
        cs = settings.Settings()
        bp: blueprints.Blueprints = blueprints.Blueprints.load(cls.BP_STR)
        bp._prepConstruction(cs)
        cls._originalBlock: blocks.HexBlock = bp.blockDesigns["fuel"].construct(cs, bp, 0, 2, 10, "A", {})

    def setUp(self):
        self.block = copy.deepcopy(self._originalBlock)
        self.block.assignPinIndices()
        self.allLocations = self.block.getPinLocations()
        self.fuelPins = self.block.getComponents(Flags.FUEL)

    def test_nonOverlappingIndices(self):
        """Test pin indices are complete and non-overlapping."""
        foundIndices: set[int] = set()
        for fp in self.fuelPins:
            actualIndices = fp.getPinIndices()
            self.assertIsNotNone(actualIndices, fp)
            overlap = foundIndices.intersection(actualIndices)
            self.assertFalse(overlap, msg="Found overlapping indices on unique fuel pin")
            foundIndices.update(actualIndices)
        # Make sure we have all the indices covered
        for i in range(len(self.allLocations)):
            self.assertIn(i, foundIndices)

    def test_consistentPinOrdering(self):
        """Test values of pin indices on a component align with pin locations of that component within the block."""
        for fp in self.fuelPins:
            locations: list[grids.IndexLocation] = list(fp.spatialLocator)
            indices = fp.getPinIndices()
            self.assertEqual(len(locations), len(indices), msg=fp)
            for loc, ix in zip(locations, indices):
                indexInBlock = self.allLocations.index(loc)
                self.assertEqual(ix, indexInBlock, msg=f"{loc=} in {fp}")

    def test_noPinIndicesForHexes(self):
        """Test we never get pin indices for hexagons."""
        duct = self.block.getComponent(Flags.DUCT)
        self.assertIsNone(duct.p.pinIndices)
        with self.assertRaisesRegex(ValueError, "no pin indices"):
            duct.getPinIndices()

    def test_recoverCladIndicesFromFuel(self):
        """Show the same indices for cladding are found for fuel that it wraps."""
        clad = self.block.getComponents(Flags.CLAD)[0]
        cladIndices = clad.getPinIndices()
        fuel = self.block.getComponents(Flags.FUEL)[0]
        fuelIndices = fuel.getPinIndices()
        # Show not only are they equal, we get literally the same object
        # through the dimension linking. This only works if the fuel pin
        # is not at all the lattice sites, or else they'd both be equal
        # equivalent to np.arange(0, N - 1) but different instances of the same data
        self.assertIs(cladIndices, fuelIndices)

    def test_locations(self):
        """Ensure we have locations consistent with the lattice map."""
        primary: components.Circle = self.block.getComponent(Flags.PRIMARY)
        # Count the number of primary pins in the blueprint above
        nPrimary = 30
        expectedPrimaryRingPos = {
            (1, 1),
        }
        # 12 and 18 pins in one-indexed rings three and four.
        # remember that range is exclusive of the stop
        expectedPrimaryRingPos.update((3, i) for i in range(1, 13))
        expectedPrimaryRingPos.update((4, i) for i in range(1, 19))
        # special pin designed to poke some edge cases
        # remember ARMI hex positions start at 1 in the north east corner and go counterclockwise
        trickyPin = (4, 11)
        # drop the tricky pin in the fourth ring
        expectedPrimaryRingPos.remove(trickyPin)
        self._checkPinLocationsAndIndices(primary, nPrimary, expectedPrimaryRingPos)

        secondary: components.Circle = self.block.getComponent(Flags.SECONDARY)
        nSecondary = 7
        # six pins in one-indexed ring two
        expectedSecondaryRingPos = {(2, i) for i in range(1, 7)}
        expectedSecondaryRingPos.add(trickyPin)
        self._checkPinLocationsAndIndices(secondary, nSecondary, expectedSecondaryRingPos)

    def _checkPinLocationsAndIndices(
        self, pin: components.Circle, expectedNumPins: int, expectedRingPos: set[tuple[int, int]]
    ):
        self.assertEqual(
            len(expectedRingPos),
            expectedNumPins,
            msg="Expected pins and locations differ. Your test inputs are not setup correct.",
        )
        self.assertEqual(pin.getDimension("mult"), expectedNumPins)
        self.assertEqual(len(pin.spatialLocator), expectedNumPins)
        primaryIndices = pin.getPinIndices()
        self.assertIsNotNone(primaryIndices)
        self.assertEqual(primaryIndices.size, expectedNumPins)
        allLocations = self.block.getPinLocations()
        for ix in primaryIndices:
            loc = allLocations[ix]
            ringPos = loc.getRingPos()
            self.assertIn(ringPos, expectedRingPos, msg=f"{ix=} : {loc=}")

    def test_nonFueledBlock(self):
        """If we have no fuel, but we have clad, we should still have pin indices."""
        nonFuel = copy.deepcopy(self._originalBlock)
        # strip out fuel flags
        for c in nonFuel.iterComponents(Flags.FUEL):
            c.p.flags &= ~Flags.FUEL
        nonFuel.assignPinIndices()
        # Should still have what ARMI considers pins
        self.assertTrue(nonFuel.getPinLocations())
        for c in nonFuel.iterComponents(Flags.CLAD):
            self.assertIsNotNone(c.getPinIndices())


class TestHexBlockOrientation(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    @staticmethod
    def getLocalCoordinatesBlockBounds(b: blocks.HexBlock):
        """Call getLocalCoordinates() for every Component in the Block and find the X/Y bounds."""
        maxX = -111
        minX = 999
        maxY = -111
        minY = 999
        for comp in b:
            locs = comp.spatialLocator
            if not isinstance(locs, grids.MultiIndexLocation):
                locs = [locs]

            for loc in locs:
                x, y, _ = loc.getLocalCoordinates()
                if x > maxX:
                    maxX = x
                elif x < minX:
                    minX = x

                if y > maxY:
                    maxY = y
                elif y < minY:
                    minY = y

        return minX, maxX, minY, maxY

    def test_validateReactorCornersUp(self):
        """Validate the spatial grid for a corners up HexBlock and its children."""
        # load a corners up reactor
        _o, r = loadTestReactor(
            os.path.join(TEST_ROOT, "smallestTestReactor"),
            inputFileName="armiRunSmallest.yaml",
        )

        # grab a pinned fuel block, and verify it is flats up
        b = r.core.getFirstBlock(Flags.FUEL)
        self.assertTrue(r.core.spatialGrid.cornersUp)
        self.assertFalse(b.spatialGrid.cornersUp)
        self.assertNotEqual(r.core.spatialGrid.cornersUp, b.spatialGrid.cornersUp)

        # for a flats up block-grid, the hex centroids should stretch more in Y than X
        minX, maxX, minY, maxY = self.getLocalCoordinatesBlockBounds(b)
        ratio = (maxY - minY) / (maxX - minX)
        self.assertAlmostEqual(ratio, 2 / math.sqrt(3), delta=0.0001)

    def test_validateReactorFlatsUp(self):
        """Validate the spatial grid for a flats up HexBlock and its children."""
        # copy the files over
        inDir = os.path.join(TEST_ROOT, "smallestTestReactor")
        for filePath in glob(os.path.join(inDir, "*.yaml")):
            outPath = os.path.join(self.td.destination, os.path.basename(filePath))
            shutil.copyfile(filePath, outPath)

        # modify the reactor to make it flats up
        testFile = os.path.join(self.td.destination, "refSmallestReactor.yaml")
        txt = open(testFile, "r").read()
        txt = txt.replace("geom: hex_corners_up", "geom: hex")
        open(testFile, "w").write(txt)

        # load a flats up reactor
        _o, r = loadTestReactor(self.td.destination, inputFileName="armiRunSmallest.yaml")

        # grab a pinned fuel block, and verify it is corners up
        b = r.core.getFirstBlock(Flags.FUEL)
        self.assertFalse(r.core.spatialGrid.cornersUp)
        self.assertTrue(b.spatialGrid.cornersUp)
        self.assertNotEqual(r.core.spatialGrid.cornersUp, b.spatialGrid.cornersUp)

        # for a corners up block-grid, the hex centroids should stretch more in X than Y
        minX, maxX, minY, maxY = self.getLocalCoordinatesBlockBounds(b)
        ratio = (maxX - minX) / (maxY - minY)
        self.assertAlmostEqual(ratio, 2 / math.sqrt(3), delta=0.0001)


class ThRZBlock_TestCase(unittest.TestCase):
    def setUp(self):
        self.ThRZBlock = blocks.ThRZBlock("TestThRZBlock")
        self.ThRZBlock.add(
            components.DifferentialRadialSegment(
                "fuel",
                "UZr",
                Tinput=273.0,
                Thot=273.0,
                inner_radius=0.0,
                radius_differential=40.0,
                inner_theta=0.0,
                azimuthal_differential=1.5 * math.pi,
                inner_axial=5.0,
                height=10.0,
                mult=1.0,
            )
        )
        self.ThRZBlock.add(
            components.DifferentialRadialSegment(
                "coolant",
                "Sodium",
                Tinput=273.0,
                Thot=273.0,
                inner_radius=40.0,
                radius_differential=10.0,
                inner_theta=0.0,
                azimuthal_differential=1.5 * math.pi,
                inner_axial=5.0,
                height=10.0,
                mult=1.0,
            )
        )
        self.ThRZBlock.add(
            components.DifferentialRadialSegment(
                "clad",
                "HT9",
                Tinput=273.0,
                Thot=273.0,
                inner_radius=50.0,
                radius_differential=7.0,
                inner_theta=0.0,
                azimuthal_differential=1.5 * math.pi,
                inner_axial=5.0,
                height=10.0,
                mult=1.0,
            )
        )
        self.ThRZBlock.add(
            components.DifferentialRadialSegment(
                "wire",
                "HT9",
                Tinput=273.0,
                Thot=273.0,
                inner_radius=57.0,
                radius_differential=3.0,
                inner_theta=0.0,
                azimuthal_differential=1.5 * math.pi,
                inner_axial=5.0,
                height=10.0,
                mult=1.0,
            )
        )
        # random 1/4 chunk taken out to exercise Theta-RZ block capabilities
        self.ThRZBlock.add(
            components.DifferentialRadialSegment(
                "chunk",
                "Sodium",
                Tinput=273.0,
                Thot=273.0,
                inner_radius=0.0,
                radius_differential=60.0,
                inner_theta=1.5 * math.pi,
                azimuthal_differential=0.5 * math.pi,
                inner_axial=5.0,
                height=10.0,
                mult=1.0,
            )
        )

    def test_radii(self):
        radialInner = self.ThRZBlock.radialInner()
        self.assertEqual(0.0, radialInner)
        radialOuter = self.ThRZBlock.radialOuter()
        self.assertEqual(60.0, radialOuter)

    def test_theta(self):
        thetaInner = self.ThRZBlock.thetaInner()
        self.assertEqual(0.0, thetaInner)
        thetaOuter = self.ThRZBlock.thetaOuter()
        self.assertEqual(2.0 * math.pi, thetaOuter)

    def test_axial(self):
        axialInner = self.ThRZBlock.axialInner()
        self.assertEqual({5.0}, axialInner)
        axialOuter = self.ThRZBlock.axialOuter()
        self.assertEqual({15.0}, axialOuter)

    def test_verifyBlockDims(self):
        """
        This function is currently null. It consists of a single line that returns nothing. This
        test covers that line. If the function is ever implemented, it can be tested here.
        """
        self.ThRZBlock.verifyBlockDims()

    def test_getThetaRZGrid(self):
        """Since not applicable to ThetaRZ Grids."""
        b = self.ThRZBlock
        self.assertIsNone(b.spatialGrid)
        b.autoCreateSpatialGrids("FakeSpatilGrid")
        self.assertIsNotNone(b.spatialGrid)

    def test_getWettedPerimeter(self):
        with self.assertRaises(NotImplementedError):
            _ = self.ThRZBlock.getWettedPerimeter()

    def test_getHydraulicDiameter(self):
        with self.assertRaises(NotImplementedError):
            _ = self.ThRZBlock.getHydraulicDiameter()


class CartesianBlock_TestCase(unittest.TestCase):
    """Tests for blocks with rectangular/square outer shape."""

    PITCH = 70

    def setUp(self):
        caseSetting = settings.Settings()
        self.cartesianBlock = blocks.CartesianBlock("TestCartesianBlock", caseSetting)

        self.cartesianComponent = components.HoledSquare(
            "duct",
            "UZr",
            Tinput=273.0,
            Thot=273.0,
            holeOD=68.0,
            widthOuter=self.PITCH,
            mult=1.0,
        )
        self.cartesianBlock.add(self.cartesianComponent)
        self.cartesianBlock.add(components.Circle("clad", "HT9", Tinput=273.0, Thot=273.0, od=68.0, mult=169.0))

    def test_getPitchSquare(self):
        self.assertEqual(self.cartesianBlock.getPitch(), (self.PITCH, self.PITCH))

    def test_getPitchHomogeneousBlock(self):
        """
        Demonstrate how to communicate pitch on a hex block with unshaped components.

        Notes
        -----
        This assumes there are 3 materials in the homogeneous block, one with half the area
        fraction, and 2 with 1/4 each.
        """
        desiredPitch = (10.0, 12.0)
        rectTotalArea = desiredPitch[0] * desiredPitch[1]

        compArgs = {"Tinput": 273.0, "Thot": 273.0}
        areaFractions = [0.5, 0.25, 0.25]
        materials = ["HT9", "UZr", "Sodium"]

        # There are 2 ways to do this, the first is to pick a component to be the pitch defining
        # component, and given it the shape of a rectangle to define the pitch. The rectangle outer
        # dimensions is defined by the pitch of the block/assembly. The inner dimensions is defined
        # by whatever thickness is necessary to have the desired area fraction. The second way is to
        # define all physical material components as unshaped, and add an additional infinitely thin
        # Void component (no area) that defines pitch. See second part of
        # HexBlock_TestCase.test_getPitchHomogeneousBlock for demonstration.
        cartBlock = blocks.CartesianBlock("TestCartBlock")

        hexComponentArea = areaFractions[0] * rectTotalArea

        # Picking 1st material to use for the hex component here, but really the choice is
        # arbitrary.
        # area grows quadratically with outer dimensions.
        # Note there are infinitely many inner dims that would preserve area, this is just one.
        innerDims = [dim * areaFractions[0] ** 0.5 for dim in desiredPitch]
        self.assertAlmostEqual(hexComponentArea, rectTotalArea - innerDims[0] * innerDims[1])

        rectArgs = {
            "lengthOuter": desiredPitch[0],
            "lengthInner": innerDims[0],
            "widthOuter": desiredPitch[1],
            "widthInner": innerDims[1],
            "mult": 1.0,
        }
        rectArgs.update(compArgs)
        pitchDefiningComponent = components.Rectangle("pitchComp", materials[0], **rectArgs)
        cartBlock.add(pitchDefiningComponent)

        # Rectangle component is added, now add the rest as unshaped.
        for aFrac, material in zip(areaFractions[1:], materials[1:]):
            unshapedArgs = {"area": rectTotalArea * aFrac}
            unshapedArgs.update(compArgs)
            name = f"unshaped {material}"
            comp = components.UnshapedComponent(name, material, **unshapedArgs)
            cartBlock.add(comp)

        self.assertEqual(desiredPitch, cartBlock.getPitch())
        self.assertAlmostEqual(rectTotalArea, cartBlock.getMaxArea())
        self.assertAlmostEqual(sum(c.getArea() for c in cartBlock), rectTotalArea)

    def test_getCartesianGrid(self):
        """Since not applicable to Cartesian Grids."""
        b = self.cartesianBlock
        self.assertIsNone(b.spatialGrid)
        b.autoCreateSpatialGrids("FakeSpatialGrid")
        self.assertIsNotNone(b.spatialGrid)

    def test_getWettedPerimeter(self):
        with self.assertRaises(NotImplementedError):
            _ = self.cartesianBlock.getWettedPerimeter()

    def test_getHydraulicDiameter(self):
        with self.assertRaises(NotImplementedError):
            _ = self.cartesianBlock.getHydraulicDiameter()


class MassConservationTests(unittest.TestCase):
    """Tests designed to verify mass conservation during thermal expansion."""

    def setUp(self):
        self.b = buildSimpleFuelBlock()

    def test_heightExpansionDifferences(self):
        """The point of this test is to determine if the number densities stay the same with two
        different heights of the same block.  Since we want to expand a block from cold temperatures
        to hot using the fuel expansion coefficient (most important neutronicall), other components
        are not grown correctly. This means that on the block level, axial expansion will NOT
        conserve mass of non-fuel components. However, the excess mass is simply added to the top of
        the reactor in the plenum regions (or any non fueled region).
        """
        # Assume the default block height is 'cold' height.  Now we must determine what the hot
        # height should be based on thermal expansion.  Change the height of the block based on the
        # different thermal expansions of the components then see the effect on number densities.
        fuel = self.b.getComponent(Flags.FUEL)
        height = self.b.getHeight()
        Thot = fuel.temperatureInC
        Tcold = fuel.inputTemperatureInC

        dllHot = fuel.getProperties().linearExpansionFactor(Tc=Thot, T0=Tcold)
        hotFuelHeight = height * (1 + dllHot)

        self.b.setHeight(hotFuelHeight)

        hotFuelU238 = self.b.getNumberDensity("U238")
        hotFuelIRON = self.b.getNumberDensity("FE")

        # look at clad
        clad = self.b.getComponent(Flags.CLAD)

        Thot = clad.temperatureInC
        Tcold = clad.inputTemperatureInC

        dllHot = fuel.getProperties().linearExpansionFactor(Tc=Thot, T0=Tcold)
        hotCladHeight = height * (1 + dllHot)

        self.b.setHeight(hotCladHeight)

        hotCladU238 = self.b.getNumberDensity("U238")
        hotCladIRON = self.b.getNumberDensity("FE")

        self.assertAlmostEqual(
            hotFuelU238,
            hotCladU238,
            10,
            "Number Density of fuel in one height ({0}) != number density of fuel at another "
            "height {1}. Number density conservation violated during thermal "
            "expansion".format(hotFuelU238, hotCladU238),
        )

        self.assertAlmostEqual(
            hotFuelIRON,
            hotCladIRON,
            10,
            "Number Density of clad in one height ({0}) != number density of clad at another "
            "height {1}. Number density conservation violated during thermal "
            "expansion".format(hotFuelIRON, hotCladIRON),
        )

    def test_massFuelHeatup(self):
        fuel = self.b.getComponent(Flags.FUEL)
        massCold = fuel.getMass()
        fuel.setTemperature(100)
        massHot = fuel.getMass()

        self.assertAlmostEqual(
            massCold,
            massHot,
            10,
            "Cold mass of fuel ({0}) != hot mass {1}. Mass conservation violated during thermal expansion".format(
                massCold, massHot
            ),
        )

    def test_massCladHeatup(self):
        cladding = self.b.getComponent(Flags.CLAD)
        massCold = cladding.getMass()
        cladding.setTemperature(100)
        massHot = cladding.getMass()

        self.assertAlmostEqual(
            massCold,
            massHot,
            10,
            "Cold mass of clad ({0}) != hot mass {1}. Mass conservation violated during thermal expansion".format(
                massCold, massHot
            ),
        )

    def test_massDuctHeatup(self):
        duct = self.b.getComponent(Flags.DUCT)
        massCold = duct.getMass()
        duct.setTemperature(100)
        massHot = duct.getMass()

        self.assertAlmostEqual(
            massCold,
            massHot,
            10,
            "Cold mass of duct ({0}) != hot mass {1}. Mass conservation violated during thermal expansion".format(
                massCold, massHot
            ),
        )

    def test_massCoolHeatup(self):
        """Make sure mass of coolant goes down when it heats up."""
        coolant = self.b.getComponent(Flags.COOLANT)
        massCold = coolant.getMass()
        coolant.setTemperature(coolant.temperatureInC + 100)
        massHot = coolant.getMass()

        self.assertGreater(
            massCold,
            massHot,
            "Cold mass of coolant ({0}) <= hot mass {1}. Mass conservation not violated during "
            "thermal expansion of coolant".format(massCold, massHot),
        )

    def test_dimensionDuctHeatup(self):
        duct = self.b.getComponent(Flags.DUCT)
        pitchCold = duct.getDimension("op", cold=True)
        duct.setTemperature(100)
        pitchHot = duct.getDimension("op")
        dLL = duct.getProperties().linearExpansionFactor(100, 25)
        correctHot = pitchCold * (1 + dLL)
        self.assertAlmostEqual(
            correctHot,
            pitchHot,
            10,
            "Theoretical pitch of duct ({0}) != hot pitch {1}. Linear expansion violated during "
            "heatup. \nTc={tc} Tref={tref} dLL={dLL} cold={pcold}".format(
                correctHot,
                pitchHot,
                tc=duct.temperatureInC,
                tref=duct.inputTemperatureInC,
                dLL=dLL,
                pcold=pitchCold,
            ),
        )

    def test_coldMass(self):
        """
        Verify that the cold mass is what it should be, even though the hot height is input.

        At the cold temperature (but with hot height), the mass should be the same as at hot
        temperature and hot height.
        """
        fuel = self.b.getComponent(Flags.FUEL)
        # set ref (input/cold) temperature.
        Thot = fuel.temperatureInC
        Tcold = fuel.inputTemperatureInC

        # change temp to cold
        fuel.setTemperature(Tcold)
        massCold = fuel.getMass()
        fuelArea = fuel.getArea()
        # we are at cold temp so cold and hot area are equal
        self.assertAlmostEqual(fuel.getArea(cold=True), fuel.getArea())
        height = self.b.getHeight()  # hot height.
        rho = fuel.getProperties().density(Tc=Tcold)
        # can't use getThermalExpansionFactor since hot=cold so it would be 0
        dllHot = fuel.getProperties().linearExpansionFactor(Tc=Thot, T0=Tcold)
        coldHeight = height / (1 + dllHot)
        theoreticalMass = fuelArea * coldHeight * rho

        self.assertAlmostEqual(
            massCold,
            theoreticalMass,
            7,
            msg="Cold mass of fuel ({0}) != theoretical mass {1}.  Check calculation of cold mass".format(
                massCold, theoreticalMass
            ),
        )

    def test_massConsistency(self):
        """Verify that the sum of the component masses equals the total mass."""
        tMass = 0.0
        for child in self.b:
            tMass += child.getMass()
        bMass = self.b.getMass()
        self.assertAlmostEqual(
            tMass,
            bMass,
            10,
            "Sum of component mass {0} != total block mass {1}. ".format(tMass, bMass),
        )
