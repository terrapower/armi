# Copyright 2025 TerraPower, LLC
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

import io
from unittest import TestCase

from armi.reactor.assemblies import HexAssembly, grids
from armi.reactor.blocks import HexBlock
from armi.reactor.blueprints import Blueprints
from armi.reactor.components import UnshapedComponent
from armi.reactor.components.basicShapes import Circle, Hexagon, Rectangle
from armi.reactor.components.complexShapes import Helix
from armi.reactor.converters.axialExpansionChanger.assemblyAxialLinkage import (
    AssemblyAxialLinkage,
    AxialLink,
    _checkOverlap,
)
from armi.reactor.converters.tests.test_axialExpansionChanger import (
    AxialExpansionTestBase,
    _buildDummySodium,
    buildTestAssemblyWithFakeMaterial,
)
from armi.reactor.flags import Flags
from armi.settings.caseSettings import Settings

MULTIPIN_BP = """
blocks:
    fuel multiPin: &block_fuel_multiPin
        grid name: twoPin
        fuel 1: &component_fuelmultiPin
            shape: Circle
            material: UZr
            Tinput: 25.0
            Thot: 600.0
            id: 0.0
            od: 0.8
            latticeIDs: [1]
        fuel 2:
            <<: *component_fuelmultiPin
            latticeIDs: [2]
        coolant:
            shape: DerivedShape
            material: Sodium
            Tinput: 450.0
            Thot: 450.0
        duct:
            shape: Hexagon
            material: HT9
            Tinput: 25.0
            Thot: 450.0
            ip: 16.0
            mult: 1.0
            op: 16.6
assemblies:
    fuel:
        specifier: LA
        blocks: [*block_fuel_multiPin, *block_fuel_multiPin]
        height: [25.0, 25.0]
        axial mesh points: [1, 1]
        xs types: [A, A]
grids:
    twoPin:
       geom: hex_corners_up
       symmetry: full
       lattice map: |
         - - -  1 1 1 1
           - - 1 1 2 1 1
            - 1 1 1 1 1 1
             1 2 1 2 1 2 1
              1 1 1 1 1 1
               1 1 2 1 1
                1 1 1 1
"""


class TestAxialLinkHelper(TestCase):
    """Tests for the AxialLink dataclass / namedtuple like class."""

    @classmethod
    def setUpClass(cls):
        cls.LOWER_BLOCK = _buildDummySodium(20, 10)

    def test_override(self):
        """Test lower attribute can be set after construction."""
        empty = AxialLink()
        self.assertIsNone(empty.lower)
        empty.lower = self.LOWER_BLOCK
        self.assertIs(empty.lower, self.LOWER_BLOCK)

    def test_construct(self):
        """Test lower attributes can be set at construction."""
        link = AxialLink(self.LOWER_BLOCK)
        self.assertIs(link.lower, self.LOWER_BLOCK)


class TestAreAxiallyLinked(AxialExpansionTestBase):
    """Provide test coverage for the different cases in assemblyAxialLinkage.areAxiallyLinked."""

    def test_mismatchComponentType(self):
        """Case 4; component type mismatch."""
        compDims = ("test", "FakeMat", 25.0, 25.0)  # name, material, Tinput, Thot
        comp1 = Circle(*compDims, od=1.0, id=0.0)
        comp2 = UnshapedComponent(*compDims, area=1.0)
        self.assertFalse(AssemblyAxialLinkage.areAxiallyLinked(comp1, comp2))

    def test_unshapedComponents(self):
        """Case 1; unshaped components."""
        compDims = {"Tinput": 25.0, "Thot": 25.0}
        comp1 = UnshapedComponent("unshaped_1", "FakeMat", **compDims)
        comp2 = UnshapedComponent("unshaped_2", "FakeMat", **compDims)
        self.assertFalse(AssemblyAxialLinkage.areAxiallyLinked(comp1, comp2))

    def test_componentMult(self):
        """Case 3; multiplicity based linking."""
        compDims = ("test", "FakeMat", 25.0, 25.0)
        comp1 = Circle(*compDims, od=1.0, id=0.0)
        comp2 = Circle(*compDims, od=1.0, id=0.0)
        # mult are same, comp1 and comp2 are linked
        self.assertTrue(AssemblyAxialLinkage.areAxiallyLinked(comp1, comp2))
        # mult is different, now they are not linked
        comp2.p.mult = 2
        self.assertFalse(AssemblyAxialLinkage.areAxiallyLinked(comp1, comp2))

    def test_multiIndexLocation(self):
        """Case 2; block-grid based linking."""
        cs = Settings()
        with io.StringIO(MULTIPIN_BP) as stream:
            bps = Blueprints.load(stream)
            bps._prepConstruction(cs)
            lowerB: HexBlock = bps.assemblies["fuel"][0]
            upperB: HexBlock = bps.assemblies["fuel"][1]
            lowerFuel1, lowerFuel2 = lowerB.getComponents(Flags.FUEL)
            upperFuel1, _upperFuel2 = upperB.getComponents(Flags.FUEL)
            # same grid locs, are linked
            self.assertTrue(
                AssemblyAxialLinkage.areAxiallyLinked(lowerFuel1, upperFuel1)
            )
            # different grid locs, are not linked
            self.assertFalse(
                AssemblyAxialLinkage.areAxiallyLinked(lowerFuel2, upperFuel1)
            )


