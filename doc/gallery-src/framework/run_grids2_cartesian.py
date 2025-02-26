# Copyright 2019 TerraPower, LLC
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
"""
Make a Cartesian grid.
======================

This builds a Cartesian grid with squares 1 cm square, with the z-coordinates
provided explicitly. It is also offset in 3D space to X, Y, Z = 10, 5, 5 cm.

Learn more about :py:mod:`grids <armi.reactor.grids>`.
"""

import itertools

import matplotlib.pyplot as plt

from armi import configure
from armi.reactor import grids

configure(permissive=True)

fig = plt.figure()
zCoords = [1, 4, 8]
cartesian_grid = grids.CartesianGrid(
    unitSteps=((1, 0), (0, 1)),
    bounds=(None, None, zCoords),
    offset=(10, 5, 5),
)
xyz = []

# the grid is infinite in i and j so we will just plot the first 10 items
for i, j, k in itertools.product(range(10), range(10), range(len(zCoords) - 1)):
    xyz.append(cartesian_grid[i, j, k].getGlobalCoordinates())
ax = fig.add_subplot(1, 1, 1, projection="3d")
x, y, z = zip(*xyz)
ax.scatter(x, y, z)
plt.show()
