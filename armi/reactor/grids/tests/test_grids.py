# Copyright 2023 TerraPower, LLC
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

"""Tests for grids."""
from io import BytesIO
import math
import unittest
import pickle

import numpy
from numpy.testing import assert_allclose, assert_array_equal

from armi.reactor import geometry
from armi.reactor import grids


class MockLocator(grids.IndexLocation):
    """
    Locator subclass that with direct location -> location paternity (to avoid
    needing blocks, assems).
    """

    @property
    def parentLocation(self):
        return self._parent


class MockCoordLocator(grids.CoordinateLocation):
    @property
    def parentLocation(self):
        return self._parent


class MockArmiObject:
    """Any sort of object that can serve as a grid's armiObject attribute."""

    def __init__(self, parent=None):
        self.parent = parent


class MockStructuredGrid(grids.StructuredGrid):
    """Need a concrete class to test a lot of inherited methods.

    Abstract methods from the parent now raise ``NotImplementedError``
    """


# De-abstract the mock structured grid to test some basic
# properties, but let the abstract methods error
def _throwsNotImplemented(*args, **kwargs):
    raise NotImplementedError


for f in MockStructuredGrid.__abstractmethods__:
    setattr(MockStructuredGrid, f, _throwsNotImplemented)

MockStructuredGrid.__abstractmethods__ = ()


class TestSpatialLocator(unittest.TestCase):
    def test_add(self):
        loc1 = grids.IndexLocation(1, 2, 0, None)
        loc2 = grids.IndexLocation(2, 2, 0, None)
        self.assertEqual(loc1 + loc2, grids.IndexLocation(3, 4, 0, None))

    def test_recursion(self):
        """
        Make sure things work as expected with a chain of locators/grids/locators.

        This makes a Cartesian-like reactor out of unit cubes. The origin
        is in the center of the central cube radially and the bottom axially due
        to the different way steps and bounds are set up.
        """
        core = MockArmiObject()
        assem = MockArmiObject(core)
        block = MockArmiObject(assem)

        # build meshes just like how they're used on a regular system.
        # 2-D grid
        coreGrid = grids.CartesianGrid.fromRectangle(1.0, 1.0, armiObject=core)

        # 1-D z-mesh
        assemblyGrid = grids.AxialGrid.fromNCells(5, armiObject=assem)

        # pins sit in this 2-D grid.
        blockGrid = grids.CartesianGrid.fromRectangle(0.1, 0.1, armiObject=block)

        coreLoc = grids.CoordinateLocation(0.0, 0.0, 0.0, None)
        core.spatialLocator = coreLoc

        assemblyLoc = grids.IndexLocation(2, 3, 0, coreGrid)
        assem.spatialLocator = assemblyLoc

        blockLoc = grids.IndexLocation(0, 0, 3, assemblyGrid)
        block.spatialLocator = blockLoc

        pinIndexLoc = grids.IndexLocation(1, 5, 0, blockGrid)
        pinFree = grids.CoordinateLocation(1.0, 2.0, 3.0, blockGrid)

        assert_allclose(blockLoc.getCompleteIndices(), numpy.array((2, 3, 3)))
        assert_allclose(blockLoc.getGlobalCoordinates(), (2.0, 3.0, 3.5))
        assert_allclose(blockLoc.getGlobalCellBase(), (1.5, 2.5, 3))
        assert_allclose(blockLoc.getGlobalCellTop(), (2.5, 3.5, 4))

        # check coordinates of pins in block
        assert_allclose(
            pinFree.getGlobalCoordinates(), (2.0 + 1.0, 3.0 + 2.0, 3.5 + 3.0)
        )  # epic
        assert_allclose(
            pinIndexLoc.getGlobalCoordinates(), (2.0 + 0.1, 3.0 + 0.5, 3.5)
        )  # wow

        # pin indices should not combine with the parent indices.
        assert_allclose(pinIndexLoc.getCompleteIndices(), (1, 5, 0))

    def test_recursionPin(self):
        """Ensure pin the center assem has axial coordinates consistent with a pin in
        an off-center assembly.
        """
        core = MockArmiObject()
        assem = MockArmiObject(core)
        block = MockArmiObject(assem)

        # 2-D grid
        coreGrid = grids.CartesianGrid.fromRectangle(1.0, 1.0, armiObject=core)
        # 1-D z-mesh
        assemblyGrid = grids.AxialGrid.fromNCells(5, armiObject=assem)
        # pins sit in this 2-D grid.
        blockGrid = grids.CartesianGrid.fromRectangle(0.1, 0.1, armiObject=block)

        coreLoc = grids.CoordinateLocation(0.0, 0.0, 0.0, None)
        core.spatialLocator = coreLoc
        assemblyLoc = grids.IndexLocation(0, 0, 0, coreGrid)
        assem.spatialLocator = assemblyLoc
        blockLoc = grids.IndexLocation(0, 0, 3, assemblyGrid)
        block.spatialLocator = blockLoc
        pinIndexLoc = grids.IndexLocation(1, 5, 0, blockGrid)

        assert_allclose(pinIndexLoc.getCompleteIndices(), (1, 5, 0))


