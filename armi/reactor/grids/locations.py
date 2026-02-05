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
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Hashable, Iterator, List, Optional, Tuple, Union

import numpy as np

if TYPE_CHECKING:
    # Avoid some circular imports
    from armi.reactor.grids import Grid


IJType = Tuple[int, int]
IJKType = Tuple[int, int, int]


class LocationBase(ABC):
    """
    A namedtuple-like object for storing location information.

    It's immutable (you can't set things after construction) and has names.
    """

    __slots__ = ("_i", "_j", "_k", "_grid")

    def __init__(self, i: int, j: int, k: int, grid: Optional["Grid"]):
        self._i = i
        self._j = j
        self._k = k
        self._grid = grid

    def __repr__(self) -> str:
        return "<{} @ ({},{:},{})>".format(self.__class__.__name__, self.i, self.j, self.k)

    def __getstate__(self) -> Hashable:
        """Used in pickling and deepcopy, this detaches the grid."""
        return (self._i, self._j, self._k, None)

    def __setstate__(self, state: Hashable):
        """Unpickle a locator, the grid will attach itself if it was also pickled, otherwise this will be detached."""
        self.__init__(*state)

    @property
    def i(self) -> int:
        return self._i

    @property
    def j(self) -> int:
        return self._j

    @property
    def k(self) -> int:
        return self._k

    @property
    def grid(self) -> Optional["Grid"]:
        return self._grid

    def __getitem__(self, index: int) -> Union[int, "Grid"]:
        return (self.i, self.j, self.k, self.grid)[index]

    def __hash__(self) -> Hashable:
        """
        Define a hash so we can use these as dict keys w/o having exact object.

        Notes
        -----
        Including the ``grid`` attribute may be more robust; however, using only (i, j, k) allows dictionaries to use
        IndexLocations and (i,j,k) tuples interchangeably.
        """
        return hash((self.i, self.j, self.k))

    def __eq__(self, other: Union[IJKType, "LocationBase"]) -> bool:
        if isinstance(other, tuple):
            return (self.i, self.j, self.k) == other
        if isinstance(other, LocationBase):
            return self.i == other.i and self.j == other.j and self.k == other.k and self.grid is other.grid
        return NotImplemented

    def __lt__(self, that: "LocationBase") -> bool:
        """
        A Locationbase is less than another if the pseudo-radius is less, or if equal, in order any index is less.

        Examples
        --------
        >>> grid = grids.HexGrid.fromPitch(1.0)
        >>> grid[0, 0, 0] < grid[2, 3, 4]  # the "radius" is less
        True
        >>> grid[2, 3, 4] < grid[2, 3, 4]  # they are equal
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

    def __len__(self) -> int:
        """Returns 3, the number of directions."""
        return 3

    def associate(self, grid: "Grid"):
        """Re-assign locator to another Grid."""
        self._grid = grid

    @property
    @abstractmethod
    def indices(self) -> np.ndarray:
        """Get the non-grid indices (i,j,k) of this locator.

        This strips off the annoying ``grid`` tagalong which is there to ensure proper equality (i.e. (0,0,0) in a
        storage rack is not equal to (0,0,0) in a core).

        It is a numpy array for two reasons:

        1. It can be added and subtracted for the recursive computations through different coordinate systems.
        2. It can be written/read from the database.
        """


class IndexLocation(LocationBase):
    """
    An immutable location representing one cell in a grid.

    The locator is intimately tied to a grid and together, they represent a grid cell somewhere in
    the coordinate system of the grid.

    ``grid`` is not in the constructor (must be added after construction ) because the extra argument (grid) gives an
    inconsistency between __init__ and __new__. Unfortunately this decision makes whipping up IndexLocations on the fly
    awkward. But perhaps that's ok because they should only be created by their grids.
    """

    __slots__ = ()

    def __add__(self, that: Union[IJKType, "IndexLocation"]) -> "IndexLocation":
        """
        Enable adding with other objects like this and/or 3-tuples.

        Tuples are needed so we can terminate the recursive additions with a (0,0,0) basis.
        """
        # New location is not associated with any particular grid.
        return self.__class__(self[0] + that[0], self[1] + that[1], self[2] + that[2], None)

    def __sub__(self, that: Union[IJKType, "IndexLocation"]) -> "IndexLocation":
        return self.__class__(self[0] - that[0], self[1] - that[1], self[2] - that[2], None)

    def detachedCopy(self) -> "IndexLocation":
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

        For example, if this is one of many spatialLocators in a 2-D grid representing a reactor, then the
        ``parentLocation`` is the spatialLocator of the reactor, which will often be a ``CoordinateLocation``.
        """
        grid = self.grid  # performance matters a lot here so we remove a dot
        # check for None rather than __nonzero__ for speed (otherwise it checks the length)
        if grid is not None and grid.armiObject is not None and grid.armiObject.parent is not None:
            return grid.armiObject.spatialLocator
        return None

    @property
    def indices(self) -> np.ndarray:
        """
        Get the non-grid indices (i,j,k) of this locator.

        This strips off the annoying ``grid`` tagalong which is there to ensure proper equality (i.e. (0,0,0) in a
        storage rack is not equal to (0,0,0) in a core).

        It is a numpy array for two reasons:

        1. It can be added and subtracted for the recursive computations through different coordinate systems.
        2. It can be written/read from the database.

        """
        return np.array(self[:3])

    def getCompleteIndices(self) -> IJKType:
        """
        Transform the indices of this object up to the top mesh.

        The top mesh is either the one where there's no more parent (true top) or when an axis gets added twice. Unlike
        with coordinates, you can only add each index axis one time. Thus a *complete* set of indices is one where an
        index for each axis has been defined by a set of 1, 2, or 3 nested grids.

        This is useful for getting the reactor-level (i,j,k) indices of an object in a multi-layered 2-D(assemblies in
        core)/1-D(blocks in assembly) mesh like the one mapping blocks up to reactor in Hex reactors.

        The benefit of that particular mesh over a 3-D one is that different assemblies can have different axial meshes,
        a common situation.

        It will just return local indices for pin-meshes inside of blocks.

        A tuple is returned so that it is easy to compare pairs of indices.
        """
        parentLocation = self.parentLocation  # to avoid evaluating property if's twice
        indices = self.indices
        if parentLocation is not None:
            if parentLocation.grid is not None and addingIsValid(self.grid, parentLocation.grid):
                indices += parentLocation.indices
        return tuple(indices)

    def getLocalCoordinates(self, nativeCoords=False):
        """Return the coordinates of the center of the mesh cell here in cm."""
        if self.grid is None:
            raise ValueError(f"Cannot get local coordinates of {self} because grid is None.")
        return self.grid.getCoordinates(self.indices, nativeCoords=nativeCoords)

    def getGlobalCoordinates(self, nativeCoords=False):
        """Get coordinates in global 3D space of the centroid of this object."""
        parentLocation = self.parentLocation  # to avoid evaluating property if's twice
        if parentLocation:
            return self.getLocalCoordinates(nativeCoords=nativeCoords) + parentLocation.getGlobalCoordinates(
                nativeCoords=nativeCoords
            )
        return self.getLocalCoordinates(nativeCoords=nativeCoords)

    def getGlobalCellBase(self):
        """Return the cell base (i.e. "bottom left"), in global coordinate system."""
        parentLocation = self.parentLocation  # to avoid evaluating property if's twice
        if parentLocation:
            return parentLocation.getGlobalCellBase() + self.grid.getCellBase(self.indices)
        return self.grid.getCellBase(self.indices)

    def getGlobalCellTop(self):
        """Return the cell top (i.e. "top right"), in global coordinate system."""
        parentLocation = self.parentLocation  # to avoid evaluating property if's twice
        if parentLocation:
            return parentLocation.getGlobalCellTop() + self.grid.getCellTop(self.indices)
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

    def distanceTo(self, other: "IndexLocation") -> float:
        """Return the distance from this locator to another."""
        return math.sqrt(((np.array(self.getGlobalCoordinates()) - np.array(other.getGlobalCoordinates())) ** 2).sum())


