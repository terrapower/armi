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

"""Magnesium.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

from armi.materials import material
from armi.utils.units import getTk


class Magnesium(material.Fluid):
    propertyValidTemperature = {"density": ((923, 1390), "K")}

    def setDefaultMassFracs(self):
        self.setMassFrac("MG", 1.0)

    def pseudoDensity(self, Tk=None, Tc=None):
        """Returns mass density of magnesium in g/cm3.

        The Liquid Temperature Range, Density and Constants of Magnesium. P.J. McGonigal. Temple University 1961.

        Notes
        -----
        For Fluids, ARMI defines this 2D pseudodensity is the same as the usual 3D physical density.
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("density", Tk)

        return 1.834 - 2.647e-4 * Tk
