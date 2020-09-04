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
Visualization implementation for VTK files.

Limitations
-----------
This version of the VTK file writer comes with a number of limitations and/or aspects
that can be improved upon. For instance
 - Only the Block mesh and related parameters are exported to the VTK file. Adding
   Assembly and Core meshes is totally doable, and will be the product of future work.
   With more considerable effort, arbitrary component may be visualizable!
 - No efforts are made to de-duplicate the vertices in the mesh, so there are more
   vertices than needed. Some fancy canned algorithms probably exist to do this, and it
   wouldn't be too difficult to do here either. Also future work, but probably not super
   important unless dealing with really big meshes.
 - Nuclide number densities are not output, because thay are not longer formal
   parameters. These should be added by calling the code in database3 that writes them.
"""

import pathlib
from typing import List, Optional, Set, Tuple
import math

from pyevtk.hl import unstructuredGridToVTK
from pyevtk.vtk import VtkGroup, VtkHexahedron, VtkQuadraticHexahedron
import numpy

from armi import runLog
from armi.reactor import reactors
from armi.reactor import blocks
from armi.reactor import parameters
from armi.utils import hexagon
from armi.bookkeeping.db import database3
from armi.bookkeeping.visualization import dumper


# The hex prism cell type is not very well-documented, and so is not described in
# pyevtk. Digging into the header reveals that `16` does the trick.
_HEX_PRISM_TID = 16


class VtkMesh:
    """
    Container for VTK unstructured mesh data.

    This provides a container for the necessary data to describe a mesh to VTK (vertex
    locations, connectivity, offsets, cell types). It supports appending one set of mesh
    data onto another, handling the necessary index offsets.
    """

    def __init__(self, vertices, connectivity, offsets, cellTypes):
        """
        Parameters
        ----------
        vertices : numpy array
            An Nx3 numpy array with one row per (x,y,z) vertex
        connectivity : numpy array
            A 1-D array containing the vertex indices belonging to each cell
        offsets : numpy array
            A 1-D array containing the index of the first vertex for the next cell
        cellTypes : numpy array
            A 1-D array contining the cell type ID for each cell
        """
        self.vertices = vertices
        self.connectivity = connectivity
        self.offsets = offsets
        self.cellTypes = cellTypes

    @staticmethod
    def empty():
        return VtkMesh(
            numpy.empty((0, 3), dtype=numpy.float64),
            numpy.array([], dtype=numpy.int32),
            numpy.array([], dtype=numpy.int32),
            numpy.array([], dtype=numpy.int32),
        )

    @property
    def x(self):
        return numpy.array(self.vertices[:, 0])

    @property
    def y(self):
        return numpy.array(self.vertices[:, 1])

    @property
    def z(self):
        return numpy.array(self.vertices[:, 2])

    def append(self, other):
        """
        Add more cells to the mesh.
        """
        connectOffset = self.vertices.shape[0]
        offsetOffset = self.offsets[-1] if self.offsets.size > 0 else 0

        self.vertices = numpy.vstack((self.vertices, other.vertices))
        self.connectivity = numpy.append(
            self.connectivity, other.connectivity + connectOffset
        )
        self.offsets = numpy.append(self.offsets, other.offsets + offsetOffset)
        self.cellTypes = numpy.append(self.cellTypes, other.cellTypes)


class VtkDumper(dumper.VisFileDumper):
    """
    Dumper for VTK data.

    This handles writing unstructured meshes and associated Block parameter data to VTK
    files. The context manager keeps track of how many files have been written (one per
    time node), and creates a group/collection file when finished.
    """

    def __init__(self, baseName: str):
        self._baseName = baseName
        self._statesDumped: List[Tuple[str, float]] = []

    def dumpState(
        self,
        r: reactors.Reactor,
        includeParams: Optional[Set[str]] = None,
        excludeParams: Optional[Set[str]] = None,
    ):
        """
        Dump a reactor to a VTK file.

        Parameters
        ----------
        r : reactors.Reactor
            The reactor state to visualize
        includeParams : list of str, optional
            A list of parameter names to include in the viz file. Defaults to all
            params.
        excludeParams : list of str, optional
            A list of parameter names to exclude from the output. Defaults to no params.
        """

        cycle = r.p.cycle
        timeNode = r.p.timeNode

        # you never know...
        assert cycle < 1000
        assert timeNode < 1000

        # We avoid using cXnY, since VisIt doesn't support .pvd files, but *does* know
        # to lump data with similar file names and integers at the end.
        path = "{}_{:0>3}{:0>3}".format(self._baseName, cycle, timeNode)

        # include and exclude params are mutually exclusive
        if includeParams is not None and excludeParams is not None:
            raise ValueError(
                "includeParams and excludeParams can not both be used at the same time"
            )

        # make the mesh
        blks = r.core.getBlocks()
        mesh = _createReactorMesh(r)

        # collect param data
        allData = dict()
        for pDef in blocks.Block.pDefs.toWriteToDB(parameters.SINCE_ANYTHING):
            if includeParams is not None and pDef.name not in includeParams:
                continue
            if excludeParams is not None and pDef.name in excludeParams:
                continue

            data = []
            for b in blks:
                val = b.p[pDef.name]
                data.append(val)

            data = numpy.array(data)

            if data.dtype.kind == "S" or data.dtype.kind == "U":
                # no string support!
                continue
            if data.dtype.kind == "O":
                # datatype is "object", usually because it's jagged, or has Nones. We are
                # willing to try handling the Nones, but jagged also isnt visualizable.
                nones = numpy.where([d is None for d in data])[0]

                if len(nones) == data.shape[0]:
                    # all Nones, so give up
                    continue

                if len(nones) == 0:
                    # looks like Nones had nothing to do with it. bail
                    continue

                try:
                    data = database3.replaceNonesWithNonsense(data, pDef.name, nones=nones)
                except ValueError:
                    # Looks like we have some weird data. We might be able to handle it
                    # with more massaging, but probably not visualizable anyhow
                    continue

                if data.dtype.kind == "O":
                    # Didn't work
                    runLog.warning(
                        "The parameter data for  `{}` could not be coerced into "
                        "a native type for output; skipping.".format(pDef.name)
                    )
                    continue
            if len(data.shape) != 1:
                # We aren't interested in vector data on each block
                continue
            allData[pDef.name] = data

        fullPath = unstructuredGridToVTK(
            path,
            mesh.x,
            mesh.y,
            mesh.z,
            connectivity=mesh.connectivity,
            offsets=mesh.offsets,
            cell_types=mesh.cellTypes,
            cellData=allData,
        )

        self._statesDumped.append((fullPath, r.p.time))

    def __enter__(self):
        self._statesDumped = []

    def __exit__(self, type, value, traceback):
        if len(self._statesDumped) > 1:
            # multiple files need to be wrapped up into a group
            group = VtkGroup(self._baseName)
            for path, time in self._statesDumped:
                group.addFile(filepath=path, sim_time=time)
            group.save()


def _createReactorMesh(r: reactors.Reactor):
    mesh = VtkMesh.empty()
    for b in r.core.getBlocks():
        mesh.append(_createBlockMesh(b))

    return mesh


def _createBlockMesh(b: blocks.Block) -> VtkMesh:
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


def _createHexBlockMesh(b: blocks.HexBlock) -> VtkMesh:
    assert b.spatialLocator is not None

    zMin = b.p.zbottom
    zMax = b.p.ztop

    gridOffset = b.spatialLocator.getGlobalCoordinates()[:2]
    gridOffset = numpy.tile(gridOffset, (6, 1))

    pitch = b.getPitch()
    hexVerts2d = numpy.array(hexagon.corners(rotation=0)) * pitch
    hexVerts2d += gridOffset

    # we need a top and bottom hex
    hexVerts2d = numpy.vstack((hexVerts2d, hexVerts2d))

    # fold in z locations to get 3d coordinates
    hexVerts = numpy.hstack(
        (hexVerts2d, numpy.array([[zMin] * 6 + [zMax] * 6]).transpose())
    )

    return VtkMesh(
        hexVerts,
        numpy.array(list(range(12))),
        numpy.array([12]),
        numpy.array([_HEX_PRISM_TID]),
    )


def _createCartesianBlockMesh(b: blocks.CartesianBlock) -> VtkMesh:
    assert b.spatialLocator is not None

    zMin = b.p.zbottom
    zMax = b.p.ztop

    gridOffset = b.spatialLocator.getGlobalCoordinates()[:2]
    gridOffset = numpy.tile(gridOffset, (4, 1))

    pitch = b.getPitch()
    halfPitchX = pitch[0] * 0.5
    halfPitchY = pitch[0] * 0.5

    rectVerts = numpy.array(
        [
            [halfPitchX, halfPitchY],
            [-halfPitchX, halfPitchY],
            [-halfPitchX, -halfPitchY],
            [halfPitchX, -halfPitchY],
        ]
    )
    rectVerts += gridOffset

    # make top/bottom rectangles
    boxVerts = numpy.vstack((rectVerts, rectVerts))

    # fold in z coordinates
    boxVerts = numpy.hstack(
        (boxVerts, numpy.array([[zMin] * 4 + [zMax] * 4]).transpose())
    )

    return VtkMesh(
        boxVerts,
        numpy.array(list(range(8))),
        numpy.array([8]),
        numpy.array([VtkHexahedron.tid]),
    )


def _createTRZBlockMesh(b: blocks.ThRZBlock) -> VtkMesh:
    # There's no sugar-coating this one. It sucks.
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
    vertsXYZ = numpy.array(
        [[r * math.cos(th), r * math.sin(th), z] for r, th, z in vertsRTZ]
    )

    return VtkMesh(
        vertsXYZ,
        numpy.array(list(range(20))),
        numpy.array([20]),
        numpy.array([VtkQuadraticHexahedron.tid]),
    )
