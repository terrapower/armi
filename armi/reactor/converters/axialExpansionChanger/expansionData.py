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
from typing import TYPE_CHECKING, Iterable, Optional

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

if TYPE_CHECKING:
    from armi.reactor.assemblies import Assembly
    from armi.reactor.blocks import Block
    from armi.reactor.components import Component


def iterSolidComponents(b: "Block") -> Iterable["Component"]:
    """Iterate over all solid components in the block."""
    return filter(lambda c: not isinstance(c.material, material.Fluid), b)


def getSolidComponents(b: "Block") -> list["Component"]:
    """
    Return list of components in the block that have solid material.

    Notes
    -----
    Axial expansion only needs to be applied to solid materials. We should not update
    number densities on fluid materials to account for changes in block height.

    See Also
    --------
    :func:`iterSolidComponents` produces an iterable rather than a list and may be better
    suited if you simply want to iterate over solids in a block.
    """
    return list(iterSolidComponents(b))


class ExpansionData:
    r"""Data container for axial expansion.

    The primary responsibility of this class is to determine the axial expansion factors
    for each solid component in the assembly. Expansion factors can be computed from the component
    temperatures in :meth:`computeThermalExpansionFactors` or provided directly to the class
    via :meth:`setExpansionFactors`.

    This class relies on the concept of a "target" expansion component for each block. While
    components will expand at different rates, the final height of the block must be determined.
    The target component, determined by :meth:`determineTargetComponents`, will drive the total
    height of the block post-expansion.

    Parameters
    ----------
    a: :py:class:`Assembly <armi.reactor.assemblies.Assembly>`
        Assembly to assign component-wise expansion data to
    setFuel: bool
        used to determine if fuel component should be set as
        axial expansion target component during initialization.
        see self._isFuelLocked
    expandFromTinputToThot: bool
        Determines if thermal expansion factors should be calculated from
            - ``c.inputTemperatureInC`` to ``c.temperatureInC`` when ``True``, or
            - some other reference temperature and ``c.temperatureInC`` when ``False``
    """

    _expansionFactors: dict["Component", float]
    componentReferenceTemperature: dict["Component", float]

    def __init__(self, a: "Assembly", setFuel: bool, expandFromTinputToThot: bool):
        self._a = a
        self.componentReferenceTemperature = {}
        self._expansionFactors = {}
        self._componentDeterminesBlockHeight = {}
        self._setTargetComponents(setFuel)
        self.expandFromTinputToThot = expandFromTinputToThot

    def setExpansionFactors(self, components: list["Component"], expFrac: list[float]):
        """Sets user defined expansion fractions.

        Parameters
        ----------
        components : List[:py:class:`Component <armi.reactor.components.component.Component>`]
            list of Components to have their heights changed
        expFrac : List[float]
            list of L1/L0 height changes that are to be applied to components

        Raises
        ------
        RuntimeError
            If components and expFrac are different lengths
        """
        if len(components) != len(expFrac):
            runLog.error(
                "Number of components and expansion fractions must be the same!\n"
                f"     len(components) = {len(components)}\n"
                f"        len(expFrac) = {len(expFrac)}"
            )
            raise RuntimeError
        for exp in expFrac:
            if exp <= 0.0:
                msg = f"Expansion factor {exp}, L1/L0, is not physical. Expansion fractions should be greater than 0.0."
                runLog.error(msg)
                raise RuntimeError(msg)
        for c, p in zip(components, expFrac):
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

    def updateComponentTemp(self, c: "Component", temp: float):
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
            self._setComponentThermalExpansionFactors(b)

    def _setComponentThermalExpansionFactors(self, b: "Block"):
        """For each component in the block, set the thermal expansion factors."""
        for c in iterSolidComponents(b):
            self._perComponentThermalExpansionFactors(c)

    def _perComponentThermalExpansionFactors(self, c: "Component"):
        """Set the thermal expansion factors for a single component."""
        if self.expandFromTinputToThot:
            # get thermal expansion factor between c.inputTemperatureInC & c.temperatureInC
            self._expansionFactors[c] = c.getThermalExpansionFactor()
        elif c in self.componentReferenceTemperature:
            growFrac = c.getThermalExpansionFactor(T0=self.componentReferenceTemperature[c])
            self._expansionFactors[c] = growFrac
        else:
            # We want expansion factors relative to componentReferenceTemperature not
            # Tinput. But for this component there isn't a componentReferenceTemperature, so
            # we'll assume that the expansion factor is 1.0.
            self._expansionFactors[c] = 1.0

    def getExpansionFactor(self, c: "Component"):
        """Retrieves expansion factor for c.

        Parameters
        ----------
        c : :py:class:`Component <armi.reactor.components.component.Component>`
            Component to retrieve expansion factor for
        """
        value = self._expansionFactors.get(c, 1.0)
        return value

    def _setTargetComponents(self, setFuel: bool):
        """Sets target component for each block.

        Parameters
        ----------
        setFuel : bool
            boolean to determine if fuel block should have its target component set. Useful for when
            target components should be determined on the fly.
        """
        for b in self._a:
            if b.p.axialExpTargetComponent:
                target = b.getComponentByName(b.p.axialExpTargetComponent)
                self._setExpansionTarget(b, target)
            elif b.hasFlags(Flags.PLENUM) or b.hasFlags(Flags.ACLP):
                self.determineTargetComponent(b, Flags.CLAD)
            elif b.hasFlags(Flags.DUMMY):
                # Dummy blocks are intended to contain only fluid and do not need a target component
                pass
            elif setFuel and b.hasFlags(Flags.FUEL):
                self._isFuelLocked(b)
            else:
                self.determineTargetComponent(b)

    def determineTargetComponent(self, b: "Block", flagOfInterest: Optional[Flags] = None) -> "Component":
        """Determines the component who's expansion will determine block height.

        This information is also stored on the block at ``Block.p.axialExpTargetComponent`` for faster
        retrieval later.

        Parameters
        ----------
        b : :py:class:`Block <armi.reactor.blocks.Block>`
            block to specify target component for
        flagOfInterest : :py:class:`Flags <armi.reactor.flags.Flags>`
            the flag of interest to identify the target component

        Returns
        -------
        Component
            Component identified as target component, if found.

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
                candidates = b.getChildrenWithFlags(targetFlag)
                if candidates:
                    break
            # some blocks/components are not included in the above list but should still be found
            if not candidates:
                candidates = [c for c in b.getChildren() if c.p.flags in b.p.flags]
        else:
            candidates = b.getChildrenWithFlags(flagOfInterest)
        if len(candidates) == 0:
            # if only 1 solid, be smart enought to snag it
            solidMaterials = getSolidComponents(b)
            if len(solidMaterials) == 1:
                candidates = solidMaterials
        if len(candidates) == 0:
            raise RuntimeError(f"No target component found!\n   Block {b}")
        if len(candidates) > 1:
            raise RuntimeError(
                "Cannot have more than one component within a block that has the target flag!"
                f"Block {b}\nflagOfInterest {flagOfInterest}\nComponents {candidates}"
            )
        target = candidates[0]
        self._setExpansionTarget(b, target)
        return target

    def _setExpansionTarget(self, b: "Block", target: "Component"):
        self._componentDeterminesBlockHeight[target] = True
        b.p.axialExpTargetComponent = target.name

    def _isFuelLocked(self, b: "Block"):
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
        self._setExpansionTarget(b, c)

    def isTargetComponent(self, c: "Component") -> bool:
        """Returns bool if c is a target component.

        Parameters
        ----------
        c : :py:class:`Component <armi.reactor.components.component.Component>`
            Component to check target component status
        """
        return bool(c in self._componentDeterminesBlockHeight)
