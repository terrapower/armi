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
"""
Utilities that perturb specific types of block objects.

This code is relatively design-specific and will only work given
certain object designs. At the moment it only works on Block objects.

Notes
-----
These were once Block method and were moved here as part of an ongoing
effort to remove design-specific assumptions from the reactor model.

These operations are shared by code that modifies objects in place during runtime
and also for inputModifiers that change inputs for parameter sweeping.

"""
import math

from armi import runLog
from armi.reactor.flags import Flags


def adjustSmearDensity(obj, value, bolBlock=None):
    r"""
    modifies the *cold* smear density of a fuel pin by adding or removing fuel dimension.

    Adjusts fuel dimension while keeping cladding ID constant

    sd = fuel_r**2/clad_ir**2  =(fuel_od/2)**2 / (clad_id/2)**2 = fuel_od**2 / clad_id**2
    new fuel_od = sqrt(sd*clad_id**2)

    useful for optimization cases

    Parameters
    ----------
    value : float
        new smear density as a fraction.  This fraction must
        evaluate between 0.0 and 1.0

    bolBlock : Block, optional
        See completeInitialLoading. Required for ECPT cases

    """
    if value <= 0.0 or value > 1.0:
        raise ValueError(
            "Cannot modify smear density of {0} to {1}. Must be a positive fraction"
            "".format(obj, value)
        )
    fuel = obj.getComponent(Flags.FUEL)
    if not fuel:
        runLog.warning(
            "Cannot modify smear density of {0} because it is not fuel".format(obj),
            single=True,
            label="adjust smear density",
        )
        return

    clad = obj.getComponent(Flags.CLAD)
    cladID = clad.getDimension("id", cold=True)
    fuelID = fuel.getDimension("id", cold=True)

    if fuelID > 0.0:  # Annular fuel (Adjust fuel ID to get new smear density)
        fuelOD = fuel.getDimension("od", cold=True)
        newID = fuelOD * math.sqrt(1.0 - value)
        fuel.setDimension("id", newID)
    else:  # Slug fuel (Adjust fuel OD to get new smear density)
        newOD = math.sqrt(value * cladID**2)
        fuel.setDimension("od", newOD)

    # update things like hm at BOC and smear density parameters.
    obj.completeInitialLoading(bolBlock=bolBlock)


def adjustCladThicknessByOD(obj, value):
    """Modifies the cladding thickness by adjusting the cladding outer diameter."""
    clad = _getCladdingComponentToModify(obj, value)
    if clad is None:
        return
    innerDiam = clad.getDimension("id", cold=True)
    clad.setDimension("od", innerDiam + 2.0 * value)


def adjustCladThicknessByID(obj, value):
    """
    Modifies the cladding thickness by adjusting the cladding inner diameter.

    Notes
    -----
    This WILL adjust the fuel smear density
    """
    clad = _getCladdingComponentToModify(obj, value)
    if clad is None:
        return
    od = clad.getDimension("od", cold=True)
    clad.setDimension("id", od - 2.0 * value)


def _getCladdingComponentToModify(obj, value):
    clad = obj.getComponent(Flags.CLAD)
    if not clad:
        runLog.warning("{} does not have a cladding component to modify.".format(obj))
    if value < 0.0:
        raise ValueError(
            "Cannot modify {} on {} due to a negative modifier {}".format(
                clad, obj, value
            )
        )
    return clad
