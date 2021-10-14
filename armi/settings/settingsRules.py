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
This module contains rules supporting custom actions taken on the reading of setting inputs

Note
----
The ``settingsRules`` system was developed before the pluginification of ARMI, and
doesn't play very nicely with the post-plugin world. This is mainly because
registration of new rules happens at import time of the rule itself, which is
unreliable and difficult to control, and even sort of implicit and sneaky. They are
also somewhat redundant with the
:py:class:`armi.operators.settingsValidation.Query`/:py:class:`armi.operators.settingsValidation.Inspector`
system and the ``scripts.migration`` package.. It is not recommended for plugins to define
settings rules using the mechanism
in this module, which may be removed in the future.
"""
import re

from armi import runLog

OLD_TAGS = {
    "int": "int",
    "float": "float",
    "tuple": "tuple",
    "boolean": "bool",
    "string": "str",
    "list": "list",
}

TARGETED_CONVERSIONS = {}
GENERAL_CONVERSIONS = []


def include_as_rule(*args):
    def decorated_conversion(func):
        def signature_enforcement(cs, name, value):
            updateSettings = func(cs, name, value)
            return updateSettings

        if isinstance(args[0], str):
            for trigger in args:  # should be a setting name
                if trigger in TARGETED_CONVERSIONS:
                    raise Exception(
                        "Only one targeted conversion should be alloted per trigger. "
                        "{} is given at least twice.".format(trigger)
                    )
                TARGETED_CONVERSIONS[trigger] = signature_enforcement
        else:
            GENERAL_CONVERSIONS.append(signature_enforcement)

        return signature_enforcement

    if len(args) == 1 and callable(args[0]):  # general conversion
        return decorated_conversion(args[0])
    elif isinstance(args[0], str):  # setting string names provided
        return decorated_conversion
    else:
        raise ValueError(
            "The setting conversion decorator has been misused. "
            "Input args were {}".format(args)
        )


@include_as_rule
def nullRule(_cs, name, value):
    """
    Pass setting values through.

    All settings are passed through these settings rules when being read, with the
    filtered results actually being used. Therefore, settings that aren't manipulated
    need to be returned by something.
    """
    return {name: value}


@include_as_rule("verbosity", "branchVerbosity")
def applyVerbosity(cs, name, value):
    # rather than erroring on poor inputs because these used to be integers, just go to the default
    # this isn't a high risk setting that terribly needs protection. 'value' should only be fed in after
    # a valid definition has been supplied so we can look at the existing options.
    if name in cs and value not in cs.getSetting("verbosity").options:
        value = cs["verbosity"]

    return {name: value}


@include_as_rule("fpModel")
def oldFourPass(_cs, name, value):
    if value == "oldFourPass":
        runLog.warning(
            'The fpModel setting value of "oldFourPass" is no longer valid, '
            'changing to "infinitelyDilute"'
        )
        value = "infinitelyDilute"

    return {name: value}


@include_as_rule("fuelPerformanceEngine")
def squashNoneFP(_cs, name, value):
    if value == "None":
        value = ""
    return {name: value}


@include_as_rule("assemblyRotationAlgorithm")
def assemblyRotationAlgorithmStringNone(_cs, name, value):
    """Some users experienced a string None being introduced into this setting
    and we want to provide a smooth fix

    See T1345

    """
    if value == "None":
        value = ""

    return {name: value}


@include_as_rule("sensitivityCoefficientsToCompute")
def sensitivityCoefficientsCommonCapitalizationMistake(_cs, name, value):
    newval = []
    # only convert when already converted to list. (Default starts as string!)
    if isinstance(value, list):
        for val in value:
            original = val
            val = re.sub("voidworth", "rxCoreWideCoolantVoidWorth", val)
            val = re.sub("naDensity3", "totalCoolantDensity", val)
            val = re.sub("totalCoolantDensity", "rxCoolantDensityCoeffPerTemp", val)
            if val != original:
                runLog.warning(
                    "invalid sensitivityCoefficientsToCompute setting value `{}` changed to `{}`.".format(
                        original, val
                    )
                )
            newval.append(val)
    else:
        newval = value

    return {name: newval}


@include_as_rule("twrcOption")
def twrcOptionConversion(_cs, name, value):
    """
    Deprecated `twrcOption` is warned about here.
    """
    raise ValueError(
        "The `twrcOption` setting has been removed and cannot be migrated automatically. Please "
        "`sasPlantModelInputFile` settings as appropriate."
    )


@include_as_rule("PumpInertiaPercentChange")
def PumpInertiaPercentChange(_cs, name, value):
    percentChange = float(value) / 100.0
    if abs(percentChange) < 0.001:
        # small values used to be used to trigger the default pump inertia. Now we just set it exactly
        percentChange = 0.0
    newVal = _cs["pumpInertia"] * (1.0 + percentChange)
    runLog.warning(
        "Setting new `pumpInertia` setting to {} based on deprecated `PumpInertiaPercentChange` value"
        " of {}".format(newVal, value)
    )
    return {"pumpInertia": newVal}
