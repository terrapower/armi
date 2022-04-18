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
Hex reactor to RZ geometry conversion
=====================================
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
from armi import configure, runLog

# configure ARMI
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
