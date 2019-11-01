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

from armi.utils.units import getTk
from armi.materials.material import Material


class Be9(Material):
    name = "Be-9"

    def setDefaultMassFracs(self):
        self.setMassFrac("BE9", 1.0)

    def linearExpansion(self, Tk=None, Tc=None):
        r"""
        Finds the linear expansion coefficient of Be9. given T in C
        returns m/m-K
        Based on Austenitic SS http://www-ferp.ucsd.edu/LIB/PROPS/PANOS/ss.html
        which is in turn based on Fusion Engineering and Design . FEDEEE 5(2), 141-234 (1987)
        Valid up to 1000K
        """
        Tk = getTk(Tc, Tk)
        self.checkTempRange(50, 1560.0, Tk, "linear expansion")

        return 1e-6 * 11.4

    def density(self, Tk=None, Tc=None):
        Tk = getTk(Tc, Tk)
        return 1.85 / (1.0 + self.volumetricExpansion(Tk=Tk) * (Tk - 295.0))  # g/cc
