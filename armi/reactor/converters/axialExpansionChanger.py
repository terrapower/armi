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
"""enable component-wise axial expansion for assemblies and/or a reactor"""

from statistics import mean
from numpy import array
from armi import runLog
from armi.reactor.flags import Flags
from armi.reactor.components import UnshapedComponent

TARGET_FLAGS_IN_PREFERRED_ORDER = [
    Flags.FUEL,
    Flags.CONTROL,
    Flags.POISON,
    Flags.SHIELD,
    Flags.SLUG,
]


class AxialExpansionChanger:
    """
    Axially expand or contract assemblies or an entire core.

    Attributes
    ----------
    linked : :py:class:`AssemblyAxialLinkage` object.
        establishes object containing axial linkage information
    expansionData : :py:class:`ExpansionData <armi.reactor.converters.axialExpansionChanger.ExpansionData>` object.
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
        """Perform axial expansion of an assembly given prescribed expansion percentages

        Parameters
        ----------
        a : :py:class:`Assembly <armi.reactor.assemblies.Assembly>` object.
            ARMI assembly to be changed
        componentList : :py:class:`Component <armi.reactor.components.component.Component>`, list
            list of :py:class:`Component <armi.reactor.components.component.Component>` objects to be expanded
        percents : float, list
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
        self.axiallyExpandAssembly(thermal=False)

    def performThermalAxialExpansion(
        self, a, tempGrid: list, tempField: list, setFuel=True
    ):
        """Perform thermal expansion for an assembly given an axial temperature grid and field

        Parameters
        ----------
        a : :py:class:`Assembly <armi.reactor.assemblies.Assembly>` object.
            ARMI assembly to be changed
        tempGrid : float, list
            Axial temperature grid (in cm) (i.e., physical locations where temp is stored)
        tempField : float, list
            Temperature values (in C) along grid
        setFuel : boolean, optional
            Boolean to determine whether or not fuel blocks should have their target components set
            This is useful when target components within a fuel block need to be determined on-the-fly.
        """
        self.setAssembly(a, setFuel)
        self.expansionData.updateComponentTempsBy1DTempField(tempGrid, tempField)
        self.expansionData.computeThermalExpansionFactors()
        self.axiallyExpandAssembly(thermal=True)

    def reset(self):
        self.linked = None
        self.expansionData = None

    def setAssembly(self, a, setFuel=True):
        """set the armi assembly to be changed and init expansion data class for assembly

        Parameters
        ----------
         a : :py:class:`Assembly <armi.reactor.assemblies.Assembly>` object.
            ARMI assembly to be changed
        setFuel : boolean, optional
            Boolean to determine whether or not fuel blocks should have their target components set
            This is useful when target components within a fuel block need to be determined on-the-fly.
        """
        self.linked = AssemblyAxialLinkage(a)
        self.expansionData = ExpansionData(a, setFuel)
        self._isTopDummyBlockPresent()

    def applyColdHeightMassIncrease(self):
        """
        Increase component mass because they are declared at cold dims

        Notes
        -----
        A cold 1 cm tall component will have more mass that a component with the
        same mass/length as a component with a hot height of 1 cm. This should be
        called when the setting `inputHeightsConsideredHot` is used. This basically
        undoes component.applyHotHeightDensityReduction
        """
        for c in self.linked.a.getComponents():
            axialExpansionFactor = 1.0 + c.material.linearExpansionFactor(
                c.temperatureInC, c.inputTemperatureInC
            )
            c.changeNDensByFactor(axialExpansionFactor)

    def _isTopDummyBlockPresent(self):
        """determines if top most block of assembly is a dummy block

        Notes
        -----
        - If true, then axial expansion will be physical for all blocks.
        - If false, the top most block in the assembly is artificially chopped
          to preserve the assembly height. A runLog.Warning also issued.
        """
        blkLst = self.linked.a.getBlocks()
        if not blkLst[-1].hasFlags(Flags.DUMMY):
            runLog.warning(
                "No dummy block present at the top of {0}! "
                "Top most block will be artificially chopped "
                "to preserve assembly height".format(self.linked.a)
            )
            if self._detailedAxialExpansion:
                msg = "Cannot run detailedAxialExpansion without a dummy block at the top of the assembly!"
                runLog.error(msg)
                raise RuntimeError(msg)

    def axiallyExpandAssembly(self, thermal: bool = False):
        """Utilizes assembly linkage to do axial expansion

        Parameters
        ----------
        thermal : bool, optional
            boolean to determine whether or not expansion is thermal or non-thermal driven

        Notes
        -----
            The "thermal" parameter plays a role as thermal expansion is relative to the
            BOL heights where non-thermal is relative to the most recent height.
        """
        mesh = [0.0]
        numOfBlocks = self.linked.a.countBlocksWithFlags()
        runLog.debug(
            "Printing component expansion information (growth percentage and 'target component')"
            "for each block in assembly {0}.".format(self.linked.a)
        )
        for ib, b in enumerate(self.linked.a):
            runLog.debug(msg="  Block {0}".format(b))
            if thermal:
                blockHeight = b.p.heightBOL
            else:
                blockHeight = b.p.height
            # set bottom of block equal to top of block below it
            # if ib == 0, leave block bottom = 0.0
            if ib > 0:
                b.p.zbottom = self.linked.linkedBlocks[b][0].p.ztop
            isDummyBlock = ib == (numOfBlocks - 1)
            if not isDummyBlock:
                for c in b:

                    growFrac = self.expansionData.getExpansionFactor(c)
                    runLog.debug(
                        msg="      Component {0}, growFrac = {1:.4e}".format(
                            c, growFrac
                        )
                    )
                    if thermal and self.expansionData.componentReferenceHeight:
                        blockHeight = self.expansionData.componentReferenceHeight[c]
                    if growFrac >= 0.0:
                        c.height = (1.0 + growFrac) * blockHeight
                    else:
                        c.height = (1.0 / (1.0 - growFrac)) * blockHeight
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
                    # redistribute block boundaries if on the target component
                    if self.expansionData.isTargetComponent(c):
                        if b.axialExpTargetComponent is None:
                            runLog.debug(
                                "      Component {0} is target component (inferred)".format(
                                    c
                                )
                            )
                        else:
                            runLog.debug(
                                "      Component {0} is target component (blueprints defined)".format(
                                    c
                                )
                            )
                        b.p.ztop = c.ztop

            # see also b.setHeight()
            # - the above not chosen due to call to calculateZCoords
            oldComponentVolumes = [c.getVolume() for c in b]
            oldHeight = b.p.height
            b.p.height = b.p.ztop - b.p.zbottom

            _checkBlockHeight(b)
            _conserveComponentMass(b, oldHeight, oldComponentVolumes)
            # set block mid point and redo mesh
            # - functionality based on assembly.calculateZCoords()
            b.p.z = b.p.zbottom + b.p.height / 2.0
            mesh.append(b.p.ztop)
            b.spatialLocator = self.linked.a.spatialGrid[0, 0, ib]

        # pylint: disable = protected-access
        bounds = list(self.linked.a.spatialGrid._bounds)
        bounds[2] = array(mesh)
        self.linked.a.spatialGrid._bounds = tuple(bounds)

    def manageCoreMesh(self, r):
        """
        manage core mesh post assembly-level expansion

        Parameters
        ----------
        r : :py:class:`Reactor <armi.reactor.reactors.Reactor>` object.
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


def _conserveComponentMass(b, oldHeight, oldVolume):
    """Update block height dependent component parameters

    1) update component volume (used to compute block volume)
    2) update number density

    Parameters
    ----------
    oldHeight : list of floats
        list containing block heights pre-expansion
    oldVolume : list of floats
        list containing component volumes pre-expansion
    """
    for ic, c in enumerate(b):
        c.p.volume = oldVolume[ic] * b.p.height / oldHeight
        for key in c.getNuclides():
            c.setNumberDensity(key, c.getNumberDensity(key) * oldHeight / b.p.height)


def _checkBlockHeight(b):
    if b.p.height < 3.0:
        runLog.debug(
            "Block {0:s} ({1:s}) has a height less than 3.0 cm. ({2:.12e})".format(
                b.name, str(b.p.flags), b.p.height
            )
        )
    if b.p.height < 0.0:
        raise ArithmeticError(
            "Block {0:s} ({1:s}) has a negative height! ({2:.12e})".format(
                b.name, str(b.p.flags), b.p.height
            )
        )


class AssemblyAxialLinkage:
    """Determines and stores the block- and component-wise axial linkage for an assembly

    Attributes
    ----------
    a : :py:class:`Assembly <armi.reactor.assemblies.Assembly>` object.
        reference to original assembly; is directly modified/changed during expansion.
    linkedBlocks : dict
        keys   --> :py:class:`Block <armi.reactor.blocks.Block>` object
        values --> list of axially linked blocks; index 0 = lower linked block; index 1: upper linked block.
                   see also: self._getLinkedBlocks()
    linkedComponents : dict
        keys -->   :py:class:`Component <armi.reactor.components.component.Component>` object
        values --> list of axially linked components; index 0 = lower linked component; index 1: upper linked component.
                   see also: self._getLinkedComponents
    """

    def __init__(self, StdAssem):
        self.a = StdAssem
        self.linkedBlocks = {}
        self.linkedComponents = {}
        self._determineAxialLinkage()

    def _determineAxialLinkage(self):
        """gets the block and component based linkage"""
        for b in self.a:
            self._getLinkedBlocks(b)
            for c in b:
                self._getLinkedComponents(b, c)

    def _getLinkedBlocks(self, b):
        """retrieve the axial linkage for block b

        Parameters
        ----------
        b : :py:class:`Block <armi.reactor.blocks.Block>` object
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
                )
            )
        if upperLinkedBlock is None:
            runLog.debug(
                "Assembly {0:22s} at location {1:22s}, Block {2:22s}"
                "is not linked to a block above!".format(
                    str(self.a.getName()),
                    str(self.a.getLocation()),
                    str(b.p.flags),
                )
            )

    def _getLinkedComponents(self, b, c):
        """retrieve the axial linkage for component c

        Parameters
        ----------
        b : :py:class:`Block <armi.reactor.blocks.Block>` object
            key to access blocks containing linked components
        c : :py:class:`Component <armi.reactor.components.component.Component>` object
            component to determine axial linkage for

        Raises
        ------
        RuntimeError
            multiple candidate components are found to be axially linked to a component
        """
        lstLinkedC = [None, None]
        for ib, linkdBlk in enumerate(self.linkedBlocks[b]):
            if linkdBlk is not None:
                for otherC in linkdBlk.getChildren():
                    if _determineLinked(c, otherC):
                        if lstLinkedC[ib] is not None:
                            errMsg = (
                                "Multiple component axial linkages have been found for "
                                "Component {0}; Block {1}; Assembly {2}."
                                " This is indicative of an error in the blueprints! Linked components found are"
                                "{3} and {4}".format(
                                    c, b, b.parent, lstLinkedC[ib], otherC
                                )
                            )
                            runLog.error(msg=errMsg)
                            raise RuntimeError(errMsg)
                        lstLinkedC[ib] = otherC

        self.linkedComponents[c] = lstLinkedC

        if lstLinkedC[0] is None:
            runLog.debug(
                "Assembly {0:22s} at location {1:22s}, Block {2:22s}, Component {3:22s} "
                "has nothing linked below it!".format(
                    str(self.a.getName()),
                    str(self.a.getLocation()),
                    str(b.p.flags),
                    str(c.p.flags),
                )
            )
        if lstLinkedC[1] is None:
            runLog.debug(
                "Assembly {0:22s} at location {1:22s}, Block {2:22s}, Component {3:22s} "
                "has nothing linked above it!".format(
                    str(self.a.getName()),
                    str(self.a.getLocation()),
                    str(b.p.flags),
                    str(c.p.flags),
                )
            )


