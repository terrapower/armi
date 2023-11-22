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

"""Tests for the composite pattern."""
from copy import deepcopy
import unittest

from armi import nuclearDataIO
from armi import runLog
from armi import settings
from armi import utils
from armi.nucDirectory import nucDir, nuclideBases
from armi.physics.neutronics.fissionProductModel.tests.test_lumpedFissionProduct import (
    getDummyLFPFile,
)
from armi.reactor import assemblies
from armi.reactor import components
from armi.reactor import composites
from armi.reactor import grids
from armi.reactor import parameters
from armi.reactor.blueprints import assemblyBlueprint
from armi.reactor.components import basicShapes
from armi.reactor.composites import getReactionRateDict
from armi.reactor.flags import Flags, TypeSpec
from armi.reactor.tests.test_blocks import loadTestBlock
from armi.tests import ISOAA_PATH


class MockBP:
    allNuclidesInProblem = set(nuclideBases.byName.keys())
    """:meta hide-value:"""
    activeNuclides = allNuclidesInProblem
    """:meta hide-value:"""
    inactiveNuclides = set()
    elementsToExpand = set()
    customIsotopics = {}


def getDummyParamDefs():
    dummyDefs = parameters.ParameterDefinitionCollection()
    with dummyDefs.createBuilder() as pb:
        pb.defParam("type", units=utils.units.UNITLESS, description="Fake type")
    return dummyDefs


_testGrid = grids.CartesianGrid.fromRectangle(0.01, 0.01)


class DummyComposite(composites.Composite):
    pDefs = getDummyParamDefs()

    def __init__(self, name, i=0):
        composites.Composite.__init__(self, name)
        self.p.type = name
        self.spatialLocator = grids.IndexLocation(i, i, i, _testGrid)


class DummyLeaf(composites.Composite):
    pDefs = getDummyParamDefs()

    def __init__(self, name, i=0):
        composites.Composite.__init__(self, name)
        self.p.type = name
        self.spatialLocator = grids.IndexLocation(i, i, i, _testGrid)

    def getChildren(
        self, deep=False, generationNum=1, includeMaterials=False, predicate=None
    ):
        """Return empty list, representing that this object has no children."""
        return []

    def getChildrenWithFlags(self, typeSpec: TypeSpec, exactMatch=True):
        """Return empty list, representing that this object has no children."""
        return []

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        return 1.0

    def iterComponents(self, typeSpec=None, exact=False):
        if self.hasFlags(typeSpec, exact):
            yield self


