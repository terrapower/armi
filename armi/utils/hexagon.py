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

r"""
Generic hexagon math.

Hexagons are fundamental to advanced reactors.

.. image:: /.static/hexagon.png
    :width: 100%

"""

import math

import numpy

SQRT3 = math.sqrt(3.0)


def area(pitch):
    """Area of a hex given the flat-to-flat pitch."""
    return SQRT3 / 2.0 * pitch ** 2


def side(pitch):
    r"""
    Side length of a hex given the flat-to-flat pitch.

    Pythagorean theorem says:

    .. math::

        \frac{s}{2}^2 + \frac{p}{2}^2 = s^2

    which you can solve to find p = sqrt(3)*s
    """
    return pitch / SQRT3


def corners(rotation=0):
    """
    Return the coordinates of a unit hexagon, rotated as requested.

    Zero rotation implies flat-to-flat aligned with y-axis. Origin in the center.
    """
    points = numpy.array(
        [
            (1.0 / (2.0 * math.sqrt(3.0)), 0.5),
            (1.0 / math.sqrt(3.0), 0.0),
            (1.0 / (2.0 * math.sqrt(3.0)), -0.5),
            (-1.0 / (2.0 * math.sqrt(3.0)), -0.5),
            (-1.0 / math.sqrt(3.0), 0.0),
            (-1.0 / (2.0 * math.sqrt(3.0)), 0.5),
        ]
    )

    rotation = rotation / 180.0 * math.pi

    rotation = numpy.array(
        [
            [math.cos(rotation), -math.sin(rotation)],
            [math.sin(rotation), math.cos(rotation)],
        ]
    )

    return numpy.array([tuple(rotation.dot(point)) for point in points])


def pitch(side):
    return side * SQRT3


def numRingsToHoldNumCells(numCells):
    r"""
    Determine the number of rings in a hexagonal grid with this many hex cells.
    If the number of pins don't fit exactly into any ring, returns the ring just large
    enough to fit them.

    Parameters
    ----------
    numCells : int
        The number of hex cells in a hex lattice

    Returns
    -------
    numRings : int
        Number of rings required to contain numCells items.

    Notes
    -----
    The first hex ring (center) holds 1 position. Each subsequent hex ring contains 6
    more positions than the last.  This method works by incrementing ring numbers until
    the number of items is reached or exceeded. It could easily be replaced by a lookup
    table if so desired.
    """
    if numCells == 0:
        return 0
    nPinRings = int(math.ceil(0.5 * (1 + math.sqrt(1 + 4 * (numCells - 1) // 3))))

    return nPinRings


def numPositionsInRing(ring):
    """Number of positions in ring (starting at 1) of a hex lattice."""
    return (ring - 1) * 6 if ring != 1 else 1
