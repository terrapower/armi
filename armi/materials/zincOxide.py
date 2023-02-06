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

"""Zinc Oxide"""

from armi.materials.material import Material
from armi.utils.units import getTk


class ZnO(Material):
    name = "ZnO"

    propertyValidTemperature = {"linear expansion percent": ((10.12, 1491.28), "K")}

    def setDefaultMassFracs(self):
        self.setMassFrac("ZN", 0.8034)
        self.setMassFrac("O16", 0.1966)

    def density(self, Tk=None, Tc=None):
        return 5.61

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """
        Return the linear expansion percent for Polycrystalline ZnO

        Notes
        -----
        Digitized from Figure 1.24 from
        Zinc Oxide: Fundamentals, Materials and Device Technology
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion percent", Tk)

        return (
            -1.9183e-10 * Tk ** 3 + 6.5944e-07 * Tk ** 2 + 5.2992e-05 * Tk - 5.2631e-02
        )
