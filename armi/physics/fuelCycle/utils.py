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

import typing

import numpy as np

from armi.reactor.flags import Flags
from armi.reactor.grids import IndexLocation

if typing.TYPE_CHECKING:
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

    """
    # Avoid using Assembly.getChildrenWithFlags(Flags.FUEL)
    # because that creates an entire list where we may just need the first
    # fuel block. Same for avoiding Block.getChildrenWithFlags.
    return any(b.hasFlags(Flags.FUEL) and b.p.percentBuMaxPinLocation for b in a)


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
    """
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
