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
"""Geometric agnostic routines that are useful for fuel cycle analysis on pin-type reactors."""

import operator
import typing

import numpy as np

from armi import runLog
from armi.reactor.flags import Flags
from armi.reactor.grids import IndexLocation, MultiIndexLocation

if typing.TYPE_CHECKING:
    from armi.reactor.blocks import Block
    from armi.reactor.components import Component


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
    fuelBlocks = filter(lambda b: b.hasFlags(Flags.FUEL), a)
    return any(b.hasFlags(Flags.FUEL) and np.any(b.p.linPowByPin) for b in fuelBlocks)


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
    Checks if any `Component.p.pinPercentBu`` is set and contains non-zero data
    on a fuel component in the block.
    """
    # Avoid using Assembly.getChildrenWithFlags(Flags.FUEL)
    # because that creates an entire list where we may just need the first
    # fuel block. Same for avoiding Block.getChildrenWithFlags.
    hasFuelFlags = lambda o: o.hasFlags(Flags.FUEL)
    for b in filter(hasFuelFlags, a):
        for c in filter(hasFuelFlags, b):
            if np.any(c.p.pinPercentBu):
                return True
    return False


def maxBurnupLocator(
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
                f"Pin burnup (n={len(locations)}) and pin locations (n={pinBu.size}) "
                f"on {child} differ: {locations=} :: {pinBu=}"
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
    buGetter = operator.attrgetter("p.percentBuPeak")
    # Discard any blocks with zero burnup
    blocksWithBurnup = filter(buGetter, a)
    try:
        return max(blocksWithBurnup, key=buGetter)
    except Exception as ee:
        msg = f"Error finding max burnup block from {a}"
        runLog.error(msg)
        raise ValueError(msg) from ee
