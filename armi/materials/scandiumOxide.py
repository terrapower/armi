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

"""Scandium Oxide.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

from armi.materials.material import Material
from armi.utils.units import getTk


class Sc2O3(Material):
    propertyValidTemperature = {"linear expansion percent": ((273.15, 1573.15), "K")}

    def __init__(self):
        Material.__init__(self)
        """
        https://en.wikipedia.org/wiki/Scandium_oxide
        """
        self.refDens = 3.86

    def setDefaultMassFracs(self):
        self.setMassFrac("SC45", 0.6520)
        self.setMassFrac("O16", 0.3480)

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """
        Return the linear expansion percent for Scandium Oxide (Scandia).

        Notes
        -----
        From Table 4 of "Thermal Expansion and Phase Inversion of Rare-Earth Oxides.
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion percent", Tk)
        return 2.6045e-07 * Tk**2 + 4.6374e-04 * Tk - 1.4696e-01
