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

import armi
from armi import runLog
from armi.reactor import blocks
from armi.reactor import parameters
from armi.reactor.blueprints import componentBlueprint
from armi.reactor.converters import blockConverters
from armi.reactor.locations import AXIAL_CHARS
from armi.reactor import grids


def _configureGeomOptions():
    blockTypes = dict()
    pm = armi.getPluginManagerOrFail()
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
    _geomOptions = _configureGeomOptions()

    def _getBlockClass(self, outerComponent):
        """
        Get the ARMI ``Block`` class for the specified geomType.

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
            dict containing material modification names and values
        """
        runLog.debug("Constructing block {}".format(self.name))
        appliedMatMods = False
        components = collections.OrderedDict()
        # build grid before components so you can load
        # the components into the grid.
        gridDesign = self._getGridDesign(blueprint)
        if gridDesign:
            spatialGrid = gridDesign.construct()
        else:
            spatialGrid = None
        for componentDesign in self:
            c = componentDesign.construct(blueprint, materialInput)
            components[c.name] = c
            if spatialGrid:
                c.spatialLocator = gridDesign.getMultiLocator(
                    spatialGrid, componentDesign.latticeIDs
                )
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

        for c in components.values():
            c._resolveLinkedDims(components)

        boundingComp = sorted(components.values())[-1]
        b = self._getBlockClass(boundingComp)("Bxxx{0}".format(AXIAL_CHARS[axialIndex]))

        for paramDef in b.p.paramDefs.inCategory(
            parameters.Category.assignInBlueprints
        ):
            val = getattr(self, paramDef.name)
            if val is not None:
                b.p[paramDef.name] = val

        b.setType(self.name)
        for c in components.values():
            b.addComponent(c)
        b.p.nPins = b.getNumPins()
        b.p.axMesh = _setBlueprintNumberOfAxialMeshes(
            axialMeshPoints, cs["axialMeshRefinementFactor"]
        )
        b.p.height = height
        b.p.heightBOL = height  # for fuel performance
        b.p.xsType = xsType
        b.setBuLimitInfo(cs)
        b.buildNumberDensityParams(nucNames=blueprint.allNuclidesInProblem)
        b = self._mergeComponents(b)
        b.verifyBlockDims()
        b.spatialGrid = spatialGrid

        return b

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

    def _mergeComponents(self, b):
        solventNamesToMergeInto = set(c.p.mergeWith for c in b if c.p.mergeWith)

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
