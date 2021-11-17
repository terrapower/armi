from typing import Tuple, Any, Union

from armi.reactor.composites import Composite
from armi.reactor.components.volumetricShapes import Sphere


class ParticleFuel(Composite):
    """Composite structure representing concentric spheres of particle fuel

    Each layer of the particle fuel is expected to be added via :meth:`add`
    rather than ``__init__`` because we need this to be constructable via
    blueprint file and the heirarchy written to / read from the database file.

    Parameters
    ----------
    name : str
        Name of this specification, typically something that is easily
        recognizable by an engineering team, e.g., ``"AGR TRISO"``

    Attributes
    ----------
    layers : tuple of :class:`~armi.reactor.components.Sphere`
        Each layer of the specification in order of increasing outer
        diameter

    """

    def __init__(self, name: str):
        super().__init__(name)
        self._layers = None

    def __repr__(self) -> str:
        return f"<{type(self).__qualname__}({self.name}, {self.layers}>"

    def _checkChildAndClearCacheBeforeAdding(self, obj: Union[Any, Sphere]):
        if isinstance(obj, Sphere):
            self._layers = None
            return
        raise TypeError(f"Cannot add non-spherical layer {obj} to {self}")

    def add(self, obj: Union[Any, Sphere]):
        """Add a component layer to this spec"""
        self._checkChildAndClearCacheBeforeAdding(obj)
        return super().add(obj)

    def remove(self, obj: Union[Any, Sphere]):
        """Remove a layer from this spec"""
        self._checkChildAndClearCacheBeforeAdding(obj)
        return super().remove(obj)

    def insert(self, index: int, obj: Union[Any, Sphere]):
        """Insert a layer in this spec

        .. note::

            Ordering of layers is not based on ordering
            of the children as ARMI defines them, but the
            outer diameter of each individual layer

        """
        self._checkChildAndClearCacheBeforeAdding(obj)
        return super().insert(index, obj)

    def append(self, obj: Union[Any, Sphere]):
        """Append a layer to the children of this spec

        .. note::

            Ordering of layers is not based on ordering
            of the children as ARMI defines them, but the
            outer diameter of each individual layer

        """
        self._checkChildAndClearCacheBeforeAdding(obj)
        return super().append(obj)

    @property
    def layers(self) -> Tuple[Sphere]:
        if self._layers is None:
            self._layers = tuple(sorted(self))
        return self._layers

    def __lt__(self, other: Union["ParticleFuel", Any]) -> bool:
        """Is the outer diameter of the this spec less than that of another spec"""
        if isinstance(other, type(self)):
            mine = self.layers
            theirs = other.layers
            if mine is not None and theirs is not None:
                return mine[-1].getDimension("od") < theirs[-1].getDimension("od")
        return super().__lt__(other)
