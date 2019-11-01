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
Hastelloy-N is a high-nickel structural material invented by ORNL for handling molten fluoride salts.
"""

from armi.utils.units import getTk
from armi.materials.material import Material


class HastelloyN(Material):
    name = "HastelloyN"
    type = "Structural"

    materialIntro = (
        "Hastelloy N alloy is a nickel-base alloy that was invented at Oak RIdge National Laboratories "
        "as a container material for molten fluoride salts. It has good oxidation resistance to hot fluoride "
        "salts in the temperature range of 704 to 871C (1300 to 1600F)"
    )

    # Dictionary of valid temperatures (in C) over which the property models are valid in the format
    # 'Property_Name': ((Temperature_Lower_Limit, Temperature_Upper_Limit), Temperature_Units)
    propertyValidTemperature = {  #'yield strength': ((0, 800), 'C'),
        "thermal conductivity": ((373.15, 973.15), "K"),
        "heat capacity": ((373.15, 973.15), "K"),
    }

    def setDefaultMassFracs(self):
        # from Haynes Internations (http://www.haynesintl.com/pdf/h2052.pdf)
        self.setMassFrac("NI", 0.71)
        self.setMassFrac("CR", 0.07)
        self.setMassFrac("MO", 0.16)
        self.setMassFrac("FE", 0.05)
        self.setMassFrac("SI", 0.01)
        self.setMassFrac("MN55", 0.0080)
        self.setMassFrac("C", 0.0008)
        self.setMassFrac("CO59", 0.0020)
        self.setMassFrac("CU", 0.0035)
        self.setMassFrac("W182", 0.00131143377)
        self.setMassFrac("W183", 0.0007120653)
        self.setMassFrac("W184", 0.00153297716)
        self.setMassFrac("W186", 0.00143786762)
        self.setMassFrac("AL27", 0.00175)
        self.setMassFrac("TI", 0.00175)

        self.p.refTempK = 273.15 + 22
        self.p.refDens = 8.86

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""
        Calculates the thermal conductivity of Hastelloy N

        Parameters
        ----------
        Tk : float
            Temperature in (K)

        Tc : float
            Temperature in (C)

        Returns
        -------
        Hastelloy N thermal conductivity (W/m-K)

        """
        Tk = getTk(Tc, Tk)
        (TLowerLimit, TUpperLimit) = self.propertyValidTemperature[
            "thermal conductivity"
        ][0]
        # 100 - 700
        self.checkTempRange(TLowerLimit, TUpperLimit, Tk, "thermal conductivity")
        thermalConductivity = (
            -3.81441015e01
            + 3.97910693e-01 * Tk
            - 1.29474249e-03 * Tk ** 2
            + 2.13159780e-06 * Tk ** 3
            - 1.71326610e-09 * Tk ** 4
            + 5.41666667e-13 * Tk ** 5
        )
        return thermalConductivity  # W/m-K

    def heatCapacity(self, Tk=None, Tc=None):
        r"""
        Calculates the specific heat capacity of Hastelloy N.

        Parameters
        ----------
        Tk : float
            Temperature in (K)

        Tc : float
            Temperature in (C)

        Returns
        -------
        SS316 specific heat capacity (J/kg-K)

        """
        Tk = getTk(Tc, Tk)
        (TLowerLimit, TUpperLimit) = self.propertyValidTemperature["heat capacity"][0]
        self.checkTempRange(TLowerLimit, TUpperLimit, Tk, "heat capacity")
        return (
            -1.62743324e03
            + 2.96283219e01 * Tk
            - 1.64632142e-01 * Tk ** 2
            + 4.54953485e-04 * Tk ** 3
            - 6.64662604e-07 * Tk ** 4
            + 4.90884449e-10 * Tk ** 5
            - 1.44036064e-13 * Tk ** 6
        )
