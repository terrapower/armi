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

"""Uranium Thorium Zirconium alloy metal."""

from armi import runLog
from armi.materials.material import FuelMaterial
from armi.utils.units import getTk


class UThZr(FuelMaterial):
    """
    U-235 enriched uranium with Thorium 232 - Zirc fuel.

    This gives the combined fuel cycle of U-235, U-238, U-233, Pu-239 etc.
    """

    enrichedNuclide = "U235"
    th232FracDefault = 0.00001
    u235FracDefault = 0.1
    u238FracDefault = 0.8
    zrFracDefault = 0.09999

    def applyInputParams(self, U235_wt_frac=None, ZR_wt_frac=None, *args, **kwargs):
        ZR_wt_frac = self.zrFracDefault if ZR_wt_frac is None else ZR_wt_frac
        U235_wt_frac = self.u238FracDefault if U235_wt_frac is None else U235_wt_frac

        self.adjustMassFrac("U238", U235_wt_frac)
        self.adjustMassFrac("ZR", ZR_wt_frac)

        FuelMaterial.applyInputParams(self, *args, **kwargs)

    def setDefaultMassFracs(self):
        """U-ZR mass fractions."""
        self.setMassFrac("U238", self.u238FracDefault)
        self.setMassFrac("U235", self.u235FracDefault)
        self.setMassFrac("ZR", self.zrFracDefault)
        self.setMassFrac("TH232", self.th232FracDefault)

    def pseudoDensity(self, Tk=None, Tc=None):
        """Calculate the mass density in g/cc of U-Zr alloy with various percents."""
        zrFrac = self.getMassFrac("ZR")
        thFrac = self.getMassFrac("TH232")
        uFrac = 1 - zrFrac - thFrac

        if zrFrac is None:
            runLog.warning(
                "Cannot get UZr density without Zr%. Set ZIRC massFrac",
                single=True,
                label="no zrfrac",
            )
            return None

        Tk = getTk(Tc, Tk)

        # use Vegard's law to mix densities by weight fraction at 50C
        u0 = 19.1
        zr0 = 6.52
        th0 = 11.68
        uThZr0 = 1.0 / (zrFrac / zr0 + (uFrac) / u0 + thFrac / th0)

        dLL = self.linearExpansionPercent(Tk=Tk)

        f = (1 + dLL / 100.0) ** 2
        density = uThZr0 * (1.0 + (1.0 - f) / f)

        return density