class TestCompositePattern(unittest.TestCase):
    def setUp(self):
        self.cs = settings.Settings()
        runLog.setVerbosity("error")
        container = DummyComposite("inner test fuel", 99)
        for i in range(5):
            leaf = DummyLeaf("duct {}".format(i), i + 100)
            leaf.setType("duct")
            container.add(leaf)
        nested = DummyComposite("clad", 98)
        nested.setType("clad")
        self.secondGen = DummyComposite("liner", 97)
        self.thirdGen = DummyLeaf("pin 77", 33)
        self.secondGen.add(self.thirdGen)
        nested.add(self.secondGen)
        container.add(nested)
        self.container = container

    def test_Composite(self):
        container = self.container

        children = container.getChildren()
        for child in children:
            self.assertEqual(child.parent, container)

        allChildren = container.getChildren(deep=True)
        self.assertEqual(len(allChildren), 8)

    def test_iterComponents(self):
        self.assertIn(self.thirdGen, list(self.container.iterComponents()))

    def test_getChildren(self):
        # There are 5 leaves and 1 composite in container. The composite has one leaf.
        firstGen = self.container.getChildren()
        self.assertEqual(len(firstGen), 6)
        secondGen = self.container.getChildren(generationNum=2)
        self.assertEqual(len(secondGen), 1)
        self.assertIs(secondGen[0], self.secondGen)
        third = self.container.getChildren(generationNum=3)
        self.assertEqual(len(third), 1)
        self.assertIs(third[0], self.thirdGen)
        allC = self.container.getChildren(deep=True)
        self.assertEqual(len(allC), 8)

        onlyLiner = self.container.getChildren(
            deep=True, predicate=lambda o: o.p.type == "liner"
        )
        self.assertEqual(len(onlyLiner), 1)

    def test_sort(self):
        # in this case, the children should start sorted
        c0 = [c.name for c in self.container.getChildren()]
        self.container.sort()
        c1 = [c.name for c in self.container.getChildren()]
        self.assertNotEqual(c0, c1)

        # verify repeated sortings behave
        for _ in range(3):
            self.container.sort()
            ci = [c.name for c in self.container.getChildren()]
            self.assertEqual(c1, ci)

        # break the order
        children = self.container.getChildren()
        self.container._children = children[2:] + children[:2]
        c2 = [c.name for c in self.container.getChildren()]
        self.assertNotEqual(c1, c2)

        # verify the sort order
        self.container.sort()
        c3 = [c.name for c in self.container.getChildren()]
        self.assertEqual(c1, c3)

    def test_areChildernOfType(self):
        expectedResults = [False, False, False, False, False, True]
        for i, b in enumerate(self.container.doChildrenHaveFlags(Flags.CLAD)):
            self.assertEqual(b, expectedResults[i])

    def test_containsAtLeastOneChildOfType(self):
        c = self.container
        self.assertTrue(c.containsAtLeastOneChildWithFlags(Flags.DUCT))
        self.assertTrue(c.containsAtLeastOneChildWithFlags(Flags.CLAD))

    def test_containsOnlyChildrenOfType(self):
        c = self.container
        for b in c:
            b.setType("bond")
        self.assertTrue(c.containsOnlyChildrenWithFlags(Flags.BOND))

    def test_nameContains(self):
        c = self.container
        c.setName("test one two three")
        self.assertTrue(c.nameContains("one"))
        self.assertTrue(c.nameContains("One"))
        self.assertTrue(c.nameContains("THREE"))
        self.assertFalse(c.nameContains("nope"))
        self.assertFalse(c.nameContains(["nope"]))
        self.assertTrue(c.nameContains(["one", "TWO", "three"]))
        self.assertTrue(c.nameContains(["nope", "dope", "three"]))

    def test_nucSpec(self):
        self.assertEqual(self.container._getNuclidesFromSpecifier("U235"), ["U235"])
        uNucs = self.container._getNuclidesFromSpecifier("U")
        self.assertIn("U235", uNucs)
        self.assertIn("U241", uNucs)
        self.assertIn("U227", uNucs)
        self.assertEqual(
            self.container._getNuclidesFromSpecifier(["U238", "U235"]), ["U235", "U238"]
        )

        uzr = self.container._getNuclidesFromSpecifier(["U238", "U235", "ZR"])
        self.assertIn("U235", uzr)
        self.assertIn("ZR92", uzr)
        self.assertNotIn("ZR", uzr)

        puIsos = self.container._getNuclidesFromSpecifier(
            ["PU"]
        )  # PU is special because it has no natural isotopics
        self.assertIn("PU239", puIsos)
        self.assertNotIn("PU", puIsos)

        self.assertEqual(
            self.container._getNuclidesFromSpecifier(["FE", "FE56"]).count("FE56"), 1
        )

    def test_hasFlags(self):
        """Ensure flags are queryable.

        .. test:: Flags can be queried.
            :id: T_ARMI_CMP_HAS_FLAGS
            :tests: R_ARMI_CMP_HAS_FLAGS
        """
        self.container.setType("fuel")
        self.assertFalse(self.container.hasFlags(Flags.SHIELD | Flags.FUEL, exact=True))
        self.assertTrue(self.container.hasFlags(Flags.FUEL))
        self.assertTrue(self.container.hasFlags(None))

    def test_hasFlagsSubstring(self):
        """Make sure typespecs with the same word in them no longer match."""
        self.container.setType("intercoolant")
        self.assertFalse(self.container.hasFlags(Flags.COOLANT))
        self.assertFalse(self.container.hasFlags(Flags.COOLANT, exact=True))
        self.assertTrue(self.container.hasFlags(Flags.INTERCOOLANT, exact=True))

        self.container.setType("innerduct")
        self.assertFalse(self.container.hasFlags(Flags.DUCT, exact=True))

    def test_hasFlagsNoTypeSpecified(self):
        self.container.setType("fuel")
        types = [None, [], [None]]
        for t in types:
            self.assertTrue(self.container.hasFlags(t))
            self.assertFalse(self.container.hasFlags(t, exact=True))

    def test_getBoundingCirlceOuterDiameter(self):
        od = self.container.getBoundingCircleOuterDiameter()
        self.assertAlmostEqual(od, len(list(self.container.iterComponents())))

    def test_getParamNames(self):
        params = self.container.getParamNames()
        self.assertEqual(len(params), 3)
        self.assertIn("flags", params)
        self.assertIn("serialNum", params)
        self.assertIn("type", params)

    def test_updateVolume(self):
        self.assertAlmostEqual(self.container.getVolume(), 0)
        self.container._updateVolume()
        self.assertAlmostEqual(self.container.getVolume(), 0)

    def test_expandLFPs(self):
        # simple test, with no lumped fission product mappings
        numDens = {"NA23": 1.0}
        numDens = self.container._expandLFPs(numDens)
        self.assertEqual(len(numDens), 1)

        # set the lumped fission product mapping
        fpd = getDummyLFPFile()
        lfps = fpd.createLFPsFromFile()
        self.container.setLumpedFissionProducts(lfps)

        # get back the lumped fission product mapping, just to check
        lfp = self.container.getLumpedFissionProductCollection()
        self.assertEqual(len(lfp), 3)
        self.assertIn("LFP35", lfp)
        self.assertIn("LFP38", lfp)
        self.assertIn("LFP39", lfp)

        # quick test WITH some lumped fission products in the mix
        numDens = {"NA23": 1.0, "LFP35": 2.0}
        numDens = self.container._expandLFPs(numDens)
        self.assertEqual(len(numDens), 9)
        self.assertEqual(numDens["MO99"], 0)

    def test_getIntegratedMgFlux(self):
        mgFlux = self.container.getIntegratedMgFlux()
        self.assertEqual(mgFlux, [0.0])

    def test_getReactionRates(self):
        rRates = self.container.getReactionRates("U235")
        self.assertEqual(len(rRates), 6)
        self.assertEqual(sum([r for r in rRates.values()]), 0)

    def test_syncParameters(self):
        data = [{"serialNum": 123}, {"flags": "FAKE"}]
        numSynced = self.container._syncParameters(data, {})
        self.assertEqual(numSynced, 2)


