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

from statistics import mean
from typing import List

from armi import runLog
from armi.materials import material
from armi.reactor.components import UnshapedComponent
from armi.reactor.flags import Flags
from numpy import array

TARGET_FLAGS_IN_PREFERRED_ORDER = [
    Flags.FUEL,
    Flags.CONTROL,
    Flags.POISON,
    Flags.SHIELD,
    Flags.SLUG,
]


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


def expandColdDimsToHot(
    assems: list,
    isDetailedAxialExpansion: bool,
    referenceAssembly=None,
):
    """
    Expand BOL assemblies, resolve disjoint axial mesh (if needed), and update block BOL heights.

    Parameters
    ----------
    assems: list[:py:class:`Assembly <armi.reactor.assemblies.Assembly>`]
        list of assemblies to be thermally expanded
    isDetailedAxialExpansion: bool
        If False, assemblies will be forced to conform to the reference mesh after expansion
    referenceAssembly: :py:class:`Assembly <armi.reactor.assemblies.Assembly>`, optional
        Assembly whose mesh other meshes will conform to if isDetailedAxialExpansion is False.
        If not provided, will assume the finest mesh assembly which is typically fuel.
    """
    assems = list(assems)
    if not referenceAssembly:
        referenceAssembly = getDefaultReferenceAssem(assems)
    axialExpChanger = AxialExpansionChanger(isDetailedAxialExpansion)
    for a in assems:
        axialExpChanger.setAssembly(a, coldHeightsToHot=True)
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


class AxialExpansionChanger:
    """
    Axially expand or contract assemblies or an entire core.

    Attributes
    ----------
    linked : :py:class:`AssemblyAxialLinkage`
        establishes object containing axial linkage information
    expansionData : :py:class:`ExpansionData <armi.reactor.converters.axialExpansionChanger.ExpansionData>`
        establishes object to store and access relevant expansion data

    Notes
    -----
    - Is designed to work with general, vertically oriented, pin-type assembly designs. It is not set up to account
      for any other assembly type.
    - Useful for fuel performance, thermal expansion, reactivity coefficients, etc.
    """

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

    def performPrescribedAxialExpansion(
        self, a, componentLst: list, percents: list, setFuel=True
    ):
        """Perform axial expansion of an assembly given prescribed expansion percentages.

        Parameters
        ----------
        a : :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
            ARMI assembly to be changed
        componentLst : list[:py:class:`Component <armi.reactor.components.component.Component>`]
            list of Components to be expanded
        percents : list[float]
            list of expansion percentages for each component listed in componentList
        setFuel : boolean, optional
            Boolean to determine whether or not fuel blocks should have their target components set
            This is useful when target components within a fuel block need to be determined on-the-fly.

        Notes
        -----
        - percents may be positive (expansion) or negative (contraction)
        """
        self.setAssembly(a, setFuel)
        self.expansionData.setExpansionFactors(componentLst, percents)
        self.axiallyExpandAssembly()

    def performThermalAxialExpansion(
        self,
        a,
        tempGrid: list,
        tempField: list,
        setFuel: bool = True,
        coldHeightsToHot: bool = False,
    ):
        """Perform thermal expansion for an assembly given an axial temperature grid and field.

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
        """
        self.setAssembly(a, setFuel, coldHeightsToHot)
        self.expansionData.updateComponentTempsBy1DTempField(tempGrid, tempField)
        self.expansionData.computeThermalExpansionFactors()
        self.axiallyExpandAssembly()

    def reset(self):
        self.linked = None
        self.expansionData = None

    def setAssembly(self, a, setFuel=True, coldHeightsToHot=False):
        """Set the armi assembly to be changed and init expansion data class for assembly.

        Parameters
        ----------
         a : :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
            ARMI assembly to be changed
        setFuel : boolean, optional
            Boolean to determine whether or not fuel blocks should have their target components set
            This is useful when target components within a fuel block need to be determined on-the-fly.
        """
        self.linked = AssemblyAxialLinkage(a)
        self.expansionData = ExpansionData(a, setFuel, coldHeightsToHot)
        self._isTopDummyBlockPresent()

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
        for c in self.linked.a.getComponents():
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
        blkLst = self.linked.a.getBlocks()
        if not blkLst[-1].hasFlags(Flags.DUMMY):
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
        """Utilizes assembly linkage to do axial expansion."""
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
                b.p.zbottom = self.linked.linkedBlocks[b][0].p.ztop
            isDummyBlock = ib == (numOfBlocks - 1)
            if not isDummyBlock:
                for c in getSolidComponents(b):
                    growFrac = self.expansionData.getExpansionFactor(c)
                    runLog.debug(msg=f"      Component {c}, growFrac = {growFrac:.4e}")
                    c.height = growFrac * blockHeight
                    # align linked components
                    if ib == 0:
                        c.zbottom = 0.0
                    else:
                        if self.linked.linkedComponents[c][0] is not None:
                            # use linked components below
                            c.zbottom = self.linked.linkedComponents[c][0].ztop
                        else:
                            # otherwise there aren't any linked components
                            # so just set the bottom of the component to
                            # the top of the block below it
                            c.zbottom = self.linked.linkedBlocks[b][0].p.ztop
                    c.ztop = c.zbottom + c.height
                    # update component number densities
                    newNumberDensities = {
                        nuc: c.getNumberDensity(nuc) / growFrac
                        for nuc in c.getNuclides()
                    }
                    c.setNumberDensities(newNumberDensities)
                    # redistribute block boundaries if on the target component
                    if self.expansionData.isTargetComponent(c):
                        b.p.ztop = c.ztop
                        b.p.height = b.p.ztop - b.p.zbottom
            else:
                b.p.height = b.p.ztop - b.p.zbottom

            b.p.z = b.p.zbottom + b.getHeight() / 2.0

            _checkBlockHeight(b)
            # call component.clearCache to update the component volume, and therefore the masses, of all solid components.
            for c in getSolidComponents(b):
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
                a.setBlockMesh(r.core.refAssem.getAxialMesh())

        oldMesh = r.core.p.axialMesh
        r.core.updateAxialMesh()
        if oldMesh:
            runLog.extra("Updated r.core.p.axialMesh (old, new)")
            for old, new in zip(oldMesh, r.core.p.axialMesh):
                runLog.extra(f"{old:.6e}\t{new:.6e}")


