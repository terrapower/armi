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
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Hashable, Iterable, List, Optional, Tuple, Union

import numpy as np

from armi.reactor import geometry
from armi.reactor.grids.locations import IJKType, IJType, IndexLocation, LocationBase

if TYPE_CHECKING:
    from armi.reactor.composites import ArmiObject


class Grid(ABC):
    """Base class that defines the interface for grids.

    Most work will be done with structured grids, e.g., hexagonal grid, Cartesian grids,
    but some physics codes accept irregular or unstructured grids. Consider
    a Cartesian grid but with variable stepping between cells, where ``dx`` may not be
    constant.

    So here, we define an interface so things that rely on grids can worry less
    about how the location data are stored.

    .. impl:: Grids can nest.
        :id: I_ARMI_GRID_NEST
        :implements: R_ARMI_GRID_NEST

        The reactor will usually have (i,j,k) coordinates to define a
        simple mesh for locating objects in the reactor. But inside that mesh can
        be a smaller mesh to define the layout of pins in a reactor, or fuel pellets in
        a pin, or the layout of some intricate ex-core structure.

        Every time the :py:class:`armi.reactor.grids.locations.IndexLocation` of an
        object in the reactor is returned, ARMI will look to see if the grid this object
        is in has a :py:meth:`parent <armi.reactor.grids.locations.IndexLocation.parentLocation>`,
        and if so, ARMI will try to sum the
        :py:meth:`indices <armi.reactor.grids.locations.IndexLocation.indices>` of the two
        nested grids to give a resultant, more finely-grained grid position. ARMI can only
        handle grids nested 3 deep.

    Parameters
    ----------
    geomType : str or armi.reactor.geometry.GeomType
        Underlying geometric representation
    symmetry : str or armi.reactor.geometry.SymmetryType
        Symmetry conditions
    armiObject : optional, armi.reactor.composites.ArmiObject
        If given, what is this grid attached to or what does it describe?
        Something like a :class:`armi.reactor.Core`
    """

    _geomType: str
    _symmetry: str
    armiObject: Optional["ArmiObject"]

    def __init__(
        self,
        geomType: Union[str, geometry.GeomType] = "",
        symmetry: Union[str, geometry.SymmetryType] = "",
        armiObject: Optional["ArmiObject"] = None,
    ):
        # geometric metadata encapsulated here because it's related to the grid.
        # They do not impact the grid object itself.
        # Notice that these are stored using their string representations, rather than
        # the GridType enum. This avoids the danger of deserializing an enum value from
        # an old version of the code that may have had different numeric values.
        self.geomType = geomType
        self.symmetry = symmetry
        self.armiObject = armiObject
        self._backup = None

    @property
    def geomType(self) -> geometry.GeomType:
        """Geometric representation."""
        return geometry.GeomType.fromStr(self._geomType)

    @geomType.setter
    def geomType(self, geomType: Union[str, geometry.GeomType]):
        if geomType:
            self._geomType = str(geometry.GeomType.fromAny(geomType))
        else:
            self._geomType = ""

    @property
    def symmetry(self) -> str:
        """Symmetry applied to the grid.

        .. impl:: Grids shall be able to represent 1/3 and full core symmetries.
            :id: I_ARMI_GRID_SYMMETRY0
            :implements: R_ARMI_GRID_SYMMETRY

            Every grid contains a :py:class:`armi.reactor.geometry.SymmetryType` or
            string that defines a grid as full core or a partial core: 1/3, 1/4, 1/8, or 1/16
            core. The idea is that the user can define 1/3 or 1/4 of the reactor, so
            the analysis can be run faster on a smaller reactor. And if a non-full
            core reactor grid is defined, the boundaries of the grid can be reflective
            or periodic, to determine what should happen at the boundaries of the
            reactor core.

            It is important to note, that not all of these geometries will apply to
            every reactor or core. If your core is made of hexagonal assemblies, then a
            1/3 core grid would make sense, but not if your reactor core was made up of
            square assemblies. Likewise, a hexagonal core would not make be able to
            support a 1/4 grid. You want to leave assemblies (and other objects) whole
            when dividing a grid up fractionally.
        """
        return geometry.SymmetryType.fromStr(self._symmetry)

    @symmetry.setter
    def symmetry(self, symmetry: Union[str, geometry.SymmetryType]):
        if symmetry:
            self._symmetry = str(geometry.SymmetryType.fromAny(symmetry))
        else:
            self._symmetry = ""

    def __getstate__(self) -> Dict:
        """
        Pickling removes reference to ``armiObject``.

        Removing the ``armiObject`` allows us to pickle an assembly without pickling
        the entire reactor. An ``Assembly.spatialLocator.grid.armiObject`` is the
        reactor, by removing the link here, we still have spatial orientation, but are
        not required to pickle the entire reactor to pickle an assembly.

        This relies on the ``armiObject.__setstate__`` to assign itself.
        """
        state = self.__dict__.copy()
        state["armiObject"] = None

        return state

    def __setstate__(self, state: Dict):
        """
        Pickling removes reference to ``armiObject``.

        This relies on the ``ArmiObject.__setstate__`` to assign itself.
        """
        self.__dict__.update(state)

        for _index, locator in self.items():
            locator._grid = self

    @property
    @abstractmethod
    def isAxialOnly(self) -> bool:
        """Indicate to parts of ARMI if this Grid handles only axial cells."""

    @abstractmethod
    def __len__(self) -> int:
        """Number of items in the grid."""

    @abstractmethod
    def items(self) -> Iterable[Tuple[IJKType, IndexLocation]]:
        """Return list of ((i, j, k), IndexLocation) tuples."""

    @abstractmethod
    def locatorInDomain(self, locator: LocationBase, symmetryOverlap: Optional[bool] = False) -> bool:
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

        Returns
        -------
        bool
            If the given locator is within the given grid
        """

    @abstractmethod
    def getSymmetricEquivalents(self, indices: IJType) -> List[IJType]:
        """
        Return a list of grid indices that contain matching contents based on symmetry.

        The length of the list will depend on the type of symmetry being used, and
        potentially the location of the requested indices. E.g.,
        third-core will return the two sets of indices at the matching location in the
        other two thirds of the grid, unless it is the central location, in which case
        no indices will be returned.
        """

    @abstractmethod
    def overlapsWhichSymmetryLine(self, indices: IJType) -> Optional[int]:
        """Return lines of symmetry position at a given index can be found.

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
        """

    @abstractmethod
    def getCoordinates(
        self,
        indices: Union[IJKType, List[IJKType]],
        nativeCoords: bool = False,
    ) -> np.ndarray:
        pass

    @abstractmethod
    def backUp(self):
        """Subclasses should modify the internal backup variable."""

    @abstractmethod
    def restoreBackup(self):
        """Restore state from backup."""

    @abstractmethod
    def getCellBase(self, indices: IJKType) -> np.ndarray:
        """Return the lower left case of this cell in cm."""

    @abstractmethod
    def getCellTop(self, indices: IJKType) -> np.ndarray:
        """Get the upper right of this cell in cm."""

    @staticmethod
    def getLabel(indices):
        """
        Get a string label from a 0-based spatial locator.

        Returns a string representing i, j, and k indices of the locator
        """
        i, j = indices[:2]
        label = f"{i:03d}-{j:03d}"
        if len(indices) == 3:
            label += f"-{indices[2]:03d}"
        return label

    @abstractmethod
    def reduce(self) -> Tuple[Hashable, ...]:
        """
        Return the set of arguments used to create this Grid.

        This is very much like the argument tuple from ``__reduce__``, but we do not
        implement ``__reduce__`` for real, because we are generally happy with
        ``__getstate__`` and ``__setstate__`` for pickling purposes. However, getting
        these arguments to ``__init__`` is useful for storing Grids to the database, as
        they are more stable (less likely to change) than the actual internal state of
        the objects.

        The return value should be hashable, such that a set of these can be created.

        The return type should be symmetric such that a similar grid can be
        created just with the outputs of ``Grid.reduce``, e.g.,
        ``type(grid)(*grid.reduce())``

        Notes
        -----
        For consistency, the second to last argument **must** be the geomType
        """
