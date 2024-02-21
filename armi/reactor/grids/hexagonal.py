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
from math import sqrt
from typing import Tuple, List, Optional

import numpy

from armi.reactor import geometry
from armi.utils import hexagon

from armi.reactor.grids.constants import (
    BOUNDARY_0_DEGREES,
    BOUNDARY_120_DEGREES,
    BOUNDARY_60_DEGREES,
    BOUNDARY_CENTER,
)
from armi.reactor.grids.locations import IndexLocation, IJKType, IJType
from armi.reactor.grids.structuredgrid import StructuredGrid

COS30 = sqrt(3) / 2.0
SIN30 = 1.0 / 2.0
# going counter-clockwise from "position 1" (top right)
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


class HexGrid(StructuredGrid):
    """
    Has 6 neighbors in plane.

    It is recommended to use :meth:`fromPitch` rather than calling the ``__init__``
    constructor directly.

    .. impl:: Construct a hexagonal lattice.
        :id: I_ARMI_GRID_HEX
        :implements: R_ARMI_GRID_HEX

        This class represents a hexagonal ``StructuredGrid``, that is one where the
        mesh maps to real, physical coordinates. This hexagonal grid is 2D, and divides
        the plane up into regular hexagons. That is, each hexagon is symmetric and
        is precisely flush with six neighboring hexagons. This class only allows for
        two rotational options: flats up (where two sides of the hexagons are parallel
        with the X-axis), and points up (where two sides are parallel with the Y-axis).

    Notes
    -----
    In an axial plane (i, j) are as follows (second one is cornersUp)::

                    ( 0, 1)
             (-1, 1)       ( 1, 0)
                    ( 0, 0)
             (-1, 0)       ( 1,-1)
                    ( 0,-1)

                ( 0, 1) ( 1, 0)
            (-1, 1) ( 0, 0) ( 1,-1)
                (-1, 0) ( 0,-1)

    Basic hexagon geometry::

    - pitch = sqrt(3) * side
    - long diagonal = 2 * side
    - Area = (sqrt(3) / 4) * side^2
    - perimeter = 6 * side

    """

    def __init__(
        self,
        unitSteps=(0, 0, 0),
        bounds=(None, None, None),
        unitStepLimits=((0, 1), (0, 1), (0, 1)),
        offset=None,
        geomType="",
        symmetry="",
        armiObject=None,
        cornersUp=False,
    ):
        super().__init__(
            unitSteps, bounds, unitStepLimits, offset, geomType, symmetry, armiObject
        )

    @property
    def cornersUp(self) -> bool:
        """
        Check whether the hexagonal grid is "corners up" or "flats up".

        See the armi.reactor.grids.HexGrid class documentation for an
        illustration of the two types of grid indexing.
        """
        return self._unitSteps[0][1] != 0.0

    @staticmethod
    def fromPitch(pitch, numRings=25, armiObject=None, cornersUp=False, symmetry=""):
        """
        Build a finite step-based 2-D hex grid from a hex pitch in cm.

        .. impl:: Hexagonal grids can be points-up or flats-up.
            :id: I_ARMI_GRID_HEX_TYPE
            :implements: R_ARMI_GRID_HEX_TYPE

            When this method creates a ``HexGrid`` object, it can create a hexagonal
            grid with one of two rotations: flats up (where two sides of the hexagons
            are parallel with the X-axis), and points up (where two sides are parallel
            with the Y-axis). While it is possible to imagine the hexagons being
            rotated at other arbitrary angles, those are not supported here.

        .. impl:: When creating a hexagonal grid, the user can specify the symmetry.
            :id: I_ARMI_GRID_SYMMETRY1
            :implements: R_ARMI_GRID_SYMMETRY

            When this method creates a ``HexGrid`` object, it takes as an input the
            symmetry of the resultant grid. This symmetry can be a string (e.g. "full")
            or a ``SymmetryType`` object (e.g. ``FULL_CORE``). If the grid is not full-
            core, the method ``getSymmetricEquivalents()`` will be usable to map any
            possible grid cell to the ones that are being modeled in the sub-grid.

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
        cornersUp : bool, optional
            Rotate the hexagons 30 degrees so that the corners point up instead of
            the flat faces.
        symmetry : string, optional
            A string representation of the symmetry options for the grid.

        Returns
        -------
        HexGrid
            A functional hexagonal grid object.
        """
        unitSteps = HexGrid.getRawUnitSteps(pitch, cornersUp)

        hex = HexGrid(
            unitSteps=unitSteps,
            unitStepLimits=((-numRings, numRings), (-numRings, numRings), (0, 1)),
            armiObject=armiObject,
            symmetry=symmetry,
            cornersUp=cornersUp,
        )
        return hex

    @property
    def pitch(self) -> float:
        """
        Get the hex-pitch of a regular hexagonal array.

        See Also
        --------
        armi.reactor.grids.HexGrid.fromPitch
        """
        return self._unitSteps[1][1]

    @staticmethod
    def indicesToRingPos(i: int, j: int) -> Tuple[int, int]:
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

    def getMinimumRings(self, n: int) -> int:
        """
        Return the minimum number of rings needed to fit ``n`` objects.

        Notes
        -----
        ``self`` is not used because hex grids always behave the same w.r.t.
        rings/positions.
        """
        return hexagon.numRingsToHoldNumCells(n)

    def getPositionsInRing(self, ring: int) -> int:
        """Return the number of positions within a ring."""
        return hexagon.numPositionsInRing(ring)

    def getNeighboringCellIndices(
        self, i: int, j: int = 0, k: int = 0
    ) -> List[IJKType]:
        """
        Return the indices of the immediate neighbors of a mesh point in the plane.

        Note that these neighbors are ordered counter-clockwise beginning from the
        30 or 60 degree direction. Exact direction is dependent on cornersUp arg.
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
            return super().getLabel((ring, pos))
        else:
            return super().getLabel((ring, pos, indices[2]))

    @staticmethod
    def _indicesAndEdgeFromRingAndPos(ring, position):
        """Given the ring and position, return the (I,J) coordinates, and which edge the grid
        cell is on.

        Parameters
        ----------
        ring : int
            Starting with 1 (not zero), the ring of the grid cell.
        position : int
            Starting with 1 (not zero), the position of the grid cell, in the ring.

        Returns
        -------
        (int, int, int) : I coordinate, J coordinate, which edge of the hex ring

        Notes
        -----
        - Edge indicates which edge of the ring in which the hexagon resides.
        - Edge 0 is the NE edge, edge 1 is the N edge, etc.
        - Offset is (0-based) index of the hexagon in that edge. For instance,
          ring 3, pos 12 resides in edge 5 at index 1; it is the second hexagon
          in ring 3, edge 5.
        """
        # The inputs start counting at 1, but the grid starts counting at zero.
        ring = ring - 1
        pos = position - 1

        # Handle the center grid cell.
        if ring == 0:
            if pos != 0:
                raise ValueError(f"Position in center ring must be 1, not {position}")
            return 0, 0, 0

        # find the edge and offset (pos//ring or pos%ring)
        edge, offset = divmod(pos, ring)

        # find (I,J) based on the ring, edge, and offset
        if edge == 0:
            i = ring - offset
            j = offset
        elif edge == 1:
            i = -offset
            j = ring
        elif edge == 2:
            i = -ring
            j = ring - offset
        elif edge == 3:
            i = offset - ring
            j = -offset
        elif edge == 4:
            i = offset
            j = -ring
        elif edge == 5:
            i = ring
            j = offset - ring
        else:
            raise ValueError(f"Edge {edge} is invalid. From ring {ring}, pos {pos}")

        return i, j, edge

    @staticmethod
    def getIndicesFromRingAndPos(ring: int, pos: int) -> IJType:
        """Given the ring and position, return the (I,J) coordinates in the hex grid.

        Parameters
        ----------
        ring : int
            Starting with 1 (not zero), the ring of the grid cell.
        position : int
            Starting with 1 (not zero), the position of the grid cell, in the ring.

        Returns
        -------
        (int, int) : I coordinate, J coordinate
        """
        i, j, _edge = HexGrid._indicesAndEdgeFromRingAndPos(ring, pos)
        return i, j

    def getRingPos(self, indices: IJKType) -> Tuple[int, int]:
        """
        Get 1-based ring and position from normal indices.

        See Also
        --------
        getIndicesFromRingAndPos : does the reverse
        """
        i, j = indices[:2]
        return self.indicesToRingPos(i, j)

    def overlapsWhichSymmetryLine(self, indices: IJType) -> Optional[int]:
        """Return a list of which lines of symmetry this is on.

        Parameters
        ----------
        indices : tuple of [int, int]
            Indices for the requested object

        Returns
        -------
        None or int
            None if not line of symmetry goes through the object at the
            requested index. Otherwise, some grid constants like ``BOUNDARY_CENTER``
            will be returned.

        Notes
        -----
        - Only the 1/3 core view geometry is actually coded in here right now.
        - Being "on" a symmetry line means the line goes through the middle of you.
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

    def getSymmetricEquivalents(self, indices: IJKType) -> List[IJType]:
        """Retrieve the equivalent indices. If full core return nothing, if 1/3-core grid,
        return the symmetric equivalents, if any other grid, raise an error.

        .. impl:: Equivalent contents in 1/3-core geometries are retrievable.
            :id: I_ARMI_GRID_EQUIVALENTS
            :implements: R_ARMI_GRID_EQUIVALENTS

            This method takes in (I,J,K) indices, and if this ``HexGrid`` is full core,
            it returns nothing. If this ``HexGrid`` is 1/3-core, this method will return
            the 1/3-core symmetric equivalent of just (I,J). If this grid is any other kind,
            this method will just return an error; a hexagonal grid with any other
            symmetry is probably an error.
        """
        if (
            self.symmetry.domain == geometry.DomainType.THIRD_CORE
            and self.symmetry.boundary == geometry.BoundaryType.PERIODIC
        ):
            return self._getSymmetricIdenticalsThird(indices)
        elif self.symmetry.domain == geometry.DomainType.FULL_CORE:
            return []
        else:
            raise NotImplementedError(
                "Unhandled symmetry condition for HexGrid: {}".format(
                    str(self.symmetry)
                )
            )

    @staticmethod
    def _getSymmetricIdenticalsThird(indices) -> List[IJType]:
        """This works by rotating the indices by 120 degrees twice, counterclockwise."""
        i, j = indices[:2]
        if i == 0 and j == 0:
            return []
        identicals = [(-i - j, i), (j, -i - j)]
        return identicals

    def triangleCoords(self, indices: IJKType) -> numpy.ndarray:
        """
        Return 6 coordinate pairs representing the centers of the 6 triangles in a
        hexagon centered here.

        Ignores z-coordinate and only operates in 2D for now.
        """
        xy = self.getCoordinates(indices)[:2]
        scale = self.pitch / 3.0
        return xy + scale * TRIANGLES_IN_HEXAGON

    @staticmethod
    def getRawUnitSteps(pitch, cornersUp=False):
        """Get the raw unit steps (ignore step dimensions), for a hex grid.

        Parameters
        ----------
        pitch : float
            The short diameter of the hexagons (from flat side to flat side).
        cornersUp : bool, optional
            If True, the hexagons have a corner pointing in the Y direction. Default: False

        Returns
        -------
        tuple : The full 3D set of derivatives of X,Y,Z in terms of i,j,k.
        """
        side = hexagon.side(pitch)
        if cornersUp:
            # rotated 30 degrees counter-clockwise from normal
            # increases in i moves you in x and y
            # increases in j also moves you in x and y
            unitSteps = (
                (pitch / 2.0, -pitch / 2.0, 0),
                (1.5 * side, 1.5 * side, 0),
                (0, 0, 0),
            )
        else:
            # x direction is only a function of i because j-axis is vertical.
            # y direction is a function of both.
            unitSteps = ((1.5 * side, 0.0, 0.0), (pitch / 2.0, pitch, 0.0), (0, 0, 0))

        return unitSteps

    def changePitch(self, newPitchCm: float):
        """Change the hex pitch."""
        unitSteps = numpy.array(HexGrid.getRawUnitSteps(newPitchCm, self.cornersUp))
        self._unitSteps = unitSteps[self._stepDims]

    def locatorInDomain(self, locator, symmetryOverlap: Optional[bool] = False) -> bool:
        # This will include the "top" 120-degree symmetry lines. This is to support
        # adding of edge assemblies.
        if self.symmetry.domain == geometry.DomainType.THIRD_CORE:
            return self.isInFirstThird(locator, includeTopEdge=symmetryOverlap)
        else:
            return True

    def isInFirstThird(self, locator, includeTopEdge=False) -> bool:
        """Test if the given locator is in the first 1/3 of the HexGrid.

        .. impl:: Determine if grid is in first third.
            :id: I_ARMI_GRID_SYMMETRY_LOC
            :implements: R_ARMI_GRID_SYMMETRY_LOC

            This is a simple helper method to determine if a given locator (from an
            ArmiObject) is in the first 1/3 of the ``HexGrid``. This method does not
            attempt to check if this grid is full or 1/3-core. It just does the basic
            math of dividing up a hex-assembly reactor core into thirds and testing if
            the given location is in the first 1/3 or not.
        """
        ring, pos = self.getRingPos(locator.indices)
        if ring == 1:
            return True

        maxPosTotal = self.getPositionsInRing(ring)

        maxPos1 = ring + ring // 2 - 1
        maxPos2 = maxPosTotal - ring // 2 + 1
        if ring % 2:
            # Odd ring; upper edge assem typically not included.
            if includeTopEdge:
                maxPos1 += 1
        else:
            # Even ring; upper edge assem included.
            maxPos2 += 1

        if pos <= maxPos1 or pos >= maxPos2:
            return True

        return False

    def generateSortedHexLocationList(self, nLocs: int):
        """
        Generate a list IndexLocations, sorted based on their distance from the center.

        IndexLocation are taken from a full core.

        Ties between locations with the same distance (e.g. A3001 and A3003) are broken
        by ring number then position number.
        """
        # first, roughly calculate how many rings need to be created to cover nLocs worth of assemblies
        nLocs = int(nLocs)

        # next, generate a list of locations and corresponding distances
        locList = []
        for ring in range(1, hexagon.numRingsToHoldNumCells(nLocs) + 1):
            positions = self.getPositionsInRing(ring)
            for position in range(1, positions + 1):
                i, j = self.getIndicesFromRingAndPos(ring, position)
                locList.append(self[(i, j, 0)])

        # round to avoid differences due to floating point math
        locList.sort(
            key=lambda loc: (
                round(numpy.linalg.norm(loc.getGlobalCoordinates()), 6),
                loc.i,
                loc.j,
            )
        )

        return locList[:nLocs]

    # TODO: This is only used by the old GUI code, and should be moved there.
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
