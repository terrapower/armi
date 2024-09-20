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
    """Test the ability to rotate data defined on a hexagonal lattice.

    For a single 60 degree rotation, the pre- and post-rotation pin
    layouts are::

              2  1      1  6
            3  0  6 -> 2  0  5
              4  5      3  4

    If the data were originally assigned with ``np.arange()``,
    the pre- and post-rotation vectors would be

    - Pre:  ``[0, 1, 2, 3, 4, 5, 6, ...]``
    - Post: ``[0, 6, 1, 2, 3, 4, 5, ...]``

    """

    def test_rotateTwoRingsOfScalars(self):
        """Test we can rotate scalar data on a two ringed hexagon."""
        data = np.arange(7, dtype=float)
        self._check2RingsAllRotations(data)

    def test_rotateTwoRingsOfVector(self):
        """Test we can rotate vector data provided in a two ringed hexagon."""
        data = np.arange(14, dtype=float).reshape((7, 2))
        self._check2RingsAllRotations(data)

    def _check2RingsAllRotations(self, data: np.ndarray):
        for rotations in range(0, 7):
            new = hexagon.rotateHexCellData(data, rotations)
            self._testTwoRotatedRings(
                new,
                data,
                shiftedBy=rotations,
            )

    def test_rotateTwoRingsOfHighDimensionalData(self):
        """Test data dimensioned beyond vectors at a cell are rotated properly."""
        nCells = 7
        # Could be neutron, gamma, and total multi-group flux per cell
        shape = (nCells, 3, 20)
        data = np.random.random_sample(shape)
        self._check2RingsAllRotations(data)

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

    def test_threeRings(self):
        """Test data up to the third ring can be rotated.

        For three rings::

                9   8   7             7   18  17
              10  2   1   18        8   1   6   16
            11  3   0   6   17 -> 9   2   0   5   15
              12  4   5   10        10  3   4   14
                13  14  15            11  12  13

        Ring three data before after one rotation:

        - ``[7,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18]``
        - ``[17, 18, 7, 8,  9,  10, 11, 12, 13, 14, 15, 16]``

        """
        nCells = 19
        data = np.arange(nCells, dtype=float)
        singleRot = hexagon.rotateHexCellData(data, nRotations=1)
        self._testTwoRotatedRings(singleRot, data, shiftedBy=1)
        postRing3 = singleRot[7:]
        expectedRing3 = np.array(
            [17, 18, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16], dtype=float
        )
        np.testing.assert_array_equal(postRing3, expectedRing3)

    def test_multiRingRotation(self):
        """Test that larger hex data arrays can be correctly rotated.

        Involves three types of checks:

        1. Rotation of the first two rings is exactly correct.
        2. Rotated data beyond the first cell differs from the original.
        3. If we rotate back to the original orientation, we get the original data.

        """
        nRings = 9
        nCells = hexagon.totalPositionsUpToRing(nRings)
        data = np.arange(nCells, dtype=float)
        for rotation in range(7):
            self._testRotateAndRestore(data, rotation)

    def _testRotateAndRestore(self, data: np.ndarray, firstRotation: int):
        rotated = hexagon.rotateHexCellData(data, firstRotation)
        self._testTwoRotatedRings(rotated, data, firstRotation)
        # If we actually rotated, make sure data that should be different is different
        if firstRotation % 6:
            diff = data[1:] == rotated[1:]
            self.assertFalse(
                diff.any(),
                msg="Rotated data beyond first cell should differ and don't.",
            )
        else:
            np.testing.assert_array_equal(
                rotated,
                data,
                err_msg="Data rotated a full 360 degrees or not rotated should not differ but does.",
            )
        # Rotate to the original configuration
        secondRotation = 6 - firstRotation
        restored = hexagon.rotateHexCellData(rotated, secondRotation)
        np.testing.assert_array_equal(
            restored, data, err_msg=f"{firstRotation=} and {secondRotation=}"
        )

    def test_rotateLists(self):
        """Test we can rotate list data identically as we would rotate array data."""
        shapes = (
            (7,),
            (7, 2),
            (hexagon.totalPositionsUpToRing(3), 2, 3),
            (hexagon.totalPositionsUpToRing(9),),
        )
        for shape in shapes:
            arrayData = np.random.random_sample(shape)
            rotatedList = hexagon.rotateHexCellData(arrayData.tolist(), 2)
            self.assertIsInstance(rotatedList, list)
            rotatedArray = hexagon.rotateHexCellData(arrayData, 2)
            np.testing.assert_array_equal(rotatedList, rotatedArray)

    def test_invalidNumCells(self):
        """Test that data must fully fill a hexagon."""
        dataMissingCenter = np.arange(1, 7)
        with self.assertRaisesRegex(ValueError, ".*missing cells"):
            hexagon.rotateHexCellData(dataMissingCenter, 2)
