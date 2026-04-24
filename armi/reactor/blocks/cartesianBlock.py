# Copyright 2026 TerraPower, LLC
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

"""Cartesian blocks can be square or more generically rectangular in cross section."""

import math

from armi.reactor import components
from armi.reactor.blocks.block import Block
from armi.reactor.flags import Flags


class CartesianBlock(Block):
    """
    A Cartesian Block is a vertical slice of an Assembly which is laid out on a Cartesian grid. That is, a grid that is
    square or rectangular.

    A Cartesian grid can have an origin that is in the middle of a grid cell:

    +---------+--------+--------+
    |         |        |        |
    | (-1,1)  | (0,1)  | (1,1)  |
    |         |        |        |
    +---------+--------+--------+
    |         |        |        |
    | (-1,0)  | (0,0)  | (1,0)  |
    |         |        |        |
    +---------+--------+--------+
    |         |        |        |
    | (-1,-1) | (0,-1) | (1,-1) |
    |         |        |        |
    +---------+--------+--------+

    Or the grid cells can be aligned so the origin is between the grid cells:

    +---------+---------+--------+--------+
    |         |         |        |        |
    | (-2,1)  | (-1,1)  | (0,1)  | (1,1)  |
    |         |         |        |        |
    +---------+---------+--------+--------+
    |         |         |        |        |
    | (-2,0)  | (-1,0)  | (0,0)  | (1,0)  |
    |         |         |        |        |
    +---------+---------+--------+--------+
    |         |         |        |        |
    | (-2,-1) | (-1,-1) | (0,-1) | (1,-1) |
    |         |         |        |        |
    +---------+---------+--------+--------+
    |         |         |        |        |
    | (-2,-2) | (-1,-2) | (0,-2) | (1,-2) |
    |         |         |        |        |
    +---------+---------+--------+--------+
    """

    PITCH_DIMENSION = "widthOuter"
    PITCH_COMPONENT_TYPE = components.Rectangle

    def getMaxArea(self):
        """Get area of this block if it were totally full."""
        xw, yw = self.getPitch()
        return xw * yw

    def setPitch(self, val, updateBolParams=False):
        raise NotImplementedError("Directly setting the pitch of a cartesian block is currently not supported.")

    def getSymmetryFactor(self):
        """Return a factor between 1 and N where 1/N is how much cut-off by symmetry lines this mesh cell is."""
        if self.core is not None:
            indices = self.spatialLocator.getCompleteIndices()
            if self.core.symmetry.isThroughCenterAssembly:
                if indices[0] == 0 and indices[1] == 0:
                    # central location
                    return 4.0
                elif indices[0] == 0 or indices[1] == 0:
                    # edge location
                    return 2.0

        return 1.0

    def getPinCenterFlatToFlat(self, cold=False):
        """Return the flat-to-flat distance between the centers of opposing pins (corner-2-corner) in the outer ring."""
        clad = self.getComponent(Flags.CLAD)
        nRings = self.numRingsToHoldNumCells(clad.getDimension("mult"))
        pinPitch = self.getPinPitch(cold=cold)
        pinPitchDist = math.sqrt(pinPitch[0] ** 2 + pinPitch[1] ** 2)

        if self.core.symmetry.isThroughCenterAssembly:
            return 2 * (nRings - 1) * pinPitchDist
        else:
            return ((2 * nRings) - 1) * pinPitchDist

    def getNumCellsGivenRings(self, nRings: int):
        """Calculate the number of cells in a Cartesian grid with a given number of rings.

        The logic here is separated out into two scenarios: one for when the origin is inside the center grid cell and
        one where the origin is on the line between grid cells.
        """
        if self.core.symmetry.isThroughCenterAssembly:
            return (2 * nRings - 1) ** 2
        else:
            return (2 * nRings) ** 2

    def numRingsToHoldNumCells(self, nCells: int):
        """Calculate the number of rings needed in a Cartesian grid to hold a given number of cells.

        The logic here is separated out into two scenarios: one for when the origin is inside the center grid cell and
        one where the origin is on the line between grid cells.
        """
        if self.core.symmetry.isThroughCenterAssembly:
            return math.ceil((math.sqrt(nCells) + 1) / 2.0)
        else:
            return math.ceil(math.sqrt(nCells) / 2.0)
