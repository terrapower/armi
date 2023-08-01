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
r"""
This contains structured meshes in multiple geometries and spatial locators (i.e. locations).

:py:class:`Grids <Grid>` are objects that map indices (i, j, k) to spatial locations
(x,y,z) or (t,r,z).  They are useful for arranging things in reactors, such as:

* Fuel assemblies in a reactor
* Plates in a heat exchanger
* Pins in a fuel assembly
* Blocks in a fuel assembly (1-D)

Fast reactors often use a hexagonal grid, while other reactors may be better suited for
Cartesian or RZT grids. This module contains representations of all these.

``Grid``\ s can be defined by any arbitrary combination of absolute grid boundaries and
unit step directions.

Associated with grids are :py:class:`IndexLocations <IndexLocation>`. Each of these maps
to a single cell in a grid, or to an arbitrary point in the continuous space represented
by a grid. When a `Grid`` is built, it builds a collection of ``IndexLocation``\ s, one
for each cell.

In the ARMI :py:mod:`armi.reactor` module, each object is assigned a locator either from
a grid or in arbitrary, continuous space (using a :py:class:`CoordinateLocation`) on the
``spatialLocator`` attribute.

Below is a basic example of how to use a 2-D grid::

    >>> grid = CartesianGrid.fromRectangle(1.0, 1.0)  # 1 cm square-pitch Cartesian grid
    >>> location = grid[1,2,0]
    >>> location.getGlobalCoordinates()
    array([ 1.,  2.,  0.])

Grids can be chained together in a parent-child relationship. This is often used in ARMI
where a 1-D axial grid (e.g. in an assembly) is being positioned in a core or spent-fuel
pool. See example in
:py:meth:`armi.reactor.tests.test_grids.TestSpatialLocator.test_recursion`.

The "radial" (ring, position) indexing used in DIF3D can be converted to and from the
more quasi-Cartesian indexing in a hex mesh easily with the utility methods
:py:meth:`HexGrid.getRingPos` and :py:func:`indicesToRingPos`.

This module is designed to satisfy the spatial arrangement requirements of :py:mod:`the
Reactor package <armi.reactor>`.

Throughout the module, the term **global** refers to the top-level coordinate system
while the word **local** refers to within the current coordinate system defined by the
current grid.
"""
import itertools
import math
from typing import Tuple, Optional

import numpy.linalg

from armi.utils import hexagon
from armi.reactor import geometry


TAU = math.pi * 2.0


COS30 = math.sqrt(3) / 2.0
SIN30 = 1.0 / 2.0
# going CCW from "position 1" (top right)
TRIANGLES_IN_HEXAGON = numpy.array(
    [
        (+COS30, SIN30),
        (+0, 1.0),
        (-COS30, SIN30),
        (-COS30, -SIN30),
        (+0, -1.0),
        (+COS30, -SIN30),
    ]
)

from .constants import (
    BOUNDARY_CENTER,
    BOUNDARY_0_DEGREES,
    BOUNDARY_120_DEGREES,
    BOUNDARY_60_DEGREES,
)

from .locations import (
    LocationBase,
    IndexLocation,
    MultiIndexLocation,
    CoordinateLocation,
)

from .grid import Grid, GridParameters, _tuplify


