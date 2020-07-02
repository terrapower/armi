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

"""Simple sodium material."""

from armi.materials import material
from armi import runLog
from armi.utils.units import getTc, getTk


class Sodium(material.Fluid):
    """
    Simplified sodium material.

    .. warning:: This is an academic-quality material. Bring in user-provided material
        properties through plugins as necessary.

    Most info from  [ANL-RE-95-2]_

    .. [ANL-RE-95-2] Fink, J.K., and Leibowitz, L. Thermodynamic and transport properties of sodium
        liquid and vapor. United States: N. p., 1995. Web. doi:10.2172/94649.
        https://www.osti.gov/biblio/94649-gXNdLI/webviewable/

    """

    name = "Sodium"

    def setDefaultMassFracs(self):
        """It's just sodium"""
        self.setMassFrac("NA", 1.0)
        self.p.refDens = 0.968

    def density(self, Tk=None, Tc=None, check_range=True):
        """
        Returns density of Sodium in g/cc.

        This is from 1.3.1 in [ANL-RE-95-2]_.

        Parameters
        ----------
        Tk : float, optional
            temperature in degrees Kelvin
        Tc : float, optional
            temperature in degrees Celsius
        check_range : Boolean, optional
            Set check_range=False to avoid "zillions" of print-out warnings that occur if
            the input temperature (Tc or Tk) is out of the applicability range of properties.

        Returns
        -------
        density : float
            mass density in g/cc
        """
        Tk = getTk(Tc, Tk)
        Tc = getTc(Tc, Tk)
        if check_range:
            self.checkTempRange(97.85, 2230.55, Tc, "density")

        if check_range and (Tc is not None) and (Tc <= 97.72):
            runLog.warning(
                "Sodium frozen at Tc: {0}".format(Tc),
                label="Sodium frozen at Tc={0}".format(Tc),
                single=True,
            )

        critDens = 219  # critical density
        f = 275.32  #
        g = 511.58
        h = 0.5
        Tcrit = 2503.7  # critical temperature
        return (
            critDens
            + f * (1 - (Tc + 273.15) / Tcrit)
            + g * (1 - (Tc + 273.15) / Tcrit) ** h
        ) / 1000.0  # convert from kg/m^3 to g/cc.

    def specificVolumeLiquid(self, Tk=None, Tc=None):
        """
        Returns the liquid specific volume in m^3/kg of this material given Tk in K or Tc in C.
        """
        return 1 / (1000.0 * self.density(Tk, Tc))

    def enthalpy(self, Tk=None, Tc=None):
        """
        Return enthalpy in J/kg.

        From [ANL-RE-95-2]_, Table 1.1-2.
        """
        Tk = getTk(Tc, Tk)
        self.checkTempRange(371.0, 2000.0, Tk, "enthalpy")
        enthalpy = (
            -365.77
            + 1.6582 * Tk
            - 4.2395e-4 * Tk ** 2
            + 1.4847e-7 * Tk ** 3
            + 2992.6 / Tk
        )
        enthalpy = enthalpy * 1000  # convert from kJ/kg to kJ/kg
        return enthalpy

    def thermalConductivity(self, Tk=None, Tc=None):
        """
        Returns thermal conductivity of Sodium

        From [ANL-RE-95-2]_, Table 2.1-2

        Parameters
        ----------
        Tk : float, optional
            temperature in degrees Kelvin
        Tc : float, optional
            temperature in degrees Celsius

        Returns
        -------
        thermalConductivity : float
            thermal conductivity of Sodium (W/m-K)

        """
        Tc = getTc(Tc, Tk)
        self.checkTempRange(3715, 1500, Tk, "thermal conductivity")
        thermalConductivity = (
            124.67 - 0.11381 * Tk + 5.5226e-5 * Tk ** 2 - 1.1842e-8 * Tk ** 3
        )
        return thermalConductivity
