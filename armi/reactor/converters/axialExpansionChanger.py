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


class AxialExpansionChanger:
    """
    Axially expand or contract assemblies or an entire core.

    Useful for fuel performance, thermal expansion, reactivity coefficients, etc.
    """

    def __init__(self, converterSettings: dict):
        """
        Build an axial expansion converter.

        Parameters
        ----------
        converterSettings : dict
            A set of str, value settings used in mesh conversion. Required
            settings are implementation specific.
        """
        self._converterSettings = converterSettings
        self._linked = None
        self.expansionData = None

    def setAssembly(self, a):
        """set the armi assembly to be changed and init expansion data class for assembly

        Parameters
        ----------
        a
            ARMI assembly to be changed
        """
        self._linked = AssemblyAxialLinkage(a)
        self.expansionData = ExpansionData(a)

    def axiallyExpandAssembly(self):
        """utilizes assembly linkage to do axial expansion"""
        mesh = [0.0]
        numOfBlocks = self._linked.a.countBlocksWithFlags()
        for ib, b in enumerate(self._linked.a):
            ## set bottom of block equal to top of block below it
            # if ib == 0, leave block bottom = 0.0
            if ib > 0:
                b.p.zbottom = self._linked.linkedBlocks[b][0].p.ztop
            ## if not in the dummy block, get expansion factor, do alignment, and modify block
            if ib < (numOfBlocks - 1):
                for c in b:
                    c.height = self.expansionData.getExpansionFactor(c) * b.p.height
                    # align linked components
                    if ib == 0:
                        c.zbottom = 0.0
                    else:
                        if self._linked.linkedComponents[c][0] is not None:
                            # use linked components below
                            c.zbottom = self._linked.linkedComponents[c][0].ztop
                        else:
                            # otherwise there aren't any linked components
                            # so just set the bottom of the component to
                            # the top of the block below it
                            c.zbottom = self._linked.linkedBlocks[b][0].p.ztop
                    c.ztop = c.zbottom + c.height
                    # redistribute block boundaries if on the target component
                    if self.expansionData.isTargetComponent(c):
                        b.p.ztop = c.ztop

            ## see also b.setHeight()
            # - the above not chosen due to call to calculateZCoords
            oldComponentVolumes = _getComponentVolumes(b)
            oldHeight = b.getHeight()
            b.p.height = b.p.ztop - b.p.zbottom
            _checkBlockHeight(b)
            _conserveComponentMass(b, oldHeight, oldComponentVolumes)
            ## set block mid point and redo mesh
            # - functionality based on assembly.calculateZCoords()
            b.p.z = b.p.zbottom + b.p.height / 2.0
            mesh.append(b.p.ztop)
            b.spatialLocator = self._linked.a.spatialGrid[0, 0, ib]

        bounds = list(self._linked.a.spatialGrid._bounds)
        bounds[2] = array(mesh)
        self._linked.a.spatialGrid._bounds = tuple(bounds)

    def mapHotTempToBlocks(self, tempGrid, tempField):
        """map axial temp distribution to blocks in assembly

        Parameters
        ----------
        tempGrid : numpy array
            axial temperature grid (i.e., physical locations where temp is stored)
        tempField : numpy array
            temperature values along grid

        Notes
        -----
        - maps the radially uniform axial temperature distribution to blocks
        - searches for temperatures that fall within the bounds of a block,
          averages them, and assigns them as appropriate
        - tempGrid and tempField must be same length

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

        for b in self._linked.a:
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
            b.p.THcoolantStaticT = (
                blockAveTemp  # difference relative to THcoolantAverageT ?
            )
            b.p.THaverageCladTemp = blockAveTemp
            b.p.THaverageGapTemp = blockAveTemp  # used for bond and plenum
            b.p.THaverageDuctTemp = blockAveTemp
            b.p.THTfuelCL = blockAveTemp

    def axiallyExpandCore(self, r):  # , componentLst=None, percents=None):
        """
        Perform an axial expansion of the core.

        Parameters
        ----------
        r
            ARMI reactor to be expanded

        Notes
        -----
        - Only does thermal expansion. Need to decide on data structure to account for
          manual expansion.
        """
        oldMesh = r.core.p.axialMesh
        for a in r.core.getAssemblies(includeBolAssems=True):
            self.setAssembly(a)
            self.expansionData.computeThermalExpansionFactors()
            # self.expansionData.setExpansionFactors() # TO-DO figure out data structure for manual expansion factors
            self.axiallyExpandAssembly()

        if not self._converterSettings["detailedAxialExpansion"]:
            # loop through again now that the reference is adjusted and adjust the non-fuel assemblies.
            refAssem = r.core.refAssem
            axMesh = refAssem.getAxialMesh()
            for a in r.core.getAssemblies(includeBolAssems=True):
                # See ARMI Ticket #112 for explanation of the commented out code
                a.setBlockMesh(
                    axMesh
                )  # , conserveMassFlag=True, adjustList=adjustList)

        r.core.updateAxialMesh()  # floating point correction
        newMesh = r.core.p.axialMesh
        runLog.important(
            "Adjusted full core fuel axial mesh uniformly "
            "From {1} cm to {2} cm.".format(oldMesh, newMesh)
        )


def _getComponentVolumes(b):
    """manually retrieve volume of components within a block

    Parameters
    ----------
    c
        ARMI component

    Notes
    -----
    This is functionally very similar to c.computeVolume(), however differs in
    the temperatures that get used to compute dimensions.
    - In c.getArea() -> c.getComponentArea(cold=cold) -> self.getDimension(str, cold=cold),
    cold=False results in self.getDimension to use the cold/input component temperature.
    However, we want the "old hot" temp to be used. So, here we manually call
    c.getArea and pass in the correct "cold" (old hot) temperature. This ensures that
    component mass is conserved.

    """
    cVolumes = []
    for c in b:
        cVolumes.append(c.getArea(cold=c.temperatureInC) * c.parent.getHeight())

    return cVolumes

def _conserveComponentMass(b, oldHeight, oldVolume):
    """Update block height dependent component parameters
    1) update component volume (used to compute block volume)
    2) update number density
    """
    for ic, c in enumerate(b[:-1]):
        c.p.volume = oldVolume[ic] * b.p.height / oldHeight
        for key in c.getNuclides():
            c.setNumberDensity(
                key, c.getNumberDensity(key) * oldHeight / b.p.height
            )

def _checkBlockHeight(b):
    if b.p.height < 3.0:
        runLog.warning(
            "Block {0:s} has a height less than 3.0 cm. ({1:.12e})".format(
                b.name, b.p.height
            )
        )
    if b.p.height < 0.0:
        raise ArithmeticError(
            "Block {0:s} has a negative height! ({1:.12e})".format(
                b.name, b.p.height
            )
        )

class AssemblyAxialLinkage:
    """Determines and stores the block- and component-wise axial linkage for an assembly"""

    _TOLERANCE = 1.0e-03

    def __init__(self, StdAssem):
        self.a = StdAssem
        self.linkedBlocks = {}
        self.linkedComponents = {}
        self._determineAxialLinkage()
        self._isTopDummyBlockPresent()

    def _isTopDummyBlockPresent(self):
        """determines if top most block of assembly is a dummy block
        
        Notes
        -----
        - If true, then axial expansion will be physical for all blocks.
        - If false, the top most block in the assembly is artificially chopped 
          to preserve the assembly height. A runLog.Warning also issued.
        """
        blkLst = self.a.getBlocks()
        if not blkLst[-1].hasFlags(Flags.DUMMY):
            runLog.warning(
                "No dummy block present at the top of {0}! Top most block will be \
                    artificially chopped to preserve assembly height".format(self.a)
            )

    def _determineAxialLinkage(self):
        """gets the block and component based linkage"""
        for b in self.a:
            self._getLinkedBlocks(b)
            for c in b:
                self._getLinkedComponents(b, c)

    def _getLinkedBlocks(self, b):
        """retrieve the axial linkage for block b

        NOTES
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

    def _getLinkedComponents(self, b, c):
        """retrieve the axial linkage for component c"""
        lstLinkedC = [None, None]
        for ib, linkdBlk in enumerate(self.linkedBlocks[b]):
            if linkdBlk is not None:
                for otherC in linkdBlk.getChildren():
                    if isinstance(
                        otherC, type(c)
                    ):  # equivalent to type(otherC) == type(c)
                        area_diff = abs(otherC.getArea() - c.getArea())
                        if area_diff < self._TOLERANCE:
                            lstLinkedC[ib] = otherC

        self.linkedComponents[c] = lstLinkedC

        if not lstLinkedC:
            runLog.warning(
                "Component {0:22s} within Block {1:22s} is not axially linked to anything!".format(
                    str(c.p.flags), str(c.parent.p.flags)
                )
            )


