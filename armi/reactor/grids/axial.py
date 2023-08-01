from typing import List, Optional, TYPE_CHECKING, NoReturn
import warnings

import numpy

from .locations import IJType, LocationBase
from .structuredgrid import StructuredGrid

if TYPE_CHECKING:
    from armi.reactor.composites import ArmiObject


class AxialGrid(StructuredGrid):
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

    @staticmethod
    def getSymmetricEquivalents(indices: IJType) -> List[IJType]:
        return []

    @staticmethod
    def locatorInDomain(
        locator: LocationBase, symmetryOverlap: Optional[bool] = False
    ) -> NoReturn:
        raise NotImplementedError

    @staticmethod
    def getIndicesFromRingAndPos(ring: int, pos: int) -> NoReturn:
        raise NotImplementedError

    @staticmethod
    def getMinimumRings(n: int) -> NoReturn:
        raise NotImplementedError

    @staticmethod
    def getPositionsInRing(ring: int) -> NoReturn:
        raise NotImplementedError

    @staticmethod
    def overlapsWhichSymmetryLine(indices: IJType) -> None:
        return None

    @property
    def pitch(self) -> float:
        """Grid spacing in the z-direction

        Returns
        -------
        float
            Pitch in cm

        """


def axialUnitGrid(
    numCells: int, armiObject: Optional["ArmiObject"] = None
) -> AxialGrid:
    """
    Build a 1-D unit grid in the k-direction based on a number of times. Each mesh is 1cm wide.

    .. deprecated::

        Use :class:`AxialUnitGrid` class instead

    """
    warnings.warn(
        "Use grids.AxialGrid class rather than function",
        PendingDeprecationWarning,
        stacklevel=2,
    )
    return AxialGrid.fromNCells(numCells, armiObject)
