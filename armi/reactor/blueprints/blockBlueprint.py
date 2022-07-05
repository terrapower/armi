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
This module defines the ARMI input for a block definition, and code for constructing an ARMI ``Block``.
"""
import collections

import yamlize

from armi import getPluginManagerOrFail, runLog
from armi.reactor import blocks
from armi.reactor import parameters
from armi.reactor.flags import Flags
from armi.reactor.blueprints import componentBlueprint
from armi.reactor.converters import blockConverters
from armi.settings.fwSettings import globalSettings


def _configureGeomOptions():
    blockTypes = dict()
    pm = getPluginManagerOrFail()
    for pluginBlockTypes in pm.hook.defineBlockTypes():
        for compType, blockType in pluginBlockTypes:
            blockTypes[compType] = blockType

    return blockTypes


class BlockBlueprint(yamlize.KeyedList):
    """Input definition for Block."""

    item_type = componentBlueprint.ComponentBlueprint
    key_attr = componentBlueprint.ComponentBlueprint.name
    name = yamlize.Attribute(key="name", type=str)
    gridName = yamlize.Attribute(key="grid name", type=str, default=None)
    flags = yamlize.Attribute(type=str, default=None)
    axialExpTargetComponent = yamlize.Attribute(
        key="axial expansion target component", type=str, default=None
    )
    _geomOptions = _configureGeomOptions()

    def _getBlockClass(self, outerComponent):
        """
        Get the ARMI ``Block`` class for the specified outerComponent.

        Parameters
        ----------
        outerComponent : Component
            Largest component in block.
        """
        for compCls, blockCls in self._geomOptions.items():
            if isinstance(outerComponent, compCls):
                return blockCls

        raise ValueError(
            "Block input for {} has outer component {} which is "
            " not a supported Block geometry subclass. Update geometry."
            "".format(self.name, outerComponent)
        )

    def construct(
        self, cs, blueprint, axialIndex, axialMeshPoints, height, xsType, materialInput
    ):
        """
        Construct an ARMI ``Block`` to be placed in an ``Assembly``.

        Parameters
        ----------
        cs : CaseSettings
            CaseSettings object for the appropriate simulation.

        blueprint : Blueprints
            Blueprints object containing various detailed information, such as nuclides to model

        axialIndex : int
            The Axial index this block exists within the parent assembly

        axialMeshPoints : int
            number of mesh points for use in the neutronics kernel

        height : float
            initial height of the block

        xsType : str
            String representing the xsType of this block.

        materialInput : dict
            Double-layered dict.
            Top layer groups the by-block material modifications under the `byBlock` key
            and the by-component material modifications under the component's name.
            The inner dict under each key contains material modification names and values.

        """
        runLog.debug("Constructing block {}".format(self.name))
        components = collections.OrderedDict()
        # build grid before components so you can load
        # the components into the grid.
        gridDesign = self._getGridDesign(blueprint)
        if gridDesign:
            spatialGrid = gridDesign.construct()
        else:
            spatialGrid = None

        self._checkByComponentMaterialInput(materialInput)

        for componentDesign in self:
            filteredMaterialInput = self._filterMaterialInput(
                materialInput, componentDesign
            )
            c = componentDesign.construct(blueprint, filteredMaterialInput)
            components[c.name] = c
            if spatialGrid:
                componentLocators = gridDesign.getMultiLocator(
                    spatialGrid, componentDesign.latticeIDs
                )
                if componentLocators:
                    # this component is defined in the block grid
                    # We can infer the multiplicity from the grid.
                    # Otherwise it's a component that is in a block
                    # with grids but that's not in the grid itself.
                    c.spatialLocator = componentLocators
                    mult = c.getDimension("mult")
                    if mult and mult != 1.0 and mult != len(c.spatialLocator):
                        raise ValueError(
                            f"Conflicting ``mult`` input ({mult}) and number of "
                            f"lattice positions ({len(c.spatialLocator)}) for {c}. "
                            "Recommend leaving off ``mult`` input when using grids."
                        )
                    elif not mult or mult == 1.0:
                        # learn mult from grid definition
                        c.setDimension("mult", len(c.spatialLocator))

        # Resolve linked dims after all components in the block are created
        for c in components.values():
            c.resolveLinkedDims(components)

        boundingComp = sorted(components.values())[-1]
        # give a temporary name (will be updated by b.makeName as real blocks populate systems)
        b = self._getBlockClass(boundingComp)(name=f"block-bol-{axialIndex:03d}")

        for paramDef in b.p.paramDefs.inCategory(
            parameters.Category.assignInBlueprints
        ):
            val = getattr(self, paramDef.name)
            if val is not None:
                b.p[paramDef.name] = val

        flags = None
        if self.flags is not None:
            flags = Flags.fromString(self.flags)

        b.setType(self.name, flags)

        if self.axialExpTargetComponent is not None:
            try:
                b.setAxialExpTargetComp(components[self.axialExpTargetComponent])
            except KeyError as noMatchingComponent:
                raise RuntimeError(
                    "Block {0} --> axial expansion target component {1} specified in the blueprints does not "
                    "match any component names. Revise axial expansion target component in blueprints "
                    "to match the name of a component and retry.".format(
                        b,
                        self.axialExpTargetComponent,
                    )
                ) from noMatchingComponent

        for c in components.values():
            b.add(c)
        b.p.nPins = b.getNumPins()
        b.p.axMesh = _setBlueprintNumberOfAxialMeshes(
            axialMeshPoints, cs["axialMeshRefinementFactor"]
        )
        b.p.height = height
        b.p.heightBOL = height  # for fuel performance
        b.p.xsType = xsType
        b.setBuLimitInfo()
        b = self._mergeComponents(b)
        b.verifyBlockDims()
        b.spatialGrid = spatialGrid

        if b.spatialGrid is None and cs[globalSettings.CONF_BLOCK_AUTO_GRID]:
            try:
                b.autoCreateSpatialGrids()
            except (ValueError, NotImplementedError) as e:
                runLog.warning(str(e), single=True)

        # now that components are in blocks we have heights and can actually
        # compute the mults of the component groups.
        b.updateComponentGroupMults()

        return b

    def _checkByComponentMaterialInput(self, materialInput):
        for component in materialInput:
            if component != "byBlock":
                if component not in [componentDesign.name for componentDesign in self]:
                    if materialInput[component]:  # ensure it is not empty
                        raise ValueError(
                            f"The component '{component}' used to specify a by-component"
                            f" material modification is not in block '{self.name}'."
                        )

    @staticmethod
    def _filterMaterialInput(materialInput, componentDesign):
        """
        Get the by-block material modifications and those specifically for this
        component.

        If a material modification is specified both by-block and by-component
        for a given component, the by-component value will be used.
        """
        filteredMaterialInput = {}

        # first add the by-block modifications without question
        if "byBlock" in materialInput:
            for modName, modVal in materialInput["byBlock"].items():
                filteredMaterialInput[modName] = modVal

        # then get the by-component modifications as appropriate
        for component, mod in materialInput.items():
            if component == "byBlock":
                pass  # we already added these
            else:
                # these are by-component mods, first test if the component matches
                # before adding. if component matches, add the modifications,
                # overwriting any by-block modifications of the same type
                if component == componentDesign.name:
                    for modName, modVal in mod.items():
                        filteredMaterialInput[modName] = modVal

        return filteredMaterialInput

    def _getGridDesign(self, blueprint):
        """
        Get the appropriate grid design

        This happens when a lattice input is provided on the block. Otherwise all
        components are ambiguously defined in the block.
        """
        if self.gridName:
            if self.gridName not in blueprint.gridDesigns:
                raise KeyError(
                    f"Lattice {self.gridName} defined on {self} is not "
                    "defined in the blueprints `lattices` section."
                )
            return blueprint.gridDesigns[self.gridName]
        return None

    @staticmethod
    def _mergeComponents(b):
        solventNamesToMergeInto = set(
            c.p.mergeWith for c in b.iterComponents() if c.p.mergeWith
        )

        if solventNamesToMergeInto:
            runLog.warning(
                "Component(s) {} in block {} has merged components inside it. The merge was valid at hot "
                "temperature, but the merged component only has the basic thermal expansion factors "
                "of the component(s) merged into. Expansion properties or dimensions of non hot  "
                "temperature may not be representative of how the original components would have acted had "
                "they not been merged. It is recommended that merging happen right before "
                "a physics calculation using a block converter to avoid this."
                "".format(solventNamesToMergeInto, b.name),
                single=True,
            )

        for solventName in solventNamesToMergeInto:
            soluteNames = []

            for c in b:
                if c.p.mergeWith == solventName:
                    soluteNames.append(c.name)

            converter = blockConverters.MultipleComponentMerger(
                b, soluteNames, solventName
            )
            b = converter.convert()

        return b


for paramDef in parameters.forType(blocks.Block).inCategory(
    parameters.Category.assignInBlueprints
):
    setattr(
        BlockBlueprint,
        paramDef.name,
        yamlize.Attribute(name=paramDef.name, default=None),
    )


def _setBlueprintNumberOfAxialMeshes(meshPoints, factor):
    """
    Set the blueprint number of axial mesh based on the axial mesh refinement factor.
    """
    if factor <= 0:
        raise ValueError(
            "A positive axial mesh refinement factor "
            f"must be provided. A value of {factor} is invalid."
        )

    if factor != 1:
        runLog.important(
            "An axial mesh refinement factor of {} is applied "
            "to blueprint based on setting specification.".format(factor),
            single=True,
        )
    return int(meshPoints) * factor


class BlockKeyedList(yamlize.KeyedList):
    """
    An OrderedDict of BlockBlueprints keyed on the name. Utilizes yamlize for serialization to and from YAML.

    This is used within the ``blocks:`` main entry of the blueprints.
    """

    item_type = BlockBlueprint
    key_attr = BlockBlueprint.name


class BlockList(yamlize.Sequence):
    """
    A list of BlockBlueprints keyed on the name. Utilizes yamlize for serialization to and from YAML.

    This is used to define the ``blocks:`` attribute of the assembly definitions.
    """

    item_type = BlockBlueprint