class TestGrid(unittest.TestCase):
    def test_basicPosition(self):
        """
        Ensure a basic Cartesian grid works as expected.

        The default stepped grid defines zero at the center of the (0,0,0)th cell.
        Its centroid is 0., 0., 0). This convention is nicely compatible with 120-degree hex grid.

        Full core Cartesian meshes will want to be shifted to bottom left of 0th cell.
        """
        grid = MockStructuredGrid(
            unitSteps=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        )
        assert_allclose(grid.getCoordinates((1, 1, 1)), (1, 1, 1))
        assert_allclose(grid.getCoordinates((0, 0, 0)), (0.0, 0.0, 0.0))
        assert_allclose(grid.getCoordinates((0, 0, -1)), (0, 0, -1))
        assert_allclose(grid.getCoordinates((1, 0, 0)), (1, 0, 0))

    def test_neighbors(self):
        grid = MockStructuredGrid(
            unitSteps=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        )
        neighbs = grid.getNeighboringCellIndices(0, 0, 0)
        self.assertEqual(len(neighbs), 4)

    def test_label(self):
        grid = MockStructuredGrid(
            unitSteps=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        )
        self.assertEqual(grid.getLabel((1, 1, 2)), "001-001-002")

    def test_isAxialOnly(self):
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)
        self.assertEqual(grid.isAxialOnly, False)

        grid2 = grids.AxialGrid.fromNCells(10)
        self.assertEqual(grid2.isAxialOnly, True)

    def test_lookupFactory(self):
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)
        self.assertEqual(grid[10, 5, 0].i, 10)

    def test_quasiReduce(self):
        """Make sure our DB-friendly version of reduce works."""
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)
        reduction = grid.reduce()
        self.assertAlmostEqual(reduction[0][1][1], 1.0)

    def test_getitem(self):
        """
        Test that locations are created on demand, and the multi-index locations are
        returned when necessary.

        .. test:: Return the locations of grid items with multiplicity greater than one.
            :id: T_ARMI_GRID_ELEM_LOC
            :tests: R_ARMI_GRID_ELEM_LOC
        """
        grid = grids.HexGrid.fromPitch(1.0, numRings=0)
        self.assertNotIn((0, 0, 0), grid._locations)
        _ = grid[0, 0, 0]
        self.assertIn((0, 0, 0), grid._locations)

        multiLoc = grid[[(0, 0, 0), (1, 0, 0), (0, 1, 0)]]
        self.assertIsInstance(multiLoc, grids.MultiIndexLocation)
        self.assertIn((1, 0, 0), grid._locations)

        i = multiLoc.indices
        i = [ii.tolist() for ii in i]
        self.assertEqual(i, [[0, 0, 0], [1, 0, 0], [0, 1, 0]])

    def test_ringPosFromIndicesIncorrect(self):
        """Test the getRingPos fails if there is no armiObect or parent."""
        grid = MockStructuredGrid(
            unitSteps=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        )

        grid.armiObject = None
        with self.assertRaises(ValueError):
            grid.getRingPos(((0, 0), (1, 1)))


