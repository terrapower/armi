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
The legacy SystemLayoutInput class and supporting code.

This module contains the soon-to-be defunct ``SystemLayoutInput`` class, which used to
be used for specifying assembly locations in the core. This has been replaced by the
``systems:`` and ``grids:`` sections of ``Blueprints``, but still exists to facilitate
input migrations.

See Also
--------
reactor.blueprints.reactorBlueprint
reactor.blueprints.gridBlueprint
"""

from collections import OrderedDict
from copy import copy
import os
import sys
import xml.etree.ElementTree as ET

from ruamel.yaml import YAML
import voluptuous as vol

from armi import runLog
from armi.reactor import geometry
from armi.reactor import grids
from armi.utils import asciimaps
from armi.utils import directoryChangers

INP_SYSTEMS = "reactor"
INP_SYMMETRY = "symmetry"
INP_GEOM = "geom"
INP_DISCRETES = "discretes"
INP_LATTICE = "lattice"
INP_LOCATION = "location"
INP_SPEC = "spec"
INP_FUEL_PATH = "eqPathIndex"
INP_FUEL_CYCLE = "eqPathCycle"

LOC_CARTESIAN = ("xi", "yi")
LOC_HEX = ("ring", "pos")
LOC_RZ = ("rad1", "rad2", "theta1", "theta2")
MESH_RZ = ("azimuthalMesh", "radialMesh")

LOC_KEYS = {
    geometry.CARTESIAN: LOC_CARTESIAN,
    geometry.HEX: LOC_HEX,
    geometry.RZ: LOC_RZ + MESH_RZ,
    geometry.RZT: LOC_RZ + MESH_RZ,
}

DISCRETE_SCHEMA = vol.Schema(
    [
        {
            INP_LOCATION: vol.Schema(
                {
                    vol.In(LOC_CARTESIAN + LOC_HEX + LOC_RZ + MESH_RZ): vol.Any(
                        float, int
                    )
                }
            ),
            INP_SPEC: str,
            vol.Inclusive(INP_FUEL_PATH, "eq shuffling"): int,
            vol.Inclusive(INP_FUEL_CYCLE, "eq shuffling"): int,
        }
    ]
)

INPUT_SCHEMA = vol.Schema(
    {
        INP_SYSTEMS: vol.Schema(
            {
                str: vol.Schema(
                    {
                        vol.Optional(INP_GEOM, default=geometry.HEX): vol.In(
                            geometry.VALID_GEOMETRY_TYPE
                        ),
                        vol.Optional(
                            INP_SYMMETRY,
                            default=geometry.THIRD_CORE + " " + geometry.PERIODIC,
                        ): vol.In(geometry.SymmetryType.createValidSymmetryStrings()),
                        vol.Optional(INP_DISCRETES): DISCRETE_SCHEMA,
                        vol.Optional(INP_LATTICE): str,
                    }
                )
            }
        )
    }
)


class SystemLayoutInput:
    """
    Geometry file. Contains 2-D mapping of geometry.

    This approach to specifying core layout has been deprecated in favor of the
    :py:class:`armi.reactor.blueprints.gridBlueprints.GridBlueprints` and ``systems:``
    section of :py:class:`armi.reactor.blueprints.Blueprints`
    """

    _GEOM_FILE_EXTENSION = ".xml"
    ROOT_TAG = INP_SYSTEMS

    def __init__(self):
        self.fName = None
        self.modifiedFileName = None
        self.geomType: str
        self.symmetry = None
        self.assemTypeByIndices = OrderedDict()
        self.eqPathInput = {}
        self.eqPathsHaveBeenModified = False
        self.maxRings = 0

    def __repr__(self):
        return "<Geometry file {0}>".format(self.fName)

    def readGeomFromFile(self, fName):
        """
        Read the 2-d geometry input file.

        See Also
        --------
        fromReactor : Build SystemLayoutInput from a Reactor object.
        """
        self.fName = os.path.expandvars(fName)
        with open(self.fName) as stream:
            self.readGeomFromStream(stream)

    def readGeomFromStream(self, stream):
        """
        Read geometry info from a stream.

        This populates the object with info from any source.

        Notes
        -----
        There are two formats of geometry: yaml and xml. This tries
        xml first (legacy), and if it fails it tries yaml.
        """
        # Warn the user that this feature is schedule for deletion.
        warn = "XML Geom Files are scheduled to be removed from ARMI, please use blueprint files."
        runLog.important(warn)

        try:
            self._readXml(stream)
        except ET.ParseError:
            stream.seek(0)
            self._readYaml(stream)

    def toGridBlueprints(self, name: str = "core"):
        """
        Migrate old-style SystemLayoutInput to new GridBlueprint.

        Returns a list of GridBlueprint objects. There will at least be one entry,
        containing the main core layout. If equilibrium fuel paths are specified, it
        will occupy the second element.
        """
        # TODO: After moving SystemLayoutInput out of geometry.py, we may be able to
        # move this back out to top-level without causing blueprint import order issues.
        from armi.reactor.blueprints.gridBlueprint import GridBlueprint

        geom = self.geomType
        symmetry = self.symmetry

        bounds = None

        if self.geomType == geometry.GeomType.RZT:
            # We need a grid in order to go from whats in the input to indices, and to
            # be able to provide grid bounds to the blueprint.
            rztGrid = grids.ThetaRZGrid.fromGeom(self)
            theta, r, _ = rztGrid.getBounds()
            bounds = {"theta": theta.tolist(), "r": r.tolist()}

        gridContents = dict()
        for indices, spec in self.assemTypeByIndices.items():
            if self.geomType == geometry.GeomType.HEX:
                i, j = grids.HexGrid.getIndicesFromRingAndPos(*indices)
            elif self.geomType == geometry.GeomType.RZT:
                i, j, _ = rztGrid.indicesOfBounds(*indices[0:4])
            else:
                i, j = indices
            gridContents[(i, j)] = spec

        bp = GridBlueprint(
            name=name,
            gridContents=gridContents,
            geom=geom,
            symmetry=symmetry,
            gridBounds=bounds,
        )

        bps = [bp]

        if any(val != (None, None) for val in self.eqPathInput.values()):
            # We could probably just copy eqPathInput, but we don't want to preserve
            # (None, None) entries.
            eqPathContents = dict()
            for idx, eqPath in self.eqPathInput.items():
                if eqPath == (None, None):
                    continue
                if self.geomType == geometry.GeomType.HEX:
                    i, j = grids.HexGrid.getIndicesFromRingAndPos(*idx)
                elif self.geomType == geometry.GeomType.RZT:
                    i, j, _ = rztGrid.indicesOfBounds(*idx[0:4])
                else:
                    i, j = idx
                eqPathContents[i, j] = copy(self.eqPathInput[idx])

            pathBp = GridBlueprint(
                name=name + "EqPath",
                gridContents=eqPathContents,
                geom=geom,
                symmetry=symmetry,
                gridBounds=bounds,
            )

            bps.append(pathBp)

        return bps

    def _readXml(self, stream):
        tree = ET.parse(stream)
        root = tree.getroot()
        self._getGeomTypeAndSymmetryFromXml(root)
        self.assemTypeByIndices.clear()

        for assemblyNode in root:
            aType = str(assemblyNode.attrib["name"])
            eqPathIndex, eqPathCycle = None, None

            if self.geomType == geometry.GeomType.CARTESIAN:
                indices = x, y = tuple(
                    int(assemblyNode.attrib[key]) for key in LOC_CARTESIAN
                )
                self.maxRings = max(x + 1, y + 1, self.maxRings)
            elif self.geomType == geometry.GeomType.RZT:
                indices = tuple(
                    float(assemblyNode.attrib[key]) for key in LOC_RZ
                ) + tuple(int(assemblyNode.attrib[key]) for key in MESH_RZ)
            else:
                # assume hex geom.
                indices = ring, _pos = tuple(
                    int(assemblyNode.attrib[key]) for key in LOC_HEX
                )
                self.maxRings = max(ring, self.maxRings)

                if INP_FUEL_PATH in assemblyNode.attrib:
                    # equilibrium geometry info.
                    eqPathIndex = int(assemblyNode.attrib[INP_FUEL_PATH])
                    eqPathCycle = int(assemblyNode.attrib[INP_FUEL_CYCLE])

            self.assemTypeByIndices[indices] = aType
            self.eqPathInput[indices] = (eqPathIndex, eqPathCycle)

    def _readYaml(self, stream):
        """
        Read geometry from yaml.

        Notes
        -----
        This is intended to replace the XML format as we converge on
        consistent inputs.
        """
        yaml = YAML()
        tree = yaml.load(stream)
        tree = INPUT_SCHEMA(tree)
        self.assemTypeByIndices.clear()
        for _systemName, system in tree[INP_SYSTEMS].items():
            # no need to check for valid since the schema handled that.
            self.geomType = geometry.GeomType.fromStr(system[INP_GEOM])
            self.symmetry = geometry.SymmetryType.fromStr(system[INP_SYMMETRY])
            if INP_DISCRETES in system:
                self._read_yaml_discretes(system)
            elif INP_LATTICE in system:
                self._read_yaml_lattice(system)

    def _read_yaml_discretes(self, system):
        for discrete in system[INP_DISCRETES]:
            location = discrete[INP_LOCATION]
            indices = tuple(location[k] for k in LOC_KEYS[str(self.geomType)])
            if self.geomType == geometry.GeomType.CARTESIAN:
                x, y = indices
                self.maxRings = max(x + 1, y + 1, self.maxRings)
            elif self.geomType == geometry.GeomType.RZT:
                pass
            else:
                # assume hex geom.
                x, y = indices
                self.maxRings = max(x, self.maxRings)

            self.assemTypeByIndices[indices] = discrete[INP_SPEC]
            self.eqPathInput[indices] = (
                discrete.get(INP_FUEL_CYCLE),
                discrete.get(INP_FUEL_PATH),
            )

    def _read_yaml_lattice(self, system):
        """Read a ascii map string into this object."""
        mapTxt = system[INP_LATTICE]
        if (
            self.geomType == geometry.GeomType.HEX
            and self.symmetry.domain == geometry.DomainType.THIRD_CORE
        ):
            asciimap = asciimaps.AsciiMapHexThirdFlatsUp()
            asciimap.readAscii(mapTxt)
            for (i, j), spec in asciimap.items():
                if spec == "-":
                    # skip whitespace placeholders
                    continue
                ring, pos = grids.HexGrid.indicesToRingPos(i, j)
                self.assemTypeByIndices[(ring, pos)] = spec
                self.maxRings = max(ring, self.maxRings)
        else:
            raise ValueError(
                f"ASCII map reading from geom/domain: {self.geomType}/"
                f"{self.symmetry.domain} not supported."
            )

    def modifyEqPaths(self, modifiedPaths):
        """
        Modifies the geometry object by updating the equilibrium path indices and equilibrium path cycles.

        Parameters
        ----------
        modifiedPaths : dict, required
            This is a dictionary that contains the indices that are mapped to the
            eqPathIndex and eqPathCycle.  modifiedPath[indices] = (eqPathIndex,
            eqPathCycle)
        """
        runLog.important("Modifying the equilibrium paths on {}".format(self))
        self.eqPathsHaveBeenModified = True
        self.eqPathInput.update(modifiedPaths)

    def _getModifiedFileName(self, originalFileName, suffix):
        """
        Generates the modified geometry file name based on the requested suffix
        """
        originalFileName = originalFileName.split(self._GEOM_FILE_EXTENSION)[0]
        suffix = suffix.split(self._GEOM_FILE_EXTENSION)[0]
        self.modifiedFileName = originalFileName + suffix + self._GEOM_FILE_EXTENSION

    def writeGeom(self, outputFileName, suffix=""):
        """
        Write data out as a geometry xml file

        Parameters
        ----------
        outputFileName : str
            Geometry file name

        suffix : str
            Added suffix to the geometry output file name

        """
        if suffix:
            self._getModifiedFileName(outputFileName, suffix)
            outputFileName = self.modifiedFileName

        runLog.important("Writing reactor geometry file as {}".format(outputFileName))
        root = ET.Element(
            INP_SYSTEMS,
            attrib={
                INP_GEOM: str(self.geomType),
                INP_SYMMETRY: str(self.symmetry),
            },
        )
        tree = ET.ElementTree(root)
        # start at ring 1 pos 1 and go out
        for targetIndices in sorted(list(self.assemTypeByIndices)):
            ring, pos = targetIndices
            assembly = ET.SubElement(root, "assembly")
            assembly.set("ring", str(ring))
            assembly.set("pos", str(pos))
            fuelPath, fuelCycle = self.eqPathInput.get((ring, pos), (None, None))
            if fuelPath is not None:
                # set the equilibrium shuffling info if it exists
                assembly.set(INP_FUEL_PATH, str(fuelPath))
                assembly.set(INP_FUEL_CYCLE, str(fuelCycle))

            aType = self.assemTypeByIndices[targetIndices]
            assembly.set("name", aType)
        # note: This is ugly and one-line, but that's ok
        # since we're transitioning.
        tree.write(outputFileName)

    def _writeYaml(self, stream, sysName="core"):
        """
        Write the system layout in YAML format.

        These can eventually either define a type/specifier mapping and then point
        to a grid definition full of specifiers to be populated, or
        they can just be a list of "singles" which define indices:specifier.

        Note
        ----
        So far, only singles are implemented (analogous to old XML format)
        """
        geomData = []
        for indices in sorted(list(self.assemTypeByIndices)):
            specifier = self.assemTypeByIndices[indices]
            fuelPath, fuelCycle = self.eqPathInput.get(indices, (None, None))
            keys = LOC_KEYS[str(self.geomType)]
            dataPoint = {INP_LOCATION: dict(zip(keys, indices)), INP_SPEC: specifier}
            if fuelPath is not None:
                dataPoint.update({INP_FUEL_PATH: fuelPath, INP_FUEL_CYCLE: fuelCycle})
            geomData.append(dataPoint)

        yaml = YAML()
        yaml.default_flow_style = False
        yaml.indent(mapping=2, sequence=4, offset=2)
        fullData = {
            INP_SYSTEMS: {
                sysName: {
                    INP_GEOM: str(self.geomType),
                    INP_SYMMETRY: str(self.symmetry),
                    INP_DISCRETES: geomData,
                }
            }
        }
        fullData = INPUT_SCHEMA(fullData)  # validate on the way out
        yaml.dump(fullData, stream)

    def _writeAsciiMap(self):
        """Generate an ASCII map representation.

        Warning
        -------
        This only works for HexGrid.
        """
        lattice = {}
        for ring, pos in sorted(list(self.assemTypeByIndices)):
            specifier = self.assemTypeByIndices[(ring, pos)]
            i, j = grids.HexGrid.getIndicesFromRingAndPos(ring, pos)
            lattice[i, j] = specifier

        geomMap = asciimaps.AsciiMapHexThirdFlatsUp()
        geomMap.asciiLabelByIndices = lattice
        geomMap.gridContentsToAscii()
        geomMap.writeAscii(sys.stdout)

    def growToFullCore(self):
        """
        Convert geometry input to full core.

        Notes
        -----
        This only works for Hex 1/3rd core geometry inputs.
        """
        if self.symmetry.domain == geometry.DomainType.FULL_CORE:
            # already full core from geometry file. No need to copy symmetry over.
            runLog.important(
                "Detected that full core geometry already exists. Cannot expand."
            )
            return
        elif (
            self.symmetry.domain != geometry.DomainType.THIRD_CORE
            or self.symmetry.boundary != geometry.BoundaryType.PERIODIC
        ):
            raise ValueError(
                "Cannot convert shape `{}` to full core, must be {}".format(
                    self.symmetry.domain,
                    str(
                        geometry.SymmetryType(
                            geometry.DomainType.THIRD_CORE,
                            geometry.BoundaryType.PERIODIC,
                        )
                    ),
                ),
            )

        grid = grids.HexGrid.fromPitch(1.0)
        grid._symmetry: str = str(self.symmetry)

        # need to cast to a list because we will modify during iteration
        for (ring, pos), specifierID in list(self.assemTypeByIndices.items()):
            indices = grids.HexGrid.getIndicesFromRingAndPos(ring, pos)
            for symmetricI, symmetricJ in grid.getSymmetricEquivalents(indices):
                symmetricRingPos = grids.HexGrid.indicesToRingPos(
                    symmetricI, symmetricJ
                )
                self.assemTypeByIndices[symmetricRingPos] = specifierID

        self.symmetry = geometry.SymmetryType(
            geometry.DomainType.FULL_CORE,
            geometry.BoundaryType.NO_SYMMETRY,
        )

    def _getGeomTypeAndSymmetryFromXml(self, root):
        """Read the geometry type and symmetry."""
        try:
            self.geomType = geometry.GeomType.fromStr(
                str(root.attrib[INP_GEOM]).lower()
            )
        except ValueError:
            # will not execute if the geom was specified as thetarz, cartesian or anything else specific
            runLog.warning(
                "Could not find geometry type. Assuming hex geometry with third core periodic symmetry."
            )
            self.geomType = geometry.GeomType.HEX
            self.symmetry = geometry.SymmetryType(
                geometry.DomainType.THIRD_CORE,
                geometry.BoundaryType.PERIODIC,
            )
        else:
            inputString = str(root.attrib[INP_SYMMETRY]).lower()
            self.symmetry = geometry.SymmetryType.fromStr(inputString)

    @classmethod
    def fromReactor(cls, reactor):
        """
        Build SystemLayoutInput object based on the current state of a Reactor.

        See Also
        --------
        readGeomFromFile : Builds a SystemLayoutInput from an XML file.
        """
        geom = cls()
        runLog.info("Reading core map from {}".format(reactor))
        geom.geomType = str(reactor.core.geomType)
        geom.symmetry = reactor.core.symmetry

        bp = reactor.blueprints
        assemDesigns = bp.assemDesigns if bp else ()

        for assembly in reactor.core:
            aType = assembly.getType()

            if aType in assemDesigns:
                aType = assemDesigns[aType].specifier

            (x, _y) = indices = reactor.core.spatialGrid.getRingPos(
                assembly.spatialLocator.getCompleteIndices()
            )
            geom.maxRings = max(x, geom.maxRings)

            geom.assemTypeByIndices[indices] = aType

        return geom

    @classmethod
    def loadFromCs(cls, cs):
        """Function to load Geoemtry based on supplied ``CaseSettings``."""
        if not cs["geomFile"]:
            return None

        with directoryChangers.DirectoryChanger(cs.inputDirectory):
            geom = cls()
            geom.readGeomFromFile(cs["geomFile"])
            return geom
