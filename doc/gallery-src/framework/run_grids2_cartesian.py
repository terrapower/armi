"""
Make a Cartesian grid
=====================

This builds a Cartesian grid with squares 1 cm square, with the z-coordinates
provided explicitly. It is also offset in 3D space to X, Y, Z = 10, 5, 5 cm.

Learn more about :py:mod:`grids <armi.reactor.grids>`.
"""
import itertools
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from armi.reactor import grids
from armi import configure

configure(permissive=True)

fig = plt.figure()
zCoords = [1, 4, 8]
cartesian_grid = grids.Grid(
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
