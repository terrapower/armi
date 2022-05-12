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
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access,no-member,invalid-name,consider-using-f-string
import copy
import math
import os
import unittest
import numpy
from numpy.testing import assert_allclose

from armi.reactor import blocks
from armi.reactor import components
from armi import runLog
from armi import settings
from armi import materials
from armi.nucDirectory import nucDir, nuclideBases
from armi.utils.units import MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
from armi.tests import TEST_ROOT
from armi.utils import units
from armi.utils import hexagon
from armi.reactor.flags import Flags
from armi import tests
from armi.reactor import grids
from armi.reactor.tests.test_assemblies import makeTestAssembly
from armi.tests import ISOAA_PATH
from armi.nuclearDataIO.cccc import isotxs
from armi.reactor import geometry
from armi.physics.neutronics import NEUTRON
from armi.physics.neutronics import GAMMA


def buildSimpleFuelBlock():
    """Return a simple block containing fuel, clad, duct, and coolant."""
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

    b.getVolumeFractions()  # TODO: remove, should be no-op when removed self.cached

    return b


def loadTestBlock(cold=True):
    """Build an annular test block for evaluating unit tests."""
    caseSetting = settings.Settings()
    settings.setMasterCs(caseSetting)
    caseSetting["xsKernel"] = "MC2v2"
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

    block.getVolumeFractions()  # TODO: remove, should be no-op when removed self.cached

    block.setHeight(16.0)

    Assembly.add(block)
    r.core.add(Assembly)
    return block


