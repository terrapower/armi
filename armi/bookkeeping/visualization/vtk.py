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
that can be improved upon. For instance:

* Only the Block and Assembly meshes and related parameters are exported to the VTK
  file. Adding Core data is totally doable, and will be the product of future work.
  With more considerable effort, arbitrary components may be visualizable!
* No efforts are made to de-duplicate the vertices in the mesh, so there are more
  vertices than needed. Some fancy canned algorithms probably exist to do this, and it
  wouldn't be too difficult to do here either. Also future work, but probably not super
  important unless dealing with really big meshes.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from pyevtk.vtk import VtkGroup

from armi import runLog
from armi.bookkeeping.db import database
from armi.bookkeeping.visualization import dumper, utils
from armi.reactor import assemblies, blocks, composites, parameters, reactors


class VtkDumper(dumper.VisFileDumper):
    """
    Dumper for VTK data.

    This handles writing unstructured meshes and associated Block parameter data to VTK
    files. The context manager keeps track of how many files have been written (one per
    time node), and creates a group/collection file when finished.
    """

    def __init__(self, baseName: str, inputName: str):
        self._baseName = baseName
        self._assemFiles: List[Tuple[str, float]] = []
        self._blockFiles: List[Tuple[str, float]] = []

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
        blockPath = "{}_blk_{:0>3}{:0>3}".format(self._baseName, cycle, timeNode)
        assemPath = "{}_asy_{:0>3}{:0>3}".format(self._baseName, cycle, timeNode)

        # include and exclude params are mutually exclusive
        if includeParams is not None and excludeParams is not None:
            raise ValueError(
                "includeParams and excludeParams can not both be used at the same time"
            )

        blks = r.getChildren(deep=True, predicate=lambda o: isinstance(o, blocks.Block))
        assems = r.getChildren(
            deep=True, predicate=lambda o: isinstance(o, assemblies.Assembly)
        )

        blockMesh = utils.createReactorBlockMesh(r)
        assemMesh = utils.createReactorAssemMesh(r)

        # collect param data
        blockData = _collectObjectData(blks, includeParams, excludeParams)
        assemData = _collectObjectData(assems, includeParams, excludeParams)
        # block number densities are special, since they aren't stored as params
        blockNdens = database.collectBlockNumberDensities(blks)
        # we need to copy the number density vectors to guarantee unit stride, which
        # pyevtk requires. Kinda seems like something it could do for us, but oh well.
        blockNdens = {key: np.array(value) for key, value in blockNdens.items()}
        blockData.update(blockNdens)

        fullPath = blockMesh.write(blockPath, blockData)
        self._blockFiles.append((fullPath, r.p.time))

        fullPath = assemMesh.write(assemPath, assemData)
        self._assemFiles.append((fullPath, r.p.time))

    def __enter__(self):
        self._assemFiles = []
        self._blockFiles = []

    def __exit__(self, type, value, traceback):
        assert len(self._assemFiles) == len(self._blockFiles)
        if len(self._assemFiles) > 1:
            # multiple files need to be wrapped up into groups. VTK does not like having
            # multiple meshes in the same group, so we write out separate Collection
            # files for them
            asyGroup = VtkGroup(f"{self._baseName}_asm")
            for path, time in self._assemFiles:
                asyGroup.addFile(filepath=path, sim_time=time)
            asyGroup.save()

            blockGroup = VtkGroup(f"{self._baseName}_blk")
            for path, time in self._blockFiles:
                blockGroup.addFile(filepath=path, sim_time=time)
            blockGroup.save()


def _collectObjectData(
    objs: List[composites.ArmiObject],
    includeParams: Optional[Set[str]] = None,
    excludeParams: Optional[Set[str]] = None,
) -> Dict[str, Any]:

    allData = dict()

    for pDef in type(objs[0]).pDefs.toWriteToDB(parameters.SINCE_ANYTHING):
        if includeParams is not None and pDef.name not in includeParams:
            continue
        if excludeParams is not None and pDef.name in excludeParams:
            continue

        data = []
        for obj in objs:
            val = obj.p[pDef.name]
            data.append(val)

        data = np.array(data)

        if data.dtype.kind == "S" or data.dtype.kind == "U":
            # no string support!
            continue
        if data.dtype.kind == "O":
            # datatype is "object", usually because it's jagged, or has Nones. We are
            # willing to try handling the Nones, but jagged also isn't visualizable.
            nones = np.where([d is None for d in data])[0]

            if len(nones) == data.shape[0]:
                # all Nones, so give up
                continue

            if len(nones) == 0:
                # looks like Nones had nothing to do with it. bail
                continue

            try:
                data = database.replaceNonesWithNonsense(data, pDef.name, nones=nones)
            except (ValueError, TypeError):
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

    return allData
