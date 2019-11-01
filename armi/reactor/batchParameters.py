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

from armi.reactor import blockParameters
from armi.reactor import parameters


def getBatchParameterDefinitions():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder() as pb:
        pb.defParam(
            "targetDensity",
            units="g/cm$^3$",
            description='target density for the "mass addition components" of this batch',
            location="?",
            saveToDB=True,
            default=1.0,
        )

    return pDefs
