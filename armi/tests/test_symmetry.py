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
Audit symmetry-aware parameters in baseline ARMI.

See Also
--------
    armi.testing.symmetryTesting
"""

from armi.reactor.assemblyParameters import getAssemblyParameterDefinitions
from armi.reactor.blockParameters import getBlockParameterDefinitions
from armi.reactor.reactorParameters import defineCoreParameters
from armi.testing import symmetryTesting


class ArmiSymmetryTest(symmetryTesting.BasicArmiSymmetryTestHelper):
    """Run symmetry intentionality tests for ARMI."""

    def setUp(self):
        self.coreParamsToTest = defineCoreParameters()
        self.assemblyParamsToTest = getAssemblyParameterDefinitions()
        self.blockParamsToTest = getBlockParameterDefinitions()
        self.expectedSymmetricBlockParams = [
            "molesHmNow",
            "molesHmBOL",
            "massHmBOL",
            "initialB10ComponentVol",
            "kgFis",
            "kgHM",
        ]
        self.expectedSymmetricAssemblyParams = ["THmassFlowRate"]
        self.parameterOverrides = {"xsType": ["A"], "xsTypeNum": 65, "notes": ""}
        self.paramsToIgnore = ["maxAssemNum"]

        super().setUp()