class TestCompositeTree(unittest.TestCase):

    blueprintYaml = """
    name: test assembly
    height: [1, 1]  # 2 blocks
    axial mesh points: [1, 1]
    xs types: [A, A]
    specifier: AA
    blocks:
    - &block_metal_fuel
        name: metal fuel
        fuel: &component_metal_fuel_fuel
            shape: Circle
            material: UZr
            Tinput: 500
            Thot: 500.0
            id: 0.0
            od: 1.0
            mult: 7
        clad: &component_metal_fuel_clad
            shape: Circle
            material: HT9
            Tinput: 450.0
            Thot: 450.0
            id: 1.09
            od: 1.1
            mult: 7
        bond: &component_metal_fuel_bond
            shape: Circle
            material: Sodium
            Tinput: 450.0
            Thot: 450.0
            id: fuel.od
            od: clad.id
            mult: 7
        coolant: &component_metal_fuel_coolant
            shape: DerivedShape
            material: Sodium
            Tinput: 450.0
            Thot: 450.0
        duct: &component_metal_fuel_duct
            shape: Hexagon
            material: HT9
            Tinput: 25.0
            Thot: 450.0
            ip: 16.0
            mult: 1.0
            op: 16.6
    - &block_oxide_fuel
        name: mox fuel
        fuel:
            <<: *component_metal_fuel_fuel
            material: MOX
        clad: *component_metal_fuel_clad
        bond: *component_metal_fuel_bond
        coolant: *component_metal_fuel_coolant
        duct: *component_metal_fuel_duct
        """

    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
        self.Block = None
        self.r = None

    def setUp(self):
        self.Block = loadTestBlock()
        self.r = self.Block.r
        self.Block.setHeight(100.0)
        self.refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "V": 2e-2,
            "NA23": 2e-2,
            "ZR": 0.00709003962772,
        }
        self.Block.setNumberDensities(self.refDict)

    def test_ordering(self):
        a = assemblies.Assembly("dummy")
        a.spatialGrid = grids.axialUnitGrid(2, armiObject=a)
        otherBlock = deepcopy(self.Block)
        a.add(self.Block)
        a.add(otherBlock)
        self.assertTrue(self.Block < otherBlock)
        locator = self.Block.spatialLocator
        self.Block.spatialLocator = otherBlock.spatialLocator
        otherBlock.spatialLocator = locator
        self.assertTrue(otherBlock < self.Block)

    def test_summing(self):
        a = assemblies.Assembly("dummy")
        a.spatialGrid = grids.axialUnitGrid(2, armiObject=a)
        otherBlock = deepcopy(self.Block)
        a.add(self.Block)
        a.add(otherBlock)

        b = self.Block + otherBlock
        self.assertEqual(len(b), 26)
        self.assertFalse(b[0].is3D)
        self.assertIn("Circle", str(b[0]))
        self.assertFalse(b[-1].is3D)
        self.assertIn("Hexagon", str(b[-1]))

    def test_constituentReport(self):
        runLog.info(self.r.core.constituentReport())
        runLog.info(self.r.core.getFirstAssembly().constituentReport())
        runLog.info(self.r.core.getFirstBlock().constituentReport())
        runLog.info(self.r.core.getFirstBlock().getComponents()[0].constituentReport())

    def test_getNuclides(self):
        """The getNuclides should return all keys that have ever been in this block, including values that are at trace."""
        cur = self.Block.getNuclides()
        ref = self.refDict.keys()
        for key in ref:
            self.assertIn(key, cur)
        self.assertIn("FE", cur)  # this is in at trace value.

    def test_getFuelMass(self):
        """
        This test creates a dummy assembly and ensures that the assembly, block, and fuel component masses are
        consistent.
        `getFuelMass` ensures that the fuel component is used to `getMass`.
        """
        cs = settings.Settings()
        assemDesign = assemblyBlueprint.AssemblyBlueprint.load(self.blueprintYaml)
        a = assemDesign.construct(cs, MockBP)

        fuelMass = 0.0
        for b in a:
            fuel = b.getComponent(Flags.FUEL)
            fuelMass += fuel.getMass()
            self.assertEqual(b.getFuelMass(), fuel.getMass())

        self.assertEqual(fuelMass, a.getFuelMass())

    def test_getNeutronEnergyDepositionConstants(self):
        """Until we improve test architecture, this test can not be more interesting."""
        with self.assertRaises(RuntimeError):
            # fails because this test reactor does not have a cross-section library
            _x = self.r.core.getNeutronEnergyDepositionConstants()

    def test_getGammaEnergyDepositionConstants(self):
        """Until we improve test architecture, this test can not be more interesting."""
        with self.assertRaises(RuntimeError):
            # fails because this test reactor does not have a cross-section library
            _x = self.r.core.getGammaEnergyDepositionConstants()

    def test_getChildrenIncludeMaterials(self):
        """Test that the ``StateRetainer`` retains material properties when they are modified."""
        cs = settings.Settings()
        assemDesign = assemblyBlueprint.AssemblyBlueprint.load(self.blueprintYaml)
        a = assemDesign.construct(cs, MockBP)
        component = a[0][0]
        referenceDensity = component.material.pseudoDensity(Tc=200)
        self.assertEqual(component.material.pseudoDensity(Tc=200), referenceDensity)

    def test_getHMMass(self):
        fuelDims = {"Tinput": 273.0, "Thot": 273.0, "od": 0.76, "id": 0.0, "mult": 1.0}
        self.fuelComponent = components.Circle("fuel", "UZr", **fuelDims)
        self.Block.add(self.fuelComponent)

        self.Block.clearNumberDensities()
        self.refDict = {
            "U235": 0.00275173784234,
            "U238": 0.0217358415457,
            "W182": 1.09115150103e-05,
            "W183": 5.89214392093e-06,
            "W184": 1.26159558164e-05,
            "W186": 1.17057432664e-05,
            "V": 3e-2,
            "NA23": 2e-2,
            "ZR": 0.00709003962772,
        }
        self.Block.setNumberDensities(self.refDict)

        cur = self.Block.getHMMass()

        mass = 0.0
        for nucName in self.refDict.keys():
            if nucDir.isHeavyMetal(nucName):
                mass += self.Block.getMass(nucName)

        places = 6
        self.assertAlmostEqual(cur, mass, places=places)

    def test_getFPMass(self):
        fuelDims = {"Tinput": 273.0, "Thot": 273.0, "od": 0.76, "id": 0.0, "mult": 1.0}
        self.fuelComponent = components.Circle("fuel", "UZr", **fuelDims)
        self.fuelComponent.material.setMassFrac("LFP38", 0.25)
        self.Block.add(self.fuelComponent)

        refDict = {"LFP35": 0.1, "LFP38": 0.05, "LFP39": 0.7}
        self.fuelComponent.setNumberDensities(refDict)

        cur = self.Block.getFPMass()

        mass = 0.0
        for nucName in refDict.keys():
            mass += self.Block.getMass(nucName)
        ref = mass

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getFissileMass(self):
        cur = self.Block.getFissileMass()

        mass = 0.0
        for nucName in self.refDict.keys():
            if nucName in nuclideBases.NuclideBase.fissile:
                mass += self.Block.getMass(nucName)
        ref = mass

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getMaxParam(self):
        for ci, c in enumerate(self.Block):
            if isinstance(c, basicShapes.Circle):
                c.p.id = ci
                lastSeen = c
                lastIndex = ci
        cMax, comp = self.Block.getMaxParam("id", returnObj=True)
        self.assertEqual(cMax, lastIndex)
        self.assertIs(comp, lastSeen)

    def test_getMinParam(self):
        for ci, c in reversed(list(enumerate(self.Block))):
            if isinstance(c, basicShapes.Circle):
                c.p.id = ci
                lastSeen = c
                lastIndex = ci
        cMax, comp = self.Block.getMinParam("id", returnObj=True)
        self.assertEqual(cMax, lastIndex)
        self.assertIs(comp, lastSeen)


