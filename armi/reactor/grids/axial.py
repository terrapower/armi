from typing import Optional, TYPE_CHECKING

import numpy

from .grid import Grid

if TYPE_CHECKING:
    from armi.reactor.composites import ArmiObject


class AxialGrid(Grid):
    """1-D grid in the k-direction (z)

    .. note:::

        It is recommended to use :meth:`fromNCells` rather than calling
        the ``__init_`` constructor directly

    """

    @classmethod
    def fromNCells(
        cls, numCells: int, armiObject: Optional["ArmiObject"] = None
    ) -> "AxialGrid":
        """Produces an unit grid where each bin is 1-cm tall

        ``numCells + 1`` mesh boundaries are added, since one block would
        require a bottom and a top.

        """
        # Need float bounds or else we truncate integers
        return cls(
            bounds=(None, None, numpy.arange(numCells + 1, dtype=numpy.float64)),
            armiObject=armiObject,
        )


def axialUnitGrid(
    numCells: int, armiObject: Optional["ArmiObject"] = None
) -> AxialGrid:
    """
    Build a 1-D unit grid in the k-direction based on a number of times. Each mesh is 1cm wide.

    .. deprecated::

        Use :class:`AxialUnitGrid` class instead

    """
    return AxialGrid.fromNCells(numCells, armiObject)
