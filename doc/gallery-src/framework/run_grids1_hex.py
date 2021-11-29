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
Make a hex grid
===============

This uses a grid factory method to build an infinite 2-D grid of hexagons with pitch
equal to 1.0 cm.

Learn more about :py:mod:`grids <armi.reactor.grids>`.
"""
import math

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection

from armi.reactor import grids
from armi import configure

configure(permissive=True)

hexes = grids.HexGrid.fromPitch(1.0)

fig = plt.figure()
xyz = []
polys = []
ax = fig.add_subplot(1, 1, 1)
for hex_i in hexes.generateSortedHexLocationList(127):
    x, y, z = hex_i.getGlobalCoordinates()
    ax.text(x, y, f"{hex_i.i},{hex_i.j}", ha="center", va="center")
    polys.append(
        mpatches.RegularPolygon(
            (x, y), numVertices=6, radius=1 / math.sqrt(3), orientation=math.pi / 2
        )
    )
patches = PatchCollection(polys, fc="white", ec="k")
ax.add_collection(patches)
ax.set_title("(i, j) indices for a hex grid")
ax.set_xlim([-7, 7])
ax.set_ylim([-7, 7])
plt.show()
