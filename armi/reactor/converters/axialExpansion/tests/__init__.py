# Copyright 2024 TerraPower, LLC
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

import collections
import unittest

from armi import materials
from armi.materials import _MATERIAL_NAMESPACE_ORDER
from armi.reactor.converters.axialExpansion import getSolidComponents
from armi.reactor.converters.axialExpansion.axialExpansionChanger import (
    AxialExpansionChanger,
)
from armi.reactor.flags import Flags


class AxialExpansionTestBase(unittest.TestCase):
    """Common methods and variables for unit tests."""

    Steel_Component_Lst = [
        Flags.DUCT,
        Flags.GRID_PLATE,
        Flags.HANDLING_SOCKET,
        Flags.INLET_NOZZLE,
        Flags.CLAD,
        Flags.WIRE,
        Flags.ACLP,
        Flags.GUIDE_TUBE,
    ]

    def setUp(self):
        self.obj = AxialExpansionChanger()
        self.componentMass = collections.defaultdict(list)
        self.componentDensity = collections.defaultdict(list)
        self.totalAssemblySteelMass = []
        self.blockZtop = collections.defaultdict(list)
        self.origNameSpace = _MATERIAL_NAMESPACE_ORDER
        # set namespace order for materials so that fake HT9 material can be found
        materials.setMaterialNamespaceOrder(
            [
                "armi.reactor.converters.axialExpansion.tests.buildAxialExpAssembly",
                "armi.materials",
            ]
        )

    def tearDown(self):
        # reset global namespace
        materials.setMaterialNamespaceOrder(self.origNameSpace)

    def _getConservationMetrics(self, a):
        """Retrieves and stores various conservation metrics.

        - useful for verification and unittesting
        - Finds and stores:
            1. mass and density of target components
            2. mass of assembly steel
            3. block heights
        """
        totalSteelMass = 0.0
        for b in a:
            # store block ztop
            self.blockZtop[b].append(b.p.ztop)
            for c in getSolidComponents(b):
                # store mass and density of component
                self.componentMass[c].append(c.getMass())
                self.componentDensity[c].append(
                    c.material.getProperty("density", c.temperatureInK)
                )
                # store steel mass for assembly
                if c.p.flags in self.Steel_Component_Lst:
                    totalSteelMass += c.getMass()

        self.totalAssemblySteelMass.append(totalSteelMass)
