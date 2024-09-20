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
"""Test hexagon tools."""
import math
import random
import unittest

import numpy as np

from armi.utils import hexagon


class TestHexagon(unittest.TestCase):
    N_FUZZY_DRAWS: int = 10
    """Number of random draws to use in some fuzzy testing"""

    def test_hexagon_area(self):
        """
        Area of a hexagon.

        .. test:: Hexagonal area is retrievable.
            :id: T_ARMI_UTIL_HEXAGON0
            :tests: R_ARMI_UTIL_HEXAGON
        """
        # Calculate area given a pitch
        self.assertEqual(hexagon.area(1), math.sqrt(3.0) / 2)
        self.assertEqual(hexagon.area(2), 4 * math.sqrt(3.0) / 2)

    def test_numPositionsInRing(self):
        """
        Calculate number of positions in a ring of hexagons.

        .. test:: Compute number of positions in ring.
            :id: T_ARMI_UTIL_HEXAGON1
            :tests: R_ARMI_UTIL_HEXAGON
        """
        self.assertEqual(hexagon.numPositionsInRing(1), 1)
        self.assertEqual(hexagon.numPositionsInRing(2), 6)
        self.assertEqual(hexagon.numPositionsInRing(3), 12)
        self.assertEqual(hexagon.numPositionsInRing(4), 18)

    def test_rotatedCellCenter(self):
        """Test that location of the center cell is invariant through rotation."""
        for rot in range(6):
            self.assertTrue(hexagon.getIndexOfRotatedCell(1, rot), 1)

    def test_rotatedFirstRing(self):
        """Simple test for the corners of the first ring are maintained during rotation."""
        # A 60 degree rotation is just incrementing the cell index by one here
        locations = list(range(2, 8))
        for locIndex, initialPosition in enumerate(locations):
            for rot in range(6):
                actual = hexagon.getIndexOfRotatedCell(initialPosition, rot)
                newIndex = (locIndex + rot) % 6
                expectedPosition = locations[newIndex]
                self.assertEqual(
                    actual, expectedPosition, msg=f"{initialPosition=}, {rot=}"
                )

    def test_rotateFuzzy(self):
        """Select some position number and rotation and check for consistency."""
        N_DRAWS = 100
        for _ in range(N_DRAWS):
            self._rotateFuzzyInner()

    def _rotateFuzzyInner(self):
        rot = random.randint(1, 5)
        initialCell = random.randint(2, 300)
        testInfoMsg = f"{rot=}, {initialCell=}"
        newCell = hexagon.getIndexOfRotatedCell(initialCell, rot)
        self.assertNotEqual(newCell, initialCell, msg=testInfoMsg)
        # should be in the same ring
        initialRing = hexagon.numRingsToHoldNumCells(initialCell)
        newRing = hexagon.numRingsToHoldNumCells(newCell)
        self.assertEqual(newRing, initialRing, msg=testInfoMsg)
        # If we un-rotate, we should get our initial cell
        reverseRot = (6 - rot) % 6
        reverseCell = hexagon.getIndexOfRotatedCell(newCell, reverseRot)
        self.assertEqual(reverseCell, initialCell, msg=testInfoMsg)

    def test_positionsUpToRing(self):
        """Test totalPositionsUpToRing is consistent with numPositionsInRing."""
        self.assertEqual(hexagon.totalPositionsUpToRing(1), 1)
        self.assertEqual(hexagon.totalPositionsUpToRing(2), 7)
        self.assertEqual(hexagon.totalPositionsUpToRing(3), 19)

        totalPositions = 19
        for ring in range(4, 30):
            posInThisRing = hexagon.numPositionsInRing(ring)
            totalPositions += posInThisRing
            self.assertEqual(
                hexagon.totalPositionsUpToRing(ring), totalPositions, msg=f"{ring=}"
            )

    def test_rotatedCellIndexErrors(self):
        """Test errors for non-positive initial cell indices during rotation."""
        self._testNonPosRotIndex(0)
        for _ in range(self.N_FUZZY_DRAWS):
            index = random.randint(-100, -1)
            self._testNonPosRotIndex(index)

    def _testNonPosRotIndex(self, index: int):
        with self.assertRaisesRegex(ValueError, ".*must be positive", msg=f"{index=}"):
            hexagon.getIndexOfRotatedCell(index, 0)

    def test_rotatedCellOrientationErrors(self):
        """Test errors for invalid orientation numbers during rotation."""
        for _ in range(self.N_FUZZY_DRAWS):
            upper = random.randint(6, 100)
            self._testRotOrientation(upper)
            lower = random.randint(-100, -1)
            self._testRotOrientation(lower)

    def _testRotOrientation(self, orientation: int):
        with self.assertRaisesRegex(
            ValueError, "Orientation number", msg=f"{orientation=}"
        ):
            hexagon.getIndexOfRotatedCell(
                initialCellIndex=1, orientationNumber=orientation
            )

    def test_indexWithNoRotation(self):
        """Test that the initial cell location is returned if not rotated."""
        for _ in range(self.N_FUZZY_DRAWS):
            ix = random.randint(1, 300)
            postRotation = hexagon.getIndexOfRotatedCell(ix, orientationNumber=0)
            self.assertEqual(postRotation, ix)


class TestHexCellRotate(unittest.TestCase):
    """Test the ability to rotate data defined on a hexagonal lattice."""

    def test_rotateTwoRingsOfScalars(self):
        """Test we can rotate scalar data on a two ringed hexagon.

        Pre-rotate pin layout -> Post-rotate layout::

              2  1      1  6
            3  0  6 -> 2  0  5
              4  5      3  4

        - Pre-rotate data:  ``[0, 1, 2, 3, 4, 5, 6, ...]``
        - Post-rotate data: ``[0, 6, 1, 2, 3, 4, 5, ...]``

        """
        data = np.arange(7, dtype=float)
        new = hexagon.rotateHexCellData(data, data.size, 1)
        self._testTwoRotatedRings(
            new,
            data,
            shiftedBy=1,
        )

    def test_rotateTwoRingsOfVector(self):
        """Test we can rotate vector data provided in a two ringed hexagon.

        Pre-rotate pin layout -> Post-rotate layout with two rotations::

              2  1      6  5
            3  0  6 -> 1  0  4
              4  5      2  3

        - Pre-rotate data:  ``[0, 1, 2, 3, 4, 5, 6, ...]``
        - Post-rotate data: ``[0, 5, 6, 1, 2, 3, 4, ...]``

        """
        data = np.arange(14, dtype=float).reshape((7, 2))
        new = hexagon.rotateHexCellData(data, data.size, 2)
        self._testTwoRotatedRings(
            new,
            data,
            shiftedBy=2,
        )

    @staticmethod
    def _testTwoRotatedRings(
        actual: np.array,
        expected: np.array,
        shiftedBy: int,
    ):
        np.testing.assert_array_equal(
            actual[0], expected[0], "Center location [0] differs when it should not"
        )
        for j in range(1, 7):
            i = j + shiftedBy
            # Wrap to start of counter
            if i > 6:
                i -= 6
            msg = f"post rotate [{i=}] != pre rotate [{j=}] with {shiftedBy=}"
            np.testing.assert_array_equal(actual[i], expected[j], msg)
