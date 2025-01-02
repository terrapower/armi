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
from typing import TYPE_CHECKING, List, NoReturn, Optional

import numpy as np

from armi.reactor.grids.locations import IJType, LocationBase
from armi.reactor.grids.structuredGrid import StructuredGrid

if TYPE_CHECKING:
    from armi.reactor.composites import ArmiObject


class AxialGrid(StructuredGrid):
    """1-D grid in the k-direction (z).

    .. note::

        It is recommended to use :meth:`fromNCells` rather than calling
        the ``__init_`` constructor directly

    """

    @classmethod
    def fromNCells(
        cls, numCells: int, armiObject: Optional["ArmiObject"] = None
    ) -> "AxialGrid":
        """Produces an unit grid where each bin is 1-cm tall.

        ``numCells + 1`` mesh boundaries are added, since one block would
        require a bottom and a top.

        """
        # Need float bounds or else we truncate integers
        return cls(
            bounds=(None, None, np.arange(numCells + 1, dtype=np.float64)),
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
        """Grid spacing in the z-direction.

        Returns
        -------
        float
            Pitch in cm

        """
