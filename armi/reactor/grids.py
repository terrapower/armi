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
"""
This contains structured meshes in multiple geometries and spatial locators (i.e. locations).

:py:class:`Grids <Grid>` are objects that map indices (i, j, k) to spatial locations
(x,y,z) or (t,r,z).  They are useful for arranging things in reactors, such as:

* Fuel assemblies in a reactor
* Plates in a heat exchanger
* Pins in a fuel assembly
* Blocks in a fuel assembly (1-D)

Fast reactors often use a hexagonal grid, while other reactors may be better suited for
Cartesian or RZT grids. This module contains representations of all these.

``Grid``s can be defined by any arbitrary combination of absolute grid boundaries and
unit step directions.

Associated with grids are :py:class:`IndexLocations <IndexLocation>`. Each of these maps
to a single cell in a grid, or to an arbitrary point in the continuous space represented
by a grid. When a `Grid`` is built, it builds a collection of ``IndexLocation``s, one
for each cell.

In the ARMI :py:mod:`armi.reactor` module, each object is assigned a locator either from
a grid or in arbitrary, continuous space (using a :py:class:`CoordinateLocation`) on the
``spatialLocator`` attribute.

Below is a basic example of how to use a 2-D grid::

>>> grid = cartesianGridFromRectangle(1.0, 1.0)  # 1 cm square-pitch Cartesian grid
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

.. note:: ``IndexLocation`` is intended to replace
:py:class:`armi.reactor.locations.Location`.

This module is designed to satisfy the spatial arrangement requirements of :py:mod:`the
Reactor package <armi.reactor>`.

Throughout the module, the term **global** refers to the top-level coordinate system
while the word **local** refers to within the current coordinate system defined by the
current grid.
"""
import itertools
import math
import re
from typing import Tuple, List, Optional, Sequence
import collections

import numpy.linalg

from armi.utils.units import ASCII_LETTER_A, ASCII_ZERO
from armi.utils import hexagon

# data structure for database-serialization of grids
GridParameters = collections.namedtuple(
    "GridParameters",
    ("unitSteps", "bounds", "unitStepLimits", "offset", "geomType", "symmetry"),
)
TAU = math.pi * 2.0
BOUNDARY_0_DEGREES = 1
BOUNDARY_60_DEGREES = 2
BOUNDARY_120_DEGREES = 3
BOUNDARY_CENTER = 4
# list of valid ASCII representations of axial levels.
# A-Z, 0-9, and then some special characters, then a-z
AXIAL_CHARS = [
    chr(asciiCode)
    for asciiCode in (
        list(range(ASCII_LETTER_A, ASCII_LETTER_A + 26))
        + list(range(ASCII_ZERO, ASCII_ZERO + 10))
        + list(range(ASCII_LETTER_A + 26, ASCII_LETTER_A + 32 + 26))
    )
]
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


