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
from armi.utils.customExceptions import InputError


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


def makeAssemsAbleToSnapToUniformMesh(
    assems, nonUniformAssemFlags, referenceAssembly=None
):
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

    def performPrescribedAxialExpansion(
        self, a: Assembly, components: list, percents: list, setFuel=True
    ):
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
        self.expansionData = ExpansionData(
            a, setFuel=setFuel, expandFromTinputToThot=expandFromTinputToThot
        )
        self._checkAssemblyConstructionIsValid()

    def _checkAssemblyConstructionIsValid(self):
        self._isTopDummyBlockPresent()
        self._checkForBlocksWithoutSolids()

    def _checkForBlocksWithoutSolids(self):
        """
        Makes sure that there aren't any blocks (other than the top-most dummy block)
        that are entirely fluid filled, unless all blocks in the assembly are only
        fluids. The expansion changer doesn't know what to do with such mixed assemblies.
        """
        for b in self.linked.a[:-1]:
            # the topmost block has already been confirmed as the dummy block
            solidCompsInBlock = list(
                filter(lambda c: not isinstance(c.material, Fluid), b.iterComponents())
            )
            if len(solidCompsInBlock) == 0:
                raise InputError(
                    f"Assembly {self.linked.a} is constructed improperly for use with the axial expansion changer "
                    f"as block, {b}, consists of exclusively fluid component(s) (excluding the top-most 'dummy' "
                    "block). If this is not a mistake, consider using the 'assemFlagsToSkipAxialExpansion' case "
                    "setting to bypass performing axial expansion on this assembly."
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
            axialExpansionFactor = 1.0 + c.material.linearExpansionFactor(
                c.temperatureInC, c.inputTemperatureInC
            )
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
        for ib, b in enumerate(self.linked.a):
            runLog.debug(msg=f"  Block {b}")
            blockHeight = b.getHeight()
            # set bottom of block equal to top of block below it
            # if ib == 0, leave block bottom = 0.0
            if ib > 0:
                b.p.zbottom = self.linked.linkedBlocks[b].lower.p.ztop
            isDummyBlock = ib == (numOfBlocks - 1)
            if not isDummyBlock:
                for c in iterSolidComponents(b):
                    growFrac = self.expansionData.getExpansionFactor(c)
                    runLog.debug(msg=f"      Component {c}, growFrac = {growFrac:.4e}")
                    c.height = growFrac * blockHeight
                    # align linked components
                    if ib == 0:
                        c.zbottom = 0.0
                    else:
                        if self.linked.linkedComponents[c].lower is not None:
                            # use linked components below
                            c.zbottom = self.linked.linkedComponents[c].lower.ztop
                        else:
                            # otherwise there aren't any linked components
                            # so just set the bottom of the component to
                            # the top of the block below it
                            c.zbottom = self.linked.linkedBlocks[b].lower.p.ztop
                    c.ztop = c.zbottom + c.height
                    # update component number densities
                    c.changeNDensByFactor(1.0 / growFrac)
                    # redistribute block boundaries if on the target component
                    if self.expansionData.isTargetComponent(c):
                        b.p.ztop = c.ztop
                        b.p.height = b.p.ztop - b.p.zbottom
            else:
                b.p.height = b.p.ztop - b.p.zbottom

            b.p.z = b.p.zbottom + b.getHeight() / 2.0

            _checkBlockHeight(b)
            # Call Component.clearCache to update the Component volume, and therefore the masses,
            # of all components.
            for c in b:
                c.clearCache()
            # redo mesh -- functionality based on assembly.calculateZCoords()
            mesh.append(b.p.ztop)
            b.spatialLocator = self.linked.a.spatialGrid[0, 0, ib]

        bounds = list(self.linked.a.spatialGrid._bounds)
        bounds[2] = array(mesh)
        self.linked.a.spatialGrid._bounds = tuple(bounds)

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
        runLog.debug(
            f"Block {b.name} ({str(b.p.flags)}) has a height less than 3.0 cm. ({b.getHeight():.12e})"
        )

    if b.getHeight() < 0.0:
        raise ArithmeticError(
            f"Block {b.name} ({str(b.p.flags)}) has a negative height! ({b.getHeight():.12e})"
        )
