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
"""Unit tests for fluid-specific behaviors.

The ARMI framework has a lot of thermal expansion machinery that applies to all components
but doesn't make sense for fluids. The tests here help show fluid materials still
play nice with the rest of the framework.
"""

from unittest import TestCase

from armi.materials.material import Fluid, Material
from armi.reactor.components import Circle
from armi.tests import mockRunLogs


class TestFluids(TestCase):
    class MyFluid(Fluid):
        """Stand-in fluid that doesn't provide lots of functionality."""

    class MySolid(Material):
        """Stand-in solid that doesn't provide lots of functionality."""

    def test_fluidDensityWrapperNoWarning(self):
        """Test that Component.material.density does not raise a warning for fluids.

        The ARMI Framework contains a mechanism to warn users if they ask for the density of a
        material attached to a component. But the component is the source of truth for volume and
        composition. And can be thermally expanded during operation. Much of the framework operates
        on ``Component.density`` and other ``Component`` methods for mass accounting. However,
        ``comp.material.density`` does not know about the new composition or volumes and can diverge
        from ``component.density``.

        Additionally, the framework does not do any thermal expansion on fluids. So the above calls
        to ``component.material.density`` are warranted for fluids.
        """
        self._checkCompDensityLogs(
            mat=self.MySolid(),
            nExpectedWarnings=1,
            msg="Solids should have the density warning logged.",
        )
        self._checkCompDensityLogs(
            mat=self.MyFluid(),
            nExpectedWarnings=0,
            msg="Fluids should not have the density warning logged.",
        )

    def _checkCompDensityLogs(self, mat: Material, nExpectedWarnings: int, msg: str):
        comp = Circle(name="test", material=mat, Tinput=20, Thot=20, id=0, od=1, mult=1)
        with mockRunLogs.LogCounter() as logs:
            comp.material.density(Tc=comp.temperatureInC)
        self.assertEqual(logs.messageCounts["warning"], nExpectedWarnings, msg=msg)