# pylint: disable=protected-access
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
    # slight hack here because the test block was created
    # by hand rather than via blueprints and so elemental expansion
    # of isotopics did not occur. But, the ISOTXS library being used
    # did go through an isotopic expansion, so we map nuclides here.
    xslib._nuclides["NAAA"] = xslib._nuclides["NA23AA"]
    xslib._nuclides["WAA"] = xslib._nuclides["W184AA"]
    xslib._nuclides["MNAA"] = xslib._nuclides["MN55AA"]
    block.p.mgFlux = flux
    block.r.core.lib = xslib


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
        self.block = loadTestBlock()
        self._hotBlock = loadTestBlock(cold=False)
        self.r = self.block.r

    def test_getSmearDensity(self):
        cur = self.block.getSmearDensity()
        ref = (
            self.block.getDim(Flags.FUEL, "od") ** 2
            - self.block.getDim(Flags.FUEL, "id") ** 2
        ) / self.block.getDim(Flags.LINER, "id") ** 2
        places = 10
        self.assertAlmostEqual(cur, ref, places=places)

        # test with liner instead of clad
        ref = (
            self.block.getDim(Flags.FUEL, "od") ** 2
            - self.block.getDim(Flags.FUEL, "id") ** 2
        ) / self.block.getDim(Flags.LINER, "id") ** 2
        cur = self.block.getSmearDensity()
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
            self.block.getDim(Flags.FUEL, "od") ** 2
            - self.block.getDim(Flags.FUEL, "id") ** 2
        ) / self.block.getDim(Flags.LINER, "id") ** 2
        cur = self.block.getSmearDensity()
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
            1 for c in self.block if "liner" in c.name and "gap" not in c.name
        )
        self.assertEqual(
            numLiners,
            2,
            "self.block needs at least 2 liners for this test to be functional.",
        )
        cur = self.block.getSmearDensity()
        ref = (
            self.block.getDim(Flags.FUEL, "od") ** 2
            - self.block.getDim(Flags.FUEL, "id") ** 2
        ) / self.block.getDim(Flags.INNER | Flags.LINER, "id") ** 2
        self.assertAlmostEqual(cur, ref, places=10)

    def test_timeNodeParams(self):
        self.block.p["avgFuelTemp", 3] = 2.0
        self.assertEqual(2.0, self.block.p[("avgFuelTemp", 3)])

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
        Block2 = copy.deepcopy(self.block)
        originalComponents = self.block.getComponents()
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

    def test_getXsType(self):
        self.cs = settings.getMasterCs()
        newSettings = {"loadingFile": os.path.join(TEST_ROOT, "refSmallReactor.yaml")}
        self.cs = self.cs.modified(newSettings=newSettings)

        self.block.p.xsType = "B"
        cur = self.block.p.xsType
        ref = "B"
        self.assertEqual(cur, ref)

        oldBuGroups = self.cs["buGroups"]
        newSettings = {"buGroups": [100]}
        self.cs = self.cs.modified(newSettings=newSettings)

        self.block.p.xsType = "BB"
        cur = self.block.p.xsType
        ref = "BB"
        self.assertEqual(cur, ref)

    def test_27b_setBuGroup(self):
        type_ = "A"
        self.block.p.buGroup = type_
        cur = self.block.p.buGroupNum
        ref = ord(type_) - 65
        self.assertEqual(cur, ref)

        typeNumber = 25
        self.block.p.buGroupNum = typeNumber
        cur = self.block.p.buGroup
        ref = chr(typeNumber + 65)
        self.assertEqual(cur, ref)

    def test_setZeroHeight(self):
        """Test that demonstrates that a block's height can be set to zero."""
        b = buildSimpleFuelBlock()

        # Check for a DerivedShape component
        self.assertEqual(
            len([c for c in b if c.__class__ is components.DerivedShape]), 1
        )
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
            self.assertEqual(
                ndens, 0.0, msg=(f"Number density of {nuc} is " "expected to be zero.")
            )

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
        r"""Tests conservation of mass flag in replaceBlockWithBlock"""
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

    def test_getWettedPerimeter(self):
        cur = self.block.getWettedPerimeter()
        ref = math.pi * (
            self.block.getDim(Flags.CLAD, "od") + self.block.getDim(Flags.WIRE, "od")
        ) + 6 * self.block.getDim(Flags.DUCT, "ip") / math.sqrt(3) / self.block.getDim(
            Flags.CLAD, "mult"
        )
        self.assertAlmostEqual(cur, ref)

    def test_getFlowAreaPerPin(self):
        area = self.block.getComponent(Flags.COOLANT).getArea()
        nPins = self.block.getNumPins()
        cur = self.block.getFlowAreaPerPin()
        ref = area / nPins
        self.assertAlmostEqual(cur, ref)

    def test_getHydraulicDiameter(self):
        cur = self.block.getHydraulicDiameter()
        ref = 4.0 * self.block.getFlowAreaPerPin() / self.block.getWettedPerimeter()
        self.assertAlmostEqual(cur, ref)

    def test_adjustUEnrich(self):
        self.block.setHeight(100.0)

        ref = 0.25
        self.block.adjustUEnrich(ref)

        cur = self.block.getComponent(Flags.FUEL).getEnrichment()
        places = 5
        self.assertAlmostEqual(cur, ref, places=places)

    def test_setLocation(self):
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
                geometry.SymmetryType(
                    geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC
                ),
                3,
            ),
        ):
            self.r.core.symmetry = geometry.SymmetryType.fromAny(symmetry)
            i, j = grids.HexGrid.getIndicesFromRingAndPos(1, 1)
            b.spatialLocator = b.core.spatialGrid[i, j, 0]
            self.assertEqual(0, b.spatialLocator.k)
            self.assertEqual(b.getSymmetryFactor(), powerMult)

    def test_setBuLimitInfo(self):
        cs = settings.getMasterCs()

        self.block.adjustUEnrich(0.1)
        self.block.setType("igniter fuel")

        self.block.setBuLimitInfo(cs)

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

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

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
        moles = (
            self.block.getNumberOfAtoms(nucName) / units.AVOGADROS_NUMBER
        )  # about 158 moles
        refMoles = (
            refDict["U238"]
            * self.block.getVolume()
            / (units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM)
        )
        self.assertAlmostEqual(moles, refMoles)

    def test_getPuN(self):
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

        cur = self.block.getPuN()

        ndens = 0.0
        for nucName in refDict.keys():
            if nucName in ["PU238", "PU239", "PU240", "PU241", "PU242"]:
                ndens += self.block.getNumberDensity(nucName)
        ref = ndens

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getPuMass(self):

        fuel = self.block.getComponent(Flags.FUEL)
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
        cur = self.block.getPuMass()
        pu = 0.0
        for nucName in refDict.keys():
            if nucName in ["PU238", "PU239", "PU240", "PU241", "PU242"]:
                pu += self.block.getMass(nucName)
        self.assertAlmostEqual(cur, pu)

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
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

        cur = self.block.getNumberDensity("U238")
        ref = densAdj * u238Dens
        self.assertAlmostEqual(cur, ref, places=places)

        self.assertAlmostEqual(mass2 - mass1, massDiff)

    def test_completeInitialLoading(self):

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

        cur = self.block.p.molesHmBOL
        ref = self.block.getHMDens() / MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * height * area
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

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
        self.assertFalse(
            self.block.hasComponents([Flags.FUEL, Flags.CLAD, Flags.DUMMY])
        )

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

        comps = self.block.getComponents(Flags.FUEL) + self.block.getComponents(
            Flags.CLAD
        )
        self.assertEqual(len(comps), 2)

        inter = self.block.getComponents(Flags.INTERCOOLANT)
        self.assertEqual(len(inter), 1)

        inter = self.block.getComponents(
            Flags.INTERCOOLANT, exact=True
        )  # case insensitive
        self.assertEqual(inter, [self.block.getComponent(Flags.INTERCOOLANT)])

        cool = self.block.getComponents(Flags.COOLANT, exact=True)
        self.assertEqual(len(cool), 1)

    def test_getComponent(self):
        cur = self.block.getComponent(Flags.FUEL)
        self.assertIsInstance(cur, components.Component)

        inter = self.block.getComponent(Flags.INTERCOOLANT)
        self.assertIsInstance(inter, components.Component)

        with self.assertRaises(KeyError):
            # this really isnt the responsibility of block, more of Flags, but until this refactor
            # is over...
            inter = self.block.getComponent(
                Flags.fromString("intercoolantlala"), exact=True
            )

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

    def test_getComponentByName(self):
        self.assertIsNone(
            self.block.getComponentByName("not the droid youre looking for")
        )
        self.assertIsNotNone(self.block.getComponentByName("annular void"))

    def test_getSortedComponentsInsideOfComponent(self):
        """Test that components can be sorted within a block and returned in the correct order."""
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

    def test_getSortedComponentsInsideOfComponentSpecifiedTypes(self):
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

    def test_getNumComponents(self):
        cur = self.block.getNumComponents(Flags.FUEL)
        ref = self.block.getDim(Flags.FUEL, "mult")
        self.assertEqual(cur, ref)

        self.assertEqual(ref, self.block.getNumComponents(Flags.CLAD))

        self.assertEqual(1, self.block.getNumComponents(Flags.DUCT))

    def test_getNumPins(self):
        cur = self.block.getNumPins()
        ref = self.block.getDim(Flags.FUEL, "mult")
        self.assertEqual(cur, ref)

        emptyBlock = blocks.HexBlock("empty")
        self.assertEqual(emptyBlock.getNumPins(), 0)

    def test_setPinPowers(self):
        numPins = self.block.getNumPins()
        neutronPower = [10.0 * i for i in range(numPins)]
        gammaPower = [1.0 * i for i in range(numPins)]
        totalPower = [x + y for x, y in zip(neutronPower, gammaPower)]
        imax = 9  # hexagonal rings of pins
        jmax = [max(1, 6 * i) for i in range(imax)]  # pins in each hexagonal ring
        self.block.setPinPowers(
            neutronPower,
            numPins,
            imax,
            jmax,
            gamma=False,
            removeSixCornerPins=False,
            powerKeySuffix=NEUTRON,
        )
        self.block.setPinPowers(
            gammaPower,
            numPins,
            imax,
            jmax,
            gamma=True,
            removeSixCornerPins=False,
            powerKeySuffix=GAMMA,
        )
        assert_allclose(self.block.p.pinPowersNeutron, numpy.array(neutronPower))
        assert_allclose(self.block.p.pinPowersGamma, numpy.array(gammaPower))
        assert_allclose(self.block.p.pinPowers, numpy.array(totalPower))

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
        val = self.block.getComponentAreaFrac(
            [Flags.COOLANT, Flags.INTERCOOLANT], exact=False
        )
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

        self.assertTrue(c1 is not c2)
        self.assertTrue(newb.getLargestComponent("op") is c2)
        self.assertTrue(p1 == p2)

    def test_102_setPitch(self):
        pitch = 17.5
        self.block.setPitch(pitch)
        cur = self.block.getPitch()
        self.assertEqual(cur, pitch)
        self.assertEqual(
            self.block.getComponent(Flags.INTERCOOLANT).getDimension("op"), pitch
        )

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
        for (c, a) in cur:
            self.assertAlmostEqual(a, fracs[c.getName()], places=places)

        self.assertAlmostEqual(sum(fracs.values()), sum([a for c, a in cur]))

    def test_rotatePins(self):
        b = self.block
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

        index = b.rotatePins(2)
        index = b.rotatePins(4)  # over-rotate to check modulus
        self.assertEqual(b.getRotationNum(), 2)
        self.assertEqual(index[2], 4)
        self.assertEqual(index[6], 2)

        self.assertRaises(ValueError, b.rotatePins, -1)
        self.assertRaises(ValueError, b.rotatePins, 10)
        self.assertRaises((ValueError, TypeError), b.rotatePins, None)
        self.assertRaises((ValueError, TypeError), b.rotatePins, "a")

    def test_expandElementalToIsotopics(self):
        r"""Tests the expand to elementals capability."""
        initialN = {}
        initialM = {}
        elementals = [nuclideBases.byName[nn] for nn in ["FE", "CR", "SI", "V", "MO"]]
        for elemental in elementals:
            initialN[elemental] = self.block.getNumberDensity(
                elemental.name
            )  # homogenized
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
                msg="Isotopic {2} ndens does not add up to {0}. It adds to {1}"
                "".format(initialN[elemental], newDens, elemental),
            )
            self.assertAlmostEqual(
                initialM[elemental],
                newMass,
                msg="Isotopic {2} mass does not add up to {0} g. "
                "It adds to {1}".format(initialM[elemental], newMass, elemental),
            )

    def test_expandAllElementalsToIsotopics(self):
        r"""Tests the expand all elementals simlutaneously capability."""
        initialN = {}
        initialM = {}
        elementals = [nuclideBases.byName[nn] for nn in ["FE", "CR", "SI", "V", "MO"]]
        for elemental in elementals:
            initialN[elemental] = self.block.getNumberDensity(
                elemental.name
            )  # homogenized
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
        b = self.block
        moles1 = b.p.molesHmBOL
        b.setPitch(17.5)
        moles2 = b.p.molesHmBOL
        self.assertAlmostEqual(moles1, moles2)
        b.setPitch(20.0)
        moles3 = b.p.molesHmBOL
        self.assertAlmostEqual(moles2, moles3)

    def test_getMfp(self):
        """Test mean free path."""
        applyDummyData(self.block)
        # These are unverified numbers, just the result of this calculation.
        mfp, mfpAbs, diffusionLength = self.block.getMfp()
        # no point testing these number to high accuracy.
        assert_allclose(3.9, mfp, rtol=0.1)
        assert_allclose(235.0, mfpAbs, rtol=0.1)
        assert_allclose(17.0, diffusionLength, rtol=0.1)

    def test_consistentMassDensityVolumeBetweenColdBlockAndColdComponents(self):
        block = self.block
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
        numFE56 = self.block.getNumberOfAtoms("FE56")
        numU235 = self.block.getNumberOfAtoms("U235")
        for c in self.block:
            c.setTemperature(800)
        hasNegativeArea = any(c.getArea() < 0 for c in self.block)
        self.assertTrue(hasNegativeArea)
        self.block.getVolumeFractions()  # sets coolant area
        self._testDimensionsAreLinked()  # linked dimensions are needed for this test to work

        blockPitch = self.block.getPitch()
        self.assertAlmostEqual(
            blockPitch, self.block.getComponent(Flags.INTERCOOLANT).getDimension("op")
        )
        totalHexArea = blockPitch ** 2 * math.sqrt(3) / 2.0

        clad = self.block.getComponent(Flags.CLAD)
        pinArea = (
            math.pi / 4.0 * clad.getDimension("od") ** 2 * clad.getDimension("mult")
        )
        ref = (
            totalHexArea
            - self.block.getComponent(Flags.INTERCOOLANT).getArea()
            - self.block.getComponent(Flags.DUCT).getArea()
            - self.block.getComponent(Flags.WIRE).getArea()
            - pinArea
        )

        self.assertAlmostEqual(totalHexArea, self.block.getArea())
        self.assertAlmostEqual(ref, self.block.getComponent(Flags.COOLANT).getArea())

        self.assertTrue(numpy.allclose(numFE56, self.block.getNumberOfAtoms("FE56")))
        self.assertTrue(numpy.allclose(numU235, self.block.getNumberOfAtoms("U235")))

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

    def test_breakFuelComponentsIntoIndividuals(self):
        fuel = self.block.getComponent(Flags.FUEL)
        mult = fuel.getDimension("mult")
        self.assertGreater(mult, 1.0)
        self.block.completeInitialLoading()
        self.block.breakFuelComponentsIntoIndividuals()
        self.assertEqual(fuel.getDimension("mult"), 1.0)

    def test_pinMgFluxes(self):
        """
        Test setting/getting of pin-wise fluxes.

        .. warning:: This will likely be pushed to the component level.
        """
        fluxes = numpy.ones((33, 10))
        self.block.setPinMgFluxes(fluxes, 10)
        self.block.setPinMgFluxes(fluxes * 2, 10, adjoint=True)
        self.block.setPinMgFluxes(fluxes * 3, 10, gamma=True)
        self.assertEqual(self.block.p.pinMgFluxes[0][2], 1.0)
        self.assertEqual(self.block.p.pinMgFluxesAdj[0][2], 2.0)
        self.assertEqual(self.block.p.pinMgFluxesGamma[0][2], 3.0)

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


