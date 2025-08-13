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

import math
import pickle
import unittest
from io import BytesIO
from random import randint

import numpy as np
from numpy.testing import assert_allclose, assert_array_equal

from armi.reactor import geometry, grids
from armi.utils import hexagon


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

    def test_multiIndexEq(self):
        """Check multi index locations are only true if they live on the same grid and have the same locations."""
        a = grids.MultiIndexLocation(None)
        a.append(grids.IndexLocation(0, 0, 0, None))
        b = grids.MultiIndexLocation(None)
        b.append(grids.IndexLocation(1, 1, 1, None))
        self.assertNotEqual(a, b)

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

        assert_allclose(blockLoc.getCompleteIndices(), np.array((2, 3, 3)))
        assert_allclose(blockLoc.getGlobalCoordinates(), (2.0, 3.0, 3.5))
        assert_allclose(blockLoc.getGlobalCellBase(), (1.5, 2.5, 3))
        assert_allclose(blockLoc.getGlobalCellTop(), (2.5, 3.5, 4))

        # check coordinates of pins in block
        assert_allclose(pinFree.getGlobalCoordinates(), (2.0 + 1.0, 3.0 + 2.0, 3.5 + 3.0))  # epic
        assert_allclose(pinIndexLoc.getGlobalCoordinates(), (2.0 + 0.1, 3.0 + 0.5, 3.5))  # wow

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
        grid = MockStructuredGrid(unitSteps=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
        assert_allclose(grid.getCoordinates((1, 1, 1)), (1, 1, 1))
        assert_allclose(grid.getCoordinates((0, 0, 0)), (0.0, 0.0, 0.0))
        assert_allclose(grid.getCoordinates((0, 0, -1)), (0, 0, -1))
        assert_allclose(grid.getCoordinates((1, 0, 0)), (1, 0, 0))

    def test_neighbors(self):
        grid = MockStructuredGrid(unitSteps=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
        neighbs = grid.getNeighboringCellIndices(0, 0, 0)
        self.assertEqual(len(neighbs), 4)

    def test_label(self):
        grid = MockStructuredGrid(unitSteps=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
        self.assertEqual(grid.getLabel((1, 1, 2)), "001-001-002")

    def test_isAxialOnly(self):
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)
        self.assertAlmostEqual(grid.pitch, 1.0)
        self.assertEqual(grid.isAxialOnly, False)

        grid2 = grids.AxialGrid.fromNCells(10)
        self.assertEqual(grid2.isAxialOnly, True)

    def test_lookupFactory(self):
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)
        self.assertAlmostEqual(grid.pitch, 1.0)
        self.assertEqual(grid[10, 5, 0].i, 10)

    def test_quasiReduce(self):
        """Make sure our DB-friendly version of reduce works."""
        grid = grids.HexGrid.fromPitch(1.0, numRings=3)
        self.assertAlmostEqual(grid.pitch, 1.0)
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
        self.assertAlmostEqual(grid.pitch, 1.0)
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
        grid = MockStructuredGrid(unitSteps=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))

        grid.armiObject = None
        with self.assertRaises(ValueError):
            grid.getRingPos(((0, 0), (1, 1)))


