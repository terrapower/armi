"""Collection of composites with a 1-D grid"""

from abc import ABC, ABCMeta, abstractmethod
from typing import Optional, Iterator, Tuple

from numpy import empty, ndarray

from armi import runLog
from armi.reactor import flags
from armi.reactor.grids import Grid, axialUnitGrid
from armi.reactor.composites import Composite, CompositeModelType


class AbstractCompositeMetaclass(ABCMeta, CompositeModelType):
    """Metaclass that allows for abstract composites"""


class AbstractComposite(ABC, Composite, metaclass=AbstractCompositeMetaclass):
    """Composite that can have abstract methods

    Useful for enforcing interfaces across generic subclasses
    """


class CompositeWithHeight(AbstractComposite):
    """Interface for a composite with a height.

    Like a block but more general

    """

    @abstractmethod
    def getHeight(self) -> float:
        """Return the height of this object"""


class CompositeList(CompositeWithHeight):
    """Axial collection of composites

    Many things in an ARMI :class:`~armi.reactor.reactors.Reactor`
    can be seen as things stacked on things. An
    :class:`~armi.reactor.assemblies.Assemblies` is a 1-D stack of
    :class:`~armi.reactor.blocks.Block` instances, each with an axial
    location and height. Fuel pins are another concept that would benefit
    from a 1-D stack of :class:`~armi.reactor.composites.Composite` like things.

    This class seeks to separate out storing and maintaing the axial mesh
    of things (iteration, item access, mesh updating, etc.) from
    assembly-specific tasks (moving assemblies within the reactor,
    looking for coolant channels, etc.)

    """

    spatialGrid: Optional[Grid]

    def __init__(self, name):
        super().__init__(name)
        self.spatialGrid = None

    def __iter__(self) -> Iterator[CompositeWithHeight]:
        """Iterate over all children"""
        return super().__iter__()

    def __getitem__(self, index: int) -> CompositeWithHeight:
        """Return the child at a specific index"""
        return super().__getitem__(index)

    def add(self, obj: CompositeWithHeight):
        """Add an item to the end of the list

        .. note::

            Object **must** at least have a ``getHeight`` method
            to understand how the spatial grid needs to be updated

        Parameters
        ----------
        obj : Composite
            Object to be added to the end.

        """
        super().add(obj)
        nItems = len(self)
        # Assume spatial grid has been added already
        obj.spatialLocator = self.spatialGrid[0, 0, nItems - 1]
        zbounds = self.spatialGrid.getBounds()[2]
        # Spatial grid has space for this component
        if len(zbounds) < nItems:
            zbounds[nItems] = zbounds[nItems - 1] + obj.getHeight()
        else:
            self.reestablishOrder()
            self.calculateZCoords()

    def insert(self, index: int, obj: CompositeWithHeight):
        """Insert an object at a given position

        Parameters
        ----------
        index : int
            Position to insert the object
        obj : CompositeWithHeight
            Child to be inserted

        """
        super().insert(index, obj)
        obj.spatialLocator = self.spatialGrid[0, 0, index]

    def reestablishOrder(self):
        """After children have been mixed up axially, place them in ascending order

        See Also
        --------
        * :meth:`calculateZCoords` : Updates the zbottom / ztop parameters on each block

        """
        self.spatialGrid = axialUnitGrid(len(self), self)
        for zi, child in enumerate(self):
            child.spatialLocator = self.spatialGrid[0, 0, zi]
            self._renameChild(child, zi)

    @abstractmethod
    def _renameChild(self, child: Composite, index: int):
        """Rename a child at a given index in the list"""

    def calculateZCoords(self):
        """Set the top, bottom, and center z-coordinates"""
        bottom = 0.0
        # Bounds include N + 1 entries to capture the bottom and top of each cell.
        mesh = empty(len(self) + 1)
        mesh[0] = bottom

        for zi, child in enumerate(self):
            height = child.getHeight()
            child.p.zbottom = bottom
            child.p.z = bottom + 0.5 * height

            # Update the upper index and mesh height
            bottom += height
            child.p.ztop = bottom
            mesh[zi + 1] = bottom

            child.spatialLocator = self.spatialGrid[0, 0, zi]

        self._updateZGrid(mesh)

    def _updateZGrid(self, mesh: ndarray):
        previousX, previousY, _previousZ = self.spatialGrid.getBounds()
        self.spatialGrid._bounds = (previousX, previousY, mesh)

    def getHeight(self, typeSpec: Optional[flags.TypeSpec] = None) -> float:
        """Return the height of some or all items in this list

        Parameters
        ----------
        typeSpec : optional Flag or sequence of flags
            Only calculate the height of children that match these flags

        Returns
        -------
        float
            Cumulative height of some or all children

        """
        h = 0.0
        for child in filter(lambda c: c.hasFlags(typeSpec), self):
            h += child.getHeight()
        return h

    def getVolume(self):
        """Compute the total volume in cm^3"""
        return self.getArea() * self.getHeight()

    def getArea(self, cold=False):
        """Return the area of the first child

        .. note::

            This assumes that all children have the same area

        Parameters
        ----------
        cold : optional bool
            Evaluate at cold temperatures if ``cold==True``

        Returns
        -------
        float
            Area in cm^2

        """
        try:
            return self[0].getArea(cold=cold)
        except IndexError:
            runLog.warning(f"{self} has no blocks and therefore no area. Assuming 1.0")
            return 1.0

    def getChildrenAndZ(
        self,
        typeSpec: Optional[flags.TypeSpec] = None,
        returnBottomZ=False,
        returnTopZ=False,
    ) -> Iterator[Tuple[CompositeWithHeight, float]]:
        """
        Get children and their z-coordinates from bottom to top.

        By default, z-coordinates returned will reflect the center of
        the mesh.

        This method is useful when you need to know the z-coord of a
        child in the list.

        Parameters
        ----------
        typeSpec : Flags or list of Flags, optional
            Composite type specification to restrict to
        returnBottomZ : bool, optional
            If true, will return bottom coordinates instead of centers.
        returnTopZ : bool, optional
            If true, return the top coordinates instead of centers.

        Returns
        -------
        iterator of (Composite, float)
            Children and the appropriate z-coordinate
        """

        if returnBottomZ and returnTopZ:
            raise ValueError(
                "Both returnTopZ and returnBottomZ cannot be set to ``True``"
            )
        children = []
        zCoords = []
        bottom = 0.0
        for child in self:
            height = child.getHeight()
            if child.hasFlags(typeSpec):
                children.append(child)
                if returnBottomZ:
                    value = bottom
                elif returnTopZ:
                    value = bottom + height
                else:
                    value = bottom + 0.5 * height
                zCoords.append(value)
            bottom += height
        return zip(children, zCoords)
