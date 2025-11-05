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

"""Yttrium Oxide.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

from armi.materials.material import Material
from armi.utils.units import getTk


class Y2O3(Material):
    propertyValidTemperature = {"linear expansion percent": ((273.15, 1573.15), "K")}

    def __init__(self):
        Material.__init__(self)
        self.refDens = 5.03

    def setDefaultMassFracs(self):
        self.setMassFrac("Y89", 0.7875)
        self.setMassFrac("O16", 0.2125)

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """
        Return the linear expansion percent for Yttrium Oxide (Yttria).

        Notes
        -----
        From Table 5 of "Thermal Expansion and Phase Inversion of Rare-Earth Oxides.
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion percent", Tk)

        return 1.4922e-07 * Tk**2 + 6.2448e-04 * Tk - 1.8414e-01
