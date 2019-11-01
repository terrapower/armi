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

"""Yttrium Oxide"""

from armi.utils.units import getTk
from armi.materials.material import Material


class Y2O3(Material):
    name = "Y2O3"

    def setDefaultMassFracs(self):
        self.setMassFrac("Y89", 0.7875)
        self.setMassFrac("O16", 0.2125)

    def density(self, Tk=None, Tc=None):
        return 5.03

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """
        Return the linear expansion percent for Yttrium Oxide (Yttria).

        Notes
        -----
        From Table 5 of "Thermal Expansion and Phase Inversion of Rare-Earth Oxides.
        """
        Tk = getTk(Tc, Tk)
        self.checkTempRange(273.15, 1573.15, Tk, "linear expansion percent")
        return 1.4922e-07 * Tk ** 2 + 6.2448e-04 * Tk - 1.8414e-01