class CartesianGrid(Grid):
    """
    Grid class representing a conformal Cartesian mesh.

    Notes
    -----
    In Cartesian, (i, j, k) indices map to (x, y, z) coordinates.
    In an axial plane (i, j) are as follows::

        (-1, 1) ( 0, 1) ( 1, 1)
        (-1, 0) ( 0, 0) ( 1, 0)
        (-1,-1) ( 0,-1) ( 1,-1)

    The concepts of ring and position are a bit tricker in Cartesian grids than in Hex,
    because unlike in the Hex case, there is no guaranteed center location. For example,
    when using a CartesianGrid to lay out assemblies in a core, there is only a single
    central location if the number of assemblies in the core is odd-by-odd; in an
    even-by-even case, there are four center-most assemblies. Therefore, the number of
    locations per ring will vary depending on the "through center" nature of
    ``symmetry``.

    Furthermore, notice that in the "through center" (odd-by-odd) case, the central
    index location, (0,0) is typically centered at the origin (0.0, 0.0), whereas with
    the "not through center" (even-by-even) case, the (0,0) index location is offset,
    away from the origin.

    These concepts are illustrated in the example drawings below.

    .. figure:: ../.static/through-center.png
        :width: 400px
        :align: center

        Grid example where the axes pass through the "center assembly" (odd-by-odd).
        Note that ring 1 only has one location in it.

    .. figure:: ../.static/not-through-center.png
        :width: 400px
        :align: center

        Grid example where the axes lie between the "center assemblies" (even-by-even).
        Note that ring 1 has four locations, and that the center of the (0, 0)-index
        location is offset from the origin.

    .. impl:: ARMI supports a Cartesian mesh.
       :id: IMPL_REACTOR_MESH_1
       :links: REQ_REACTOR_MESH
    """

    @classmethod
    def fromRectangle(
        cls, width, height, numRings=5, symmetry="", isOffset=False, armiObject=None
    ):
        """
        Build a finite step-based 2-D Cartesian grid based on a width and height in cm.

        Parameters
        ----------
        width : float
            Width of the unit rectangle
        height : float
            Height of the unit rectangle
        numRings : int
            Number of rings that the grid should span
        symmetry : str
            The symmetry condition (see :py:mod:`armi.reactor.geometry`)
        isOffset : bool
            If True, the origin of the Grid's coordinate system will be placed at the
            bottom-left corner of the center-most cell. Otherwise, the origin will be
            placed at the center of the center-most cell.
        armiObject : ArmiObject
            An object in a Composite model that the Grid should be bound to.
        """
        unitSteps = ((width, 0.0, 0.0), (0.0, height, 0.0), (0, 0, 0))
        offset = numpy.array((width / 2.0, height / 2.0, 0.0)) if isOffset else None
        return cls(
            unitSteps=unitSteps,
            unitStepLimits=((-numRings, numRings), (-numRings, numRings), (0, 1)),
            offset=offset,
            armiObject=armiObject,
            symmetry=symmetry,
        )

    def getRingPos(self, indices):
        """
        Return ring and position from indices.

        Ring is the Manhattan distance from (0, 0) to the passed indices. Position
        counts up around the ring counter-clockwise from the quadrant 1 diagonal, like
        this::

            7   6  5  4  3  2  1
            8         |       24
            9         |       23
            10 -------|------ 22
            11        |       21
            12        |       20
            13 14 15 16 17 18 19

        Grids that split the central locations have 1 location in in inner-most ring,
        whereas grids without split central locations will have 4.

        Notes
        -----
        This is needed to support GUI, but should not often be used.
        i, j (0-based) indices are much more useful. For example:

        >>> locator = core.spatialGrid[i, j, 0] # 3rd index is 0 for assembly
        >>> a = core.childrenByLocator[locator]

        >>> a = core.childrenByLocator[core.spatialGrid[i, j, 0]] # one liner
        """
        i, j = indices[0:2]
        split = self._isThroughCenter()

        if not split:
            i += 0.5
            j += 0.5

        ring = max(abs(int(i)), abs(int(j)))

        if not split:
            ring += 0.5

        if j == ring:
            # region 1
            pos = -i + ring
        elif i == -ring:
            # region 2
            pos = 3 * ring - j
        elif j == -ring:
            # region 3
            pos = 5 * ring + i
        else:
            # region 4
            pos = 7 * ring + j
        return (int(ring) + 1, int(pos) + 1)

    @staticmethod
    def getIndicesFromRingAndPos(ring, pos):
        """Not implemented for Cartesian-see getRingPos notes."""
        raise NotImplementedError(
            "Cartesian should not need need ring/pos, use i, j indices."
            "See getRingPos doc string notes for more information/example."
        )

    def getMinimumRings(self, n):
        """Return the minimum number of rings needed to fit ``n`` objects."""
        numPositions = 0
        ring = 0
        for ring in itertools.count(1):
            ringPositions = self.getPositionsInRing(ring)
            numPositions += ringPositions
            if numPositions >= n:
                break

        return ring

    def getPositionsInRing(self, ring):
        """
        Return the number of positions within a ring.

        Notes
        -----
        The number of positions within a ring will change
        depending on whether the central position in the
        grid is at origin, or if origin is the point
        where 4 positions meet (i.e., the ``_isThroughCenter``
        method returns True).
        """
        if ring == 1:
            ringPositions = 1 if self._isThroughCenter() else 4
        else:
            ringPositions = (ring - 1) * 8
            if not self._isThroughCenter():
                ringPositions += 4
        return ringPositions

    def locatorInDomain(self, locator, symmetryOverlap: Optional[bool] = False):
        if self.symmetry.domain == geometry.DomainType.QUARTER_CORE:
            return locator.i >= 0 and locator.j >= 0
        else:
            return True

    def changePitch(self, xw, yw):
        """
        Change the pitch of a Cartesian grid.

        This also scales the offset.
        """
        xwOld = self._unitSteps[0][0]
        ywOld = self._unitSteps[1][1]
        self._unitSteps = numpy.array(((xw, 0.0, 0.0), (0.0, yw, 0.0), (0, 0, 0)))[
            self._stepDims
        ]
        newOffsetX = self._offset[0] * xw / xwOld
        newOffsetY = self._offset[1] * yw / ywOld
        self._offset = numpy.array((newOffsetX, newOffsetY, 0.0))

    def getSymmetricEquivalents(self, indices):
        symmetry = self.symmetry  # construct the symmetry object once up top
        isRotational = symmetry.boundary == geometry.BoundaryType.PERIODIC

        i, j = indices[0:2]
        if symmetry.domain == geometry.DomainType.FULL_CORE:
            return []
        elif symmetry.domain == geometry.DomainType.QUARTER_CORE:
            if symmetry.isThroughCenterAssembly:
                # some locations lie on the symmetric boundary
                if i == 0 and j == 0:
                    # on the split corner, so the location is its own symmetric
                    # equivalent
                    return []
                elif i == 0:
                    if isRotational:
                        return [(j, i), (i, -j), (-j, i)]
                    else:
                        return [(i, -j)]
                elif j == 0:
                    if isRotational:
                        return [(j, i), (-i, j), (j, -i)]
                    else:
                        return [(-i, j)]
                else:
                    # Math is a bit easier for the split case, since there is an actual
                    # center location for (0, 0)
                    if isRotational:
                        return [(-j, i), (-i, -j), (j, -i)]
                    else:
                        return [(-i, j), (-i, -j), (i, -j)]
            else:
                # most objects have 3 equivalents. the bottom-left corner of Quadrant I
                # is (0, 0), so to reflect, add one and negate each index in
                # combination. To rotate, first flip the indices for the Quadrant II and
                # Quadrant IV
                if isRotational:
                    # rotational
                    #        QII           QIII          QIV
                    return [(-j - 1, i), (-i - 1, -j - 1), (j, -i - 1)]
                else:
                    # reflective
                    #        QII           QIII          QIV
                    return [(-i - 1, j), (-i - 1, -j - 1), (i, -j - 1)]

        elif symmetry.domain == geometry.DomainType.EIGHTH_CORE:
            raise NotImplementedError(
                "Eighth-core symmetry isn't fully implemented for grids yet!"
            )
        else:
            raise NotImplementedError(
                "Unhandled symmetry condition for {}: {}".format(
                    type(self).__name__, symmetry.domain
                )
            )

    def _isThroughCenter(self):
        """Return whether the central cells are split through the middle for symmetry."""
        return all(self._offset == [0, 0, 0])


