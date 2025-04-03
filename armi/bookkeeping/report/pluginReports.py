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
"""
TODO: JOHN.

TODO: JOHN.
"""
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from armi.plugins import ArmiPlugin


def parametersReport(
    plugin: type["ArmiPlugin"], returnDict: bool = True
) -> Union[list, dict]:
    """TODO: JOHN."""
    parameters = plugin.defineParameters()
    data = {}
    for armiObjType, params in parameters.items():
        d = {}
        for param in params:
            d[param.name] = {"description": param.description, "units": param.units}
        data[armiObjType] = d

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
    """TODO: JOHN: This needs to be more configurable in columns."""
    settings = plugin.defineSettings()
    header = ["name", "description", "default", "options"]
    data = [header]
    for setting in settings:
        data.append(
            [
                setting.name,
                setting.description,
                getattr(setting, "default", ""),
                getattr(setting, "options", ""),  # TODO: Handle list?
            ]
        )

    if returnDict:
        return {name: dict(zip(header[1:], vals)) for name, *vals in data[1:]}

    return data
