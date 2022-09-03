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
Magnesium Oxide
"""
from armi.utils.units import getTc, getTk
from armi.materials.material import Material


class MgO(Material):
    r"""MagnesiumOxide"""
    name = "MgO"
    propertyValidTemperature = {
        "density": ((273, 1273), "K"),
        "linear expansion percent": ((273.15, 1273.15), "K"),
    }

    def __init__(self):
        Material.__init__(self)
        """same reference as linear expansion. Table II.
        Reference density is from Wolfram Alpha At STP (273 K)"""

        self.p.refDens = 3.58

    def setDefaultMassFracs(self):
        r"""mass fractions"""
        self.setMassFrac("MG", 0.603035897)
        self.setMassFrac("O16", 0.396964103)

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """THE COEFFICIENT OF EXPANSION OF MAGNESIUM OXIDE
        Milo A. Durand

        Journal of Applied Physics 7, 297 (1936); doi: 10.1063/1.174539

        This is based on a 3rd order polynomial fit of the data in Table I.
        """
        Tc = getTc(Tc, Tk)
        Tk = getTk(Tc=Tc)
        self.checkPropertyTempRange("linear expansion percent", Tk)
        return 1.0489e-5 * Tc + 6.0458e-9 * Tc ** 2 - 2.6875e-12 * Tc ** 3