def _determineLinked(componentA, componentB):
    """determine axial component linkage for two components

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
    """object containing data needed for axial expansion"""

    def __init__(self, a, setFuel):
        self._a = a
        self.componentReferenceHeight = {}
        self.componentReferenceTemperature = {}
        self._expansionFactors = {}
        self._componentDeterminesBlockHeight = {}
        self._setTargetComponents(setFuel)

    def setExpansionFactors(self, componentLst, percents):
        """sets user defined expansion factors

        Parameters
        ----------
        componentLst : list of :py:class:`Component <armi.reactor.components.component.Component>`
            list of :py:class:`Component <armi.reactor.components.component.Component>` objects to have their heights changed # pylint: disable=line-too-long
        percents : list of floats
            list of height changes in percent that are to be applied to componentLst

        Raises
        ------
        RuntimeError
            If componentLst and percents are different lengths

        Notes
        -----
        - requires that the length of componentLst and percents be the same
        """
        if len(componentLst) != len(percents):
            runLog.error(
                "Number of components and percent changes must be the same!\n\
                    len(componentLst) = {0:d}\n\
                        len(percents) = {1:d}".format(
                    len(componentLst), len(percents)
                )
            )
            raise RuntimeError
        for c, p in zip(componentLst, percents):
            self._expansionFactors[c] = p

    def updateComponentTempsBy1DTempField(self, tempGrid, tempField):
        """assign a block-average axial temperature to components

        Parameters
        ----------
        tempGrid : numpy array
            1D axial temperature grid (i.e., physical locations where temp is stored)
        tempField : numpy array
            temperature values along grid

        Notes
        -----
        - maps a 1D axial temperature distribution to components
        - searches for temperatures that fall within the bounds of a block,
          averages them, and assigns them as appropriate
        - Updating component volume is functionally very similar to c.computeVolume().
          However, this implementation differs in the temperatures that get used to compute dimensions.
            - In c.getArea() -> c.getComponentArea(cold=cold) -> self.getDimension(str, cold=cold),
              cold=False results in self.getDimension to use the cold/input component temperature.
            - However, we want the temperature from the previous state to be used (the reference temperature).
              So, here we manually call c.getArea() and pass in the reference temperature. This ensures that
              as the component is expanded its mass is conserved.

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
                    "Block {0:s} has no temperature points within it! \
                        Likely need to increase the refinement of the temperature grid.".format(
                        str(b.name)
                    )
                )

            blockAveTemp = mean(tmpMapping)
            for c in b:
                self.componentReferenceHeight[c] = b.getHeight()
                # store the temperature from previous state (i.e., reference temp)
                self.componentReferenceTemperature[c] = c.temperatureInC
                # set component volume to be evaluated at reference temp
                c.p.volume = (
                    c.getArea(cold=self.componentReferenceTemperature[c])
                    * c.parent.getHeight()
                )
                # DO NOT use self.setTemperature(). This calls changeNDensByFactor(f)
                # and ruins mass conservation via number densities. Instead, set manually.
                c.temperatureInC = blockAveTemp

    def computeThermalExpansionFactors(self):
        """computes expansion factors for all components via thermal expansion"""

        for b in self._a:
            for c in b:
                if self.componentReferenceTemperature:
                    self._expansionFactors[c] = (
                        c.getThermalExpansionFactor(
                            T0=self.componentReferenceTemperature[c]
                        )
                        - 1.0
                    )
                else:
                    self._expansionFactors[c] = c.getThermalExpansionFactor() - 1.0

    def getExpansionFactor(self, c):
        """retrieves expansion factor for c

        Parameters
        ----------
        c : :py:class:`Component <armi.reactor.components.component.Component>` object
            :py:class:`Component <armi.reactor.components.component.Component>` object to retrive expansion factor for

        """
        if c in self._expansionFactors:
            value = self._expansionFactors[c]
        else:
            value = 0.0
        return value

    def _setTargetComponents(self, setFuel):
        """sets target component for each block

        Parameters
        ----------
        setFuel : bool
            boolean to determine if fuel block should have its target component set. Useful for when
            target components should be determined on the fly.
        """
        for b in self._a:
            if b.axialExpTargetComponent is not None:
                self._componentDeterminesBlockHeight[b.axialExpTargetComponent] = True
            elif b.hasFlags(Flags.PLENUM) or b.hasFlags(Flags.ACLP):
                self.determineTargetComponent(b, Flags.CLAD)
            elif b.hasFlags(Flags.DUMMY):
                self.determineTargetComponent(b, Flags.COOLANT)
            elif setFuel and b.hasFlags(Flags.FUEL):
                self._isFuelLocked(b)
            else:
                self.determineTargetComponent(b)

    def determineTargetComponent(self, b, flagOfInterest=None):
        """appends target component to self._componentDeterminesBlockHeight

        Parameters
        ----------
        b : :py:class:`Block <armi.reactor.blocks.Block>` object
            block to specify target component for
        flagOfInterest : :py:class:`Flags <armi.reactor.flags.Flags>` object
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
            raise RuntimeError("No target component found!\n   Block {0}".format(b))
        if len(componentWFlag) > 1:
            raise RuntimeError(
                "Cannot have more than one component within a block that has the target flag!"
                "Block {0}\nflagOfInterest {1}\nComponents {2}".format(
                    b, flagOfInterest, componentWFlag
                )
            )
        self._componentDeterminesBlockHeight[componentWFlag[0]] = True

    def _isFuelLocked(self, b):
        """physical/realistic implementation reserved for ARMI plugin

        Parameters
        ----------
        b : :py:class:`Block <armi.reactor.blocks.Block>` object
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
        c = b.getChildrenWithFlags(Flags.FUEL)
        if len(c) == 0:  # pylint: disable=no-else-raise
            raise RuntimeError("No fuel component within {0}!".format(b))
        elif len(c) > 1:
            raise RuntimeError(
                "Cannot have more than one fuel component within {0}!".format(b)
            )
        self._componentDeterminesBlockHeight[c[0]] = True

    def isTargetComponent(self, c):
        """returns bool if c is a target component

        Parameters
        ----------
        c : :py:class:`Component <armi.reactor.components.component.Component>` object
            :py:class:`Component <armi.reactor.components.component.Component>` object to check target component status
        """
        return bool(c in self._componentDeterminesBlockHeight)
