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

"""Incoloy 800.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

from armi.materials.material import Material
from armi.utils.units import getTc


class Inconel800(Material):
    r"""
    Incoloy 800/800H (UNS N08800/N08810).

    .. [SM] Special Metals - Incoloy alloy 800
        (https://www.specialmetals.com/assets/smc/documents/alloys/incoloy/incoloy-alloy-800.pdf)
    """

    propertyValidTemperature = {"thermal expansion": ((20.0, 800.0), "C")}
    refTempK = 294.15

    def setDefaultMassFracs(self):
        """
        Incoloy 800H mass fractions.

        From [SM]_.
        """
        self.setMassFrac("NI", 0.325)  # ave.
        self.setMassFrac("CR", 0.21)  # ave.
        self.setMassFrac("C", 0.00075)  # ave. 800H
        self.setMassFrac("MN", 0.015)  # max.
        self.setMassFrac("S", 0.00015)  # max.
        self.setMassFrac("SI", 0.01)  # max.
        self.setMassFrac("CU", 0.0075)  # max.
        self.setMassFrac("AL", 0.00375)  # ave.
        self.setMassFrac("TI", 0.00375)  # ave.
        self.setMassFrac("FE", 1.0 - sum(self.massFrac.values()))  # balance, 0.395 min.

        self.refDens = 7.94

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """
        Average thermal expansion dL/L. Used for computing hot dimensions.

        Parameters
        ----------
        Tk : float
            temperature in (K)
        Tc : float
            Temperature in (C)

        Returns
        -------
        %dLL(T) in m/m/K
        """
        Tc = getTc(Tc, Tk)
        refTempC = getTc(Tk=self.refTempK)
        return 100.0 * self.meanCoefficientThermalExpansion(Tc=Tc) * (Tc - refTempC)

    def meanCoefficientThermalExpansion(self, Tk=None, Tc=None):
        """
        Mean coefficient of thermal expansion for Incoloy 800.
        Third order polynomial fit of table 5 from [SM]_.

        Parameters
        ----------
        Tk : float
            temperature in (K)
        Tc : float
            Temperature in (C)

        Returns
        -------
        mean coefficient of thermal expansion in m/m/C
        """
        Tc = getTc(Tc, Tk)
        self.checkPropertyTempRange("thermal expansion", Tc)
        return 2.52525e-14 * Tc**3 - 3.77814e-11 * Tc**2 + 2.06360e-08 * Tc + 1.28071e-05
