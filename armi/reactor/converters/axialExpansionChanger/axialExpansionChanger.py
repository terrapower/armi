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
"""Enable component-wise axial expansion for assemblies and/or a reactor."""

import re
import typing
from math import isclose
from textwrap import dedent

from numpy import array, sum
from scipy.optimize import brentq

from armi import runLog
from armi.materials.material import Fluid
from armi.reactor.assemblies import Assembly
from armi.reactor.converters.axialExpansionChanger.assemblyAxialLinkage import (
    AssemblyAxialLinkage,
)
from armi.reactor.converters.axialExpansionChanger.expansionData import (
    ExpansionData,
    iterSolidComponents,
)
from armi.reactor.flags import Flags
from armi.utils import densityTools
from armi.utils.customExceptions import InputError

if typing.TYPE_CHECKING:
    from armi.reactor.blocks import Block
    from armi.reactor.components.component import Component


def getDefaultReferenceAssem(assems):
    """Return a default reference assembly."""
    # if assemblies are defined in blueprints, handle meshing
    # assume finest mesh is reference
    assemsByNumBlocks = sorted(
        assems,
        key=lambda a: len(a),
        reverse=True,
    )
    return assemsByNumBlocks[0] if assemsByNumBlocks else None


def makeAssemsAbleToSnapToUniformMesh(assems, nonUniformAssemFlags, referenceAssembly=None):
    """Make this set of assemblies aware of the reference mesh so they can stay uniform as they axially expand."""
    if not referenceAssembly:
        referenceAssembly = getDefaultReferenceAssem(assems)
    # make the snap lists so assems know how to expand
    nonUniformAssems = [Flags.fromStringIgnoreErrors(t) for t in nonUniformAssemFlags]
    for a in assems:
        if any(a.hasFlags(f) for f in nonUniformAssems):
            continue
        a.makeAxialSnapList(referenceAssembly)


