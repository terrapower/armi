"""
Hex reactor to RZ geometry conversion
===================================
This shows how an entire reactor specified in full hex detail can be
automatically converted to an equivalent 2-D or 3-D RZ case.

"""
# sphinx_gallery_thumbnail_number=2
import math

import matplotlib.pyplot as plt

from armi.reactor.tests import test_reactors
from armi.reactor.flags import Flags
from armi.reactor.converters import geometryConverters
from armi.utils import plotting
import armi

armi.configure()

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

converter = geometryConverters.HexToRZConverter(
    o.cs, converterSettings
)
converter.convert(r)
figs = converter.plotConvertedReactor()

plt.show()
