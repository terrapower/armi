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

"""Sulfur."""

from armi import runLog
from armi.materials import material
from armi.utils.mathematics import linearInterpolation
from armi.utils.units import getTk


class Sulfur(material.Fluid):
    propertyValidTemperature = {
        "density": ((334, 430), "K"),
        "volumetric expansion": ((334, 430), "K"),
    }

    def applyInputParams(self, sulfur_density_frac=None, TD_frac=None):
        if sulfur_density_frac is not None:
            runLog.warning(
                "The 'sulfur_density_frac' material modification for Sulfur "
                "will be deprecated. Update your inputs to use 'TD_frac' instead.",
                single=True,
            )
            if TD_frac is not None:
                runLog.warning(
                    f"Both 'sulfur_density_frac' and 'TD_frac' are specified for {self}. 'TD_frac' will be used."
                )
            else:
                self.updateTD(sulfur_density_frac)

        if TD_frac is not None:
            self.updateTD(TD_frac)

    def updateTD(self, TD):
        self.fullDensFrac = float(TD)

    def setDefaultMassFracs(self):
        """Mass fractions."""
        self.fullDensFrac = 1.0
        self.setMassFrac("S32", 0.9493)
        self.setMassFrac("S33", 0.0076)
        self.setMassFrac("S34", 0.0429)
        self.setMassFrac("S36", 0.002)

    def pseudoDensity(self, Tk=None, Tc=None):
        """Density of Liquid Sulfur.

        Ref: P. Espeau, R. Ceolin "density of molten sulfur in the 334-508K range"

        Notes
        -----
        In ARMI, we define pseudoDensity() and density() as the same for Fluids.
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("density", Tk)

        return (2.18835 - 0.00098187 * Tk) * (self.fullDensFrac)

    def volumetricExpansion(self, Tk=None, Tc=None):
        """
        This is just a two-point interpolation.

        P. Espeau, R. Ceolin "density of molten sulfur in the 334-508K range"
        """
        Tk = getTk(Tc, Tk)
        (Tmin, Tmax) = self.propertyValidTemperature["volumetric expansion"][0]
        self.checkPropertyTempRange("volumetric expansion", Tk)

        return linearInterpolation(x0=334, y0=5.28e-4, x1=430, y1=5.56e-4, targetX=Tk)