class AxialExpansionChanger:
    """
    Axially expand or contract assemblies or an entire core.

    Attributes
    ----------
    linked: :py:class:`AssemblyAxialLinkage`
        establishes object containing axial linkage information
    expansionData: :py:class:`ExpansionData <armi.reactor.converters.axialExpansionChanger.expansionData.ExpansionData>`
        establishes object to store and access relevant expansion data

    Notes
    -----
    - Is designed to work with general, vertically oriented, pin-type assembly designs. It is not set up to account
      for any other assembly type.
    - Useful for fuel performance, thermal expansion, reactivity coefficients, etc.
    """

    linked: typing.Optional[AssemblyAxialLinkage]
    expansionData: typing.Optional[ExpansionData]
    topMostBlock: typing.Optional["Block"]

    # 3cm is a presumptive lower threshold for DIF3D
    DIF3D_MIN_BLOCK_HEIGHT: float = 3.0
    # when checking the diffference between the component and block heights, 1e-12 cm is used as a threshold to account
    # for meaningful differences. This threshold filters out negligible differences arising from numerical precision
    # that otherwise have a negliglble impact on the assembly post-axial expansion. Anything larger than this value is
    # presumed to be valid of a warning that may warrant further investigation.
    COMP_BLOCK_HEIGHT_DIFF_THRESHOLD: float = 1e-12

    def __init__(self, detailedAxialExpansion: bool = False):
        """
        Build an axial expansion converter.

        Parameters
        ----------
        detailedAxialExpansion : bool, optional
            A boolean to indicate whether or not detailedAxialExpansion is to be utilized.
        """
        self._detailedAxialExpansion = detailedAxialExpansion
        self.linked = None
        self.expansionData = None
        self.topMostBlock = None

    @classmethod
    def expandColdDimsToHot(
        cls,
        assems: list,
        isDetailedAxialExpansion: bool,
        referenceAssembly=None,
    ):
        """Expand BOL assemblies, resolve disjoint axial mesh (if needed), and update block BOL heights.

        .. impl:: Perform expansion during core construction based on block heights at a specified temperature.
            :id: I_ARMI_INP_COLD_HEIGHT
            :implements: R_ARMI_INP_COLD_HEIGHT

            This method is designed to be used during core construction to axially thermally expand the
            assemblies to their "hot" temperatures (as determined by ``Thot`` values in blueprints).
            First, The Assembly is prepared for axial expansion via ``setAssembly``. In
            ``applyColdHeightMassIncrease``, the number densities on each Component is adjusted to
            reflect that Assembly inputs are at cold (i.e., ``Tinput``) temperatures. To expand to
            the requested hot temperatures, thermal expansion factors are then computed in
            ``computeThermalExpansionFactors``. Finally, the Assembly is axially thermally expanded in
            ``axiallyExpandAssembly``.

            If the setting ``detailedAxialExpansion`` is ``False``, then each Assembly gets its Block mesh
            set to match that of the "reference" Assembly (see ``getDefaultReferenceAssem`` and ``setBlockMesh``).

            Once the Assemblies are axially expanded, the Block BOL heights are updated. To account for the change in
            Block volume from axial expansion, ``completeInitialLoading`` is called to update any volume-dependent
            Block information.

        Parameters
        ----------
        assems: list[:py:class:`Assembly <armi.reactor.assemblies.Assembly>`]
            list of assemblies to be thermally expanded
        isDetailedAxialExpansion: bool
            If False, assemblies will be forced to conform to the reference mesh after expansion
        referenceAssembly: :py:class:`Assembly <armi.reactor.assemblies.Assembly>`, optional
            Assembly whose mesh other meshes will conform to if isDetailedAxialExpansion is False.
            If not provided, will assume the finest mesh assembly which is typically fuel.

        Notes
        -----
        Calling this method will result in an increase in mass via applyColdHeightMassIncrease!

        See Also
        --------
        :py:meth:`applyColdHeightMassIncrease`
        """
        assems = list(assems)
        if not referenceAssembly:
            referenceAssembly = getDefaultReferenceAssem(assems)
        axialExpChanger = cls(isDetailedAxialExpansion)
        for a in assems:
            axialExpChanger.setAssembly(a, expandFromTinputToThot=True)
            axialExpChanger.applyColdHeightMassIncrease()
            axialExpChanger.expansionData.computeThermalExpansionFactors()
            axialExpChanger.axiallyExpandAssembly()
        if not isDetailedAxialExpansion:
            for a in assems:
                a.setBlockMesh(referenceAssembly.getAxialMesh())
        # update block BOL heights to reflect hot heights
        for a in assems:
            for b in a:
                b.p.heightBOL = b.getHeight()
                b.completeInitialLoading()
                axialExpChanger._recalculateBurnup(b)

    def _recalculateBurnup(self, b):
        """After moving nuclides around, recalculate burnup."""
        for c in b.iterComponents(Flags.FUEL):
            c.p.percentBu = self._calcBurnup(c.getHMMoles(), c.p.molesHmBOL, c)
        b.p.percentBu = self._calcBurnup(b.getHMMoles(), b.p.molesHmBOL, b)

    def _calcBurnup(self, currentHM, initialHM, obj):
        """Handle edge cases in floating point math for burnup calc."""
        if initialHM == 0.0:
            return 0.0
        burnup = 100.0 * (1 - currentHM / initialHM)
        if abs(burnup) < 1e-10:
            return 0.0
        if burnup < 0.0:
            msg = (
                f"Negative burnup {burnup} encountered in axial expansion for {obj}, parent = {obj.parent}"
                f"{currentHM}, {initialHM}, {obj.parent.getHeight()}, {obj.parent.p.heightBOL}"
            )
            runLog.error(msg)
            raise ValueError(msg)
        return burnup

    def performPrescribedAxialExpansion(self, a: Assembly, components: list, percents: list, setFuel=True):
        """Perform axial expansion/contraction of an assembly given prescribed expansion percentages.

        .. impl:: Perform expansion/contraction, given a list of components and expansion coefficients.
            :id: I_ARMI_AXIAL_EXP_PRESC
            :implements: R_ARMI_AXIAL_EXP_PRESC

            This method performs component-wise axial expansion for an Assembly given expansion coefficients
            and a corresponding list of Components. In ``setAssembly``, the Assembly is prepared
            for axial expansion by determining Component-wise axial linkage and checking to see if a dummy Block
            is in place (necessary for ensuring conservation properties). The provided expansion factors are
            then assigned to their corresponding Components in ``setExpansionFactors``. Finally, the axial
            expansion is performed in ``axiallyExpandAssembly``

        Parameters
        ----------
        a : :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
            ARMI assembly to be changed
        components : list[:py:class:`Component <armi.reactor.components.component.Component>`]
            list of Components to be expanded
        percents : list[float]
            list of expansion percentages for each component listed in components
        setFuel : boolean, optional
            Boolean to determine whether or not fuel blocks should have their target components set
            This is useful when target components within a fuel block need to be determined on-the-fly.

        Notes
        -----
        - percents may be positive (expansion) or negative (contraction)
        """
        self.setAssembly(a, setFuel)
        self.expansionData.setExpansionFactors(components, percents)
        self.axiallyExpandAssembly()

    def performThermalAxialExpansion(
        self,
        a: Assembly,
        tempGrid: list,
        tempField: list,
        setFuel: bool = True,
        expandFromTinputToThot: bool = False,
    ):
        """Perform thermal expansion/contraction for an assembly given an axial temperature grid and
        field.

        .. impl:: Perform thermal expansion/contraction, given an axial temperature distribution
            over an assembly.
            :id: I_ARMI_AXIAL_EXP_THERM
            :implements: R_ARMI_AXIAL_EXP_THERM

            This method performs component-wise thermal expansion for an assembly given a discrete
            temperature distribution over the axial length of the Assembly. In ``setAssembly``, the
            Assembly is prepared for axial expansion by determining Component-wise axial linkage and
            checking to see if a dummy Block is in place (necessary for ensuring conservation
            properties). The discrete temperature distribution is then leveraged to update Component
            temperatures and compute thermal expansion factors (via
            ``updateComponentTempsBy1DTempField`` and ``computeThermalExpansionFactors``,
            respectively). Finally, the axial expansion is performed in ``axiallyExpandAssembly``.

        Parameters
        ----------
        a : :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
            ARMI assembly to be changed
        tempGrid : float, list
            Axial temperature grid (in cm) (i.e., physical locations where temp is stored)
        tempField : float, list
            Temperature values (in C) along grid
        setFuel : boolean, optional
            Boolean to determine whether or not fuel blocks should have their target components set
            This is useful when target components within a fuel block need to be determined on-the-fly.
        expandFromTinputToThot: bool
            determines if thermal expansion factors should be calculated from c.inputTemperatureInC
            to c.temperatureInC (True) or some other reference temperature and c.temperatureInC (False)
        """
        self.setAssembly(a, setFuel, expandFromTinputToThot)
        self.expansionData.updateComponentTempsBy1DTempField(tempGrid, tempField)
        self.expansionData.computeThermalExpansionFactors()
        self.axiallyExpandAssembly()

    def reset(self):
        self.linked = None
        self.expansionData = None

    def setAssembly(self, a: Assembly, setFuel=True, expandFromTinputToThot=False):
        """Set the armi assembly to be changed and init expansion data class for assembly.

        Parameters
        ----------
         a : :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
            ARMI assembly to be changed
        setFuel : boolean, optional
            Boolean to determine whether or not fuel blocks should have their target components set
            This is useful when target components within a fuel block need to be determined on-the-fly.
        expandFromTinputToThot: bool
            determines if thermal expansion factors should be calculated from c.inputTemperatureInC
            to c.temperatureInC (True) or some other reference temperature and c.temperatureInC (False)

        Notes
        -----
        When considering thermal expansion, if there is an axial temperature distribution on the
        assembly, the axial expansion methodology will NOT perfectly preserve mass. The magnitude of
        the gradient of the temperature distribution is the primary factor in determining the
        cumulative loss of mass conservation.
        """
        self.linked = AssemblyAxialLinkage(a)
        self.expansionData = ExpansionData(a, setFuel=setFuel, expandFromTinputToThot=expandFromTinputToThot)
        self._checkAssemblyConstructionIsValid()

    def _checkAssemblyConstructionIsValid(self):
        self._isTopDummyBlockPresent()
        self._checkForBlocksWithoutSolids()

    def _checkForBlocksWithoutSolids(self):
        """
        Makes sure that there aren't any blocks (other than the top-most dummy block)
        that consist entirely of fluid components. The expansion changer doesn't know
        what to do with such assemblies.
        """
        # skip top most dummy block since that is, by design, all fluid
        for b in self.linked.a[:-1]:
            if all(isinstance(c.material, Fluid) for c in b.iterComponents()):
                raise InputError(
                    f"Assembly {self.linked.a} is constructed improperly for use with the axial expansion changer "
                    f"as block, {b}, consists of exclusively fluid component(s). If this is not a mistake, consider "
                    "using the 'assemFlagsToSkipAxialExpansion' case setting to bypass performing axial expansion "
                    "on this assembly."
                )

    def applyColdHeightMassIncrease(self):
        """
        Increase component mass because they are declared at cold dims.

        Notes
        -----
        A cold 1 cm tall component will have more mass that a component with the
        same mass/length as a component with a hot height of 1 cm. This should be
        called when the setting `inputHeightsConsideredHot` is used. This adjusts
        the expansion factor applied during applyMaterialMassFracsToNumberDensities.
        """
        for c in self.linked.a.iterComponents():
            axialExpansionFactor = 1.0 + c.material.linearExpansionFactor(c.temperatureInC, c.inputTemperatureInC)
            c.changeNDensByFactor(axialExpansionFactor)

    def _isTopDummyBlockPresent(self):
        """Determines if top most block of assembly is a dummy block.

        Notes
        -----
        - If true, then axial expansion will be physical for all blocks.
        - If false, the top most block in the assembly is artificially chopped
          to preserve the assembly height. A runLog.Warning also issued.
        """
        self.topMostBlock = self.linked.a[-1]
        if not self.topMostBlock.hasFlags(Flags.DUMMY):
            runLog.warning(
                f"No dummy block present at the top of {self.linked.a}! "
                "Top most block will be artificially chopped "
                "to preserve assembly height"
            )
            if self._detailedAxialExpansion:
                msg = "Cannot run detailedAxialExpansion without a dummy block at the top of the assembly!"
                runLog.error(msg)
                raise RuntimeError(msg)

    def axiallyExpandAssembly(self):
        """Utilizes assembly linkage to do axial expansion.

        .. impl:: Preserve the total height of an ARMI assembly, during expansion.
            :id: I_ARMI_ASSEM_HEIGHT_PRES
            :implements: R_ARMI_ASSEM_HEIGHT_PRES

            The total height of an Assembly is preserved by not changing the ``ztop`` position
            of the top-most Block in an Assembly. The ``zbottom`` of the top-most Block is
            adjusted to match the Block immediately below it. The ``height`` of the
            top-most Block is is then updated to reflect any expansion/contraction.
        """
        mesh = [0.0]
        runLog.debug(
            "Printing component expansion information (growth percentage and 'target component')"
            f"for each block in assembly {self.linked.a}."
        )
        # expand all of the components
        for b in self.linked.a:
            for c in iterSolidComponents(b):
                growFrac = self.expansionData.getExpansionFactor(c)
                # component ndens and component heights are scaled to their respective growth factor
                c.changeNDensByFactor(1.0 / growFrac)
                c.zbottom = b.p.zbottom
                c.height = growFrac * b.getHeight()
                c.ztop = c.zbottom + c.height

        # align blocks on target components
        for ib, b in enumerate(self.linked.a):
            if b is not self.topMostBlock:
                targetComp = self.expansionData.getTargetComponent(b)
                # redefine block bounds based on target component
                b.p.zbottom = targetComp.zbottom
                b.p.ztop = targetComp.ztop
                b.p.height = b.p.ztop - b.p.zbottom
                b.clearCache()
                b.p.z = b.p.zbottom + b.getHeight() / 2.0
                cLinkedAbove = self.linked.linkedComponents[targetComp].upper
                if cLinkedAbove is not None:
                    if self.expansionData.isTargetComponent(cLinkedAbove):
                        # the linked component in the block above is the target component for that block. e.g., fuel to
                        # fuel. Shift this linked target component up (expansion) or down (contraction) without changing
                        # its height. In this case, component mass is conserved for both target components.
                        cLinkedAbove.zbottom = targetComp.ztop
                        cLinkedAbove.ztop = cLinkedAbove.height + cLinkedAbove.zbottom
                    else:
                        # the current target component type continues in the block above, but the target component in
                        # the block above is different. e.g., the transition from stationary duct to control material in
                        # a typical pin-based reactor control assembly design. Shift the target component in the block
                        # above up (expansion) or down (contraction) without changing its height. In this case,
                        # component mass is conserved for both target components.
                        for c in iterSolidComponents(self.linked.linkedBlocks[b].upper):
                            c.zbottom = targetComp.ztop
                            c.ztop = c.height + c.zbottom

                else:
                    bAbove = self.linked.linkedBlocks[b].upper
                    if bAbove is self.topMostBlock:
                        if not bAbove.hasFlags(Flags.DUMMY):
                            for c in iterSolidComponents(bAbove):
                                c.zbottom = b.p.ztop
                                c.ztop = c.zbottom + c.height
                    else:
                        targetCompAbove = self.expansionData.getTargetComponent(bAbove)
                        # shift the bounds of the target component in the block above to align with the bounds of the
                        # current block.
                        targetCompAbove.zbottom = b.p.ztop
                        targetCompAbove.ztop = targetCompAbove.zbottom + targetCompAbove.height

                # deal with non-target components
                for c in filter(lambda c: c is not targetComp, iterSolidComponents(b)):
                    if self.linked.linkedComponents[c].lower is None:
                        # this component is not axially linked to anything below and needs to shift with its
                        # respective parent block.
                        c.zbottom = b.p.zbottom
                        c.ztop = c.zbottom + c.height

                    cAbove = self.linked.linkedComponents[c].upper
                    if cAbove is not None:
                        # align components
                        cAbove.zbottom = c.ztop
                        cAbove.ztop = cAbove.zbottom + cAbove.height

                        # redistribute mass
                        deltaZTop = b.p.ztop - c.ztop
                        self._checkComponentHeight(c)
                        if deltaZTop > 0.0:
                            RedistributeMass(
                                fromComp=cAbove, toComp=c, assemName=repr(self.linked.a), deltaZTop=deltaZTop
                            )
                        elif deltaZTop < 0.0:
                            RedistributeMass(
                                fromComp=c, toComp=cAbove, assemName=repr(self.linked.a), deltaZTop=deltaZTop
                            )

                        # realign components based on deltaZTop
                        self._shiftLinkedCompsForDelta(c, cAbove, deltaZTop)
            else:
                b.p.zbottom = self.linked.linkedBlocks[b].lower.p.ztop
                b.p.height = b.p.ztop - b.p.zbottom
                b.p.z = b.p.zbottom + b.getHeight() / 2.0
                b.clearCache()
                # If the self.topMostBlock is a dummy block, the following is meaningless as there are no solid
                # components. However, if it is not a dummy block, we need to adjust the solid components within it in
                # order to keep their elevation information consistent with the block.
                for c in iterSolidComponents(b):
                    c.zbottom = b.p.zbottom
                    c.ztop = b.p.ztop
                    c.height = c.ztop - c.zbottom

            self._checkBlockHeight(b)
            self._recomputeBlockMassParams(b)

            # redo mesh -- functionality based on assembly.calculateZCoords()
            mesh.append(b.p.ztop)
            b.spatialLocator = self.linked.a.spatialGrid[0, 0, ib]

        bounds = list(self.linked.a.spatialGrid._bounds)
        bounds[2] = array(mesh)
        self.linked.a.spatialGrid._bounds = tuple(bounds)

    def _recomputeBlockMassParams(self, b: "Block"):
        """
        After component initial mass parameters have been adjusted for expansion,
        recompute block parameters that are derived from children.
        """
        paramsToMove = (
            "massHmBOL",
            "molesHmBOL",
        )
        for paramName in paramsToMove:
            b.p[paramName] = sum(c.p[paramName] for c in b.iterComponents() if c.p[paramName] is not None)

    def _shiftLinkedCompsForDelta(self, c: "Component", cAbove: "Component", deltaZTop: float):
        # shift the height and ztop of c downwards (-deltaZTop) or upwards (+deltaZTop)
        c.height += deltaZTop
        c.ztop += deltaZTop
        # the height of cAbove grows and zbottom moves downwards (-deltaZTop) or shrinks and moves upward (+deltaZTop)
        cAbove.height -= deltaZTop
        cAbove.zbottom += deltaZTop

    def manageCoreMesh(self, r):
        """Manage core mesh post assembly-level expansion.

        Parameters
        ----------
        r : :py:class:`Reactor <armi.reactor.reactors.Reactor>`
            ARMI reactor to have mesh modified

        Notes
        -----
        - if no detailedAxialExpansion, then do "cheap" approach to uniformMesh converter.
        - update average core mesh values with call to r.core.updateAxialMesh()
        - oldMesh will be None during initial core construction at processLoading as it has not yet
          been set.
        """
        if not self._detailedAxialExpansion:
            # loop through again now that the reference is adjusted and adjust the non-fuel assemblies.
            for a in r.core.getAssemblies():
                a.setBlockMesh(r.core.refAssem.getAxialMesh(), conserveMassFlag="auto")

        oldMesh = r.core.p.axialMesh
        r.core.updateAxialMesh()
        if oldMesh:
            runLog.extra("Updated r.core.p.axialMesh (old, new)")
            for old, new in zip(oldMesh, r.core.p.axialMesh):
                runLog.extra(f"{old:.6e}\t{new:.6e}")

    def _checkComponentHeight(self, c):
        if c.zbottom > c.ztop:
            msg = f"""
            {c} has a negative height. This is unphysical.
                Assembly: {self.linked.a}
                    Block: {c.parent}
                Component: {c}

                Component Height = {c.ztop} - {c.zbottom} = {c.height}.
            """
            raise ArithmeticError(dedent(msg))

    def _checkBlockHeight(self, b):
        """Do some basic block height validation."""
        if b.getHeight() < self.DIF3D_MIN_BLOCK_HEIGHT:
            runLog.debug(f"Block {b.name} ({str(b.p.flags)}) has a height less than 3.0 cm. ({b.getHeight():.12e})")

        if b.getHeight() < 0.0:
            raise ArithmeticError(f"Block {b.name} ({str(b.p.flags)}) has a negative height. ({b.getHeight():.12e})")

        for c in iterSolidComponents(b):
            if c.height - b.getHeight() > self.COMP_BLOCK_HEIGHT_DIFF_THRESHOLD:
                diff = c.height - b.getHeight()
                expectedChange = "increase" if diff < 0.0 else "decrease"
                if c.hasFlags(Flags.FUEL) or c.hasFlags(Flags.CONTROL):
                    msg = f"""
                    The height of {c} has gone out of sync with its parent block!
                        Assembly: {self.linked.a}
                            Block: {b}
                        Component: {c}

                            Block Height = {b.getHeight()}
                        Component Height = {c.height}

                    The difference in height is {diff} cm. This difference will result in an artificial {expectedChange}
                    in the mass of {c}. This is indicative that there are multiple axial component terminations in {b}.
                    Per the ARMI User Manual, to preserve mass there can only be one axial component termination
                    per block.
                    """
                    runLog.warning(dedent(msg), label="Component height different.")

        if self.linked.linkedBlocks[b].lower:
            lowerBlock = self.linked.linkedBlocks[b].lower
            if lowerBlock.p.ztop != b.p.zbottom:
                runLog.warning(
                    "Block heights have gone out of sync!\n"
                    f"\t{lowerBlock.getType()}: {lowerBlock.p.ztop}\n"
                    f"\t{b.getType()}: {b.p.zbottom}",
                    single=True,
                )


