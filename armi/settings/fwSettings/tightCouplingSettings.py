# Copyright 2023 TerraPower, LLC
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
The data structures and schema of the tight coupling settings.

These are advanced/compound settings that are carried along in the normal cs
object but aren't simple key/value pairs.
"""

from typing import Dict, Union

import voluptuous as vol

from armi.settings import Setting

_SCHEMA = vol.Schema(
    {
        str: vol.Schema(
            {
                vol.Required("parameter"): str,
                vol.Required("convergence"): vol.Coerce(float),
            }
        )
    }
)


class TightCouplingSettings(dict):
    """
    Dictionary with keys of Interface functions and a dictionary value.

    Notes
    -----
    The dictionary value for each Interface function is required to contain a ``parameter``
    and a ``convergence`` key with string and float values, respectively. No other
    keys are allowed.

    Examples
    --------
        couplingSettings = TightCouplingSettings({'globalFlux': {'parameter': 'keff', 'convergence': 1e-05}})
    """

    def __repr__(self):
        return f"<{self.__class__.__name__} with Interface functions {self.keys()}>"


def serializeTightCouplingSettings(tightCouplingSettingsDict: Union[TightCouplingSettings, Dict]) -> Dict[str, Dict]:
    """
    Return a serialized form of the ``TightCouplingSettings`` as a dictionary.

    Notes
    -----
    Attributes that are not set (i.e., set to None) will be skipped.
    """
    if not isinstance(tightCouplingSettingsDict, dict):
        raise TypeError(f"Expected a dictionary for {tightCouplingSettingsDict}")

    output = {}
    for interfaceFunction, options in tightCouplingSettingsDict.items():
        # Setting the value to an empty dictionary
        # if it is set to a None or an empty
        # dictionary.
        if not options:
            continue

        output[str(interfaceFunction)] = options
    return output


class TightCouplingSettingDef(Setting):
    """
    Custom setting object to manage the tight coupling settings for each interface.

    Notes
    -----
    This uses the ``tightCouplingSettingsValidator`` schema to validate the inputs
    and will automatically coerce the value into a ``TightCouplingSettings`` dictionary.
    """

    def __init__(self, name):
        description = (
            "Data structure defining the tight coupling parameters and convergence criteria for each interface."
        )
        label = "Interface Tight Coupling Control"
        default = TightCouplingSettings()
        options = None
        schema = tightCouplingSettingsValidator
        enforcedOptions = False
        subLabels = None
        isEnvironment = False
        oldNames = None
        Setting.__init__(
            self,
            name,
            default,
            description,
            label,
            options,
            schema,
            enforcedOptions,
            subLabels,
            isEnvironment,
            oldNames,
        )

    def dump(self):
        """Return a serialized version of the ``TightCouplingSettings`` object."""
        return serializeTightCouplingSettings(self._value)


def tightCouplingSettingsValidator(tightCouplingSettingsDict: Dict[str, Dict]) -> TightCouplingSettings:
    """Returns a ``TightCouplingSettings`` object if validation is successful."""
    tightCouplingSettingsDict = serializeTightCouplingSettings(tightCouplingSettingsDict)
    tightCouplingSettingsDict = _SCHEMA(tightCouplingSettingsDict)
    vals = TightCouplingSettings()
    for interfaceFunction, inputParams in tightCouplingSettingsDict.items():
        vals[interfaceFunction] = inputParams
    return vals
