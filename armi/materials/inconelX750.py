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

"""Inconel X750."""

import numpy as np

from armi.materials.material import Material
from armi.utils.units import getTc


class InconelX750(Material):
    propertyValidTemperature = {
        "heat capacity": ((-18.0, 1093.0), "C"),
        "linear expansion": ((21.1, 982.2), "C"),
        "linear expansion percent": ((21.1, 982.2), "C"),
        "thermal conductivity": ((-156.7, 871.1), "C"),
    }
    references = {
        "mass fractions": "http://www.specialmetals.com/documents/Inconel%20alloy%20X-750.pdf",
        "density": "http://www.specialmetals.com/documents/Inconel%20alloy%20X-750.pdf",
        "thermalConductivity": "http://www.specialmetals.com/documents/Inconel%20alloy%20X-750.pdf",
        "specific heat": "http://www.specialmetals.com/documents/Inconel%20alloy%20X-750.pdf",
        "linearExpansionPercent": "http://www.specialmetals.com/documents/Inconel%20alloy%20X-750.pdf",
        "linearExpansion": "http://www.specialmetals.com/documents/Inconel%20alloy%20X-750.pdf",
    }
    refTempK = 294.15

    def __init__(self):
        Material.__init__(self)
        self.refDens = 8.28  # g/cc
        # Only density measurement presented in the reference.
        # Presumed to be performed at 21C since this was the reference temperature for linear
        # expansion measurements.

    def setDefaultMassFracs(self):
        massFracs = {
            "NI": 0.7180,
            "CR": 0.1550,
            "FE": 0.0700,
            "TI": 0.0250,
            "AL27": 0.0070,
            "NB93": 0.0095,
            "MN55": 0.0050,
            "SI": 0.0025,
            "S": 0.0001,
            "CU": 0.0025,
            "C": 0.0004,
            "CO59": 0.0050,
        }
        for element, massFrac in massFracs.items():
            self.setMassFrac(element, massFrac)

    def polyfitThermalConductivity(self, power=2):
        r"""
        Calculates the coefficients of a polynomial fit for thermalConductivity. Based on data from
        https://web.archive.org/web/20170215105917/http://www.specialmetals.com:80/documents/Inconel%20alloy%20X-750.pdf
        Fits a polynomial to the data set and returns the coefficients.

        Parameters
        ----------
        power : int, optional
            power of the polynomial fit equation

        Returns
        -------
        list of length 'power' containing the polynomial fit coefficients for thermal conductivity.
        """
        Tc = [
            -156.7,
            -128.9,
            -73.3,
            21.1,
            93.3,
            204.4,
            315.6,
            426.7,
            537.8,
            648.9,
            760.0,
            871.1,
        ]
        k = [
            9.66,
            10.10,
            10.67,
            11.97,
            12.84,
            14.13,
            15.72,
            17.31,
            18.89,
            20.62,
            22.21,
            23.65,
        ]
        return np.polyfit(np.array(Tc), np.array(k), power).tolist()

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""
        Returns the thermal conductivity of InconelX750.

        Parameters
        ----------
        Tk : float, optional
            Temperature in Kelvin.
        Tc : float, optional
            Temperature in degrees Celsius.

        Returns
        -------
        thermalCond : float
            thermal conductivity in W/m/C
        """
        Tc = getTc(Tc, Tk)
        self.checkPropertyTempRange("thermal conductivity", Tc)
        thermalCond = 1.4835e-6 * Tc**2 + 1.2668e-2 * Tc + 11.632
        return thermalCond  # W/m-C

    def polyfitHeatCapacity(self, power=3):
        r"""
        Calculates the coefficients of a polynomial fit for heatCapacity.
        Based on data from http://www.specialmetals.com/documents/Inconel%20alloy%20X-750.pdf
        Fits a polynomial to the data set and returns the coefficients.

        Parameters
        ----------
        power : int, optional
            power of the polynomial fit equation

        Returns
        -------
        list of length 'power' containing the polynomial fit coefficients for heat capacity.
        """
        Tc = [21.1, 93.3, 204.4, 315.6, 426.7, 537.8, 648.9, 760.0, 871.1]
        cp = [431.2, 456.4, 485.7, 502.4, 523.4, 544.3, 573.6, 632.2, 715.9]
        return np.polyfit(np.array(Tc), np.array(cp), power).tolist()

    def heatCapacity(self, Tk=None, Tc=None):
        r"""
        Returns the specific heat capacity of InconelX750.

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
        heatCapacity = 9.2261e-7 * Tc**3 - 9.6368e-4 * Tc**2 + 4.7778e-1 * Tc + 420.55
        return heatCapacity  # J/kg-C

    def polyfitLinearExpansionPercent(self, power=2):
        r"""
        Calculates the coefficients of a polynomial fit for linearExpansionPercent.
        Based on data from http://www.specialmetals.com/documents/Inconel%20alloy%20X-750.pdf.

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
        Tc = [93.3, 204.4, 315.6, 426.7, 537.8, 648.9, 760.0, 871.1, 982.2]
        alpha_mean = [
            1.260e-05,
            1.296e-05,
            1.350e-05,
            1.404e-05,
            1.458e-05,
            1.512e-05,
            1.584e-05,
            1.674e-05,
            1.764e-05,
        ]

        linExpPercent = [0.0]
        for i, alpha in enumerate(alpha_mean):
            linExpPercentVal = 100.0 * alpha * (Tc[i] - refTempC)
            linExpPercent.append(linExpPercentVal)

        Tc.insert(0, refTempC)

        return np.polyfit(np.array(Tc), np.array(linExpPercent), power).tolist()

    def linearExpansionPercent(self, Tk=None, Tc=None):
        r"""
        Returns percent linear expansion of InconelX750.

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
        linExpPercent = 6.8378e-7 * Tc**2 + 1.056e-3 * Tc - 1.3161e-2
        return linExpPercent

    def linearExpansion(self, Tk=None, Tc=None):
        r"""
        From http://www.specialmetals.com/documents/Inconel%20alloy%20X-750.pdf.

        Using the correlation for linearExpansionPercent, the 2nd order polynomial is divided by 100
        to convert from percent strain to strain, then differentiated with respect to temperature to
        find the correlation for instantaneous linear expansion.

        i.e. for a linearExpansionPercent correlation of a*Tc**2 + b*Tc + c, the linearExpansion
        correlation is 2*a/100*Tc + b/100

        2*(6.8378e-7/100.0)*Tc + 1.056e-3/100.0

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
        linExp = 1.36756e-8 * Tc + 1.056e-5
        return linExp
