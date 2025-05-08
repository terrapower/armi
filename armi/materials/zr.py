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

"""Zirconium metal."""

from numpy import interp

from armi.materials.material import Material
from armi.utils.units import getTk


class Zr(Material):
    """Metallic zirconium."""

    propertyValidTemperature = {
        "density": ((293, 1800), "K"),
        "linear expansion": ((293, 1800), "K"),
        "linear expansion percent": ((293, 1800), "K"),
        "thermal conductivity": ((298, 2000), "K"),
    }

    references = {
        "density": "AAA Materials Handbook 45803",
        "thermal conductivity": "AAA Fuels handbook. ANL",
        "linear expansion": "Y.S. Touloukian, R.K. Kirby, R.E. Taylor and P.D. Desai, Thermal Expansion, "
        + "Thermophysical Properties of Matter, Vol. 12, IFI/Plenum, New York-Washington (1975)",
        "linear expansion percent": "Y.S. Touloukian, R.K. Kirby, R.E. Taylor and P.D. Desai, Thermal Expansion, "
        + "Thermophysical Properties of Matter, Vol. 12, IFI/Plenum, New York-Washington (1975)",
    }

    linearExpansionTableK = [
        293,
        400,
        500,
        600,
        700,
        800,
        900,
        1000,
        1100,
        1136.99999,
        1137,
        1200,
        1400,
        1600,
        1800,
    ]

    linearExpansionTable = [
        5.70e-6,
        5.90e-6,
        6.60e-6,
        7.10e-6,
        7.60e-6,
        7.90e-6,
        8.00e-6,
        8.20e-6,
        8.20e-6,
        8.20e-6,
        9.00e-6,
        9.10e-6,
        9.50e-6,
        1.03e-5,
        1.13e-5,
    ]

    refTempK = 298.15

    def __init__(self):
        Material.__init__(self)
        self.refDens = self._computeReferenceDensity(Tk=self.refTempK)

    def setDefaultMassFracs(self):
        self.setMassFrac("ZR", 1.0)

    def _computeReferenceDensity(self, Tk=None, Tc=None):
        r"""AAA Materials Handbook 45803."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("density", Tk)

        if Tk < 1135:
            return -3.29256e-8 * Tk**2 - 9.67145e-5 * Tk + 6.60176
        else:
            return -2.61683e-8 * Tk**2 - 1.11331e-4 * Tk + 6.63616

    def thermalConductivity(self, Tk=None, Tc=None):
        """
        Thermal conductivity in W/mK.

        Reference: AAA Fuels handbook. ANL.
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("thermal conductivity", Tk)
        return 8.853 + (0.007082 * Tk) + (0.000002533 * Tk**2) + (2992.0 / Tk)

    def linearExpansion(self, Tk=None, Tc=None):
        r"""Linear expansion in m/mK.

        Reference: Y.S. Touloukian, R.K. Kirby, R.E. Taylor and P.D. Desai, Thermal Expansion,
                   Thermophysical Properties of Matter, Vol. 12, IFI/Plenum, New York-Washington (1975)

        See page 400
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion", Tk)
        return interp(Tk, self.linearExpansionTableK, self.linearExpansionTable)

    def linearExpansionPercent(self, Tk=None, Tc=None):
        r"""Linear expansion in dL/L.

        Reference: Y.S. Touloukian, R.K. Kirby, R.E. Taylor and P.D. Desai, Thermal Expansion,
                   Thermophysical Properties of Matter, Vol. 12, IFI/Plenum, New York-Washington (1975)

        See page 400
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion percent", Tk)

        # NOTE: checkPropertyTempRange takes care of lower/upper limits
        if Tk < 1137:
            return (
                -0.111 + (2.325e-4 * Tk) + (5.595e-7 * Tk**2) - (1.768e-10 * Tk**3)
            )
        else:
            return (
                -0.759 + (1.474e-3 * Tk) - (5.140e-7 * Tk**2) + (1.559e-10 * Tk**3)
            )