class HexGrid(Grid):
    """
    Has 6 neighbors in plane.

    Notes
    -----
    In an axial plane (i, j) are as follows (second one is pointedEndUp)::


                    ( 0, 1)
             (-1, 1)       ( 1, 0)
                    ( 0, 0)
             (-1, 0)       ( 1,-1)
                    ( 0,-1)


                ( 0, 1) ( 1, 0)

            (-1, 1) ( 0, 0) ( 1,-1)

                (-1, 0) ( 0,-1)

    .. impl:: ARMI supports a Hexagonal mesh.
       :id: IMPL_REACTOR_MESH_2
       :links: REQ_REACTOR_MESH
    """

    @staticmethod
    def fromPitch(pitch, numRings=25, armiObject=None, pointedEndUp=False, symmetry=""):
        """
        Build a finite step-based 2-D hex grid from a hex pitch in cm.

        Parameters
        ----------
        pitch : float
            Hex pitch (flat-to-flat) in cm
        numRings : int, optional
            The number of rings in the grid to pre-populate with locatator objects.
            Even if positions are not pre-populated, locators will be generated
            there on the fly.
        armiObject : ArmiObject, optional
            The object that this grid is anchored to (i.e. the reactor for a grid of
            assemblies)
        pointedEndUp : bool, optional
            Rotate the hexagons 30 degrees so that the pointed end faces up instead of
            the flat.
        symmetry : string, optional
            A string representation of the symmetry options for the grid.

        Returns
        -------
        HexGrid
            A functional hexagonal grid object.
        """
        side = pitch / math.sqrt(3.0)
        if pointedEndUp:
            # rotated 30 degrees CCW from normal
            # increases in i move you in x and y
            # increases in j also move you in x and y
            unitSteps = (
                (pitch / 2.0, -pitch / 2.0, 0),
                (1.5 * side, 1.5 * side, 0),
                (0, 0, 0),
            )
        else:
            # x direction is only a function of i because j-axis is vertical.
            # y direction is a function of both.
            unitSteps = ((1.5 * side, 0.0, 0.0), (pitch / 2.0, pitch, 0.0), (0, 0, 0))

        return HexGrid(
            unitSteps=unitSteps,
            unitStepLimits=((-numRings, numRings), (-numRings, numRings), (0, 1)),
            armiObject=armiObject,
            symmetry=symmetry,
        )

    @property
    def pitch(self):
        """
        Get the hex-pitch of a regular hexagonal array.

        See Also
        --------
        armi.reactor.grids.HexGrid.fromPitch
        """
        return self._unitSteps[1][1]

    @staticmethod
    def indicesToRingPos(i, j):
        """
        Convert spatialLocator indices to ring/position.

        One benefit it has is that it never has negative numbers.

        Notes
        -----
        Ring, pos index system goes in counterclockwise hex rings.
        """
        if i > 0 and j >= 0:
            edge = 0
            ring = i + j + 1
            offset = j
        elif i <= 0 and j > -i:
            edge = 1
            ring = j + 1
            offset = -i
        elif i < 0 and j > 0:
            edge = 2
            ring = -i + 1
            offset = -j - i
        elif i < 0:
            edge = 3
            ring = -i - j + 1
            offset = -j
        elif i >= 0 and j < -i:
            edge = 4
            ring = -j + 1
            offset = i
        else:
            edge = 5
            ring = i + 1
            offset = i + j

        positionBase = 1 + edge * (ring - 1)
        return ring, positionBase + offset

    def getMinimumRings(self, n):
        """
        Return the minimum number of rings needed to fit ``n`` objects.

        Notes
        -----
        ``self`` is not used because hex grids always behave the same w.r.t.
        rings/positions.
        """
        return hexagon.numRingsToHoldNumCells(n)

    def getPositionsInRing(self, ring):
        """Return the number of positions within a ring."""
        return hexagon.numPositionsInRing(ring)

    def getNeighboringCellIndices(self, i, j=0, k=0):
        """
        Return the indices of the immediate neighbors of a mesh point in the plane.

        Note that these neighbors are ordered counter-clockwise beginning from the
        30 or 60 degree direction. Exact direction is dependent on pointedEndUp arg.
        """
        return [
            (i + 1, j, k),
            (i, j + 1, k),
            (i - 1, j + 1, k),
            (i - 1, j, k),
            (i, j - 1, k),
            (i + 1, j - 1, k),
        ]

    def getLabel(self, indices):
        """
        Hex labels start at 1, and are ring/position based rather than i,j.

        This difference is partially because ring/pos is easier to understand in hex
        geometry, and partially because it is used in some codes ARMI originally was focused
        on.
        """
        ring, pos = self.getRingPos(indices)
        if len(indices) == 2:
            return Grid.getLabel(self, (ring, pos))
        else:
            return Grid.getLabel(self, (ring, pos, indices[2]))

    @staticmethod
    def _indicesAndEdgeFromRingAndPos(ring, position):
        ring = ring - 1
        pos = position - 1

        if ring == 0:
            if pos != 0:
                raise ValueError(f"Position in center ring must be 1, not {position}")
            return 0, 0, 0

        # Edge indicates which edge of the ring in which the hexagon resides.
        # Edge 0 is the NE edge, edge 1 is the N edge, etc.
        # Offset is (0-based) index of the hexagon in that edge. For instance,
        # ring 3, pos 12 resides in edge 5 at index 1; it is the second hexagon
        # in ring 3, edge 5.
        edge, offset = divmod(pos, ring)  # = pos//ring, pos%ring
        if edge == 0:
            i = ring - offset
            j = offset
        elif edge == 1:
            i = -offset
            j = ring
        elif edge == 2:
            i = -ring
            j = -offset + ring
        elif edge == 3:
            i = -ring + offset
            j = -offset
        elif edge == 4:
            i = offset
            j = -ring
        elif edge == 5:
            i = ring
            j = offset - ring
        else:
            raise ValueError(
                "Edge {} is invalid. From ring {}, pos {}".format(edge, ring, pos)
            )
        return i, j, edge

    @staticmethod
    def getIndicesFromRingAndPos(ring, pos):
        i, j, _edge = HexGrid._indicesAndEdgeFromRingAndPos(ring, pos)
        return i, j

    def getRingPos(self, indices):
        """
        Get 1-based ring and position from normal indices.

        See Also
        --------
        getIndicesFromRingAndPos : does the reverse
        """
        i, j = indices[:2]
        return HexGrid.indicesToRingPos(i, j)

    def overlapsWhichSymmetryLine(self, indices):
        """Return a list of which lines of symmetry this is on.

        If none, returns []
        If on a line of symmetry in 1/6 geometry, returns a list containing a 6.
        If on a line of symmetry in 1/3 geometry, returns a list containing a 3.
        Only the 1/3 core view geometry is actually coded in here right now.

        Being "on" a symmetry line means the line goes through the middle of you.

        """
        i, j = indices[:2]

        if i == 0 and j == 0:
            symmetryLine = BOUNDARY_CENTER
        elif i > 0 and i == -2 * j:
            # edge 1: 1/3 symmetry line (bottom horizontal side in 1/3 core view, theta = 0)
            symmetryLine = BOUNDARY_0_DEGREES
        elif i == j and i > 0 and j > 0:
            # edge 2: 1/6 symmetry line (bisects 1/3 core view, theta = pi/3)
            symmetryLine = BOUNDARY_60_DEGREES
        elif j == -2 * i and j > 0:
            # edge 3: 1/3 symmetry line (left oblique side in 1/3 core view, theta = 2*pi/3)
            symmetryLine = BOUNDARY_120_DEGREES
        else:
            symmetryLine = None

        return symmetryLine

    def getSymmetricEquivalents(self, indices):
        if (
            self.symmetry.domain == geometry.DomainType.THIRD_CORE
            and self.symmetry.boundary == geometry.BoundaryType.PERIODIC
        ):
            return HexGrid._getSymmetricIdenticalsThird(indices)
        elif self.symmetry.domain == geometry.DomainType.FULL_CORE:
            return []
        else:
            raise NotImplementedError(
                "Unhandled symmetry condition for HexGrid: {}".format(
                    str(self.symmetry)
                )
            )

    @staticmethod
    def _getSymmetricIdenticalsThird(indices):
        """This works by rotating the indices by 120 degrees twice, counterclockwise."""
        i, j = indices[:2]
        if i == 0 and j == 0:
            return []
        identicals = [(-i - j, i), (j, -i - j)]
        return identicals

    def triangleCoords(self, indices):
        """
        Return 6 coordinate pairs representing the centers of the 6 triangles in a hexagon centered here.

        Ignores z-coordinate and only operates in 2D for now.
        """
        xy = self.getCoordinates(indices)[:2]
        scale = self.pitch / 3.0
        return xy + scale * TRIANGLES_IN_HEXAGON

    def changePitch(self, newPitchCm):
        """Change the hex pitch."""
        side = newPitchCm / math.sqrt(3.0)
        self._unitSteps = numpy.array(
            ((1.5 * side, 0.0, 0.0), (newPitchCm / 2.0, newPitchCm, 0.0), (0, 0, 0))
        )[self._stepDims]

    def locatorInDomain(self, locator, symmetryOverlap: Optional[bool] = False):
        # This will include the "top" 120-degree symmetry lines. This is to support
        # adding of edge assemblies.
        if self.symmetry.domain == geometry.DomainType.THIRD_CORE:
            return self.isInFirstThird(locator, includeTopEdge=symmetryOverlap)
        else:
            return True

    def isInFirstThird(self, locator, includeTopEdge=False):
        """True if locator is in first third of hex grid."""
        ring, pos = self.getRingPos(locator.indices)
        if ring == 1:
            return True
        maxPosTotal = self.getPositionsInRing(ring)

        maxPos1 = ring + ring // 2 - 1
        maxPos2 = maxPosTotal - ring // 2 + 1
        if ring % 2:
            # odd ring. Upper edge assem typically not included.
            if includeTopEdge:
                maxPos1 += 1
        else:
            maxPos2 += 1  # make a table to understand this.
        if pos <= maxPos1 or pos >= maxPos2:
            return True
        return False

    def generateSortedHexLocationList(self, nLocs):
        """
        Generate a list IndexLocations, sorted based on their distance from the center.

        IndexLocation are taken from a full core.

        Ties between locations with the same distance (e.g. A3001 and A3003) are broken
        by ring number then position number.
        """
        # first, roughly calculate how many rings need to be created to cover nLocs worth of assemblies
        nLocs = int(nLocs)  # need to make this an integer

        # next, generate a list of locations and corresponding distances
        locs = []
        for ring in range(1, hexagon.numRingsToHoldNumCells(nLocs) + 1):
            positions = self.getPositionsInRing(ring)
            for position in range(1, positions + 1):
                i, j = self.getIndicesFromRingAndPos(ring, position)
                locs.append(self[(i, j, 0)])
        # round to avoid differences due to floating point math
        locs.sort(
            key=lambda loc: (
                round(numpy.linalg.norm(loc.getGlobalCoordinates()), 6),
                loc.i,  # loc.i=ring
                loc.j,
            )
        )  # loc.j= pos
        return locs[:nLocs]

    # TODO: this is only used by testing and another method that just needs the count of assemblies
    #       in a ring, not the actual positions
    def allPositionsInThird(self, ring, includeEdgeAssems=False):
        """
        Returns a list of all the positions in a ring (in the first third).

        Parameters
        ----------
        ring : int
            The ring to check
        includeEdgeAssems : bool, optional
            If True, include repeated positions in odd ring numbers. Default: False

        Notes
        -----
        Rings start at 1, positions start at 1

        Returns
        -------
        positions : int
        """
        positions = []
        for pos in range(1, self.getPositionsInRing(ring) + 1):
            i, j = self.getIndicesFromRingAndPos(ring, pos)
            loc = IndexLocation(i, j, 0, None)
            if self.isInFirstThird(loc, includeEdgeAssems):
                positions.append(pos)
        return positions


