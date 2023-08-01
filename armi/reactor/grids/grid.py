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
import collections
from typing import Optional, List, Sequence, Union, Tuple

import numpy

from armi.reactor import geometry

from .locations import IndexLocation, LocationBase, MultiIndexLocation

# data structure for database-serialization of grids
GridParameters = collections.namedtuple(
    "GridParameters",
    ("unitSteps", "bounds", "unitStepLimits", "offset", "geomType", "symmetry"),
)


class Grid:
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
        than the unit step information.  The default of (0, 0, 0) makes all dimensions
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
        the center of the grid.  Offsets can move it so that the (0,0,0)-th object can
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

    .. impl:: ARMI supports a number of structured mesh options.
       :id: IMPL_REACTOR_MESH_0
       :links: REQ_REACTOR_MESH
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
        self._unitSteps = numpy.array(unitSteps)[self._stepDims]
        self._offset = numpy.zeros(3) if offset is None else numpy.array(offset)

        self._locations = {}  # indices -> SpatialLocator map
        self.armiObject = armiObject
        self.buildLocations()  # locations are owned by a grid, so the grid builds them.
        self._backup = None  # for retainState

        (_ii, iLen), (_ji, jLen), (_ki, kLen) = self.getIndexBounds()
        # True if only contains k-cells.
        self.isAxialOnly = iLen == jLen == 1 and kLen > 1

        # geometric metadata encapsulated here because it's related to the grid.
        # They do not impact the grid object itself.
        # Notice that these are stored using their string representations, rather than
        # the GridType enum. This avoids the danger of deserializing an enum value from
        # an old version of the code that may have had different numeric values.
        self._geomType: str = str(geomType)
        self._symmetry: str = str(symmetry)

    def reduce(self):
        """
        Return the set of arguments used to create this Grid.

        This is very much like the argument tuple from ``__reduce__``, but we do not
        implement ``__reduce__`` for real, because we are generally happy with
        ``__getstate__`` and ``__setstate__`` for pickling purposes. However, getting
        these arguments to ``__init__`` is useful for storing Grids to the database, as
        they are more stable (less likely to change) than the actual internal state of
        the objects.

        The return value should be hashable, such that a set of these can be created.
        """
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
    def geomType(self) -> geometry.GeomType:
        return geometry.GeomType.fromStr(self._geomType)

    @geomType.setter
    def geomType(self, geomType: Union[str, geometry.GeomType]):
        self._geomType = str(geometry.GeomType.fromAny(geomType))

    @property
    def symmetry(self) -> geometry.SymmetryType:
        return geometry.SymmetryType.fromStr(self._symmetry)

    @symmetry.setter
    def symmetry(self, symmetry: Union[str, geometry.SymmetryType]):
        self._symmetry = str(geometry.SymmetryType.fromAny(symmetry))

    @property
    def offset(self):
        return self._offset

    @offset.setter
    def offset(self, offset):
        self._offset = offset

    def __repr__(self):
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

    def __getstate__(self):
        """
        Pickling removes reference to ``armiObject``.

        Removing the ``armiObject`` allows us to pickle an assembly without pickling the entire
        reactor. An ``Assembly.spatialLocator.grid.armiObject`` is the reactor, by removing the link
        here, we still have spatial orientation, but are not required to pickle the entire reactor
        to pickle an assembly.

        This relies on the ``armiObject.__setstate__`` to assign itself.
        """
        state = self.__dict__.copy()
        state["armiObject"] = None

        return state

    def __setstate__(self, state):
        """
        Pickling removes reference to ``armiObject``.

        This relies on the ``ArmiObject.__setstate__`` to assign itself.
        """
        self.__dict__.update(state)

        for _indices, locator in self.items():
            locator._grid = self

    def __getitem__(self, ijk: Union[Tuple[int, int, int], List[Tuple[int, int, int]]]):
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

    def __len__(self):
        return len(self._locations)

    def items(self):
        """Return list of ((i, j, k), IndexLocation) tuples."""
        return self._locations.items()

    def backUp(self):
        """Gather internal info that should be restored within a retainState."""
        self._backup = self._unitSteps, self._bounds, self._offset

    def restoreBackup(self):
        self._unitSteps, self._bounds, self._offset = self._backup

    def getCoordinates(self, indices, nativeCoords=False) -> numpy.ndarray:
        """Return the coordinates of the center of the mesh cell at the given given indices in cm."""
        indices = numpy.array(indices)
        return self._evaluateMesh(
            indices, self._centroidBySteps, self._centroidByBounds
        )

    def getCellBase(self, indices) -> numpy.ndarray:
        """Get the mesh base (lower left) of this mesh cell in cm."""
        indices = numpy.array(indices)
        return self._evaluateMesh(
            indices, self._meshBaseBySteps, self._meshBaseByBounds
        )

    def getCellTop(self, indices) -> numpy.ndarray:
        """Get the mesh top (upper right) of this mesh cell in cm."""
        indices = numpy.array(indices) + 1
        return self._evaluateMesh(
            indices, self._meshBaseBySteps, self._meshBaseByBounds
        )

    def locatorInDomain(
        self, locator: LocationBase, symmetryOverlap: Optional[bool] = False
    ) -> bool:
        """
        Return whether the passed locator is in the domain represented by the Grid.

        For instance, if we have a 1/3rd core hex grid, this would return False for
        locators that are outside of the first third of the grid.

        Parameters
        ----------
        locator : LocationBase
            The location to test
        symmetryOverlap : bool, optional
            Whether grid locations along the symmetry line should be considered "in the
            represented domain". This can be useful when assemblies are split along the
            domain boundary, with fractions of the assembly on either side.
        """
        raise NotImplementedError("Not implemented on base Grid type.")

    def _evaluateMesh(self, indices, stepOperator, boundsOperator) -> numpy.ndarray:
        """
        Evaluate some function of indices on this grid.

        Recall from above that steps are mesh centered and bounds are mesh edged.

        Notes
        -----
        This method may be able to be simplified. Complications from arbitrary
        mixtures of bounds-based and step-based meshing caused it to get bad.
        These were separate subclasses first, but in practice almost all cases have some mix
        of step-based (hexagons, squares), and bounds based (radial, zeta).

        Improvements welcome!
        """
        boundCoords = []
        for ii, bounds in enumerate(self._bounds):
            if bounds is not None:
                boundCoords.append(boundsOperator(indices[ii], bounds))

        # limit step operator to the step dimensions
        stepCoords = stepOperator(numpy.array(indices)[self._stepDims])

        # now mix/match bounds coords with step coords appropriately.
        result = numpy.zeros(len(indices))
        result[self._stepDims] = stepCoords
        result[self._boundDims] = boundCoords
        return result + self._offset

    def _centroidBySteps(self, indices):
        return numpy.dot(self._unitSteps, indices)

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
        return ((i + 1, j, k), (1, j + 1, k), (i - 1, j, k), (i, j - 1, k))

    def getSymmetricEquivalents(self, indices):
        """
        Return a list of grid indices that contain matching contents based on symmetry.

        The length of the list will depend on the type of symmetry being used, and
        potentially the location of the requested indices. E.g.,
        third-core will return the two sets of indices at the matching location in the
        other two thirds of the grid, unless it is the central location, in which case
        no indices will be returned.
        """
        raise NotImplementedError

    @staticmethod
    def getAboveAndBelowCellIndices(indices):
        i, j, k = indices
        return ((i, j, k + 1), (i, j, k - 1))

    def cellIndicesContainingPoint(self, x, y=0.0, z=0.0):
        """Return the indices of a mesh cell that contains a point."""
        raise NotImplementedError

    def overlapsWhichSymmetryLine(self, indices):
        return None

    def getLabel(self, indices):
        """
        Get a string label from a 0-based spatial locator.

        Returns a string representing i, j, and k indices of the locator
        """
        i, j = indices[:2]
        label = f"{i:03d}-{j:03d}"
        if len(indices) == 3:
            label += f"-{indices[2]:03d}"
        return label

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
    def getIndicesFromRingAndPos(ring, pos):
        """
        Return i, j indices given ring and position.

        Note
        ----
        This should be implemented as a staticmethod, since no Grids currently in
        exsistence actually need any instance data to perform this task, and
        staticmethods provide the convenience of calling the method without an instance
        of the class in the first place.
        """
        raise NotImplementedError("Base Grid does not know about ring/pos")

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
        raise NotImplementedError("Base grid does not know about rings")

    def getPositionsInRing(self, ring: int) -> int:
        """Return the number of positions within a ring."""
        raise NotImplementedError("Base grid does not know about rings")

    def getRingPos(self, indices) -> Tuple[int, int]:
        """
        Get ring and position number in this grid.

        For non-hex grids this is just i and j.

        A tuple is returned so that it is easy to compare pairs of indices.
        """
        # Regular grids dont really know about ring and position. We can try to see if
        # their parent does!
        if (
            self.armiObject is not None
            and self.armiObject.parent is not None
            and self.armiObject.parent.spatialGrid is not None
        ):
            return self.armiObject.parent.spatialGrid.getRingPos(indices)

        # For compatibility's sake, return __something__. TODO: We may want to just
        # throw here, to be honest.
        return tuple(i + 1 for i in indices[:2])

    def getAllIndices(self):
        """Get all possible indices in this grid."""
        iBounds, jBounds, kBounds = self.getIndexBounds()
        allIndices = tuple(
            itertools.product(range(*iBounds), range(*jBounds), range(*kBounds))
        )
        return allIndices

    def buildLocations(self):
        """Populate all grid cells with a characteristic SpatialLocator."""
        for i, j, k in self.getAllIndices():
            loc = IndexLocation(i, j, k, self)
            self._locations[(i, j, k)] = loc

    @property
    def pitch(self):
        """
        The pitch of the grid.

        Assumes 2-d unit-step defined (works for cartesian)
        """
        # TODO move this to the CartesianGrid
        pitch = (self._unitSteps[0][0], self._unitSteps[1][1])
        if pitch[0] == 0:
            raise ValueError(f"Grid {self} does not have a defined pitch.")
        return pitch


def _tuplify(maybeArray):
    if isinstance(maybeArray, (numpy.ndarray, list, tuple)):
        maybeArray = tuple(
            tuple(row) if isinstance(row, (numpy.ndarray, list)) else row
            for row in maybeArray
        )

    return maybeArray
