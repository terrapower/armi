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

"""This module defines the ARMI input for a block definition, and code for constructing an ARMI ``Block``."""

import collections
from inspect import signature
from typing import Iterable, Iterator, Set

import yamlize

from armi import getPluginManagerOrFail, runLog
from armi.materials.material import Material
from armi.reactor import blocks, parameters
from armi.reactor.blueprints import componentBlueprint
from armi.reactor.components.component import Component
from armi.reactor.composites import Composite
from armi.reactor.converters import blockConverters
from armi.reactor.flags import Flags
from armi.settings.fwSettings.globalSettings import CONF_INPUT_HEIGHTS_HOT


def _configureGeomOptions():
    blockTypes = dict()
    pm = getPluginManagerOrFail()
    for pluginBlockTypes in pm.hook.defineBlockTypes():
        for compType, blockType in pluginBlockTypes:
            blockTypes[compType] = blockType

    return blockTypes


class BlockBlueprint(yamlize.KeyedList):
    """Input definition for Block.

    .. impl:: Create a Block from blueprint file.
        :id: I_ARMI_BP_BLOCK
        :implements: R_ARMI_BP_BLOCK

        Defines a yaml construct that allows the user to specify attributes of a block from within
        their blueprints file, including a name, flags, a radial grid to specify locations of pins,
        and the name of a component which drives the axial expansion of the block (see
        :py:mod:`~armi.reactor.converters.axialExpansionChanger`).

        In addition, the user may specify key-value pairs to specify the components contained within
        the block, where the keys are component names and the values are component blueprints (see
        :py:class:`~armi.reactor.blueprints.ComponentBlueprint.ComponentBlueprint`).

        Relies on the underlying infrastructure from the ``yamlize`` package for reading from text
        files, serialization, and internal storage of the data.

        Is implemented into a blueprints file by being imported and used as an attribute within the
        larger :py:class:`~armi.reactor.blueprints.Blueprints` class.

        Includes a ``construct`` method, which instantiates an instance of
        :py:class:`~armi.reactor.blocks.Block` with the characteristics as specified in the
        blueprints.
    """

    item_type = componentBlueprint.ComponentBlueprint
    key_attr = componentBlueprint.ComponentBlueprint.name
    name = yamlize.Attribute(key="name", type=str)
    gridName = yamlize.Attribute(key="grid name", type=str, default=None)
    flags = yamlize.Attribute(type=str, default=None)
    axialExpTargetComponent = yamlize.Attribute(key="axial expansion target component", type=str, default=None)
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

    def construct(self, cs, blueprint, axialIndex, axialMeshPoints, height, xsType, materialInput):
        """
        Construct an ARMI ``Block`` to be placed in an ``Assembly``.

        Parameters
        ----------
        cs : Settings
            Settings object for the appropriate simulation.

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

        allLatticeIds = set()
        for componentDesign in self:
            filteredMaterialInput, byComponentMatModKeys = self._filterMaterialInput(materialInput, componentDesign)
            c = componentDesign.construct(
                blueprint,
                filteredMaterialInput,
                cs[CONF_INPUT_HEIGHTS_HOT],
            )
            components[c.name] = c

            # check that the mat mods for this component are valid options
            # this will only examine by-component mods, block mods are done later
            if isinstance(c, Component):
                # there are other things like composite groups that don't get
                # material modifications -- skip those
                validMatModOptions = self._getMaterialModsFromBlockChildren(c)
                for key in byComponentMatModKeys:
                    if key not in validMatModOptions:
                        raise ValueError(f"{c} in block {self.name} has invalid material modification: {key}")

            if spatialGrid:
                componentLocators = gridDesign.getMultiLocator(spatialGrid, componentDesign.latticeIDs)
                if componentLocators:
                    # this component is defined in the block grid
                    # We can infer the multiplicity from the grid.
                    # Otherwise it's a component that is in a block
                    # with grids but that's not in the grid itself.
                    c.spatialLocator = componentLocators
                    mult = c.getDimension("mult")
                    if mult and mult != 1.0 and mult != len(c.spatialLocator):
                        raise ValueError(
                            f"For {c} in {self.name} there is a conflicting ``mult`` input ({mult}) "
                            f"and number of lattice positions ({len(c.spatialLocator)}). "
                            "Recommend leaving off ``mult`` input when using grids."
                        )
                    elif not mult or mult == 1.0:
                        # learn mult from grid definition
                        c.setDimension("mult", len(c.spatialLocator))

                idsInGrid = list(gridDesign.gridContents.values())
                if componentDesign.latticeIDs:
                    for latticeID in componentDesign.latticeIDs:
                        allLatticeIds.add(str(latticeID))
                        # the user has given this component latticeIDs. check that
                        # each of the ids appears in the grid, otherwise
                        # their blueprints are probably wrong
                        if len([i for i in idsInGrid if i == str(latticeID)]) == 0:
                            raise ValueError(
                                f"latticeID {latticeID} in block blueprint '{self.name}' is expected "
                                "to be present in the associated block grid. "
                                "Check that the component's latticeIDs align with the block's grid."
                            )

        # for every id in grid, confirm that at least one component had it
        if gridDesign:
            idsInGrid = list(gridDesign.gridContents.values())
            for idInGrid in idsInGrid:
                if str(idInGrid) not in allLatticeIds:
                    raise ValueError(
                        f"ID {idInGrid} in grid {gridDesign.name} is not in any components of block {self.name}. "
                        "All IDs in the grid must appear in at least one component."
                    )

        # check that the block level mat mods use valid options in the same way
        # as we did for the by-component mods above
        validMatModOptions = self._getBlockwiseMaterialModifierOptions(components.values())

        if "byBlock" in materialInput:
            for key in materialInput["byBlock"]:
                if key not in validMatModOptions:
                    raise ValueError(f"Block {self.name} has invalid material modification key: {key}")

        # Resolve linked dims after all components in the block are created
        for c in components.values():
            c.resolveLinkedDims(components)

        boundingComp = sorted(components.values())[-1]
        # give a temporary name (will be updated by b.makeName as real blocks populate systems)
        b = self._getBlockClass(boundingComp)(name=f"block-bol-{axialIndex:03d}")

        for paramDef in b.p.paramDefs.inCategory(parameters.Category.assignInBlueprints):
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
                    f"Block {b} --> axial expansion target component {self.axialExpTargetComponent} "
                    "specified in the blueprints does not match any component names. "
                    "Revise axial expansion target component in blueprints "
                    "to match the name of a component and retry."
                ) from noMatchingComponent

        for c in components.values():
            b.add(c)
        b.p.nPins = b.getNumPins()
        b.p.axMesh = _setBlueprintNumberOfAxialMeshes(axialMeshPoints, cs["axialMeshRefinementFactor"])
        b.p.height = height
        b.p.heightBOL = height  # for fuel performance
        b.p.xsType = xsType
        b.setBuLimitInfo()
        b = self._mergeComponents(b)
        b.verifyBlockDims()
        b.spatialGrid = spatialGrid

        return b

    def _getBlockwiseMaterialModifierOptions(self, children: Iterable[Composite]) -> Set[str]:
        """Collect all the material modifiers that exist on a block."""
        validMatModOptions = set()
        for c in children:
            perChildModifiers = self._getMaterialModsFromBlockChildren(c)
            validMatModOptions.update(perChildModifiers)
        return validMatModOptions

    def _getMaterialModsFromBlockChildren(self, c: Composite) -> Set[str]:
        """Collect all the material modifiers from a child of a block."""
        perChildModifiers = set()
        for material in self._getMaterialsInComposite(c):
            for materialParentClass in material.__class__.__mro__:
                # we must loop over parents as well, since applyInputParams
                # could call to Parent.applyInputParams()
                if issubclass(materialParentClass, Material):
                    perChildModifiers.update(signature(materialParentClass.applyInputParams).parameters.keys())
        # self is a parameter to methods, so it gets picked up here
        # but that's obviously not a real material modifier
        perChildModifiers.discard("self")
        return perChildModifiers

    def _getMaterialsInComposite(self, child: Composite) -> Iterator[Material]:
        """Collect all the materials in a composite."""
        # Leaf node, no need to traverse further down
        if isinstance(child, Component):
            yield child.material
            return
        # Don't apply modifications to other things that could reside
        # in a block e.g., component groups

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
        byComponentMatModKeys = set()

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
                        byComponentMatModKeys.add(modName)
                        filteredMaterialInput[modName] = modVal

        return filteredMaterialInput, byComponentMatModKeys

    def _getGridDesign(self, blueprint):
        """
        Get the appropriate grid design.

        This happens when a lattice input is provided on the block. Otherwise all
        components are ambiguously defined in the block.
        """
        if self.gridName:
            if self.gridName not in blueprint.gridDesigns:
                raise KeyError(
                    f"Lattice {self.gridName} defined on {self} is not defined in the blueprints `lattices` section."
                )
            return blueprint.gridDesigns[self.gridName]
        return None

    @staticmethod
    def _mergeComponents(b):
        solventNamesToMergeInto = set(c.p.mergeWith for c in b.iterComponents() if c.p.mergeWith)

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

            converter = blockConverters.MultipleComponentMerger(b, soluteNames, solventName)
            b = converter.convert()

        return b


for paramDef in parameters.forType(blocks.Block).inCategory(parameters.Category.assignInBlueprints):
    setattr(
        BlockBlueprint,
        paramDef.name,
        yamlize.Attribute(name=paramDef.name, default=None),
    )


def _setBlueprintNumberOfAxialMeshes(meshPoints, factor):
    """Set the blueprint number of axial mesh based on the axial mesh refinement factor."""
    if factor <= 0:
        raise ValueError(f"A positive axial mesh refinement factor must be provided. A value of {factor} is invalid.")

    if factor != 1:
        runLog.important(
            "An axial mesh refinement factor of {} is applied to blueprint based on setting specification.".format(
                factor
            ),
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
