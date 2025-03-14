# Copyright 2020 TerraPower, LLC
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
Generic Thermal/Hydraulics Plugin.

Thermal/hydraulics is concerned with temperatures, flows, pressures,
and heat transfer.
"""

from armi import interfaces, plugins
from armi.physics.thermalHydraulics import settings

ORDER = interfaces.STACK_ORDER.THERMAL_HYDRAULICS


class ThermalHydraulicsPlugin(plugins.ArmiPlugin):
    """Plugin for thermal/hydraulics."""

    @staticmethod
    @plugins.HOOKIMPL
    def exposeInterfaces(cs):
        """Expose the T/H interfaces."""
        return []

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        """Define settings for T/H."""
        return settings.defineSettings()

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettingsValidators(inspector):
        """Define settings inspections for T/H."""
        return settings.defineValidators(inspector)

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameters():
        """Define additional parameters for the reactor data model."""
        from armi.physics.thermalHydraulics import parameters

        return parameters.getParameterDefinitions()

    @staticmethod
    @plugins.HOOKIMPL
    def afterConstructionOfAssemblies(assemblies, cs):
        """After new assemblies are built, set some state information."""
