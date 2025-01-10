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
# ruff: noqa: F401
from typing import Optional, Tuple

from armi.reactor.grids.axial import AxialGrid
from armi.reactor.grids.cartesian import CartesianGrid
from armi.reactor.grids.constants import (
    BOUNDARY_0_DEGREES,
    BOUNDARY_60_DEGREES,
    BOUNDARY_120_DEGREES,
    BOUNDARY_CENTER,
)
from armi.reactor.grids.grid import Grid
from armi.reactor.grids.hexagonal import COS30, SIN30, TRIANGLES_IN_HEXAGON, HexGrid
from armi.reactor.grids.locations import (
    CoordinateLocation,
    IndexLocation,
    LocationBase,
    MultiIndexLocation,
    addingIsValid,
)
from armi.reactor.grids.structuredGrid import GridParameters, StructuredGrid, _tuplify
from armi.reactor.grids.thetarz import TAU, ThetaRZGrid


def locatorLabelToIndices(label: str) -> Tuple[int, int, Optional[int]]:
    """
    Convert a locator label to numerical i,j,k indices.

    If there are only i,j  indices, make the last item None
    """
    intVals = tuple(int(idx) for idx in label.split("-"))
    if len(intVals) == 2:
        intVals = (intVals[0], intVals[1], None)
    return intVals
