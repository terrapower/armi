"""
Write MCNP Material Cards
=========================

Here we load a test reactor and write each component of one fuel block out as
MCNP material cards.

Normally, code-specific utility code would belong in a code-specific ARMI
plugin. But in this case, the need for MCNP materials cards is so pervasive
that it made it into the framework.
"""

from armi.reactor.tests import test_reactors
from armi.reactor.flags import Flags
from armi.utils.densityTools import formatMaterialCard
from armi.nucDirectory import nuclideBases as nb
from armi import configure

configure(permissive=True)

_o, r = test_reactors.loadTestReactor()

bFuel = r.core.getBlocks(Flags.FUEL)[0]

for ci, component in enumerate(bFuel, start=1):
    ndens = component.getNumberDensities()
    # convert nucName (str) keys to nuclideBase keys
    ndensByBase = {nb.byName[nucName]: dens for nucName, dens in ndens.items()}
    print("".join(formatMaterialCard(ndensByBase, matNum=ci)))
