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
from typing import TYPE_CHECKING, Optional, NoReturn

import numpy

from armi.reactor.grids.locations import IJType, IJKType
from armi.reactor.grids.structuredgrid import StructuredGrid

if TYPE_CHECKING:
    # Avoid circular imports
    from armi.reactor.composites import ArmiObject

TAU = math.tau


class ThetaRZGrid(StructuredGrid):
    """
    A grid characterized by azimuthal, radial, and zeta indices.

    The angular meshes are limited to 0 to 2pi radians. R and Zeta are as in other
    meshes.

    It is recommended to call :meth:`fromGeom` to construct,
    rather than directly constructing with ``__init__``

    See Figure 2.2 in Derstine 1984, ANL. [DIF3D]_.
    """

    def getSymmetricEquivalents(self, indices: IJType) -> NoReturn:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support symmetric equivalents"
        )

    @classmethod
    def fromGeom(cls, geom, armiObject: Optional["ArmiObject"] = None) -> "ThetaRZGrid":
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
    def getIndicesFromRingAndPos(ring: int, pos: int) -> IJType:
        return (pos - 1, ring - 1)

    def getCoordinates(self, indices, nativeCoords=False) -> numpy.ndarray:
        meshCoords = theta, r, z = super().getCoordinates(
            indices, nativeCoords=nativeCoords
        )
        if not 0 <= theta <= TAU:
            raise ValueError("Invalid theta value: {}. Check mesh.".format(theta))
        if nativeCoords:
            # return Theta, R, Z values directly.
            return meshCoords
        else:
            # return x, y ,z
            return numpy.array((r * math.cos(theta), r * math.sin(theta), z))

    def indicesOfBounds(
        self,
        rad0: float,
        rad1: float,
        theta0: float,
        theta1: float,
        sigma: float = 1e-4,
    ) -> IJKType:
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

    @staticmethod
    def locatorInDomain(*args, **kwargs) -> bool:
        """
        ThetaRZGrids do not check for bounds, though they could if that becomes a
        problem.
        """
        return True

    @staticmethod
    def getMinimumRings(n: int) -> NoReturn:
        raise NotImplementedError

    @staticmethod
    def getPositionsInRing(ring: int) -> NoReturn:
        raise NotImplementedError

    @staticmethod
    def overlapsWhichSymmetryLine(indices: IJType) -> None:
        return None

    @staticmethod
    def pitch() -> NoReturn:
        raise NotImplementedError()
