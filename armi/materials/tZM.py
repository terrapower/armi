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
TZM
"""
from numpy import interp

from armi.materials.material import Material
from armi.utils.units import getTc


class TZM(Material):
    name = "TZM"
    references = {
        "linear expansion percent": "Report on the Mechanical and Thermal Properties of Tungsten and TZM Sheet Produced \
                   in the Refractory Metal Sheet Rolling Program, Part 1 to Bureau of Naval Weapons Contract No. N600(19)-59530, \
                   Southern Research Institute"
    }

    temperatureC = [
        21.11,
        456.11,
        574.44,
        702.22,
        840.56,
        846.11,
        948.89,
        1023.89,
        1146.11,
        1287.78,
        1382.22,
    ]

    percentThermalExpansion = [
        0,
        1.60e-01,
        2.03e-01,
        2.53e-01,
        3.03e-01,
        3.03e-01,
        3.42e-01,
        3.66e-01,
        4.21e-01,
        4.68e-01,
        5.04e-01,
    ]

    def setDefaultMassFracs(self):
        self.setMassFrac("C", 2.50749e-05)
        self.setMassFrac("TI", 0.002502504)
        self.setMassFrac("ZR", 0.000761199)
        self.setMassFrac("MO", 0.996711222)

    def density(self, Tk=None, Tc=None):
        return 10.16  # g/cc

    def linearExpansionPercent(self, Tk=None, Tc=None):
        r"""
        return linear expansion in %dL/L from interpolation of tabular data.

        This function is used to expand a material from its reference temperature (21C)
        to a particular hot temperature.

        Parameters
        ----------
        Tk : float
            temperature in K
        Tc : float
            temperature in C

        Source: Report on the Mechanical and Thermal Properties of Tungsten and TZM Sheet Produced \
                in the Refractory Metal Sheet Rolling Program, Part 1 to Bureau of Naval Weapons Contract No. N600(19)-59530, 1966 \
                Southern Research Institute.

        See Table viii-b, Appendix B, page 181.
        """
        Tc = getTc(Tc, Tk)
        self.checkTempRange(21.11, 1382.22, Tc, "linear expansion percent")
        return interp(Tc, self.temperatureC, self.percentThermalExpansion)