class ExpansionData:
    """object containing data needed for axial expansion"""

    def __init__(self, a):
        self.a = a
        self.expansionFactors = {}
        self._componentDeterminesBlockHeight = {}
        self._setTargetComponents()

    def setExpansionFactors(self, componentLst, percents):
        """sets user defined expansion factors

        Parameters
        ----------
        componentLst
            list of armi component objects to have their heights changed
        percents
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
            self.expansionFactors[c] = p

    def _mapTempToComponent(self, c):
        if c.hasFlags(Flags.FUEL) or c.hasFlags(Flags.SHIELD):
            temp = c.parent.p.THTfuelCL
        elif c.hasFlags(Flags.CLAD) or c.hasFlags(Flags.WIRE):
            temp = c.parent.p.THaverageCladTemp
        elif (
            c.hasFlags(Flags.DUCT)
            or c.hasFlags(Flags.HANDLING_SOCKET)
            or c.hasFlags(Flags.GRID_PLATE)
            or c.hasFlags(Flags.INLET_NOZZLE)
        ):
            temp = c.parent.p.THaverageDuctTemp
        elif (
            c.hasFlags(Flags.COOLANT)
            or c.hasFlags(Flags.INTERCOOLANT)
            or c.hasFlags(Flags.BOND)
        ):
            temp = c.parent.p.THcoolantStaticT
        elif c.hasFlags(Flags.PLENUM) or c.hasFlags(Flags.GAP):
            temp = c.parent.p.THaverageGapTemp
        else:
            raise ValueError(
                "Component temperature not found!\n\
                    Block = {0:s}\n\
                    Component = {1:s}".format(
                    str(c.parent.p.flags), str(c.p.flags)
                )
            )
        return temp

    def computeThermalExpansionFactors(self):
        """computes expansion factors for all components via thermal expansion"""

        for b in self.a:
            for c in b:
                temp = self._mapTempToComponent(c)

                self.expansionFactors[c] = c.getThermalExpansionFactor(
                    Tc=temp, T0=c.temperatureInC
                )
                # DO NOT use self.setTemperature(). This calls changeNDensByFactor(f)
                # and ruins mass conservation via number densities. Instead,
                # set manually.
                c.temperatureInC = temp

    def getExpansionFactor(self, c):
        """retrieves expansion factor for c. If not set, assumes it to be 1.0 (i.e., no change)"""
        if c in self.expansionFactors:
            value = self.expansionFactors[c]
        else:
            runLog.warning("No expansion factor for {}! Setting to 1.0".format(c))
            value = 1.0
        return value

    def _setTargetComponents(self):
        """sets target component for each block

        - To-Do: allow users to specify target component for a block in settings
        """
        for b in self.a:
            if b.hasFlags(Flags.PLENUM):
                self._specifyTargetComponent(b.getChildrenWithFlags(Flags.CLAD))
            elif b.hasFlags(Flags.FUEL):
                self._isFuelLocked(b)
            else:
                self._specifyTargetComponent(b.getChildrenWithFlags(b.p.flags))

    def _specifyTargetComponent(self, componentWFlag):
        """appends target component to self._componentDeterminesBlockHeight

        Parameters
        ----------
        componentWFlag
            list of components (len == 1) that match prescribed flag

        Notes
        -----
        - The length of componentWFlag MUST be 1! Will throw an error otherwise.
        """
        errorMsg = "Cannot have more than one component within a block that has the target flag! \
                    Block {0}, Flags {1}, Components {2}".format(
            componentWFlag[0].parent, componentWFlag[0].parent.p.flags, componentWFlag
        )
        assert len(componentWFlag) == 1, errorMsg
        self._componentDeterminesBlockHeight[componentWFlag[0]] = True

    # TO-DO update this
    def _isFuelLocked(self, b):
        """needs updating"""
        for c in b:
            if c.hasFlags(Flags.FUEL):
                self._componentDeterminesBlockHeight[c] = True

    def isTargetComponent(self, c):
        return bool(c in self._componentDeterminesBlockHeight)
