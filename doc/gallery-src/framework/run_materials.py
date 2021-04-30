"""
Listing of Material Library
===========================

This is a listing of all the elements in all the materials that are included in the ARMI
material library. Many of the materials in this library are academic in quality and
contents. Some have temperature dependent properties, but some don't. You can provide
your own proprietary material properties via a plugin.

More info about the materials here: :py:mod:`armi.materials`.

"""

import numpy as np
import matplotlib.pyplot as plt

from armi import configure, materials
from armi.nucDirectory import nuclideBases

MAX_Z = 96  # stop at Curium

configure(permissive=True)

materialNames = []
mats = list(materials.iterAllMaterialClassesInNamespace(materials))

numMats = len(mats)

zVals = np.zeros((numMats, MAX_Z))


for mi, matCls in enumerate(mats):
    m = matCls()
    materialNames.append(m.name)
    for nucName, frac in m.p.massFrac.items():
        nb = nuclideBases.byName[nucName]
        idx = mi, nb.z - 1
        zVals[idx] += frac

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
