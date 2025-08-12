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

import typing

from numpy import array
from scipy.optimize import brentq

from armi import runLog
from armi.materials.material import Fluid
from armi.reactor.assemblies import Assembly
from armi.reactor.converters.axialExpansionChanger.assemblyAxialLinkage import (
    AssemblyAxialLinkage,
)
from armi.reactor.converters.axialExpansionChanger.expansionData import (
    ExpansionData,
    getSolidComponents,
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
    dummyBlock: typing.Optional["Block"]

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
        self.dummyBlock = None

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
        :py:meth:`armi.reactor.converters.axialExpansionChanger.axialExpansionChanger.AxialExpansionChanger.applyColdHeightMassIncrease`
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
        if self.linked.a[-1].hasFlags(Flags.DUMMY):
            self.dummyBlock = self.linked.a[-1]
        else:
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
        numOfBlocks = self.linked.a.countBlocksWithFlags()
        runLog.debug(
            "Printing component expansion information (growth percentage and 'target component')"
            f"for each block in assembly {self.linked.a}."
        )
        # expand all of the components
        for b in filter(lambda b: b is not self.dummyBlock, self.linked.a):
            for c in iterSolidComponents(b):
                growFrac = self.expansionData.getExpansionFactor(c)
                # component ndens and component heights are scaled to their respective growth factor
                c.changeNDensByFactor(1.0 / growFrac)
                c.zbottom = b.p.zbottom
                c.height = growFrac * b.getHeight()
                c.ztop = c.zbottom + c.height

        # align blocks on target components
        for ib, b in enumerate(self.linked.a):
            if b is not self.dummyBlock:
                targetComp = self.expansionData.getTargetComponent(b)
                # redefine block bounds based on target component
                b.p.zbottom = targetComp.zbottom
                b.p.ztop = targetComp.ztop
                b.p.height = b.p.ztop - b.p.zbottom
                b.clearCache()
                b.p.z = b.p.zbottom + b.getHeight() / 2.0
                cLinkedAbove = self.linked.linkedComponents[targetComp].upper
                if cLinkedAbove:
                    if self.expansionData.isTargetComponent(cLinkedAbove):
                        # the linked component in the block above is the target component for the block above.
                        # e.g., fuel to fuel. Shift the target component in the block above up (expansion) or
                        # down (contraction) without changing its height. In this case, component mass is conserved for
                        # both target components.
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

                if self.linked.linkedComponents[targetComp].upper is None and len(getSolidComponents(b)) == 1:
                    # there is no linked component above and there is only one solid component in the current block.
                    # push up (expansion) or pull down (contraction) all components in the block above.
                    # e.g., the transition from grid plate to pin assembly.
                    if self.linked.linkedBlocks[b].upper:  # split off to accommodate unit tests in other parts of ARMI
                        for c in iterSolidComponents(self.linked.linkedBlocks[b].upper):
                            c.zbottom = b.p.ztop
                            c.ztop = c.zbottom + c.height

                # deal with non-target components
                for c in filter(lambda c: c is not targetComp, iterSolidComponents(b)):
                    cAbove = self.linked.linkedComponents[c].upper
                    if cAbove is not None:
                        # align components
                        cAbove.zbottom = c.ztop
                        cAbove.ztop = cAbove.zbottom + cAbove.height

                        # redistribute mass
                        deltaZTop = b.p.ztop - c.ztop
                        if deltaZTop > 0.0:
                            # move mass, m, from the above comp to the current comp. this adds mass, m, to current comp
                            # and removes it from the above comp
                            self.redistributeMass(cAbove, c, deltaZTop)
                        elif deltaZTop < 0.0:
                            # move mass, m, from the current comp to the above comp. this adds mass, m, to the above
                            # comp and removes it from the current comp
                            self.redistributeMass(c, cAbove, deltaZTop)

                        # realign components based on deltaZTop
                        self.shiftLinkedCompsForDelta(c, cAbove, deltaZTop)
            if b is self.dummyBlock or ib == (numOfBlocks - 1):
                b.p.zbottom = self.linked.linkedBlocks[b].lower.p.ztop
                b.p.height = b.p.ztop - b.p.zbottom
                if b is not self.dummyBlock:
                    # if an assembly doesn't have a dummy block, we still need to adjust the components within it in
                    # order to keep them consistent with the block.
                    for c in iterSolidComponents(b):
                        c.zbottom = b.p.zbottom
                        c.ztop = b.p.ztop
                        c.height = c.ztop - c.zbottom

            self._checkBlockHeight(b)
            # redo mesh -- functionality based on assembly.calculateZCoords()
            mesh.append(b.p.ztop)
            b.spatialLocator = self.linked.a.spatialGrid[0, 0, ib]

        bounds = list(self.linked.a.spatialGrid._bounds)
        bounds[2] = array(mesh)
        self.linked.a.spatialGrid._bounds = tuple(bounds)

    def redistributeMass(self, fromComp: "Component", toComp: "Component", deltaZTop: float):
        self.addMassToComponent(
            fromComp=fromComp,
            toComp=toComp,
            deltaZTop=abs(deltaZTop),
        )
        self.rmMassFromComponent(
            fromComp=fromComp,
            deltaZTop=-deltaZTop,
        )

    def shiftLinkedCompsForDelta(self, c: "Component", cAbove: "Component", deltaZTop: float):
        # shift the height and ztop of the current component downwards (-deltaZTop) or upwards (+deltaZTop)
        c.height += deltaZTop
        c.ztop += deltaZTop
        # the height and zbottom of cAbove grows and moves downwards (-deltaZTop) or shrinks and moves upward (+deltaZTop)
        cAbove.height -= deltaZTop
        cAbove.zbottom += deltaZTop

    def addMassToComponent(self, fromComp: "Component", toComp: "Component", deltaZTop: float):
        r"""
        Parameters
        ----------
        fromComp
            Component which is going to give mass to toComp
        toComp
            Component that is recieving mass from fromComp
        deltaZTop
            The length, in cm, of fromComp being given to toComp

        Notes
        -----
        When redistributing mass, if ``fromComp`` and ``toComp`` are different temperatures, the temperature of
        ``toComp`` will change. Calculating this new temperature is non trivial due to thermal expansion. The following
        defines what the area of ``toComp`` is post-redictribution,

        .. math::

            A_1(\hat{T}) \left( H_1 + \delta \right) &= A_1(T_1) H_1 + A_2(T_2)\delta,
            A_1(\hat{T}) &= \frac{A_1(T_1) H_1 + A_2(T_2)\delta}{H_1 + \delta}.

        Where, :math`A_1, T_1, H_1`, are the area, temparature, and height of ``toComp``, :math:`A_2, T_2`, are the
        area and temparature of ``fromComp``, :math:`\delta` is the parameter ``deltaZTop``, and :math:`\hat{T}` is
        the new temperature of ``toComp`` post-redistribution. Brent's method within ``scipy.optimize`` is used to
        find the root of the above equation, indicating the value for :math:`\hat{T}`.
        """
        # limitation: fromComp and toComp **must** be the same materials.
        if type(fromComp.material) is not type(toComp.material):
            raise RuntimeError(
                f"Cannot redistribute mass from {fromComp} to {toComp} as they are not the same material.\n"
                f"{type(fromComp.material)} is not {type(toComp.material)}"
            )

        toCompVolume = toComp.getArea() * toComp.height
        fromCompVolume = fromComp.getArea() * abs(deltaZTop)
        newVolume = fromCompVolume + toCompVolume

        ## calculate the mass of each nuclide and then the ndens for the new mass
        newNDens: dict[str, float] = {}
        for nuc in fromComp.getNuclides():
            massByNucFrom = densityTools.getMassInGrams(nuc, fromCompVolume, fromComp.getNumberDensity(nuc))
            massByNucTo = densityTools.getMassInGrams(nuc, toCompVolume, toComp.getNumberDensity(nuc))
            newNDens[nuc] = densityTools.calculateNumberDensity(nuc, massByNucFrom + massByNucTo, newVolume)

        ## Set newNDens on toComp
        toComp.setNumberDensities(newNDens)

        # calculate the new temperature of toComp.
        if fromComp.temperatureInC == toComp.temperatureInC:
            newToCompTemp = toComp.temperatureInC
        else:
            targetArea = newVolume / (toComp.height + abs(deltaZTop))
            newToCompTemp = brentq(
                f=lambda T: toComp.getArea(Tc=T) - targetArea, a=fromComp.temperatureInC, b=toComp.temperatureInC
            )
        # Do not use component.setTemperature as this mucks with the number densities we just calculated.
        toComp.temperatureInC = newToCompTemp
        toComp.clearCache()

    def rmMassFromComponent(self, fromComp: "Component", deltaZTop: float):
        """Create new number densities for the component that is having mass removed."""
        # calculate the new volume
        newFromCompVolume = fromComp.getArea() * (fromComp.height + deltaZTop)

        ## calculate the mass of each nuclide and then the ndens for the new mass
        newNDens: dict[str, float] = {}
        for nuc in fromComp.getNuclides():
            massByNucFrom = densityTools.getMassInGrams(nuc, newFromCompVolume, fromComp.getNumberDensity(nuc))
            newNDens[nuc] = densityTools.calculateNumberDensity(nuc, massByNucFrom, newFromCompVolume)

        # Set newNDens on fromComp
        fromComp.setNumberDensities(newNDens)

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

    def _checkBlockHeight(self, b):
        """
        Do some basic block height validation.

        Notes
        -----
        3cm is a presumptive lower threshold for DIF3D
        """
        if b.getHeight() < 3.0:
            runLog.debug(f"Block {b.name} ({str(b.p.flags)}) has a height less than 3.0 cm. ({b.getHeight():.12e})")

        if b.getHeight() < 0.0:
            raise ArithmeticError(f"Block {b.name} ({str(b.p.flags)}) has a negative height! ({b.getHeight():.12e})")

        for c in iterSolidComponents(b):
            if c.height - b.getHeight() > 1e-12:
                msg = f"Component heights have gotten out of sync with height of {b}.\nBlock Height = {b.getHeight()}"
                for c in iterSolidComponents(b):
                    msg += f"\n{c}, {c.height}"
                raise RuntimeError(msg)

        if self.linked.linkedBlocks[b].lower:
            lowerBlock = self.linked.linkedBlocks[b].lower
            if lowerBlock.p.ztop != b.p.zbottom:
                raise RuntimeError(
                    "Block heights have gone out of sync!\n"
                    f"\t{lowerBlock.getType()}: {lowerBlock.p.ztop}\n"
                    f"\t{b.getType()}: {b.p.zbottom}"
                )