class LocationBase:
    """
    A namedtuple-like object for storing location information.

    It's immutable (you can't set things after construction) and has names.

    Notes
    -----
    This was originally a namedtuple but there was a somewhat unbelievable
    bug in Python 2.7.8 where unpickling a reactor full of these ended up
    inexplicably replacing one of them with an AssemblyParameterCollection.
    The bug did not show up in Python 3.

    Converting to this class solved that problem.
    """

    __slots__ = ("_i", "_j", "_k", "_grid")

    def __init__(self, i, j, k, grid):
        self._i = i
        self._j = j
        self._k = k
        self._grid = grid

    def __repr__(self):
        return "<{} @ ({},{:},{})>".format(
            self.__class__.__name__, self.i, self.j, self.k
        )

    def __getstate__(self):
        """
        Used in pickling and deepcopy, this detaches the grid.
        """
        return (self._i, self._j, self._k, None)

    def __setstate__(self, state):
        """
        Unpickle a locator, the grid will attach itself if it was also pickled, otherwis this will
        be detached.
        """
        self.__init__(*state)

    @property
    def i(self):
        return self._i

    @property
    def j(self):
        return self._j

    @property
    def k(self):
        return self._k

    @property
    def grid(self):
        return self._grid

    def __getitem__(self, index):
        return (self.i, self.j, self.k, self.grid)[index]

    def __hash__(self):
        """
        Define a hash so we can use these as dict keys w/o having exact object.

        Notes
        -----
        Including the ``grid`` attribute may be more robust; however, using only (i, j, k) allows
        dictionaries to use IndexLocations and (i,j,k) tuples interchangeably.
        """
        return hash((self.i, self.j, self.k))

    def __eq__(self, other):
        if isinstance(other, tuple):
            return (self.i, self.j, self.k) == other
        return (
            self.i == other.i
            and self.j == other.j
            and self.k == other.k
            and self.grid is other.grid
        )

    def __lt__(self, that):
        """
        A Locationbase is less than another if the pseudo-radius is less, or if equal, in order
        any index is less.

        Examples
        --------
        >>> grid = grids.hexGridFromPitch(1.0)
        >>> grid[0, 0, 0] < grid[2, 3, 4]   # the "radius" is less
        True
        >>> grid[2, 3, 4] < grid[2, 3, 4]   # they are equal
        False
        >>> grid[2, 3, 4] < grid[-2, 3, 4]  # 2 is greater than -2
        False
        >>> grid[-2, 3, 4] < grid[2, 3, 4]  # -2 is less than 2
        True
        >>> grid[1, 3, 4] < grid[-2, 3, 4]  # the "radius" is less
        True
        """
        selfIndices = self.indices
        thatIndices = that.indices
        # this is not really r, but it is fast and consistent
        selfR = abs(selfIndices).sum()
        thatR = abs(thatIndices).sum()

        # this cannot be reduced to
        #   return selfR < thatR or (selfIndices < thatIndices).any()
        # because the comparison is not symmetric.
        if selfR < thatR:
            return True
        else:
            for lt, eq in zip(selfIndices < thatIndices, selfIndices == thatIndices):
                if eq:
                    continue

                return lt

            return False

    def __len__(self):
        """Returns 3, the number of directions."""
        return 3


class IndexLocation(LocationBase):
    """
    An immutable location representing one cell in a grid.

    The locator is intimately tied to a grid and together, they represent
    a grid cell somewhere in the coordinate system of the grid.

    ``grid`` is not in the constructor (must be added after construction ) because
    the extra argument (grid) gives an inconsistency between __init__ and __new__.
    Unfortunately this decision makes whipping up IndexLocations on the fly awkward.
    But perhaps that's ok because they should only be created by their grids.
    """

    __slots__ = ()

    def __add__(self, that):
        """
        Enable adding with other objects like this and/or 3-tuples.

        Tuples are needed so we can terminate the recursive additions with a (0,0,0) basis.
        """
        # New location is not associated with any particular grid.
        return self.__class__(
            self[0] + that[0], self[1] + that[1], self[2] + that[2], None
        )

    def __sub__(self, that):
        return self.__class__(
            self[0] - that[0], self[1] - that[1], self[2] - that[2], None
        )

    def detachedCopy(self):
        """
        Make a copy of this locator that is not associated with a grid.

        See Also
        --------
        armi.reactor.reactors.detach : uses this
        """
        return self.__class__(self.i, self.j, self.k, None)

    @property
    def parentLocation(self):
        """
        Get the spatialLocator of the ArmiObject that this locator's grid is anchored to.

        For example, if this is one of many spatialLocators in a 2-D grid representing
        a reactor, then the ``parentLocation`` is the spatialLocator of the reactor, which
        will often be a ``CoordinateLocation``.
        """
        if self.grid and self.grid.armiObject and self.grid.armiObject.parent:
            return self.grid.armiObject.spatialLocator
        return None

    @property
    def indices(self):
        """
        Get the non-grid indices (i,j,k) of this locator.

        This strips off the annoying ``grid`` tagalong which is there to ensure proper
        equality (i.e. (0,0,0) in a storage rack is not equal to (0,0,0) in a core).

        It is a numpy array for two reasons:
        1. It can be added and subtracted for the recursive computations
           through different coordinate systems
        2. It can be written/read from the database.
        """
        return numpy.array(self[:3])

    def getCompleteIndices(self) -> Tuple[int, int, int]:
        """
        Transform the indices of this object up to the top mesh.

        The top mesh is either the one where there's no more parent (true top)
        or when an axis gets added twice. Unlike with coordinates,
        you can only add each index axis one time. Thus a *complete*
        set of indices is one where an index for each axis has been defined
        by a set of 1, 2, or 3 nested grids.

        This is useful for getting the reactor-level (i,j,k) indices of an object
        in a multi-layered 2-D(assemblies in core)/1-D(blocks in assembly) mesh
        like the one mapping blocks up to reactor in Hex reactors.

        The benefit of that particular mesh over a 3-D one is that different
        assemblies can have different axial meshes, a common situation.

        It will just return local indices for pin-meshes inside of blocks.

        A tuple is returned so that it is easy to compare pairs of indices.
        """
        parentLocation = self.parentLocation  # to avoid evaluating property if's twice
        indices = self.indices
        if parentLocation:
            if parentLocation.grid and addingIsValid(self.grid, parentLocation.grid):
                indices += parentLocation.indices
        return tuple(indices)

    def getLocalCoordinates(self, nativeCoords=False):
        """Return the coordinates of the center of the mesh cell here in cm."""
        if self.grid is None:
            raise ValueError(
                "Cannot get local coordinates of {} because grid is None.".format(self)
            )
        return self.grid.getCoordinates(self.indices, nativeCoords=nativeCoords)

    def getGlobalCoordinates(self, nativeCoords=False):
        """Get coordinates in global 3D space of the centroid of this object."""
        parentLocation = self.parentLocation  # to avoid evaluating property if's twice
        if parentLocation:
            return self.getLocalCoordinates(
                nativeCoords=nativeCoords
            ) + parentLocation.getGlobalCoordinates(nativeCoords=nativeCoords)
        return self.getLocalCoordinates(nativeCoords=nativeCoords)

    def getGlobalCellBase(self):
        """Return the cell base (i.e. "bottom left"), in global coordinate system."""
        parentLocation = self.parentLocation  # to avoid evaluating property if's twice
        if parentLocation:
            return parentLocation.getGlobalCellBase() + self.grid.getCellBase(
                self.indices
            )
        return self.grid.getCellBase(self.indices)

    def getGlobalCellTop(self):
        """Return the cell top (i.e. "top right"), in global coordinate system."""
        parentLocation = self.parentLocation  # to avoid evaluating property if's twice
        if parentLocation:
            return parentLocation.getGlobalCellTop() + self.grid.getCellTop(
                self.indices
            )
        return self.grid.getCellTop(self.indices)

    def getRingPos(self):
        """Return ring and position of this locator."""
        return self.grid.getRingPos(self.getCompleteIndices())