class TestHexGrid(unittest.TestCase):
    """A set of tests for the Hexagonal Grid."""

    def test_getCoordinatesFlatsUp(self):
        """Test getCoordinates() for flats up hex grids."""
        grid = grids.HexGrid.fromPitch(1.0, cornersUp=False)
        self.assertAlmostEqual(grid.pitch, 1.0)
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
                msg=f"Direction vector {directionVector} should have magnitude 1 for pitch 1.",
            )
        assert_allclose(grid.getCoordinates((1, 0, 0)), iDirection)
        assert_allclose(grid.getCoordinates((0, 1, 0)), jDirection)

    def test_getCoordinatesCornersUp(self):
        """Test getCoordinates() for corners up hex grids."""
        grid = grids.HexGrid.fromPitch(1.0, cornersUp=True)
        self.assertAlmostEqual(grid.pitch, 1.0)
        side = 1.0 / math.sqrt(3)
        assert_allclose(grid.getCoordinates((0, 0, 0)), (0.0, 0.0, 0.0))
        assert_allclose(grid.getCoordinates((1, 0, 0)), (0.5, 1.5 * side, 0.0))
        assert_allclose(grid.getCoordinates((-1, 0, 0)), (-0.5, -1.5 * side, 0.0))
        assert_allclose(grid.getCoordinates((0, 1, 0)), (-0.5, 1.5 * side, 0.0))
        assert_allclose(grid.getCoordinates((1, -1, 0)), (1, 0.0, 0.0))

        unitSteps = grid.reduce()[0]
        iDirection = tuple(direction[0] for direction in unitSteps)
        jDirection = tuple(direction[1] for direction in unitSteps)
        for directionVector in (iDirection, jDirection):
            self.assertAlmostEqual(
                (sum(val**2 for val in directionVector)) ** 0.5,
                1.0,
                msg=f"Direction vector {directionVector} should have magnitude 1 for pitch 1.",
            )
        assert_allclose(grid.getCoordinates((1, 0, 0)), iDirection)
        assert_allclose(grid.getCoordinates((0, 1, 0)), jDirection)

    def test_getLocalCoordinatesHex(self):
        """Test getLocalCoordinates() is different for corners up vs flats up hex grids."""
        grid0 = grids.HexGrid.fromPitch(1.0, cornersUp=True)
        grid1 = grids.HexGrid.fromPitch(1.0, cornersUp=False)
        for i in range(3):
            for j in range(3):
                if i == 0 and j == 0:
                    continue
                coords0 = grid0[i, j, 0].getLocalCoordinates()
                coords1 = grid1[i, j, 0].getLocalCoordinates()
                self.assertNotEqual(coords0[0], coords1[0], msg=f"X @ ({i}, {j})")
                self.assertNotEqual(coords0[1], coords1[1], msg=f"Y @ ({i}, {j})")
                self.assertEqual(coords0[2], coords1[2], msg=f"Z @ ({i}, {j})")

    def test_getLocalCoordinatesCornersUp(self):
        """Test getLocalCoordinates() for corners up hex grids."""
        # validate the first ring of a corners-up hex grid
        grid = grids.HexGrid.fromPitch(1.0, cornersUp=True)
        vals = []
        for pos in range(grid.getPositionsInRing(2)):
            i, j = grid.getIndicesFromRingAndPos(2, pos + 1)
            vals.append(grid[i, j, 0].getLocalCoordinates())

        # short in Y
        maxY = max(v[1] for v in vals)
        minY = min(v[1] for v in vals)
        val = math.sqrt(3) / 2
        self.assertAlmostEqual(maxY, val, delta=0.0001)
        self.assertAlmostEqual(minY, -val, delta=0.0001)

        # long in X
        maxX = max(v[0] for v in vals)
        minX = min(v[0] for v in vals)
        self.assertAlmostEqual(maxX, 1)
        self.assertAlmostEqual(minX, -1)

    def test_getLocalCoordinatesFlatsUp(self):
        """Test getLocalCoordinates() for flats up hex grids."""
        # validate the first ring of a flats-up hex grid
        grid = grids.HexGrid.fromPitch(1.0, cornersUp=False)
        vals = []
        for pos in range(grid.getPositionsInRing(2)):
            i, j = grid.getIndicesFromRingAndPos(2, pos + 1)
            vals.append(grid[i, j, 0].getLocalCoordinates())

        # long in Y
        maxY = max(v[1] for v in vals)
        minY = min(v[1] for v in vals)
        self.assertAlmostEqual(maxY, 1)
        self.assertAlmostEqual(minY, -1)

        # short in X
        maxX = max(v[0] for v in vals)
        minX = min(v[0] for v in vals)
        val = math.sqrt(3) / 2
        self.assertAlmostEqual(maxX, val, delta=0.0001)
        self.assertAlmostEqual(minX, -val, delta=0.0001)

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
        g.symmetry = str(geometry.SymmetryType(geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC))
        self.assertEqual(g.getSymmetricEquivalents((3, -2)), [(-1, 3), (-2, -1)])
        self.assertEqual(g.getSymmetricEquivalents((2, 1)), [(-3, 2), (1, -3)])

        symmetrics = g.getSymmetricEquivalents(g.getIndicesFromRingAndPos(5, 3))
        self.assertEqual([(5, 11), (5, 19)], [g.getRingPos(indices) for indices in symmetrics])

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
        flatsUp = grids.HexGrid.fromPitch(1.0, cornersUp=False)
        self.assertAlmostEqual(flatsUp._unitSteps[0][0], math.sqrt(3) / 2)
        self.assertAlmostEqual(flatsUp.pitch, 1.0)

        cornersUp = grids.HexGrid.fromPitch(1.0, cornersUp=True)
        self.assertAlmostEqual(cornersUp._unitSteps[0][0], 0.5)
        self.assertAlmostEqual(cornersUp.pitch, 1.0)

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
        self.assertEqual(boundsIJK, ((-numRings, numRings), (-numRings, numRings), (0, 1)))

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
        """Adjust the pitch of a hexagonal lattice, for a "flats up" grid.

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
                offset=np.array([offset, offset, offset]),
            )

            # test number of rings before converting pitch
            self.assertEqual(grid._unitStepLimits[0][1], 3)

            # test that we CAN change the pitch, and it scales the grid (but not the offset)
            v1 = grid.getCoordinates((1, 0, 0))
            grid.changePitch(2.0)
            self.assertAlmostEqual(grid.pitch, 2.0)
            v2 = grid.getCoordinates((1, 0, 0))
            assert_allclose(2 * v1 - offset, v2)

            # basic sanity: test number of rings has not changed
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
                unitSteps=(
                    (0.5, -0.5, 0),
                    (1.5 / math.sqrt(3), 1.5 / math.sqrt(3), 0),
                    (0, 0, 0),
                ),
                unitStepLimits=((-3, 3), (-3, 3), (0, 1)),
                offset=np.array(offsets),
            )

            # test number of rings before converting pitch
            self.assertEqual(grid._unitStepLimits[0][1], 3)

            # test that we CAN change the pitch, and it scales the grid (but not the offset)
            v1 = grid.getCoordinates((1, 0, 0))
            grid.changePitch(2.0)
            self.assertAlmostEqual(grid.pitch, 2.0, delta=1e-9)
            v2 = grid.getCoordinates((1, 0, 0))
            correction = np.array([0.5, math.sqrt(3) / 2, 0])
            assert_allclose(v1 + correction, v2)

            # basic sanity: test number of rings has not changed
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

    def test_rotatedIndices(self):
        """Test that a hex grid can produce a rotated cell location."""
        g = grids.HexGrid.fromPitch(1.0, numRings=3)
        center: grids.IndexLocation = g[(0, 0, 0)]
        notRotated = self._rotateAndCheckAngle(g, center, 0)
        self.assertEqual(notRotated, center)

        # One rotation for a trivial check
        northEast: grids.IndexLocation = g[(1, 0, 0)]
        dueNorth: grids.IndexLocation = g[(0, 1, 0)]
        northWest: grids.IndexLocation = g[(-1, 1, 0)]
        actual = self._rotateAndCheckAngle(g, northEast, 1)
        self.assertEqual(actual, dueNorth)
        np.testing.assert_allclose(dueNorth.getLocalCoordinates(), [0.0, 1.0, 0.0])

        actual = self._rotateAndCheckAngle(g, dueNorth, 1)
        self.assertEqual(actual, northWest)
        np.testing.assert_allclose(northWest.getLocalCoordinates(), [-hexagon.SQRT3 / 2, 0.5, 0])

        # Two rotations from the "first" object in the first full ring
        actual = self._rotateAndCheckAngle(g, northEast, 2)
        self.assertEqual(actual, northWest)

        # Fuzzy rotation: if we rotate an location, and then rotate it back, we get the same location
        for _ in range(10):
            startI = randint(-10, 10)
            startJ = randint(-10, 10)
            start = g[(startI, startJ, 0)]
            rotations = randint(-10, 10)
            postRotate = self._rotateAndCheckAngle(g, start, rotations)
            if startI == 0 and startJ == 0:
                self.assertEqual(postRotate, start)
                continue
            if rotations % 6:
                self.assertNotEqual(postRotate, start, msg=rotations)
            else:
                self.assertEqual(postRotate, start, msg=rotations)
            reversed = self._rotateAndCheckAngle(g, postRotate, -rotations)
            self.assertEqual(reversed, start)

    def _rotateAndCheckAngle(self, g: grids.HexGrid, start: grids.IndexLocation, rotations: int) -> grids.IndexLocation:
        """Rotate a location and verify it lands where we expected."""
        finish = g.rotateIndex(start, rotations)
        self._checkAngle(start, finish, rotations)
        return finish

    def _checkAngle(self, start: grids.IndexLocation, finish: grids.IndexLocation, rotations: int):
        """Compare two locations that should be some number of 60 degree CCW rotations apart."""
        startXY = start.getLocalCoordinates()[:2]
        theta = math.pi / 3 * rotations
        rotationMatrix = np.array(
            [
                [math.cos(theta), -math.sin(theta)],
                [math.sin(theta), math.cos(theta)],
            ]
        )
        expected = rotationMatrix.dot(startXY)
        finishXY = finish.getLocalCoordinates()[:2]
        np.testing.assert_allclose(finishXY, expected, atol=1e-8)

    def test_inconsistentRotationGrids(self):
        """Test that only locations in consistent grids are rotatable."""
        base = grids.HexGrid.fromPitch(1, cornersUp=False)
        larger = grids.HexGrid.fromPitch(base.pitch * 2, cornersUp=base.cornersUp)
        fromLarger = larger[1, 0, 0]
        with self.assertRaises(TypeError):
            base.rotateIndex(fromLarger)

        differentOrientation = grids.HexGrid.fromPitch(base.pitch, cornersUp=not base.cornersUp)
        fromDiffOrientation = differentOrientation[0, 1, 0]
        with self.assertRaises(TypeError):
            base.rotateIndex(fromDiffOrientation)

        axialGrid = grids.AxialGrid.fromNCells(5)
        fromAxial = axialGrid[2, 0, 0]
        with self.assertRaises(TypeError):
            base.rotateIndex(fromAxial)

    def test_rotatedIndexGridAssignment(self):
        """Test that the grid of the rotated index is identical through rotation."""
        base = grids.HexGrid.fromPitch(1)
        other = grids.HexGrid.fromPitch(base.pitch, cornersUp=base.cornersUp)

        for i, j in ((0, 0), (1, 1), (2, 1), (-1, 3)):
            loc = grids.IndexLocation(i, j, k=0, grid=other)
            postRotate = base.rotateIndex(loc, rotations=2)
            self.assertIs(postRotate.grid, loc.grid)

    def test_rotatedIndexRoughEqualPitch(self):
        """Test indices can be rotated in close but not exactly equal grids."""
        base = grids.HexGrid.fromPitch(1.345)
        other = grids.HexGrid.fromPitch(base.pitch * 1.00001)

        for i, j in ((0, 0), (1, 1), (2, 1), (-1, 3)):
            loc = grids.IndexLocation(i, j, k=0, grid=base)
            fromBase = base.rotateIndex(loc, rotations=2)
            fromOther = other.rotateIndex(loc, rotations=2)
            self.assertEqual((fromBase.i, fromBase.j), (fromOther.i, fromOther.j))


class TestBoundsDefinedGrid(unittest.TestCase):
    def test_positions(self):
        grid = MockStructuredGrid(bounds=([0, 1, 2, 3, 4], [0, 10, 20, 50], [0, 20, 60, 90]))
        assert_allclose(grid.getCoordinates((1, 1, 1)), (1.5, 15.0, 40.0))

    def test_base(self):
        grid = MockStructuredGrid(bounds=([0, 1, 2, 3, 4], [0, 10, 20, 50], [0, 20, 60, 90]))
        assert_allclose(grid.getCellBase((1, 1, 1)), (1.0, 10.0, 20.0))

    def test_positionsMixedDefinition(self):
        grid = MockStructuredGrid(unitSteps=((1.0, 0.0), (0.0, 1.0)), bounds=(None, None, [0, 20, 60, 90]))
        assert_allclose(grid.getCoordinates((1, 1, 1)), (1, 1, 40.0))

    def test_getIndexBounds(self):
        grid = MockStructuredGrid(bounds=([0, 1, 2, 3, 4], [0, 10, 20, 50], [0, 20, 60, 90]))
        boundsIJK = grid.getIndexBounds()
        self.assertEqual(boundsIJK, ((0, 5), (0, 4), (0, 4)))


class TestThetaRZGrid(unittest.TestCase):
    """A set of tests for the RZTheta Grid."""

    def test_positions(self):
        grid = grids.ThetaRZGrid(bounds=(np.linspace(0, 2 * math.pi, 13), [0, 2, 2.5, 3], [0, 10, 20, 30]))
        assert_allclose(grid.getCoordinates((1, 0, 1)), (math.sqrt(2) / 2, math.sqrt(2) / 2, 15.0))

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
            symmetry=str(geometry.SymmetryType(geometry.DomainType.QUARTER_CORE, geometry.BoundaryType.PERIODIC)),
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
            symmetry=geometry.SymmetryType(geometry.DomainType.QUARTER_CORE, geometry.BoundaryType.REFLECTIVE),
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
