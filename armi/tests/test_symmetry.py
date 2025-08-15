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

"""Unit tests for handling of symmetry-aware parameters."""

from armi.reactor.assemblyParameters import getAssemblyParameterDefinitions
from armi.reactor.blockParameters import getBlockParameterDefinitions
from armi.reactor.reactorParameters import defineCoreParameters
from armi.testing import symmetryTesting


class ArmiSymmetryTest(symmetryTesting.BasicArmiSymmetryTestHelper):
    """Run symmetry intentionality tests for ARMI."""

    def setUp(self):
        self.pluginCoreParams = defineCoreParameters()
        self.pluginAssemblyParams = getAssemblyParameterDefinitions()
        self.pluginBlockParams = getBlockParameterDefinitions()
        self.pluginSymmetricBlockParams = [
            "molesHmNow",
            "molesHmBOL",
            "massHmBOL",
            "initialB10ComponentVol",
            "kgFis",
            "kgHM",
        ]
        super().setUp()