class MultiIndexLocation(IndexLocation):
    """
    A collection of index locations that can be used as a spatialLocator.

    This allows components with multiplicity>1 to have location information
    within a parent grid. The implication is that there are multiple
    discrete components, each one residing in one of the actual locators
    underlying this collection.

    This class contains an implementation that allows a multi-index
    location to be used in the ARMI data model similar to a
    individual IndexLocation.
    """

    def __init__(self, grid):
        IndexLocation.__init__(self, 0, 0, 0, grid)
        self._locations = []

    def __getstate__(self):
        """
        Used in pickling and deepcopy, this detaches the grid.
        """
        return self._locations

    def __setstate__(self, state):
        """
        Unpickle a locator, the grid will attach itself if it was also pickled, otherwise this will
        be detached.
        """
        self.__init__(None)
        self._locations = state

    def __getitem__(self, index):
        return self._locations[index]

    def __setitem__(self, index, obj):
        self._locations[index] = obj

    def __iter__(self):
        return iter(self._locations)

    def __len__(self):
        return len(self._locations)

    def getCompleteIndices(self) -> Tuple[int, int, int]:
        raise NotImplementedError("Multi locations cannot do this yet.")

    def append(self, location: IndexLocation):
        self._locations.append(location)

    def extend(self, locations: List[IndexLocation]):
        self._locations.extend(locations)

    def pop(self, location: IndexLocation):
        self._locations.pop(location)


