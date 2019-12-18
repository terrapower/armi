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
Sulfur
"""

from armi import utils
from armi.utils.units import getTk
from armi.materials import material


class Sulfur(material.Fluid):
    name = "Sulfur"

    def applyInputParams(self, sulfur_density_frac=None):
        if sulfur_density_frac:
            self.fullDensFrac = float(sulfur_density_frac)

    def setDefaultMassFracs(self):
        """Mass fractions"""
        self.fullDensFrac = 1.0
        self.setMassFrac("S32", 0.9493)
        self.setMassFrac("S33", 0.0076)
        self.setMassFrac("S34", 0.0429)
        self.setMassFrac("S36", 0.002)

    def density(self, Tk=None, Tc=None):
        r""" P. Espeau, R. Ceolin "density of molten sulfur in the 334-508K range" """
        Tk = getTk(Tc, Tk)

        self.checkTempRange(334, 430, Tk, "density")

        return (2.18835 - 0.00098187 * Tk) * (self.fullDensFrac)

    def volumetricExpansion(self, Tk=None, Tc=None):
        r""" P. Espeau, R. Ceolin "density of molten sulfur in the 334-508K range"
        This is just a two-point interpolation."""
        Tk = getTk(Tc, Tk)

        self.checkTempRange(334, 430, Tk, "volumetric expansion")
        return utils.linearInterpolation(
            x0=334, y0=5.28e-4, x1=430, y1=5.56e-4, targetX=Tk
        )
