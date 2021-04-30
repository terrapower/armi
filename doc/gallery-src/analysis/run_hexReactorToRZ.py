"""
Hex reactor to RZ geometry conversion
===================================
This shows how an entire reactor specified in full hex detail can be
automatically converted to a 2-D or 3-D RZ case with conserved mass.

.. warning:: 
    This uses :py:mod:`armi.reactor.converters.geometryConverters`, which
    will only work on a constrained set of hex-based geometries. For your systems,
    consider these an example and starting point and build your own converters as
    appropriate.


"""
# sphinx_gallery_thumbnail_number=2
import math

import matplotlib.pyplot as plt

from armi.reactor.tests import test_reactors
from armi.reactor.flags import Flags
from armi.reactor.converters import geometryConverters
from armi.utils import plotting
from armi import configure

configure(permissive=True)

o, r = test_reactors.loadTestReactor()
kgFis = [a.getHMMass() for a in r.core]
plotting.plotFaceMap(r.core, data=kgFis, labelFmt="{:.1e}")

converterSettings = {
    "radialConversionType": "Ring Compositions",
    "axialConversionType": "Axial Coordinates",
    "uniformThetaMesh": True,
    "thetaBins": 1,
    "axialMesh": [50, 100, 150, 175],
    "thetaMesh": [2 * math.pi],
}

converter = geometryConverters.HexToRZConverter(o.cs, converterSettings)
# makes new reactor in converter.convReactor
converter.convert(r)
figs = converter.plotConvertedReactor()

plt.show()
