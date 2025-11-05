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

"""Inconel625.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

import numpy as np

from armi.materials.material import Material
from armi.utils.units import getTc


class Inconel625(Material):
    propertyValidTemperature = {
        "heat capacity": ((221.0, 1093.0), "C"),
        "linear expansion": ((21.0, 927.0), "C"),
        "linear expansion percent": ((21.0, 927.0), "C"),
        "thermal conductivity": ((21.0, 982.0), "C"),
    }
    references = {
        "mass fractions": "http://www.specialmetals.com/assets/documents/alloys/inconel/inconel-alloy-625.pdf",
        "density": "http://www.specialmetals.com/assets/documents/alloys/inconel/inconel-alloy-625.pdf",
        "linearExpansionPercent": "http://www.specialmetals.com/assets/documents/alloys/inconel/inconel-alloy-625.pdf",
        "linearExpansion": "http://www.specialmetals.com/assets/documents/alloys/inconel/inconel-alloy-625.pdf",
        "thermalConductivity": "http://www.specialmetals.com/assets/documents/alloys/inconel/inconel-alloy-625.pdf",
        "specific heat": "http://www.specialmetals.com/assets/documents/alloys/inconel/inconel-alloy-625.pdf",
    }
    refTempK = 294.15

    def __init__(self):
        Material.__init__(self)
        self.refDens = 8.44  # g/cc
        # Only density measurement presented in the reference.
        # Presumed to be performed at 21C since this was the reference temperature for linear expansion measurements.

    def setDefaultMassFracs(self):
        massFracs = {
            "NI": 0.6188,
            "CR": 0.2150,
            "FE": 0.0250,
            "MO": 0.0900,
            "TA181": 0.0365,
            "C": 0.0005,
            "MN55": 0.0025,
            "SI": 0.0025,
            "P31": 0.0001,
            "S": 0.0001,
            "AL27": 0.0020,
            "TI": 0.0020,
            "CO59": 0.0050,
        }
        for element, massFrac in massFracs.items():
            self.setMassFrac(element, massFrac)

    def polyfitThermalConductivity(self, power=2):
        r"""
        Calculates the coefficients of a polynomial fit for thermalConductivity.
        Based on data from http://www.specialmetals.com/assets/documents/alloys/inconel/inconel-alloy-625.pdf
        Fits a polynomial to the data set and returns the coefficients.

        Parameters
        ----------
        power : int, optional
            power of the polynomial fit equation

        Returns
        -------
        list of length 'power' containing the polynomial fit coefficients for thermal conductivity.
        """
        Tc = [21.0, 38.0, 93.0, 204.0, 316.0, 427.0, 538.0, 649.0, 760.0, 871.0, 982.0]
        k = [9.8, 10.1, 10.8, 12.5, 14.1, 15.7, 17.5, 19.0, 20.8, 22.8, 25.2]
        return np.polyfit(np.array(Tc), np.array(k), power).tolist()

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""
        Returns the thermal conductivity of Inconel625.

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
        thermalCond = 2.7474e-6 * Tc**2 + 0.012907 * Tc + 9.62532
        return thermalCond  # W/m-C

    def polyfitHeatCapacity(self, power=2):
        r"""
        Calculates the coefficients of a polynomial fit for heatCapacity.
        Based on data from http://www.specialmetals.com/assets/documents/alloys/inconel/inconel-alloy-625.pdf
        Fits a polynomial to the data set and returns the coefficients.

        Parameters
        ----------
        power : int, optional
            power of the polynomial fit equation

        Returns
        -------
        list of length 'power' containing the polynomial fit coefficients for heat capacity.
        """
        Tc = [
            21.0,
            93.0,
            204.0,
            316.0,
            427.0,
            538.0,
            649.0,
            760.0,
            871.0,
            982.0,
            1093.0,
        ]
        cp = [
            410.0,
            427.0,
            456.0,
            481.0,
            511.0,
            536.0,
            565.0,
            590.0,
            620.0,
            645.0,
            670.0,
        ]
        return np.polyfit(np.array(Tc), np.array(cp), power).tolist()

    def heatCapacity(self, Tk=None, Tc=None):
        """
        Returns the specific heat capacity of Inconel625.

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
        heatCapacity = -5.3777e-6 * Tc**2 + 0.25 * Tc + 404.26
        return heatCapacity  # J/kg-C

    def polyfitLinearExpansionPercent(self, power=2):
        r"""
        Calculates the coefficients of a polynomial fit for linearExpansionPercent.
        Based on data from http://www.specialmetals.com/assets/documents/alloys/inconel/inconel-alloy-625.pdf.

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
        Tc = [93.0, 204.0, 316.0, 427.0, 538.0, 649.0, 760.0, 871.0, 927.0]
        alpha_mean = [
            1.28e-05,
            1.31e-05,
            1.33e-05,
            1.37e-05,
            1.40e-05,
            1.48e-05,
            1.53e-05,
            1.58e-05,
            1.62e-05,
        ]

        linExpPercent = [0.0]
        for i, alpha in enumerate(alpha_mean):
            linExpPercentVal = 100.0 * alpha * (Tc[i] - refTempC)
            linExpPercent.append(linExpPercentVal)

        Tc.insert(0, refTempC)

        return np.polyfit(np.array(Tc), np.array(linExpPercent), power).tolist()

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """
        Returns percent linear expansion of Inconel625.

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
        linExpPercent = 5.083e-7 * Tc**2 + 1.125e-3 * Tc - 1.804e-2
        return linExpPercent

    def linearExpansion(self, Tk=None, Tc=None):
        r"""
        From http://www.specialmetals.com/assets/documents/alloys/inconel/inconel-alloy-625.pdf.

        Using the correlation for linearExpansionPercent, the 2nd order polynomial is divided by 100
        to convert from percent strain to strain, then differentiated with respect to temperature to
        find the correlation for instantaneous linear expansion.

        i.e. for a linearExpansionPercent correlation of a*Tc**2 + b*Tc + c, the linearExpansion
        correlation is 2*a/100*Tc + b/100

        2*(5.083e-7/100.0)*Tc + 1.125e-3/100.0

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
        linExp = 1.0166e-8 * Tc + 1.125e-5
        return linExp
