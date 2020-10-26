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
Utility functions to aid in removing old location objects.

The location module used to store classes and functions that were used to make sense of
where ARMI objects were in space, and relative to each other. This functionality is now
satisfied by the :py:mod:`armi.reactor.grids` module and its Grid and Location objects.

This module still exists to help satisfy some weird cases where using Grids/Locations
was not easy. This mostly has to do with the concept of ring and position, which are
difficult to reason about in the absence of a Grid instance.

This is pretty weird and nuanced. Cartesian grids need state (throughCenter) in order to
reason about ring/pos. So, for ring/pos to be part of the base Grid abstraction, we need
to assume that *any* Grid can only cough up ring/pos information through an instance
method. HexGrid is sort of the special case, in that it *could* do ring/pos stuff as a
static method (notice that it punts the actual implementation to ``hexagon.py``). There
is no similar ``rectangle.py`` to hold the concept of ring/pos for the CartesianGrid
case, and to do such a thing would be extra weird, because a ``throughCenter`` doesn't
really mean anything to a simple rectangle; the grid carries the meaning of
``throughCenter``.

So in the rare circumstances where we want to know about ring/pos from a block/assembly
that may or may not actually live in a Grid, we need to just make assumptions and grab
something. In the hex case, that something can be ``hexagon.py``, in the Cartesian
case that something are the private static methods unique to
:py:class:`armi.reactor.grids.CartesianGrid`.

Further improvements to the Block and Assembly classes (or more fundamentally with the
``ArmiObject`` class) will likely render this module useless at which point it can and
should be removed. Namely, there are plans to associate simple shape objects with each
``ArmiObject``, which would allow for knowing about the Hex/HexGrid-ness of an object
without it needing to live in a ``.spatialGrid``.

