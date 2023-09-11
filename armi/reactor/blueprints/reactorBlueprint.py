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

See documentation of blueprints in :doc:`/user/inputs/blueprints` for more context. See
example in :py:mod:`armi.reactor.blueprints.tests.test_reactorBlueprints`.

This was built to replace the old system that loaded the core geometry from the
cs['geometry'] setting. Until the geom file-based input is completely removed, this
system will attempt to migrate the core layout from geom files. When geom files are
used, explicitly specifying a ``core`` system will result in an error.

System Blueprints are a big step in the right direction to generalize user input, but
was still mostly adapted from the old Core layout input. As such, they still only really
support Core-like systems. Future work should generalize the concept of "system" to more
varied scenarios.

See Also
--------
armi.reactor.blueprints.gridBlueprints : Method for storing system assembly layouts.
armi.reactor.systemLayoutInput.SystemLayoutInput : Deprecated method for reading the individual
face-map xml files.
"""
import tabulate
import yamlize

from armi import context
from armi import getPluginManagerOrFail
from armi import runLog
from armi.reactor import geometry
from armi.reactor import grids
from armi.reactor.blueprints.gridBlueprint import Triplet


class SystemBlueprint(yamlize.Object):
    """
    The reactor-level structure input blueprint.

    .. note:: We use string keys to link grids to objects that use them. This differs
        from how blocks/assembies are specified, which use YAML anchors. YAML anchors
        have proven to be problematic and difficult to work with
    """

    name = yamlize.Attribute(key="name", type=str)
    typ = yamlize.Attribute(key="type", type=str, default="core")
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

    @staticmethod
    def _resolveSystemType(typ: str):
        # Loop over all plugins that could be attached and determine if any
        # tell us how to build a specific systems attribute. Sub-optimial
        # as this check is called for each system (e.g., core, spent fuel pool).
        # It is assumed that the number of systems is currently low enough to justify
        # this structure.

        manager = getPluginManagerOrFail()

        # Only need this to handle the case we don't find the system we expect
        seen = set()
        for options in manager.hook.defineSystemBuilders():
            for key, builder in options.items():
                # Take the first match we find. This would allow other plugins to
                # define a new core builder before finding those defined by the
                # ReactorPlugin
                if key == typ:
                    return builder
                seen.add(key)

        raise ValueError(
            "Could not determine an appropriate class for handling a "
            "system of type `{}`. Supported types are {}.".format(typ, sorted(seen))
        )

    def construct(self, cs, bp, reactor, geom=None, loadAssems=True):
        """Build a core/IVS/EVST/whatever and fill it with children.

        Parameters
        ----------
        cs : :py:class:`Settings <armi.settings.Settings>` object.
            armi settings to apply
        bp : :py:class:`Reactor <armi.reactor.blueprints.Blueprints>` object.
            armi blueprints to apply
        reactor : :py:class:`Reactor <armi.reactor.reactors.Reactor>` object.
            reactor to fill
        geom : optional
        loadAssems : bool, optional
            whether to fill reactor with assemblies, as defined in blueprints, or not. Is False in
            :py:class:`UniformMeshGeometryConverter <armi.reactor.converters.uniformMesh.UniformMeshGeometryConverter>`
            within the initNewReactor() class method.

        Raises
        ------
        ValueError
            input error, no grid design provided
        ValueError
            for 1/3 core maps, assemblies are defined outside the expected 1/3 core region
        """
        from armi.reactor import reactors  # avoid circular import

        runLog.info("Constructing the `{}`".format(self.name))

        # TODO: We should consider removing automatic geom file migration.
        if geom is not None and self.name == "core":
            gridDesign = geom.toGridBlueprints("core")[0]
        else:
            if not bp.gridDesigns:
                raise ValueError(
                    "The input must define grids to construct a reactor, but "
                    "does not. Update input."
                )
            gridDesign = bp.gridDesigns.get(self.gridName, None)

        system = self._resolveSystemType(self.typ)(self.name)

        # Some systems may not require a prescribed grid design. Only try to use one if
        # it was provided
        if gridDesign is not None:
            spatialGrid = gridDesign.construct()
            system.spatialGrid = spatialGrid
            system.spatialGrid.armiObject = system

        reactor.add(system)  # need parent before loading assemblies
        spatialLocator = grids.CoordinateLocation(
            self.origin.x, self.origin.y, self.origin.z, None
        )
        system.spatialLocator = spatialLocator
        if context.MPI_RANK != 0:
            # on non-primary nodes we don't bother building up the assemblies
            # because they will be populated with DistributeState.
            return None

        # TODO: This is also pretty specific to Core-like things. We envision systems
        # with non-Core-like structure. Again, probably only doable with subclassing of
        # Blueprints
        if loadAssems and gridDesign is not None:
            self._loadAssemblies(cs, system, gridDesign.gridContents, bp)

            # TODO: This post-construction work is specific to Cores for now. We need to
            # generalize this. Things to consider:
            # - Should the Core be able to do geom modifications itself, since it already
            # has the grid constructed from the grid design?
            # - Should the summary be so specifically Material data? Should this be done for
            # non-Cores? Like geom modifications, could this just be done in processLoading?
            # Should it be invoked higher up, by whatever code is requesting the Reactor be
            # built from Blueprints?
            if isinstance(system, reactors.Core):
                summarizeMaterialData(system)
                self._modifyGeometry(system, gridDesign)
                system.processLoading(cs)
        return system

    def _loadAssemblies(self, cs, container, gridContents, bp):
        runLog.header(
            "=========== Adding Assemblies to {} ===========".format(container)
        )
        badLocations = set()
        for locationInfo, aTypeID in gridContents.items():
            newAssembly = bp.constructAssem(cs, specifier=aTypeID)

            i, j = locationInfo
            loc = container.spatialGrid[i, j, 0]
            try:
                container.add(newAssembly, loc)
            except LookupError:
                badLocations.add(loc)

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
            if container.geomType == geometry.GeomType.HEX:
                container.spatialGrid.changePitch(container[0][0].getPitch())
            elif container.geomType == geometry.GeomType.CARTESIAN:
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
    runLog.header(
        "=========== Summarizing Source of Material Data for {} ===========".format(
            container
        )
    )
    materialNames = set()
    materialData = []
    for c in container.iterComponents():
        if c.material.name in materialNames:
            continue
        materialData.append((c.material.name, c.material.DATA_SOURCE, False))
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
