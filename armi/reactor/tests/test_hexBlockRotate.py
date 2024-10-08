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

from armi.reactor.components import Component
from armi.reactor.blocks import HexBlock
from armi.utils import iterables
from armi.reactor.tests.test_blocks import loadTestBlock


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

    @classmethod
    def setUpClass(cls):
        cls.BASE_BLOCK = loadTestBlock()
        cls._assignParamData(cls.BOUNDARY_PARAMS, cls.BOUNDARY_DATA)

    @classmethod
    def _assignParamData(cls, names: list[str], referenceData: np.ndarray):
        """Assign initial rotatable pararameter data.

        Make some arrays, some lists to make sure we have good coverage of usage.
        """
        # Yes we're putting the variable type in the name but that's why this method exists
        listData = referenceData.tolist()
        for ix, name in enumerate(names):
            cls.BASE_BLOCK.p[name] = referenceData if (ix % 2) else listData

    def test_orientationVector(self):
        """Test the z-value in the orientation vector matches rotation.

        .. test:: Rotate a hex block in 60 degree increments.
            :id: T_ARMI_ROTATE_HEX
            :tests: R_ARMI_ROTATE_HEX

        .. test:: Update block orientation.
            :id: T_ARMI_ROTATE_HEX_ORIENTATION
            :tests: R_ARMI_ROTATE_HEX_PARAMS
        """
        for nRotations in range(-10, 10):
            rotationAmount = 60 * nRotations
            fresh = copy.deepcopy(self.BASE_BLOCK)
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
            :tests: R_ARMI_ROTATE_HEX_PARAMS
        """
        # No rotation == no changes to data
        self._rotateAndCompareBoundaryParams(0, self.BOUNDARY_DATA)
        for rotNum in range(1, 6):
            expected = iterables.pivot(self.BOUNDARY_DATA, -rotNum)
            self._rotateAndCompareBoundaryParams(rotNum * 60, expected)
        # Six rotations of 60 degrees puts us back to the original layout
        self._rotateAndCompareBoundaryParams(360, self.BOUNDARY_DATA)

    def _rotateAndCompareBoundaryParams(self, degrees: float, expected: np.ndarray):
        fresh = copy.deepcopy(self.BASE_BLOCK)
        fresh.rotate(math.radians(degrees))
        for name in self.BOUNDARY_PARAMS:
            data = fresh.p[name]
            msg = f"{name=} :: {degrees=} :: {data=}"
            np.testing.assert_array_equal(data, expected, err_msg=msg)

    @staticmethod
    def getComponentCoordinates(b: HexBlock) -> dict[Component, np.ndarray]:
        locations = {}
        for c in b:
            if c.spatialLocator is not None:
                coords = c.spatialLocator.getLocalCoordinates()
                # IndexLocator return array([x, y, z])
                # MultiIndexLocator return array([[x0, y0, z0], [x1, y1, z1]])
                # Reshape so we always have a shape of [nItems, 3] even if nItems == 1
                if coords.ndim == 1:
                    coords = coords.reshape((1, 3))
                locations[c] = coords
        return locations

    def test_childRotation(self):
        """Test that child coordinates are updated through rotation.

        .. test:: Rotating a hex block updates the spatial coordinates on contained objects.
            :id: T_ARMI_ROTATE_HEX_CHILD_LOCS
            :tests: R_ARMI_ROTATE_HEX
        """
        fresh = copy.deepcopy(self.BASE_BLOCK)
        originalCoords = self.getComponentCoordinates(fresh)
        for i in range(-10, 10):
            rotation = 60 * i
            self._rotateAndCheckComponentLocations(fresh, originalCoords, rotation)

    def _rotateAndCheckComponentLocations(
        self, b: HexBlock, originalCoords: dict[Component, np.ndarray], degrees: float
    ):
        rads = math.radians(degrees)
        b.rotate(rads)
        cosTheta = math.cos(rads)
        sinTheta = math.sin(rads)
        newCoords = self.getComponentCoordinates(b)
        for comp, coords in originalCoords.items():
            new = newCoords[comp]
            self._compareLocations(
                cosTheta, sinTheta, coords, new, msg=f"{comp=} :: {degrees=}"
            )

    def _compareLocations(
        self,
        cosTheta: float,
        sinTheta: float,
        previousCoords: np.ndarray,
        updatedCoords: np.ndarray,
        msg: str,
    ):
        oz = previousCoords[:, 2]
        nz = updatedCoords[:, 2]
        np.testing.assert_array_equal(nz, oz)
        ox = previousCoords[:, 0]
        oy = previousCoords[:, 1]
        nx = updatedCoords[:, 0]
        ny = updatedCoords[:, 1]
        expectedX = ox * cosTheta - oy * sinTheta
        np.testing.assert_array_equal(nx, expectedX, err_msg=msg)
        expectedY = ox * sinTheta + oy * cosTheta
        np.testing.assert_array_equal(ny, expectedY, err_msg=msg)

    def test_pinRotation(self):
        """Test that pin coordinates are updated through rotation.

        .. test:: HexBlock.getPinCoordinates is consistent with rotation.
            :id: T_ARMI_ROTATE_HEX_PIN_COORDS
            :tests: R_ARMI_ROTATE_HEX

        """


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
