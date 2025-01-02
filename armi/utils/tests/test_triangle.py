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
"""Test the basic triangle math."""
import unittest

from armi.utils import triangle


class TestTriangle(unittest.TestCase):
    def test_getTriangleArea(self):
        """Test that getTriangleArea correctly calculates the area of a right triangle."""
        x1 = 0.0
        y1 = 0.0
        x2 = 1.0
        y2 = 0.0
        x3 = 0.0
        y3 = 1.0
        refArea = 1.0 / 2.0 * (y3 - y1) * (x2 - x1)
        Area = triangle.getTriangleArea(x1, y1, x2, y2, x3, y3)
        self.assertAlmostEqual(refArea, Area, 6)

    def test_checkIfPointIsInTriangle(self):
        """Test that checkIfPointIsInTrinagle can correctly identify if a point is inside or outside of a triangle."""
        # First check the right triangle case
        xT1 = 0.0
        yT1 = 0.0
        xT2 = 1.0
        yT2 = 0.0
        xT3 = 0.0
        yT3 = 1.0
        xP = 0.0
        yP = 0.0
        rightTriangleInOrOut = triangle.checkIfPointIsInTriangle(
            xT1, yT1, xT2, yT2, xT3, yT3, xP, yP
        )

        self.assertTrue(rightTriangleInOrOut)

        # now create a case that should evaluate False
        xP = 2.0
        yP = 0.5
        rightTriangleInOrOut = triangle.checkIfPointIsInTriangle(
            xT1, yT1, xT2, yT2, xT3, yT3, xP, yP
        )
        self.assertFalse(rightTriangleInOrOut)

        # Now check non right triangle
        xT1 = 26.0
        yT1 = 10.0
        xT2 = 100.0
        yT2 = 0.0
        xT3 = 0.0
        yT3 = 100.0
        xP = 50.0
        yP = 50.0

        generalTriangleInOrOut = triangle.checkIfPointIsInTriangle(
            xT1, yT1, xT2, yT2, xT3, yT3, xP, yP
        )
        self.assertTrue(generalTriangleInOrOut)

        # now check false case
        xP = 1.0
        yP = 60.0
        generalTriangleInOrOut = triangle.checkIfPointIsInTriangle(
            xT1, yT1, xT2, yT2, xT3, yT3, xP, yP
        )
        self.assertFalse(generalTriangleInOrOut)

        # Check a case that should cause failure since only two triangle can be drawn
        xP = 0.0
        yP = 0.17
        generalTriangleInOrOut = triangle.checkIfPointIsInTriangle(
            xT1, yT1, xT2, yT2, xT3, yT3, xP, yP
        )
        self.assertFalse(generalTriangleInOrOut)

    def test_checkIfPointIsInTriangle2(self):
        """Test that barycentricCheckIfPointIsInTriangle can identify if a point is inside or outside of a triangle."""
        # First check the right triangle case
        xT1 = 0.0
        yT1 = 0.0
        xT2 = 1.0
        yT2 = 0.0
        xT3 = 0.0
        yT3 = 1.0
        xP = 0.5
        yP = 0.5
        rightTriangleInOrOut = triangle.checkIfPointIsInTriangle(
            xT1, yT1, xT2, yT2, xT3, yT3, xP, yP
        )
        self.assertTrue(rightTriangleInOrOut)

        # Check a case that should cause failure for checkIfPointIsInTriangle since only two triangle can be drawn
        x1 = 0.15
        x2 = 0.0
        x3 = 0.0
        y1 = 0.17
        y2 = 0.054
        y3 = 0.376
        xP = 0.0
        yP = 0.17
        generalTriangleInOrOut = triangle.checkIfPointIsInTriangle(
            x1, y1, x2, y2, x3, y3, xP, yP
        )
        self.assertTrue(generalTriangleInOrOut)

        # now create a case that should evaluate False
        xP = 2.0
        yP = 0.5
        rightTriangleInOrOut = triangle.checkIfPointIsInTriangle(
            xT1, yT1, xT2, yT2, xT3, yT3, xP, yP
        )
        self.assertFalse(rightTriangleInOrOut)

        # Now check non right triangle
        xT1 = 26.0
        yT1 = 10.0
        xT2 = 100.0
        yT2 = 0.0
        xT3 = 0.0
        yT3 = 100.0
        xP = 50.0
        yP = 50.0

        generalTriangleInOrOut = triangle.checkIfPointIsInTriangle(
            xT1, yT1, xT2, yT2, xT3, yT3, xP, yP
        )
        self.assertTrue(generalTriangleInOrOut)

        # now check false case
        xP = 1.0
        yP = 60.0
        generalTriangleInOrOut = triangle.checkIfPointIsInTriangle(
            xT1, yT1, xT2, yT2, xT3, yT3, xP, yP
        )
        self.assertFalse(generalTriangleInOrOut)
