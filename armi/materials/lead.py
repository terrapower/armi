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

"""Lead.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

from armi.materials import material
from armi.utils.units import getTk


class Lead(material.Fluid):
    """Natural lead."""

    propertyValidTemperature = {
        "density": ((600, 1700), "K"),
        "heat capacity": ((600, 1500), "K"),
        "volumetric expansion": ((600, 1700), "K"),
    }

    def volumetricExpansion(self, Tk=None, Tc=None):
        r"""Volumetric expansion inferred from density.

        NOT BASED ON MEASUREMENT.
        Done by V. sobolev/ J Nucl Mat 362 (2007) 235-247
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("volumetric expansion", Tk)

        return 1.0 / (9516.9 - Tk)

    def setDefaultMassFracs(self):
        """Mass fractions."""
        self.setMassFrac("PB", 1)

    def pseudoDensity(self, Tk=None, Tc=None):
        """Density in g/cc from V. sobolev/ J Nucl Mat 362 (2007) 235-247."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("density", Tk)

        return 11.367 - 0.0011944 * Tk  # pre-converted from kg/m^3 to g/cc

    def heatCapacity(self, Tk=None, Tc=None):
        """Heat capacity in J/kg/K from Sobolev."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("heat capacity", Tk)

        return 162.9 - 3.022e-2 * Tk + 8.341e-6 * Tk**2
