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

r"""Tests blocks.py"""
import copy
import math
import os
import unittest
import numpy
from numpy.testing import assert_allclose

from armi.reactor import blocks
from armi.reactor import components
import armi.runLog as runLog
import armi.settings as settings
from armi.reactor.components import shapes
from armi import materials
from armi.nucDirectory import nucDir, nuclideBases
from armi.utils.units import MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
from armi.tests import TEST_ROOT
from armi.utils import units
from armi.reactor.flags import Flags
from armi import tests
from armi.reactor import grids
from armi.reactor.tests.test_assemblies import makeTestAssembly
from armi.tests import ISOAA_PATH
from armi.nuclearDataIO import isotxs
from armi.reactor import geometry


def loadTestBlock(cold=True):
    """Build an annular test block for evaluating unit tests."""
    caseSetting = settings.Settings()
    settings.setMasterCs(caseSetting)
    runLog.setVerbosity("error")
    caseSetting["nCycles"] = 1
    r = tests.getEmptyHexReactor()

    assemNum = 3
    block = blocks.HexBlock("TestHexBlock")
    block.setType("defaultType")
    block.p.nPins = 217
    Assembly = makeTestAssembly(assemNum, 1, r=r)

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
        "mult": 217.0,
    }
    fuel = components.Circle("fuel", "UZr", **fuelDims)

    bondDims = {
        "Tinput": coldTemp,
        "Thot": hotTempCoolant,
        "od": "fuel.id",
        "id": 0.3,
        "mult": 217.0,
    }
    bondDims["components"] = {"fuel": fuel}
    bond = components.Circle("bond", "Sodium", **bondDims)

    annularVoidDims = {
        "Tinput": hotTempStructure,
        "Thot": hotTempStructure,
        "od": "bond.id",
        "id": 0.0,
        "mult": 217.0,
    }
    annularVoidDims["components"] = {"bond": bond}
    annularVoid = components.Circle("annular void", "Void", **annularVoidDims)

    innerLinerDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "od": 0.90,
        "id": 0.85,
        "mult": 217.0,
    }
    innerLiner = components.Circle("inner liner", "Graphite", **innerLinerDims)

    fuelLinerGapDims = {
        "Tinput": hotTempStructure,
        "Thot": hotTempStructure,
        "od": "inner liner.id",
        "id": "fuel.od",
        "mult": 217.0,
    }
    fuelLinerGapDims["components"] = {"inner liner": innerLiner, "fuel": fuel}
    fuelLinerGap = components.Circle("gap1", "Void", **fuelLinerGapDims)

    outerLinerDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "od": 0.95,
        "id": 0.90,
        "mult": 217.0,
    }
    outerLiner = components.Circle("outer liner", "HT9", **outerLinerDims)

    linerLinerGapDims = {
        "Tinput": hotTempStructure,
        "Thot": hotTempStructure,
        "od": "outer liner.id",
        "id": "inner liner.od",
        "mult": 217.0,
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
        "mult": 217.0,
    }
    cladding = components.Circle("clad", "HT9", **claddingDims)

    linerCladGapDims = {
        "Tinput": hotTempStructure,
        "Thot": hotTempStructure,
        "od": "clad.id",
        "id": "outer liner.od",
        "mult": 217.0,
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
        "mult": 217.0,
    }
    wire = components.Helix("wire", "HT9", **wireDims)

    coolantDims = {"Tinput": hotTempCoolant, "Thot": hotTempCoolant}
    coolant = components.DerivedShape("coolant", "Sodium", **coolantDims)

    ductDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "ip": 16.6,
        "op": 17.3,
        "mult": 1.0,
    }
    duct = components.Hexagon("duct", "HT9", **ductDims)

    interDims = {
        "Tinput": hotTempCoolant,
        "Thot": hotTempCoolant,
        "op": 17.8,
        "ip": "duct.op",
        "mult": 1.0,
    }
    interDims["components"] = {"duct": duct}
    interSodium = components.Hexagon("interCoolant", "Sodium", **interDims)

    block.addComponent(annularVoid)
    block.addComponent(bond)
    block.addComponent(fuel)
    block.addComponent(fuelLinerGap)
    block.addComponent(innerLiner)
    block.addComponent(linerLinerGap)
    block.addComponent(outerLiner)
    block.addComponent(linerCladGap)
    block.addComponent(cladding)

    block.addComponent(wire)
    block.addComponent(coolant)
    block.addComponent(duct)
    block.addComponent(interSodium)

    block.getVolumeFractions()  # TODO: remove, should be no-op when removed self.cached

    block.setHeight(16.0)

    Assembly.add(block)
    r.core.add(Assembly)
    return block


def getComponentDataFromBlock(component, block):
    density = 0.0
    for nuc in component.getNuclides():
        density += (
            component.getNumberDensity(nuc)
            * nucDir.getAtomicWeight(nuc)
            / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
        )
    volume = component.getVolume()
    mass = component.getMass()
    return component, density, volume, mass


