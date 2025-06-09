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

import dataclasses
import functools
import itertools
import typing

from armi import runLog
from armi.reactor.blocks import Block
from armi.reactor.components import Component, UnshapedComponent
from armi.reactor.converters.axialExpansionChanger.expansionData import (
    iterSolidComponents,
)
from armi.reactor.grids import MultiIndexLocation

if typing.TYPE_CHECKING:
    from armi.reactor.assemblies import Assembly


def areAxiallyLinked(componentA: Component, componentB: Component) -> bool:
    """Determine axial component linkage for two components.

    Parameters
    ----------
    componentA : :py:class:`Component <armi.reactor.components.component.Component>`
        component of interest
    componentB : :py:class:`Component <armi.reactor.components.component.Component>`
        component to compare and see if is linked to componentA

    Notes
    -----
    If componentA and componentB are both solids and the same type, geometric overlap can be checked via
    getCircleInnerDiameter and getBoundingCircleOuterDiameter. Four different cases are accounted for.
    If they do not meet these initial criteria, linkage is assumed to be False.
    Case #1: Unshaped Components. There is no way to determine overlap so they're assumed to be not linked.
    Case #2: Blocks with specified grids. If componentA and componentB have identical grid indices (cannot be a partial
    case, ALL of the indices must be contained by one or the other), then overlap can be checked.
    Case #3: If Component position is not specified via a grid, the multiplicity is checked. If consistent, they are
    assumed to be in the same positions and their overlap is checked.
    Case #4: Components are either not both solids, are not the same type, or Cases 1-3 are not True.

    Returns
    -------
    linked : bool
        status is componentA and componentB are axially linked to one another
    """
    ## Cases 4
    linked = False

    if isinstance(componentA, type(componentB)) and (
        componentA.containsSolidMaterial() and componentB.containsSolidMaterial()
    ):
        if isinstance(componentA, UnshapedComponent):
            ## Case 1
            runLog.warning(
                f"Components {componentA} and {componentB} are UnshapedComponents "
                "and do not have 'getCircleInnerDiameter' or getBoundingCircleOuterDiameter methods; "
                "nor is it physical to do so. Instead of crashing and raising an error, "
                "they are going to be assumed to not be linked.",
                single=True,
            )
        elif isinstance(componentA.spatialLocator, MultiIndexLocation) and isinstance(
            componentB.spatialLocator, MultiIndexLocation
        ):
            ## Case 2
            fromA = set(tuple(index) for index in componentA.spatialLocator.indices)
            fromB = set(tuple(index) for index in componentB.spatialLocator.indices)
            if fromA == fromB:
                linked = _checkOverlap(componentA, componentB)
        elif componentA.getDimension("mult") == componentB.getDimension("mult"):
            ## Case 3
            linked = _checkOverlap(componentA, componentB)

    return linked


def _checkOverlap(componentA: Component, componentB: Component) -> bool:
    """Check two components for geometric overlap by seeing if one can fit within the other.

    Notes
    -----
    When component dimensions are retrieved, cold=True to ensure that dimensions are evaluated
    at cold/input temperatures. At temperature, solid-solid interfaces in ARMI may produce
    slight overlaps due to thermal expansion. Handling these potential overlaps are out of scope.
    """
    idA = componentA.getCircleInnerDiameter(cold=True)
    odA = componentA.getBoundingCircleOuterDiameter(cold=True)
    idB = componentB.getCircleInnerDiameter(cold=True)
    odB = componentB.getBoundingCircleOuterDiameter(cold=True)
    biggerID = max(idA, idB)
    smallerOD = min(odA, odB)
    return biggerID < smallerOD


# Make a generic type so we can "template" the axial link class based on what could be above/below a thing
Comp = typing.TypeVar("Comp", Block, Component)


@dataclasses.dataclass
class AxialLink(typing.Generic[Comp]):
    """Small class for named references to objects above and below a specific object.

    Axial expansion in ARMI works by identifying what objects occupy the same axial space.
    For components in blocks, identify which below axially align. This is used
    to determine what, if any, mass needs to be re-assigned across blocks during expansion.
    For blocks, the linking determines what blocks need to move as a result of a specific block's
    axial expansion.

    Attributes
    ----------
    lower
        Object below, if any.

    Notes
    -----
    This class is "templated" by the type of composite that could be assigned and fetched. A
    block-to-block linkage could be type-hinted via ``AxialLink[Block]`` or ``AxialLink[Component]``
    for component-to-component link.

    See Also
    --------
    * :attr:`AxialAssemblyLinkage.linkedBlocks`
    * :attr:`AxialAssemblyLinkage.linkedComponents`
    """

    lower: typing.Optional[list[Comp]] = dataclasses.field(default=None)


