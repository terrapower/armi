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
Plotting Multi-group XS from ISOTXS.
====================================

In this example, several cross sections are plotted from
an existing binary cross section library file in :py:mod:`ISOTXS <armi.nuclearDataIO.isotxs>` format.
"""

import matplotlib.pyplot as plt

from armi import configure
from armi.nuclearDataIO.cccc import isotxs
from armi.physics.neutronics import energyGroups
from armi.tests import ISOAA_PATH

configure(permissive=True)

gs = energyGroups.getGroupStructure("ANL33")
lib = isotxs.readBinary(ISOAA_PATH)

fe56 = lib.getNuclide("FE", "AA")
u235 = lib.getNuclide("U235", "AA")
u238 = lib.getNuclide("U238", "AA")
b10 = lib.getNuclide("B10", "AA")

plt.step(gs, fe56.micros.nGamma, label=r"Fe (n, $\gamma$)")
plt.step(gs, u235.micros.fission, label="U-235 (n, fission)")
plt.step(gs, u238.micros.nGamma, label=r"U-238 (n, $\gamma$)")
plt.step(gs, b10.micros.nalph, label=r"B-10 (n, $\alpha$)")

plt.xscale("log")
plt.yscale("log")
plt.xlabel("Neutron Energy, eV")
plt.ylabel("Cross Section, barns")
plt.grid(alpha=0.2)
plt.legend()

plt.show()
