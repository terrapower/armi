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
This module defines the blueprints input object for assemblies.

In addition to defining the input format, the ``AssemblyBlueprint`` class is responsible
for constructing ``Assembly`` objects. An attempt has been made to decouple ``Assembly``
construction from the rest of ARMI as much as possible. For example, an assembly does
not require a reactor to be constructed, or a geometry file (but uses ``geomType``
string as a surrogate).

"""
import yamlize

import armi
from armi import runLog
from armi.reactor import assemblies

# justification=required to populate assembly parameter definitions
from armi.reactor import parameters
from armi.reactor.blueprints import blockBlueprint
from armi.reactor import grids


def _configureAssemblyTypes():
    assemTypes = dict()
    pm = armi.getPluginManagerOrFail()
    for pluginAssemTypes in pm.hook.defineAssemblyTypes():
        for blockType, assemType in pluginAssemTypes:
            assemTypes[blockType] = assemType

    return assemTypes


class MaterialModifications(yamlize.Map):
    key_type = yamlize.Typed(str)
    value_type = yamlize.Sequence


class AssemblyBlueprint(yamlize.Object):
    """
    A data container for holding information needed to construct an ARMI assembly.

    This class utilizes ``yamlize`` to enable serialization to and from the
    blueprints YAML file.
    """

    name = yamlize.Attribute(type=str)
    specifier = yamlize.Attribute(type=str)
    blocks = yamlize.Attribute(type=blockBlueprint.BlockList)
    height = yamlize.Attribute(type=yamlize.FloatList)
    axialMeshPoints = yamlize.Attribute(key="axial mesh points", type=yamlize.IntList)
    radialMeshPoints = yamlize.Attribute(
        key="radial mesh points", type=int, default=None
    )
    azimuthalMeshPoints = yamlize.Attribute(
        key="azimuthal mesh points", type=int, default=None
    )
    materialModifications = yamlize.Attribute(
        key="material modifications", type=MaterialModifications, default=None
    )
    xsTypes = yamlize.Attribute(key="xs types", type=yamlize.StrList)
    # note: yamlizable does not call an __init__ method, instead it uses __new__ and setattr

    _assemTypes = _configureAssemblyTypes()

    @classmethod
    def getAssemClass(cls, blocks):
        """
        Get the ARMI ``Assembly`` class for the specified geomType

        Parameters
        ----------
        geomType : str
            Geometry type string.
        """
        blockClasses = {b.__class__ for b in blocks}
        for bType, aType in cls._assemTypes.items():
            if bType in blockClasses:
                return aType
        raise ValueError(
            'Unsupported block geometries in {}: "{}"'.format(cls.name, blocks)
        )

    def construct(self, cs, blueprint):
        """
        Construct an instance of this specific assembly blueprint.

        Parameters
        ----------
        cs : CaseSettings
            CaseSettings object which containing relevant modeling options.
        blueprint : Blueprint
            Root blueprint object containing relevant modeling options.
        """
        runLog.info("Constructing assembly `{}`".format(self.name))
        a = self._constructAssembly(cs, blueprint)
        self._checkParamConsistency(a)
        a.calculateZCoords()
        return a

    def _constructAssembly(self, cs, blueprint):
        """Construct the current assembly."""
        blocks = []
        for axialIndex, bDesign in enumerate(self.blocks):
            b = self._createBlock(cs, blueprint, bDesign, axialIndex)
            blocks.append(b)

        assemblyClass = self.getAssemClass(blocks)
        a = assemblyClass(self.name)
        # set a basic grid with the right number of blocks with bounds to be adjusted.
        a.spatialGrid = grids.axialUnitGrid(len(blocks))
        a.spatialGrid.armiObject = a

        # TODO: Remove mesh points from blueprints entirely. Submeshing should be
        # handled by specific physics interfaces
        radMeshPoints = self.radialMeshPoints or 1
        a.p.RadMesh = radMeshPoints
        aziMeshPoints = self.azimuthalMeshPoints or 1
        a.p.AziMesh = aziMeshPoints

        # loop a second time because we needed all the blocks before choosing the
        # assembly class.
        for axialIndex, block in enumerate(blocks):
            b.p.assemNum = a.p.assemNum
            b.name = b.makeName(a.p.assemNum, axialIndex)
            a.add(block)

        # Assign values for the parameters if they are defined on the blueprints
        for paramDef in a.p.paramDefs.inCategory(
            parameters.Category.assignInBlueprints
        ):
            val = getattr(self, paramDef.name)
            if val is not None:
                a.p[paramDef.name] = val

        return a

    def _createBlock(self, cs, blueprint, bDesign, axialIndex):
        """Create a block based on the block design and the axial index."""
        materialInputs = self.materialModifications or {}
        meshPoints = self.axialMeshPoints[axialIndex]
        height = self.height[axialIndex]
        xsType = self.xsTypes[axialIndex]
        materialInput = {
            modName: modList[axialIndex]
            for modName, modList in materialInputs.items()
            if modList[axialIndex] != ""
        }
        b = bDesign.construct(
            cs, blueprint, axialIndex, meshPoints, height, xsType, materialInput
        )

        # TODO: remove when the plugin system is fully set up?
        b.completeInitialLoading()
        return b

    def _checkParamConsistency(self, a):
        """Check that the number of block params specified is equal to the number of blocks specified."""
        materialInputs = self.materialModifications or {}
        paramsToCheck = {
            "mesh points": self.axialMeshPoints,
            "heights": self.height,
            "xs types": self.xsTypes,
        }
        for modName, modList in materialInputs.items():
            paramName = "material modifications for {}".format(modName)
            paramsToCheck[paramName] = modList

        for paramName, blockVals in paramsToCheck.items():
            if len(self.blocks) != len(blockVals):
                raise ValueError(
                    "Assembly {} had {} blocks, but {} {}. These numbers should be equal. "
                    "Check input for errors.".format(
                        a, len(self.blocks), len(blockVals), paramName
                    )
                )


for paramDef in parameters.forType(assemblies.Assembly).inCategory(
    parameters.Category.assignInBlueprints
):
    setattr(
        AssemblyBlueprint,
        paramDef.name,
        yamlize.Attribute(name=paramDef.name, default=None),
    )


class AssemblyKeyedList(yamlize.KeyedList):
    """
    Effectively and OrderedDict of assembly items, keyed on the assembly name.

    This uses yamlize KeyedList for YAML serialization.
    """

    item_type = AssemblyBlueprint
    key_attr = AssemblyBlueprint.name
    heights = yamlize.Attribute(type=yamlize.FloatList, default=None)
    axialMeshPoints = yamlize.Attribute(
        key="axial mesh points", type=yamlize.IntList, default=None
    )

    # note: yamlize does not call an __init__ method, instead it uses __new__ and setattr

    @property
    def bySpecifier(self):
        """Used by the reactor to _loadAssembliesIntoCore later, specifiers are two character strings"""
        return {aDesign.specifier: aDesign for aDesign in self}
