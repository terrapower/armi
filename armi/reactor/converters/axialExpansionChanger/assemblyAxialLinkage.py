# Copyright 2024 TerraPower, LLC
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

from armi import runLog
from armi.reactor.blocks import Block
from armi.reactor.components import Component, UnshapedComponent
from armi.reactor.converters.axialExpansionChanger.expansionData import (
    getSolidComponents,
)


def areAxiallyLinked(componentA: Component, componentB: Component) -> bool:
    """Determine axial component linkage for two components.

    Components are considered linked if the following are found to be true:

    1. Both contain solid materials.
    2. They have compatible types (e.g., ``Circle`` and ``Circle``).
    3. Their multiplicities are the same.
    4. The smallest inner bounding diameter of the two is less than the largest outer
       bounding diameter of the two.

    Parameters
    ----------
    componentA : :py:class:`Component <armi.reactor.components.component.Component>`
        component of interest
    componentB : :py:class:`Component <armi.reactor.components.component.Component>`
        component to compare and see if is linked to componentA

    Notes
    -----
    - Requires that shapes have the getCircleInnerDiameter and getBoundingCircleOuterDiameter
      defined
    - When component dimensions are retrieved, cold=True to ensure that dimensions are evaluated
      at cold/input temperatures. At temperature, solid-solid interfaces in ARMI may produce
      slight overlaps due to thermal expansion. Handling these potential overlaps are out of scope.

    Returns
    -------
    linked : bool
        status is componentA and componentB are axially linked to one another
    """
    if (
        (componentA.containsSolidMaterial() and componentB.containsSolidMaterial())
        and isinstance(componentA, type(componentB))
        and (componentA.getDimension("mult") == componentB.getDimension("mult"))
    ):
        if isinstance(componentA, UnshapedComponent):
            runLog.warning(
                f"Components {componentA} and {componentB} are UnshapedComponents "
                "and do not have 'getCircleInnerDiameter' or getBoundingCircleOuterDiameter "
                "methods; nor is it physical to do so. Instead of crashing and raising an error, "
                "they are going to be assumed to not be linked.",
                single=True,
            )
            return False
        # Check if one component could fit within the other
        idA = componentA.getCircleInnerDiameter(cold=True)
        odA = componentA.getBoundingCircleOuterDiameter(cold=True)
        idB = componentB.getCircleInnerDiameter(cold=True)
        odB = componentB.getBoundingCircleOuterDiameter(cold=True)
        biggerID = max(idA, idB)
        smallerOD = min(odA, odB)
        if biggerID >= smallerOD:
            return False
        return True
    return False


class AssemblyAxialLinkage:
    """Determines and stores the block- and component-wise axial linkage for an assembly.

    Attributes
    ----------
    a : :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
        reference to original assembly; is directly modified/changed during expansion.
    linkedBlocks : dict
        - keys = :py:class:`Block <armi.reactor.blocks.Block>`
        - values = list of axially linked blocks; index 0 = lower linked block; index 1: upper
          linked block.
    linkedComponents : dict
        - keys = :py:class:`Component <armi.reactor.components.component.Component>`
        - values = list of axially linked components; index 0 = lower linked component;
          index 1: upper linked component.
    """

    def __init__(self, StdAssem):
        self.a = StdAssem
        self.linkedBlocks = {}
        self.linkedComponents = {}
        self._determineAxialLinkage()

    def _determineAxialLinkage(self):
        """Gets the block and component based linkage."""
        for b in self.a:
            self._getLinkedBlocks(b)
            for c in getSolidComponents(b):
                self._getLinkedComponents(b, c)

    def _getLinkedBlocks(self, b: Block):
        """Retrieve the axial linkage for block b.

        Parameters
        ----------
        b : :py:class:`Block <armi.reactor.blocks.Block>`
            block to determine axial linkage for

        Notes
        -----
        - block linkage is determined by matching ztop/zbottom (see below)
        - block linkage is stored in self.linkedBlocks[b]
         _ _
        |   |
        | 2 |  Block 2 is linked to block 1.
        |_ _|
        |   |
        | 1 |  Block 1 is linked to both block 0 and 1.
        |_ _|
        |   |
        | 0 |  Block 0 is linked to block 1.
        |_ _|
        """
        lowerLinkedBlock = None
        upperLinkedBlock = None
        block_list = self.a.getChildren()
        for otherBlk in block_list:
            if b.name != otherBlk.name:
                if b.p.zbottom == otherBlk.p.ztop:
                    lowerLinkedBlock = otherBlk
                elif b.p.ztop == otherBlk.p.zbottom:
                    upperLinkedBlock = otherBlk

        self.linkedBlocks[b] = [lowerLinkedBlock, upperLinkedBlock]

        if lowerLinkedBlock is None:
            runLog.debug(
                "Assembly {0:22s} at location {1:22s}, Block {2:22s}"
                "is not linked to a block below!".format(
                    str(self.a.getName()),
                    str(self.a.getLocation()),
                    str(b.p.flags),
                ),
                single=True,
            )
        if upperLinkedBlock is None:
            runLog.debug(
                "Assembly {0:22s} at location {1:22s}, Block {2:22s}"
                "is not linked to a block above!".format(
                    str(self.a.getName()),
                    str(self.a.getLocation()),
                    str(b.p.flags),
                ),
                single=True,
            )

    def _getLinkedComponents(self, b: Block, c: Component):
        """Retrieve the axial linkage for component c.

        Parameters
        ----------
        b : :py:class:`Block <armi.reactor.blocks.Block>`
            key to access blocks containing linked components
        c : :py:class:`Component <armi.reactor.components.component.Component>`
            component to determine axial linkage for

        Raises
        ------
        RuntimeError
            multiple candidate components are found to be axially linked to a component
        """
        lstLinkedC = [None, None]
        for ib, linkdBlk in enumerate(self.linkedBlocks[b]):
            if linkdBlk is not None:
                for otherC in getSolidComponents(linkdBlk.getChildren()):
                    if areAxiallyLinked(c, otherC):
                        if lstLinkedC[ib] is not None:
                            errMsg = (
                                "Multiple component axial linkages have been found for "
                                f"Component {c}; Block {b}; Assembly {b.parent}."
                                " This is indicative of an error in the blueprints! Linked "
                                f"components found are {lstLinkedC[ib]} and {otherC}"
                            )
                            runLog.error(msg=errMsg)
                            raise RuntimeError(errMsg)
                        lstLinkedC[ib] = otherC

        self.linkedComponents[c] = lstLinkedC

        if lstLinkedC[0] is None:
            runLog.debug(
                f"Assembly {self.a}, Block {b}, Component {c} has nothing linked below it!",
                single=True,
            )
        if lstLinkedC[1] is None:
            runLog.debug(
                f"Assembly {self.a}, Block {b}, Component {c} has nothing linked above it!",
                single=True,
            )
