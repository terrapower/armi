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
Plot a reactor facemap.
=======================

Load a test reactor from the test suite and plot a dummy
power distribution from it. You can plot any block parameter.
"""
from armi import configure
from armi.reactor.tests import test_reactors
from armi.utils import plotting

# configure ARMI
configure(permissive=True)

operator, reactor = test_reactors.loadTestReactor()
reactor.core.growToFullCore(None)
# set dummy power
for b in reactor.core.getBlocks():
    x, y, z = b.spatialLocator.getGlobalCoordinates()
    b.p.pdens = x**2 + y**2 + z**2

plotting.plotFaceMap(reactor.core, param="pdens", labelFmt="{0:.1e}")
