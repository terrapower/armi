# Copyright 2023 Apache License, Version 2.0 (the "License");
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

import collections
import itertools
from abc import abstractmethod
from typing import Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

from armi.reactor.grids.grid import Grid
from armi.reactor.grids.locations import (
    IJKType,
    IndexLocation,
    LocationBase,
    MultiIndexLocation,
)

# data structure for database-serialization of grids
GridParameters = collections.namedtuple(
    "GridParameters",
    ("unitSteps", "bounds", "unitStepLimits", "offset", "geomType", "symmetry"),
)


class StructuredGrid(Grid):
    """
    A connected set of cells characterized by indices mapping to space and vice versa.

    The cells may be characterized by any mixture of regular repeating steps and
    user-defined steps in any direction.

    For example, a 2-D hex lattice has constant, regular steps whereas a 3-D hex mesh
    may have user-defined axial meshes. Similar for Cartesian, RZT, etc.

    Parameters
    ----------
    unitSteps : tuple of tuples, optional
        Describes the grid spatially as a function on indices.
        Each tuple describes how each ``(x,y,or z)`` dimension is influenced by
        ``(i,j,k)``. In other words, it is::

            (dxi, dxj, jxk), (dyi, dyj, dyk), (dzi, dzj, dzk)

        where ``dmn`` is the distance (in cm) that dimension ``m`` will change as a
        function of index ``n``.

        Unit steps are used as a generic method for defining repetitive grids in a
        variety of geometries, including hexagonal and Cartesian.  The tuples are not
        vectors in the direction of the translation, but rather grouped by direction. If
        the bounds argument is described for a direction, the bounds will be used rather
        than the unit step information. The default of (0, 0, 0) makes all dimensions
        insensitive to indices since the coordinates are calculated by the dot product
        of this and the indices.  With this default, any dimension that is desired to
        change with indices should be defined with bounds. RZtheta grids are created
        exclusively with bounds.
    bounds : 3-tuple
        Absolute increasing bounds in cm including endpoints of a non-uniform grid.
        Each item represents the boundaries in the associated direction.  Use Nones when
        unitSteps should be applied instead. Most useful for thetaRZ grids or other
        non-uniform grids.
    unitStepLimits : 3-tuple
        The limit of the steps in all three directions. This constrains step-defined
        grids to be finite so we can populate them with SpatialLocator objects.
    offset : 3-tuple, optional
        Offset in cm for each axis. By default the center of the (0,0,0)-th object is in
        the center of the grid. Offsets can move it so that the (0,0,0)-th object can
        be fully within a quadrant (i.e. in a Cartesian grid).
    armiObject : ArmiObject, optional
        The ArmiObject that this grid describes. For example if it's a 1-D assembly
        grid, the armiObject is the assembly. Note that ``self.armiObject.spatialGrid``
        is ``self``.

    Examples
    --------
    A 2D a rectangular grid with width (x) 2 and height (y) 3 would be::

    >>> grid = Grid(unitSteps=((2, 0, 0), (0, 3, 0),(0, 0, 0)))

    A regular hex grid with pitch 1 is::

    >>> grid = Grid(unitSteps= ((sqrt(3)/2, 0.0, 0.0), (0.5, 1.0, 0.0), (0, 0, 0))

    .. note:: For this unit hex the magnitude of the vector constructed using the
              0th index of each tuple is 1.0.

    Notes
    -----
    Each dimension must either be defined through unitSteps or bounds.
    The combination of unitSteps with bounds was settled upon after some struggle to
    have one unified definition of a grid (i.e. just bounds). A hexagonal grid is
    somewhat challenging to represent with bounds because the axes are not orthogonal,
    so a unit-direction vector plus bounds would be required. And then the bounds would
    be wasted space because they can be derived simply by unit steps. Memory efficiency
    is important in this object so the compact representation of
    unitSteps-when-possible, bounds-otherwise was settled upon.

    Design considerations include:

    * unitSteps are more intuitive as operations starting from the center of a cell,
      particularly with hexagons and rectangles. Otherwise the 0,0 position of a hexagon
      in the center of 1/3-symmetric hexagon is at the phantom bottom left of the
      hexagon.

    * Users generally prefer to input mesh bounds rather than centers (e.g. starting at
      0.5 instead of 0.0 in a unit mesh is weird).

    * If we store bounds, computing bounds is simple and computing centers takes ~2x the
      effort. If we store centers, it's the opposite.

    * Regardless of how we store things, we'll need a Grid that has the lower-left
      assembly fully inside the problem (i.e. for full core Cartesian) as well as
      another one that has the lower-left assembly half-way or quarter-way sliced off
      (for 1/2, 1/4, and 1/8 symmetries).  The ``offset`` parameter handles this.

    * Looking up mesh boundaries (to define a mesh in another code) is generally more
      common than looking up centers (for plotting or measuring distance).

    * A grid can be anchored to the object that it is in with a backreference. This
      gives it the ability to traverse the composite tree and map local to global
      locations without having to duplicate the composite pattern on grids. This remains
      optional so grids can be used for non-reactor-package reasons.  It may seem
      slightly cleaner to set the armiObject to the parent's spatialLocator itself
      but the major disadvantage of this is that when an object moves, the armiObject
      would have to be updated. By anchoring directly to Composite objects, the parent
      is always up to date no matter where or how things get moved.

    * Unit step calculations use dot products and must not be polluted by the bound
      indices. Thus we reduce the size of the unitSteps tuple accordingly.
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
    ):
        super().__init__(geomType, symmetry, armiObject)
        # these lists contain the indices representing which dimensions for which steps
        # are used, or for which bounds are used. index 0 is x direction, etc.
        self._boundDims = []
        self._stepDims = []
        for dimensionIndex, bound in enumerate(bounds):
            if bound is None:
                self._stepDims.append(dimensionIndex)
            else:
                self._boundDims.append(dimensionIndex)

        # numpy prefers tuples like this to do slicing on arrays
        self._boundDims = (tuple(self._boundDims),)
        self._stepDims = (tuple(self._stepDims),)

        unitSteps = _tuplify(unitSteps)

        self._bounds = bounds
        self._unitStepLimits = _tuplify(unitStepLimits)

        # only represent unit steps in dimensions they're being used so as to not
        # pollute the dot product. This may reduce the length of this from 3 to 2 or 1
        self._unitSteps = np.array(unitSteps)[self._stepDims]
        self._offset = np.zeros(3) if offset is None else np.array(offset)
        self._locations = {}
        self._buildLocations()  # locations are owned by a grid, so the grid builds them.

        (_ii, iLen), (_ji, jLen), (_ki, kLen) = self.getIndexBounds()
        # True if only contains k-cells.
        self._isAxialOnly = iLen == jLen == 1 and kLen > 1

    def __len__(self) -> int:
        return len(self._locations)

    @property
    def isAxialOnly(self) -> bool:
        return self._isAxialOnly

    def reduce(self) -> GridParameters:
        """Recreate the parameter necessary to create this grid."""
        offset = None if not self._offset.any() else tuple(self._offset)

        bounds = _tuplify(self._bounds)

        # recreate a constructor-friendly version of `_unitSteps` from live data (may have been reduced from
        # length 3 to length 2 or 1 based on mixing the step-based definition and the bounds-based definition
        # described in Design Considerations above.)
        # We don't just save the original tuple passed in because that may miss transformations that
        # occur between instantiation and reduction.
        unitSteps = []
        compressedSteps = list(self._unitSteps[:])
        for i in range(3):
            # Recall _stepDims are stored as a single-value tuple (for numpy indexing)
            # So this just is grabbing the actual data.
            if i in self._stepDims[0]:
                unitSteps.append(compressedSteps.pop(0))
            else:
                # Add dummy value which will never get used (it gets reduced away)
                unitSteps.append(0)
        unitSteps = _tuplify(unitSteps)

        return GridParameters(
            unitSteps,
            bounds,
            self._unitStepLimits,
            offset,
            self._geomType,
            self._symmetry,
        )

    @property
    def offset(self) -> np.ndarray:
        """Offset in cm for each axis."""
        return self._offset

    @offset.setter
    def offset(self, offset: np.ndarray):
        self._offset = offset

    def __repr__(self) -> str:
        msg = (
            ["<{} -- {}\nBounds:\n".format(self.__class__.__name__, id(self))]
            + ["  {}\n".format(b) for b in self._bounds]
            + ["Steps:\n"]
            + ["  {}\n".format(b) for b in self._unitSteps]
            + [
                "Anchor: {}\n".format(self.armiObject),
                "Offset: {}\n".format(self._offset),
                "Num Locations: {}>".format(len(self)),
            ]
        )
        return "".join(msg)

    def __getitem__(self, ijk: Union[IJKType, List[IJKType]]) -> LocationBase:
        """
        Get a location by (i, j, k) indices. If it does not exist, create a new one and return it.

        Parameters
        ----------
        ijk : tuple of indices or list of the same
            If provided a tuple, an IndexLocation will be created (if necessary) and
            returned. If provided a list, each element will create a new IndexLocation
            (if necessary), and a MultiIndexLocation containing all of the passed
            indices will be returned.

        Notes
        -----
        The method is defaultdict-like, in that it will create a new location on the fly. However,
        the class itself is not really a dictionary, it is just index-able. For example, there is no
        desire to have a ``__setitem__`` method, because the only way to create a location is by
        retrieving it or through ``buildLocations``.
        """
        try:
            return self._locations[ijk]
        except (KeyError, TypeError):
            pass

        if isinstance(ijk, tuple):
            i, j, k = ijk
            val = IndexLocation(i, j, k, self)
            self._locations[ijk] = val
        elif isinstance(ijk, list):
            val = MultiIndexLocation(self)
            locators = [self[idx] for idx in ijk]
            val.extend(locators)
        else:
            raise TypeError(
                "Unsupported index type `{}` for `{}`".format(type(ijk), ijk)
            )
        return val

    def items(self) -> Iterable[Tuple[IJKType, IndexLocation]]:
        return self._locations.items()

    def backUp(self):
        """Gather internal info that should be restored within a retainState."""
        self._backup = self._unitSteps, self._bounds, self._offset

    def restoreBackup(self):
        self._unitSteps, self._bounds, self._offset = self._backup

    def getCoordinates(self, indices, nativeCoords=False) -> np.ndarray:
        """Return the coordinates of the center of the mesh cell at the given indices
        in cm.

        .. impl:: Get the coordinates from a location in a grid.
            :id: I_ARMI_GRID_GLOBAL_POS
            :implements: R_ARMI_GRID_GLOBAL_POS

            Probably the most common request of a structure grid will be to give the
            grid indices and return the physical coordinates of the center of the mesh
            cell. This is super handy in any situation where the coordinates have
            physical meaning.

            The math for finding the centroid turns out to be very easy, as the mesh is
            defined on the coordinates. So finding the mid-point along one axis is just
            taking the upper and lower bounds and dividing by two. And this is done for
            all axes. There are no more complicated situations where we need to find
            the centroid of a octagon on a rectangular mesh, or the like.
        """
        indices = np.array(indices)
        return self._evaluateMesh(
            indices, self._centroidBySteps, self._centroidByBounds
        )

    def getCellBase(self, indices) -> np.ndarray:
        """Get the mesh base (lower left) of this mesh cell in cm."""
        indices = np.array(indices)
        return self._evaluateMesh(
            indices, self._meshBaseBySteps, self._meshBaseByBounds
        )

    def getCellTop(self, indices) -> np.ndarray:
        """Get the mesh top (upper right) of this mesh cell in cm."""
        indices = np.array(indices) + 1
        return self._evaluateMesh(
            indices, self._meshBaseBySteps, self._meshBaseByBounds
        )

    def _evaluateMesh(self, indices, stepOperator, boundsOperator) -> np.ndarray:
        """
        Evaluate some function of indices on this grid.

        Recall from above that steps are mesh-centered and bounds are mesh-edged.

        Notes
        -----
        This method may be simplifiable. Complications arose from mixtures of bounds-
        based and step-based meshing. These were separate subclasses, but in practice
        many cases have some mix of step-based (hexagons, squares), and bounds based
        (radial, zeta).
        """
        boundCoords = []
        for ii, bounds in enumerate(self._bounds):
            if bounds is not None:
                boundCoords.append(boundsOperator(indices[ii], bounds))

        # limit step operator to the step dimensions
        stepCoords = stepOperator(np.array(indices)[self._stepDims])

        # now mix/match bounds coords with step coords appropriately.
        result = np.zeros(len(indices))
        result[self._stepDims] = stepCoords
        result[self._boundDims] = boundCoords

        return result + self._offset

    def _centroidBySteps(self, indices):
        return np.dot(self._unitSteps, indices)

    def _meshBaseBySteps(self, indices):
        return (
            self._centroidBySteps(indices - 1) + self._centroidBySteps(indices)
        ) / 2.0

    @staticmethod
    def _centroidByBounds(index, bounds):
        if index < 0:
            # avoid wrap-around
            raise IndexError("Bounds-defined indices may not be negative.")
        return (bounds[index + 1] + bounds[index]) / 2.0

    @staticmethod
    def _meshBaseByBounds(index, bounds):
        if index < 0:
            raise IndexError("Bounds-defined indices may not be negative.")
        return bounds[index]

    @staticmethod
    def getNeighboringCellIndices(i, j=0, k=0):
        """Return the indices of the immediate neighbors of a mesh point in the plane."""
        return ((i + 1, j, k), (i, j + 1, k), (i - 1, j, k), (i, j - 1, k))

    @staticmethod
    def getAboveAndBelowCellIndices(indices):
        i, j, k = indices
        return ((i, j, k + 1), (i, j, k - 1))

    def getIndexBounds(self):
        """
        Get min index and number of indices in this grid.

        Step-defined grids would be infinite but for the step limits defined in the constructor.

        Notes
        -----
        This produces output that is intended to be passed to a ``range`` statement.
        """
        indexBounds = []
        for minMax, bounds in zip(self._unitStepLimits, self._bounds):
            if bounds is None:
                indexBounds.append(minMax)
            else:
                indexBounds.append((0, len(bounds)))
        return tuple(indexBounds)

    def getBounds(
        self,
    ) -> Tuple[
        Optional[Sequence[float]], Optional[Sequence[float]], Optional[Sequence[float]]
    ]:
        """Return the grid bounds for each dimension, if present."""
        return self._bounds

    def getLocatorFromRingAndPos(self, ring, pos, k=0):
        """
        Return the location based on ring and position.

        Parameters
        ----------
        ring : int
            Ring number (1-based indexing)
        pos : int
            Position number (1-based indexing)
        k : int, optional
            Axial index (0-based indexing)

        See Also
        --------
        getIndicesFromRingAndPos
            This implements the transform into i, j indices based on ring and position.
        """
        i, j = self.getIndicesFromRingAndPos(ring, pos)
        return self[i, j, k]

    @staticmethod
    @abstractmethod
    def getIndicesFromRingAndPos(ring: int, pos: int):
        """
        Return i, j indices given ring and position.

        Note
        ----
        This should be implemented as a staticmethod, since no Grids currently in
        existence actually need any instance data to perform this task, and
        staticmethods provide the convenience of calling the method without an instance
        of the class in the first place.
        """

    @abstractmethod
    def getMinimumRings(self, n: int) -> int:
        """
        Return the minimum number of rings needed to fit ``n`` objects.

        Warning
        -------
        While this is useful and safe for answering the question of "how many rings do I
        need to hold N things?", is generally not safe to use it to answer "I have N
        things; within how many rings are they distributed?". This function provides a
        lower bound, assuming that objects are densely-packed. If they are not actually
        densely packed, this may be unphysical.
        """

    @abstractmethod
    def getPositionsInRing(self, ring: int) -> int:
        """Return the number of positions within a ring."""

    def getRingPos(self, indices) -> Tuple[int, int]:
        """
        Get ring and position number in this grid.

        For non-hex grids this is just i and j.

        A tuple is returned so that it is easy to compare pairs of indices.
        """
        # Regular grids don't know about ring and position. Check the parent.
        if (
            self.armiObject is not None
            and self.armiObject.parent is not None
            and self.armiObject.parent.spatialGrid is not None
        ):
            return self.armiObject.parent.spatialGrid.getRingPos(indices)

        raise ValueError("No ring position found, because no spatial grid was found.")

    def getAllIndices(self):
        """Get all possible indices in this grid."""
        iBounds, jBounds, kBounds = self.getIndexBounds()
        allIndices = tuple(
            itertools.product(range(*iBounds), range(*jBounds), range(*kBounds))
        )
        return allIndices

    def _buildLocations(self):
        """Populate all grid cells with a characteristic SpatialLocator."""
        for i, j, k in self.getAllIndices():
            loc = IndexLocation(i, j, k, self)
            self._locations[(i, j, k)] = loc

    @property
    @abstractmethod
    def pitch(self) -> Union[float, Tuple[float, float]]:
        """Grid pitch.

        Some implementations may rely on a single pitch, such
        as axial or hexagonal grids. Cartesian grids may use
        a single pitch between elements or separate pitches
        for the x and y dimensions.

        Returns
        -------
        float or tuple of (float, float)
            Grid spacing in cm
        """


def _tuplify(maybeArray) -> tuple:
    if isinstance(maybeArray, (np.ndarray, list, tuple)):
        maybeArray = tuple(
            tuple(row) if isinstance(row, (np.ndarray, list)) else row
            for row in maybeArray
        )

    return maybeArray
