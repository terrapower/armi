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
"""Data container for axial expansion."""

from statistics import mean
from typing import List

from armi import runLog
from armi.materials import material
from armi.reactor.flags import Flags

TARGET_FLAGS_IN_PREFERRED_ORDER = [
    Flags.FUEL,
    Flags.CONTROL,
    Flags.POISON,
    Flags.SHIELD,
    Flags.SLUG,
]


def getSolidComponents(b):
    """
    Return list of components in the block that have solid material.

    Notes
    -----
    Axial expansion only needs to be applied to solid materials. We should not update
    number densities on fluid materials to account for changes in block height.
    """
    return [c for c in b if not isinstance(c.material, material.Fluid)]


class ExpansionData:
    """Data container for axial expansion."""

    def __init__(self, a, setFuel: bool, expandFromTinputToThot: bool):
        """
        Parameters
        ----------
        a: :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
            Assembly to assign component-wise expansion data to
        setFuel: bool
            used to determine if fuel component should be set as
            axial expansion target component during initialization.
            see self._isFuelLocked
        expandFromTinputToThot: bool
            determines if thermal expansion factors should be calculated
            from c.inputTemperatureInC to c.temperatureInC (True) or some other
            reference temperature and c.temperatureInC (False)
        """
        self._a = a
        self.componentReferenceTemperature = {}
        self._expansionFactors = {}
        self._componentDeterminesBlockHeight = {}
        self._setTargetComponents(setFuel)
        self.expandFromTinputToThot = expandFromTinputToThot

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
                "Number of components and expansion fractions must be the same!\n"
                f"    len(componentLst) = {len(componentLst)}\n"
                f"        len(expFrac) = {len(expFrac)}"
            )
            raise RuntimeError
        if 0.0 in expFrac:
            msg = (
                "An expansion fraction, L1/L0, equal to 0.0, is not physical. Expansion fractions "
                "should be greater than 0.0."
            )
            runLog.error(msg)
            raise RuntimeError(msg)
        for exp in expFrac:
            if exp < 0.0:
                msg = (
                    "A negative expansion fraction, L1/L0, is not physical. Expansion fractions "
                    "should be greater than 0.0."
                )
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
                if self.expandFromTinputToThot:
                    # get thermal expansion factor between c.inputTemperatureInC & c.temperatureInC
                    self._expansionFactors[c] = c.getThermalExpansionFactor()
                elif c in self.componentReferenceTemperature:
                    growFrac = c.getThermalExpansionFactor(
                        T0=self.componentReferenceTemperature[c]
                    )
                    self._expansionFactors[c] = growFrac
                else:
                    # We want expansion factors relative to componentReferenceTemperature not
                    # Tinput. But for this component there isn't a componentReferenceTemperature, so
                    # we'll assume that the expansion factor is 1.0.
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
        """Determines target component, stores it on the block, and appends it to
        self._componentDeterminesBlockHeight.

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
            # Follow expansion of most neutronically important component, fuel then control/poison
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
                "Cannot have more than one component within a block that has the target flag!"
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