class CoordinateLocation(IndexLocation):
    """
    A triple representing a point in space.

    This is still associated with a grid. The grid defines the continuous coordinate
    space and axes that the location is within. This also links to the composite tree.
    """

    __slots__ = ()

    def getLocalCoordinates(self, nativeCoords=False):
        """Return x,y,z coordinates in cm within the grid's coordinate system."""
        return self.indices

    def getCompleteIndices(self):
        """Top of chain. Stop recursion and return basis."""
        return numpy.array((0, 0, 0))

    def getGlobalCellBase(self):
        return self.indices

    def getGlobalCellTop(self):
        return self.indices


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
        self.geomType = geomType
        self.symmetry = symmetry

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
            self.geomType,
            self.symmetry,
        )

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
        Pickling removes reference to ``armiObject``

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
        Pickling removes reference to ``armiObject``

        This relies on the ``ArmiObject.__setstate__`` to assign itself.
        """
        self.__dict__.update(state)

        for _indices, locator in self.items():
            locator._grid = self

    def __getitem__(self, ijk):
        """
        Get a location by (i, j, k) indices. If it does not exist, create a new one and return it.

        Notes
        -----

        The method is defaultdict-like, in that it will create a new location on the fly. However,
        the class itself is not really a dictionary, it is just index-able. For example, there is no
        desire to have a ``__setitem__`` method, because the only way to create a location is by
        retrieving it or through ``buildLocations``.
        """
        try:
            return self._locations[ijk]
        except KeyError:
            i, j, k = ijk
            val = IndexLocation(i, j, k, self)
            self._locations[ijk] = val
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

    def getCoordinates(self, indices, nativeCoords=False):
        """Return the coordinates of the center of the mesh cell at the given given indices in cm."""
        indices = numpy.array(indices)
        return self._evaluateMesh(
            indices, self._centroidBySteps, self._centroidByBounds
        )

    def getCellBase(self, indices):
        """Get the mesh base (lower left) of this mesh cell in cm"""
        indices = numpy.array(indices)
        return self._evaluateMesh(
            indices, self._meshBaseBySteps, self._meshBaseByBounds
        )

    def getCellTop(self, indices):
        """Get the mesh top (upper right) of this mesh cell in cm"""
        indices = numpy.array(indices) + 1
        return self._evaluateMesh(
            indices, self._meshBaseBySteps, self._meshBaseByBounds
        )

    def _evaluateMesh(self, indices, stepOperator, boundsOperator):
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

    def _centroidByBounds(self, index, bounds):
        if index < 0:
            # avoid wrap-around
            raise IndexError("Bounds-defined indices may not be negative.")
        return (bounds[index + 1] + bounds[index]) / 2.0

    def _meshBaseByBounds(self, index, bounds):
        if index < 0:
            raise IndexError("Bounds-defined indices may not be negative.")
        return bounds[index]

    def getNeighboringCellIndices(self, i, j=0, k=0):
        """Return the indices of the immediate neighbors of a mesh point in the plane."""
        return ((i + 1, j, k), (1, j + 1, k), (i - 1, j, k), (i, j - 1, k))

    def getAboveAndBelowCellIndices(self, indices):
        i, j, k = indices
        return ((i, j, k + 1), (i, j, k - 1))

    def cellIndicesContainingPoint(self, x, y=0.0, z=0.0):
        """Return the indices of a mesh cell that contains a point."""
        raise NotImplementedError

    def overlapsWhichSymmetryLine(self, indices):
        return None

    def getLabel(self, indices):
        """Get a string label from a 0-based spatial locator."""
        i, j = indices[:2]
        chrNum = int(i // 10)
        label = "{}{:03d}".format(chr(ASCII_LETTER_A + chrNum) + str(i % 10), j)
        if len(indices) == 3:
            label += AXIAL_CHARS[indices[2]]
        return label

    def getLocationFromRingAndPos(self, i, j, k=0):
        """
        Return the location based on ring and position.

        Parameters
        ----------
        i : int
            Ring index
        j : int
            Position index
        k : int, optional
            Axial index

        See Also
        --------
        HexGrid.getLocationFromRingAndPos
            This implements a special method to transform the i, j location based
            on ring and position.
        """
        return self[i, j, k]

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
        self
    ) -> Tuple[
        Optional[Sequence[float]], Optional[Sequence[float]], Optional[Sequence[float]]
    ]:
        """
        Return the grid bounds for each dimension, if present.
        """
        return self._bounds

    def getIndicesFromRingAndPos(self, ring, pos):
        return ring, pos

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

    def getRingPos(self, indices) -> Tuple[int, int]:
        """
        Get ring and position number in this grid.

        For non-hex grids this is just i and j.

        A tuple is returned so that it is easy to compare pairs of indices.
        """
        return tuple(indices[:2])

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

    @property
    def pitch(self):
        """
        The pitch of the grid.

        Assumes 2-d unit-step defined (works for cartesian)
        """
        pitch = (self._unitSteps[0][0], self._unitSteps[1][1])
        if pitch[0] == 0:
            raise ValueError(f"Grid {self} does not have a defined pitch.")
        return pitch


class HexGrid(Grid):
    """Has 6 neighbors in plane."""

    @property
    def pitch(self):
        """
        Get the hex-pitch of a regular hexagonal array.

        See Also
        --------
        armi.reactor.grids.hexGridFromPitch
        """
        return self._unitSteps[1][1]

    def getNeighboringCellIndices(self, i, j=0, k=0):
        """
        Return the indices of the immediate neighbors of a mesh point in the plane.

        Note that these neighbors are ordered counter-clockwise beginning from 2 o'clock.
        This is very important!"""
        return [
            (i + 1, j, k),
            (i, j + 1, k),
            (i - 1, j + 1, k),
            (i - 1, j, k),
            (i, j - 1, k),
            (i + 1, j - 1, k),
        ]

    def getLabel(self, indices):
        """Hex labels start at 1."""
        ring, pos = self.getRingPos(indices)
        if len(indices) == 2:
            return Grid.getLabel(self, (ring, pos))
        else:
            return Grid.getLabel(self, (ring, pos, indices[2]))

    def getIndicesFromRingAndPos(self, ring, pos):
        i, j, _edge = _indicesAndEdgeFromRingAndPos(ring, pos)
        return i, j

    def getLocationFromRingAndPos(self, i, j, k=0):
        """
        Return the location based on ring and position.

        Parameters
        ----------
        i : int
            Ring index
        j : int
            Position index
        k : int, optional
            Axial index

        See Also
        --------
        Grid.getLocationFromRingAndPos
        """
        i, j = self.getIndicesFromRingAndPos(i, j)
        return self[i, j, k]

    def getRingPos(self, indices):
        """
        Get 1-based ring and position from normal indices.

        See Also
        --------
        getIndicesFromRingAndPos : does the reverse
        """
        i, j = indices[:2]
        return indicesToRingPos(i, j)

    def overlapsWhichSymmetryLine(self, indices):
        """Return a list of which lines of symmetry this is on.

        If none, returns []
        If on a line of symmetry in 1/6 geometry, returns a list containing a 6.
        If on a line of symmetry in 1/3 geometry, returns a list containing a 3.
        Only the 1/3 core view geometry is actually coded in here right now.

        Being "on" a symmety line means the line goes through the middle of you.

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

    def getSymmetricIdenticalsThird(self, indices):
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

    def isInFirstThird(self, locator, includeTopEdge=False):
        """True if locator is in first third of hex grid. """
        ring, pos = self.getRingPos(locator.indices)
        if ring == 1:
            return True
        maxPosTotal = hexagon.numPositionsInRing(ring)

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
        locList = []
        for ring in range(1, hexagon.numRingsToHoldNumCells(nLocs) + 1):
            positions = hexagon.numPositionsInRing(ring)
            for position in range(1, positions + 1):
                i, j = getIndicesFromRingAndPos(ring, position)
                locList.append(self[(i, j, 0)])
        # round to avoid differences due to floating point math
        locList.sort(
            key=lambda loc: (
                round(numpy.linalg.norm(loc.getGlobalCoordinates()), 6),
                loc.i,  # loc.i=ring
                loc.j,
            )
        )  # loc.j= pos
        return locList[:nLocs]

    # TODO: this is only used by testing and another method that just needs the count of assemblies
    #       in a ring, not the actual positions
    def allPositionsInThird(self, ring, includeEdgeAssems=False):
        """
        Returns a list of all the positions in a ring (in the first third)

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
        for pos in range(1, hexagon.numPositionsInRing(ring) + 1):
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
    """

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
        i = numpy.abs(self._bounds[0] - theta0).argmin()
        j = numpy.abs(self._bounds[1] - rad0).argmin()

        return (i, j, 0)


