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
Support for dumping XDMF files.

`XDMF <http://www.xdmf.org/index.php/Main_Page>`_ is a data interchange format that
allows for separate representation of the data itself and a description of how those
data are to be interpreted. The data description ("light" data) lives in an XML file,
while the actual data (in our case, data to be plotted), as well as the data describing
the mesh ("hard" data) can be stored in HDF5 files, binary files, or embedded directly
into the XML file. In most cases, this allows for visualizing data directly out of an
ARMI database file. Using the ``XdmfDumper`` will produce an XML file (with an ``.xdmf``
extension) containing the description of data, as well as an HDF5 file containing the
mesh. Together with the input database, the ``.xdmf`` file can be opened in a
visualization tool that supports XDMF.

.. note::
    Paraview seems to have rather good support for XDMF, while VisIt does not. The main
    issue seems to be that VisIt does not properly render the general polyhedra that
    XDMF supports. Unfortunately, we __need__ to use this to show hexagonal geometries,
    since it's the only way to get a hexagonal prism without splitting up the mesh into
    wedges. To do that would require splitting the parameter data, which would defeat
    the main benefit of using XMDF in the first place (to be able to plot out of the
    original Database file). Cartesian and R-X-Theta geometries in VisIt seem to work
    fine.
"""

import io
import math
import pathlib
import xml.dom.minidom
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Set, Tuple

import h5py
import numpy as np

from armi import runLog
from armi.bookkeeping.db import database
from armi.bookkeeping.visualization import dumper, utils
from armi.reactor import assemblies, blocks, composites, reactors

_VTK_TO_XDMF_CELLS = {16: 16}

_POLYHEDRON = 16
_HEXAHEDRON = 9
_QUADRATIC_HEXAHEDRON = 48

# The topology of a hexagonal prism, represented as a general polyhedron. To get this in
# proper XDMF, these need to be offset to the proper vertex indices in the full mesh,
# and have the number of face vertices inserted into the proper locations (notice the
# [0] placeholders).
_HEX_PRISM_TOPO = np.array(
    [0]
    + list(range(6))
    + [0]
    + list(range(6, 12))
    + [0]
    + [0, 1, 7, 6]
    + [0]
    + [1, 2, 8, 7]
    + [0]
    + [2, 3, 9, 8]
    + [0]
    + [3, 4, 10, 9]
    + [0]
    + [4, 5, 11, 10]
    + [0]
    + [5, 0, 6, 11]
)

# The indices of the placeholder zeros from _HEX_PRISM_TOPO array above
_HEX_PRISM_FACE_SIZE_IDX = np.array([0, 7, 14, 19, 24, 29, 34, 39])

# The number of vertices for each face
_HEX_PRISM_FACE_SIZES = np.array([6, 6, 4, 4, 4, 4, 4, 4])


def _getAttributesFromDataset(d: h5py.Dataset) -> Dict[str, str]:
    dataType = {
        np.dtype("int32"): "Int",
        np.dtype("int64"): "Int",
        np.dtype("float32"): "Float",
        np.dtype("float64"): "Float",
    }[d.dtype]

    precision = {
        np.dtype("int32"): "4",
        np.dtype("int64"): "8",
        np.dtype("float32"): "4",
        np.dtype("float64"): "8",
    }[d.dtype]

    return {
        "Dimensions": " ".join(str(i) for i in d.shape),
        "DataType": dataType,
        "Precision": precision,
        "Format": "HDF",
    }


class XdmfDumper(dumper.VisFileDumper):
    """
    VisFileDumper implementation for XDMF format.

    The general strategy of this dumper is to create a new HDF5 file that contains just
    the necessary mesh information for each dumped time step. The XML that
    describes/points to these data is stored internally as ``ElementTree`` objects until
    the end. When all time steps have been processed, these elements have time
    information added to them, and are collected into a "TemporalCollection" Grid and
    written to an ``.xdmf`` file.
    """

    def __init__(self, baseName: str, inputName: Optional[str] = None):
        self._baseName = baseName
        if inputName is None:
            runLog.warning(
                "No input database name was given, so only an XMDF mesh will be created"
            )
        self._inputName = inputName

        # Check that the inputName is a relative path. XDMF doesn't seem to like
        # absolute paths; at least on windows with ParaView
        if pathlib.Path(inputName).is_absolute():
            raise ValueError(
                "XDMF tools tend not to like absolute paths; provide a "
                "relative path to the input database."
            )

        self._meshH5 = None
        self._inputDb = None
        self._times = []
        self._blockGrids = []
        self._assemGrids = []

    def __enter__(self):
        """
        Prepare to write states.

        The dumper keeps track of ``<Grid>`` tags that need to be written into a
        Collection at the end. This also opens an auxiliary HDF5 file for writing meshes
        at each time step.
        """
        self._meshH5 = h5py.File(self._baseName + "_mesh.h5", "w")

        if self._inputName is None:
            # we could handle the case where the database wasn't passed by pumping state
            # into a new h5 file, but why?
            raise ValueError("Input database needed to generate XDMF output!")

        self._inputDb = database.Database(self._inputName, "r")
        with self._inputDb as db:
            dbVersion = db.version

        if math.floor(float(dbVersion)) != 3:
            raise ValueError(
                "XDMF output requires Database version 3. Got version `{}`".format(
                    dbVersion
                )
            )

        self._times = []
        self._blockGrids = []
        self._assemGrids = []

    def __exit__(self, type, value, traceback):
        """
        Finalize file writing.

        This writes all of the ``<Grid>`` tags into a Collection for all time steps, and
        closes the input database and mesh-bearing HDF5 file.
        """
        self._meshH5.close()
        self._meshH5 = None
        if self._inputDb is not None:
            self._inputDb.close()
            self._inputDb = None

        timeCollectionBlk = ET.Element(
            "Grid", attrib={"GridType": "Collection", "CollectionType": "Temporal"}
        )
        timeCollectionAsm = ET.Element(
            "Grid", attrib={"GridType": "Collection", "CollectionType": "Temporal"}
        )

        # make sure all times are unique. Paraview will crash if they are not
        times = self._dedupTimes(self._times)

        for aGrid, bGrid, time in zip(self._assemGrids, self._blockGrids, times):
            timeElement = ET.Element(
                "Time", attrib={"TimeType": "Single", "Value": str(time)}
            )
            bGrid.append(timeElement)
            timeCollectionBlk.append(bGrid)

            aGrid.append(timeElement)
            timeCollectionAsm.append(aGrid)

        for collection, typ in [
            (timeCollectionBlk, "_blk"),
            (timeCollectionAsm, "_asm"),
        ]:
            xdmf = ET.Element("Xdmf", attrib={"Version": "3.0"})
            domain = ET.Element("Domain", attrib={"Name": "Reactor"})

            domain.append(collection)
            xdmf.append(domain)

            # Write to an internal buffer so that we can print more fancy below
            tree = ET.ElementTree(element=xdmf)
            buf = io.StringIO()
            tree.write(buf, encoding="unicode")
            buf.seek(0)

            # Round-trip through minidom to do the pretty print
            dom = xml.dom.minidom.parse(buf)
            with open(self._baseName + typ + ".xdmf", "w") as f:
                f.write(dom.toprettyxml())

    @staticmethod
    def _dedupTimes(times: List[float]) -> List[float]:
        """
        Make sure that no two times are the same.

        Duplicates will be resolved by bumping each subsequent duplicate time forward by
        some epsilon, cascading following duplicates by the same amount until no
        duplicates remain. This will fail in the case where there are already times that
        are within Ndup*epsilon of each other. In such cases, this function probably
        isn't valid anyways.
        """
        assert all(
            a <= b for a, b in zip(times, times[1:])
        ), "Input list must be sorted"

        # This should be used as a multiplicative epsilon, to avoid precision issues
        # with large times
        _EPS = 1.0e-9

        # ...except when close enough to 0. Floating-point is a pain
        mapZeroToOne = lambda x: x if x > _EPS else 1.0

        dups = [0] * len(times)

        # We iterate in reverse so that each entry in dups will contain the number of
        # duplicate entries that **precede** it
        for i in reversed(range(len(times))):
            ti = times[i]
            nDup = 0
            for j in range(i - 1, -1, -1):
                if times[j] == ti:
                    nDup += 1
                else:
                    break
            dups[i] = nDup

        return [t + dups * _EPS * mapZeroToOne(t) for dups, t in zip(dups, times)]

    def dumpState(
        self,
        r: reactors.Reactor,
        includeParams: Optional[Set[str]] = None,
        excludeParams: Optional[Set[str]] = None,
    ):
        """Produce a ``<Grid>`` for a single timestep, as well as supporting HDF5 datasets."""
        cycle = r.p.cycle
        node = r.p.timeNode

        timeGroupName = database.getH5GroupName(cycle, node)

        # careful here! we are trying to use the database datasets as the source of hard
        # data without copying, so the order that we make the mesh needs to be the same
        # order as the data in the database. There is no guarantee that the way a loaded
        # reactor is ordered is the same way that it was ordered in the database (though
        # perhaps we should do some work to specify that better). We need to look at the
        # layout in the input database to re-order the objects.
        with self._inputDb as db:
            layout = db.getLayout(cycle, node)

        snToIdx = {sn: i for i, sn in zip(layout.indexInData, layout.serialNum)}

        blks = r.getChildren(deep=True, predicate=lambda o: isinstance(o, blocks.Block))
        blks = sorted(blks, key=lambda b: snToIdx[b.p.serialNum])

        assems = r.getChildren(
            deep=True, predicate=lambda o: isinstance(o, assemblies.Assembly)
        )
        assems = sorted(assems, key=lambda a: snToIdx[a.p.serialNum])

        blockGrid = self._makeBlockMesh(r, snToIdx)
        self._collectObjectData(blks, timeGroupName, blockGrid)

        assemGrid = self._makeAssemblyMesh(r, snToIdx)
        self._collectObjectData(assems, timeGroupName, assemGrid)

        self._blockGrids.append(blockGrid)
        self._assemGrids.append(assemGrid)
        self._times.append(r.p.time)

    def _collectObjectData(
        self, objs: List[composites.ArmiObject], timeGroupName, node: ET.Element
    ):
        """
        Scan for things that look plottable in the input database.

        "Plottable" things are anything that have int or float data, and the same number
        of elements as there are objects.

        .. warning::
            This makes some assumptions as to the structure of the database.
        """
        if self._inputDb is None:
            # If we weren't given a database to draw data from, we will just skip this
            # for now. Most of the time, a dumper should have an input database.
            # Otherwise, this **could** extract from the reactor state.
            return

        typeNames = {type(o).__name__ for o in objs}
        if len(typeNames) != 1:
            raise ValueError("Currently only supporting homogeneous block types")
        typeName = next(iter(typeNames))
        dataGroupName = "/".join((timeGroupName, typeName))
        with self._inputDb as db:
            for key, val in db.h5db[dataGroupName].items():
                if val.shape != (len(objs),):
                    continue
                try:
                    dataItem = ET.Element(
                        "DataItem", attrib=_getAttributesFromDataset(val)
                    )
                except KeyError:
                    continue
                dataItem.text = ":".join((db.fileName, val.name))
                attrib = ET.Element(
                    "Attribute",
                    attrib={"Name": key, "Center": "Cell", "AttributeType": "Scalar"},
                )
                attrib.append(dataItem)
                node.append(attrib)

    def _makeBlockMesh(self, r: reactors.Reactor, indexMap) -> ET.Element:
        cycle = r.p.cycle
        node = r.p.timeNode

        blks = r.getChildren(deep=True, predicate=lambda o: isinstance(o, blocks.Block))
        blks = sorted(blks, key=lambda b: indexMap[b.p.serialNum])

        groupName = "c{}n{}".format(cycle, node)

        # VTK stuff turns out to be pretty flexible
        blockMesh = utils.VtkMesh.empty()
        for b in blks:
            blockMesh.append(utils.createBlockMesh(b))

        verts = blockMesh.vertices

        verticesInH5 = groupName + "/blk_vertices"
        self._meshH5[verticesInH5] = verts

        topoValues = np.array([], dtype=np.int32)
        offset = 0
        for b in blks:
            nVerts, cellTopo = _getTopologyFromShape(b, offset)
            topoValues = np.append(topoValues, cellTopo)
            offset += nVerts

        topoInH5 = groupName + "/blk_topology"
        self._meshH5[topoInH5] = topoValues

        return self._makeGenericMesh(
            "Blocks", len(blks), self._meshH5[verticesInH5], self._meshH5[topoInH5]
        )

    def _makeAssemblyMesh(self, r: reactors.Reactor, indexMap) -> ET.Element:
        cycle = r.p.cycle
        node = r.p.timeNode
        asys = r.getChildren(
            deep=True, predicate=lambda o: isinstance(o, assemblies.Assembly)
        )
        asys = sorted(asys, key=lambda b: indexMap[b.p.serialNum])

        groupName = "c{}n{}".format(cycle, node)

        # VTK stuff turns out to be pretty flexible
        assemMesh = utils.VtkMesh.empty()
        for assem in asys:
            assemMesh.append(utils.createAssemMesh(assem))

        verts = assemMesh.vertices

        verticesInH5 = groupName + "/asy_vertices"
        self._meshH5[verticesInH5] = verts

        topoValues = np.array([], dtype=np.int32)
        offset = 0
        for a in asys:
            nVerts, cellTopo = _getTopologyFromShape(a[0], offset)
            topoValues = np.append(topoValues, cellTopo)
            offset += nVerts

        topoInH5 = groupName + "/asy_topology"
        self._meshH5[topoInH5] = topoValues

        return self._makeGenericMesh(
            "Assemblies", len(asys), self._meshH5[verticesInH5], self._meshH5[topoInH5]
        )

    @staticmethod
    def _makeGenericMesh(
        name: str, nCells: int, vertexData: h5py.Dataset, topologyData: h5py.Dataset
    ) -> ET.Element:
        grid = ET.Element("Grid", attrib={"GridType": "Uniform", "Name": name})
        geometry = ET.Element("Geometry", attrib={"GeometryType": "XYZ"})
        geomData = ET.Element(
            "DataItem",
            attrib={
                "Dimensions": "{} {}".format(*vertexData.shape),
                "NumberType": "Float",
                "Format": "HDF",
            },
        )

        geomData.text = ":".join((vertexData.file.filename, vertexData.name))
        geometry.append(geomData)

        topology = ET.Element(
            "Topology",
            attrib={"TopologyType": "Mixed", "NumberOfElements": str(nCells)},
        )

        topoData = ET.Element(
            "DataItem",
            attrib={
                "Dimensions": "{}".format(topologyData.size),
                "NumberType": "Int",
                "Format": "HDF",
            },
        )
        topoData.text = ":".join((topologyData.file.filename, topologyData.name))
        topology.append(topoData)

        grid.append(geometry)
        grid.append(topology)

        return grid


def _getTopologyFromShape(b: blocks.Block, offset: int) -> Tuple[int, List[int]]:
    """
    Returns the number of vertices used to make the shape, and XDMF topology values.

    The size of the XDMF topology values cannot be used directly in computing the next
    offset because it sometimes contains vertex indices __and__ sizing information.
    """
    if isinstance(b, blocks.HexBlock):
        # polyhedron, 8 faces
        prefix = [_POLYHEDRON, 8]
        topo = _HEX_PRISM_TOPO + offset
        topo[_HEX_PRISM_FACE_SIZE_IDX] = _HEX_PRISM_FACE_SIZES
        topo = np.append(prefix, topo)

        return 12, topo

    if isinstance(b, blocks.CartesianBlock):
        return (
            8,
            [
                _HEXAHEDRON,
            ]
            + list(range(offset, offset + 8)),
        )
    if isinstance(b, blocks.ThRZBlock):
        return 20, [_QUADRATIC_HEXAHEDRON] + list(range(offset, offset + 20))

    else:
        raise TypeError("Unsupported block type `{}`".format(type(b)))
