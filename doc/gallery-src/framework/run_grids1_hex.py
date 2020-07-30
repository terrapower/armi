"""
Make a hex grid
===============

This uses a grid factory method to build an infinite 2-D grid of hexagons with pitch
equal to 1.0 cm. 

Learn more about :py:mod:`grids <armi.reactor.grids>`.
"""
import matplotlib.pyplot as plt

from armi.reactor import grids

import armi

armi.configure()

hexes = grids.HexGrid.fromPitch(1.0)

fig = plt.figure()
xyz = []

ax = fig.add_subplot(1, 1, 1)
for hex_i in hexes.generateSortedHexLocationList(127):
    xyz.append(hex_i.getGlobalCoordinates())
x, y, z = zip(*xyz)
ax.plot(x, y, "o")
plt.show()
