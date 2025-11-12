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

"""Cesium.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

from armi.materials.material import Fluid
from armi.utils.units import getTk


class Cs(Fluid):
    """Cesium."""

    def setDefaultMassFracs(self):
        self.setMassFrac("CS133", 1.0)

    def pseudoDensity(self, Tk=None, Tc=None):
        """The 2D/3D density of liquid Cesium.

        https://en.wikipedia.org/wiki/Caesium

        Notes
        -----
        In ARMI, we define pseudoDensity() and density() as the same for Fluids.
        """
        Tk = getTk(Tc, Tk)
        if Tk < self.meltingPoint():
            return 1.93  # g/cm3
        else:
            return 1.843  # g/cm3

    def meltingPoint(self):
        return 301.7  # K
