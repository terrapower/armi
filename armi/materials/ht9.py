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
Simple/academic/incomplete HT9 ferritic-martensitic stainless steel material.

This is a famous SFR cladding/duct material because it doesn't void swell that much.
"""

from armi import materials
from armi.utils import units


class HT9(materials.Material):
    """
    Simplified HT9 stainless steel.

    .. warning:: This is an academic-quality material.
        When more detail is desired, a custom material should be implemented via a
        user-provided plugin.

    .. [MFH] Metallic Fuels Handbook
            Hofman, G. L., Billone, M. C., Koenig, J. F., Kramer, J. M., Lambert, J. D. B., Leibowitz, L.,
            Orechwa, Y., Pedersen, D. R., Porter, D. L., Tsai, H., and Wright, A. E. Metallic Fuels Handbook.
            United States: N. p., 2019. Web. doi:10.2172/1506477.
            https://www.osti.gov/biblio/1506477-metallic-fuels-handbook
    """

    name = "HT9"

    def setDefaultMassFracs(self):
        """
        HT9 mass fractions

        From E.2-1 of [MFH]_.
        """
        self.setMassFrac("C", 0.002)
        self.setMassFrac("MN", 0.005)
        self.setMassFrac("SI", 0.0025)
        self.setMassFrac("NI", 0.0055)
        self.setMassFrac("CR", 0.1175)
        self.setMassFrac("MO", 0.01)
        self.setMassFrac("W", 0.0055)
        self.setMassFrac("V", 0.0030)
        self.setMassFrac("FE", 1.0 - sum(self.p.massFrac.values()))

        self.p.refDens = 8.86

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """
        Gets the linear expansion from E.2.2.2 in [MFH]_ for HT9.

        The ref gives dL/L0 in percent and is valid from 293 - 1050 K.
        """
        tk = units.getTk(Tc, Tk)
        self.checkTempRange(293, 1050, tk, "linear expansion")
        return -0.16256 + 1.62307e-4 * tk + 1.42357e-6 * tk ** 2 - 5.50344e-10 * tk ** 3

    def thermalConductivity(self, Tk=None, Tc=None):
        """
        Thermal conductivity in W/m-K)

        From [MFH]_, E.2.2.3, eq 5.

        .. tip:: This can probably be sped up with a polynomial evaluator.
        """
        return (
            29.65
            - 6.668e-2 * Tk
            + 2.184e-4 * Tk ** 2
            - 2.527e-7 * Tk ** 3
            + 9.621e-11 * Tk ** 4
        )
