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

import itertools
import logging
import unittest
from copy import deepcopy

from armi import nuclearDataIO, runLog, settings, utils
from armi.nucDirectory import nucDir, nuclideBases
from armi.physics.neutronics.fissionProductModel.tests.test_lumpedFissionProduct import (
    getDummyLFPFile,
)
from armi.reactor import assemblies, components, composites, grids, parameters
from armi.reactor.blueprints import assemblyBlueprint
from armi.reactor.components import basicShapes
from armi.reactor.composites import getReactionRateDict
from armi.reactor.flags import Flags, TypeSpec
from armi.reactor.tests.test_blocks import loadTestBlock
from armi.testing import loadTestReactor
from armi.tests import ISOAA_PATH, mockRunLogs


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
        # Some special material attribute for testing getChildren(includeMaterials=True)
        self.material = ("hello", "world")

    def getChildren(self, deep=False, generationNum=1, includeMaterials=False, predicate=None):
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
            leaf = DummyLeaf(f"duct {i}", i + 100)
            leaf.setType("duct")
            container.add(leaf)
        nested = DummyComposite("clad", 98)
        nested.setType("clad")
        self.cladChild = nested
        self.secondGen = DummyComposite("liner", 97)
        self.thirdGen = DummyLeaf("pin 77", 33)
        self.secondGen.add(self.thirdGen)
        nested.add(self.secondGen)
        container.add(nested)
        self.container = container
        # Composite tree structure in list of lists for testing
        # tree[i] contains the children at "generation" or "depth" i
        self.tree: list[list[composites.Composite]] = [
            [self.container],
            list(self.container),
            [self.secondGen],
            [self.thirdGen],
        ]

    def test_composite(self):
        """Test basic Composite things.

        .. test:: Composites are part of a hierarchical model.
            :id: T_ARMI_CMP0
            :tests: R_ARMI_CMP
        """
        container = self.container

        children = container.getChildren()
        for child in children:
            self.assertEqual(child.parent, container)

        allChildren = container.getChildren(deep=True)
        self.assertEqual(len(allChildren), 8)

    def test_iterComponents(self):
        self.assertIn(self.thirdGen, list(self.container.iterComponents()))

    def test_getChildren(self):
        """Test the get children method.

        .. test:: Composites are part of a hierarchical model.
            :id: T_ARMI_CMP1
            :tests: R_ARMI_CMP
        """
        firstGen = self.container.getChildren()
        self.assertEqual(firstGen, self.tree[1])

        secondGen = self.container.getChildren(generationNum=2)
        self.assertEqual(secondGen, self.tree[2])

        self.assertIs(secondGen[0], self.secondGen)
        third = self.container.getChildren(generationNum=3)
        self.assertEqual(third, self.tree[3])
        self.assertIs(third[0], self.thirdGen)

        allC = self.container.getChildren(deep=True)
        expected = self.tree[1] + self.tree[2] + self.tree[3]
        self.assertTrue(
            all(a is e for a, e in itertools.zip_longest(allC, expected)),
            msg=f"Deep traversal differs: {allC=} != {expected=}",
        )

        onlyLiner = self.container.getChildren(deep=True, predicate=lambda o: o.p.type == "liner")
        self.assertEqual(len(onlyLiner), 1)
        self.assertIs(onlyLiner[0], self.secondGen)

    def test_getChildrenWithMaterials(self):
        """Test the ability for getChildren to place the material after the object."""
        withMaterials = self.container.getChildren(deep=True, includeMaterials=True)
        # Grab the iterable so we can control the progression
        items = iter(withMaterials)
        for item in items:
            expectedMat = getattr(item, "material", None)
            if expectedMat is None:
                continue
            # Material should be the next item in the list
            actualMat = next(items)
            self.assertIs(actualMat, expectedMat)
            break
        else:
            raise RuntimeError("No materials found with includeMaterials=True")

    def test_iterChildren(self):
        """Detailed testing on Composite.iterChildren."""

        def compareIterables(actual, expected: list[composites.Composite]):
            for e in expected:
                a = next(actual)
                self.assertIs(a, e)
            # Ensure we've consumed the actual iterator and there's nothing left
            with self.assertRaises(StopIteration):
                next(actual)

        compareIterables(self.container.iterChildren(), self.tree[1])
        compareIterables(self.container.iterChildren(generationNum=2), self.tree[2])
        compareIterables(self.container.iterChildren(generationNum=3), self.tree[3])
        compareIterables(
            self.container.iterChildren(deep=True),
            self.tree[1] + self.tree[2] + self.tree[3],
        )

    def test_iterAndGetChildren(self):
        """Compare that iter children and get children are consistent."""
        self._compareIterGetChildren()
        self._compareIterGetChildren(deep=True)
        self._compareIterGetChildren(generationNum=2)
        # Some wacky predicate just to check we can use that too
        self._compareIterGetChildren(deep=True, predicate=lambda c: len(c.name) % 3)

    def _compareIterGetChildren(self, **kwargs):
        fromIter = self.container.iterChildren(**kwargs)
        fromGetter = self.container.getChildren(**kwargs)
        msg = repr(kwargs)
        # Use zip longest just in case one iterator comes up short
        for count, (it, gt) in enumerate(itertools.zip_longest(fromIter, fromGetter)):
            self.assertIs(it, gt, msg=f"{count=} :: {msg}")

    def test_simpleIterChildren(self):
        """Test that C.iterChildren() is identical to iter(C)."""
        for count, (fromNative, fromIterChildren) in enumerate(
            itertools.zip_longest(self.container, self.container.iterChildren())
        ):
            self.assertIs(fromIterChildren, fromNative, msg=count)

    def test_iterChildrenWithMaterials(self):
        """Test that C.iterChildrenWithMaterials gets materials following their parent component."""
        items = iter(self.container.iterChildrenWithMaterials(deep=True))
        for item in items:
            if isinstance(item, components.Component):
                mat = next(items)
                self.assertIs(mat, item.material)

    def test_getName(self):
        """Test the getName method."""
        self.assertEqual(self.secondGen.getName(), "liner")
        self.assertEqual(self.thirdGen.getName(), "pin 77")
        self.assertEqual(self.secondGen.getName(), "liner")
        self.assertEqual(self.container.getName(), "inner test fuel")

    def test_sort(self):
        # in this case, the children should start sorted
        c0 = [c.name for c in self.container]
        self.container.sort()
        c1 = [c.name for c in self.container]
        self.assertNotEqual(c0, c1)

        # verify repeated sorting behave
        for _ in range(3):
            self.container.sort()
            ci = [c.name for c in self.container]
            self.assertEqual(c1, ci)

        # break the order
        children = self.container.getChildren()
        self.container._children = children[2:] + children[:2]
        c2 = [c.name for c in self.container]
        self.assertNotEqual(c1, c2)

        # verify the sort order
        self.container.sort()
        c3 = [c.name for c in self.container]
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
        self.assertEqual(self.container._getNuclidesFromSpecifier(["U238", "U235"]), ["U235", "U238"])

        uzr = self.container._getNuclidesFromSpecifier(["U238", "U235", "ZR"])
        self.assertIn("U235", uzr)
        self.assertIn("ZR92", uzr)
        self.assertNotIn("ZR", uzr)

        puIsos = self.container._getNuclidesFromSpecifier(["PU"])  # PU is special because it has no natural isotopics
        self.assertIn("PU239", puIsos)
        self.assertNotIn("PU", puIsos)

        self.assertEqual(self.container._getNuclidesFromSpecifier(["FE", "FE56"]).count("FE56"), 1)

    def test_hasFlags(self):
        """Ensure flags are queryable.

        .. test:: Flags can be queried.
            :id: T_ARMI_CMP_FLAG
            :tests: R_ARMI_CMP_FLAG
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

    def test_setChildrenLumpedFissionProducts(self):
        # build a lumped fission product collection
        fpd = getDummyLFPFile()
        lfps = fpd.createLFPsFromFile()

        # validate that the LFP collection is None
        self.container.setChildrenLumpedFissionProducts(None)
        for c in self.container:
            self.assertIsNone(c._lumpedFissionProducts)

        # validate that the LFP collection is not None
        self.container.setChildrenLumpedFissionProducts(lfps)
        for c in self.container:
            self.assertIsNotNone(c._lumpedFissionProducts)

    def test_requiresLumpedFissionProducts(self):
        # build a lumped fission product collection
        fpd = getDummyLFPFile()
        lfps = fpd.createLFPsFromFile()
        self.container.setChildrenLumpedFissionProducts(lfps)

        # test the null case
        result = self.container.requiresLumpedFissionProducts(None)
        self.assertFalse(result)

        # test the usual case
        result = self.container.requiresLumpedFissionProducts(set())
        self.assertFalse(result)

        # test a positive case
        result = self.container.requiresLumpedFissionProducts(["LFP35"])
        self.assertTrue(result)

    def test_getLumpedFissionProductsIfNecessaryNullCase(self):
        # build a lumped fission product collection
        fpd = getDummyLFPFile()
        lfps = fpd.createLFPsFromFile()
        self.container.setChildrenLumpedFissionProducts(lfps)

        # test the null case
        result = self.container.getLumpedFissionProductsIfNecessary(None)
        self.assertEqual(len(result), 0)

        # test a positive case
        result = self.container.getLumpedFissionProductsIfNecessary(["LFP35"])
        self.assertGreater(len(result), 0)

    def test_getIntegratedMgFlux(self):
        mgFlux = self.container.getIntegratedMgFlux()
        self.assertEqual(mgFlux, [0.0])

    def test_getReactionRates(self):
        # test the null case
        rRates = self.container.getReactionRates("U235")
        self.assertEqual(len(rRates), 6)
        self.assertEqual(sum([r for r in rRates.values()]), 0)

        # init reactor
        _o, r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        lib = nuclearDataIO.isotxs.readBinary(ISOAA_PATH)
        r.core.lib = lib

        # test on a Component
        b = r.core.getFirstAssembly().getFirstBlock()
        b.p.mgFlux = 1
        c = b.getComponents()[0]
        rRatesComp = c.getReactionRates("U235")
        self.assertEqual(len(rRatesComp), 6)
        self.assertGreater(sum([r for r in rRatesComp.values()]), 0)

        # test on a Block
        rRatesBlock = b.getReactionRates("U235")
        self.assertEqual(len(rRatesBlock), 6)
        self.assertGreater(sum([r for r in rRatesBlock.values()]), 0)

        # test on an Assembly
        assem = r.core.getFirstAssembly()
        rRatesAssem = assem.getReactionRates("U235")
        self.assertEqual(len(rRatesAssem), 6)
        self.assertGreater(sum([r for r in rRatesAssem.values()]), 0)

        # test on a Core
        rRatesCore = r.core.getReactionRates("U235")
        self.assertEqual(len(rRatesCore), 6)
        self.assertGreater(sum([r for r in rRatesCore.values()]), 0)

        # test on a Reactor
        rRatesReactor = r.getReactionRates("U235")
        self.assertEqual(len(rRatesReactor), 6)
        self.assertGreater(sum([r for r in rRatesReactor.values()]), 0)

        # test that all different levels of the hierarchy have the same reaction rates
        for key, val in rRatesBlock.items():
            self.assertAlmostEqual(rRatesAssem[key], val)
            self.assertAlmostEqual(rRatesCore[key], val)
            self.assertAlmostEqual(rRatesReactor[key], val)

    def test_getFirstComponent(self):
        c = self.container.getComponents()[0]
        c0 = self.container.getFirstComponent()
        self.assertIs(c, c0)
        self.assertIsInstance(c0, composites.Composite)

        c = self.cladChild.getComponents()[0]
        c0 = self.cladChild.getFirstComponent()
        self.assertIs(c, c0)
        self.assertIsInstance(c0, composites.Composite)

        c = self.secondGen.getComponents()[0]
        c0 = self.secondGen.getFirstComponent()
        self.assertIs(c, c0)
        self.assertIsInstance(c0, composites.Composite)

        b = loadTestBlock()
        c = b.getComponents()[0]
        c0 = b.getFirstComponent()
        self.assertIs(c, c0)
        self.assertIsInstance(c0, composites.Composite)

    def test_syncParameters(self):
        data = [{"serialNum": 123}, {"flags": "FAKE"}]
        numSynced = self.container._syncParameters(data, {})
        self.assertEqual(numSynced, 2)

    def test_iterChildrenWithFlags(self):
        expectedChildren = {c for c in self.container if c.hasFlags(Flags.DUCT)}
        found = set()
        for c in self.container.iterChildrenWithFlags(Flags.DUCT):
            self.assertIn(c, expectedChildren)
            found.add(c)
        self.assertSetEqual(found, expectedChildren)

    def test_iterChildrenOfType(self):
        clads = self.container.iterChildrenOfType("clad")
        first = next(clads)
        self.assertIs(first, self.cladChild)
        with self.assertRaises(StopIteration):
            next(clads)

    def test_removeAll(self):
        """Test the ability to remove all children of a composite."""
        self.container.removeAll()
        self.assertEqual(len(self.container), 0)
        # Nothing to iterate over
        items = iter(self.container)
        with self.assertRaises(StopIteration):
            next(items)
        for child in self.tree[1]:
            self.assertIsNone(child.parent)

    def test_setChildren(self):
        """Test the ability to override children on a composite."""
        newChildren = self.tree[2] + self.tree[3]
        oldChildren = list(self.container)
        self.container.setChildren(newChildren)
        self.assertEqual(len(self.container), len(newChildren))
        for old in oldChildren:
            self.assertIsNone(old.parent)
        for actualNew, expectedNew in zip(newChildren, self.container):
            self.assertIs(actualNew, expectedNew)


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
        self.block = None
        self.r = None

    def setUp(self):
        self.block = loadTestBlock()
        self.r = self.block.core.r
        self.block.setHeight(100.0)
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
        self.block.setNumberDensities(self.refDict)

    def test_ordering(self):
        a = assemblies.Assembly("dummy")
        a.spatialGrid = grids.AxialGrid.fromNCells(2, armiObject=a)
        otherBlock = deepcopy(self.block)
        a.add(self.block)
        a.add(otherBlock)
        self.assertTrue(self.block < otherBlock)
        locator = self.block.spatialLocator
        self.block.spatialLocator = otherBlock.spatialLocator
        otherBlock.spatialLocator = locator
        self.assertTrue(otherBlock < self.block)

        # test some edge cases
        otherBlock.spatialLocator._grid = None
        with self.assertRaises(ValueError):
            otherBlock < self.block

        otherBlock.spatialLocator = None
        with self.assertRaises(ValueError):
            otherBlock < self.block

    def test_getAncestorWithFlags(self):
        c = self.block.getAncestorWithFlags(Flags.FUEL)
        self.assertIsNone(c)

        comp = self.block.getFirstComponent()
        c = comp.getAncestorWithFlags(Flags.FUEL)
        self.assertIsNone(c)

        compos = self.block.getChildrenWithFlags(Flags.FUEL)[0]
        compon = compos.getFirstComponent()
        c = compon.getAncestorWithFlags(Flags.FUEL)
        self.assertEqual(c, compon)
        c = compos.getAncestorWithFlags(Flags.FUEL)
        self.assertEqual(c, compos)

    def test_changeNDensByFactor(self):
        c = deepcopy(self.block.getComponents(Flags.FUEL)[0])

        # test inital state
        dens = c.getNumberDensities()
        self.assertAlmostEqual(dens["ZR"], 0.03302903991506813, delta=1e-6)
        self.assertAlmostEqual(dens["U235"], 0.012819005788784095, delta=1e-6)
        self.assertAlmostEqual(dens["U238"], 0.10125669470078642, delta=1e-6)

        # change N dens
        c.changeNDensByFactor(0.5)

        # test new state
        dens = c.getNumberDensities()
        self.assertAlmostEqual(dens["ZR"], 0.03302903991506813 / 2, delta=1e-6)
        self.assertAlmostEqual(dens["U235"], 0.012819005788784095 / 2, delta=1e-6)
        self.assertAlmostEqual(dens["U238"], 0.10125669470078642 / 2, delta=1e-6)

    def test_summing(self):
        a = assemblies.Assembly("dummy")
        a.spatialGrid = grids.AxialGrid.fromNCells(2, armiObject=a)
        otherBlock = deepcopy(self.block)
        a.add(self.block)
        a.add(otherBlock)

        b = self.block + otherBlock
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
        """
        The getNuclides should return all keys that have ever been in this block, including values
        that are at trace.
        """
        cur = self.block.getNuclides()
        ref = self.refDict.keys()
        for key in ref:
            self.assertIn(key, cur)
        self.assertIn("FE", cur)  # this is in at trace value.

    def test_getFuelMass(self):
        """
        This test creates a dummy assembly and ensures that the assembly, block, and fuel component
        masses are consistent. `getFuelMass` ensures that the fuel component is used to `getMass`.
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
        referenceDensity = component.material.pseudoDensity(Tc=200)
        self.assertEqual(component.material.pseudoDensity(Tc=200), referenceDensity)

    def test_getHMMass(self):
        fuelDims = {"Tinput": 273.0, "Thot": 273.0, "od": 0.76, "id": 0.0, "mult": 1.0}
        self.fuelComponent = components.Circle("fuel", "UZr", **fuelDims)
        self.block.add(self.fuelComponent)

        self.block.clearNumberDensities()
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
        self.block.setNumberDensities(self.refDict)

        cur = self.block.getHMMass()

        mass = 0.0
        for nucName in self.refDict.keys():
            if nucDir.isHeavyMetal(nucName):
                mass += self.block.getMass(nucName)

        places = 6
        self.assertAlmostEqual(cur, mass, places=places)

    def test_getFPMass(self):
        fuelDims = {"Tinput": 273.0, "Thot": 273.0, "od": 0.76, "id": 0.0, "mult": 1.0}
        self.fuelComponent = components.Circle("fuel", "UZr", **fuelDims)
        self.fuelComponent.material.setMassFrac("LFP38", 0.25)
        self.block.add(self.fuelComponent)

        refDict = {"LFP35": 0.1, "LFP38": 0.05, "LFP39": 0.7}
        self.fuelComponent.setNumberDensities(refDict)

        cur = self.block.getFPMass()

        mass = 0.0
        for nucName in refDict.keys():
            mass += self.block.getMass(nucName)
        ref = mass

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_setMassFrac(self):
        # build test component
        c = DummyComposite("test_setMassFrac")
        c.getHeight = lambda: 1.0

        fuelDims = {"Tinput": 273.0, "Thot": 273.0, "od": 0.76, "id": 0.0, "mult": 1.0}
        fuelComponent = components.Circle("fuel", "UZr", **fuelDims)
        c.add(fuelComponent)

        # test initial state
        self.assertEqual(c.getFPMass(), 0.0)
        self.assertAlmostEqual(c.getHMMass(), 6.468105962375698, delta=1e-6)
        self.assertAlmostEqual(c.getMass(), 7.186784402639664, delta=1e-6)

        # use setMassFrac
        c.setMassFrac("U235", 0.99)
        c.setMassFrac("U238", 0.01)

        # test new state
        self.assertEqual(c.getFPMass(), 0.0)
        self.assertAlmostEqual(c.getHMMass(), 7.178895593948443, delta=1e-6)
        self.assertAlmostEqual(c.getMass(), 7.186784402639666, delta=1e-6)

        # test edge case were zero density
        for nucName in c.getMassFracs().keys():
            c.setNumberDensity(nucName, 0.0)

        with self.assertRaises(ValueError):
            c.setMassFrac("U235", 0.98)

    def test_getFissileMass(self):
        cur = self.block.getFissileMass()

        mass = 0.0
        for nucName in self.refDict.keys():
            if nucName in nuclideBases.NuclideBase.fissile:
                mass += self.block.getMass(nucName)
        ref = mass

        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getMaxParam(self):
        """Test getMaxParam().

        .. test:: Composites have parameter collections.
            :id: T_ARMI_CMP_PARAMS0
            :tests: R_ARMI_CMP_PARAMS
        """
        for ci, c in enumerate(self.block):
            if isinstance(c, basicShapes.Circle):
                c.p.id = ci
                lastSeen = c
                lastIndex = ci
        cMax, comp = self.block.getMaxParam("id", returnObj=True)
        self.assertEqual(cMax, lastIndex)
        self.assertIs(comp, lastSeen)

    def test_getMinParam(self):
        """Test getMinParam().

        .. test:: Composites have parameter collections.
            :id: T_ARMI_CMP_PARAMS1
            :tests: R_ARMI_CMP_PARAMS
        """
        for ci, c in reversed(list(enumerate(self.block))):
            if isinstance(c, basicShapes.Circle):
                c.p.id = ci
                lastSeen = c
                lastIndex = ci
        cMax, comp = self.block.getMinParam("id", returnObj=True)
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

        data2 = composites.FlagSerializer.unpack(flagsArray, composites.FlagSerializer.version, attrs)
        self.assertEqual(data, data2)

        # discrepant versions
        with self.assertRaises(ValueError):
            data2 = composites.FlagSerializer.unpack(flagsArray, "0", attrs)

        # missing flags in current version Flags
        attrs["flag_order"].append("NONEXISTANTFLAG")
        with mockRunLogs.BufferLog() as mock:
            self.assertEqual("", mock.getStdout())
            testName = "test_flagSerialization"
            runLog.LOG.startLog(testName)
            runLog.LOG.setVerbosity(logging.WARNING)

            data2 = composites.FlagSerializer.unpack(flagsArray, composites.FlagSerializer.version, attrs)
            flagLog = mock.getStdout()

        self.assertIn("The set of flags", flagLog)
        self.assertIn("NONEXISTANTFLAG", flagLog)

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

        # ad a second block, and confirm it works
        group.add(loadTestBlock())
        self.assertGreater(group.getMass("U235"), 5)
        self.assertAlmostEqual(group.getMass("U235"), 1364.28376185)

    def test_getNumberDensities(self):
        """Get number densities from composite.

        .. test:: Number density of composite is retrievable.
            :id: T_ARMI_CMP_GET_NDENS0
            :tests: R_ARMI_CMP_GET_NDENS
        """
        # verify the number densities from the composite
        ndens = self.obj.getNumberDensities()
        self.assertAlmostEqual(0.0001096, ndens["SI"], 7)
        self.assertAlmostEqual(0.0000368, ndens["W"], 7)

        ndens = self.obj.getNumberDensity("SI")
        self.assertAlmostEqual(0.0001096, ndens, 7)

        # sum nuc densities from children components
        totalVolume = self.obj.getVolume()
        childDensities = {}
        for o in self.obj:
            m = o.getVolume()
            d = o.getNumberDensities()
            for nuc, val in d.items():
                if nuc not in childDensities:
                    childDensities[nuc] = val * (m / totalVolume)
                else:
                    childDensities[nuc] += val * (m / totalVolume)

        # verify the children match this composite
        for nuc in ["FE", "SI"]:
            self.assertAlmostEqual(self.obj.getNumberDensity(nuc), childDensities[nuc], 4, msg=nuc)

    def test_getNumDensWithExpandedFissProds(self):
        """Get number densities from composite.

        .. test:: Get number densities.
            :id: T_ARMI_CMP_NUC
            :tests: R_ARMI_CMP_NUC
        """
        # verify the number densities from the composite
        ndens = self.obj.getNumberDensities(expandFissionProducts=True)
        self.assertAlmostEqual(0.0001096, ndens["SI"], 7)
        self.assertAlmostEqual(0.0000368, ndens["W"], 7)

        ndens = self.obj.getNumberDensity("SI")
        self.assertAlmostEqual(0.0001096, ndens, 7)

        # set the lumped fission product mapping
        fpd = getDummyLFPFile()
        lfps = fpd.createLFPsFromFile()
        self.obj.setLumpedFissionProducts(lfps)

        # sum nuc densities from children components
        totalVolume = self.obj.getVolume()
        childDensities = {}
        for o in self.obj:
            # get the number densities with and without fission products
            d0 = o.getNumberDensities(expandFissionProducts=False)
            d = o.getNumberDensities(expandFissionProducts=True)

            # prove that the expanded fission products have more isotopes
            if len(d0) > 0:
                self.assertGreater(len(d), len(d0))

            # sum the child nuclide densites (weighted by mass fraction)
            m = o.getVolume()
            for nuc, val in d.items():
                if nuc not in childDensities:
                    childDensities[nuc] = val * (m / totalVolume)
                else:
                    childDensities[nuc] += val * (m / totalVolume)

        # verify the children match this composite
        for nuc in ["FE", "SI"]:
            self.assertAlmostEqual(self.obj.getNumberDensity(nuc), childDensities[nuc], 4, msg=nuc)

    def test_dimensionReport(self):
        report = self.obj.setComponentDimensionsReport()
        self.assertEqual(len(report), len(self.obj))

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
        rxRatesDict = getReactionRateDict(nucName="PU239", lib=lib, xsSuffix="AA", mgFlux=1, nDens=1)
        self.assertEqual(rxRatesDict["nG"], sum(lib["PU39AA"].micros.nGamma))
