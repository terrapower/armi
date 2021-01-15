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

# cython: profile=False
"""
Thorium Oxide solid ceramic.

Data is from [#IAEA-TECDOCT-1450]_.

.. [#IAEA-TECDOCT-1450] Thorium fuel cycle -- Potential benefits and challenges, IAEA-TECDOC-1450 (2005).
    https://www-pub.iaea.org/mtcd/publications/pdf/te_1450_web.pdf
"""

from armi.utils.units import getTk
from armi.materials.material import Material


class ThoriumOxide(Material):
    name = "ThO2"

    def setDefaultMassFracs(self):
        r"""ThO2 mass fractions. Using Pure Th-232. 100% 232
        Thorium: 232.030806 g/mol
        Oxygen:  15.9994 g/mol

        2 moles of oxygen/1 mole of Thorium

        grams of Th-232 = 232.030806 g/mol* 1 mol  =  232.030806 g
        grams of Oxygen = 15.9994 g/mol* 2 mol = 31.9988 g
        total=264.029606 g.
        Mass fractions are computed from this."""
        self.setMassFrac("TH232", 0.8788)
        self.setMassFrac("O16", 0.1212)

    def density(self, Tk=None, Tc=None):
        Tk = getTk(Tc, Tk)
        """g/cc from IAEA TE 1450"""
        return 10.00

    def linearExpansion(self, Tk=None, Tc=None):
        r"""m/m/K from IAEA TE 1450"""
        Tk = getTk(Tc, Tk)
        self.checkTempRange(298, 1223, Tk, "linear expansionn")
        return 9.67e-6

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""W/m-K from IAEA TE 1450"""
        Tk = getTk(Tc, Tk)
        return 6.20

    def meltingPoint(self):
        r"""melting point in K from IAEA TE 1450"""
        return 3643.0