class TestCheckOverlap(AxialExpansionTestBase):
    """Test axial linkage between components via the AssemblyAxialLinkage._checkOverlap."""

    @classmethod
    def setUpClass(cls):
        """Contains common dimensions for all component class types."""
        super().setUp(cls)
        cls.common = ("test", "FakeMat", 25.0, 25.0)  # name, material, Tinput, Thot

    def runTest(
        self,
        componentsToTest: dict,
        assertionBool: bool,
    ):
        """Runs various linkage tests.

        Parameters
        ----------
        componentsToTest
            keys --> component class type; values --> dimensions specific to key
        assertionBool
            expected truth value for test

        Notes
        -----
        - components "typeA" and "typeB" are assumed to be vertically stacked
        - two assertions: 1) comparing "typeB" component to "typeA"; 2) comparing "typeA" component
          to "typeB"
        - the different assertions are particularly useful for comparing two annuli
        - to add Component class types to a test add dictionary entry with following:
          {Component Class Type: [{<settings for component 1>}, {<settings for component 2>}]
        """
        for method, dims in componentsToTest.items():
            typeA = method(*self.common, **dims[0])
            typeB = method(*self.common, **dims[1])
            msg = f"{self._testMethodName} failed for component type {str(method)}!"
            if assertionBool:
                self.assertTrue(_checkOverlap(typeA, typeB), msg=msg)
                self.assertTrue(_checkOverlap(typeB, typeA), msg=msg)
            else:
                self.assertFalse(_checkOverlap(typeA, typeB), msg=msg)
                self.assertFalse(_checkOverlap(typeB, typeA), msg=msg)

    def test_overlappingSolidPins(self):
        componentTypesToTest = {
            Circle: [{"od": 0.5, "id": 0.0}, {"od": 1.0, "id": 0.0}],
            Hexagon: [{"op": 0.5, "ip": 0.0}, {"op": 1.0, "ip": 0.0}],
            Rectangle: [
                {
                    "lengthOuter": 0.5,
                    "lengthInner": 0.0,
                    "widthOuter": 0.5,
                    "widthInner": 0.0,
                },
                {
                    "lengthOuter": 1.0,
                    "lengthInner": 0.0,
                    "widthOuter": 1.0,
                    "widthInner": 0.0,
                },
            ],
            Helix: [
                {"od": 0.5, "axialPitch": 1.0, "helixDiameter": 1.0},
                {"od": 1.0, "axialPitch": 1.0, "helixDiameter": 1.0},
            ],
        }
        self.runTest(componentTypesToTest, True)

    def test_solidPinNotOverlappingAnnulus(self):
        componentTypesToTest = {
            Circle: [{"od": 0.5, "id": 0.0}, {"od": 1.0, "id": 0.6}],
        }
        self.runTest(componentTypesToTest, False)

    def test_solidPinOverlappingWithAnnulus(self):
        componentTypesToTest = {
            Circle: [{"od": 0.7, "id": 0.0}, {"od": 1.0, "id": 0.6}],
        }
        self.runTest(componentTypesToTest, True)

    def test_annularPinNotOverlappingWithAnnulus(self):
        componentTypesToTest = {
            Circle: [{"od": 0.6, "id": 0.3}, {"od": 1.0, "id": 0.6}],
        }
        self.runTest(componentTypesToTest, False)

    def test_annularPinOverlappingWithAnnuls(self):
        componentTypesToTest = {
            Circle: [{"od": 0.7, "id": 0.3}, {"od": 1.0, "id": 0.6}],
        }
        self.runTest(componentTypesToTest, True)

    def test_thinAnnularPinOverlappingWithThickAnnulus(self):
        componentTypesToTest = {
            Circle: [{"od": 0.7, "id": 0.3}, {"od": 0.6, "id": 0.5}],
        }
        self.runTest(componentTypesToTest, True)

    def test_AnnularHexOverlappingThickAnnularHex(self):
        componentTypesToTest = {
            Hexagon: [{"op": 1.0, "ip": 0.8}, {"op": 1.2, "ip": 0.8}]
        }
        self.runTest(componentTypesToTest, True)