def hexGridFromPitch(pitch, numRings=25, armiObject=None, pointedEndUp=False):
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
        The object that this grid is anchored to (i.e. the reactor for a grid of assemblies)
    pointedEndUp : bool, optional
        Rotate the hexagons 30 degrees so that the pointed end faces up instead of the flat.

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
    )


def cartesianGridFromRectangle(
    width, height, numRings=25, isOffset=False, armiObject=None
):
    """
    Build a finite step-based 2-D Cartesian grid based on a width and height in cm.

    isOffset : bool
        If true will put first mesh cell fully within the grid instead of centering it
        on the crosshairs.
    """
    unitSteps = ((width, 0.0, 0.0), (0.0, height, 0.0), (0, 0, 0))
    offset = numpy.array((width / 2.0, height / 2.0, 0.0)) if isOffset else None
    return Grid(
        unitSteps=unitSteps,
        unitStepLimits=((-numRings, numRings), (-numRings, numRings), (0, 1)),
        offset=offset,
        armiObject=armiObject,
    )


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


def thetaRZGridFromGeom(geom, armiObject=None):
    """
    Build 2-D R-theta grid based on a Geometry object.

    Parameters
    ----------
    geomInfo : list
        list of ((indices), assemName) tuples for all positions in core with input in radians

    See Also
    --------
    armi.reactor.geometry.SystemLayoutInput.readGeomXML : produces the geomInfo structure

    Examples
    --------
    >>> grid = grids.thetaRZGridFromGeom(geomInfo)
    """
    allIndices = [indices for indices, _assemName in geom.assemTypeByIndices.items()]

    # create ordered lists of all unique theta and R points
    thetas, radii = set(), set()
    for rad1, rad2, theta1, theta2, _numAzi, _numRadial in allIndices:
        radii.add(rad1)
        radii.add(rad2)
        thetas.add(theta1)
        thetas.add(theta2)
    radii = numpy.array(sorted(radii), dtype=numpy.float64)
    thetaRadians = numpy.array(sorted(thetas), dtype=numpy.float64)

    return ThetaRZGrid(bounds=(thetaRadians, radii, (0.0, 0.0)), armiObject=armiObject)