class RedistributeMass:
    """Given ``deltaZTop``, add mass from ``fromComp`` and give it to ``toComp``.

    Parameters
    ----------
    fromComp
        Component which is going to give mass to toComp
    toComp
        Component that is recieving mass from fromComp
    deltaZTop
        The length, in cm, of fromComp being given to toComp
    initOnly
        Optional parameter to only initialize the class and not perform the redistribution. If True, the redistribution
        can be executed by calling :py:meth:`performRedistribution`.
    """

    def __init__(
        self, fromComp: "Component", toComp: "Component", deltaZTop: float, assemName: str, initOnly: bool = False
    ):
        self.fromComp = fromComp
        self.toComp = toComp
        self.assemblyName: str = assemName
        self.deltaZTop = deltaZTop
        self.massFrom: float = 0.0
        self.massTo: float = 0.0
        if not initOnly:
            self.performRedistribution()

    def performRedistribution(self):
        """Perform the mass redistribution between two compatible components."""
        if self.compatabilityCheck():
            self.setNewToCompNDens()
            self.setNewToCompTemperature()
            if self.fromComp.p.molesHmBOL is not None and self.toComp.p.molesHmBOL is not None:
                self._adjustMassParams()

    @property
    def fromCompVolume(self):
        return self.fromComp.getArea() * abs(self.deltaZTop)

    @property
    def toCompVolume(self):
        return self.toComp.getArea() * self.toComp.height

    @property
    def newVolume(self):
        """Compute and return the new post-redistribution volume of toComp."""
        return self.toCompVolume + self.fromCompVolume

    def compatabilityCheck(self) -> bool:
        """Ensure fromComp and toComp are the same material.

        Notes
        -----
        If the linked components are not the same material, we cannot transfer mass between materials because then the
        resulting material has unknown properties.

        Returns
        -------
        False if incompatible; true otherwise.
        """
        if type(self.fromComp.material) is not type(self.toComp.material):
            msg = f"""
            Cannot redistribute mass between components that are different materials!
                Trying to redistribute mass between the following components in {self.assemblyName}:
                    from --> {self.fromComp.parent} : {self.fromComp} : {type(self.fromComp.material)}
                      to --> {self.toComp.parent} : {self.toComp} : {type(self.toComp.material)}

                Instead, mass will be removed from ({self.fromComp} | {type(self.fromComp.material)}) and
                ({self.toComp} | {type(self.toComp.material)} will be artificially expanded. The consequence is that
                mass conservation is no longer guaranteed for the {self.toComp.getType()} component type on this
                assembly!
            """
            runLog.warning(dedent(msg), label="Cannot redistribute mass between different materials.", single=True)
            return False
        return True

    def setNewToCompNDens(self):
        """Calculate the post-redistribution number densities for toComp and determine how much mass is in play for
        fromComp and toComp.

        Notes
        -----
        Only the mass of ``toComp`` is changed in this method. The mass of ``fromComp`` is changed separately by
        changing the height of ``fromComp`` -- the number densities of ``fromComp`` are not modified. When
        redistributing mass, if ``fromComp`` and ``toComp`` are different temperatures, the temperature of
        ``toComp`` will change. See :py:meth:`setNewToCompTemperature`.
        """
        # calculate the mass of each nuclide and then the ndens for the new mass
        newNDens: dict[str, float] = {}
        nucs = self._getAllNucs(self.toComp.getNuclides(), self.fromComp.getNuclides())
        for nuc in nucs:
            massByNucFrom = densityTools.getMassInGrams(nuc, self.fromCompVolume, self.fromComp.getNumberDensity(nuc))
            massByNucTo = densityTools.getMassInGrams(nuc, self.toCompVolume, self.toComp.getNumberDensity(nuc))
            newNDens[nuc] = densityTools.calculateNumberDensity(nuc, massByNucFrom + massByNucTo, self.newVolume)
            self.massFrom += massByNucFrom
            self.massTo += massByNucTo

        # Set newNDens on toComp
        self.toComp.setNumberDensities(newNDens)

    def setNewToCompTemperature(self):
        r"""Calculate and set the post-redistribution temperature of toComp.

        Notes
        -----
        Calculating this new temperature is non trivial due to thermal expansion. The following defines what the area
        of ``toComp`` is post-redistribution,

        .. math::

            A_1(\hat{T}) \left( H_1 + \delta \right) &= A_1(T_1) H_1 + A_2(T_2)\delta,\\
            A_1(\hat{T}) &= \frac{A_1(T_1) H_1 + A_2(T_2)\delta}{H_1 + \delta}.

        Where, :math:`A_1, T_1, H_1`, are the area, temperature, and height of ``toComp``, :math:`A_2, T_2`, are the
        area and temparature of ``fromComp``, :math:`\delta` is the parameter ``deltaZTop``, and :math:`\hat{T}` is
        the new temperature of ``toComp`` post-redistribution. :func:`scipy.optimize.brentq` is used to
        find the root of the above equation, indicating the value for :math:`\hat{T}`
        that finds the desired area, post-redistribution of mass.
        """
        if isclose(self.fromComp.temperatureInC, self.toComp.temperatureInC, rel_tol=1e-09):
            # per isclose documentation, rel_tol of 1e-09 is roughly equivaluent to ensuring the temps are
            # the same to roughly 9 digits.
            newToCompTemp = self.toComp.temperatureInC
        else:
            targetArea = self.newVolume / (self.toComp.height + abs(self.deltaZTop))
            try:
                newToCompTemp = brentq(
                    f=lambda T: self.toComp.getArea(Tc=T) - targetArea,
                    a=self.fromComp.temperatureInC,
                    b=self.toComp.temperatureInC,
                )
            except ValueError:
                totalMass = self.massFrom + self.massTo
                newToCompTemp = (
                    self.massFrom / totalMass * self.fromComp.temperatureInC
                    + self.massTo / totalMass * self.toComp.temperatureInC
                )
                if (self.toComp.hasFlags(Flags.FUEL) or self.toComp.hasFlags(Flags.CONTROL)) or (
                    self.fromComp.hasFlags(Flags.FUEL) or self.fromComp.hasFlags(Flags.CONTROL)
                ):
                    msg = f"""
                    Temperature search algorithm in axial expansion has failed in {self.assemblyName}
                    Trying to search for new temp between
                        from --> {self.fromComp.parent} : {self.fromComp} : {type(self.fromComp.material)} at {self.fromComp.temperatureInC} C
                        to --> {self.toComp.parent} : {self.toComp} : {type(self.toComp.material)} at {self.toComp.temperatureInC} C

                    f({self.fromComp.temperatureInC}) = {self.toComp.getArea(Tc=self.fromComp.temperatureInC) - targetArea}
                    f({self.toComp.temperatureInC}) = {self.toComp.getArea(Tc=self.toComp.temperatureInC) - targetArea}

                    Instead, a mass weighted average temperature of {newToCompTemp} will be used. The consequence is that
                    mass conservation is no longer guaranteed for this component type on this assembly!
                    """  # noqa: E501
                    runLog.warning(dedent(msg), label="Temp Search Failure")
            except Exception as ee:
                raise ee

        # Do not use component.setTemperature as this mucks with the number densities we just calculated.
        self.toComp.temperatureInC = newToCompTemp
        self.toComp.clearCache()

    def _adjustMassParams(self):
        """Adjust massHmBOL and molesHmBOL on fromComp and toComp."""
        paramsToMove = (
            "massHmBOL",
            "molesHmBOL",
        )
        removalFrac = abs(self.deltaZTop) / self.fromComp.height
        for paramName in paramsToMove:
            if self.fromComp.p[paramName] is not None:
                amountMoved = removalFrac * self.fromComp.p[paramName]
                self.toComp.p[paramName] = self.toComp.p[paramName] + amountMoved
                self.fromComp.p[paramName] = self.fromComp.p[paramName] - amountMoved

    @staticmethod
    def _sortKey(item):
        """Break isotope string down by element, atomic weight, and metastable state for sorting. Raises a RuntimeError
        if the string does not match the expected pattern.
        """
        pattern = re.compile(
            r"""
            ([a-zA-Z]{1,2}) # Element
            (\d{1,3})?      # atomic weight (optional, e.g., "C")
            ([a-zA-Z])?     # metastable state (optional, e.g., Am242M or Am242)
            """,
            re.VERBOSE,
        )
        match = re.search(pattern, item)
        if match:
            # Convert numeric parts to int for correct numerical sorting
            element = match.group(1)
            atomicWeight = int(match.group(2)) if match.group(2) else 0
            metastable = 1 if match.group(3) else 0
            return (atomicWeight, element, metastable)
        raise RuntimeError(f"Unknown isotope! - {item}")

    def _getAllNucs(self, nucsA: list[str], nucsB: list[str]) -> list[str]:
        """Return a list that contains all of the nuclides in nucsA and nucsB.

        Notes
        -----
        The returned list is sorted by :py:meth:`sortKey`. Isotopes are sorted based on 1) atomic weight, 2) element,
        and 3) metastable state.
        """
        nucsToAdd = set(nucsA).union(set(nucsB))
        return sorted(nucsToAdd, key=self._sortKey)
