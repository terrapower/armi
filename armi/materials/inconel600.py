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

"""Inconel600.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

import numpy as np

from armi.materials.material import Material
from armi.utils.units import getTc


class Inconel600(Material):
    propertyValidTemperature = {
        "heat capacity": ((20, 900), "C"),
        "linear expansion": ((21.0, 900.0), "C"),
        "linear expansion percent": ((21.0, 900.0), "C"),
        "thermal conductivity": ((20.0, 800.0), "C"),
    }
    references = {
        "mass fractions": "http://www.specialmetals.com/documents/Inconel%20alloy%20600.pdf",
        "density": "http://www.specialmetals.com/documents/Inconel%20alloy%20600.pdf",
        "thermalConductivity": "http://www.specialmetals.com/documents/Inconel%20alloy%20600.pdf",
        "specific heat": "http://www.specialmetals.com/documents/Inconel%20alloy%20600.pdf",
        "linear expansion percent": "http://www.specialmetals.com/documents/Inconel%20alloy%20600.pdf",
        "linear expansion": "http://www.specialmetals.com/documents/Inconel%20alloy%20600.pdf",
    }
    refTempK = 294.15

    def __init__(self):
        Material.__init__(self)
        self.refDens = 8.47  # g/cc
        # Only density measurement presented in the reference. Presumed to be performed at 21C since
        # this was the reference temperature for linear expansion measurements.

    def setDefaultMassFracs(self):
        massFracs = {
            "NI": 0.7541,
            "CR": 0.1550,
            "FE": 0.0800,
            "C": 0.0008,
            "MN55": 0.0050,
            "S": 0.0001,
            "SI": 0.0025,
            "CU": 0.0025,
        }
        for element, massFrac in massFracs.items():
            self.setMassFrac(element, massFrac)

    def polyfitThermalConductivity(self, power=2):
        r"""
        Calculates the coefficients of a polynomial fit for thermalConductivity.
        Based on data from http://www.specialmetals.com/documents/Inconel%20alloy%20600.pdf
        Fits a polynomial to the data set and returns the coefficients.

        Parameters
        ----------
        power : int, optional
            power of the polynomial fit equation

        Returns
        -------
        list of length 'power' containing the polynomial fit coefficients for thermal conductivity.
        """
        Tc = [20.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]
        k = [14.9, 15.9, 17.3, 19.0, 20.5, 22.1, 23.9, 25.7, 27.5]
        return np.polyfit(np.array(Tc), np.array(k), power).tolist()

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""
        Returns the thermal conductivity of Inconel600.

        Parameters
        ----------
        Tk : float, optional
            temperature in (K)
        Tc : float, optional
            Temperature in (C)

        Returns
        -------
        thermalCond : float
            thermal conductivity in W/m/C
        """
        Tc = getTc(Tc, Tk)
        self.checkPropertyTempRange("thermal conductivity", Tc)
        thermalCond = 3.4938e-6 * Tc**2 + 1.3403e-2 * Tc + 14.572
        return thermalCond  # W/m-C

    def polyfitHeatCapacity(self, power=2):
        r"""
        Calculates the coefficients of a polynomial fit for heatCapacity.
        Based on data from http://www.specialmetals.com/documents/Inconel%20alloy%20600.pdf
        Fits a polynomial to the data set and returns the coefficients.

        Parameters
        ----------
        power : int, optional
            power of the polynomial fit equation

        Returns
        -------
        list of length 'power' containing the polynomial fit coefficients for heat capacity.
        """
        Tc = [20.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0]
        cp = [444.0, 465.0, 486.0, 502.0, 519.0, 536.0, 578.0, 595.0, 611.0, 628.0]
        return np.polyfit(np.array(Tc), np.array(cp), power).tolist()

    def heatCapacity(self, Tk=None, Tc=None):
        r"""
        Returns the specific heat capacity of Inconel600.

        Parameters
        ----------
        Tk : float, optional
            Temperature in Kelvin.
        Tc : float, optional
            Temperature in degrees Celsius.

        Returns
        -------
        heatCapacity : float
            heat capacity in J/kg/C
        """
        Tc = getTc(Tc, Tk)
        self.checkPropertyTempRange("heat capacity", Tc)
        heatCapacity = 7.4021e-6 * Tc**2 + 0.20573 * Tc + 441.3
        return heatCapacity  # J/kg-C

    def polyfitLinearExpansionPercent(self, power=2):
        r"""
        Calculates the coefficients of a polynomial fit for linearExpansionPercent.
        Based on data from http://www.specialmetals.com/documents/Inconel%20alloy%20600.pdf.

        Uses mean CTE values to find percent thermal strain values. Fits a polynomial
        to the data set and returns the coefficients.

        Parameters
        ----------
        power : int, optional
            power of the polynomial fit equation

        Returns
        -------
        list of length 'power' containing the polynomial fit coefficients for linearExpansionPercent
        """
        refTempC = getTc(None, Tk=self.refTempK)
        Tc = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0]
        alpha_mean = [
            1.33e-05,
            1.38e-05,
            1.42e-05,
            1.45e-05,
            1.49e-05,
            1.53e-05,
            1.58e-05,
            1.61e-05,
            1.64e-05,
        ]

        linExpPercent = [0.0]
        for i, alpha in enumerate(alpha_mean):
            linExpPercentVal = 100.0 * alpha * (Tc[i] - refTempC)
            linExpPercent.append(linExpPercentVal)

        Tc.insert(0, refTempC)

        return np.polyfit(np.array(Tc), np.array(linExpPercent), power).tolist()

    def linearExpansionPercent(self, Tk=None, Tc=None):
        r"""
        Returns percent linear expansion of Inconel600.

        Parameters
        ----------
        Tk : float
            temperature in (K)
        Tc : float
            Temperature in (C)

        Returns
        -------
        linExpPercent in %-m/m/C
        """
        Tc = getTc(Tc, Tk)
        self.checkPropertyTempRange("linear expansion percent", Tc)
        linExpPercent = 3.722e-7 * Tc**2 + 1.303e-3 * Tc - 2.863e-2
        return linExpPercent

    def linearExpansion(self, Tk=None, Tc=None):
        r"""
        From http://www.specialmetals.com/documents/Inconel%20alloy%20600.pdf.

        Using the correlation for linearExpansionPercent, the 2nd order polynomial is divided by 100
        to convert from percent strain to strain, then differentiated with respect to temperature to
        find the correlation for instantaneous linear expansion.

        i.e. for a linearExpansionPercent correlation of a*Tc**2 + b*Tc + c, the linearExpansion
        correlation is 2*a/100*Tc + b/100

        2*(3.722e-7/100.0)*Tc + 1.303e-3/100.0

        Parameters
        ----------
        Tk : float
            temperature in (K)
        Tc : float
            Temperature in (C)

        Returns
        -------
        linExp in m/m/C
        """
        Tc = getTc(Tc, Tk)
        self.checkPropertyTempRange("linear expansion", Tc)
        linExp = 7.444e-9 * Tc + 1.303e-5
        return linExp
