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

See documentation of blueprints in :ref:`bp-input-file` for more context. See example in
:py:mod:`armi.reactor.blueprints.tests.test_reactorBlueprints`.

This was built to replace the old system that loaded the core geometry from the ``cs['geometry']`` setting. Until the
geom file-based input is completely removed, this system will attempt to migrate the core layout from geom files. When
geom files are used, explicitly specifying a ``core`` system will result in an error.

System Blueprints are a big step in the right direction to generalize user input, but was still mostly adapted from the
old Core layout input. As such, they still only really support Core-like systems. Future work should generalize the
concept of "system" to more varied scenarios.

See Also
--------
armi.reactor.blueprints.gridBlueprints : Method for storing system assembly layouts.
"""

import yamlize

from armi import context, getPluginManagerOrFail, runLog
from armi.reactor import geometry, grids
from armi.reactor.blueprints.gridBlueprint import Triplet
from armi.utils import tabulate


class SystemBlueprint(yamlize.Object):
    """
    The reactor-level structure input blueprint.

    .. impl:: Build core and spent fuel pool from blueprints
        :id: I_ARMI_BP_SYSTEMS
        :implements: R_ARMI_BP_SYSTEMS, R_ARMI_BP_CORE

        This class creates a yaml interface for the user to define systems with grids, such as cores or spent fuel
        pools, each having their own name, type, grid, and position in space. It is incorporated into the "systems"
        section of a blueprints file by being included as key-value pairs within the
        :py:class:`~armi.reactor.blueprints.reactorBlueprint.Systems` class, which is in turn included into the overall
        blueprints within :py:class:`~armi.reactor.blueprints.Blueprints`.

        This class includes a :py:meth:`~armi.reactor.blueprints.reactorBlueprint.SystemBlueprint.construct` method,
        which is typically called from within :py:func:`~armi.reactor.reactors.factory` during the initialization of the
        reactor object to instantiate the core and/or spent fuel pool objects. During that process, a spatial grid is
        constructed based on the grid blueprints specified in the "grids" section of the blueprints (see
        :need:`I_ARMI_BP_GRID`) and the assemblies needed to fill the lattice are built from blueprints using
        :py:meth:`~armi.reactor.blueprints.Blueprints.constructAssem`.

    Notes
    -----
    We use string keys to link grids to objects that use them. This differs from how blocks / assembies are specified,
    which use YAML anchors. YAML anchors have proven to be problematic and difficult to work with.
    """

    name = yamlize.Attribute(key="name", type=str)
    typ = yamlize.Attribute(key="type", type=str, default="core")
    gridName = yamlize.Attribute(key="grid name", type=str)
    origin = yamlize.Attribute(key="origin", type=Triplet, default=None)

    def __init__(self, name=None, gridName=None, origin=None):
        """
        A Reactor-level structure like a core, or ex-core like SFP.

        Notes
        -----
        yamlize does not call an __init__ method, instead it uses __new__ and setattr this is only needed for when you
        want to make this object from a non-YAML source.
        """
        self.name = name
        self.gridName = gridName
        self.origin = origin

    @staticmethod
    def _resolveSystemType(typ: str):
        """Loop over all plugins that could be attached and determine if any tell us how to build a specific systems
        attribute.
        """
        manager = getPluginManagerOrFail()

        # Only need this to handle the case we don't find the system we expect
        seen = set()
        for options in manager.hook.defineSystemBuilders():
            for key, builder in options.items():
                # Take the first match we find. This would allow other plugins to define a new core builder before
                # finding those defined by the ReactorPlugin
                if key == typ:
                    return builder
                seen.add(key)

        raise ValueError(
            f"Could not determine an appropriate class for handling a system of type `{typ}`. "
            f"Supported types are {seen}."
        )

    def construct(self, cs, bp, reactor, loadComps=True):
        """Build a core or ex-core grid and fill it with children.

        Parameters
        ----------
        cs : :py:class:`Settings <armi.settings.Settings>`
            armi settings to apply
        bp : :py:class:`Reactor <armi.reactor.blueprints.Blueprints>`
            armi blueprints to apply
        reactor : :py:class:`Reactor <armi.reactor.reactors.Reactor>`
            reactor to fill
        loadComps : bool, optional
            whether to fill reactor with assemblies, as defined in blueprints, or not. Is False in
            :py:class:`UniformMeshGeometryConverter <armi.reactor.converters.uniformMesh.UniformMeshGeometryConverter>`
            within the initNewReactor() method.

        Returns
        -------
        Composite
            A Composite object with a grid, like a Spent Fuel Pool or other ex-core structure.

        Raises
        ------
        ValueError
            input error, no grid design provided
        ValueError
            objects were added to non-existent grid locations
        """
        runLog.info(f"Constructing the `{self.name}`")

        if not bp.gridDesigns:
            raise ValueError("The input must define grids to construct a reactor, but does not. Update input.")

        gridDesign = bp.gridDesigns.get(self.gridName, None)
        system = self._resolveSystemType(self.typ)(self.name)

        # Some systems may not require a prescribed grid design. Only use one if provided
        if gridDesign is not None:
            spatialGrid = gridDesign.construct()
            system.spatialGrid = spatialGrid
            system.spatialGrid.armiObject = system

        reactor.add(system)  # ensure the reactor is the parent
        spatialLocator = grids.CoordinateLocation(self.origin.x, self.origin.y, self.origin.z, None)
        system.spatialLocator = spatialLocator
        if context.MPI_RANK != 0:
            # Non-primary nodes get the reactor via DistributeState.
            return None

        system = self._constructComposites(cs, bp, loadComps, system, gridDesign)

        return system

    def _constructComposites(self, cs, bp, loadComps, system, gridDesign):
        """Fill a grid with composities, if there are any to fill.

        Parameters
        ----------
        cs : Settings object.
            armi settings to apply
        bp : Blueprints object.
            armi blueprints to apply
        loadComps : bool
            whether to fill reactor with composities, as defined in blueprints, or not
        system : Composite
            The composite we are building.
        gridDesign : GridBlueprint
            The definition of the grid on the object.

        Returns
        -------
        Composite
            A Composite object with a grid, like a Spent Fuel Pool or other ex-core structure.
        """
        from armi.reactor.reactors import Core  # avoid circular import

        if loadComps and gridDesign is not None:
            self._loadComposites(cs, bp, system, gridDesign.gridContents, gridDesign.orientationBOL)

            if isinstance(system, Core):
                self._modifyGeometry(system, gridDesign)
                summarizeMaterialData(system)
                system.processLoading(cs)

        return system

    def _loadComposites(self, cs, bp, container, gridContents, orientationBOL):
        from armi.reactor.cores import Core

        runLog.header(f"=========== Adding Composites to {container} ===========")
        badLocations = set()
        for locationInfo, aTypeID in gridContents.items():
            # handle the hex-grid special case, where the user enters (ring, pos)
            i, j = locationInfo
            if isinstance(container, Core) and container.geomType == geometry.GeomType.HEX:
                loc = container.spatialGrid.indicesToRingPos(i, j)
            else:
                loc = locationInfo

            # correctly rotate the Composite
            if orientationBOL is None or loc not in orientationBOL:
                orientation = 0.0
            else:
                orientation = orientationBOL[loc]

            # create a new Composite to add to the grid
            newAssembly = bp.constructAssem(cs, specifier=aTypeID, orientation=orientation)

            # add the Composite to the grid
            posi = container.spatialGrid[i, j, 0]
            try:
                container.add(newAssembly, posi)
            except LookupError:
                badLocations.add(posi)

        if badLocations:
            raise ValueError(f"Attempted to add objects to non-existent locations on the grid: {badLocations}.")

        # init position history param on each assembly
        for a in container:
            loc = a.getLocation()
            if loc in a.NOT_IN_CORE:
                a.p.ringPosHist = [(loc, loc)]
            else:
                try:
                    ring, pos, _ = grids.locatorLabelToIndices(a.getLocation())
                    a.p.ringPosHist = [(ring, pos)]
                except ValueError:
                    # some ex-core structures may not have valid locator label indices
                    a.p.ringPosHist = [(a.NOT_CREATED_YET, a.NOT_CREATED_YET)]

    def _modifyGeometry(self, container, gridDesign):
        """Perform post-load geometry conversions like full core, edge assems."""
        # all cases should have no edge assemblies. They are added ephemerally when needed
        from armi.reactor.converters import geometryConverters

        runLog.header("=========== Applying Geometry Modifications ===========")
        if not container.isFullCore:
            runLog.extra("Applying non-full core modifications")
            converter = geometryConverters.EdgeAssemblyChanger()
            converter.scaleParamsRelatedToSymmetry(container)
            converter.removeEdgeAssemblies(container)

        # now update the spatial grid dimensions based on the populated children (unless specified on input)
        if not gridDesign.latticeDimensions:
            runLog.info(f"Updating spatial grid pitch data for {container.geomType} geometry")
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
    runLog.header(f"=========== Summarizing Source of Material Data for {container} ===========")
    materialNames = set()
    materialData = []
    for c in container.iterComponents():
        if c.material.name in materialNames:
            continue
        materialData.append((c.material.name, c.material.DATA_SOURCE))
        materialNames.add(c.material.name)

    materialData = sorted(materialData)
    runLog.info(tabulate.tabulate(data=materialData, headers=["Material Name", "Source Location"], tableFmt="armi"))
    return materialData
