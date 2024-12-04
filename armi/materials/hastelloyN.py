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

"""Hastelloy-N is a high-nickel structural material invented by ORNL for handling molten fluoride salts."""

from armi.materials.material import Material
from armi.utils.units import getTc, getTk


class HastelloyN(Material):
    r"""
    Hastelloy N alloy (UNS N10003).

    .. [Haynes] Haynes International, H-2052D 2020
        (http://haynesintl.com/docs/default-source/pdfs/new-alloy-brochures/corrosion-resistant-alloys/brochures/n-brochure.pdf)

    .. [SAB] Sabharwall, et. al.
        Feasibility Study of Secondary Heat Exchanger Concepts for the Advanced High Temperature Reactor
        INL/EXT-11-23076, 2011

    """

    materialIntro = (
        "Hastelloy N alloy is a nickel-base alloy that was invented at Oak RIdge National Laboratories "
        "as a container material for molten fluoride salts. It has good oxidation resistance to hot fluoride "
        "salts in the temperature range of 704 to 871C (1300 to 1600F)"
    )

    propertyValidTemperature = {
        "thermal conductivity": ((473.15, 973.15), "K"),
        "heat capacity": ((373.15, 973.15), "K"),
        "thermal expansion": ((293.15, 1173.15), "K"),
    }

    refTempK = 293.15

    def setDefaultMassFracs(self):
        """
        Hastelloy N mass fractions.

        From [Haynes]_.
        """
        self.setMassFrac("CR", 0.07)
        self.setMassFrac("MO", 0.16)
        self.setMassFrac("FE", 0.04)  # max.
        self.setMassFrac("SI", 0.01)  # max.
        self.setMassFrac("MN", 0.0080)  # max.
        self.setMassFrac("V", 0.0005)  # max.
        self.setMassFrac("C", 0.0006)
        self.setMassFrac("CO", 0.0020)  # max.
        self.setMassFrac("CU", 0.0035)  # max.
        self.setMassFrac("W", 0.005)  # max.
        self.setMassFrac("AL", 0.0025)  # max.
        self.setMassFrac("TI", 0.0025)  # max.
        self.setMassFrac("NI", 1.0 - sum(self.massFrac.values()))  # balance

        self.refDens = 8.86

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""
        Calculates the thermal conductivity of Hastelloy N.
        Second order polynomial fit to data from [Haynes]_.

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
        Tc = getTc(Tc, Tk)
        Tk = getTk(Tc=Tc)
        self.checkPropertyTempRange("thermal conductivity", Tk)
        return 1.92857e-05 * Tc**2 + 3.12857e-03 * Tc + 1.17743e01  # W/m-K

    def heatCapacity(self, Tk=None, Tc=None):
        r"""
        Calculates the specific heat capacity of Hastelloy N.
        Sixth order polynomial fit to data from Table 2-20 [SAB]_ (R^2=0.97).

        Parameters
        ----------
        Tk : float
            Temperature in (K)

        Tc : float
            Temperature in (C)

        Returns
        -------
        Hastelloy N specific heat capacity (J/kg-C)
        """
        Tc = getTc(Tc, Tk)
        Tk = getTk(Tc=Tc)
        self.checkPropertyTempRange("heat capacity", Tk)
        return (
            +3.19981e02
            + 2.47421e00 * Tc
            - 2.49306e-02 * Tc**2
            + 1.32517e-04 * Tc**3
            - 3.58872e-07 * Tc**4
            + 4.69003e-10 * Tc**5
            - 2.32692e-13 * Tc**6
        )

    def linearExpansionPercent(self, Tk=None, Tc=None):
        r"""
        average thermal expansion dL/L. Used for computing hot dimensions.

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
        r"""
        Mean coefficient of thermal expansion for Hastelloy N.
        Second order polynomial fit of data from [Haynes]_.

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
        Tk = getTk(Tc=Tc)
        self.checkPropertyTempRange("thermal expansion", Tk)
        return 2.60282e-12 * Tc**2 + 7.69859e-10 * Tc + 1.21036e-05