class TestHexGrid(unittest.TestCase):
    """A set of tests for the Hexagonal Grid."""

    def test_positions(self):
        grid = grids.HexGrid.fromPitch(1.0)
        side = 1.0 / math.sqrt(3)
        assert_allclose(grid.getCoordinates((0, 0, 0)), (0.0, 0.0, 0.0))
        assert_allclose(grid.getCoordinates((1, 0, 0)), (1.5 * side, 0.5, 0.0))
        assert_allclose(grid.getCoordinates((-1, 0, 0)), (-1.5 * side, -0.5, 0.0))
        assert_allclose(grid.getCoordinates((0, 1, 0)), (0, 1.0, 0.0))
        assert_allclose(grid.getCoordinates((1, -1, 0)), (1.5 * side, -0.5, 0.0))

        unitSteps = grid.reduce()[0]
        iDirection = tuple(direction[0] for direction in unitSteps)
        jDirection = tuple(direction[1] for direction in unitSteps)
        for directionVector in (iDirection, jDirection):
            self.assertAlmostEqual(
                (sum(val**2 for val in directionVector)) ** 0.5,
                1.0,
                msg=f"Direction vector {directionVector} should have "
                "magnitude 1 for pitch 1.",
            )
        assert_allclose(grid.getCoordinates((1, 0, 0)), iDirection)
        assert_allclose(grid.getCoordinates((0, 1, 0)), jDirection)

    def test_neighbors(self):
        grid = grids.HexGrid.fromPitch(1.0)
        neighbs = grid.getNeighboringCellIndices(0, 0, 0)
        self.assertEqual(len(neighbs), 6)
        self.assertIn((1, -1, 0), neighbs)

    def test_ringPosFromIndices(self):
        """Test conversion from<-->to ring/position based on hand-prepared right answers."""
        grid = grids.HexGrid.fromPitch(1.0)
        for indices, ringPos in [
            ((0, 0), (1, 1)),
            ((1, 0), (2, 1)),
            ((0, 1), (2, 2)),
            ((-1, 1), (2, 3)),
            ((-1, 0), (2, 4)),
            ((0, -1), (2, 5)),
            ((1, -1), (2, 6)),
            ((1, 1), (3, 2)),
            ((11, -7), (12, 60)),
            ((-1, -2), (4, 12)),
            ((-3, 1), (4, 9)),
            ((-2, 3), (4, 6)),
            ((1, 2), (4, 3)),
            ((2, -4), (5, 19)),
        ]:
            self.assertEqual(indices, grid.getIndicesFromRingAndPos(*ringPos))
            self.assertEqual(ringPos, grid.getRingPos(indices))

    def test_label(self):
        grid = grids.HexGrid.fromPitch(1.0)
        indices = grid.getIndicesFromRingAndPos(12, 5)
        label1 = grid.getLabel(indices)
        self.assertEqual(label1, "012-005")
        self.assertEqual(grids.locatorLabelToIndices(label1), (12, 5, None))

        label2 = grid.getLabel(indices + (5,))
        self.assertEqual(label2, "012-005-005")
        self.assertEqual(grids.locatorLabelToIndices(label2), (12, 5, 5))

    def test_overlapsWhichSymmetryLine(self):
        grid = grids.HexGrid.fromPitch(1.0)
        self.assertEqual(
            grid.overlapsWhichSymmetryLine(grid.getIndicesFromRingAndPos(5, 3)),
            grids.BOUNDARY_60_DEGREES,
        )
        self.assertEqual(
            grid.overlapsWhichSymmetryLine(grid.getIndicesFromRingAndPos(5, 23)),
            grids.BOUNDARY_0_DEGREES,
        )
        self.assertEqual(
            grid.overlapsWhichSymmetryLine(grid.getIndicesFromRingAndPos(3, 4)),
            grids.BOUNDARY_120_DEGREES,
        )

    def test_getSymmetricIdenticalsThird(self):
        """Retrieve equivalent contents based on 3rd symmetry.

        .. test:: Equivalent contents in 3rd geometry are retrievable.
            :id: T_ARMI_GRID_EQUIVALENTS
            :tests: R_ARMI_GRID_EQUIVALENTS
        """
        g = grids.HexGrid.fromPitch(1.0)
        g.symmetry = str(
            geometry.SymmetryType(
                geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC
            )
        )
        self.assertEqual(g.getSymmetricEquivalents((3, -2)), [(-1, 3), (-2, -1)])
        self.assertEqual(g.getSymmetricEquivalents((2, 1)), [(-3, 2), (1, -3)])

        symmetrics = g.getSymmetricEquivalents(g.getIndicesFromRingAndPos(5, 3))
        self.assertEqual(
            [(5, 11), (5, 19)], [g.getRingPos(indices) for indices in symmetrics]
        )

    def test_thirdAndFullSymmetry(self):
        """Test that we can construct a full and a 1/3 core grid.

        .. test:: Test 1/3 and full cores have the correct positions and rings.
            :id: T_ARMI_GRID_SYMMETRY
            :tests: R_ARMI_GRID_SYMMETRY
        """
        full = grids.HexGrid.fromPitch(1.0, symmetry="full core")
        third = grids.HexGrid.fromPitch(1.0, symmetry="third core periodic")

        # check full core
        self.assertEqual(full.getMinimumRings(2), 2)
        self.assertEqual(full.getIndicesFromRingAndPos(2, 2), (0, 1))
        self.assertEqual(full.getPositionsInRing(3), 12)
        self.assertEqual(full.getSymmetricEquivalents((3, -2)), [])

        # check 1/3 core
        self.assertEqual(third.getMinimumRings(2), 2)
        self.assertEqual(third.getIndicesFromRingAndPos(2, 2), (0, 1))
        self.assertEqual(third.getPositionsInRing(3), 12)
        self.assertEqual(third.getSymmetricEquivalents((3, -2)), [(-1, 3), (-2, -1)])

    def test_cornersUpFlatsUp(self):
        """Test the cornersUp attribute of the fromPitch method.

        .. test:: Build a points-up and a flats-up hexagonal grids.
            :id: T_ARMI_GRID_HEX_TYPE
            :tests: R_ARMI_GRID_HEX_TYPE
        """
        tipsUp = grids.HexGrid.fromPitch(1.0, cornersUp=True)
        flatsUp = grids.HexGrid.fromPitch(1.0, cornersUp=False)

        self.assertEqual(tipsUp._unitSteps[0][0], 0.5)
        self.assertAlmostEqual(flatsUp._unitSteps[0][0], 0.8660254037844388)

    def test_triangleCoords(self):
        g = grids.HexGrid.fromPitch(8.15)
        indices1 = g.getIndicesFromRingAndPos(5, 3) + (0,)
        indices2 = g.getIndicesFromRingAndPos(5, 23) + (0,)
        indices3 = g.getIndicesFromRingAndPos(3, 4) + (0,)
        cur = g.triangleCoords(indices1)
        ref = [
            (16.468_916_428_634_078, 25.808_333_333_333_337),
            (14.116_214_081_686_351, 27.166_666_666_666_67),
            (11.763_511_734_738_627, 25.808_333_333_333_337),
            (11.763_511_734_738_627, 23.091_666_666_666_67),
            (14.116_214_081_686_351, 21.733_333_333_333_334),
            (16.468_916_428_634_078, 23.091_666_666_666_67),
        ]
        assert_allclose(cur, ref)

        cur = grids.HexGrid.fromPitch(2.5).triangleCoords(indices2)
        ref = [
            (9.381_941_874_331_42, 0.416_666_666_666_666_7),
            (8.660_254_037_844_387, 0.833_333_333_333_333_4),
            (7.938_566_201_357_355_5, 0.416_666_666_666_666_7),
            (7.938_566_201_357_355_5, -0.416_666_666_666_666_7),
            (8.660_254_037_844_387, -0.833_333_333_333_333_4),
            (9.381_941_874_331_42, -0.416_666_666_666_666_7),
        ]
        assert_allclose(cur, ref)

        cur = grids.HexGrid.fromPitch(3.14).triangleCoords(indices3)
        ref = [
            (-1.812_879_845_255_425, 5.233_333_333_333_333),
            (-2.719_319_767_883_137_6, 5.756_666_666_666_667),
            (-3.625_759_690_510_850_2, 5.233_333_333_333_333),
            (-3.625_759_690_510_850_2, 4.186_666_666_666_666_5),
            (-2.719_319_767_883_137_6, 3.663_333_333_333_333),
            (-1.812_879_845_255_425, 4.186_666_666_666_666_5),
        ]
        assert_allclose(cur, ref)

    def test_getIndexBounds(self):
        numRings = 5
        g = grids.HexGrid.fromPitch(1.0, numRings=numRings)
        boundsIJK = g.getIndexBounds()
        self.assertEqual(
            boundsIJK, ((-numRings, numRings), (-numRings, numRings), (0, 1))
        )

    def test_getAllIndices(self):
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)
        indices = grid.getAllIndices()
        self.assertIn((1, 2, 0), indices)

    def test_buildLocations(self):
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)
        loc1 = grid[1, 2, 0]
        self.assertEqual(loc1.i, 1)
        self.assertEqual(loc1.j, 2)

    def test_is_pickleable(self):
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)
        loc = grid[1, 1, 0]
        for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
            buf = BytesIO()
            pickle.dump(loc, buf, protocol=protocol)
            buf.seek(0)
            newLoc = pickle.load(buf)
            assert_allclose(loc.indices, newLoc.indices)

    def test_adjustPitchFlatsUp(self):
        """Adjust the pich of a hexagonal lattice, for a "flats up" grid.

        .. test:: Construct a hexagonal lattice with three rings.
            :id: T_ARMI_GRID_HEX0
            :tests: R_ARMI_GRID_HEX

        .. test:: Return the grid coordinates of different locations.
            :id: T_ARMI_GRID_GLOBAL_POS0
            :tests: R_ARMI_GRID_GLOBAL_POS
        """
        # run this test for a grid with no offset, and then a few random offset values
        for offset in [0, 1, 1.123, 3.14]:
            # build a hex grid with pitch=1, 3 rings, and the above offset
            grid = grids.HexGrid(
                unitSteps=((1.5 / math.sqrt(3), 0.0, 0.0), (0.5, 1, 0.0), (0, 0, 0)),
                unitStepLimits=((-3, 3), (-3, 3), (0, 1)),
                offset=numpy.array([offset, offset, offset]),
                cornersUp=False,
            )

            # test that we CAN change the pitch, and it scales the grid (but not the offset)
            v1 = grid.getCoordinates((1, 0, 0))
            grid.changePitch(2.0)
            self.assertEqual(grid.pitch, 2.0)
            v2 = grid.getCoordinates((1, 0, 0))
            assert_allclose(2 * v1 - offset, v2)

            # basic sanity: test number of rings has changed
            self.assertEqual(grid._unitStepLimits[0][1], 3)

            # basic sanity: check the offset exists and is correct
            for i in range(3):
                self.assertEqual(grid.offset[i], offset)

    def test_adjustPitchCornersUp(self):
        """Adjust the pich of a hexagonal lattice, for a "corners up" grid.

        .. test:: Construct a hexagonal lattice with three rings.
            :id: T_ARMI_GRID_HEX1
            :tests: R_ARMI_GRID_HEX

        .. test:: Return the grid coordinates of different locations.
            :id: T_ARMI_GRID_GLOBAL_POS1
            :tests: R_ARMI_GRID_GLOBAL_POS
        """
        # run this test for a grid with no offset, and then a few random offset values
        for offset in [0, 1, 1.123, 3.14]:
            offsets = [offset, 0, 0]
            # build a hex grid with pitch=1, 3 rings, and the above offset
            grid = grids.HexGrid(
                unitSteps=((1.5 / math.sqrt(3), 0.0, 0.0), (0.5, 1, 0.0), (0, 0, 0)),
                unitStepLimits=((-3, 3), (-3, 3), (0, 1)),
                offset=numpy.array(offsets),
                cornersUp=True,
            )

            # test that we CAN change the pitch, and it scales the grid (but not the offset)
            v1 = grid.getCoordinates((1, 0, 0))
            grid.changePitch(2.0)
            self.assertAlmostEqual(grid.pitch, math.sqrt(3), delta=1e-9)
            v2 = grid.getCoordinates((1, 0, 0))
            b = math.sqrt(3) - 0.5
            a = math.sqrt(3) * b - 2
            correction = numpy.array([a, b, 0])
            assert_allclose(v1 + correction, v2)

            # basic sanity: test number of rings has changed
            self.assertEqual(grid._unitStepLimits[0][1], 3)

            # basic sanity: check the offset exists and is correct
            for i, off in enumerate(offsets):
                self.assertEqual(grid.offset[i], off)

    def test_badIndices(self):
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)

        # this is actually ok because step-defined grids are infinite
        self.assertEqual(grid.getCoordinates((-100, 2000, 5))[2], 0.0)

        grid = grids.AxialGrid.fromNCells(10)
        with self.assertRaises(IndexError):
            grid.getCoordinates((0, 5, -1))

    def test_isInFirstThird(self):
        """Determine if grid is in first third.

        .. test:: Determine if grid in first third.
            :id: T_ARMI_GRID_SYMMETRY_LOC
            :tests: R_ARMI_GRID_SYMMETRY_LOC
        """
        grid = grids.HexGrid.fromPitch(1.0, numRings=10)
        self.assertTrue(grid.isInFirstThird(grid[0, 0, 0]))
        self.assertTrue(grid.isInFirstThird(grid[1, 0, 0]))
        self.assertTrue(grid.isInFirstThird(grid[3, -1, 0]))
        self.assertFalse(grid.isInFirstThird(grid[1, -1, 0]))
        self.assertFalse(grid.isInFirstThird(grid[-1, -1, 0]))
        self.assertFalse(grid.isInFirstThird(grid[3, -2, 0]))

    def test_indicesAndEdgeFromRingAndPos(self):
        i, j, edge = grids.HexGrid._indicesAndEdgeFromRingAndPos(0, 0)
        self.assertEqual(i, 0)
        self.assertEqual(j, -1)
        self.assertEqual(edge, 1)

        i, j, edge = grids.HexGrid._indicesAndEdgeFromRingAndPos(1, 1)
        self.assertEqual(i, 0)
        self.assertEqual(j, 0)
        self.assertEqual(edge, 0)

        i, j, edge = grids.HexGrid._indicesAndEdgeFromRingAndPos(3, 11)
        self.assertEqual(i, 2)
        self.assertEqual(j, -2)
        self.assertEqual(edge, 5)

        i, j, edge = grids.HexGrid._indicesAndEdgeFromRingAndPos(3, 9)
        self.assertEqual(i, 0)
        self.assertEqual(j, -2)
        self.assertEqual(edge, 4)

        i, j, edge = grids.HexGrid._indicesAndEdgeFromRingAndPos(3, 7)
        self.assertEqual(i, -2)
        self.assertEqual(j, 0)
        self.assertEqual(edge, 3)

        i, j, edge = grids.HexGrid._indicesAndEdgeFromRingAndPos(3, 5)
        self.assertEqual(i, -2)
        self.assertEqual(j, 2)
        self.assertEqual(edge, 2)

        i, j, edge = grids.HexGrid._indicesAndEdgeFromRingAndPos(3, 3)
        self.assertEqual(i, 0)
        self.assertEqual(j, 2)
        self.assertEqual(edge, 1)

        i, j, edge = grids.HexGrid._indicesAndEdgeFromRingAndPos(7, 3)
        self.assertEqual(i, 4)
        self.assertEqual(j, 2)
        self.assertEqual(edge, 0)

        with self.assertRaises(ValueError):
            _ = grids.HexGrid._indicesAndEdgeFromRingAndPos(3, 13)

        with self.assertRaises(ValueError):
            _ = grids.HexGrid._indicesAndEdgeFromRingAndPos(1, 3)