class Test_NegativeVolume(unittest.TestCase):
    def test_negativeVolume(self):
        """Build a block with WAY too many fuel pins and show that the derived volume is negative"""
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
        _ = settings.Settings()
        self.HexBlock = blocks.HexBlock("TestHexBlock")
        hexDims = {"Tinput": 273.0, "Thot": 273.0, "op": 70.6, "ip": 70.0, "mult": 1.0}
        self.hexComponent = components.Hexagon("duct", "UZr", **hexDims)
        self.HexBlock.add(self.hexComponent)
        self.HexBlock.add(
            components.Circle(
                "clad", "HT9", Tinput=273.0, Thot=273.0, od=0.1, mult=169.0
            )
        )
        self.HexBlock.add(
            components.Circle(
                "wire", "HT9", Tinput=273.0, Thot=273.0, od=0.01, mult=169.0
            )
        )
        self.HexBlock.add(
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

    def test_symmetryFactor(self):
        # full hex
        self.HexBlock.spatialLocator = self.HexBlock.r.core.spatialGrid[2, 0, 0]
        self.HexBlock.clearCache()
        self.assertEqual(1.0, self.HexBlock.getSymmetryFactor())
        a0 = self.HexBlock.getArea()
        v0 = self.HexBlock.getVolume()
        m0 = self.HexBlock.getMass()

        # 1/3 symmetric
        self.HexBlock.spatialLocator = self.HexBlock.r.core.spatialGrid[0, 0, 0]
        self.HexBlock.clearCache()
        self.assertEqual(3.0, self.HexBlock.getSymmetryFactor())
        self.assertEqual(a0 / 3.0, self.HexBlock.getArea())
        self.assertEqual(v0 / 3.0, self.HexBlock.getVolume())
        self.assertAlmostEqual(m0 / 3.0, self.HexBlock.getMass())

        symmetryLine = self.HexBlock.isOnWhichSymmetryLine()
        self.assertEqual(grids.BOUNDARY_CENTER, symmetryLine)

    def test_retainState(self):
        """Ensure retainState restores params and spatialGrids."""
        self.HexBlock.spatialGrid = grids.HexGrid.fromPitch(1.0)
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

    def test_getPitchHomogenousBlock(self):
        """
        Demonstrate how to communicate pitch on a hex block with unshaped components.

        Notes
        -----
        This assumes there are 3 materials in the homogeneous block, one with half
        the area fraction, and 2 with 1/4 each.
        """
        desiredPitch = 14.0
        hexTotalArea = hexagon.area(desiredPitch)

        compArgs = {"Tinput": 273.0, "Thot": 273.0}
        areaFractions = [0.5, 0.25, 0.25]
        materials = ["HT9", "UZr", "Sodium"]

        # There are 2 ways to do this, the first is to pick a component to be the pitch
        # defining component, and given it the shape of a hexagon to define the pitch
        # The hexagon outer pitch (op) is defined by the pitch of the block/assembly.
        # the ip is defined by whatever thickness is necessary to have the desired area
        # fraction. The second way is shown in the second half of this test.
        hexBlock = blocks.HexBlock("TestHexBlock")

        hexComponentArea = areaFractions[0] * hexTotalArea

        # Picking 1st material to use for the hex component here, but really the choice
        # is arbitrary.
        # area grows quadratically with op
        ipNeededForCorrectArea = desiredPitch * areaFractions[0] ** 0.5
        self.assertEqual(
            hexComponentArea, hexTotalArea - hexagon.area(ipNeededForCorrectArea)
        )

        hexArgs = {"op": desiredPitch, "ip": ipNeededForCorrectArea, "mult": 1.0}
        hexArgs.update(compArgs)
        pitchDefiningComponent = components.Hexagon(
            "pitchComp", materials[0], **hexArgs
        )
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

        # For this second way, we will simply define the 3 components as unshaped, with
        # the desired area fractions, and make a 4th component that is an infinitely
        # thin hexagon with the the desired pitch. The downside of this method is that
        # now the block has a fourth component with no volume.
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
        ductIP = self.HexBlock.getDuctIP()
        self.assertAlmostEqual(70.0, ductIP)
        ductOP = self.HexBlock.getDuctOP()
        self.assertAlmostEqual(70.6, ductOP)

    def test_getPinCenterFlatToFlat(self):
        nRings = hexagon.numRingsToHoldNumCells(self.HexBlock.getNumPins())
        pinPitch = self.HexBlock.getPinPitch()
        pinCenterCornerToCorner = 2 * (nRings - 1) * pinPitch
        pinCenterFlatToFlat = math.sqrt(3.0) / 2.0 * pinCenterCornerToCorner
        f2f = self.HexBlock.getPinCenterFlatToFlat()
        self.assertAlmostEqual(pinCenterFlatToFlat, f2f)

    def test_gridCreation(self):
        b = self.HexBlock
        # The block should have a spatial grid at construction,
        # since it has mults = 1 or 169 from setup
        b.autoCreateSpatialGrids()
        self.assertTrue(b.spatialGrid is not None)
        for c in b:
            if c.getDimension("mult", cold=True) == 169:
                # Then it's spatialLocator must be of size 169
                locations = c.spatialLocator
                self.assertEqual(type(locations), grids.MultiIndexLocation)
                mult = 0
                for _ in locations:
                    mult = mult + 1
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
            b.autoCreateSpatialGrids()
        self.assertTrue(b.spatialGrid is None)

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
        self.HexBlock.add(wire)
        with self.assertRaises(ValueError):
            self.HexBlock.autoCreateSpatialGrids()

        self.assertTrue(self.HexBlock.spatialGrid is None)


class ThRZBlock_TestCase(unittest.TestCase):
    def setUp(self):
        _ = settings.Settings()
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
        This function is currently null. It consists of a single line that
        returns nothing. This test covers that line. If the function is ever
        implemented, it can be tested here.
        """
        self.ThRZBlock.verifyBlockDims()

    def test_getThetaRZGrid(self):
        """Since not applicable to ThetaRZ Grids"""
        b = self.ThRZBlock
        with self.assertRaises(NotImplementedError):
            b.autoCreateSpatialGrids()

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
        self.cartesianBlock.add(
            components.Circle(
                "clad", "HT9", Tinput=273.0, Thot=273.0, od=68.0, mult=169.0
            )
        )

    def test_getPitchSquare(self):
        self.assertEqual(self.cartesianBlock.getPitch(), (self.PITCH, self.PITCH))

    def test_getPitchHomogenousBlock(self):
        """
        Demonstrate how to communicate pitch on a hex block with unshaped components.

        Notes
        -----
        This assumes there are 3 materials in the homogeneous block, one with half
        the area fraction, and 2 with 1/4 each.
        """
        desiredPitch = (10.0, 12.0)
        rectTotalArea = desiredPitch[0] * desiredPitch[1]

        compArgs = {"Tinput": 273.0, "Thot": 273.0}
        areaFractions = [0.5, 0.25, 0.25]
        materials = ["HT9", "UZr", "Sodium"]

        # There are 2 ways to do this, the first is to pick a component to be the pitch
        # defining component, and given it the shape of a rectangle to define the pitch
        # The rectangle outer dimensions is defined by the pitch of the block/assembly.
        # the inner dimensions is defined by whatever thickness is necessary to have
        # the desired area fraction.
        # The second way is to define all physical material components as unshaped, and
        # add an additional infinitely thin Void component (no area) that defines pitch.
        # See second part of HexBlock_TestCase.test_getPitchHomogenousBlock for
        # demonstration.
        cartBlock = blocks.CartesianBlock("TestCartBlock")

        hexComponentArea = areaFractions[0] * rectTotalArea

        # Picking 1st material to use for the hex component here, but really the choice
        # is arbitrary.
        # area grows quadratically with outer dimensions.
        # Note there are infinitely many inner dims that would preserve area,
        # this is just one of them.
        innerDims = [dim * areaFractions[0] ** 0.5 for dim in desiredPitch]
        self.assertAlmostEqual(
            hexComponentArea, rectTotalArea - innerDims[0] * innerDims[1]
        )

        rectArgs = {
            "lengthOuter": desiredPitch[0],
            "lengthInner": innerDims[0],
            "widthOuter": desiredPitch[1],
            "widthInner": innerDims[1],
            "mult": 1.0,
        }
        rectArgs.update(compArgs)
        pitchDefiningComponent = components.Rectangle(
            "pitchComp", materials[0], **rectArgs
        )
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
        """Since not applicable to Cartesian Grids"""
        b = self.cartesianBlock
        with self.assertRaises(NotImplementedError):
            b.autoCreateSpatialGrids()

    def test_getWettedPerimeter(self):
        with self.assertRaises(NotImplementedError):
            _ = self.cartesianBlock.getWettedPerimeter()

    def test_getHydraulicDiameter(self):
        with self.assertRaises(NotImplementedError):
            _ = self.cartesianBlock.getHydraulicDiameter()


class PointTests(unittest.TestCase):
    def setUp(self):
        self.point = blocks.Point()

    def test_getters(self):
        self.assertEqual(1.0, self.point.getVolume())
        self.assertEqual(1.0, self.point.getBurnupPeakingFactor())

    def test_getWettedPerimeter(self):
        self.assertEqual(0.0, self.point.getWettedPerimeter())

    def test_getHydraulicDiameter(self):
        self.assertEqual(0.0, self.point.getHydraulicDiameter())


class MassConservationTests(unittest.TestCase):
    r"""
    Tests designed to verify mass conservation during thermal expansion
    """

    def setUp(self):
        self.b = buildSimpleFuelBlock()

    def test_heightExpansionDifferences(self):
        r"""The point of this test is to determine if the number densities stay the same
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
        r"""Verify that the sum of the component masses equals the total mass."""
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
    unittest.main()
