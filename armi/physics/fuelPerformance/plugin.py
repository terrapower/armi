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

"""Generic Fuel Performance Plugin."""

from armi import interfaces, plugins
from armi.physics.fuelPerformance import settings

ORDER = interfaces.STACK_ORDER.CROSS_SECTIONS


class FuelPerformancePlugin(plugins.ArmiPlugin):
    """Plugin for fuel performance."""

    @staticmethod
    @plugins.HOOKIMPL
    def exposeInterfaces(cs):
        """Expose the fuel performance interfaces."""
        return []

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        """Define settings for fuel performance."""
        return settings.defineSettings()

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettingsValidators(inspector):
        """Define settings inspections for fuel performance."""
        return settings.defineValidators(inspector)

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameters():
        """Define parameters for the plugin."""
        from armi.physics.fuelPerformance import parameters

        return parameters.getFuelPerformanceParameterDefinitions()
