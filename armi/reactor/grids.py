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
import collections
import itertools
import math
from typing import Tuple, List, Optional, Sequence, Union

import numpy.linalg


from armi.utils import hexagon
from armi.reactor import geometry

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
        Unpickle a locator, the grid will attach itself if it was also pickled, otherwise this will
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
        >>> grid = grids.HexGrid.fromPitch(1.0)
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

    def associate(self, grid):
        """Re-assign locator to another Grid."""
        self._grid = grid


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
        grid = self.grid  # performance matters a lot here so we remove a dot
        # check for None rather than __nonzero__ for speed (otherwise it checks the length)
        if (
            grid is not None
            and grid.armiObject is not None
            and grid.armiObject.parent is not None
        ):
            return grid.armiObject.spatialLocator
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
        if parentLocation is not None:
            if parentLocation.grid is not None and addingIsValid(
                self.grid, parentLocation.grid
            ):
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

    def getSymmetricEquivalents(self):
        """
        Get symmetrically-equivalent locations, based on Grid symmetry.

        See Also
        --------
        Grid.getSymmetricEquivalents
        """
        return self.grid.getSymmetricEquivalents(self.indices)

    def distanceTo(self, other) -> float:
        """
        Return the distance from this locator to another.
        """
        return math.sqrt(
            (
                (
                    numpy.array(self.getGlobalCoordinates())
                    - numpy.array(other.getGlobalCoordinates())
                )
                ** 2
            ).sum()
        )


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

    # MIL's cannot be hashed, so we need to scrape off the implementation from
    # LocationBase. This raises some interesting questions of substitutability of the
    # various Location classes, which should be addressed.
    __hash__ = None

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

    def __repr__(self):
        return "<{} with {} locations>".format(
            self.__class__.__name__, len(self._locations)
        )

    def __getitem__(self, index):
        return self._locations[index]

    def __setitem__(self, index, obj):
        self._locations[index] = obj

    def __iter__(self):
        return iter(self._locations)

    def __len__(self):
        return len(self._locations)

    def detachedCopy(self):
        loc = MultiIndexLocation(None)
        loc.extend(self._locations)
        return loc

    def associate(self, grid):
        self._grid = grid
        for loc in self._locations:
            loc.associate(grid)

    def getCompleteIndices(self) -> Tuple[int, int, int]:
        raise NotImplementedError("Multi locations cannot do this yet.")

    def append(self, location: IndexLocation):
        self._locations.append(location)

    def extend(self, locations: List[IndexLocation]):
        self._locations.extend(locations)

    def pop(self, location: IndexLocation):
        self._locations.pop(location)

    @property
    def indices(self):
        """
        Return indices for all locations.

        Notes
        -----
        Notice that this returns a list of all of the indices, unlike the ``indices()``
        implementation for :py:class:`IndexLocation`. This is intended to make the
        behavior of getting the indices from the Locator symmetric with passing a list
        of indices to the Grid's ``__getitem__()`` function, which constructs and
        returns a ``MultiIndexLocation`` containing those indices.
        """
        return [loc.indices for loc in self._locations]


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
        return 0, 0, 0

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
        """Get the mesh base (lower left) of this mesh cell in cm"""
        indices = numpy.array(indices)
        return self._evaluateMesh(
            indices, self._meshBaseBySteps, self._meshBaseByBounds
        )

    def getCellTop(self, indices) -> numpy.ndarray:
        """Get the mesh top (upper right) of this mesh cell in cm"""
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
        """
        Return the grid bounds for each dimension, if present.
        """
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
        """
        Return the number of positions within a ring.
        """
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
        """
        Not implemented for Cartesian-see getRingPos notes.
        """
        raise NotImplementedError(
            "Cartesian should not need need ring/pos, use i, j indices."
            "See getRingPos doc string notes for more information/example."
        )

    def getMinimumRings(self, n):
        """
        Return the minimum number of rings needed to fit ``n`` objects.
        """
        numPositions = 0
        for ring in itertools.count(1):
            ringPositions = self.getPositionsInRing(ring)
            numPositions += ringPositions
            if numPositions >= n:
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
        """
        Return the number of positions within a ring.
        """
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
                raise ValueError(f"Position in center ring must be 1, not {pos}")
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
            return self._getSymmetricIdenticalsThird(indices)
        elif self.symmetry.domain == geometry.DomainType.FULL_CORE:
            return []
        else:
            raise NotImplementedError(
                "Unhandled symmetry condition for HexGrid: {}".format(
                    str(self.symmetry)
                )
            )

    def _getSymmetricIdenticalsThird(self, indices):
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


def _tuplify(maybeArray):
    if isinstance(maybeArray, (numpy.ndarray, list, tuple)):
        maybeArray = tuple(
            tuple(row) if isinstance(row, (numpy.ndarray, list)) else row
            for row in maybeArray
        )

    return maybeArray
