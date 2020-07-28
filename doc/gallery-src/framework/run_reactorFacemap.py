"""
Plot a reactor facemap
======================

Load a test reactor from the test suite and plot a dummy
power distribution from it. You can plot any 
"""
from armi.reactor.tests import test_reactors
from armi.utils import plotting

operator, reactor = test_reactors.loadTestReactor()
# set dummy power
for b in reactor.core.getBlocks():
    x, y, z = b.spatialLocator.getGlobalCoordinates()
    b.p.pdens = x ** 2 + y ** 2 + z ** 2
plotting.plotFaceMap(
    reactor.core, param="pdens",
)