class TestBoundsDefinedGrid(unittest.TestCase):
    def test_positions(self):
        grid = MockStructuredGrid(
            bounds=([0, 1, 2, 3, 4], [0, 10, 20, 50], [0, 20, 60, 90])
        )
        assert_allclose(grid.getCoordinates((1, 1, 1)), (1.5, 15.0, 40.0))

    def test_base(self):
        grid = MockStructuredGrid(
            bounds=([0, 1, 2, 3, 4], [0, 10, 20, 50], [0, 20, 60, 90])
        )
        assert_allclose(grid.getCellBase((1, 1, 1)), (1.0, 10.0, 20.0))

    def test_positionsMixedDefinition(self):
        grid = MockStructuredGrid(
            unitSteps=((1.0, 0.0), (0.0, 1.0)), bounds=(None, None, [0, 20, 60, 90])
        )
        assert_allclose(grid.getCoordinates((1, 1, 1)), (1, 1, 40.0))

    def test_getIndexBounds(self):
        grid = MockStructuredGrid(
            bounds=([0, 1, 2, 3, 4], [0, 10, 20, 50], [0, 20, 60, 90])
        )
        boundsIJK = grid.getIndexBounds()
        self.assertEqual(boundsIJK, ((0, 5), (0, 4), (0, 4)))


