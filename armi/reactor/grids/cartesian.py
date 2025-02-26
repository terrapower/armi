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
import itertools
from typing import NoReturn, Optional, Tuple

import numpy as np

from armi.reactor import geometry
from armi.reactor.grids.locations import IJType
from armi.reactor.grids.structuredGrid import StructuredGrid


class CartesianGrid(StructuredGrid):
    """
    Grid class representing a conformal Cartesian mesh.

    It is recommended to call :meth:`fromRectangle` to construct,
    rather than directly constructing with ``__init__``

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
    """

    @classmethod
    def fromRectangle(cls, width, height, numRings=5, symmetry="", isOffset=False, armiObject=None):
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
        offset = np.array((width / 2.0, height / 2.0, 0.0)) if isOffset else None
        return cls(
            unitSteps=unitSteps,
            unitStepLimits=((-numRings, numRings), (-numRings, numRings), (0, 1)),
            offset=offset,
            armiObject=armiObject,
            symmetry=symmetry,
        )

    def overlapsWhichSymmetryLine(self, indices: IJType) -> None:
        """Return lines of symmetry position at a given index can be found.

        .. warning::

            This is not really implemented, but parts of ARMI need it to
            not fail, so it always returns None.

        """
        return None

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
    def getIndicesFromRingAndPos(ring: int, pos: int) -> NoReturn:
        """Not implemented for Cartesian-see getRingPos notes."""
        raise NotImplementedError(
            "Cartesian should not need need ring/pos, use i, j indices."
            "See getRingPos doc string notes for more information/example."
        )

    def getMinimumRings(self, n: int) -> int:
        """Return the minimum number of rings needed to fit ``n`` objects."""
        numPositions = 0
        ring = 0
        for ring in itertools.count(1):
            ringPositions = self.getPositionsInRing(ring)
            numPositions += ringPositions
            if numPositions >= n:
                break

        return ring

    def getPositionsInRing(self, ring: int) -> int:
        """
        Return the number of positions within a ring.

        Parameters
        ----------
        ring : int
            Ring in question

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

    def changePitch(self, xw: float, yw: float):
        """
        Change the pitch of a Cartesian grid.

        This also scales the offset.
        """
        xwOld = self._unitSteps[0][0]
        ywOld = self._unitSteps[1][1]
        self._unitSteps = np.array(((xw, 0.0, 0.0), (0.0, yw, 0.0), (0, 0, 0)))[self._stepDims]
        newOffsetX = self._offset[0] * xw / xwOld
        newOffsetY = self._offset[1] * yw / ywOld
        self._offset = np.array((newOffsetX, newOffsetY, 0.0))

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
            raise NotImplementedError("Eighth-core symmetry isn't fully implemented for grids yet!")
        else:
            raise NotImplementedError(
                "Unhandled symmetry condition for {}: {}".format(type(self).__name__, symmetry.domain)
            )

    def _isThroughCenter(self):
        """Return whether the central cells are split through the middle for symmetry."""
        return all(self._offset == [0, 0, 0])

    @property
    def pitch(self) -> Tuple[float, float]:
        """Grid pitch in the x and y dimension.

        Returns
        -------
        float
            x-pitch (cm)
        float
            y-pitch (cm)

        """
        pitch = (self._unitSteps[0][0], self._unitSteps[1][1])
        if pitch[0] == 0:
            raise ValueError(f"Grid {self} does not have a defined pitch.")
        return pitch
