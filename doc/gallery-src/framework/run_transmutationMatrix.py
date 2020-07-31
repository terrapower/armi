"""
Transmutation matrix
====================

Plot a transmutation matrix. 
"""
import os

import matplotlib.patches as mpatch
from matplotlib.patches import Arrow
from matplotlib.collections import PatchCollection
import matplotlib.pyplot as plt
from armi.tests import ISOAA_PATH
from armi.context import ROOT, RES
from armi.nucDirectory import nuclideBases
from armi.nuclearDataIO import isotxs


def plotNuc(nb, ax):
    patch = mpatch.Rectangle((nb.a - nb.z, nb.z), 1.0, 1.0)
    rx, ry = patch.get_xy()
    cx = rx + patch.get_width() / 2.0
    cy = ry + 3 * patch.get_height() / 4.0
    ax.annotate(
        nb.name,
        (cx, cy),
        color="k",
        weight="normal",
        fontsize=10,
        ha="center",
        va="center",
    )
    return patch


with open(os.path.join(RES, "burn-chain.yaml")) as burnChainStream:
    nuclideBases.imposeBurnChain(burnChainStream)
lib = isotxs.readBinary(ISOAA_PATH)
nucs = [nuc.name for nuc in lib.getNuclides("AA")]
nbs = [nuclideBases.fromName(n) for n in nucs]
fig, ax = plt.subplots(figsize=(15, 10))

patches = []
for nb in nbs:
    if nb.z < 91 and False:
        continue
    patch = plotNuc(nb, ax)
    patches.append(patch)
    for trans in nb.trans:
        nbp = nuclideBases.fromName(trans.productNuclides[0])
        if nbp.z == 0:
            # LFP
            continue
        x, y, dx, dy = (
            nb.a - nb.z,
            nb.z,
            ((nbp.a - nbp.z) - (nb.a - nb.z)),
            (nbp.z - nb.z),
        )
        if abs(dx) > 2:
            continue
        # print(nbp, x,y,dx,dy)
        arrow = ax.arrow(x + 0.5, y + 0.5, dx / 7, dy / 7, width=0.05, edgecolor="blue")
        # patches.append(arrow)

pc = PatchCollection(patches, facecolor="green", alpha=0.2, edgecolor="black")
ax.add_collection(pc)
ax.set_xlim((1, 155))
ax.set_ylim((1, 97))
ax.set_aspect("equal")
plt.show()
# ax.autoscale_view(True, True, True)