class MultiIndexLocation(IndexLocation):
    """
    A collection of index locations that can be used as a spatialLocator.

    This allows components with multiplicity>1 to have location information within a parent grid. The implication is
    that there are multiple discrete components, each one residing in one of the actual locators underlying this
    collection.

    .. impl:: Store components with multiplicity greater than 1
        :id: I_ARMI_GRID_MULT
        :implements: R_ARMI_GRID_MULT

        As not all grids are "full core symmetry", ARMI will sometimes need to track multiple positions for a single
        object: one for each symmetric portion of the reactor. This class doesn't calculate those positions in the
        reactor, it just tracks the multiple positions given to it. In practice, this class is mostly just a list of
        ``IndexLocation`` objects.
    """

    # MIL's cannot be hashed, so we need to scrape off the implementation from LocationBase. This raises some
    # interesting questions of substitutability of the various Location classes, which should be addressed.
    __hash__ = None

    _locations: List[IndexLocation]

    def __init__(self, grid: "Grid"):
        IndexLocation.__init__(self, 0, 0, 0, grid)
        self._locations = []

    def __eq__(self, other):
        """Considered equal if the grids are identical and contained locations are identical.

        Two ``MultiIndexLocation`` objects with the same total collection of locations, but in
        different orders, will not be considered equal.
        """
        if isinstance(other, type(self)):
            return self.grid == other.grid and self._locations == other._locations
        # Different objects -> let other.__eq__(self) handle it
        return NotImplemented

    def __getstate__(self) -> List[IndexLocation]:
        """Used in pickling and deepcopy, this detaches the grid."""
        return self._locations

    def __setstate__(self, state: List[IndexLocation]):
        """Unpickle a locator, the grid will attach itself if it was also pickled, otherwise this will be detached."""
        self.__init__(None)
        self._locations = state

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} with {len(self._locations)} locations>"

    def __getitem__(self, index: int) -> IndexLocation:
        return self._locations[index]

    def __setitem__(self, index: int, obj: IndexLocation):
        self._locations[index] = obj

    def __iter__(self) -> Iterator[IndexLocation]:
        return iter(self._locations)

    def __len__(self) -> int:
        return len(self._locations)

    def detachedCopy(self) -> "MultiIndexLocation":
        loc = MultiIndexLocation(None)
        loc.extend(self._locations)
        return loc

    def associate(self, grid: "Grid"):
        self._grid = grid
        for loc in self._locations:
            loc.associate(grid)

    def getCompleteIndices(self) -> IJKType:
        raise NotImplementedError("Multi locations cannot do this yet.")

    def append(self, location: IndexLocation):
        self._locations.append(location)

    def extend(self, locations: List[IndexLocation]):
        self._locations.extend(locations)

    def pop(self, location: IndexLocation):
        self._locations.pop(location)

    @property
    def indices(self) -> List[np.ndarray]:
        """
        Return indices for all locations.

        .. impl:: Return the location of all instances of grid components with multiplicity greater than 1.
            :id: I_ARMI_GRID_ELEM_LOC
            :implements: R_ARMI_GRID_ELEM_LOC

            This method returns the indices of all the ``IndexLocation`` objects. To be clear, this does not return the
            ``IndexLocation`` objects themselves. This is designed to be consistent with the Grid's ``__getitem__()``
            method.
        """
        return [loc.indices for loc in self._locations]


