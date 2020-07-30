"""
Fuel management in a LWR
========================

Demo of locating and swapping assemblies in a core with Cartesian geometry. Given a burnup
distribution, this swaps high burnup assemblies with low ones.

Because the ARMI framework does not come with a LWR global flux/depletion solver, actual
flux/depletion results would need to be provided by a physics plugin before actually using
ARMI to do fuel management. Thus, this example applies a dummy burnup distribution for
demonstration purposes.

"""
# Tell the gallery to feature the 2nd image
# sphinx_gallery_thumbnail_number = 2
import math

import matplotlib.pyplot as plt

from armi.utils import directoryChangers
from armi.tests import TEST_ROOT
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.reactor import geometry
from armi.physics.fuelCycle import fuelHandlers

from armi.utils import plotting

import armi

armi.configure()

o, reactor = test_reactors.loadTestReactor(inputFileName="refTestCartesian.yaml")

# Apply a dummy burnup distribution roughly in a cosine
for b in reactor.core.getBlocks(Flags.FUEL):
    x, y, z = b.spatialLocator.getGlobalCoordinates()
    d = math.sqrt(x ** 2 + y ** 2)
    b.p.percentBu = 5 * math.cos(d * math.pi / 2 / 90)

# show the initial burnup distribution
plotting.plotFaceMap(reactor.core, param="percentBu")

# swap fuel assemblies
fuelHandler = fuelHandlers.FuelHandler(o)
exclusions = []
for num in range(12):
    # find the 12 highest burnup fuel assemblies...
    high = fuelHandler.findAssembly(
        param="percentBu", compareTo=100, exclusions=exclusions, blockLevelMax=True
    )
    # and the 12 lowest burnup assemblies...
    low = fuelHandler.findAssembly(
        param="percentBu", compareTo=0, exclusions=exclusions, blockLevelMax=True
    )
    # and swap them!
    fuelHandler.swapAssemblies(high, low)
    exclusions.extend([high, low])

# also swap out some slightly lower burnup ones
for num in range(8):
    high = fuelHandler.findAssembly(
        param="percentBu", compareTo=4.0, exclusions=exclusions, blockLevelMax=True
    )
    low = fuelHandler.findAssembly(
        param="percentBu", compareTo=0, exclusions=exclusions, blockLevelMax=True
    )
    fuelHandler.swapAssemblies(high, low)
    exclusions.extend([high, low])

# show final burnup distribution
plotting.plotFaceMap(reactor.core, param="percentBu")
