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

from armi.physics.neutronics.parameters import getNeutronicsParameterDefinitions
from armi.reactor.blocks import Block
from armi.reactor.cores import Core
from armi.testing.tests import test_testing


class TestArmiNeutronicsParams(test_testing.BasicArmiSymmetryTestHelper):
    def setUp(self):
        pluginParameters = getNeutronicsParameterDefinitions()
        self.pluginCoreParams = [p if isinstance(p, str) else p.name for p in pluginParameters[Core]]
        self.pluginBlockParams = [p if isinstance(p, str) else p.name for p in pluginParameters[Block]]
        self.pluginSymmetricBlockParams = ["mgFlux", "adjMgFlux", "lastMgFlux", "mgFluxGamma", "reactionRates"]
        super().setUp()
