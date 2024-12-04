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
Baseline fuel performance related executers and options.

These can be subclassed in fuel performance plugins to perform
fuel performance physics calculations.

Fuel performance is described in the
:py:mod:`Fuel Performance subpackage <armi.physics.fuelPerformance>`
"""

from armi.physics import executers
from armi.physics.fuelPerformance.settings import (
    CONF_AXIAL_EXPANSION,
    CONF_BOND_REMOVAL,
    CONF_CLADDING_STRAIN,
    CONF_CLADDING_WASTAGE,
    CONF_FGR_REMOVAL,
    CONF_FGYF,
    CONF_FUEL_PERFORMANCE_ENGINE,
)


class FuelPerformanceOptions(executers.ExecutionOptions):
    """Options relevant to all fuel performance engines."""

    def __init__(self, label=None):
        executers.ExecutionOptions.__init__(self, label)
        self.fuelPerformanceEngine = None
        self.axialExpansion = None
        self.bondRemoval = None
        self.fissionGasRemoval = None
        self.claddingWastage = None
        self.claddingStrain = None

    def fromUserSettings(self, cs):
        """Copy relevant settings values from cs into this object."""
        self.fuelPerformanceEngine = cs[CONF_FUEL_PERFORMANCE_ENGINE]
        self.axialExpansion = cs[CONF_AXIAL_EXPANSION]
        self.bondRemoval = cs[CONF_BOND_REMOVAL]
        self.fissionGasRemoval = cs[CONF_FGR_REMOVAL]
        self.claddingWastage = cs[CONF_CLADDING_WASTAGE]
        self.claddingStrain = cs[CONF_CLADDING_STRAIN]
        self.fissionGasYieldFraction = cs[CONF_FGYF]

    def fromReactor(self, reactor):
        """Load options from reactor."""


class FuelPerformanceExecuter(executers.DefaultExecuter):
    """
    Prep, execute, and process a fuel performance solve.

    This uses the ``DefaultExecuter`` with the hope that most
    subclasses can use that run loop. As more fuel performance plugins are
    built we can reconsider this hierarchy.
    """

    def __init__(self, options, reactor):
        executers.DefaultExecuter.__init__(self, options, reactor)
