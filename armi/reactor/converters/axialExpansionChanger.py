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
        self._isTopDummyBlockPresent()

    def _isTopDummyBlockPresent(self):
        """determines if top most block of assembly is a dummy block

        Notes
        -----
        - If true, then axial expansion will be physical for all blocks.
        - If false, the top most block in the assembly is artificially chopped
          to preserve the assembly height. A runLog.Warning also issued.
        """
        blkLst = self._linked.a.getBlocks()
        if not blkLst[-1].hasFlags(Flags.DUMMY):
            runLog.warning(
                "No dummy block present at the top of {0}! "
                "Top most block will be artificially chopped "
                "to preserve assembly height".format(self._linked.a)
            )
            if "detailedAxialExpansion" in self._converterSettings:  # avoid KeyError
                if self._converterSettings["detailedAxialExpansion"]:
                    runLog.error(
                        "Cannot run detailedAxialExpansion without a dummy block"
                        "at the top of the assembly!"
                    )
                    raise RuntimeError

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
                    growFrac = self.expansionData.getExpansionFactor(c)
                    if growFrac >= 0.0:
                        c.height = (1.0 + growFrac) * b.p.height
                    else:
                        c.height = (1.0 / (1.0 - growFrac)) * b.p.height
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

    def axiallyExpandCoreThermal(self, r, tempGrid, tempField):
        """
        Perform thermally driven axial expansion of the core.

        Parameters
        ----------
        r
            ARMI reactor to be expanded
        tempGrid : dictionary
            keys --> assembly object
            values --> grid
        tempField : dictionary
            keys --> assembly object
            values --> temperatures

        """
        for a in r.core.getAssemblies(includeBolAssems=True):
            self.setAssembly(a)
            self.expansionData.mapHotTempToComponents(tempGrid[a], tempField[a])
            self.expansionData.computeThermalExpansionFactors()
            self.axiallyExpandAssembly()

        self._manageCoreMesh(r)

    def axiallyExpandCorePercent(self, r, components, percents):
        """
        Perform axial expansion of the core driven by user-defined expansion percentages.

        Parameters
        ----------
        r
            ARMI reactor to be expanded
        components : dictionary
            keys --> assembly object
            values --> list of components to be expanded
        percents : dictionary
            keys --> assembly object
            values --> list of percentages to expand components by
        """
        for a in r.core.getAssemblies(includeBolAssems=True):
            self.setAssembly(a)
            self.expansionData.setExpansionFactors(components[a], percents[a])
            self.axiallyExpandAssembly()

        self._manageCoreMesh(r)

    def _manageCoreMesh(self, r):
        """
        Notes
        -----
        - if no detailedAxialExpansion, then do "cheap" approach to uniformMesh converter.
        - update average core mesh values with call to r.core.updateAxialMesh()
        """
        if not self._converterSettings["detailedAxialExpansion"]:
            # loop through again now that the reference is adjusted and adjust the non-fuel assemblies.
            refAssem = r.core.refAssem
            axMesh = refAssem.getAxialMesh()
            for a in r.core.getAssemblies(includeBolAssems=True):
                # See ARMI Ticket #112 for explanation of the commented out code
                a.setBlockMesh(
                    axMesh
                )  # , conserveMassFlag=True, adjustList=adjustList)

        oldMesh = r.core.p.axialMesh
        r.core.updateAxialMesh()  # floating point correction
        runLog.important(
            "Adjusted full core fuel axial mesh uniformly "
            "From {0} cm to {1} cm.".format(oldMesh, r.core.p.axialMesh)
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
            c.setNumberDensity(key, c.getNumberDensity(key) * oldHeight / b.p.height)


def _checkBlockHeight(b):
    if b.p.height < 3.0:
        runLog.warning(
            "Block {0:s} has a height less than 3.0 cm. ({1:.12e})".format(
                b.name, b.p.height
            )
        )
    if b.p.height < 0.0:
        raise ArithmeticError(
            "Block {0:s} has a negative height! ({1:.12e})".format(b.name, b.p.height)
        )


class AssemblyAxialLinkage:
    """Determines and stores the block- and component-wise axial linkage for an assembly"""

    _TOLERANCE = 1.0e-03

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

        if lstLinkedC[0] is None:
            runLog.warning(
                "Component {0:22s} within Block {1:22s} has nothing linked below it!".format(
                    str(c.p.flags), str(c.parent.p.flags)
                )
            )
        if lstLinkedC[1] is None:
            runLog.warning(
                "Component {0:22s} within Block {1:22s} has nothing linked above it!".format(
                    str(c.p.flags), str(c.parent.p.flags)
                )
            )


class ExpansionData:
    """object containing data needed for axial expansion"""

    def __init__(self, a):
        self.a = a
        self.oldHotTemp = {}
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

    def mapHotTempToComponents(self, tempGrid, tempField):
        """map axial temp distribution to blocks and components in self.a

        Parameters
        ----------
        tempGrid : numpy array
            axial temperature grid (i.e., physical locations where temp is stored)
        tempField : numpy array
            temperature values along grid

        Notes
        -----
        - maps the radially uniform axial temperature distribution to components
        - searches for temperatures that fall within the bounds of a block,
          averages them, and assigns them as appropriate
        - tempGrid and tempField must be same length
        - provides an example for mapping temperature field to components. Can be replaced
          with a different approach (e.g., from a plugin). The only requirement is that
          a temperature is mapped to **all** components.

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

        self.oldHotTemp = {}  # reset, just to be safe
        for b in self.a:
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
            # DO NOT use self.setTemperature(). This calls changeNDensByFactor(f)
            # and ruins mass conservation via number densities. Instead,
            # set manually.
            for c in b:
                self.oldHotTemp[c] = c.temperatureInC  # stash the "old" hot temp
                c.temperatureInC = blockAveTemp

    def computeThermalExpansionFactors(self):
        """computes expansion factors for all components via thermal expansion"""

        for b in self.a:
            for c in b:
                try:
                    self.expansionFactors[c] = (
                        c.getThermalExpansionFactor(
                            Tc=c.temperatureInC, T0=self.oldHotTemp[c]
                        )
                        - 1.0
                    )
                except KeyError:
                    runLog.error(
                        "Component {0} is not in self.oldHotTemp."
                        "Did you assign temperatures to the components?".format(c)
                    )
                    raise

    def getExpansionFactor(self, c):
        """retrieves expansion factor for c. If not set, assumes it to be 1.0 (i.e., no change)"""
        if c in self.expansionFactors:
            value = self.expansionFactors[c]
        else:
            runLog.warning("No expansion factor for {}! Setting to 1.0".format(c))
            value = 0.0
        return value

    def _setTargetComponents(self):
        """sets target component for each block

        - To-Do: allow users to specify target component for a block in settings
        """
        for b in self.a:
            if b.hasFlags(Flags.PLENUM):
                self._specifyTargetComponent(b, Flags.CLAD)
            elif b.hasFlags(Flags.FUEL):
                self._isFuelLocked(b)
            else:
                self._specifyTargetComponent(b)

    def _specifyTargetComponent(self, b, flagOfInterest=None):
        """appends target component to self._componentDeterminesBlockHeight

        Parameters
        ----------
        b
            armi block
        flagOfInterest
            the flag of interest to identify the target component

        Notes
        -----
        - if flagOfInterest is None, finds the component within b that contains flags that
          are defined in b.p.flags
        - if flagOfInterest is not None, finds the component that contains the flagOfInterest.
          This is currently used **only** for the plenum - see _setTargetComponents.

        Raises
        ------
        RuntimeError
            no target component found
        RuntimeError
            multiple target components found
        """
        if flagOfInterest is None:
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

    # TO-DO update this
    def _isFuelLocked(self, b):
        """needs updating"""
        for c in b:
            if c.hasFlags(Flags.FUEL):
                self._componentDeterminesBlockHeight[c] = True

    def isTargetComponent(self, c):
        return bool(c in self._componentDeterminesBlockHeight)
