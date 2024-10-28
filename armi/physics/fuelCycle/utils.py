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

from armi.reactor.grids import IndexLocation

if typing.TYPE_CHECKING:
    from armi.reactor.blocks import Block


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
