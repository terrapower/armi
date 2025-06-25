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

"""Generic triangle math."""

import math


def getTriangleArea(x1: float, y1: float, x2: float, y2: float, x3: float, y3: float) -> float:
    """
    Get the area of a triangle given the vertices of a triangle using Heron's formula.

    Parameters
    ----------
    x1 : float
        x coordinate of first point defining a triangle
    y1 : float
        y coordinate of first point defining a triangle
    x2 : float
        x coordinate of second point defining a triangle
    y2 : float
        y coordinate of second point defining a triangle
    x3 : float
        x coordinate of third point defining a triangle
    y3 : float
        y coordinate of third point defining a triangle

    Notes
    -----
    See `https://en.wikipedia.org/wiki/Heron%27s_formula` for more information.
    """
    a = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
    b = math.sqrt((x2 - x3) ** 2 + (y2 - y3) ** 2)
    c = math.sqrt((x1 - x3) ** 2 + (y1 - y3) ** 2)

    area = 1.0 / 4.0 * math.sqrt((a + (b + c)) * (c - (a - b)) * (c + (a - b)) * (a + (b - c)))

    return area


def getTriangleCentroid(x1, y1, x2, y2, x3, y3):
    """
    Return the x and y coordinates of a triangle's centroid.

    Parameters
    ----------
    x1 : float
        x coordinate of first point defining a triangle
    y1 : float
        y coordinate of first point defining a triangle
    x2 : float
        x coordinate of second point defining a triangle
    y2 : float
        y coordinate of second point defining a triangle
    x3 : float
        x coordinate of third point defining a triangle
    y3 : float
        y coordinate of third point defining a triangle

    Returns
    -------
    x : float
        x coordinate of triangle's centroid
    y : float
        y coordinate of a triangle's centroid
    """
    x = (x1 + x2 + x3) / 3.0
    y = (y1 + y2 + y3) / 3.0

    return x, y


def checkIfPointIsInTriangle(
    x1: float, y1: float, x2: float, y2: float, x3: float, y3: float, x: float, y: float
) -> bool:
    """
    Test if a point defined by x,y coordinates is within a triangle defined by vertices with x,y coordinates.

    Parameters
    ----------
    x1 : float
        x coordinate of first point of the bounding triangle
    y1 : float
        y coordinate of first point of the bounding triangle
    x2 : float
        x coordinate of second point of the bounding triangle
    y2 : float
        y coordinate of second point of the bounding triangle
    x3 : float
        x coordinate of third point of the bounding triangle
    y3 : float
        y coordinate of third point of the bounding triangle
    x : float
        x coordinate of point being tested
    y : float
        y coordinate of point being tested

    Notes
    -----
    This method uses the barycentric method.
    See `http://totologic.blogspot.com/2014/01/accurate-point-in-triangle-test.html`
    """
    a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / ((y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3))
    b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / ((y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3))
    c = 1.0 - a - b
    epsilon = 1e-10  # need to have some tolerance in case the point lies on the edge of the triangle

    aCondition = a + epsilon >= 0.0 and a - epsilon <= 1.0
    bCondition = b + epsilon >= 0.0 and b - epsilon <= 1.0
    cCondition = c + epsilon >= 0.0 and c - epsilon <= 1.0

    return aCondition and bCondition and cCondition
