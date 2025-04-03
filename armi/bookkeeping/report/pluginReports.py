# Copyright 2025 TerraPower, LLC
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
"""Helpful tools for reporting data on Plugins."""
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from armi.plugins import ArmiPlugin


def parametersReport(
    plugin: type["ArmiPlugin"], returnDict: bool = True
) -> Union[list, dict]:
    """Return a simple data structure with information on the parameters defined by a single Plugin.

    Parameters
    ----------
    plugin : ArmiPlugin
        The Plugin we want to get data about.
    returnDict : bool
        True if we want to report the data as a pure dict. If False, the data is returned as a list.

    Returns
    -------
    dict or list
        The parameters report in dict or lsit format.
    """
    parameters = plugin.defineParameters()
    if parameters is None or not len(parameters):
        # handle special, empty case
        if returnDict:
            return {}
        else:
            return []

    # pull the data from the Plugin
    data = {}
    for armiObjType, params in parameters.items():
        d = {}
        for param in params:
            d[param.name] = {"description": param.description, "units": param.units}
        data[armiObjType] = d

    # handle the return dict param
    if not returnDict:
        header = ["param-type", "name", "description", "units"]
        d = [header]
        for armiObjType, params in data.items():
            for name, p in params.items():
                d.append([armiObjType, name, p["description"], p["units"]])

        return d

    return data


def settingsReport(
    plugin: type["ArmiPlugin"], returnDict: bool = True
) -> Union[list, dict]:
    """Return a simple data structure with information on the settings defined by a single Plugin.

    Parameters
    ----------
    plugin : ArmiPlugin
        The Plugin we want to get data about.
    returnDict : bool
        True if we want to report the data as a pure dict. If False, the data is returned as a list.

    Returns
    -------
    dict or list
        The settings report in dict or lsit format.
    """
    settings = plugin.defineSettings()
    if settings is None or not len(settings):
        # handle special, empty case
        if returnDict:
            return {}
        else:
            return []

    # pull the data from the Plugin
    header = ["name", "description", "default", "options"]
    data = [header]
    for setting in settings:
        data.append(
            [
                setting.name,
                setting.description,
                getattr(setting, "default", ""),
                getattr(setting, "options", ""),
            ]
        )

    # handle the return dict param
    if returnDict:
        return {name: dict(zip(header[1:], vals)) for name, *vals in data[1:]}

    return data