class TestMultipleComponentLinkage(AxialExpansionTestBase):
    """Ensure that multiple component axial linkage can be caught."""

    def test_getLinkedComponents(self):
        """Test for multiple component axial linkage."""
        linked = AssemblyAxialLinkage(buildTestAssemblyWithFakeMaterial("FakeMat"))
        b = linked.a.getFirstBlockByType("fuel")
        c = b.getComponent(typeSpec=Flags.FUEL)
        c.setDimension("od", 0.785, cold=True)
        with self.assertRaisesRegex(
            RuntimeError,
            expected_regex="Multiple component axial linkages have been found for ",
        ):
            linked._getLinkedComponents(b, c)


class TestBlockLink(TestCase):
    """Test the ability to link blocks in an assembly."""

    def test_singleBlock(self):
        """Test an edge case where a single block exists."""
        b = _buildDummySodium(300, 50)
        links = AssemblyAxialLinkage.getLinkedBlocks([b])
        self.assertEqual(len(links), 1)
        self.assertIn(b, links)
        linked = links.pop(b)
        self.assertIsNone(linked.lower)

    def test_multiBlock(self):
        """Test links with multiple blocks."""
        N_BLOCKS = 5
        blocks = [_buildDummySodium(300, 50) for _ in range(N_BLOCKS)]
        links = AssemblyAxialLinkage.getLinkedBlocks(blocks)
        first = blocks[0]
        lowLink = links[first]
        self.assertIsNone(lowLink.lower)
        for ix in range(1, N_BLOCKS - 1):
            current = blocks[ix]
            below = blocks[ix - 1]
            link = links[current]
            self.assertIs(link.lower, below)
        top = blocks[-1]
        lastLink = links[top]
        self.assertIs(lastLink.lower, blocks[-2])

    def test_emptyBlocks(self):
        """Test even smaller edge case when no blocks are passed."""
        with self.assertRaisesRegex(
            ValueError, "No blocks passed. Cannot determine links"
        ):
            AssemblyAxialLinkage.getLinkedBlocks([])

    def test_onAssembly(self):
        """Test assembly behavior is the same as sequence of blocks."""
        assembly = HexAssembly("test")
        N_BLOCKS = 5
        assembly.spatialGrid = grids.AxialGrid.fromNCells(numCells=N_BLOCKS)
        assembly.spatialGrid.armiObject = assembly

        blocks = []
        for _ in range(N_BLOCKS):
            b = _buildDummySodium(300, 10)
            assembly.add(b)
            blocks.append(b)

        fromBlocks = AssemblyAxialLinkage.getLinkedBlocks(blocks)
        fromAssem = AssemblyAxialLinkage.getLinkedBlocks(assembly)

        self.assertSetEqual(set(fromBlocks), set(fromAssem))

        for b, bLink in fromBlocks.items():
            aLink = fromAssem[b]
            self.assertIs(aLink.lower, bLink.lower)