def getSolidComponents(b):
    """
    Return list of components in the block that have solid material.

    Notes
    -----
    Axial expansion only needs to be applied to solid materials. We should not update
    number densities on fluid materials to account for changes in block height.
    """
    return [c for c in b if not isinstance(c.material, material.Fluid)]


def _checkBlockHeight(b):
    """
    Do some basic block height validation.

    Notes
    -----
    3cm is a presumptive lower threshhold for DIF3D
    """
    if b.getHeight() < 3.0:
        runLog.debug(
            "Block {0:s} ({1:s}) has a height less than 3.0 cm. ({2:.12e})".format(
                b.name, str(b.p.flags), b.getHeight()
            )
        )

    if b.getHeight() < 0.0:
        raise ArithmeticError(
            "Block {0:s} ({1:s}) has a negative height! ({2:.12e})".format(
                b.name, str(b.p.flags), b.getHeight()
            )
        )


class AssemblyAxialLinkage:
    """Determines and stores the block- and component-wise axial linkage for an assembly.

    Attributes
    ----------
    a : :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
        reference to original assembly; is directly modified/changed during expansion.

    linkedBlocks : dict
        keys   --> :py:class:`Block <armi.reactor.blocks.Block>`

        values --> list of axially linked blocks; index 0 = lower linked block; index 1: upper linked block.

        see also: self._getLinkedBlocks()

    linkedComponents : dict
        keys -->   :py:class:`Component <armi.reactor.components.component.Component>`

        values --> list of axially linked components; index 0 = lower linked component; index 1: upper linked component.

        see also: self._getLinkedComponents
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

    def _getLinkedBlocks(self, b):
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

    def _getLinkedComponents(self, b, c):
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
                    if _determineLinked(c, otherC):
                        if lstLinkedC[ib] is not None:
                            errMsg = (
                                "Multiple component axial linkages have been found for "
                                f"Component {c}; Block {b}; Assembly {b.parent}."
                                " This is indicative of an error in the blueprints! Linked components found are"
                                f"{lstLinkedC[ib]} and {otherC}"
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


def _determineLinked(componentA, componentB):
    """Determine axial component linkage for two components.

    Parameters
    ----------
    componentA : :py:class:`Component <armi.reactor.components.component.Component>`
        component of interest
    componentB : :py:class:`Component <armi.reactor.components.component.Component>`
        component to compare and see if is linked to componentA

    Notes
    -----
    - Requires that shapes have the getCircleInnerDiameter and getBoundingCircleOuterDiameter defined
    - For axial linkage to be True, components MUST be solids, the same Component Class, multiplicity, and meet inner
      and outer diameter requirements.
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
                "and do not have 'getCircleInnerDiameter' or getBoundingCircleOuterDiameter methods; "
                "nor is it physical to do so. Instead of crashing and raising an error, "
                "they are going to be assumed to not be linked.",
                single=True,
            )
            linked = False
        else:
            idA, odA = (
                componentA.getCircleInnerDiameter(cold=True),
                componentA.getBoundingCircleOuterDiameter(cold=True),
            )
            idB, odB = (
                componentB.getCircleInnerDiameter(cold=True),
                componentB.getBoundingCircleOuterDiameter(cold=True),
            )

            biggerID = max(idA, idB)
            smallerOD = min(odA, odB)
            if biggerID >= smallerOD:
                # one object fits inside the other
                linked = False
            else:
                linked = True

    else:
        linked = False

    return linked