This module also retains the ``Line`` and ``Area`` classes, which at the very least
should be moved somewhere else more relevant.
"""

from armi.utils import hexagon
from armi.reactor import blocks
from armi.reactor import assemblies
from armi.reactor import grids


def numPositionsInRing(obj, ring: int) -> int:
    """
    Get the number of positions in a given ring, considering the geometry of the object.

    This is a holdover from the old locations days, and helps in situations where
    ring/pos are relevant, but an object is not guaranteed to be in a grid that can give
    that sort of information. Instead we use the object class to infer the shape of a
    grid that we would expect it to live in to determine the meaning of ring and
    position. We also assume in the Cartesian case that the center location is split,
    since this is the historical interpretation.

    This function can be removed once object get a shape member, which can be used to do
    this sort of thing more cleanly.
    """
    if isinstance(obj, (blocks.HexBlock, assemblies.HexAssembly)):
        nPos = hexagon.numPositionsInRing(ring)
        return nPos
    elif isinstance(obj, (blocks.CartesianBlock, assemblies.CartesianAssembly)):
        # allow protected access because these functions exist to be called here, but
        # are protected to prevent them being used elsewhere.
        # pylint: disable=protected-access
        nPos = grids.CartesianGrid._getPositionsInRing(ring, throughCenter=True)
        return nPos
    else:
        raise TypeError(
            "Unexpected object type `{}`. Only supporting Hex|Cartesian "
            "Block|Assembly"
        )


def minimumRings(obj, positions):
    """
    Return the number of rings needed to hold at least ``positions`` objects.

    This is a holdover from the old locations days, and helps in situations where
    ring/pos are relevant, but an object is not guaranteed to be in a grid that can give
    that sort of information. Instead we use the object class to infer the shape of a
    grid that we would expect it to live in to determine the meaning of ring and
    position. We also assume in the Cartesian case that the center location is split,
    since this is the historical interpretation.

    This function can be removed once object get a shape member, which can be used to do
    this sort of thing more cleanly.
    """
    if isinstance(obj, (blocks.HexBlock, assemblies.HexAssembly)):
        return hexagon.numRingsToHoldNumCells(positions)
    elif isinstance(obj, (blocks.CartesianBlock, assemblies.CartesianAssembly)):
        # allow protected access because these functions exist to be called here, but
        # are protected to prevent them being used elsewhere.
        # pylint: disable=protected-access
        return grids.CartesianGrid._getMinimumRingsStatic(
            positions, throughCenter=True
        )
    else:
        raise TypeError(
            "Unexpected object type `{}`. Only supporting Hex|Cartesian "
            "Block|Assembly"
        )


class Line:
    """A quadradic equation that represents a line in 2D space"""

    def __init__(self):
        self.origin = (0, 0)
        # a reference point on this line

        self.coefficients = {"c": 0, "x1": 0, "x2": 0, "y1": 0, "y2": 0}
        # polynomical coefficients that define this line

        self.cardinalDirection = "y"
        # a flag

    def sense(self, cartesian):
        """
        This method returns the 'sense' of a cartesian point (x, y) with
        respect to the line. The sense of a point is useful in establishing
        whethor or not a point is within a defined area or volume.
        Parameters
        ----------
        cartesian: tuple-like of float-like
            the first element is the x-coordinate and the second element is the y-coordinate
        Returns
        -------
        sense: float
            this can be negative (inside) positive (outside) or zero (actually on the line,
            the cartesian point satisfies the polynomial equation)
        """
        s = self.coefficients["c"]
        s += (
            self.coefficients["x1"] * cartesian[0]
            + self.coefficients["x2"] * cartesian[0] ** 2
        )
        s += (
            self.coefficients["y1"] * cartesian[1]
            + self.coefficients["y2"] * cartesian[1] ** 2
        )
        return s

    def getY(self, x=0):
        """
        This method returns the a list of y-values that satisfy the polynomial equation of
        this line by using the quadratic formula.
        Parameters
        ----------
        x: float-like
            x-coordinate
        Returns
        -------
        sense: [y1, (y2)]
            The solutions to the polynomial equation, this method returns [None]
            if there are no real intercepts and 'inf' if there are this is a
            constant value line (c=0)
        """
        if x is not None:
            a = self.coefficients["y2"]
            b = self.coefficients["y1"]
            c = (
                self.coefficients["c"]
                + self.coefficients["x2"] * x ** 2.0
                + self.coefficients["x1"] * x
            )

            return self.quadratic(a, b, c)
        else:
            return [None]

    def getX(self, y=0):
        """
        This method returns the a list of x-values that satisfy the polynomial equation of
        this line by using the quadratic formula.
        Parameters
        ----------
        y: float-like
            y-coordinate
        Returns
        -------
        sense: [x1, (x2)]
            The solutions to the polynomial equation, this method returns [None]
            if there are no real intercepts and 'inf' if there are this is a
            constant value line (c=0)
        """
        if y is not None:
            a = self.coefficients["x2"]
            b = self.coefficients["x1"]
            c = (
                self.coefficients["c"]
                + self.coefficients["y2"] * y ** 2.0
                + self.coefficients["y1"] * y
            )

            return self.quadratic(a, b, c)
        else:
            return [None]

    def quadratic(self, a, b, c):
        """
        This method solves the quadratic equation (a*x**2 + b*x + c = 0).
        Parameters
        ----------
        a, b, c : float-like
            coefficients in a quadratic equation: (a*x**2 + b*x + c = 0).
        Returns
        -------
        [x1, (x2)]: list of floats
            Solutions to the polynomial.
        """
        if a == 0 and b == 0:
            return ["inf"]
        elif a == 0 and b != 0:
            # form b*y + c = 0
            return [-c / b]
        elif (b ** 2 - 4 * a * c) > 0:
            # standard quadradic formula
            return [
                (-b + (b ** 2 - 4.0 * a * c) ** 0.5) / (2.0 * a),
                (-b - (b ** 2 - 4.0 * a * c) ** 0.5) / (2.0 * a),
            ]
        elif (b ** 2 - 4 * a * c) == 0:
            return [-b / (2.0 * a)]
        else:
            # only interested in real solutions, so toss out imaginary ones
            runLog.warning("warning no intercepts")
            return [None]

    def arcLength(self, x1=None, x2=None, n=10):

        # numerically integrate
        if self.cardinalDirection == "x":
            # transform coordinates from y-based to x-based
            dy = float(x2 - x1) / n
        else:
            dx = float(x2 - x1) / n

        s = 0

        for i in range(n):

            if self.cardinalDirection == "y":
                x = x1 + (i + 0.5) * dx
                s += (
                    dx ** 2
                    + (
                        dx
                        * (
                            -2.0 * self.coefficients["x2"] / self.coefficients["y1"] * x
                            - self.coefficients["x1"] / self.coefficients["y1"]
                        )
                    )
                    ** 2
                ) ** 0.5
            else:
                y = x1 + (i + 0.5) * dy
                s += (
                    dy ** 2
                    + (
                        dy
                        * (
                            -2.0 * self.coefficients["y2"] / self.coefficients["x1"] * y
                            - self.coefficients["y1"] / self.coefficients["x1"]
                        )
                    )
                    ** 2
                ) ** 0.5
        return s


class Area:
    def __init__(self):

        self.lines = {}

    def sense(self, cartesianTuple):

        S = -1
        for line, s in self.lines.items():
            if s * line.sense(cartesianTuple) > 0:
                S = 1
                break

        return S
