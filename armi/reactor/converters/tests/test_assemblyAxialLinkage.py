import unittest

from armi.reactor.assemblies import HexAssembly, grids
from armi.reactor.components import UnshapedComponent
from armi.reactor.components.basicShapes import Circle, Hexagon, Rectangle
from armi.reactor.components.complexShapes import Helix
from armi.reactor.converters.axialExpansionChanger.assemblyAxialLinkage import (
    AssemblyAxialLinkage,
    AxialLink,
    _checkOverlap,
    areAxiallyLinked,
)
from armi.reactor.converters.tests.test_axialExpansionChanger import (
    AxialExpansionTestBase,
    _buildDummySodium,
    buildTestAssemblyWithFakeMaterial,
)
from armi.reactor.flags import Flags


class TestAxialLinkHelper(unittest.TestCase):
    """Tests for the AxialLink dataclass / namedtuple like class."""

    @classmethod
    def setUpClass(cls):
        cls.LOWER_BLOCK = _buildDummySodium(20, 10)

    def test_override(self):
        """Test the upper and lower attributes can be set after construction."""
        empty = AxialLink()
        self.assertIsNone(empty.lower)
        empty.lower = self.LOWER_BLOCK
        self.assertIs(empty.lower, self.LOWER_BLOCK)

    def test_construct(self):
        """Test the upper and lower attributes can be set at construction."""
        link = AxialLink(self.LOWER_BLOCK)
        self.assertIs(link.lower, self.LOWER_BLOCK)


class TestComponentLinks(AxialExpansionTestBase):
    """Test axial linkage between components."""

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

    def test_unshapedComponentAndCircle(self):
        comp1 = Circle(*self.common, od=1.0, id=0.0)
        comp2 = UnshapedComponent(*self.common, area=1.0)
        self.assertFalse(areAxiallyLinked(comp1, comp2))

    def test_unshapedComponents(self):
        compDims = {"Tinput": 25.0, "Thot": 25.0}
        compA = UnshapedComponent("unshaped_1", "FakeMat", **compDims)
        compB = UnshapedComponent("unshaped_2", "FakeMat", **compDims)
        self.assertFalse(areAxiallyLinked(compA, compB))

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


class TestBlockLink(unittest.TestCase):
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
