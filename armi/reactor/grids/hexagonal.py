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
import math
from typing import Optional

import numpy

from armi.utils import hexagon
from armi.reactor import geometry

from .constants import (
    BOUNDARY_0_DEGREES,
    BOUNDARY_120_DEGREES,
    BOUNDARY_60_DEGREES,
    BOUNDARY_CENTER,
)
from .locations import IndexLocation
from .grid import Grid

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
