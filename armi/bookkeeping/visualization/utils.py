# Copyright 2020 TerraPower, LLC
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
Utility classes/functions for visualization.

Most of these are derived from the VTK format, which tends to be general enough to
support other formats. Most of the work goes into figuring out where the vertices should
be for a given block/assembly shape. If this coupling becomes problematic, abstractions
for primitive shapes should be created.
"""

import math

import numpy as np
from pyevtk.hl import unstructuredGridToVTK
from pyevtk.vtk import VtkHexahedron, VtkQuadraticHexahedron

from armi.reactor import assemblies, blocks, reactors
from armi.utils import hexagon

# The hex prism cell type is not very well-documented, and so is not described in
# pyevtk. Digging into the header reveals that `16` does the trick.
_HEX_PRISM_TID = 16


class VtkMesh:
    """
    Container for VTK unstructured mesh data.

    This provides a container for the necessary data to describe a mesh to VTK (vertex
    locations, connectivity, offsets, cell types). It supports appending one set of mesh
    data onto another, handling the necessary index offsets.

    While the specifics are somewhat specific to the VTK format, the concept of storing
    a bunch of vertices and their connectivity is a relatively general one, so this may
    be of use to other formats as well.
    """

    def __init__(self, vertices, connectivity, offsets, cellTypes):
        """
        Parameters
        ----------
        vertices : np.ndarray
            An Nx3 numpy array with one row per (x,y,z) vertex
        connectivity : np.ndarray
            A 1-D array containing the vertex indices belonging to each cell
        offsets : np.ndarray
            A 1-D array containing the index of the first vertex for the next cell
        cellTypes : np.ndarray
            A 1-D array containing the cell type ID for each cell
        """
        self.vertices = vertices
        self.connectivity = connectivity
        self.offsets = offsets
        self.cellTypes = cellTypes

    @staticmethod
    def empty():
        return VtkMesh(
            np.empty((0, 3), dtype=np.float64),
            np.array([], dtype=np.int32),
            np.array([], dtype=np.int32),
            np.array([], dtype=np.int32),
        )

    @property
    def x(self):
        return np.array(self.vertices[:, 0])

    @property
    def y(self):
        return np.array(self.vertices[:, 1])

    @property
    def z(self):
        return np.array(self.vertices[:, 2])

    def append(self, other):
        """Add more cells to the mesh."""
        connectOffset = self.vertices.shape[0]
        offsetOffset = self.offsets[-1] if self.offsets.size > 0 else 0

        self.vertices = np.vstack((self.vertices, other.vertices))
        self.connectivity = np.append(
            self.connectivity, other.connectivity + connectOffset
        )
        self.offsets = np.append(self.offsets, other.offsets + offsetOffset)
        self.cellTypes = np.append(self.cellTypes, other.cellTypes)

    def write(self, path, data) -> str:
        """
        Write this mesh and the passed data to a VTK file. Returns the base path, plus
        relevant extension.
        """
        fullPath = unstructuredGridToVTK(
            path,
            self.x,
            self.y,
            self.z,
            connectivity=self.connectivity,
            offsets=self.offsets,
            cell_types=self.cellTypes,
            cellData=data,
        )
        return fullPath


def createReactorBlockMesh(r: reactors.Reactor) -> VtkMesh:
    mesh = VtkMesh.empty()
    blks = r.getChildren(deep=True, predicate=lambda o: isinstance(o, blocks.Block))
    for b in blks:
        mesh.append(createBlockMesh(b))

    return mesh


def createReactorAssemMesh(r: reactors.Reactor) -> VtkMesh:
    mesh = VtkMesh.empty()
    assems = r.getChildren(
        deep=True, predicate=lambda o: isinstance(o, assemblies.Assembly)
    )
    for a in assems:
        mesh.append(createAssemMesh(a))

    return mesh


def createBlockMesh(b: blocks.Block) -> VtkMesh:
    if isinstance(b, blocks.HexBlock):
        return _createHexBlockMesh(b)
    if isinstance(b, blocks.CartesianBlock):
        return _createCartesianBlockMesh(b)
    if isinstance(b, blocks.ThRZBlock):
        return _createTRZBlockMesh(b)
    else:
        raise TypeError(
            "Unsupported block type `{}`. Supported types are: {}".format(
                type(b).__name__,
                {
                    t.__name__
                    for t in {blocks.CartesianBlock, blocks.HexBlock, blocks.ThRZBlock}
                },
            )
        )


def createAssemMesh(a: assemblies.Assembly) -> VtkMesh:
    # Kind of hacky, but since all blocks in an assembly are the same type, let's just
    # use the block mesh functions and change their z coordinates to match the size of
    # the whole assem 🤯
    mesh = createBlockMesh(a[0])

    # we should only have a single VTK mesh primitive per block
    assert len(mesh.cellTypes) == 1

    zMin = a.spatialGrid._bounds[2][0]
    zMax = a.spatialGrid._bounds[2][-1]

    if mesh.cellTypes[0] == VtkHexahedron:
        mesh.vertices[0:4, 2] = zMin
        mesh.vertices[4:8, 2] = zMax
    elif mesh.cellTypes[0] == _HEX_PRISM_TID:
        mesh.vertices[0:6, 2] = zMin
        mesh.vertices[6:12, 2] = zMax
    elif mesh.cellTypes[0] == VtkQuadraticHexahedron.tid:
        # again, quadratic hexahedra are a pain
        mesh.vertices[0:4, 2] = zMin
        mesh.vertices[8:12, 2] = zMin
        mesh.vertices[4:8, 2] = zMax
        mesh.vertices[12:16, 2] = zMax

    return mesh


def _createHexBlockMesh(b: blocks.HexBlock) -> VtkMesh:
    assert b.spatialLocator is not None

    zMin = b.p.zbottom
    zMax = b.p.ztop

    gridOffset = b.spatialLocator.getGlobalCoordinates()[:2]
    gridOffset = np.tile(gridOffset, (6, 1))

    pitch = b.getPitch()
    hexVerts2d = np.array(hexagon.corners(rotation=0)) * pitch
    hexVerts2d += gridOffset

    # we need a top and bottom hex
    hexVerts2d = np.vstack((hexVerts2d, hexVerts2d))

    # fold in z locations to get 3d coordinates
    hexVerts = np.hstack((hexVerts2d, np.array([[zMin] * 6 + [zMax] * 6]).transpose()))

    return VtkMesh(
        hexVerts,
        np.array(list(range(12))),
        np.array([12]),
        np.array([_HEX_PRISM_TID]),
    )


def _createCartesianBlockMesh(b: blocks.CartesianBlock) -> VtkMesh:
    assert b.spatialLocator is not None

    zMin = b.p.zbottom
    zMax = b.p.ztop

    gridOffset = b.spatialLocator.getGlobalCoordinates()[:2]
    gridOffset = np.tile(gridOffset, (4, 1))

    pitch = b.getPitch()
    halfPitchX = pitch[0] * 0.5
    halfPitchY = pitch[0] * 0.5

    rectVerts = np.array(
        [
            [halfPitchX, halfPitchY],
            [-halfPitchX, halfPitchY],
            [-halfPitchX, -halfPitchY],
            [halfPitchX, -halfPitchY],
        ]
    )
    rectVerts += gridOffset

    # make top/bottom rectangles
    boxVerts = np.vstack((rectVerts, rectVerts))

    # fold in z coordinates
    boxVerts = np.hstack((boxVerts, np.array([[zMin] * 4 + [zMax] * 4]).transpose()))

    return VtkMesh(
        boxVerts,
        np.array(list(range(8))),
        np.array([8]),
        np.array([VtkHexahedron.tid]),
    )


def _createTRZBlockMesh(b: blocks.ThRZBlock) -> VtkMesh:
    # This could be improved.
    rIn = b.radialInner()
    rOut = b.radialOuter()
    thIn = b.thetaInner()
    thOut = b.thetaOuter()
    zIn = b.p.zbottom
    zOut = b.p.ztop

    vertsRTZ = [
        (rIn, thOut, zIn),
        (rIn, thIn, zIn),
        (rOut, thIn, zIn),
        (rOut, thOut, zIn),
        (rIn, thOut, zOut),
        (rIn, thIn, zOut),
        (rOut, thIn, zOut),
        (rOut, thOut, zOut),
        (rIn, (thIn + thOut) * 0.5, zIn),
        ((rIn + rOut) * 0.5, thIn, zIn),
        (rOut, (thIn + thOut) * 0.5, zIn),
        ((rIn + rOut) * 0.5, thOut, zIn),
        (rIn, (thIn + thOut) * 0.5, zOut),
        ((rIn + rOut) * 0.5, thIn, zOut),
        (rOut, (thIn + thOut) * 0.5, zOut),
        ((rIn + rOut) * 0.5, thOut, zOut),
        (rIn, thOut, (zIn + zOut) * 0.5),
        (rIn, thIn, (zIn + zOut) * 0.5),
        (rOut, thIn, (zIn + zOut) * 0.5),
        (rOut, thOut, (zIn + zOut) * 0.5),
    ]
    vertsXYZ = np.array(
        [[r * math.cos(th), r * math.sin(th), z] for r, th, z in vertsRTZ]
    )

    return VtkMesh(
        vertsXYZ,
        np.array(list(range(20))),
        np.array([20]),
        np.array([VtkQuadraticHexahedron.tid]),
    )
