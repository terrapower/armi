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
from textwrap import dedent

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
                        if deltaZTop > 0.0:
                            # move mass, m, from the above comp to the current comp. this adds mass, m, to current comp
                            # and removes it from the above comp
                            self.redistributeMass(fromComp=cAbove, toComp=c, deltaZTop=deltaZTop)
                        elif deltaZTop < 0.0:
                            # move mass, m, from the current comp to the above comp. this adds mass, m, to the above
                            # comp and removes it from the current comp
                            self.redistributeMass(fromComp=c, toComp=cAbove, deltaZTop=deltaZTop)

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
            # since some heavy metal may have moved around (e.g., if there are multiple fuel pins in a block), update
            # BOL params that are useful for burnup and other calculations that rely on the HM inventory of a block.

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

    def redistributeMass(self, fromComp: "Component", toComp: "Component", deltaZTop: float):
        """This is a wrapper method to perform a complete redistribution of mass between two components.

        Parameters
        ----------
        fromComp
            Component which is going to give mass to toComp
        toComp
            Component that is recieving mass from fromComp
        deltaZTop
            The length, in cm, of fromComp being given to toComp

        See Also
        --------
        :py:meth:`_addMassToComponent`
        :py:meth:`_adjustComponentMassParams`
        """
        self._addMassToComponent(
            fromComp=fromComp,
            toComp=toComp,
            deltaZTop=abs(deltaZTop),
        )

        self._adjustMassParams(
            fromComp=fromComp,
            toComp=toComp,
            deltaZTop=abs(deltaZTop),
        )

    def _addMassToComponent(self, fromComp: "Component", toComp: "Component", deltaZTop: float):
        r"""Given ``deltaZTop``, add mass from ``fromComp`` and give it to ``toComp``.

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
        Only the mass of ``toComp`` is changed in this method. The mass of ``fromComp`` is effectively
        changed separately by changing the height of ``fromComp`` -- the number densities of
        ``fromComp`` are not modified.

        The new temperature of ``toComp`` is determined by a simple mass-weighted average temperature
        between ``toComp`` and the mass being moved over from ``fromComp``. This implicitly assumes (1)
        that ``toComp`` and ``fromComp`` are the same material and (2) that the specific heat is
        constant between the two temperatures. (2) is a reasonable assumption is reasonable because
        the difference in temperature across two blocks axially should be small. (1) is fine because
        this method raises a ``RunTimeError`` if the two components are not the same material.

        Raises
        ------
        RuntimeError if the linked components are not the same material; we cannot transfer mass between materials
        because then the resulting material has unknown properties.
        """
        # limitation: fromComp and toComp **must** be the same materials.
        if type(fromComp.material) is not type(toComp.material):
            msg = f"""
            Cannot redistribute mass between components that are different materials!
                Trying to redistribte mass between the following components in {self.linked.a}:
                    from --> {fromComp.parent} : {fromComp} : {type(fromComp.material)}
                      to --> {toComp.parent} : {toComp} : {type(toComp.material)}

                Instead, mass will be removed from ({fromComp} | {type(fromComp.material)}) and
                ({toComp} | {type(toComp.material)} will be artificially expanded. The consequence is that mass
                conservation is no longer guaranteed for the {toComp.getType()} component type on this assembly!
            """
            runLog.warning(dedent(msg))
            return

        toCompVolume = toComp.getArea() * toComp.height
        fromCompVolume = fromComp.getArea() * abs(deltaZTop)

        ## calculate the mass of each nuclide
        newMass: dict[str, float] = {}
        massTo = massFrom = 0
        for nuc in fromComp.getNuclides():
            massByNucFrom = densityTools.getMassInGrams(nuc, fromCompVolume, fromComp.getNumberDensity(nuc))
            massByNucTo = densityTools.getMassInGrams(nuc, toCompVolume, toComp.getNumberDensity(nuc))
            newMass[nuc] = massByNucFrom + massByNucTo
            massFrom += massByNucFrom
            massTo += massByNucTo

        # calculate the new temperature, then area & volume of toComp
        if abs(fromComp.temperatureInC - toComp.temperatureInC) < 1e-10:
            newToCompTemp = toComp.temperatureInC
        else:
            newToCompTemp = ((toComp.temperatureInC * massTo) + (fromComp.temperatureInC * massFrom)) / (
                massTo + massFrom
            )
        toComp.setTemperature(newToCompTemp)
        newToCompArea = toComp.getArea()
        newVolume = newToCompArea * (toComp.height + abs(deltaZTop))

        ## calculate the ndens for each nuclide
        newNDens: dict[str, float] = {}
        for nuc in fromComp.getNuclides():
            newNDens[nuc] = densityTools.calculateNumberDensity(nuc, newMass[nuc], newVolume)

        ## Set newNDens on toComp
        toComp.setNumberDensities(newNDens)

        toComp.clearCache()

    def _adjustMassParams(self, fromComp: "Component", toComp: "Component", deltaZTop: float):
        """
        Adjust the following parameters on fromComp and toComp:

        * massHmBOL
        * molesHmBOL
        """
        paramsToMove = (
            "massHmBOL",
            "molesHmBOL",
        )
        removalFrac = abs(deltaZTop) / fromComp.height
        for paramName in paramsToMove:
            if fromComp.p[paramName] is not None:
                amountMoved = removalFrac * fromComp.p[paramName]
                toComp.p[paramName] = toComp.p[paramName] + amountMoved
                fromComp.p[paramName] = fromComp.p[paramName] - amountMoved

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
                diff = c.height - b.getHeight()
                expectedChange = "increase" if diff < 0.0 else "decrease"
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
                runLog.warning(dedent(msg))

        if self.linked.linkedBlocks[b].lower:
            lowerBlock = self.linked.linkedBlocks[b].lower
            if lowerBlock.p.ztop != b.p.zbottom:
                runLog.warning(
                    "Block heights have gone out of sync!\n"
                    f"\t{lowerBlock.getType()}: {lowerBlock.p.ztop}\n"
                    f"\t{b.getType()}: {b.p.zbottom}",
                    single=True,
                )
