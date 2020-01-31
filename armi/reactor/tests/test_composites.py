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
import math

from armi import runLog
from armi import settings
from armi.nucDirectory import nucDir, nuclideBases
from armi.nuclearDataIO import isotxs

from armi.reactor import components
from armi.reactor import composites
from armi.reactor import batch
from armi.reactor import blocks
from armi.reactor import assemblies
from armi.reactor.components import shapes
from armi.reactor.components import basicShapes
from armi.reactor.components.shapes import UnshapedVolumetricComponent
from armi.materials import custom
from armi.reactor import locations
from armi.reactor import grids
from armi.reactor.blueprints import assemblyBlueprint
from armi.reactor import parameters
from armi.reactor.flags import Flags

from armi.physics.neutronics.fissionProductModel.tests import test_lumpedFissionProduct
from armi.tests import ISOAA_PATH
from armi.reactor.tests.test_blocks import loadTestBlock
from armi.tests import getEmptyHexReactor


class MockBP:
    allNuclidesInProblem = set(nuclideBases.byName.keys())
    activeNuclides = allNuclidesInProblem
    inactiveNuclides = set()
    elementsToExpand = set()
    customIsotopics = {}


def getDummyParamDefs():
    dummyDefs = parameters.ParameterDefinitionCollection()
    with dummyDefs.createBuilder() as pb:

        pb.defParam("type", units="none", description="Fake type")
    return dummyDefs


class DummyComposite(composites.Composite):
    pDefs = getDummyParamDefs()


class DummyLeaf(composites.Leaf):
    pDefs = getDummyParamDefs()


