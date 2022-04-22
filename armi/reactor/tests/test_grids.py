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

"""Tests for grids."""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import unittest
import math
from io import BytesIO

import numpy
from six.moves import cPickle

from armi.reactor import grids
from armi.reactor import geometry
from numpy.testing import assert_allclose


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
    """
    Any sort of object that can serve as a grid's armiObject attribute.
    """

    def __init__(self, parent=None):
        self.parent = parent


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
        coreGrid = grids.CartesianGrid.fromRectangle(
            1.0, 1.0, armiObject=core
        )  # 2-D grid
        # 1-D z-mesh
        assemblyGrid = grids.Grid(
            bounds=(None, None, numpy.arange(5)), armiObject=assem
        )
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
        """Ensure pin the center assem has axial coordinates consistent with a pin in an off-center assembly."""
        core = MockArmiObject()
        assem = MockArmiObject(core)
        block = MockArmiObject(assem)

        # 2-D grid
        coreGrid = grids.CartesianGrid.fromRectangle(1.0, 1.0, armiObject=core)
        # 1-D z-mesh
        assemblyGrid = grids.Grid(
            bounds=(None, None, numpy.arange(5)), armiObject=assem
        )
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
        grid = grids.Grid(unitSteps=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
        assert_allclose(grid.getCoordinates((1, 1, 1)), (1, 1, 1))
        assert_allclose(grid.getCoordinates((0, 0, 0)), (0.0, 0.0, 0.0))
        assert_allclose(grid.getCoordinates((0, 0, -1)), (0, 0, -1))
        assert_allclose(grid.getCoordinates((1, 0, 0)), (1, 0, 0))

    def test_neighbors(self):
        grid = grids.Grid(unitSteps=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
        neighbs = grid.getNeighboringCellIndices(0, 0, 0)
        self.assertEqual(len(neighbs), 4)

    def test_label(self):
        grid = grids.Grid(unitSteps=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
        self.assertEqual(grid.getLabel((1, 1, 2)), "001-001-002")

    def test_isAxialOnly(self):
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)
        self.assertEqual(grid.isAxialOnly, False)

        grid2 = grids.axialUnitGrid(10)
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
        """
        grid = grids.HexGrid.fromPitch(1.0, numRings=0)
        self.assertNotIn((0, 0, 0), grid._locations)
        _ = grid[0, 0, 0]
        self.assertIn((0, 0, 0), grid._locations)

        multiLoc = grid[[(0, 0, 0), (1, 0, 0), (0, 1, 0)]]
        self.assertIsInstance(multiLoc, grids.MultiIndexLocation)
        self.assertIn((1, 0, 0), grid._locations)


class TestHexGrid(unittest.TestCase):
    """A set of tests for the Hexagonal Grid

    .. test: Tests of the Hexagonal grid.
       :id: TEST_REACTOR_MESH_0
       :link: REQ_REACTOR_MESH
    """

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
                (sum(val ** 2 for val in directionVector)) ** 0.5,
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
        grid = grids.HexGrid.fromPitch(1.0)
        grid.symmetry = str(
            geometry.SymmetryType(
                geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC
            )
        )
        self.assertEqual(grid.getSymmetricEquivalents((3, -2)), [(-1, 3), (-2, -1)])
        self.assertEqual(grid.getSymmetricEquivalents((2, 1)), [(-3, 2), (1, -3)])

        symmetrics = grid.getSymmetricEquivalents(grid.getIndicesFromRingAndPos(5, 3))
        self.assertEqual(
            [(5, 11), (5, 19)], [grid.getRingPos(indices) for indices in symmetrics]
        )

    def test_triangleCoords(self):
        grid = grids.HexGrid.fromPitch(8.15)
        indices1 = grid.getIndicesFromRingAndPos(5, 3) + (0,)
        indices2 = grid.getIndicesFromRingAndPos(5, 23) + (0,)
        indices3 = grid.getIndicesFromRingAndPos(3, 4) + (0,)
        cur = grid.triangleCoords(indices1)
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
        grid = grids.HexGrid.fromPitch(1.0, numRings=numRings)
        boundsIJK = grid.getIndexBounds()
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
        for protocol in range(cPickle.HIGHEST_PROTOCOL + 1):
            buf = BytesIO()
            cPickle.dump(loc, buf, protocol=protocol)
            buf.seek(0)
            newLoc = cPickle.load(buf)
            assert_allclose(loc.indices, newLoc.indices)

    def test_adjustPitch(self):
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)
        v1 = grid.getCoordinates((1, 0, 0))
        grid.changePitch(2.0)
        v2 = grid.getCoordinates((1, 0, 0))
        assert_allclose(2 * v1, v2)

    def test_badIndices(self):
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)

        # this is actually ok because step-defined grids are infinite
        self.assertEqual(grid.getCoordinates((-100, 2000, 5))[2], 0.0)

        grid = grids.axialUnitGrid(10)
        with self.assertRaises(IndexError):
            grid.getCoordinates((0, 5, -1))

    def test_isInFirstThird(self):
        grid = grids.HexGrid.fromPitch(1.0, numRings=10)
        self.assertTrue(grid.isInFirstThird(grid[0, 0, 0]))
        self.assertTrue(grid.isInFirstThird(grid[1, 0, 0]))
        self.assertTrue(grid.isInFirstThird(grid[3, -1, 0]))
        self.assertFalse(grid.isInFirstThird(grid[1, -1, 0]))
        self.assertFalse(grid.isInFirstThird(grid[-1, -1, 0]))
        self.assertFalse(grid.isInFirstThird(grid[3, -2, 0]))


class TestBoundsDefinedGrid(unittest.TestCase):
    def test_positions(self):
        grid = grids.Grid(bounds=([0, 1, 2, 3, 4], [0, 10, 20, 50], [0, 20, 60, 90]))
        assert_allclose(grid.getCoordinates((1, 1, 1)), (1.5, 15.0, 40.0))

    def test_base(self):
        grid = grids.Grid(bounds=([0, 1, 2, 3, 4], [0, 10, 20, 50], [0, 20, 60, 90]))
        assert_allclose(grid.getCellBase((1, 1, 1)), (1.0, 10.0, 20.0))

    def test_positionsMixedDefinition(self):
        grid = grids.Grid(
            unitSteps=((1.0, 0.0), (0.0, 1.0)), bounds=(None, None, [0, 20, 60, 90])
        )
        assert_allclose(grid.getCoordinates((1, 1, 1)), (1, 1, 40.0))

    def test_getIndexBounds(self):
        grid = grids.Grid(bounds=([0, 1, 2, 3, 4], [0, 10, 20, 50], [0, 20, 60, 90]))
        boundsIJK = grid.getIndexBounds()
        self.assertEqual(boundsIJK, ((0, 5), (0, 4), (0, 4)))


class TestThetaRZGrid(unittest.TestCase):
    """A set of tests for the RZTheta Grid

    .. test: Tests of the RZTheta grid.
       :id: TEST_REACTOR_MESH_1
       :link: REQ_REACTOR_MESH
    """

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
    """A set of tests for the Cartesian Grid

    .. test: Tests of the Cartesian grid.
       :id: TEST_REACTOR_MESH_2
       :link: REQ_REACTOR_MESH
    """

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


if __name__ == "__main__":
    # import sys;sys.argv = ["", "TestHexGrid.testPositions"]
    unittest.main()
