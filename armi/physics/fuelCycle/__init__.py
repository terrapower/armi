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
The fuel cycle package analyzes the various elements of nuclear fuel cycles from mining to disposal.

Fuel cycle code can include things like:

* In- and ex-core fuel management
* Fuel chemistry
* Fuel processing
* Fuel fabrication
* Fuel mass flow scenarios
* And so on

There is one included fuel cycle plugin: The Fuel Handler.

The fuel handler plugin moves fuel around in a reactor.
"""

from armi import interfaces, operators, plugins
from armi.operators import RunTypes
from armi.physics.fuelCycle import fuelHandlers, settings

ORDER = interfaces.STACK_ORDER.FUEL_MANAGEMENT


class FuelHandlerPlugin(plugins.ArmiPlugin):
    """The built-in ARMI fuel management plugin."""

    @staticmethod
    @plugins.HOOKIMPL
    def exposeInterfaces(cs):
        """
        Implementation of the exposeInterfaces plugin hookspec.

        Notes
        -----
        The interface may import user input modules to customize the actual
        fuel management.
        """
        from armi.physics.neutronics.settings import CONF_NEUTRONICS_KERNEL

        fuelHandlerNeedsToBeActive = cs[settings.CONF_FUEL_HANDLER_NAME] or (
            cs["eqDirect"] and cs["runType"].lower() == RunTypes.STANDARD.lower()
        )
        if not fuelHandlerNeedsToBeActive or "MCNP" in cs[CONF_NEUTRONICS_KERNEL]:
            return []
        else:
            enabled = cs["runType"] != operators.RunTypes.SNAPSHOTS
            return [interfaces.InterfaceInfo(ORDER, fuelHandlers.FuelHandlerInterface, {"enabled": enabled})]

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        """Define settings for the plugin."""
        return settings.getFuelCycleSettings()

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettingsValidators(inspector):
        """Implementation of settings inspections for fuel cycle settings."""
        return settings.getFuelCycleSettingValidators(inspector)
