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

"""Potassium.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

from armi.materials import material
from armi.utils.units import getTc, getTk


class Potassium(material.Fluid):
    """
    Molten pure Potassium.

    From Foust, O.J. Sodium-NaK Engineering Handbook Vol. 1. New York: Gordon and Breach, 1972.
    """

    propertyValidTemperature = {"density": ((63.2, 1250), "C")}

    def pseudoDensity(self, Tk=None, Tc=None):
        r"""
        Calculates the density of molten Potassium in g/cc.

        From Foust, O.J. Sodium-NaK Engineering Handbook Vol. 1. New York: Gordon and Breach, 1972.
        Page 18.

        Notes
        -----
        In ARMI, we define pseudoDensity() and density() as the same for Fluids.
        """
        Tc = getTc(Tc, Tk)
        Tk = getTk(Tc=Tc)
        self.checkPropertyTempRange("density", Tc)
        return 0.8415 - 2.172e-4 * Tc - 2.70e-8 * Tc**2 + 4.77e-12 * Tc**3
