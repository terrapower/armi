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


class Triplet(yamlize.Object):
    """A x, y, z triplet for coordinates or lattice pitch."""

    x = yamlize.Attribute(type=float)
    y = yamlize.Attribute(type=float, default=0.0)
    z = yamlize.Attribute(type=float, default=0.0)

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z


class SystemBlueprint(yamlize.Object):
    """The reactor-level structure input blueprint."""

    name = yamlize.Attribute(key="name", type=str)
    latticeFile = yamlize.Attribute(key="lattice file", type=str)
    origin = yamlize.Attribute(key="origin", type=Triplet, default=None)
    latticeDimensions = yamlize.Attribute(
        key="lattice pitch", type=Triplet, default=None
    )

    def __init__(
        self, name=None, latticeFile=None, origin=None, latticeDimensions=None
    ):
        """
        A Reactor Level Structure like a core or SFP.

        Notes
        -----
        yamlize does not call an __init__ method, instead it uses __new__ and setattr
        this is only needed for when you want to make this object from a non-YAML source.
        """
        self.name = name
        self.latticeFile = latticeFile
        self.origin = origin
        self.latticeDimensions = latticeDimensions

    def construct(self, cs, bp, reactor, geom=None):
        """Build a core/IVS/EVST/whatever and fill it with children."""
        from armi.reactor import reactors  # avoid circular import

        runLog.info("Constructing the `{}`".format(self.name))
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromFile(self.latticeFile)
        container = reactors.Core(self.name, cs, geom)
        reactor.add(container)  # need parent before loading assemblies
        self._constructSpatialGrid(container)
        if armi.MPI_RANK != 0:
            # on non-master nodes we don't bother building up the assemblies
            # because they will be populated with DistributeState.
            # This is intended to optimize speed and minimize ram.
            return None
        self._loadAssemblies(cs, container, geom, bp)
        summarizeMaterialData(container)
        self._modifyGeometry(container)
        container.processLoading(cs)
        return container

    def _constructSpatialGrid(self, container):
        """
        Build unit-dimension spatial grid on the reactor level.

        The grid will be adjusted to the proper pitch after it is populated by
        inferring the spacing from its children. If you want to make a more
        spatially-distributed grid (i.e. with empty space between structures
        as you might have with various ex-core structures),
        """
        runLog.extra("Creating the spatial grid")
        if container.p.geomType in [geometry.RZT, geometry.RZ]:
            container.spatialGrid = grids.thetaRZGridFromGeom(
                container.geom, armiObject=container
            )
        elif container.p.geomType == geometry.HEX:
            pitch = self.latticeDimensions.x if self.latticeDimensions else 1.0
            # add 2 for potential dummy assems
            container.spatialGrid = grids.hexGridFromPitch(
                pitch, numRings=container.geom.maxRings + 2, armiObject=container
            )
        elif container.p.geomType == geometry.CARTESIAN:
            # if full core or not cut-off, bump the first assembly from the center of the mesh
            # into the positive values.
            xw, yw = (
                (self.latticeDimensions.x, self.latticeDimensions.y)
                if self.latticeDimensions
                else (1.0, 1.0)
            )
            isOffset = (
                container.isFullCore
                or geometry.THROUGH_CENTER_ASSEMBLY not in container.symmetry
            )
            container.spatialGrid = grids.cartesianGridFromRectangle(
                xw,
                yw,
                numRings=container.geom.maxRings,
                isOffset=isOffset,
                armiObject=container,
            )
        container.spatialLocator = grids.CoordinateLocation(
            self.origin.x, self.origin.y, self.origin.z, None
        )
        runLog.debug("Built grid: {}".format(container.spatialGrid))

    # pylint: disable=no-self-use
    def _loadAssemblies(self, cs, container, geom, bp):
        runLog.header(
            "=========== Adding Assemblies to {} ===========".format(container)
        )
        badLocations = set()
        for locationInfo, aTypeID in geom.assemTypeByIndices.items():
            newAssembly = bp.constructAssem(geom.geomType, cs, specifier=aTypeID)

            if geom.geomType in [geometry.RZT, geometry.RZ]:
                # in RZ, TRZ, locationInfo are upper and lower bounds in R and Theta.
                # We want to convert these into spatialLocator indices in the reactor's spatialGrid
                rad0, rad1, theta0, theta1, numAzi, numRadial = locationInfo
                loc = container.spatialGrid[
                    container.spatialGrid.indicesOfBounds(rad0, rad1, theta0, theta1)
                ]
                newAssembly.p.AziMesh = numAzi
                newAssembly.p.RadMesh = numRadial
            else:
                ring, pos = locationInfo
                i, j = container.spatialGrid.getIndicesFromRingAndPos(ring, pos)
                loc = container.spatialGrid[i, j, 0]
                if (
                    container.symmetry == geometry.THIRD_CORE + geometry.PERIODIC
                    and not container.spatialGrid.isInFirstThird(
                        loc, includeTopEdge=True
                    )
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

    def _modifyGeometry(self, container):
        """Perform post-load geometry conversions like full core, edge assems."""
        # all cases should have no edge assemblies. They are added ephemerally when needed
        from armi.reactor.converters import geometryConverters  # circular imports

        runLog.header("=========== Applying Geometry Modifications ===========")
        converter = geometryConverters.EdgeAssemblyChanger()
        converter.removeEdgeAssemblies(container)

        # now update the spatial grid dimensions based on the populated children
        # (unless specified on input)
        if not self.latticeDimensions:
            runLog.info(
                "Updating spatial grid pitch data for {} geometry".format(
                    container.p.geomType
                )
            )
            if container.p.geomType == geometry.HEX:
                container.spatialGrid.changePitch(container[0][0].getPitch())
            elif container.p.geomType == geometry.CARTESIAN:
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


def migrate(bp, cs):
    """
    Make a structure representing a Core based on a cs object with a ``geomFile``.

    This allows settings-driven core map for backwards compatibility.
    """
    from armi.reactor import blueprints  # avoid cyclic import

    # backwards compatibility
    if bp.systemDesigns is None:
        bp.systemDesigns = Systems()

    if "core" in [rd.name for rd in bp.systemDesigns]:
        raise ValueError(
            "Core map is defined in both the ``geometry`` setting and in "
            "the blueprints file. Only one definition may exist. "
            "Update inputs."
        )

    bp.systemDesigns["core"] = SystemBlueprint("core", cs["geomFile"], Triplet())

    # Someday: write out the migration file. At the moment this messes up the case
    # title and doesn't yet have the other systems in place so this isn't the right place.


#     cs.writeToXMLFile(cs.caseTitle + '.migrated.xml')
#     with open(os.path.split(cs['loadingFile'])[0] + '.migrated.' + '.yaml', 'w') as loadingFile:
#         blueprints.Blueprints.dump(bp, loadingFile)