class ThetaRZGrid(Grid):
    """
    A grid characterized by azimuthal, radial, and zeta indices.

    The angular meshes are limited to 0 to 2pi radians. R and Zeta are as in other
    meshes.

    See Figure 2.2 in Derstine 1984, ANL. [DIF3D]_.

    .. impl:: ARMI supports an RZTheta mesh.
       :id: IMPL_REACTOR_MESH_3
       :links: REQ_REACTOR_MESH
    """

    @staticmethod
    def fromGeom(geom, armiObject=None):
        """
        Build 2-D R-theta grid based on a Geometry object.

        Parameters
        ----------
        geomInfo : list
            list of ((indices), assemName) tuples for all positions in core with input
            in radians

        See Also
        --------
        armi.reactor.systemLayoutInput.SystemLayoutInput.readGeomXML : produces the geomInfo
        structure

        Examples
        --------
        >>> grid = grids.ThetaRZGrid.fromGeom(geomInfo)
        """
        allIndices = [
            indices for indices, _assemName in geom.assemTypeByIndices.items()
        ]

        # create ordered lists of all unique theta and R points
        thetas, radii = set(), set()
        for rad1, rad2, theta1, theta2, _numAzi, _numRadial in allIndices:
            radii.add(rad1)
            radii.add(rad2)
            thetas.add(theta1)
            thetas.add(theta2)
        radii = numpy.array(sorted(radii), dtype=numpy.float64)
        thetaRadians = numpy.array(sorted(thetas), dtype=numpy.float64)

        return ThetaRZGrid(
            bounds=(thetaRadians, radii, (0.0, 0.0)), armiObject=armiObject
        )

    def getRingPos(self, indices):
        return (indices[1] + 1, indices[0] + 1)

    @staticmethod
    def getIndicesFromRingAndPos(ring, pos):
        return (pos - 1, ring - 1)

    def getCoordinates(self, indices, nativeCoords=False):
        meshCoords = theta, r, z = Grid.getCoordinates(self, indices)
        if not 0 <= theta <= TAU:
            raise ValueError("Invalid theta value: {}. Check mesh.".format(theta))
        if nativeCoords:
            # return Theta, R, Z values directly.
            return meshCoords
        else:
            # return x, y ,z
            return numpy.array((r * math.cos(theta), r * math.sin(theta), z))

    def indicesOfBounds(self, rad0, rad1, theta0, theta1, sigma=1e-4):
        """
        Return indices corresponding to upper and lower radial and theta bounds.

        Parameters
        ----------
        rad0 : float
            inner radius of control volume
        rad1 : float
            outer radius of control volume
        theta0 : float
            inner azimuthal location of control volume in radians
        theta1 : float
            inner azimuthal of control volume in radians
        sigma: float
            acceptable relative error (i.e. if one of the positions in the mesh are within
            this error it'll act the same if it matches a position in the mesh)

        Returns
        -------
        tuple : i, j, k of given bounds
        """
        i = int(numpy.abs(self._bounds[0] - theta0).argmin())
        j = int(numpy.abs(self._bounds[1] - rad0).argmin())

        return (i, j, 0)

    def locatorInDomain(self, locator, symmetryOverlap: Optional[bool] = False):
        """
        ThetaRZGrids do not check for bounds, though they could if that becomes a
        problem.
        """
        return True


def axialUnitGrid(numCells, armiObject=None):
    """
    Build a 1-D unit grid in the k-direction based on a number of times. Each mesh is 1cm wide.

    numCells + 1 mesh boundaries are added, since one block would require a bottom and a
    top.
    """
    # need float bounds or else we truncate integers
    return Grid(
        bounds=(None, None, numpy.arange(numCells + 1, dtype=numpy.float64)),
        armiObject=armiObject,
    )


def locatorLabelToIndices(label: str) -> Tuple[int, int, Optional[int]]:
    """
    Convert a locator label to numerical i,j,k indices.

    If there are only i,j  indices, make the last item None
    """
    intVals = tuple(int(idx) for idx in label.split("-"))
    if len(intVals) == 2:
        intVals = (intVals[0], intVals[1], None)
    return intVals


def addingIsValid(myGrid, parentGrid):
    """
    True if adding a indices from one grid to another is considered valid.

    In ARMI we allow the addition of a 1-D axial grid with a 2-D grid.
    We do not allow any other kind of adding. This enables the 2D/1D
    grid layout in Assemblies/Blocks but does not allow 2D indexing
    in pins to become inconsistent.
    """
    return myGrid.isAxialOnly and not parentGrid.isAxialOnly