class AssemblyAxialLinkage:
    """Determines and stores the block- and component-wise axial linkage for an assembly.

    Parameters
    ----------
    assem : armi.reactor.assemblies.Assembly
        Assembly to be linked

    Attributes
    ----------
    a : :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
        reference to original assembly; is directly modified/changed during expansion.
    linkedBlocks : dict
        Keys are blocks in the assembly. Their values are :class:`AxialLink` with
        ``upper`` and ``lower`` attributes for the blocks potentially above and
        below this block.
    linkedComponents : dict
        Keys are solid components in the assembly. Their values are :class:`AxialLink` with
        ``upper`` and ``lower`` attributes for the solid components potentially above and
        below this block.
    """

    linkedBlocks: dict[Block, AxialLink[Block]]
    linkedComponents: dict[Component, AxialLink[Component]]

    def __init__(self, assem: "Assembly"):
        self.a = assem
        self.linkedBlocks = self.getLinkedBlocks(assem)
        self.linkedComponents = {}
        self._determineAxialLinkage()

    @classmethod
    def getLinkedBlocks(
        cls,
        blocks: typing.Sequence[Block],
    ) -> dict[Block, AxialLink[Block]]:
        """Produce a mapping showing how blocks are linked.

        Parameters
        ----------
        blocks : sequence of armi.reactor.blocks.Block
            Ordered sequence of blocks from bottom to top. Could just as easily be an
            :class:`armi.reactor.assemblies.Assembly`.

        Returns
        -------
        dict[Block, AxialLink[Block]]
            Dictionary where keys are individual blocks and their corresponding values point
            to blocks above and below.
        """
        nBlocks = len(blocks)
        if nBlocks:
            return cls._getLinkedBlocks(blocks, nBlocks)
        raise ValueError("No blocks passed. Cannot determine links")

    @staticmethod
    def _getLinkedBlocks(blocks: typing.Sequence[Block], nBlocks: int) -> dict[Block, AxialLink[Block]]:
        # Use islice to avoid making intermediate lists of subsequences of blocks
        lower = itertools.chain((None,), itertools.islice(blocks, 0, nBlocks - 1))
        links = {}
        for low, mid in zip(lower, blocks):
            links[mid] = AxialLink(lower=low)
        return links

    def _determineAxialLinkage(self):
        """Gets the block and component based linkage."""
        for b in self.a:
            for c in iterSolidComponents(b):
                self._getLinkedComponents(b, c)

    def _findComponentLinkedTo(self, c: Component, otherBlock: typing.Optional[Block]) -> typing.Optional[Component]:
        if otherBlock is None:
            return None
        candidate = None
        # Iterate over all solid components in the other block that are linked to this one
        areLinked = functools.partial(self.areAxiallyLinked, c)
        for otherComp in filter(areLinked, iterSolidComponents(otherBlock)):
            if candidate is None:
                candidate = otherComp
            else:
                errMsg = f"""
                    Multiple component axial linkages have been found for the following component!
                        Component {c}
                          -> Block {c.parent}
                          -> Assembly {c.parent.parent}
                    This is indicative of an error in the blueprints! Candidate components in {otherBlock}:
                        {candidate}
                        {otherComp}
                """
                runLog.error(msg=errMsg)
                raise RuntimeError(errMsg)
        return candidate

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
        lowerC = self._findComponentLinkedTo(c, self.linkedBlocks[b].lower)
        lstLinkedC = AxialLink(lowerC)
        self.linkedComponents[c] = lstLinkedC

        if self.linkedBlocks[b].lower is None and lstLinkedC.lower is None:
            runLog.debug(
                f"Assembly {self.a}, Block {b}, Component {c} has nothing linked below it!",
                single=True,
            )

    @staticmethod
    def areAxiallyLinked(componentA: Component, componentB: Component) -> bool:
        """Check if two components are axially linked.

        Parameters
        ----------
        componentA : :py:class:`Component <armi.reactor.components.component.Component>`
            component of interest
        componentB : :py:class:`Component <armi.reactor.components.component.Component>`
            component to compare and see if is linked to componentA

        Returns
        -------
        bool
            Status of linkage check

        See Also
        --------
        :func:`areAxiallyLinked` for more details, including the criteria for considering components linked.
        This method is provided to allow subclasses the ability to override the linkage check.
        """
        return areAxiallyLinked(componentA, componentB)
