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
"""Geometric agnostic routines that are useful for fuel cycle analysis."""

import contextlib
import typing

import numpy as np

from armi.reactor.flags import Flags
from armi.reactor.grids import IndexLocation, MultiIndexLocation

if typing.TYPE_CHECKING:
    from armi.reactor.components import Component
    from armi.reactor.blocks import Block


def assemblyHasFuelPinPowers(a: typing.Iterable["Block"]) -> bool:
    """Determine if an assembly has pin powers.

    These are necessary for determining rotation and may or may
    not be present on all assemblies.

    Parameters
    ----------
    a : Assembly
        Assembly in question

    Returns
    -------
    bool
        If at least one fuel block in the assembly has pin powers.
    """
    # Avoid using Assembly.getChildrenWithFlags(Flags.FUEL)
    # because that creates an entire list where we may just need the first
    # fuel block
    return any(b.hasFlags(Flags.FUEL) and np.any(b.p.linPowByPin) for b in a)


def assemblyHasFuelPinBurnup(a: typing.Iterable["Block"]) -> bool:
    """Determine if an assembly has pin burnups.

    These are necessary for determining rotation and may or may not
    be present on all assemblies.

    Parameters
    ----------
    a : Assembly
        Assembly in question

    Returns
    -------
    bool
        If a block with pin burnup was found.

    Notes
    -----
    Checks two parameters on a fuel block to determine if there is burnup:

    1. ``Block.p.percentBuMaxPinLocation``, or
    2. ``Component.p.pinPercentBu`` on a fuel component in the block.
    """
    # Avoid using Assembly.getChildrenWithFlags(Flags.FUEL)
    # because that creates an entire list where we may just need the first
    # fuel block. Same for avoiding Block.getChildrenWithFlags.
    return any(
        b.hasFlags(Flags.FUEL)
        and (
            any(c.hasFlags(Flags.FUEL) and np.any(c.p.pinPercentBu) for c in b)
            or b.p.percentBuMaxPinLocation
        )
        for b in a
    )


def maxBurnupFuelPinLocation(b: "Block") -> IndexLocation:
    """Find the grid position for the highest burnup fuel pin.

    Parameters
    ----------
    b : Block
        Block in question

    Returns
    -------
    IndexLocation
        The spatial location in the block corresponding to the pin with the
        highest burnup.

    See Also
    --------
    * :func:`getMaxBurnupLocationFromChildren` looks just at the children of this
      block, e.g., looking at pins. This function also looks at the block parameter
      ``Block.p.percentBuMaxPinLocation`` in case the max burnup location cannot be
      determined from the child pins.
    """
    # If we can't find any burnup from the children, that's okay. We have
    # another way to find the max burnup location.
    with contextlib.suppress(ValueError):
        return getMaxBurnupLocationFromChildren(b)
    # Should be an integer, that's what the description says. But a couple places
    # set it to a float like 1.0 so it's still int-like but not something we can slice
    buMaxPinNumber = int(b.p.percentBuMaxPinLocation)
    if buMaxPinNumber < 1:
        raise ValueError(f"{b.p.percentBuMaxPinLocation=} must be greater than zero")
    pinLocations = b.getPinLocations()
    # percentBuMaxPinLocation corresponds to the "pin number" which is one indexed
    # and can be found at ``maxBuBlock.getPinLocations()[pinNumber - 1]``
    maxBuPinLocation = pinLocations[buMaxPinNumber - 1]
    return maxBuPinLocation


def getMaxBurnupLocationFromChildren(
    children: typing.Iterable["Component"],
) -> IndexLocation:
    """Find the location of the pin with highest burnup by looking at components.

    Parameters
    ----------
    children : iterable[Component]
        Iterator over children with a spatial locator and ``pinPercentBu`` parameter

    Returns
    -------
    IndexLocation
        Location of the pin with the highest burnup.

    Raises
    ------
    ValueError
        If no children have burnup, or the burnup and locators differ.

    See Also
    --------
    * :func:`maxBurnupFuelPinLocation` uses this. You should use that method more generally,
      unless you **know** you will always have ``Component.p.pinPercentBu`` defined.
    """
    maxBu = 0
    maxLocation = None
    withBurnupAndLocs = filter(
        lambda c: c.spatialLocator is not None and c.p.pinPercentBu is not None,
        children,
    )
    for child in withBurnupAndLocs:
        pinBu = child.p.pinPercentBu
        if isinstance(child.spatialLocator, MultiIndexLocation):
            locations = child.spatialLocator
        else:
            locations = [child.spatialLocator]
        if len(locations) != pinBu.size:
            raise ValueError(
                f"Pin burnup and pin locations on {child} differ: {locations=} :: {pinBu=}"
            )
        myMaxIX = pinBu.argmax()
        myMaxBu = pinBu[myMaxIX]
        if myMaxBu > maxBu:
            maxBu = myMaxBu
            maxLocation = locations[myMaxIX]
    if maxLocation is not None:
        return maxLocation
    raise ValueError("No burnups found!")


def maxBurnupBlock(a: typing.Iterable["Block"]) -> "Block":
    """Find the block that contains the pin with the highest burnup."""
    maxBlock = None
    maxBurnup = 0
    for b in a:
        maxCompBu = 0
        for c in b:
            if not np.any(c.p.pinPercentBu):
                continue
            compBu = c.p.pinPercentBu.max()
            if compBu > maxCompBu:
                maxCompBu = compBu
        if maxCompBu > maxBurnup:
            maxBurnup = maxCompBu
            maxBlock = b
    if maxBlock is not None:
        return maxBlock
    raise ValueError(f"No blocks with burnup found")
