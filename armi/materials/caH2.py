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
Calcium Hydride.
"""

from armi.materials.material import SimpleSolid


class CaH2(SimpleSolid):
    """CalciumHydride"""

    name = "CaH2"

    def setDefaultMassFracs(self):
        """Default mass fractions.

        http://atom.kaeri.re.kr/ton/
        iso atomic percent abundance and atomic mass of 20-calcium
        | 20-Ca-40     96.941%    39.9625912
        | 20-Ca-42      0.647%    41.9586183
        | 20-Ca-43      0.135%    42.9587668
        | 20-Ca-44      2.086%    43.9554811
        | 20-Ca-46      0.004%    45.9536928
        | 20-Ca-48      0.187%    47.9525335

        atomic weight of H2                  2.01565
        weight of CaH2                      42.09367285

        | weight% of Ca-40 in CaH2            0.920331558
        | weight% of Ca-42 in CaH2            0.006449241
        | weight% of Ca-43 in CaH2            0.001377745
        | weight% of Ca-44 in CaH2            0.02178264
        | weight% of Ca-46 in CaH2            4.3668E-05
        | weight% of Ca-48 in CaH2            0.002130278
        | weight% of H2 in CaH2               0.047884869
        """
        self.setMassFrac("CA", 0.952115131)
        self.setMassFrac("H", 0.047884869)

    def density(self, Tk=None, Tc=None):
        """Mass density

        http://en.wikipedia.org/wiki/Calcium_hydride

        Returns
        -------
        density : float
            grams / cc
        """
        return 1.70
