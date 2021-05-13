"""
Make a Theta-R-Z grid
=====================

This builds a 3-D grid in Theta-R-Z geometry by specifying the theta, r, and z 
dimension bounds explicitly. 

Learn more about :py:mod:`grids <armi.reactor.grids>`.
"""
import itertools
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

from armi.reactor import grids
from armi import configure

configure(permissive=True)

fig = plt.figure()
theta = np.linspace(0, 2 * np.pi, 10)
rad = np.linspace(0, 10, 10)
z = np.linspace(5, 25, 6)
rz_grid = grids.ThetaRZGrid(bounds=(theta, rad, z))


xyz = []
for i, j, k in itertools.product(
    range(len(theta) - 1), range(len(rad) - 1), range(len(z) - 1)
):
    xyz.append(rz_grid[i, j, k].getGlobalCoordinates())
ax = fig.add_subplot(1, 1, 1, projection="3d")
x, y, z = zip(*xyz)
ax.scatter(x, y, z)

plt.show()