class TestCompositePattern(unittest.TestCase):
    def setUp(self):
        self.cs = settings.Settings()
        runLog.setVerbosity("error")
        container = DummyComposite("inner test fuel")
        for i in range(5):
            leaf = DummyLeaf("duct {}".format(i))
            leaf.setType("duct")
            container.add(leaf)
        nested = DummyComposite("clad")
        nested.setType("clad")
        self.secondGen = DummyComposite("liner")
        self.thirdGen = DummyLeaf("pin 77")
        self.secondGen.add(self.thirdGen)
        nested.add(self.secondGen)
        container.add(nested)
        self.container = container

    def testComposite(self):
        container = self.container

        children = container.getChildren()
        for child in children:
            self.assertEqual(child.parent, container)

        allChildren = container.getChildren(deep=True)
        self.assertEqual(len(allChildren), 8)

    def testGetChildren(self):
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

    def test_constituentReport(self):
        runLog.info(self.r.core.constituentReport())
        runLog.info(self.r.core.getFirstAssembly().constituentReport())
        runLog.info(self.r.core.getFirstBlock().constituentReport())
        runLog.info(self.r.core.getFirstBlock().getComponents()[0].constituentReport())

    def test_getNuclides(self):
        """getNuclides should return all keys that have ever been in this block, including values that are at trace."""
        cur = self.Block.getNuclides()
        ref = self.refDict.keys()
        for key in ref:
            self.assertIn(key, cur)
        self.assertIn("FE", cur)  # this is in at trace value.

    def test_getFuelMass(self):
        """
        This test creates a dummy assembly and ensures that the assembly, block, and fuel component masses are
        consistent.
        `getFuelMass` ensures that the fuel component is used to `getMass`
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

    def test_getChildrenIncludeMaterials(self):
        """Test that the ``StateRetainer`` retains material properties when they are modified."""
        cs = settings.Settings()
        assemDesign = assemblyBlueprint.AssemblyBlueprint.load(self.blueprintYaml)
        a = assemDesign.construct(cs, MockBP)
        component = a[0][0]
        referenceDensity = component.material.p.density
        self.assertEqual(component.material.p.density, referenceDensity)
        with a.retainState():
            component.material.p.density = 5.0
        self.assertEqual(component.material.p.density, referenceDensity)

    def test_getHMMass(self):
        fuelDims = {"Tinput": 273.0, "Thot": 273.0, "od": 0.76, "id": 0.0, "mult": 1.0}
        self.fuelComponent = components.Circle("fuel", "UZr", **fuelDims)
        self.Block.addComponent(self.fuelComponent)

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
        self.Block.addComponent(self.fuelComponent)

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


class TestBatchMethodsOnArmiObjectAndCompositeObject(unittest.TestCase):
    """
    a developer extended armi objects and armi composites to work with batches this series of tests ensures new
    methods work as intended

    new methods on armiObject:
        getMasses
        getMgFlux
        removeMass
        addMass - not implemented at armiObject level
        addMasses
        setMass - not implemented at armiObject level
        setMasses

    new methods on armi composite
        getLumpedFissionProductsIfNecessary
        getLumpedFissionProducts
        getIntegratedMgFlux
    """

    def test_addMass(self):
        """
        test:
            addMasses
            addMass
            removeMass
            getMasses

        right now it doesn't make sense to add mass to anything other than a
        component, some one else can implement addMass and update this test
        on block, assembly and reactor.
        """

        loc = locations.Location(i1=1, i2=1, axial=1)
        mass = 1.0

        aB = batch.Batch("testBatch")
        c = shapes.UnshapedVolumetricComponent(
            "batchMassAdditionComponent", custom.Custom(), 0.0, 0.0, volume=1
        )
        b = blocks.Block("testBlock", location=loc)
        b.add(c)
        a = assemblies.Assembly("testAssembly")
        a.spatialGrid = grids.axialUnitGrid(1)
        a.add(b)

        r = getEmptyHexReactor()
        a.spatialLocator = r.core.spatialGrid[0, 0, 0]
        r.core.add(a)

        # these armi objects have addMass implemented
        for armiObj in [aB, c]:
            for nucName in ["U235"]:
                masses = {nucName: mass}
                armiObj.addMasses(masses)
                self.assertAlmostEqual(armiObj.getMass(nucName), mass, 6)

                armiObj.removeMass(nucName, mass)
                self.assertAlmostEqual(armiObj.getMass(nucName), 0, 6)

        # create a global lumped fission product collection with a single lfp
        Fpdf = test_lumpedFissionProduct.getDummyLFPFile()
        cLfps = Fpdf.createSingleLFPCollectionFromFile("LFP35")
        self.assertAlmostEqual(aB.getMass(), 0, 6)
        aB.addMass("LFP35", mass, lumpedFissionProducts=cLfps)
        self.assertAlmostEqual(aB.getMass(), mass, 6)

        self.assertAlmostEqual(c.getMass(), 0, 6)
        c.addMass("LFP35", mass, lumpedFissionProducts=cLfps)
        self.assertAlmostEqual(c.getMass(), mass, 6)

    def test_setMass(self):
        """
        test:
            setMass
            setMasses
        """
        loc = locations.Location(i1=1, i2=1, axial=1)
        mass = 1.0

        aB = batch.Batch("testBatch")
        c = shapes.UnshapedVolumetricComponent(
            "batchMassAdditionComponent", custom.Custom(), 0.0, 0.0, volume=1
        )
        b = blocks.Block("testBlock", location=loc)
        b.add(c)
        a = assemblies.Assembly("testAssembly")
        a.spatialGrid = grids.axialUnitGrid(1, a)
        a.add(b)

        r = getEmptyHexReactor()
        a.spatialLocator = r.core.spatialGrid[0, 0, 0]
        r.core.add(a)

        # these armi objects have setMass implemented
        for armiObj in [aB, c, b]:
            for nucName in ["U235"]:
                masses = {nucName: mass}
                armiObj.setMasses(masses)
                self.assertAlmostEqual(armiObj.getMass(nucName), mass, 6)

    def test_getReactionRates(self):

        """
        test:
            getReactionRates
            getReactionRates
        """

        mgFlux1 = [
            0.0860473241399844,
            0.104859413902775,
            0.958730499751868,
            0.0608613995961131,
            0.286847241591555,
            0.255889308191141,
            0.0116901206385536,
            0.713409716738126,
            0.430296361167501,
            0.807797711781478,
            0.0337645123548413,
            0.486499349955704,
            0.734614285636136,
            0.74230952191973,
            0.262181249681019,
            0.499163237742064,
            0.522320530090222,
            0.269684933319214,
            0.286697941919085,
            0.173049285638012,
            0.881264543688633,
            0.99461769495224,
            0.267737005223648,
            0.957400117341211,
            0.767927939604005,
            0.149702253058259,
            0.332924880721111,
            0.611969570430789,
            0.227989279697323,
            0.411852641375799,
            0.500275641106796,
            0.654655431372318,
            0.223981131922656,
        ]

        lib = isotxs.readBinary(ISOAA_PATH)

        loc = locations.Location(i1=1, i2=1, axial=1)

        nDens = 0.02  # arbitrary number density for U235

        c = UnshapedVolumetricComponent("testComponent", "Custom", 0.0, 0.0, volume=1)
        c.setNumberDensity("U235", nDens)
        b = blocks.Block("testBlock", location=loc)
        b.add(c)
        b.p.mgFlux = mgFlux1[:33]
        b.p.xsType = "A"
        a = assemblies.Assembly("testAssembly")
        a.spatialGrid = grids.axialUnitGrid(1, a)
        a.add(b)

        r = getEmptyHexReactor()
        a.spatialLocator = r.core.spatialGrid[0, 0, 0]
        r.core.add(a)
        r.core.lib = lib

        aB = batch.Batch("testBatch")
        aB.add(b)

        # reference data made with this ISOTXS and this MG flux spectrum
        referenceRxRateData = {
            "nG": 2.10693674,
            "nF": 6.500339249,
            "n2n": 0.001446367,
            "nA": 0,
            "nP": 0,
            "n3n": 0,
        }
        referenceXsData = {
            "nG": 7.162060679,
            "nF": 22.09645085,
            "n2n": 0.004916601,
            "nA": 0,
            "nP": 0,
            "n3n": 0,
        }

        u235 = lib["U235AA"]
        assert not hasattr(u235.micros, "n3n")

        for armiObject in [c, b, a, r, aB]:
            rxnRates = armiObject.getReactionRates("U235")
            for rxName, rxRate in rxnRates.items():
                self.assertAlmostEqual(rxRate, referenceRxRateData[rxName], 6)
            xsTable = armiObject.getCrossSectionTable(nuclides=["U235"])
            u235Zaid = 92235
            for rxName, rxRate in xsTable[u235Zaid].items():
                self.assertAlmostEqual(rxRate, referenceXsData[rxName], 6)

    def test_getMgFluxes(self):
        """
        test:
            getMgFlux
            getIntegratedMgFlux
        """

        mgFlux1 = [
            0.0860473241399844,
            0.104859413902775,
            0.958730499751868,
            0.0608613995961131,
            0.286847241591555,
            0.255889308191141,
            0.0116901206385536,
            0.713409716738126,
            0.430296361167501,
            0.807797711781478,
            0.0337645123548413,
            0.486499349955704,
            0.734614285636136,
            0.74230952191973,
            0.262181249681019,
            0.499163237742064,
            0.522320530090222,
            0.269684933319214,
            0.286697941919085,
            0.173049285638012,
            0.881264543688633,
            0.99461769495224,
            0.267737005223648,
            0.957400117341211,
            0.767927939604005,
            0.149702253058259,
            0.332924880721111,
            0.611969570430789,
            0.227989279697323,
            0.411852641375799,
            0.500275641106796,
            0.654655431372318,
            0.223981131922656,
        ]

        loc = locations.Location(i1=1, i2=1, axial=1)

        c = UnshapedVolumetricComponent("testComponent", "Custom", 0.0, 0.0, volume=1)
        b = blocks.Block("testBlock", location=loc)
        b.add(c)
        b.p.mgFlux = mgFlux1
        a = assemblies.Assembly("testAssembly")
        a.spatialGrid = grids.axialUnitGrid(1, a)
        a.add(b)

        r = getEmptyHexReactor()
        a.spatialLocator = r.core.spatialGrid[0, 0, 0]
        r.core.add(a)

        aB = batch.Batch("testBatch")
        aB.add(b)

        for armiObject in [c, b, a, r, aB]:
            for refFlux, testFlux in zip(mgFlux1, armiObject.getIntegratedMgFlux()):
                err = math.fabs((testFlux - refFlux) / refFlux)
                try:
                    assert err < 1e-6
                except AssertionError:
                    raise AssertionError(
                        "Integrated MgFlux test is failing for {}".format(
                            type(armiObject)
                        )
                    )

            for refFlux, testFlux in zip(mgFlux1, armiObject.getMgFlux()):
                err = math.fabs((testFlux - refFlux) / refFlux)
                try:
                    assert err < 1e-6
                except AssertionError:
                    raise AssertionError(
                        "Integrated MgFlux test is failing for {}".format(
                            type(armiObject)
                        )
                    )


class TestFlagSerializer(unittest.TestCase):
    def test_flagSerialization(self):
        data = [
            Flags.FUEL,
            Flags.FUEL | Flags.DEPLETABLE,
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

        # wrong number of Flags
        removedFlag = attrs["flag_order"].pop()
        with self.assertRaises(ValueError):
            data2 = composites.FlagSerializer.unpack(
                flagsArray, composites.FlagSerializer.version, attrs
            )

        # Flags order doesn't match anymore
        attrs["flag_order"].insert(0, removedFlag)
        with self.assertRaises(ValueError):
            data2 = composites.FlagSerializer.unpack(
                flagsArray, composites.FlagSerializer.version, attrs
            )


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'TestCompositeTree.test_ordering']
    unittest.main()
