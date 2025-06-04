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
Plotting a multi-group scatter matrix.
======================================

Here we plot scatter matrices from an ISOTXS microscopic cross section library.
We plot the inelastic scatter cross section of U235 as well as the (n,2n) source
matrix.

See Also: :py:mod:`ISOTXS <armi.nuclearDataIO.isotxs>` format.
"""

import matplotlib.pyplot as plt

from armi import configure
from armi.nuclearDataIO import xsNuclides
from armi.nuclearDataIO.cccc import isotxs
from armi.tests import ISOAA_PATH

configure(permissive=True)

lib = isotxs.readBinary(ISOAA_PATH)

u235 = lib.getNuclide("U235", "AA")
xsNuclides.plotScatterMatrix(u235.micros.inelasticScatter, "U-235 inelastic")

plt.figure()
xsNuclides.plotScatterMatrix(u235.micros.n2nScatter, "U-235 n,2n src")
