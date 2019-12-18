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
Simplified UZr alloy.

This is a notional U-10Zr material based on [Chandrabhanu]_.
"""

from armi.materials import material
from armi.utils import units


class UZr(material.FuelMaterial):
    """
    Simplified UZr fuel alloy.

    .. warning:: This is an academic-quality material.
        Only the 10% Zr-frac properties are present.
        If you use a Zr-frac other than 10%, these properties will be incorrect. Bring
        in user-provided materials via plugins when necessary.

    .. [Chandrabhanu] Chandrabhanu Basak, G.J. Prasad, H.S. Kamath, N. Prabhu,
        An evaluation of the properties of As-cast U-rich UZr alloys,
        Journal of Alloys and Compounds,
        Volume 480, Issue 2,
        2009,
        Pages 857-862,
        ISSN 0925-8388,
        https://doi.org/10.1016/j.jallcom.2009.02.077.
    """

    name = "UZr"
    enrichedNuclide = "U235"
    zrFracDefault = 0.10
    uFracDefault = 1.0 - zrFracDefault

    def setDefaultMassFracs(self):
        r""" U-Pu-Zr mass fractions"""
        u235Enrichment = 0.1
        self.p.uFrac = self.uFracDefault
        self.p.zrFrac = self.zrFracDefault
        self.setMassFrac("ZR", self.p.zrFrac)
        self.setMassFrac("U235", u235Enrichment * self.p.uFrac)
        self.setMassFrac("U238", (1.0 - u235Enrichment) * self.p.uFrac)
        self._calculateReferenceDensity()

    def applyInputParams(
        self, U235_wt_frac=None, ZR_wt_frac=None, *args, **kwargs
    ):  # pylint: disable=arguments-differ
        """Apply user input."""
        ZR_wt_frac = self.zrFracDefault if ZR_wt_frac is None else ZR_wt_frac
        U235_wt_frac = 0.1 if U235_wt_frac is None else U235_wt_frac
        self.p.zrFrac = ZR_wt_frac
        self.p.uFrac = 1.0 - ZR_wt_frac
        self.setMassFrac("ZR", ZR_wt_frac)
        self.setMassFrac("U235", U235_wt_frac * self.p.uFrac)
        self.setMassFrac("U238", (1.0 - U235_wt_frac) * self.p.uFrac)
        self._calculateReferenceDensity()
        material.FuelMaterial.applyInputParams(self, *args, **kwargs)

    def _calculateReferenceDensity(self):
        """
        Calculates the reference mass density in g/cc of a U-Pu-Zr alloy at 293K with Vergard's law

        .. warning:: the zrFrac, uFrac, etc. may seem redundant with massFrac data.
            But it's complicated to update material fractions one at a time when density
            is changing on the fly.
        """
        zrFrac = self.p.zrFrac
        uFrac = self.p.uFrac
        # use vergard's law to mix densities by weight fraction at 293K
        u0 = 19.1
        zr0 = 6.52
        specificVolume = uFrac / u0 + zrFrac / zr0
        self.p.refDens = 1.0 / specificVolume

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """
        Gets the linear expansion from eq. 3 in [Chandrabhanu]_ for U-10Zr.
        """
        tk = units.getTk(Tc, Tk)
        tk2 = tk * tk
        tk3 = tk2 * tk
        return -0.73 + 3.489e-3 * tk - 5.154e-6 * tk2 + 4.39e-9 * tk3
