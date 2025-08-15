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
Audit symmetry-aware parameters in fuel performance.

See Also
--------
    armi.testing.symmetryTesting
"""

from armi.physics.fuelPerformance.parameters import getFuelPerformanceParameterDefinitions
from armi.reactor.blocks import Block
from armi.testing import symmetryTesting


class TestArmiFuelPerformanceParamSymmetry(symmetryTesting.BasicArmiSymmetryTestHelper):
    def setUp(self):
        pluginParameters = getFuelPerformanceParameterDefinitions()
        self.blockParamsToTest = pluginParameters[Block]
        self.parameterOverrides = {
            "gasReleaseFraction": 0.5,
            "bondRemoved": 0.5,
        }
        super().setUp()
