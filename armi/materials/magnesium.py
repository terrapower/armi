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

"""Magnesium"""

from armi.materials import material
from armi.utils.units import getTk


class Magnesium(material.Fluid):
    name = "Magnesium"
    propertyValidTemperature = {"density": ((923, 1390), "K")}

    def setDefaultMassFracs(self):
        self.setMassFrac("MG", 1.0)

    def density(self, Tk=None, Tc=None):
        r"""returns mass density of magnesium in g/cc
        The Liquid Temperature Range, Density and Constants of Magnesium. P.J. McGonigal. Temple University 1961."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("density", Tk)

        return 1.59 - 0.00026 * (Tk - 924.0)
