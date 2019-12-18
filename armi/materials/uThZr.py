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

# cython: profile=False
"""
Uranium Thorium Zirconium alloy metal
"""
from armi.utils.units import getTk
from armi.materials.material import Material
from armi import runLog


class UThZr(Material):
    """
    U-235 enriched uranium with Thorium 232 - Zirc fuel.

    This gives the combined fuel cycle of U-235, U-238, U-233, Pu-239 etc.
    """

    name = "UThZr"
    enrichedNuclide = "U235"

    def applyInputParams(self, U235_wt_frac=None, ZR_wt_frac=None, TH_wt_frac=None):
        self.parent.adjustMassEnrichment(U235_wt_frac)
        self.parent.adjustMassFrac("ZR", elementToHoldConstant="TH", val=ZR_wt_frac)
        self.parent.adjustMassFrac(
            elementToAdjust="TH", nuclideToHoldConstant="ZR", val=TH_wt_frac
        )
        self.p.thFrac = TH_wt_frac
        self.p.zrFrac = ZR_wt_frac

    def setDefaultMassFracs(self):
        r""" U-ZR mass fractions"""
        self.setMassFrac("U238", 0.8)
        self.setMassFrac("U235", 0.1)
        self.setMassFrac("ZR", 0.09999)
        self.setMassFrac("TH232", 0.00001)

        self.p.zrFrac = 0.09999  # custom param REM
        self.p.thFrac = 0.00001

    def density(self, Tk=None, Tc=None):
        """Calculate the mass density in g/cc of U-Zr alloy with various percents"""
        zrFrac = self.p.zrFrac
        thFrac = self.p.thFrac
        uFrac = 1 - zrFrac - thFrac

        if zrFrac is None:
            runLog.warning(
                "Cannot get UZr density without Zr%. Set ZIRC massFrac",
                single=True,
                label="no zrfrac",
            )
            return None

        Tk = getTk(Tc, Tk)

        u0 = 19.1
        zr0 = 6.52
        th0 = 11.68
        # use vegard's law to mix densities by weight fraction at 50C
        # uzr0 = 1.0/(zrFrac/zr0+(1-zrFrac)/u0)
        uThZr0 = 1.0 / (zrFrac / zr0 + (uFrac) / u0 + thFrac / th0)
        # runLog.debug('Cold density: {0} g/cc'.format(uzr0))

        dLL = self.linearExpansionPercent(Tk=Tk)

        f = (1 + dLL / 100.0) ** 2
        density = uThZr0 * (1.0 + (1.0 - f) / f)

        return density
