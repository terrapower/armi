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
Generic Fuel Performance Plugin
"""

import tabulate

from armi import plugins
from armi import interfaces
from armi import runLog
from armi.reactor.flags import Flags
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
        from armi.physics.fuelPerformance import parameters

        return parameters.getFuelPerformanceParameterDefinitions()

    @staticmethod
    @plugins.HOOKIMPL
    def afterConstructionOfAssemblies(assemblies, cs):
        """After new assemblies are built, set some state information."""
        _setBOLBond(assemblies)


def _setBOLBond(assemblies):
    """Set initial bond fractions for each block in the core."""
    assemsWithoutMatchingBond = set()
    for a in assemblies:
        for b in a:
            coolant = b.getComponent(Flags.COOLANT, quiet=True)
            bond = b.getComponent(Flags.BOND, quiet=True)
            if not bond:
                b.p.bondBOL = 0.0
                continue
            b.p.bondBOL = sum(
                [bond.getNumberDensity(nuc) for nuc in bond.getNuclides()]
            )

            if not isinstance(bond.material, coolant.material.__class__):
                assemsWithoutMatchingBond.add(
                    (
                        a.getType(),
                        b.getType(),
                        bond.material.getName(),
                        coolant.material.getName(),
                    )
                )

    if assemsWithoutMatchingBond:
        runLog.warning(
            "The following have mismatching `{}` and `{}` materials:\n".format(
                Flags.BOND, Flags.COOLANT
            )
            + tabulate.tabulate(
                list(assemsWithoutMatchingBond),
                headers=[
                    "Assembly Type",
                    "Block Type",
                    "Bond Material",
                    "Coolant Material",
                ],
                tablefmt="armi",
            )
        )