def ringPosFromRingLabel(ringLabel):
    """Convert a ring-based label like A2003B into 1-based ring, location indices."""
    locMatch = re.search(r"([A-Z]\d)(\d\d\d)([A-Z]?)", ringLabel)
    if locMatch:
        # we have a valid location label. Process it and set parameters
        # convert A4 to 04, B2 to 12, etc.
        ring = locMatch.group(1)
        posLabel = locMatch.group(2)
        axLabel = locMatch.group(3)
        firstDigit = ord(ring[0]) - ASCII_LETTER_A
        if firstDigit < 10:
            i = int("{0}{1}".format(firstDigit, ring[1]))
        else:
            raise RuntimeError(
                "invalid label {0}. 1st character too large.".format(ringLabel)
            )
        j = int(posLabel)
        if axLabel:
            k = AXIAL_CHARS.index(axLabel)
        else:
            k = None
        return i, j, k


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


def getIndicesFromRingAndPos(ring, pos):
    i, j, _edge = _indicesAndEdgeFromRingAndPos(ring, pos)
    return i, j


def _indicesAndEdgeFromRingAndPos(ring, position):
    ring = ring - 1
    pos = position - 1

    if ring == 0:
        return 0, 0, 0

    # # Edge indicates which edge of the ring in which the hexagon resides.
    # # Edge 0 is the NE edge, edge 1 is the N edge, etc.
    # # Offset is (0-based) index of the hexagon in that edge. For instance,
    # # ring 3, pos 12 resides in edge 5 at index 1; it is the second hexagon
    # # in ring 3, edge 5.
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


def addingIsValid(myGrid, parentGrid):
    """
    True if adding a indices from one grid to another is considered valid.

    In ARMI we allow the addition of a 1-D axial grid with a 2-D grid.
    We do not allow any other kind of adding. This enables the 2D/1D
    grid layout in Assemblies/Blocks but does not allow 2D indexing
    in pins to become inconsistent.
    """
    return myGrid.isAxialOnly and not parentGrid.isAxialOnly


def _tuplify(maybeArray):
    if isinstance(maybeArray, (numpy.ndarray, list, tuple)):
        maybeArray = tuple(
            tuple(row) if isinstance(row, (numpy.ndarray, list)) else row
            for row in maybeArray
        )

    return maybeArray
