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
Write MCNP Material Cards
=========================

Here we load a test reactor and write each component of one fuel block out as
MCNP material cards.

Normally, code-specific utility code would belong in a code-specific ARMI
plugin. But in this case, the need for MCNP materials cards is so pervasive
that it made it into the framework
"""

from armi import configure
from armi.nucDirectory import nuclideBases as nb
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.utils.densityTools import formatMaterialCard

# configure ARMI
configure(permissive=True)

_o, r = test_reactors.loadTestReactor()

bFuel = r.core.getBlocks(Flags.FUEL)[0]

for ci, component in enumerate(bFuel, start=1):
    ndens = component.getNumberDensities()
    # convert nucName (str) keys to nuclideBase keys
    ndensByBase = {nb.byName[nucName]: dens for nucName, dens in ndens.items()}
    print("".join(formatMaterialCard(ndensByBase, matNum=ci)))
