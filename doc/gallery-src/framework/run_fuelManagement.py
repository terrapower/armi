"""
Fuel management in a LWR
========================

Demo of locating and swapping assemblies in a core with Cartesian geometry. Given a burnup
distribution, this swaps high burnup assemblies with low ones.

Assembly selection for moving and swapping is very flexible using the ARMI API and the
high-level language features of Python. This allows highly complex fuel management
algorithms to be expressed and parameterized.

Because the ARMI framework does not come with a LWR global flux/depletion solver, actual
flux/depletion results would need to be provided by a physics plugin before actually using
ARMI to do fuel management. Thus, this example applies a dummy burnup distribution for
demonstration purposes.

"""
# Tell the gallery to feature the 2nd image
# sphinx_gallery_thumbnail_number = 2
import math

from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.physics.fuelCycle import fuelHandlers
from armi.utils import plotting

from armi import configure

configure(permissive=True)

o, reactor = test_reactors.loadTestReactor(inputFileName="refTestCartesian.yaml")

# Apply a dummy burnup distribution roughly in a cosine
for b in reactor.core.getBlocks(Flags.FUEL):
    x, y, z = b.spatialLocator.getGlobalCoordinates()
    d = math.sqrt(x ** 2 + y ** 2)
    b.p.percentBu = 5 * math.cos(d * math.pi / 2 / 90)

# show the initial burnup distribution
plotting.plotFaceMap(reactor.core, param="percentBu")

fuelHandler = fuelHandlers.FuelHandler(o)

candidateAssems = reactor.core.getAssemblies(Flags.FUEL)
criterion = lambda a: a.getMaxParam("percentBu")
candidateAssems.sort(key=criterion)

for num in range(12):
    # swap the 12 highest burnup assemblies with the 12 lowest burnup ones
    high = candidateAssems.pop()
    low = candidateAssems.pop(0)
    fuelHandler.swapAssemblies(high, low)

# re-filter the remaining candidates for more complex selections
candidateAssems = [a for a in candidateAssems if a.getMaxParam("percentBu") < 4.0]
for num in range(8):
    high = candidateAssems.pop()
    low = candidateAssems.pop(0)
    fuelHandler.swapAssemblies(high, low)

# show final burnup distribution
plotting.plotFaceMap(reactor.core, param="percentBu")
