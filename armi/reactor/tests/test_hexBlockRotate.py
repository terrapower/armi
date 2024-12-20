# Copyright 2024 TerraPower, LLC
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
"""Tests for the ability to rotate a hexagonal block."""

import copy
import math
import unittest

import numpy as np

from armi.reactor.blocks import HexBlock
from armi.reactor.components import Component
from armi.reactor.grids import (
    CoordinateLocation,
    HexGrid,
    IndexLocation,
    MultiIndexLocation,
)
from armi.reactor.tests.test_blocks import NUM_PINS_IN_TEST_BLOCK, loadTestBlock
from armi.utils import iterables


class HexBlockRotateTests(unittest.TestCase):
    """Tests for various rotation aspects of a hex block."""

    BOUNDARY_PARAMS = [
        "cornerFastFlux",
        "pointsCornerDpa",
        "pointsCornerDpaRate",
        "pointsCornerFastFluxFr",
        "pointsEdgeDpa",
        "pointsEdgeDpaRate",
        "pointsEdgeFastFluxFr",
        "THedgeTemp",
        "THcornTemp",
    ]
    BOUNDARY_DATA = np.arange(6, dtype=float) * 10

    PIN_PARAMS = [
        "percentBuByPin",
        "linPowByPin",
    ]

    PIN_DATA = np.arange(NUM_PINS_IN_TEST_BLOCK, dtype=float)

    def setUp(self):
        self.baseBlock = loadTestBlock()
        self._assignParamData(self.BOUNDARY_PARAMS, self.BOUNDARY_DATA)
        self._assignParamData(self.PIN_PARAMS, self.PIN_DATA)

    def _assignParamData(self, names: list[str], referenceData: np.ndarray):
        """Assign initial rotatable pararameter data.

        Make some arrays, some lists to make sure we have good coverage of usage.
        """
        # Yes we're putting the variable type in the name but that's why this method exists
        listData = referenceData.tolist()
        for ix, name in enumerate(names):
            self.baseBlock.p[name] = referenceData if (ix % 2) else listData

    def test_orientationVector(self):
        """Test the z-value in the orientation vector matches rotation.

        .. test:: Demonstrate that a HexBlock can be rotated in 60 degree increments, and the
            resultant orientation parameter reflects the current rotation.
            :id: T_ARMI_ROTATE_HEX_BLOCK
            :tests: R_ARMI_ROTATE_HEX
        """
        for nRotations in range(-10, 10):
            rotationAmount = 60 * nRotations
            fresh = copy.deepcopy(self.baseBlock)
            self.assertEqual(fresh.p.orientation[2], 0.0, msg=nRotations)
            fresh.rotate(math.radians(rotationAmount))
            # Ensure rotation is bounded [0, 360)
            postRotationOrientation = fresh.p.orientation[2]
            self.assertTrue(0 <= postRotationOrientation < 360, msg=nRotations)
            # Trim off any extra rotation if beyond 360 or negative
            # What is the effective counter clockwise rotation?
            expectedOrientation = rotationAmount % 360
            self.assertEqual(
                postRotationOrientation, expectedOrientation, msg=nRotations
            )

    def test_rotateBoundaryParameters(self):
        """Test that boundary parameters are correctly rotated.

        .. test:: Rotating a hex block updates parameters on the boundary of the hexagon.
            :id: T_ARMI_ROTATE_HEX_BOUNDARY
            :tests: R_ARMI_ROTATE_HEX
        """
        # No rotation == no changes to data
        self._rotateAndCompareBoundaryParams(0, self.BOUNDARY_DATA)
        for rotNum in range(1, 6):
            expected = iterables.pivot(self.BOUNDARY_DATA, -rotNum)
            self._rotateAndCompareBoundaryParams(rotNum * 60, expected)
        # Six rotations of 60 degrees puts us back to the original layout
        self._rotateAndCompareBoundaryParams(360, self.BOUNDARY_DATA)

    def _rotateAndCompareBoundaryParams(self, degrees: float, expected: np.ndarray):
        fresh = copy.deepcopy(self.baseBlock)
        fresh.rotate(math.radians(degrees))
        for name in self.BOUNDARY_PARAMS:
            data = fresh.p[name]
            msg = f"{name=} :: {degrees=} :: {data=}"
            np.testing.assert_array_equal(data, expected, err_msg=msg)

    def assertIndexLocationEquivalent(
        self, actual: IndexLocation, expected: IndexLocation
    ):
        """More flexible equivalency check on index locations.

        Specifically focused on locations on hex grids because this file
        is testing things on hex blocks.

        Checks that
        1. ``i``, ``j``, and ``k`` are equal
        2. Grids are both hex grid
        3. Grids have same pitch and orientation.
        """
        self.assertEqual(actual.i, expected.i)
        self.assertEqual(actual.j, expected.j)
        self.assertEqual(actual.k, expected.k)
        self.assertIsInstance(actual.grid, HexGrid)
        self.assertIsInstance(expected.grid, HexGrid)
        self.assertEqual(actual.grid.cornersUp, expected.grid.cornersUp)
        self.assertEqual(actual.grid.pitch, expected.grid.pitch)

    def test_pinRotationLocations(self):
        """Test that pin locations are updated through rotation.

        .. test:: HexBlock.getPinLocations is consistent with rotation.
            :id: T_ARMI_ROTATE_HEX_PIN_LOCS
            :tests: R_ARMI_ROTATE_HEX
        """
        preRotation = self.baseBlock.getPinLocations()
        for nRotations in range(-10, 10):
            degrees = 60 * nRotations
            fresh = copy.deepcopy(self.baseBlock)
            g = fresh.spatialGrid
            fresh.rotate(math.radians(degrees))
            postRotation = fresh.getPinLocations()
            self.assertEqual(len(preRotation), len(postRotation))
            for pre, post in zip(preRotation, postRotation):
                expected = g.rotateIndex(pre, nRotations)
                self.assertIndexLocationEquivalent(post, expected)

    def test_pinRotationCoordinates(self):
        """Test that pin coordinates are updated through rotation.

        .. test:: HexBlock.getPinCoordinates is consistent through rotation.
            :id: T_ARMI_ROTATE_HEX_PIN_COORDS
            :tests: R_ARMI_ROTATE_HEX
        """
        preRotation = self.baseBlock.getPinCoordinates()
        # Over- and under-rotate to make sure we can handle clockwise and counter
        # clockwise rotations, and cases that wrap around a full rotation
        for degrees in range(-600, 600, 60):
            fresh = copy.deepcopy(self.baseBlock)
            rads = math.radians(degrees)
            fresh.rotate(rads)
            rotationMatrix = np.array(
                [
                    [math.cos(rads), -math.sin(rads)],
                    [math.sin(rads), math.cos(rads)],
                ]
            )
            postRotation = fresh.getPinCoordinates()
            self.assertEqual(len(preRotation), len(postRotation))
            for pre, post in zip(preRotation, postRotation):
                start = pre[:2]
                finish = post[:2]
                if np.allclose(start, 0):
                    np.testing.assert_equal(start, finish)
                    continue
                expected = rotationMatrix.dot(start)
                np.testing.assert_allclose(expected, finish, atol=1e-8)

    def test_updateChildLocations(self):
        """Test that locations of all children are updated through rotation.

        .. test:: Rotating a hex block updates the spatial coordinates on contained objects.
            :id: T_ARMI_ROTATE_HEX_CHILD_LOCS
            :tests: R_ARMI_ROTATE_HEX
        """
        for nRotations in range(-10, 10):
            fresh = copy.deepcopy(self.baseBlock)
            degrees = 60 * nRotations
            rads = math.radians(degrees)
            fresh.rotate(rads)
            for originalC, newC in zip(self.baseBlock, fresh):
                self._compareComponentLocationsAfterRotation(
                    originalC, newC, nRotations, rads
                )

    def _compareComponentLocationsAfterRotation(
        self, original: Component, updated: Component, nRotations: int, radians: float
    ):
        if isinstance(original.spatialLocator, MultiIndexLocation):
            for originalLoc, newLoc in zip(
                original.spatialLocator, updated.spatialLocator
            ):

                expected = originalLoc.grid.rotateIndex(originalLoc, nRotations)
                self.assertIndexLocationEquivalent(newLoc, expected)
        elif isinstance(original.spatialLocator, CoordinateLocation):
            ox, oy, oz = original.spatialLocator.getLocalCoordinates()
            nx, ny, nz = updated.spatialLocator.getLocalCoordinates()
            self.assertEqual(nz, oz, msg=f"{original=} :: {radians=}")
            rotationMatrix = np.array(
                [
                    [math.cos(radians), -math.sin(radians)],
                    [math.sin(radians), math.cos(radians)],
                ]
            )
            expectedX, expectedY = rotationMatrix.dot((ox, oy))
            np.testing.assert_allclose(
                (nx, ny), (expectedX, expectedY), err_msg=f"{original=} :: {radians=}"
            )

    def test_pinParametersUnmodified(self):
        """Test that pin data are not modified through rotation.

        Reinforces the idea that data like ``linPowByPin[i]`` are assigned to
        pin ``i``, wherever it may be. Locations are defined instead by ``getPinCoordinates()[i]``.
        """
        fresh = copy.deepcopy(self.baseBlock)
        fresh.rotate(math.radians(60))
        for paramName in self.PIN_PARAMS:
            actual = fresh.p[paramName]
            np.testing.assert_equal(actual, self.PIN_DATA, err_msg=paramName)


class EmptyBlockRotateTest(unittest.TestCase):
    """Rotation tests on an empty hexagonal block.

    Useful for enforcing rotation works on blocks without pins.
    """

    def setUp(self):
        self.block = HexBlock("empty")

    def test_orientation(self):
        """Test the orientation parameter is updated on a rotated empty block."""
        rotDegrees = 60
        preRotateOrientation = self.block.p.orientation[2]
        self.block.rotate(math.radians(rotDegrees))
        postRotationOrientation = self.block.p.orientation[2]
        self.assertNotEqual(preRotateOrientation, postRotationOrientation)
        self.assertEqual(postRotationOrientation, rotDegrees)
