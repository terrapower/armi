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
Beryllium is a lightweight metal with lots of interesting nuclear use-cases.

It has a nice (n,2n) reaction and is an inhalation hazard.
"""

from armi.materials.material import Material
from armi.nucDirectory import thermalScattering as tsl
from armi.utils.units import getTk


class Be9(Material):
    """Beryllium."""

    thermalScatteringLaws = (tsl.fromNameAndCompound("BE", tsl.BE_METAL),)
    propertyValidTemperature = {"linear expansion percent": ((50, 1560.0), "K")}

    def setDefaultMassFracs(self):
        self.setMassFrac("BE9", 1.0)
        self.refDens = 1.85

    def linearExpansionPercent(self, Tk=None, Tc=None):
        r"""
        Finds the linear expansion coefficient of Be9. given T in C
        returns m/m-K
        Based on http://www-ferp.ucsd.edu/LIB/PROPS/PANOS/be.html
        which is in turn based on Fusion Engineering and Design . FEDEEE 5(2), 141-234 (1987).
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion percent", Tk)
        return 1e-4 * (8.4305 + 1.1464e-2 * Tk - 2.9752e-6 * Tk**2)