class CoordinateLocation(IndexLocation):
    """
    A triple representing a point in space.

    This is still associated with a grid. The grid defines the continuous coordinate space and axes that the location is
    within. This also links to the composite tree.
    """

    __slots__ = ()

    def __eq__(self, other):
        if isinstance(other, type(self)):
            # Mainly to avoid comparing against MultiIndexLocations. Fuel pins may have a multi index location and the
            # duct may have a coordinate location and we don't want them to be equal.
            return self.grid == other.grid and self.i == other.i and self.j == other.j and self.k == other.k
        return NotImplemented

    def __hash__(self):
        """Hash based on the coordinates but not the grid."""
        return hash((self.i, self.j, self.k))

    def getLocalCoordinates(self, nativeCoords=False):
        """Return x,y,z coordinates in cm within the grid's coordinate system."""
        return self.indices

    def getCompleteIndices(self) -> IJKType:
        """Top of chain. Stop recursion and return basis."""
        return 0, 0, 0

    def getGlobalCellBase(self):
        return self.indices

    def getGlobalCellTop(self):
        return self.indices


def addingIsValid(myGrid: "Grid", parentGrid: "Grid"):
    """
    True if adding a indices from one grid to another is considered valid.

    In ARMI we allow the addition of a 1-D axial grid with a 2-D grid. We do not allow any other kind of adding. This
    enables the 2D/1D grid layout in Assemblies/Blocks but does not allow 2D indexing in pins to become inconsistent.
    """
    return myGrid.isAxialOnly and not parentGrid.isAxialOnly
