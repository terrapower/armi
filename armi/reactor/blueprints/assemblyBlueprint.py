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

In addition to defining the input format, the ``AssemblyBlueprint`` class is responsible for
constructing ``Assembly`` objects. An attempt has been made to decouple ``Assembly`` construction
from the rest of ARMI as much as possible. For example, an assembly does not require a reactor to be
constructed, or a geometry file (but uses contained Block geometry type as a surrogate).
"""
import yamlize

from armi import getPluginManagerOrFail, runLog
from armi.reactor import assemblies, grids, parameters
from armi.reactor.blueprints import blockBlueprint
from armi.reactor.flags import Flags
from armi.settings.fwSettings.globalSettings import CONF_INPUT_HEIGHTS_HOT


def _configureAssemblyTypes():
    assemTypes = dict()
    pm = getPluginManagerOrFail()
    for pluginAssemTypes in pm.hook.defineAssemblyTypes():
        for blockType, assemType in pluginAssemTypes:
            assemTypes[blockType] = assemType

    return assemTypes


class Modifications(yamlize.Map):
    """
    The names of material modifications and lists of the modification values for each block in the
    assembly.
    """

    key_type = yamlize.Typed(str)
    value_type = yamlize.Sequence


class ByComponentModifications(yamlize.Map):
    """The name of a component within the block and an associated Modifications object."""

    key_type = yamlize.Typed(str)
    value_type = Modifications


class MaterialModifications(yamlize.Map):
    """
    A yamlize map for reading and holding material modifications.

    A user may specify material modifications directly as keys/values on this class, in which case
    these material modifications will be blanket applied to the entire block.

    If the user wishes to specify material modifications specific to a component within the block,
    they should use the `by component` attribute, specifying the keys/values underneath the name of
    a specific component in the block.

    .. impl:: User-impact on material definitions.
        :id: I_ARMI_MAT_USER_INPUT0
        :implements: R_ARMI_MAT_USER_INPUT

        Defines a yaml map attribute for the assembly portion of the blueprints (see
        :py:class:`~armi.blueprints.assemblyBlueprint.AssemblyBlueprint`) that allows users to
        specify material attributes as lists corresponding to each axial block in the assembly. Two
        types of specifications can be made:

            1. Key-value pairs can be specified directly, where the key is the name of the
            modification and the value is the list of block values.

            2. The "by component" attribute can be used, in which case the user can specify material
            attributes that are specific to individual components in each block. This is enabled
            through the
            :py:class:`~armi.reactor.blueprints.assemblyBlueprint.ByComponentModifications` class,
            which basically just allows for one additional layer of attributes corresponding to the
            component names.

        These material attributes can be used during the resolution of material classes during core
        instantiation (see
        :py:meth:`~armi.reactor.blueprints.blockBlueprint.BlockBlueprint.construct` and
        :py:meth:`~armi.reactor.blueprints.componentBlueprint.ComponentBlueprint.construct`).
    """

    key_type = yamlize.Typed(str)
    value_type = yamlize.Sequence
    byComponent = yamlize.Attribute(
        key="by component",
        type=ByComponentModifications,
        default=ByComponentModifications(),
    )


class AssemblyBlueprint(yamlize.Object):
    """
    A data container for holding information needed to construct an ARMI assembly.

    This class utilizes ``yamlize`` to enable serialization to and from the
    blueprints YAML file.

    .. impl:: Create assembly from blueprint file.
        :id: I_ARMI_BP_ASSEM
        :implements: R_ARMI_BP_ASSEM

        Defines a yaml construct that allows the user to specify attributes of an
        assembly from within their blueprints file, including a name, flags, specifier
        for use in defining a core map, a list of blocks, a list of block heights,
        a list of axial mesh points in each block, a list of cross section identifiers
        for each block, and material options (see :need:`I_ARMI_MAT_USER_INPUT0`).

        Relies on the underlying infrastructure from the ``yamlize`` package for
        reading from text files, serialization, and internal storage of the data.

        Is implemented as part of a blueprints file by being imported and used
        as an attribute within the larger :py:class:`~armi.reactor.blueprints.Blueprints`
        class.

        Includes a ``construct`` method, which instantiates an instance of
        :py:class:`~armi.reactor.assemblies.Assembly` with the characteristics
        as specified in the blueprints.
    """

    name = yamlize.Attribute(type=str)
    flags = yamlize.Attribute(type=str, default=None)
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
        key="material modifications",
        type=MaterialModifications,
        default=MaterialModifications(),
    )
    xsTypes = yamlize.Attribute(key="xs types", type=yamlize.StrList)
    # note: yamlizable does not call an __init__ method, instead it uses __new__ and setattr

    _assemTypes = _configureAssemblyTypes()

    @classmethod
    def getAssemClass(cls, blocks):
        """
        Get the ARMI ``Assembly`` class for the specified blocks.

        Parameters
        ----------
        blocks : list of Blocks
            Blocks for which to determine appropriate containing Assembly type
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
        cs : Settings
            Settings object which containing relevant modeling options.
        blueprint : Blueprint
            Root blueprint object containing relevant modeling options.
        """
        runLog.info("Constructing assembly `{}`".format(self.name))
        self._checkParamConsistency()
        a = self._constructAssembly(cs, blueprint)
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
        flags = None
        if self.flags is not None:
            flags = Flags.fromString(self.flags)
            a.p.flags = flags

        # set a basic grid with the right number of blocks with bounds to be adjusted.
        a.spatialGrid = grids.AxialGrid.fromNCells(len(blocks))
        a.spatialGrid.armiObject = a

        # init submeshes
        radMeshPoints = self.radialMeshPoints or 1
        a.p.RadMesh = radMeshPoints
        aziMeshPoints = self.azimuthalMeshPoints or 1
        a.p.AziMesh = aziMeshPoints

        # Loop a second time because we needed all the blocks before choosing the assembly class.
        for axialIndex, b in enumerate(blocks):
            b.name = b.makeName(a.p.assemNum, axialIndex)
            a.add(b)

        # Assign values for the parameters if they are defined on the blueprints
        for paramDef in a.p.paramDefs.inCategory(
            parameters.Category.assignInBlueprints
        ):
            val = getattr(self, paramDef.name)
            if val is not None:
                a.p[paramDef.name] = val

        return a

    @staticmethod
    def _shouldMaterialModiferBeApplied(value) -> bool:
        """Determine if a material modifier entry is applicable.

        Two exceptions:

        1. Modifiers that are empty strings are not applied.
        2. Modifiers that are ``None`` are not applied

        Parameters
        ----------
        value : object
            Entry in a material modifications array

        Returns
        -------
        bool: Result of the check
        """
        return bool(value != "" and value is not None)

    def _createBlock(self, cs, blueprint, bDesign, axialIndex):
        """Create a block based on the block design and the axial index."""
        meshPoints = self.axialMeshPoints[axialIndex]
        height = self.height[axialIndex]
        xsType = self.xsTypes[axialIndex]

        materialInput = {}

        for key, mod in {
            "byBlock": {**self.materialModifications},
            **self.materialModifications.byComponent,
        }.items():
            materialInput[key] = {
                modName: modList[axialIndex]
                for modName, modList in mod.items()
                if self._shouldMaterialModiferBeApplied(modList[axialIndex])
            }

        b = bDesign.construct(
            cs, blueprint, axialIndex, meshPoints, height, xsType, materialInput
        )

        b.completeInitialLoading()

        # set b10 volume cc since its a cold dim param
        b.setB10VolParam(cs[CONF_INPUT_HEIGHTS_HOT])
        return b

    def _checkParamConsistency(self) -> None:
        """Check that the number of block params specified is equal to the number of blocks specified."""
        # general things to check
        paramsToCheck = {
            "mesh points": self.axialMeshPoints,
            "heights": self.height,
            "xs types": self.xsTypes,
        }

        # check by-block mat mods
        for modName, modList in self.materialModifications.items():
            paramName = f"mat mod for {modName}"
            paramsToCheck[paramName] = modList

        # check by-component mat mods
        for comp in self.materialModifications.byComponent.values():
            for modName, modList in comp.items():
                paramName = f"material modifications for {modName}"
                paramsToCheck[paramName] = modList

        # perform the check
        for paramName, blockVals in paramsToCheck.items():
            if len(self.blocks) != len(blockVals):
                msg = (
                    f"Assembly {self.name} had {len(self.blocks)} block(s), but {len(blockVals)} "
                    f"'{paramName}'. These numbers should be equal. Check input for errors."
                )
                runLog.error(msg)
                raise ValueError(msg)


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
        """Used by the reactor to ``_loadComposites`` later, specifiers are two character strings."""
        return {aDesign.specifier: aDesign for aDesign in self}
