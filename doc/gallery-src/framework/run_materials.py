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
Listing of Material Library.
============================

This is a listing of all the elements in all the materials that are included in the ARMI
material library. Many of the materials in this library are academic in quality and
contents. Some have temperature dependent properties, but some don't. You can provide
your own proprietary material properties via a plugin.

More info about the materials here: :py:mod:`armi.materials`.
"""

import matplotlib.pyplot as plt
import numpy as np

from armi import configure, materials
from armi.nucDirectory import nuclideBases

MAX_Z = 98  # stop at Californium

configure(permissive=True)

materialNames = []
mats = list(materials.iterAllMaterialClassesInNamespace(materials))
numMats = len(mats)

zVals = np.zeros((numMats, MAX_Z))

for mi, matCls in enumerate(mats):
    m = matCls()
    materialNames.append(m.name)
    for nucName, frac in m.massFrac.items():
        nb = nuclideBases.byName[nucName]
        idx = mi, nb.z - 1
        try:
            zVals[idx] += frac
        except IndexError:
            # respect the MAX_Z bounds
            pass

fig, ax = plt.subplots(figsize=(16, 12))
im = ax.imshow(zVals, cmap="YlGn")

ax.set_xticks(np.arange(MAX_Z))
ax.set_yticks(np.arange(numMats))
ax.set_xticklabels(np.arange(MAX_Z) + 1, fontsize=6)
ax.set_yticklabels(materialNames)
ax.set_xlabel("Proton number (Z)")
ax.grid(alpha=0.2, ls="--")

ax.set_title("Mass fractions in the ARMI material library")
plt.show()