class TestFlagSerializer(unittest.TestCase):
    class TestFlagsA(utils.Flag):
        A = utils.flags.auto()
        B = utils.flags.auto()
        C = utils.flags.auto()
        D = utils.flags.auto()

    class TestFlagsB(utils.Flag):
        A = utils.flags.auto()
        B = utils.flags.auto()
        BPRIME = utils.flags.auto()
        C = utils.flags.auto()
        D = utils.flags.auto()

    def test_flagSerialization(self):
        data = [
            Flags.FUEL,
            Flags.FUEL | Flags.INNER,
            Flags.A | Flags.B | Flags.CONTROL,
        ]

        flagsArray, attrs = composites.FlagSerializer.pack(data)

        data2 = composites.FlagSerializer.unpack(
            flagsArray, composites.FlagSerializer.version, attrs
        )
        self.assertEqual(data, data2)

        # discrepant versions
        with self.assertRaises(ValueError):
            data2 = composites.FlagSerializer.unpack(flagsArray, "0", attrs)

        # missing flags in current version Flags
        attrs["flag_order"].append("NONEXISTANTFLAG")
        with self.assertRaises(ValueError):
            data2 = composites.FlagSerializer.unpack(
                flagsArray, composites.FlagSerializer.version, attrs
            )

    def test_flagConversion(self):
        data = [
            self.TestFlagsA.A,
            self.TestFlagsA.A | self.TestFlagsA.C,
            self.TestFlagsA.A | self.TestFlagsA.C | self.TestFlagsA.D,
        ]

        serialized, attrs = composites.FlagSerializer._packImpl(data, self.TestFlagsA)

        data2 = composites.FlagSerializer._unpackImpl(
            serialized, composites.FlagSerializer.version, attrs, self.TestFlagsB
        )

        expected = [
            self.TestFlagsB.A,
            self.TestFlagsB.A | self.TestFlagsB.C,
            self.TestFlagsB.A | self.TestFlagsB.C | self.TestFlagsB.D,
        ]

        self.assertEqual(data2, expected)


