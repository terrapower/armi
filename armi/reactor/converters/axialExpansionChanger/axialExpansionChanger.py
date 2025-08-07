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

from numpy import array, array_equal

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
        top = self.linked.a[-1]
        if not top.hasFlags(Flags.DUMMY):
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
        for ib, b in enumerate(self.linked.a):
            isDummyBlock = ib == (numOfBlocks - 1)
            if not isDummyBlock:
                for c in iterSolidComponents(b):
                    growFrac = self.expansionData.getExpansionFactor(c)
                    # component ndens and component heights are scaled to their respective growth factor
                    c.changeNDensByFactor(1.0 / growFrac)
                    c.zbottom = b.p.zbottom
                    c.height = growFrac * b.getHeight()
                    c.ztop = c.zbottom + c.height

        # align blocks on target components
        for ib, b in enumerate(self.linked.a):
            isDummyBlock = ib == (numOfBlocks - 1)
            if not isDummyBlock:
                targetComp = self.expansionData.getTargetComponent(b)
                # redefine block bounds based on target component
                b.p.zbottom = targetComp.zbottom
                b.p.ztop = targetComp.ztop
                b.p.height = b.p.ztop - b.p.zbottom
                b.clearCache()
                b.p.z = b.p.zbottom + b.getHeight() / 2.0
                # if the linked component above is the target component for the block above, align them
                # e.g., for expansion, this shifts up the target component in the block above
                if self.expansionData.isTargetComponent(self.linked.linkedComponents[targetComp].upper):
                    targetCompAbove = self.linked.linkedComponents[targetComp].upper
                    targetCompAbove.zbottom = targetComp.ztop
                    targetCompAbove.ztop = targetCompAbove.height + targetCompAbove.zbottom

                # deal with non-target components
                for c in filter(lambda c: c is not targetComp, iterSolidComponents(b)):

                    cAbove = self.linked.linkedComponents[c].upper
                    if cAbove:
                        # align components
                        cAbove.zbottom = c.ztop
                        cAbove.ztop = cAbove.zbottom + cAbove.height

                        # redistribute mass
                        delta = b.p.ztop - c.ztop
                        if delta > 0.0:
                            ## only move mass from the above comp to the current comp. mass removal from the
                            #  above comp happens when the lower bound of the above block shifts up
                            self.addMassToComponent(
                                fromComp=cAbove,
                                toComp=c,
                                delta=delta,
                            )
                            self.rmMassFromComponent(
                                fromComp=cAbove,
                                delta=-delta,
                            )
                            # shift the height and ztop of the current component upwards
                            c.height += delta
                            c.ztop += delta
                            # the height of cAbove shrinks and the zbottom moves upwards
                            cAbove.height -= delta
                            cAbove.zbottom += delta
                        elif delta < 0.0:
                            ## only move mass from the comp to the comp above. mass removal from the
                            #  current comp happens when the upper bound of the current block shifts down
                            self.addMassToComponent(
                                fromComp=c,
                                toComp=cAbove,
                                delta=delta,
                            )
                            self.rmMassFromComponent(
                                fromComp=c,
                                delta=-delta,
                            )
                            # shift the height and ztop of the current component downwards (delta is negative!)
                            c.height += delta
                            c.ztop += delta
                            # the height of cAbove grows and the zbottom moves downwards (delta is negative!)
                            cAbove.height -= delta
                            cAbove.zbottom += delta
                        else:
                            pass
            else:
                b.p.zbottom = self.linked.linkedBlocks[b].lower.p.ztop
                b.p.height = b.p.ztop - b.p.zbottom

            _checkBlockHeight(b)
            # redo mesh -- functionality based on assembly.calculateZCoords()
            mesh.append(b.p.ztop)
            b.spatialLocator = self.linked.a.spatialGrid[0, 0, ib]

        bounds = list(self.linked.a.spatialGrid._bounds)
        bounds[2] = array(mesh)
        self.linked.a.spatialGrid._bounds = tuple(bounds)

    def addMassToComponent(self, fromComp: "Component", toComp: "Component", delta: float):
        """
        Parameters
        ----------
        fromComp
            Component which is going to give mass to toComp
        toComp
            Component that is recieving mass from fromComp
        delta
            The length, in cm, of fromComp being given to toComp
        """
        # limitation: fromComp and toComp **must** have the same isotopics.
        nucsFrom = fromComp.getNuclides()
        nucsTo = toComp.getNuclides()
        if not array_equal(nucsFrom, nucsTo):
            runLog.warning(
                f"Cannot redistribute mass from {fromComp} to {toComp} as they do not have the same nuclides.\n"
                f"Instead, {toComp} will have it's mass changed based on the difference between its ztop and the top"
                "of its block."
            )
            if delta > 0:
                # expansion, add mass to toComp
                return self._noRedistribution(toComp, delta)
            else:
                # contraction, add mass to fromComp
                return self._noRedistribution(fromComp, delta)

        ## calculate new number densities for each isotope based on the expected total mass
        toCompVolume = toComp.getArea() * toComp.height
        fromCompVolume = fromComp.getArea() * abs(delta)
        newVolume = fromCompVolume + toCompVolume

        ## calculate the mass of each nuclide
        massByNucFrom = {}
        massByNucTo = {}
        for nuc in nucsFrom:
            massByNucFrom[nuc] = densityTools.getMassInGrams(nuc, fromCompVolume, fromComp.getNumberDensity(nuc))
            massByNucTo[nuc] = densityTools.getMassInGrams(nuc, toCompVolume, toComp.getNumberDensity(nuc))

        ## calculate the ndens from the new mass
        newNDens: dict[str, float] = {}
        for nuc in nucsFrom:
            newNDens[nuc] = densityTools.calculateNumberDensity(nuc, massByNucFrom[nuc] + massByNucTo[nuc], newVolume)

        ## Set newNDens on toComp
        toComp.setNumberDensities(newNDens)

    def rmMassFromComponent(self, fromComp: "Component", delta: float):
        """Create new number densities for the component that is having mass removed."""
        nucsFrom = fromComp.getNuclides()

        # calculate the new volume
        newFromCompVolume = fromComp.getArea() * (fromComp.height + delta)

        # calculate the mass of each nuclide for the given new volume
        massByNucFrom = {}
        for nuc in nucsFrom:
            massByNucFrom[nuc] = densityTools.getMassInGrams(nuc, newFromCompVolume, fromComp.getNumberDensity(nuc))

        # calculate the number density of each nuclide for the given new volume
        newNDens: dict[str, float] = {}
        for nuc in nucsFrom:
            newNDens[nuc] = densityTools.calculateNumberDensity(nuc, massByNucFrom[nuc], newFromCompVolume)

        # Set newNDens on fromComp
        fromComp.setNumberDensities(newNDens)


    def _noRedistribution(self, c: "Component", delta: float):
        """Calculate new number densities for each isotope based on the expected total mass.

        Parameters
        ----------
        c
            Component which is going to have mass increased by a length of delta
        delta
            The length, in cm, which corresponds to how much mass will increase by
        """
        # get new volume
        newVolume = c.getArea() * (c.height + delta)
        # get mass fractions per nuclide for the new volume
        massByNucTo = {}
        for nuc in c.getNuclides():
            massByNucTo[nuc] = densityTools.getMassInGrams(nuc, newVolume, c.getNumberDensity(nuc))
        # calculate the number densities that generate the new mass per nuclide
        newNDens: dict[str, float] = {}
        for nuc in c.getNuclides():
            newNDens[nuc] = densityTools.calculateNumberDensity(nuc, massByNucTo[nuc], newVolume)
        ## Set newNDens on toComp
        c.setNumberDensities(newNDens)

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


def _checkBlockHeight(b):
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
            msg = f"Component heights in the block have gotten out of sync with block height.\n{b.getHeight()}"
            for c in iterSolidComponents(b):
                msg += f"\n{c, c.height}"
            raise RuntimeError(msg)