class TestThetaRZGrid(unittest.TestCase):
    """A set of tests for the RZTheta Grid."""

    def test_positions(self):
        grid = grids.ThetaRZGrid(
            bounds=(numpy.linspace(0, 2 * math.pi, 13), [0, 2, 2.5, 3], [0, 10, 20, 30])
        )
        assert_allclose(
            grid.getCoordinates((1, 0, 1)), (math.sqrt(2) / 2, math.sqrt(2) / 2, 15.0)
        )

        # test round trip ring position
        ringPos = (1, 1)
        indices = grid.getIndicesFromRingAndPos(*ringPos)
        ringPosFromIndices = grid.getRingPos(indices)
        self.assertEqual(ringPos, ringPosFromIndices)


class TestCartesianGrid(unittest.TestCase):
    """A set of tests for the Cartesian Grid."""

    def test_ringPosNoSplit(self):
        grid = grids.CartesianGrid.fromRectangle(1.0, 1.0, isOffset=True)

        expectedRing = [
            [3, 3, 3, 3, 3, 3],
            [3, 2, 2, 2, 2, 3],
            [3, 2, 1, 1, 2, 3],
            [3, 2, 1, 1, 2, 3],
            [3, 2, 2, 2, 2, 3],
            [3, 3, 3, 3, 3, 3],
        ]

        expectedPos = [
            [6, 5, 4, 3, 2, 1],
            [7, 4, 3, 2, 1, 20],
            [8, 5, 2, 1, 12, 19],
            [9, 6, 3, 4, 11, 18],
            [10, 7, 8, 9, 10, 17],
            [11, 12, 13, 14, 15, 16],
        ]
        expectedPos.reverse()

        for j in range(-3, 3):
            for i in range(-3, 3):
                ring, pos = grid.getRingPos((i, j))
                self.assertEqual(ring, expectedRing[j + 3][i + 3])
                self.assertEqual(pos, expectedPos[j + 3][i + 3])

        # Bonus test of getMinimumRings() using the above grid
        self.assertEqual(grid.getMinimumRings(7), 2)
        self.assertEqual(grid.getMinimumRings(17), 3)

    def test_ringPosSplit(self):
        grid = grids.CartesianGrid.fromRectangle(1.0, 1.0)

        expectedRing = [
            [4, 4, 4, 4, 4, 4, 4],
            [4, 3, 3, 3, 3, 3, 4],
            [4, 3, 2, 2, 2, 3, 4],
            [4, 3, 2, 1, 2, 3, 4],
            [4, 3, 2, 2, 2, 3, 4],
            [4, 3, 3, 3, 3, 3, 4],
            [4, 4, 4, 4, 4, 4, 4],
        ]

        expectedPos = [
            [7, 6, 5, 4, 3, 2, 1],
            [8, 5, 4, 3, 2, 1, 24],
            [9, 6, 3, 2, 1, 16, 23],
            [10, 7, 4, 1, 8, 15, 22],
            [11, 8, 5, 6, 7, 14, 21],
            [12, 9, 10, 11, 12, 13, 20],
            [13, 14, 15, 16, 17, 18, 19],
        ]
        expectedPos.reverse()

        for j in range(-3, 4):
            for i in range(-3, 4):
                ring, pos = grid.getRingPos((i, j))
                self.assertEqual(ring, expectedRing[j + 3][i + 3])
                self.assertEqual(pos, expectedPos[j + 3][i + 3])

    def test_symmetry(self):
        # PERIODIC, no split
        grid = grids.CartesianGrid.fromRectangle(
            1.0,
            1.0,
            symmetry=str(
                geometry.SymmetryType(
                    geometry.DomainType.QUARTER_CORE, geometry.BoundaryType.PERIODIC
                )
            ),
        )

        expected = {
            (0, 0): {(-1, 0), (-1, -1), (0, -1)},
            (1, 0): {(-1, 1), (-2, -1), (0, -2)},
            (2, 1): {(-2, 2), (-3, -2), (1, -3)},
            (2, 2): {(-3, 2), (-3, -3), (2, -3)},
            (0, 1): {(-2, 0), (-1, -2), (1, -1)},
            (-2, 2): {(-3, -2), (1, -3), (2, 1)},
        }

        for idx, expectedEq in expected.items():
            equivalents = {i for i in grid.getSymmetricEquivalents(idx)}

            self.assertEqual(expectedEq, equivalents)

        # PERIODIC, split
        grid = grids.CartesianGrid.fromRectangle(
            1.0,
            1.0,
            symmetry=geometry.SymmetryType(
                geometry.DomainType.QUARTER_CORE,
                geometry.BoundaryType.PERIODIC,
                throughCenterAssembly=True,
            ),
        )

        expected = {
            (0, 0): set(),
            (1, 0): {(0, 1), (-1, 0), (0, -1)},
            (2, 2): {(-2, 2), (-2, -2), (2, -2)},
            (2, 1): {(-1, 2), (-2, -1), (1, -2)},
            (-1, 3): {(-3, -1), (1, -3), (3, 1)},
            (0, 2): {(-2, 0), (0, -2), (2, 0)},
        }

        for idx, expectedEq in expected.items():
            equivalents = {i for i in grid.getSymmetricEquivalents(idx)}

            self.assertEqual(expectedEq, equivalents)

        # REFLECTIVE, no split
        grid = grids.CartesianGrid.fromRectangle(
            1.0,
            1.0,
            symmetry=geometry.SymmetryType(
                geometry.DomainType.QUARTER_CORE, geometry.BoundaryType.REFLECTIVE
            ),
        )

        expected = {
            (0, 0): {(-1, 0), (-1, -1), (0, -1)},
            (1, 0): {(-2, 0), (-2, -1), (1, -1)},
            (-2, 2): {(-2, -3), (1, -3), (1, 2)},
        }

        for idx, expectedEq in expected.items():
            equivalents = {i for i in grid.getSymmetricEquivalents(idx)}

            self.assertEqual(expectedEq, equivalents)

        # REFLECTIVE, split
        grid = grids.CartesianGrid.fromRectangle(
            1.0,
            1.0,
            symmetry=geometry.SymmetryType(
                geometry.DomainType.QUARTER_CORE,
                geometry.BoundaryType.REFLECTIVE,
                throughCenterAssembly=True,
            ),
        )

        expected = {
            (0, 0): set(),
            (1, 0): {(-1, 0)},
            (-1, 2): {(-1, -2), (1, -2), (1, 2)},
            (-2, 0): {(2, 0)},
            (0, -2): {(0, 2)},
        }

        for idx, expectedEq in expected.items():
            equivalents = {i for i in grid.getSymmetricEquivalents(idx)}

            self.assertEqual(expectedEq, equivalents)

        # Full core
        grid = grids.CartesianGrid.fromRectangle(
            1.0,
            1.0,
            symmetry=geometry.FULL_CORE,
        )
        self.assertEqual(grid.getSymmetricEquivalents((5, 6)), [])

        # 1/8 core not supported yet
        grid = grids.CartesianGrid.fromRectangle(
            1.0,
            1.0,
            symmetry=geometry.SymmetryType(
                geometry.DomainType.EIGHTH_CORE,
                geometry.BoundaryType.REFLECTIVE,
            ),
        )
        with self.assertRaises(NotImplementedError):
            grid.getSymmetricEquivalents((5, 6))


class TestAxialGrid(unittest.TestCase):
    def test_simpleBounds(self):
        N_CELLS = 5
        g = grids.AxialGrid.fromNCells(N_CELLS)
        _x, _y, z = g.getBounds()
        self.assertEqual(len(z), N_CELLS + 1)
        assert_array_equal(z, [0, 1, 2, 3, 4, 5])
        self.assertTrue(g.isAxialOnly)

    def test_getLocations(self):
        N_CELLS = 10
        g = grids.AxialGrid.fromNCells(N_CELLS)
        for count in range(N_CELLS):
            index = g[(0, 0, count)]
            x, y, z = index.getLocalCoordinates()
            self.assertEqual(x, 0.0)
            self.assertEqual(y, 0.0)
            self.assertEqual(z, count + 0.5)


if __name__ == "__main__":
    # import sys;sys.argv = ["", "TestHexGrid.testPositions"]
    unittest.main()
