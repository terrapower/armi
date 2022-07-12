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
Cesium
"""

from armi.materials.material import Material
from armi.utils.units import getTk


class Cs(Material):

    name = "Cesium"

    def setDefaultMassFracs(self):
        self.setMassFrac("CS133", 1.0)

    def density(self, Tk=None, Tc=None):
        """
        https://en.wikipedia.org/wiki/Caesium
        """
        Tk = getTk(Tc, Tk)
        if Tk < self.meltingPoint():
            return 1.93  # g/cm3
        else:
            return 1.843  # g/cm3

    def meltingPoint(self):
        return 301.7  # K
