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
Reads the input files that define where the major systems are and what's in them.

This includes the core-map, showing which assemblies are where in a core,
and may also include a spent fuel pool, pumps, heat exchangers, etc.

The blueprints input files define the low-level dimensions and compositions
of parts, and this file maps those definitions to locations throughout the
reactor model.

It may eventually also describe the pin-maps within assemblies for solid fuel.

Historically, this file was called the "Geometry Input File", but that's too
generic so we changed it to reduce new user confusion.

Where the original geom.xml file had just one set of assemblies
in the core and other systems were pointed to in the blueprints
file, we eventually anticipate moving all systems definitions
to this geometry file.

See Also
--------
reactor.blueprints.reactorBlueprint
"""

import xml.etree.ElementTree as ET
from collections import OrderedDict
import os
import sys

from ruamel.yaml import YAML
import ruamel.yaml.comments
import voluptuous as vol

from armi import runLog
from armi.reactor import grids
from armi.utils import asciimaps


SYSTEMS = "systems"
VERSION = "version"

HEX = "hex"
RZT = "thetarz"
RZ = "rz"
CARTESIAN = "cartesian"
DODECAGON = "dodecagon"
REC_PRISM = "RecPrism"
HEX_PRISM = "HexPrism"
CONCENTRIC_CYLINDER = "ConcentricCylinder"
ANNULUS_SECTOR_PRISM = "AnnulusSectorPrism"

VALID_GEOMETRY_TYPE = {HEX, RZT, RZ, CARTESIAN}

FULL_CORE = "full"
THIRD_CORE = "third "
QUARTER_CORE = "quarter "
EIGHTH_CORE = "eighth "
SIXTEENTH_CORE = "sixteenth "
REFLECTIVE = "reflective"
PERIODIC = "periodic"
THROUGH_CENTER_ASSEMBLY = (
    " through center assembly"  # through center assembly applies only to cartesian
)

VALID_SYMMETRY = {
    FULL_CORE,
    THIRD_CORE + PERIODIC,  # third core reflective is not geometrically consistent.
    QUARTER_CORE + PERIODIC,
    QUARTER_CORE + REFLECTIVE,
    QUARTER_CORE + PERIODIC + THROUGH_CENTER_ASSEMBLY,
    QUARTER_CORE + REFLECTIVE + THROUGH_CENTER_ASSEMBLY,
    EIGHTH_CORE + PERIODIC,
    EIGHTH_CORE + REFLECTIVE,
    EIGHTH_CORE + PERIODIC + THROUGH_CENTER_ASSEMBLY,
    EIGHTH_CORE + REFLECTIVE + THROUGH_CENTER_ASSEMBLY,
    SIXTEENTH_CORE + PERIODIC,
    SIXTEENTH_CORE + REFLECTIVE,
}

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
    CARTESIAN: LOC_CARTESIAN,
    HEX: LOC_HEX,
    RZ: LOC_RZ + MESH_RZ,
    RZT: LOC_RZ + MESH_RZ,
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
                        vol.Optional(INP_GEOM, default=HEX): vol.In(
                            VALID_GEOMETRY_TYPE
                        ),
                        vol.Optional(
                            INP_SYMMETRY, default=THIRD_CORE + PERIODIC
                        ): vol.In(VALID_SYMMETRY),
                        vol.Optional(INP_DISCRETES): DISCRETE_SCHEMA,
                        vol.Optional(INP_LATTICE): str,
                    }
                )
            }
        )
    }
)

SYMMETRY_FACTORS = {}
for symmetry in VALID_SYMMETRY:
    if FULL_CORE in symmetry:
        SYMMETRY_FACTORS[symmetry] = 1.0
    elif THIRD_CORE in symmetry:
        SYMMETRY_FACTORS[symmetry] = 3.0
    elif QUARTER_CORE in symmetry:
        SYMMETRY_FACTORS[symmetry] = 4.0
    elif EIGHTH_CORE in symmetry:
        SYMMETRY_FACTORS[symmetry] = 8.0
    elif SIXTEENTH_CORE in symmetry:
        SYMMETRY_FACTORS[symmetry] = 16.0
    else:
        raise ValueError(
            "Could not calculate symmetry factor for symmetry {}. update logic.".format(
                symmetry
            )
        )


def loadFromCs(cs):
    """Function to load Geoemtry based on supplied ``CaseSettings``."""
    from armi.utils import directoryChangers  # pylint: disable=import-outside-toplevel; circular import protection
    if not cs["geomFile"]:
        return None
    with directoryChangers.DirectoryChanger(cs.inputDirectory):
        geom = SystemLayoutInput()
        geom.readGeomFromFile(cs["geomFile"])
        return geom


class SystemLayoutInput:
    """Geometry file. Contains 2-D mapping of geometry."""

    _GEOM_FILE_EXTENSION = ".xml"
    ROOT_TAG = INP_SYSTEMS

    def __init__(self):
        self.fName = None
        self.modifiedFileName = None
        self.geomType = None
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
        try:
            self._readXml(stream)
        except ET.ParseError:
            stream.seek(0)
            self._readYaml(stream)
        self._applyMigrations()

    def toGridBlueprint(self, name: str = "core"):
        """Migrate old-style SystemLayoutInput to new GridBlueprint."""
        from armi.reactor.blueprints.gridBlueprint import GridBlueprint

        geom = self.geomType
        symmetry = self.symmetry

        bounds = None

        if self.geomType == RZT:
            # We need a grid in order to go from whats in the input to indices, and to
            # be able to provide grid bounds to the blueprint.
            rztGrid = grids.thetaRZGridFromGeom(self)
            theta, r, _ = rztGrid.getBounds()
            bounds = {"theta": theta, "r": r}

        gridContents = dict()
        for indices, spec in self.assemTypeByIndices.items():
            if HEX in self.geomType:
                i, j = grids.getIndicesFromRingAndPos(*indices)
            elif RZT in self.geomType:
                i, j, _ = rztGrid.indicesOfBounds(*indices[0:4])
            else:
                i, j = indices
            gridContents[i, j] = spec

        bp = GridBlueprint(
            name=name,
            gridContents=gridContents,
            geom=geom,
            symmetry=symmetry,
            gridBounds=bounds,
        )

        bp.eqPathInput = self.eqPathInput

        return bp

    def _readXml(self, stream):
        tree = ET.parse(stream)
        root = tree.getroot()
        self._getGeomTypeAndSymmetryFromXml(root)
        self.assemTypeByIndices.clear()

        for assemblyNode in root:
            aType = str(assemblyNode.attrib["name"])
            eqPathIndex, eqPathCycle = None, None

            if self.geomType == CARTESIAN:
                indices = x, y = tuple(
                    int(assemblyNode.attrib[key]) for key in LOC_CARTESIAN
                )
                self.maxRings = max(x + 1, y + 1, self.maxRings)
            elif self.geomType == RZT:
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
            self.geomType = system[INP_GEOM]
            self.symmetry = system[INP_SYMMETRY]
            if INP_DISCRETES in system:
                self._read_yaml_discretes(system)
            elif INP_LATTICE in system:
                self._read_yaml_lattice(system)

    def _read_yaml_discretes(self, system):
        for discrete in system[INP_DISCRETES]:
            location = discrete[INP_LOCATION]
            indices = tuple(location[k] for k in LOC_KEYS[self.geomType])
            if self.geomType == CARTESIAN:
                x, y = indices
                self.maxRings = max(x + 1, y + 1, self.maxRings)
            elif self.geomType == RZT:
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
        if self.geomType == HEX and THIRD_CORE in self.symmetry:
            geomMap = asciimaps.AsciiMapHexThird()
            geomMap.readMap(mapTxt)
            for (i, j), spec in geomMap.lattice.items():
                if spec == "-":
                    # skip whitespace placeholders
                    continue
                ring, pos = grids.indicesToRingPos(i, j)
                self.assemTypeByIndices[(ring, pos)] = spec
                self.maxRings = max(ring, self.maxRings)
        else:
            raise ValueError(
                f"ASCII map reading from geom/symmetry: {self.geomType}/"
                f"{self.symmetry} not supported."
            )

    def _applyMigrations(self):
        # remove "core" so we can use symmetry for in-block things as well
        # as core maps
        self.symmetry = self.symmetry.replace(" core", "")

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
            INP_SYSTEMS, attrib={INP_GEOM: self.geomType, INP_SYMMETRY: self.symmetry}
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
            keys = LOC_KEYS[self.geomType]
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
                    INP_GEOM: self.geomType,
                    INP_SYMMETRY: self.symmetry,
                    INP_DISCRETES: geomData,
                }
            }
        }
        fullData = INPUT_SCHEMA(fullData)  # validate on the way out
        yaml.dump(fullData, stream)

    def _writeAsciiMap(self):
        """Generate an ASCII map representation."""
        lattice = {}
        for ring, pos in sorted(list(self.assemTypeByIndices)):
            specifier = self.assemTypeByIndices[(ring, pos)]
            i, j = grids.getIndicesFromRingAndPos(ring, pos)
            lattice[i, j] = specifier

        geomMap = asciimaps.AsciiMapHexThird(lattice)
        geomMap.writeMap(sys.stdout)

    def growToFullCore(self):
        """
        Convert geometry input to full core.

        Notes
        -----
        This only works for Hex 1/3rd core geometry inputs.
        """
        if self.symmetry == FULL_CORE:
            # already full core from geometry file. No need to copy symmetry over.
            runLog.important(
                "Detected that full core geometry already exists. Cannot expand."
            )
            return
        elif self.symmetry != THIRD_CORE + PERIODIC:
            raise ValueError(
                "Cannot convert symmetry `{}` to full core, must be {}".format(
                    self.symmetry, THIRD_CORE + PERIODIC
                )
            )

        grid = grids.hexGridFromPitch(1.0)

        # need to cast to a list because we will modify during iteration
        for (ring, pos), specifierID in list(self.assemTypeByIndices.items()):
            indices = grids.getIndicesFromRingAndPos(ring, pos)
            for symmetricI, symmetricJ in grid.getSymmetricIdenticalsThird(indices):
                symmetricRingPos = grids.indicesToRingPos(symmetricI, symmetricJ)
                self.assemTypeByIndices[symmetricRingPos] = specifierID

        self.symmetry = FULL_CORE

    def _getGeomTypeAndSymmetryFromXml(self, root):
        """Read the geometry type and symmetry."""
        try:
            self.geomType = str(root.attrib[INP_GEOM]).lower()
        except ValueError:
            # will not execute if the geom was specified as thetarz, cartesian or anything else specific
            runLog.warning(
                "Could not find geometry type. Assuming hex geometry with third core periodic symmetry."
            )
            self.geomType = HEX
            self.symmetry = THIRD_CORE + PERIODIC
        else:
            self.symmetry = str(root.attrib[INP_SYMMETRY]).lower()


def fromReactor(reactor):
    """
    Build SystemLayoutInput object based on the current state of a Reactor.

    See Also
    --------
    readGeomFromFile : Builds a SystemLayoutInput from an XML file.
    """
    geom = SystemLayoutInput()
    runLog.info("Reading core map from {}".format(reactor))
    geom.geomType = reactor.core.geomType
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