class Block_TestCase(unittest.TestCase):
    def setUp(self):
        self.Block = loadTestBlock()
        self._hotBlock = loadTestBlock(cold=False)
        self.r = self.Block.r

    def test_getSmearDensity(self):
        cur = self.Block.getSmearDensity()
        ref = (
            self.Block.getDim(Flags.FUEL, "od") ** 2
            - self.Block.getDim(Flags.FUEL, "id") ** 2
        ) / self.Block.getDim(Flags.LINER, "id") ** 2
        places = 10
        self.assertAlmostEqual(cur, ref, places=places)

        # test with liner instead of clad
        ref = (
            self.Block.getDim(Flags.FUEL, "od") ** 2
            - self.Block.getDim(Flags.FUEL, "id") ** 2
        ) / self.Block.getDim(Flags.LINER, "id") ** 2
        cur = self.Block.getSmearDensity()
        self.assertAlmostEqual(
            cur,
            ref,
            places=places,
            msg="Incorrect getSmearDensity with liner. Got {0}. Should be {1}".format(
                cur, ref
            ),
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

        ref = (
            self.Block.getDim(Flags.FUEL, "od") ** 2
            - self.Block.getDim(Flags.FUEL, "id") ** 2
        ) / self.Block.getDim(Flags.LINER, "id") ** 2
        cur = self.Block.getSmearDensity()
        self.assertAlmostEqual(
            cur,
            ref,
            places=places,
            msg="Incorrect getSmearDensity with annular fuel. Got {0}. Should be {1}".format(
                cur, ref
            ),
        )

    def test_getSmearDensityMultipleLiner(self):
        numLiners = sum(
            1 for c in self.Block if "liner" in c.name and "gap" not in c.name
        )
        self.assertEqual(
            numLiners,
            2,
            "self.Block needs at least 2 liners for this test to be functional.",
        )
        cur = self.Block.getSmearDensity()
        ref = (
            self.Block.getDim(Flags.FUEL, "od") ** 2
            - self.Block.getDim(Flags.FUEL, "id") ** 2
        ) / self.Block.getDim(Flags.INNER | Flags.LINER, "id") ** 2
        self.assertAlmostEqual(cur, ref, places=10)

    def test_timeNodeParams(self):
        self.Block.p["avgFuelTemp", 3] = 2.0
        self.assertEqual(2.0, self.Block.p[("avgFuelTemp", 3)])

    def test_getType(self):
        ref = "plenum pin"
        self.Block.setType(ref)
        cur = self.Block.getType()
        self.assertEqual(cur, ref)
        self.assertTrue(self.Block.hasFlags(Flags.PLENUM))
        self.assertTrue(self.Block.hasFlags(Flags.PLENUM | Flags.PIN))
        self.assertTrue(self.Block.hasFlags(Flags.PLENUM | Flags.PIN, exact=True))
        self.assertFalse(self.Block.hasFlags(Flags.PLENUM, exact=True))

    def test_hasFlags(self):

        self.Block.setType("feed fuel")

        cur = self.Block.hasFlags(Flags.FEED | Flags.FUEL)
        self.assertTrue(cur)

        cur = self.Block.hasFlags(Flags.PLENUM)
        self.assertFalse(cur)

    def test_setType(self):

        self.Block.setType("igniter fuel")

        self.assertEqual("igniter fuel", self.Block.getType())
        self.assertTrue(self.Block.hasFlags(Flags.IGNITER | Flags.FUEL))

        self.Block.adjustUEnrich(0.0001)
        self.Block.setType("feed fuel")

        self.assertTrue(self.Block.hasFlags(Flags.FEED | Flags.FUEL))
        self.assertTrue(self.Block.hasFlags(Flags.FUEL))
        self.assertFalse(self.Block.hasFlags(Flags.IGNITER | Flags.FUEL))

    def test_duplicate(self):

        Block2 = copy.deepcopy(self.Block)
        originalComponents = self.Block.getComponents()
        newComponents = Block2.getComponents()
        for c1, c2 in zip(originalComponents, newComponents):
            self.assertEqual(c1.getName(), c2.getName())
            a1, a2 = c1.getArea(), c2.getArea()
            self.assertIsNot(c1, c2)
            self.assertAlmostEqual(
                a1,
                a2,
                msg="The area of {0}={1} but "
                "the area of {2} in the copy={3}".format(c1, a1, c2, a2),
            )
            for key in c2.DIMENSION_NAMES:
                dim = c2.p[key]
                if isinstance(dim, tuple):
                    self.assertNotIn(dim[0], originalComponents)
                    self.assertIn(dim[0], newComponents)

        ref = self.Block.getMass()
        cur = Block2.getMass()
        places = 6
        self.assertAlmostEqual(ref, cur, places=places)

        ref = self.Block.getArea()
        cur = Block2.getArea()
        places = 6
        self.assertAlmostEqual(ref, cur, places=places)

        ref = self.Block.getHeight()
        cur = Block2.getHeight()
        places = 6
        self.assertAlmostEqual(ref, cur, places=places)

    def test_getXsType(self):

        self.cs = settings.getMasterCs()
        self.cs["loadingFile"] = os.path.join(TEST_ROOT, "refSmallReactor.yaml")

        self.Block.p.xsType = "B"
        cur = self.Block.p.xsType
        ref = "B"
        self.assertEqual(cur, ref)

        oldBuGroups = self.cs["buGroups"]
        self.cs["buGroups"] = [100]
        self.Block.p.xsType = "BB"
        cur = self.Block.p.xsType
        ref = "BB"
        self.assertEqual(cur, ref)
        self.cs["buGroups"] = oldBuGroups

    def test27b_setBuGroup(self):
        type_ = "A"
        self.Block.p.buGroup = type_
        cur = self.Block.p.buGroupNum
        ref = ord(type_) - 65
        self.assertEqual(cur, ref)

        typeNumber = 25
        self.Block.p.buGroupNum = typeNumber
        cur = self.Block.p.buGroup
        ref = chr(typeNumber + 65)
        self.assertEqual(cur, ref)

    def test_clearDensity(self):
        self.Block.clearNumberDensities()

        for nuc in self.Block.getNuclides():
            cur = self.Block.getNumberDensity(nuc)
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

        self.Block.setNumberDensities(refDict)

        for nuc in refDict.keys():
            cur = self.Block.getNumberDensity(nuc)
            ref = refDict[nuc]
            places = 6
            self.assertAlmostEqual(ref, cur, places=places)

    def test_setNumberDensity(self):
        ref = 0.05
        self.Block.setNumberDensity("U235", ref)

        cur = self.Block.getNumberDensity("U235")
        places = 5
        self.assertAlmostEqual(cur, ref, places=places)

    def test_setNumberDensities(self):
        """Make sure we can set multiple number densities at once."""
        b = self.Block
        b.setNumberDensity("NA", 0.5)
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W": 1.09115150103e-05,
            "ZR": 0.00709003962772,
        }

        b.setNumberDensities(refDict)

        for nuc in refDict.keys():
            cur = self.Block.getNumberDensity(nuc)
            ref = refDict[nuc]
            places = 6
            self.assertAlmostEqual(cur, ref, places=places)
            nucBase = nuclideBases.byName[nuc]
            self.assertAlmostEqual(
                b.p[nucBase.getDatabaseName()], ref
            )  # required for DB viewing/loading

        # make sure U235 stayed fully contained in the fuel component
        fuelC = b.getComponent(Flags.FUEL)
        self.assertAlmostEqual(
            b.getNumberDensity("U235"),
            fuelC.getNumberDensity("U235") * fuelC.getVolumeFraction(),
        )

        # make sure other vals were zeroed out
        self.assertAlmostEqual(b.getNumberDensity("NA23"), 0.0)

    def test_getMass(self):
        self.Block.setHeight(100.0)

        nucName = "U235"
        d = self.Block.getNumberDensity(nucName)
        v = self.Block.getVolume()
        A = nucDir.getAtomicWeight(nucName)

        ref = d * v * A / MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
        cur = self.Block.getMass(nucName)

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_setMass(self):

        self.Block.setHeight(100.0)

        mass = 100.0
        nuc = "U238"
        self.Block.setMass(nuc, mass)

        cur = self.Block.getMass(nuc)
        ref = mass
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

        cur = self.Block.getNumberDensity(nuc)
        v = self.Block.getVolume()
        A = nucDir.getAtomicWeight(nuc)
        ref = MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * mass / (v * A)

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getTotalMass(self):

        self.Block.setHeight(100.0)

        self.Block.clearNumberDensities()
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "ZR": 0.00709003962772,
        }
        self.Block.setNumberDensities(refDict)

        cur = self.Block.getMass()

        tot = 0.0
        for nucName in refDict.keys():
            d = refDict[nucName]
            A = nucDir.getAtomicWeight(nucName)
            tot += d * A

        v = self.Block.getVolume()
        ref = tot * v / MOLES_PER_CC_TO_ATOMS_PER_BARN_CM

        places = 9
        self.assertAlmostEqual(cur, ref, places=places)

    def test_replaceBlockWithBlock(self):
        r"""
        Tests conservation of mass flag in replaceBlockWithBlock
        """
        block = self.Block
        ductBlock = block.__class__("duct")
        ductBlock.addComponent(block.getComponent(Flags.COOLANT, exact=True))
        ductBlock.addComponent(block.getComponent(Flags.DUCT, exact=True))
        ductBlock.addComponent(block.getComponent(Flags.INTERCOOLANT, exact=True))

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

    def test_getWettedPerimeter(self):
        cur = self.Block.getWettedPerimeter()
        ref = math.pi * (
            self.Block.getDim(Flags.CLAD, "od") + self.Block.getDim(Flags.WIRE, "od")
        ) + 6 * self.Block.getDim(Flags.DUCT, "ip") / math.sqrt(3) / self.Block.getDim(
            Flags.CLAD, "mult"
        )
        self.assertAlmostEqual(cur, ref)

    def test_getFlowAreaPerPin(self):
        area = self.Block.getComponent(Flags.COOLANT).getArea()
        nPins = self.Block.getNumPins()
        cur = self.Block.getFlowAreaPerPin()
        ref = area / nPins
        self.assertAlmostEqual(cur, ref)

    def test_getHydraulicDiameter(self):
        cur = self.Block.getHydraulicDiameter()
        ref = 4.0 * self.Block.getFlowAreaPerPin() / self.Block.getWettedPerimeter()
        self.assertAlmostEqual(cur, ref)

    def test_getCladdingOR(self):
        cur = self.Block.getCladdingOR()
        ref = self.Block.getDim(Flags.CLAD, "od") / 2.0
        self.assertAlmostEqual(cur, ref)

    def test_getCladdingIR(self):
        cur = self.Block.getCladdingIR()
        ref = self.Block.getDim(Flags.CLAD, "id") / 2.0
        self.assertAlmostEqual(cur, ref)

    def test_getFuelRadius(self):
        cur = self.Block.getFuelRadius()
        ref = self.Block.getDim(Flags.FUEL, "od") / 2.0
        self.assertAlmostEqual(cur, ref)

    def test_adjustCladThicknessByOD(self):
        thickness = 0.05
        clad = self.Block.getComponent(Flags.CLAD)
        ref = clad.getDimension("id", cold=True) + 2.0 * thickness
        self.Block.adjustCladThicknessByOD(thickness)
        cur = clad.getDimension("od", cold=True)
        curThickness = (
            clad.getDimension("od", cold=True) - clad.getDimension("id", cold=True)
        ) / 2.0
        self.assertAlmostEqual(cur, ref)
        self.assertAlmostEqual(curThickness, thickness)

    def test_adjustCladThicknessByID(self):
        thickness = 0.05
        clad = self.Block.getComponent(Flags.CLAD)
        ref = clad.getDimension("od", cold=True) - 2.0 * thickness
        self.Block.adjustCladThicknessByID(thickness)
        cur = clad.getDimension("id", cold=True)
        curThickness = (
            clad.getDimension("od", cold=True) - clad.getDimension("id", cold=True)
        ) / 2.0
        self.assertAlmostEqual(cur, ref)
        self.assertAlmostEqual(curThickness, thickness)

    def test_adjustUEnrich(self):
        self.Block.setHeight(100.0)

        ref = 0.25
        self.Block.adjustUEnrich(ref)

        cur = self.Block.getComponent(Flags.FUEL).getEnrichment()
        places = 5
        self.assertAlmostEqual(cur, ref, places=places)

    def test_setLocation(self):
        b = self.Block
        # a bit obvious, but location is a property now...
        i, j = grids.getIndicesFromRingAndPos(2, 3)
        b.spatialLocator = b.core.spatialGrid[i, j, 0]
        self.assertEqual(b.getLocation(), "A2003A")
        self.assertEqual(0, b.spatialLocator.k)
        self.assertEqual(b.getSymmetryFactor(), 1.0)

        # now if we don't specify axial, it will move to the new xy, location and have original z index
        i, j = grids.getIndicesFromRingAndPos(4, 4)
        b.spatialLocator = b.core.spatialGrid[i, j, 0]
        self.assertEqual(0, b.spatialLocator.k)
        self.assertEqual(b.getSymmetryFactor(), 1.0)

        # center blocks have a different symmetry factor for 1/3rd core
        for symmetry, powerMult in (
            (geometry.FULL_CORE, 1),
            (geometry.THIRD_CORE + geometry.PERIODIC, 3),
        ):
            self.r.core.symmetry = symmetry
            i, j = grids.getIndicesFromRingAndPos(1, 1)
            b.spatialLocator = b.core.spatialGrid[i, j, 0]
            self.assertEqual(0, b.spatialLocator.k)
            self.assertEqual(b.getSymmetryFactor(), powerMult)

    def test_setBuLimitInfo(self):
        cs = settings.getMasterCs()

        self.Block.adjustUEnrich(0.1)
        self.Block.setType("igniter fuel")

        self.Block.setBuLimitInfo(cs)

        cur = self.Block.p.buLimit
        ref = 0.0
        self.assertEqual(cur, ref)

    def test_getTotalNDens(self):

        self.Block.setType("fuel")

        self.Block.clearNumberDensities()
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "ZR": 0.00709003962772,
        }
        self.Block.setNumberDensities(refDict)

        cur = self.Block.getTotalNDens()

        tot = 0.0
        for nucName in refDict.keys():
            ndens = self.Block.getNumberDensity(nucName)
            tot += ndens

        ref = tot
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getHMDens(self):

        self.Block.setType("fuel")
        self.Block.clearNumberDensities()
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "ZR": 0.00709003962772,
        }
        self.Block.setNumberDensities(refDict)

        cur = self.Block.getHMDens()

        hmDens = 0.0
        for nuclide in refDict.keys():
            if nucDir.isHeavyMetal(nuclide):
                # then nuclide is a HM
                hmDens += self.Block.getNumberDensity(nuclide)

        ref = hmDens

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getFissileMassEnrich(self):
        fuelDims = {"Tinput": 273.0, "Thot": 273.0, "od": 0.76, "id": 0.0, "mult": 1.0}
        self.fuelComponent = components.Circle("fuel", "UZr", **fuelDims)
        self.Block.addComponent(self.fuelComponent)
        self.Block.setHeight(100.0)

        self.Block.clearNumberDensities()
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "ZR": 0.00709003962772,
        }
        self.Block.setNumberDensities(refDict)

        cur = self.Block.getFissileMassEnrich()

        ref = self.Block.getFissileMass() / self.Block.getHMMass()
        places = 4
        self.assertAlmostEqual(cur, ref, places=places)
        self.Block.removeComponent(self.fuelComponent)

    def test_getUraniumMassEnrich(self):

        self.Block.adjustUEnrich(0.25)

        ref = 0.25

        self.Block.adjustUEnrich(ref)
        cur = self.Block.getUraniumMassEnrich()

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getUraniumNumEnrich(self):

        self.Block.adjustUEnrich(0.25)

        cur = self.Block.getUraniumNumEnrich()

        u8 = self.Block.getNumberDensity("U238")
        u5 = self.Block.getNumberDensity("U235")
        ref = u5 / (u8 + u5)

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getNumberOfAtoms(self):

        self.Block.clearNumberDensities()
        refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "ZR": 0.00709003962772,
        }
        self.Block.setNumberDensities(refDict)

        nucName = "U238"
        moles = (
            self.Block.getNumberOfAtoms(nucName) / units.AVOGADROS_NUMBER
        )  # about 158 moles
        refMoles = (
            refDict["U238"]
            * self.Block.getVolume()
            / (units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM)
        )
        self.assertAlmostEqual(moles, refMoles)

    def test_getPuN(self):
        fuel = self.Block.getComponent(Flags.FUEL)
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

        cur = self.Block.getPuN()

        ndens = 0.0
        for nucName in refDict.keys():
            if nucName in ["PU238", "PU239", "PU240", "PU241", "PU242"]:
                ndens += self.Block.getNumberDensity(nucName)
        ref = ndens

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getPuMass(self):

        fuel = self.Block.getComponent(Flags.FUEL)
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
        fuel.setNumberDensities(refDict)
        cur = self.Block.getPuMass()
        pu = 0.0
        for nucName in refDict.keys():
            if nucName in ["PU238", "PU239", "PU240", "PU241", "PU242"]:
                pu += self.Block.getMass(nucName)
        self.assertAlmostEqual(cur, pu)

    def test_adjustDensity(self):

        u235Dens = 0.003
        u238Dens = 0.010
        self.Block.setNumberDensity("U235", u235Dens)
        self.Block.setNumberDensity("U238", u238Dens)
        mass1 = self.Block.getMass(["U235", "U238"])
        densAdj = 0.9
        nucList = ["U235", "U238"]
        massDiff = self.Block.adjustDensity(densAdj, nucList, returnMass=True)
        mass2 = self.Block.getMass(["U235", "U238"])

        cur = self.Block.getNumberDensity("U235")
        ref = densAdj * u235Dens
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

        cur = self.Block.getNumberDensity("U238")
        ref = densAdj * u238Dens
        self.assertAlmostEqual(cur, ref, places=places)

        self.assertAlmostEqual(mass2 - mass1, massDiff)

    def test_completeInitialLoading(self):

        area = self.Block.getArea()
        height = 2.0
        self.Block.setHeight(height)

        self.Block.clearNumberDensities()
        self.Block.setNumberDensities(
            {
                "U238": 0.018518936996911595,
                "ZR": 0.006040713762820692,
                "U235": 0.0023444806416701184,
                "NA23": 0.009810163826158255,
            }
        )

        self.Block.completeInitialLoading()

        cur = self.Block.p.molesHmBOL
        ref = self.Block.getHMDens() / MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * height * area
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_addComponent(self):

        numComps = len(self.Block.getComponents())

        fuelDims = {"Tinput": 25.0, "Thot": 600, "od": 0.76, "id": 0.00, "mult": 127.0}

        newComp = components.Circle("fuel", "UZr", **fuelDims)
        self.Block.addComponent(newComp)
        self.assertEqual(numComps + 1, len(self.Block.getComponents()))

        self.assertIn(newComp, self.Block.getComponents())
        self.Block.removeComponent(newComp)

    def test_hasComponents(self):
        self.assertTrue(self.Block.hasComponents([Flags.FUEL, Flags.CLAD]))
        self.assertTrue(self.Block.hasComponents(Flags.FUEL))
        self.assertFalse(
            self.Block.hasComponents([Flags.FUEL, Flags.CLAD, Flags.DUMMY])
        )

    def test_getComponentNames(self):

        cur = self.Block.getComponentNames()
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
        cur = self.Block.getComponents(Flags.FUEL)
        self.assertEqual(len(cur), 1)

        comps = self.Block.getComponents(Flags.FUEL) + self.Block.getComponents(
            Flags.CLAD
        )
        self.assertEqual(len(comps), 2)

        inter = self.Block.getComponents(Flags.INTERCOOLANT)
        self.assertEqual(len(inter), 1)

        inter = self.Block.getComponents(
            Flags.INTERCOOLANT, exact=True
        )  # case insensitive
        self.assertEqual(inter, [self.Block.getComponent(Flags.INTERCOOLANT)])

        cool = self.Block.getComponents(Flags.COOLANT, exact=True)
        self.assertEqual(len(cool), 1)

    def test_getComponent(self):
        cur = self.Block.getComponent(Flags.FUEL)
        self.assertIsInstance(cur, components.Component)

        inter = self.Block.getComponent(Flags.INTERCOOLANT)
        self.assertIsInstance(inter, components.Component)

        with self.assertRaises(KeyError):
            # this really isnt the responsibility of block, more of Flags, but until this refactor
            # is over...
            inter = self.Block.getComponent(
                Flags.fromString("intercoolantlala"), exact=True
            )

        cool = self.Block.getComponent(Flags.COOLANT, exact=True)
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
        cur = [c.name for c in self.Block.getComponentsOfShape(components.Circle)]
        self.assertEqual(sorted(ref), sorted(cur))

    def test_getComponentsOfMaterial(self):
        cur = self.Block.getComponentsOfMaterial(materials.UZr())
        ref = self.Block.getComponent(Flags.FUEL)
        self.assertEqual(cur[0], ref)

        self.assertEqual(
            self.Block.getComponentsOfMaterial(materials.HT9()),
            [
                self.Block.getComponent(Flags.OUTER | Flags.LINER),
                self.Block.getComponent(Flags.CLAD),
                self.Block.getComponent(Flags.WIRE),
                self.Block.getComponent(Flags.DUCT),
            ],
        )

    def test_getComponentByName(self):
        self.assertIsNone(
            self.Block.getComponentByName("not the droid youre looking for")
        )
        self.assertIsNotNone(self.Block.getComponentByName("annular void"))

    def test_getSortedComponentsInsideOfComponent(self):
        """Test that components can be sorted within a block and returned in the correct order."""
        expected = [
            self.Block.getComponentByName(c)
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
        clad = self.Block.getComponent(Flags.CLAD)
        actual = self.Block.getSortedComponentsInsideOfComponent(clad)
        self.assertListEqual(actual, expected)

    def test_getSortedComponentsInsideOfComponentSpecifiedTypes(self):
        expected = [
            self.Block.getComponentByName(c)
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
        clad = self.Block.getComponent(Flags.CLAD)
        actual = self.Block.getSortedComponentsInsideOfComponent(clad)
        self.assertListEqual(actual, expected)

    def test_getNumComponents(self):

        cur = self.Block.getNumComponents(Flags.FUEL)
        ref = self.Block.getDim(Flags.FUEL, "mult")
        self.assertEqual(cur, ref)

        self.assertEqual(ref, self.Block.getNumComponents(Flags.CLAD))

        self.assertEqual(1, self.Block.getNumComponents(Flags.DUCT))

    def test_getNumPins(self):

        cur = self.Block.getNumPins()
        ref = self.Block.getDim(Flags.FUEL, "mult")
        self.assertEqual(cur, ref)

        emptyBlock = blocks.HexBlock("empty")
        self.assertEqual(emptyBlock.getNumPins(), 0)

    def test_getComponentAreaFrac(self):
        def calcFracManually(names):
            tFrac = 0.0
            for n in names:
                for c, frac in fracs:
                    if c.getName() == n:
                        tFrac += frac
            return tFrac

        self.Block.setHeight(2.0)

        refList = [Flags.BOND, Flags.COOLANT]
        cur = self.Block.getComponentAreaFrac(refList)
        fracs = self.Block.getVolumeFractions()

        ref = calcFracManually(("bond", "coolant"))
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

        # allow inexact for things like fuel1, fuel2 or clad vs. cladding
        val = self.Block.getComponentAreaFrac(
            [Flags.COOLANT, Flags.INTERCOOLANT], exact=False
        )
        ref = calcFracManually(["coolant", "interCoolant"])
        refWrong = calcFracManually(
            ["coolant", "interCoolant", "clad"]
        )  # can't use 'clad' b/c ``calcFracManually`` is exact only
        self.assertAlmostEqual(ref, val)
        self.assertNotAlmostEqual(refWrong, val)

    def test100_getPinPitch(self):
        cur = self.Block.getPinPitch()
        ref = self.Block.getDim(Flags.CLAD, "od") + self.Block.getDim(Flags.WIRE, "od")
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test101_getPitch(self):
        cur = self.Block.getPitch(returnComp=True)
        ref = (
            self.Block.getDim(Flags.INTERCOOLANT, "op"),
            self.Block.getComponent(Flags.INTERCOOLANT),
        )
        self.assertEqual(cur, ref)

        newb = copy.deepcopy(self.Block)
        p1, c1 = self.Block.getPitch(returnComp=True)
        p2, c2 = newb.getPitch(returnComp=True)

        self.assertTrue(c1 is not c2)
        self.assertTrue(newb.getLargestComponent("op") is c2)
        self.assertTrue(p1 == p2)

    def test102_setPitch(self):
        pitch = 17.5
        self.Block.setPitch(pitch)
        cur = self.Block.getPitch()
        self.assertEqual(cur, pitch)
        self.assertEqual(
            self.Block.getComponent(Flags.INTERCOOLANT).getDimension("op"), pitch
        )

    def test_UnshapedGetPitch(self):
        """
        Test that a homogenous block can be created with a specific pitch.
        This functionality is necessary for making simple homogenous reactors.
        """
        block = blocks.HexBlock("TestHexBlock", location=None)
        outerPitch = 2.0
        block.addComponent(
            shapes.UnshapedComponent(
                "TestComponent", "Void", Tinput=25.0, Thot=25.0, op=outerPitch
            )
        )
        self.assertEqual(block.getPitch(), outerPitch)

    def test106_getAreaFractions(self):

        cur = self.Block.getVolumeFractions()
        tot = 0.0
        areas = []
        for c in self.Block.getComponents():
            a = c.getArea()
            tot += a
            areas.append((c, a))
        fracs = {}
        for c, a in areas:
            fracs[c.getName()] = a / tot

        places = 6
        for (c, a) in cur:
            self.assertAlmostEqual(a, fracs[c.getName()], places=places)

        self.assertAlmostEqual(sum(fracs.values()), sum([a for c, a in cur]))

    def test_rotatePins(self):
        b = self.Block
        b.setRotationNum(0)
        index = b.rotatePins(0, justCompute=True)
        self.assertEqual(b.getRotationNum(), 0)
        self.assertEqual(index[5], 5)
        self.assertEqual(index[2], 2)  # pin 1 is center and never rotates.

        index = b.rotatePins(1)
        self.assertEqual(b.getRotationNum(), 1)
        self.assertEqual(index[2], 3)

        index = b.rotatePins(1)
        self.assertEqual(b.getRotationNum(), 2)
        self.assertEqual(index[2], 4)

        index = b.rotatePins(4)  # back to 0
        self.assertEqual(b.getRotationNum(), 0)
        self.assertEqual(index[2], 2)

        self.assertRaises(ValueError, b.rotatePins, -1)
        self.assertRaises(ValueError, b.rotatePins, 10)
        self.assertRaises((ValueError, TypeError), b.rotatePins, None)
        self.assertRaises((ValueError, TypeError), b.rotatePins, "a")

    def test_expandElementalToIsotopics(self):
        r"""
        Tests the expand to elementals capability.
        """

        initialN = {}
        initialM = {}
        elementals = [nuclideBases.byName[nn] for nn in ["FE", "CR", "SI", "V", "MO"]]
        for elemental in elementals:
            initialN[elemental] = self.Block.getNumberDensity(
                elemental.name
            )  # homogenized
            initialM[elemental] = self.Block.getMass(elemental.name)

        for elemental in elementals:
            self.Block.expandElementalToIsotopics(elemental)
            newDens = 0.0
            newMass = 0.0
            for natNuc in elemental.getNaturalIsotopics():
                newDens += self.Block.getNumberDensity(natNuc.name)
                newMass += self.Block.getMass(natNuc.name)

            self.assertAlmostEqual(
                initialN[elemental],
                newDens,
                msg="Isotopic {2} ndens does not add up to {0}. It adds to {1}"
                "".format(initialN[elemental], newDens, elemental),
            )
            self.assertAlmostEqual(
                initialM[elemental],
                newMass,
                msg="Isotopic {2} mass does not add up to {0} g. "
                "It adds to {1}".format(initialM[elemental], newMass, elemental),
            )

    def test_setPitch(self):
        r"""
        Checks consistency after adjusting pitch

        Needed to verify fix to Issue #165.
        """
        b = self.Block
        moles1 = b.p.molesHmBOL
        b.setPitch(17.5)
        moles2 = b.p.molesHmBOL
        self.assertAlmostEqual(moles1, moles2)
        b.setPitch(20.0)
        moles3 = b.p.molesHmBOL
        self.assertAlmostEqual(moles2, moles3)

    def test_enforceBondRemovalFraction(self):
        b = self.Block
        bond = b.getComponent(Flags.BOND)
        bondRemovalFrac = 0.705
        ndensBefore = b.getNumberDensity("NA")
        bondNdensBefore = bond.getNumberDensity("NA")
        b.p.bondBOL = bondNdensBefore
        b.enforceBondRemovalFraction(bondRemovalFrac)
        bondNdensAfter = bond.getNumberDensity("NA")
        ndensAfter = b.getNumberDensity("NA")

        self.assertAlmostEqual(
            bondNdensAfter / bondNdensBefore, (1.0 - bondRemovalFrac)
        )
        self.assertAlmostEqual(ndensBefore, ndensAfter)

        # make sure it doesn't change if you run it twice
        b.enforceBondRemovalFraction(bondRemovalFrac)
        bondNdensAfter = bond.getNumberDensity("NA")
        ndensAfter = b.getNumberDensity("NA")
        self.assertAlmostEqual(
            bondNdensAfter / bondNdensBefore, (1.0 - bondRemovalFrac)
        )
        self.assertAlmostEqual(ndensBefore, ndensAfter)

    def test_getMfp(self):
        """Test mean free path."""
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
        # slight hack here because the test block was created
        # by hand rather than via blueprints and so elemental expansion
        # of isotopics did not occur. But, the ISOTXS library being used
        # did go through an isotopic expansion, so we map nuclides here.
        xslib._nuclides["NAAA"] = xslib._nuclides[
            "NA23AA"
        ]  # pylint: disable=protected-access
        xslib._nuclides["WAA"] = xslib._nuclides[
            "W184AA"
        ]  # pylint: disable=protected-access
        xslib._nuclides["MNAA"] = xslib._nuclides[
            "MN55AA"
        ]  # pylint: disable=protected-access
        # macroCreator = xsCollections.MacroscopicCrossSectionCreator()
        # macros = macroCreator.createMacrosFromMicros(xslib, self.Block)
        self.Block.p.mgFlux = flux
        self.Block.r.core.lib = xslib
        # These are unverified numbers, just the result of this calculation.
        mfp, mfpAbs, diffusionLength = self.Block.getMfp()
        # no point testing these number to high accuracy.
        assert_allclose(3.9, mfp, rtol=0.1)
        assert_allclose(235.0, mfpAbs, rtol=0.1)
        assert_allclose(17.0, diffusionLength, rtol=0.1)

    def test_consistentMassDensityVolumeBetweenColdBlockAndColdComponents(self):
        block = self.Block
        expectedData = []
        actualData = []
        for c in block:
            expectedData.append(getComponentDataFromBlock(c, block))
            actualData.append(
                (c, c.density(), c.getVolume(), c.density() * c.getVolume())
            )

        for expected, actual in zip(expectedData, actualData):
            msg = "Data (component, density, volume, mass) for component {} does not match. Expected: {}, Actual: {}".format(
                expected[0], expected, actual
            )
            for expectedVal, actualVal in zip(expected, actual):
                self.assertAlmostEqual(expectedVal, actualVal, msg=msg)

    def test_consistentMassDensityVolumeBetweenHotBlockAndHotComponents(self):
        block = self._hotBlock
        expectedData = []
        actualData = []
        for c in block:
            expectedData.append(getComponentDataFromBlock(c, block))
            actualData.append(
                (c, c.density(), c.getVolume(), c.density() * c.getVolume())
            )

        for expected, actual in zip(expectedData, actualData):
            msg = "Data (component, density, volume, mass) for component {} does not match. Expected: {}, Actual: {}".format(
                expected[0], expected, actual
            )
            for expectedVal, actualVal in zip(expected, actual):
                self.assertAlmostEqual(expectedVal, actualVal, msg=msg)

    def test_consistentAreaWithOverlappingComponents(self):
        """
        Test that negative gap areas correctly account for area overlapping upon thermal expansion.

        Notes
        -----
        This test calculates a reference coolant area by subtracting the areas of the intercoolant, duct, wire wrap,
        and pins from the total hex block area.
        The area of the pins is calculated using only the outer radius of the clad.
        This avoids the use of negative areas as implemented in Block.getVolumeFractions.
        Na-23 mass will not be conserved as when duct/clad expands sodium is evacuated

        See Also
        --------
        armi.reactor.blocks.Block.getVolumeFractions
        """
        numFE56 = self.Block.getNumberOfAtoms("FE56")
        numU235 = self.Block.getNumberOfAtoms("U235")
        for c in self.Block:
            c.setTemperature(800)
        hasNegativeArea = any(c.getArea() < 0 for c in self.Block)
        self.assertTrue(hasNegativeArea)
        self.Block.getVolumeFractions()  # sets coolant area
        self._testDimensionsAreLinked()  # linked dimensions are needed for this test to work

        blockPitch = self.Block.getPitch()
        self.assertAlmostEqual(
            blockPitch, self.Block.getComponent(Flags.INTERCOOLANT).getDimension("op")
        )
        totalHexArea = blockPitch ** 2 * math.sqrt(3) / 2.0

        clad = self.Block.getComponent(Flags.CLAD)
        pinArea = (
            math.pi / 4.0 * clad.getDimension("od") ** 2 * clad.getDimension("mult")
        )
        ref = (
            totalHexArea
            - self.Block.getComponent(Flags.INTERCOOLANT).getArea()
            - self.Block.getComponent(Flags.DUCT).getArea()
            - self.Block.getComponent(Flags.WIRE).getArea()
            - pinArea
        )

        self.assertAlmostEqual(totalHexArea, self.Block.getArea())
        self.assertAlmostEqual(ref, self.Block.getComponent(Flags.COOLANT).getArea())

        self.assertTrue(numpy.allclose(numFE56, self.Block.getNumberOfAtoms("FE56")))
        self.assertTrue(numpy.allclose(numU235, self.Block.getNumberOfAtoms("U235")))

    def _testDimensionsAreLinked(self):
        prevC = None
        for c in self.Block.getComponentsOfShape(components.Circle):
            if prevC:
                self.assertAlmostEqual(prevC.getDimension("od"), c.getDimension("id"))
            prevC = c
        self.assertAlmostEqual(
            self.Block.getComponent(Flags.DUCT).getDimension("op"),
            self.Block.getComponent(Flags.INTERCOOLANT).getDimension("ip"),
        )

    def test_breakFuelComponentsIntoIndividuals(self):
        fuel = self.Block.getComponent(Flags.FUEL)
        mult = fuel.getDimension("mult")
        self.assertGreater(mult, 1.0)
        self.Block.completeInitialLoading()
        self.Block.breakFuelComponentsIntoIndividuals()
        self.assertEqual(fuel.getDimension("mult"), 1.0)

    def test_plotFlux(self):
        try:
            xslib = isotxs.readBinary(ISOAA_PATH)
            self.Block.r.core.lib = xslib
            self.Block.p.mgFlux = range(33)
            self.Block.plotFlux(self.Block.r.core, fName="flux.png", bList=[self.Block])
            self.assertTrue(os.path.exists("flux.png"))
        finally:
            os.remove("flux.txt")  # secondarily created during the call.
            os.remove("flux.png")  # created during the call.


class HexBlock_TestCase(unittest.TestCase):
    def setUp(self):
        caseSetting = settings.Settings()
        self.HexBlock = blocks.HexBlock("TestHexBlock")
        hexDims = {"Tinput": 273.0, "Thot": 273.0, "op": 70.6, "ip": 70.0, "mult": 1.0}
        self.hexComponent = components.Hexagon("duct", "UZr", **hexDims)
        self.HexBlock.addComponent(self.hexComponent)
        self.HexBlock.addComponent(
            components.Circle(
                "clad", "HT9", Tinput=273.0, Thot=273.0, od=0.1, mult=169.0
            )
        )
        self.HexBlock.addComponent(
            components.Circle(
                "wire", "HT9", Tinput=273.0, Thot=273.0, od=0.01, mult=169.0
            )
        )
        self.HexBlock.addComponent(
            components.DerivedShape("coolant", "Sodium", Tinput=273.0, Thot=273.0)
        )
        r = tests.getEmptyHexReactor()
        a = makeTestAssembly(1, 1)
        a.add(self.HexBlock)
        loc1 = r.core.spatialGrid[0, 1, 0]
        r.core.add(a, loc1)

    def test_getArea(self):
        cur = self.HexBlock.getArea()
        ref = math.sqrt(3) / 2.0 * 70.6 ** 2
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_coords(self):
        r = self.HexBlock.r
        a = self.HexBlock.parent
        loc1 = r.core.spatialGrid[0, 1, 0]
        a.spatialLocator = loc1
        x0, y0 = self.HexBlock.coords()
        a.spatialLocator = r.core.spatialGrid[0, -1, 0]  # symmetric
        x2, y2 = self.HexBlock.coords()
        a.spatialLocator = loc1
        self.HexBlock.p.displacementX = 0.01
        self.HexBlock.p.displacementY = 0.02
        x1, y1 = self.HexBlock.coords()

        # make sure displacements are working
        self.assertAlmostEqual(x1 - x0, 1.0)
        self.assertAlmostEqual(y1 - y0, 2.0)

        # make sure location symmetry is working
        self.assertAlmostEqual(x0, -x2)
        self.assertAlmostEqual(y0, -y2)

    def test_getNumPins(self):
        self.assertEqual(self.HexBlock.getNumPins(), 169)

    def testSymmetryFactor(self):
        self.HexBlock.spatialLocator = self.HexBlock.r.core.spatialGrid[
            2, 0, 0
        ]  # full hex
        self.HexBlock.clearCache()
        self.assertEqual(1.0, self.HexBlock.getSymmetryFactor())
        a0 = self.HexBlock.getArea()
        v0 = self.HexBlock.getVolume()
        m0 = self.HexBlock.getMass()

        self.HexBlock.spatialLocator = self.HexBlock.r.core.spatialGrid[
            0, 0, 0
        ]  # 1/3 symmetric
        self.HexBlock.clearCache()
        self.assertEqual(3.0, self.HexBlock.getSymmetryFactor())
        self.assertEqual(a0 / 3.0, self.HexBlock.getArea())
        self.assertEqual(v0 / 3.0, self.HexBlock.getVolume())
        self.assertAlmostEqual(m0 / 3.0, self.HexBlock.getMass())

    def test_retainState(self):
        """Ensure retainState restores params and spatialGrids."""
        self.HexBlock.spatialGrid = grids.hexGridFromPitch(1.0)
        self.HexBlock.setType("intercoolant")
        with self.HexBlock.retainState():
            self.HexBlock.setType("fuel")
            self.HexBlock.spatialGrid.changePitch(2.0)
        self.assertEqual(self.HexBlock.spatialGrid.pitch, 1.0)
        self.assertTrue(self.HexBlock.hasFlags(Flags.INTERCOOLANT))

    def test_getPinCoords(self):
        xyz = self.HexBlock.getPinCoordinates()
        x, y, _z = zip(*xyz)
        self.assertAlmostEqual(
            y[1], y[2]
        )  # first two pins should be side by side on top.
        self.assertNotAlmostEqual(x[1], x[2])
        self.assertEqual(len(xyz), self.HexBlock.getNumPins())


class CartesianBlock_TestCase(unittest.TestCase):
    def setUp(self):
        caseSetting = settings.Settings()
        caseSetting["xw"] = 5.0
        caseSetting["yw"] = 3.0
        self.CartesianBlock = blocks.CartesianBlock("TestCartesianBlock", caseSetting)


class MassConservationTests(unittest.TestCase):
    r"""
    Tests designed to verify mass conservation during thermal expansion
    """

    def setUp(self):
        # build a block that has some basic components in it.
        cs = settings.Settings()
        self.b = blocks.HexBlock("fuel", height=10.0)

        fuelDims = {"Tinput": 25.0, "Thot": 600, "od": 0.76, "id": 0.00, "mult": 127.0}
        cladDims = {"Tinput": 25.0, "Thot": 450, "od": 0.80, "id": 0.77, "mult": 127.0}
        ductDims = {"Tinput": 25.0, "Thot": 400, "op": 16, "ip": 15.3, "mult": 1.0}
        coolDims = {"Tinput": 25.0, "Thot": 400}

        fuel = components.Circle("fuel", "UZr", **fuelDims)
        clad = components.Circle("clad", "HT9", **cladDims)
        duct = components.Hexagon("duct", "HT9", **ductDims)
        coolant = components.DerivedShape("coolant", "Sodium", **coolDims)

        self.b.addComponent(fuel)
        self.b.addComponent(clad)
        self.b.addComponent(duct)
        self.b.addComponent(coolant)

        self.b.getVolumeFractions()  # TODO: remove, should be no-op when removed self.cached

    def test_adjustSmearDensity(self):
        r"""
        Tests the getting, setting, and getting of smear density functions

        """
        bolBlock = copy.deepcopy(self.b)

        s = self.b.getSmearDensity(cold=False)

        fuel = self.b.getComponent(Flags.FUEL)
        clad = self.b.getComponent(Flags.CLAD)

        self.assertAlmostEqual(
            s, (fuel.getDimension("od") ** 2) / clad.getDimension("id") ** 2, 8
        )

        self.b.adjustSmearDensity(self.b.getSmearDensity(), bolBlock=bolBlock)

        s2 = self.b.getSmearDensity(cold=False)

        self.assertAlmostEqual(s, s2, 8)

        self.b.adjustSmearDensity(0.733, bolBlock=bolBlock)
        self.assertAlmostEqual(0.733, self.b.getSmearDensity(), 8)

        # try annular fuel
        clad = self.b.getComponent(Flags.CLAD)
        fuel = self.b.getComponent(Flags.FUEL)

        fuel.setDimension("od", clad.getDimension("id", cold=True))
        fuel.setDimension("id", 0.0001)

        self.b.adjustSmearDensity(0.733, bolBlock=bolBlock)
        self.assertAlmostEqual(0.733, self.b.getSmearDensity(), 8)

    def test_heightExpansionDifferences(self):
        r"""  The point of this test is to determine if the number densities stay the same
        with two different heights of the same block.  Since we want to expand a block
        from cold temperatures to hot using the fuel expansion coefficient (most important neutronicall),
        other components are not grown correctly.  This means that on the block level, axial expansion will
        NOT conserve mass of non-fuel components.  However, the excess mass is simply added to the top of
        the reactor in the plenum regions (or any non fueled region).
        """
        # assume the default block height is 'cold' height.  Now we must determine
        # what the hot height should be based on thermal expansion.  Change the height
        # of the block based on the different thermal expansions of the components then
        # see the effect on the number densities.

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
            "Number Density of fuel in one height ({0}) != number density of fuel at another height {1}. Number density conservation "
            "violated during thermal expansion".format(hotFuelU238, hotCladU238),
        )

        self.assertAlmostEqual(
            hotFuelIRON,
            hotCladIRON,
            10,
            "Number Density of clad in one height ({0}) != number density of clad at another height {1}. Number density conservation "
            "violated during thermal expansion".format(hotFuelIRON, hotCladIRON),
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
            "Cold mass of fuel ({0}) != hot mass {1}. Mass conservation "
            "violated during thermal expansion".format(massCold, massHot),
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
            "Cold mass of clad ({0}) != hot mass {1}. Mass conservation "
            "violated during thermal expansion".format(massCold, massHot),
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
            "Cold mass of duct ({0}) != hot mass {1}. Mass conservation "
            "violated during thermal expansion".format(massCold, massHot),
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
            "Cold mass of coolant ({0}) <= hot mass {1}. Mass conservation "
            "not violated during thermal expansion of coolant".format(
                massCold, massHot
            ),
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
            "Theoretical pitch of duct ({0}) != hot pitch {1}. Linear expansion "
            "violated during heatup. \nTc={tc} Tref={tref} dLL={dLL} cold={pcold}".format(
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

        At the cold temperature (but with hot height), the mass should be the same as at hot temperature
        and hot height.
        """
        fuel = self.b.getComponent(Flags.FUEL)
        # set ref (input/cold) temperature.
        Thot = fuel.temperatureInC
        Tcold = fuel.inputTemperatureInC
        fuel.setTemperature(Tcold)
        massCold = fuel.getMass()
        fuelArea = fuel.getArea()
        height = self.b.getHeight()  # hot height.
        rho = fuel.getProperties().density(Tc=Tcold)
        dllHot = fuel.getProperties().linearExpansionFactor(Tc=Thot, T0=Tcold)
        coldHeight = height / (1 + dllHot)
        theoreticalMass = fuelArea * coldHeight * rho

        self.assertAlmostEqual(
            massCold,
            theoreticalMass,
            7,
            "Cold mass of fuel ({0}) != theoretical mass {1}.  "
            "Check calculation of cold mass".format(massCold, theoreticalMass),
        )

    def test_massConsistency(self):
        r"""
        Verify that the sum of the component masses equals the total mass.
        """
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


if __name__ == "__main__":
    # import sys;sys.argv = ['', '-f']
    unittest.main()