class TestMiscMethods(unittest.TestCase):
    """
    Test a variety of methods on the composite.

    these may get moved to composted classes in the future.
    """

    def setUp(self):
        self.obj = loadTestBlock()

    def test_setMass(self):
        """Test setting and retrieving mass.

        .. test:: Mass of a composite is retrievable.
            :id: T_ARMI_CMP_GET_MASS
            :tests: R_ARMI_CMP_GET_MASS
        """
        masses = {"U235": 5.0, "U238": 3.0}
        self.obj.setMasses(masses)
        self.assertAlmostEqual(self.obj.getMass("U235"), 5.0)
        self.assertAlmostEqual(self.obj.getMass("U238"), 3.0)
        self.assertAlmostEqual(self.obj.getMass(), 8.0)

        self.obj.addMasses(masses)
        self.assertAlmostEqual(self.obj.getMass("U238"), 6.0)

        # make sure it works with groups of groups
        group = composites.Composite("group")
        group.add(self.obj)
        group.add(loadTestBlock())
        group.setMass("U235", 5)
        self.assertAlmostEqual(group.getMass("U235"), 5)

    def test_getNumberDensities(self):
        """Get number densities from composite.

        .. test:: Number density of composite is retrievable.
            :id: T_ARMI_CMP_GET_NDENS0
            :tests: R_ARMI_CMP_GET_NDENS
        """
        ndens = self.obj.getNumberDensities()
        self.assertAlmostEqual(0.0001096, ndens["SI"], 7)
        self.assertAlmostEqual(0.0000368, ndens["W"], 7)

    def test_dimensionReport(self):
        report = self.obj.setComponentDimensionsReport()
        self.assertEqual(len(report), len(self.obj))

    def test_printDensities(self):
        lines = self.obj.printDensities()
        self.assertEqual(len(lines), len(self.obj.getNuclides()))

    def test_getAtomicWeight(self):
        weight = self.obj.getAtomicWeight()
        self.assertTrue(50 < weight < 100)

    def test_containsHeavyMetal(self):
        self.assertTrue(self.obj.containsHeavyMetal())

    def test_copyParamsToChildren(self):
        self.obj.p.percentBu = 5
        self.obj.copyParamsToChildren(["percentBu"])
        for child in self.obj:
            self.assertEqual(child.p.percentBu, self.obj.p.percentBu)

    def test_copyParamsFrom(self):
        obj2 = loadTestBlock()
        obj2.p.percentBu = 15.2
        self.obj.copyParamsFrom(obj2)
        self.assertEqual(obj2.p.percentBu, self.obj.p.percentBu)


class TestGetReactionRateDict(unittest.TestCase):
    def test_getReactionRateDict(self):
        lib = nuclearDataIO.isotxs.readBinary(ISOAA_PATH)
        rxRatesDict = getReactionRateDict(
            nucName="PU239", lib=lib, xsSuffix="AA", mgFlux=1, nDens=1
        )
        self.assertEqual(rxRatesDict["nG"], sum(lib["PU39AA"].micros.nGamma))
