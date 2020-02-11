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
Definitions of top-level reactor arrangements like the Core (default), SFP, etc.

Each structure is defined by a name and a geometry xml file.

See documentation of blueprints in :doc:`/user/inputs/blueprints`.
See example in :py:mod:`armi.reactor.blueprints.tests.test_reactorBlueprints`.

Lattices will form tightly to the pitch of their children by default
but you can spread them out by adding the optional ``lattice pitch`` key.
This can be useful for adding grids with lots of spacing between objects.

This was built on top of an existing system that loaded the core geometry from the
global setting cs['geometry']. This system will still allow that to exist
but will error out if you define ``core`` here and there at the same time.

See Also
--------
armi.reactor.geometry.SystemLayoutInput : reads the individual face-map xml files.
"""
import tabulate
import yamlize

import armi
from armi import runLog
from armi.reactor import geometry
from armi.reactor import grids
from armi.reactor.blueprints.gridBlueprint import Triplet


class SystemBlueprint(yamlize.Object):
    """
    The reactor-level structure input blueprint.

    .. note:: We use strings to link grids to things that use
        them rather than YAML anchors in this part of the input.
        This seems inconsistent with how blocks are referred to
        in assembly blueprints but this is part of a transition
        away from YAML anchors.
    """

    name = yamlize.Attribute(key="name", type=str)
    gridName = yamlize.Attribute(key="grid name", type=str)
    origin = yamlize.Attribute(key="origin", type=Triplet, default=None)

    def __init__(self, name=None, gridName=None, origin=None):
        """
        A Reactor Level Structure like a core or SFP.

        Notes
        -----
        yamlize does not call an __init__ method, instead it uses __new__ and setattr
        this is only needed for when you want to make this object from a non-YAML source.
        """
        self.name = name
        self.gridName = gridName
        self.origin = origin

    def construct(self, cs, bp, reactor, geom=None):
        """Build a core/IVS/EVST/whatever and fill it with children."""
        from armi.reactor import reactors  # avoid circular import

        runLog.info("Constructing the `{}`".format(self.name))
        if geom is not None:
            gridDesign = geom.toGridBlueprint("core")
        else:
            gridDesign = bp.gridDesigns[self.gridName]
        spatialGrid = gridDesign.construct()
        container = reactors.Core(self.name)
        container.setOptionsFromCs(cs)
        container.spatialGrid = spatialGrid
        container.spatialGrid.armiObject = container
        reactor.add(container)  # need parent before loading assemblies
        spatialLocator = grids.CoordinateLocation(
            self.origin.x, self.origin.y, self.origin.z, None
        )
        container.spatialLocator = spatialLocator
        if armi.MPI_RANK != 0:
            # on non-master nodes we don't bother building up the assemblies
            # because they will be populated with DistributeState.
            # This is intended to optimize speed and minimize ram.
            return None
        self._loadAssemblies(cs, container, gridDesign, gridDesign.gridContents, bp)
        summarizeMaterialData(container)
        self._modifyGeometry(container, gridDesign)
        container.processLoading(cs)
        return container

    # pylint: disable=no-self-use
    def _loadAssemblies(self, cs, container, gridDesign, gridContents, bp):
        runLog.header(
            "=========== Adding Assemblies to {} ===========".format(container)
        )
        badLocations = set()
        for locationInfo, aTypeID in gridContents.items():
            newAssembly = bp.constructAssem(gridDesign.geom, cs, specifier=aTypeID)

            i, j = locationInfo
            loc = container.spatialGrid[i, j, 0]
            if (
                container.symmetry == geometry.THIRD_CORE + geometry.PERIODIC
                and not container.spatialGrid.isInFirstThird(loc, includeTopEdge=True)
            ):
                badLocations.add(loc)
            container.add(newAssembly, loc)
        if badLocations:
            raise ValueError(
                "Geometry core map xml had assemblies outside the "
                "first third core, but had third core symmetry. \n"
                "Please update symmetry to be `full core` or "
                "remove assemblies outside the first third. \n"
                "The locations outside the first third are {}".format(badLocations)
            )

    def _modifyGeometry(self, container, gridDesign):
        """Perform post-load geometry conversions like full core, edge assems."""
        # all cases should have no edge assemblies. They are added ephemerally when needed
        from armi.reactor.converters import geometryConverters  # circular imports

        runLog.header("=========== Applying Geometry Modifications ===========")
        converter = geometryConverters.EdgeAssemblyChanger()
        converter.removeEdgeAssemblies(container)

        # now update the spatial grid dimensions based on the populated children
        # (unless specified on input)
        if not gridDesign.latticeDimensions:
            runLog.info(
                "Updating spatial grid pitch data for {} geometry".format(
                    container.geomType
                )
            )
            if container.geomType == geometry.HEX:
                container.spatialGrid.changePitch(container[0][0].getPitch())
            elif container.geomType == geometry.CARTESIAN:
                xw, yw = container[0][0].getPitch()
                container.spatialGrid.changePitch(xw, yw)


class Systems(yamlize.KeyedList):
    item_type = SystemBlueprint
    key_attr = SystemBlueprint.name


def summarizeMaterialData(container):
    """
    Create a summary of the material objects and source data for a reactor container.

    Parameters
    ----------
    container : Core object
        Any Core object with Blocks and Components defined.
    """

    def _getMaterialSourceData(materialObj):
        return (materialObj.DATA_SOURCE, materialObj.propertyRangeUpdated)

    runLog.header(
        "=========== Summarizing Source of Material Data for {} ===========".format(
            container
        )
    )
    materialNames = set()
    materialData = []
    for b in container.getBlocks():
        for c in b:
            if c.material.name in materialNames:
                continue
            sourceLocation, wasModified = _getMaterialSourceData(c.material)
            materialData.append((c.material.name, sourceLocation, wasModified))
            materialNames.add(c.material.name)
    materialData = sorted(materialData)
    runLog.info(
        tabulate.tabulate(
            tabular_data=materialData,
            headers=[
                "Material Name",
                "Source Location",
                "Property Data was Modified\nfrom the Source?",
            ],
            tablefmt="armi",
        )
    )
    return materialData
