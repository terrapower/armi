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
Lead-Bismuth eutectic.

This is a great coolant for superfast neutron reactors. It's heavy though.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

import math

from armi.materials import material
from armi.utils.units import getTk


class LeadBismuth(material.Fluid):
    """Lead bismuth eutectic."""

    propertyValidTemperature = {
        "density": ((400, 1300), "K"),
        "dynamic visc": ((400, 1100), "K"),
        "heat capacity": ((400, 1100), "K"),
        "thermal conductivity": ((400, 1100), "K"),
        "volumetric expansion": ((400, 1300), "K"),
    }

    def setDefaultMassFracs(self):
        r"""Mass fractions."""
        self.setMassFrac("PB", 0.445)
        self.setMassFrac("BI209", 0.555)

    def pseudoDensity(self, Tk=None, Tc=None):
        r"""Density in g/cc from V. sobolev/ J Nucl Mat 362 (2007) 235-247."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("density", Tk)

        return 11.096 - 0.0013236 * Tk  # pre-converted from kg/m^3 to g/cc

    def dynamicVisc(self, Tk=None, Tc=None):
        r"""Dynamic viscosity in Pa-s from Sobolev.

        Accessed online at:
        http://www.oecd-nea.org/science/reports/2007/nea6195-handbook.html on 11/9/12
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("dynamic visc", Tk)

        return 4.94e-4 * math.exp(754.1 / Tk)

    def heatCapacity(self, Tk=None, Tc=None):
        r"""Heat ccapacity in J/kg/K from Sobolev. Expected accuracy 5%."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("heat capacity", Tk)

        return 159 - 2.72e-2 * Tk + 7.12e-6 * Tk**2

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""Thermal conductivity in W/m/K from Sobolev.

        Accessed online at:
        http://www.oecd-nea.org/science/reports/2007/nea6195-handbook.html on 11/9/12
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("thermal conductivity", Tk)

        return 2.45 * Tk / (86.334 + 0.0511 * Tk)

    def volumetricExpansion(self, Tk=None, Tc=None):
        r"""Volumetric expansion inferred from density.

        NOT BASED ON MEASUREMENT.
        Done by V. sobolev/ J Nucl Mat 362 (2007) 235-247
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("volumetric expansion", Tk)

        return 1.0 / (8383.2 - Tk)