class ExpansionData:
    """Object containing data needed for axial expansion."""

    def __init__(self, a, setFuel: bool, coldHeightsToHot: bool):
        self._a = a
        self.componentReferenceTemperature = {}
        self._expansionFactors = {}
        self._componentDeterminesBlockHeight = {}
        self._setTargetComponents(setFuel)
        self.coldHeightsToHot = coldHeightsToHot

    def setExpansionFactors(self, componentLst: List, expFrac: List):
        """Sets user defined expansion fractions.

        Parameters
        ----------
        componentLst : List[:py:class:`Component <armi.reactor.components.component.Component>`]
            list of Components to have their heights changed
        expFrac : List[float]
            list of L1/L0 height changes that are to be applied to componentLst

        Raises
        ------
        RuntimeError
            If componentLst and expFrac are different lengths
        """
        if len(componentLst) != len(expFrac):
            runLog.error(
                f"Number of components and expansion fractions must be the same!\n"
                f"    len(componentLst) = {len(componentLst)}\n"
                f"        len(expFrac) = {len(expFrac)}"
            )
            raise RuntimeError
        if 0.0 in expFrac:
            msg = "An expansion fraction, L1/L0, equal to 0.0, is not physical. Expansion fractions should be greater than 0.0."
            runLog.error(msg)
            raise RuntimeError(msg)
        for exp in expFrac:
            if exp < 0.0:
                msg = "A negative expansion fraction, L1/L0, is not physical. Expansion fractions should be greater than 0.0."
                runLog.error(msg)
                raise RuntimeError(msg)
        for c, p in zip(componentLst, expFrac):
            self._expansionFactors[c] = p

    def updateComponentTempsBy1DTempField(self, tempGrid, tempField):
        """Assign a block-average axial temperature to components.

        Parameters
        ----------
        tempGrid : numpy array
            1D axial temperature grid (i.e., physical locations where temp is stored)
        tempField : numpy array
            temperature values along grid

        Notes
        -----
        - given a 1D axial temperature grid and distribution, searches for temperatures that fall
          within the bounds of a block, and averages them
        - this average temperature is then passed to self.updateComponentTemp()

        Raises
        ------
        ValueError
            if no temperature points found within a block
        RuntimeError
            if tempGrid and tempField are different lengths
        """
        if len(tempGrid) != len(tempField):
            runLog.error("tempGrid and tempField must have the same length.")
            raise RuntimeError

        self.componentReferenceTemperature = {}  # reset, just to be safe
        for b in self._a:
            tmpMapping = []
            for idz, z in enumerate(tempGrid):
                if b.p.zbottom <= z <= b.p.ztop:
                    tmpMapping.append(tempField[idz])
                if z > b.p.ztop:
                    break

            if len(tmpMapping) == 0:
                raise ValueError(
                    f"{b} has no temperature points within it!"
                    "Likely need to increase the refinement of the temperature grid."
                )

            blockAveTemp = mean(tmpMapping)
            for c in b:
                self.updateComponentTemp(c, blockAveTemp)

    def updateComponentTemp(self, c, temp: float):
        """Update component temperatures with a provided temperature.

        Parameters
        ----------
        c : :py:class:`Component <armi.reactor.components.component.Component>`
            component to which the temperature, temp, is to be applied
        temp : float
            new component temperature in C

        Notes
        -----
        - "reference" height and temperature are the current states; i.e. before
           1) the new temperature, temp, is applied to the component, and
           2) the component is axially expanded
        """
        self.componentReferenceTemperature[c] = c.temperatureInC
        c.setTemperature(temp)

    def computeThermalExpansionFactors(self):
        """Computes expansion factors for all components via thermal expansion."""
        for b in self._a:
            for c in getSolidComponents(b):
                if self.coldHeightsToHot:
                    # get expansion based on cold to hot exp factor
                    self._expansionFactors[c] = c.getThermalExpansionFactor()
                elif c in self.componentReferenceTemperature:
                    growFrac = c.getThermalExpansionFactor(
                        T0=self.componentReferenceTemperature[c]
                    )
                    self._expansionFactors[c] = growFrac
                else:
                    # we want expansion factors relative to componentReferenceTemperature not Tinput.
                    # But for this component there isn't a componentReferenceTemperature,
                    # so we'll assume that the expansion factor is 1.0.
                    self._expansionFactors[c] = 1.0

    def getExpansionFactor(self, c):
        """Retrieves expansion factor for c.

        Parameters
        ----------
        c : :py:class:`Component <armi.reactor.components.component.Component>`
            Component to retrive expansion factor for
        """
        value = self._expansionFactors.get(c, 1.0)
        return value

    def _setTargetComponents(self, setFuel):
        """Sets target component for each block.

        Parameters
        ----------
        setFuel : bool
            boolean to determine if fuel block should have its target component set. Useful for when
            target components should be determined on the fly.
        """
        for b in self._a:
            if b.p.axialExpTargetComponent:
                self._componentDeterminesBlockHeight[
                    b.getComponentByName(b.p.axialExpTargetComponent)
                ] = True
            elif b.hasFlags(Flags.PLENUM) or b.hasFlags(Flags.ACLP):
                self.determineTargetComponent(b, Flags.CLAD)
            elif b.hasFlags(Flags.DUMMY):
                self.determineTargetComponent(b, Flags.COOLANT)
            elif setFuel and b.hasFlags(Flags.FUEL):
                self._isFuelLocked(b)
            else:
                self.determineTargetComponent(b)

    def determineTargetComponent(self, b, flagOfInterest=None):
        """Determines target component, stores it on the block, and appends it to self._componentDeterminesBlockHeight.

        Parameters
        ----------
        b : :py:class:`Block <armi.reactor.blocks.Block>`
            block to specify target component for
        flagOfInterest : :py:class:`Flags <armi.reactor.flags.Flags>`
            the flag of interest to identify the target component

        Notes
        -----
        - if flagOfInterest is None, finds the component within b that contains flags that
          are defined in a preferred order of flags, or barring that, in b.p.flags
        - if flagOfInterest is not None, finds the component that contains the flagOfInterest.

        Raises
        ------
        RuntimeError
            no target component found
        RuntimeError
            multiple target components found
        """
        if flagOfInterest is None:
            # Follow expansion of most neutronically important component, fuel first then control/poison
            for targetFlag in TARGET_FLAGS_IN_PREFERRED_ORDER:
                componentWFlag = [c for c in b.getChildren() if c.hasFlags(targetFlag)]
                if componentWFlag != []:
                    break
            # some blocks/components are not included in the above list but should still be found
            if not componentWFlag:
                componentWFlag = [c for c in b.getChildren() if c.p.flags in b.p.flags]
        else:
            componentWFlag = [c for c in b.getChildren() if c.hasFlags(flagOfInterest)]
        if len(componentWFlag) == 0:
            # if only 1 solid, be smart enought to snag it
            solidMaterials = list(
                c for c in b if not isinstance(c.material, material.Fluid)
            )
            if len(solidMaterials) == 1:
                componentWFlag = solidMaterials
        if len(componentWFlag) == 0:
            raise RuntimeError(f"No target component found!\n   Block {b}")
        if len(componentWFlag) > 1:
            raise RuntimeError(
                f"Cannot have more than one component within a block that has the target flag!"
                f"Block {b}\nflagOfInterest {flagOfInterest}\nComponents {componentWFlag}"
            )
        self._componentDeterminesBlockHeight[componentWFlag[0]] = True
        b.p.axialExpTargetComponent = componentWFlag[0].name

    def _isFuelLocked(self, b):
        """Physical/realistic implementation reserved for ARMI plugin.

        Parameters
        ----------
        b : :py:class:`Block <armi.reactor.blocks.Block>`
            block to specify target component for

        Raises
        ------
        RuntimeError
            multiple fuel components found within b

        Notes
        -----
        - This serves as an example to check for fuel/clad locking/interaction found in SFRs.
        - A more realistic/physical implementation is reserved for ARMI plugin(s).
        """
        c = b.getComponent(Flags.FUEL)
        if c is None:
            raise RuntimeError(f"No fuel component within {b}!")
        self._componentDeterminesBlockHeight[c] = True
        b.p.axialExpTargetComponent = c.name

    def isTargetComponent(self, c):
        """Returns bool if c is a target component.

        Parameters
        ----------
        c : :py:class:`Component <armi.reactor.components.component.Component>`
            Component to check target component status
        """
        return bool(c in self._componentDeterminesBlockHeight)
