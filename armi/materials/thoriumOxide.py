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
Thorium Oxide solid ceramic.

Data is from [IAEA-TECDOC-1450]_.

.. [IAEA-TECDOC-1450] Thorium fuel cycle -- Potential benefits and challenges, IAEA-TECDOC-1450 (2005).
    https://www-pub.iaea.org/mtcd/publications/pdf/te_1450_web.pdf
"""

from armi import runLog
from armi.materials.material import FuelMaterial, Material, SimpleSolid
from armi.utils.units import getTk


class ThoriumOxide(FuelMaterial, SimpleSolid):
    propertyValidTemperature = {"linear expansion": ((298, 1223), "K")}

    def __init__(self):
        Material.__init__(self)
        self.refDens = 10.00

    def applyInputParams(self, TD_frac=None, *args, **kwargs):
        if TD_frac is not None:
            if TD_frac > 1.0:
                runLog.warning(
                    f"Theoretical density frac for {self} is {TD_frac}, which is >1",
                    single=True,
                    label="Large theoretical density",
                )
            elif TD_frac == 0:
                runLog.warning(
                    f"Theoretical density frac for {self} is zero!",
                    single=True,
                    label="Zero theoretical density",
                )
            elif TD_frac < 0:
                runLog.error(
                    "TD_frac is entered as negative. This is not allowed!",
                    single=True,
                    label="Negative TD_frac",
                )
            self.adjustTD(TD_frac)

        FuelMaterial.applyInputParams(self, *args, **kwargs)

    def setDefaultMassFracs(self):
        r"""ThO2 mass fractions. Using Pure Th-232. 100% 232.

        Thorium: 232.030806 g/mol
        Oxygen:  15.9994 g/mol

        2 moles of oxygen/1 mole of Thorium

        grams of Th-232 = 232.030806 g/mol* 1 mol  =  232.030806 g
        grams of Oxygen = 15.9994 g/mol* 2 mol = 31.9988 g
        total=264.029606 g.
        Mass fractions are computed from this.
        """
        self.setMassFrac("TH232", 0.8788)
        self.setMassFrac("O16", 0.1212)

    def linearExpansion(self, Tk=None, Tc=None):
        r"""Linear expansion in m/m/K from IAEA TE 1450."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion", Tk)

        return 9.67e-6

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """
        Approximate the linear thermal expansion percent from the linear expansion
        coefficient, taking 298K as the reference temperature.
        """
        Tk = getTk(Tc=Tc, Tk=Tk)
        linearExpansionCoef = self.linearExpansion(Tk=Tk)

        return 100 * (linearExpansionCoef * (Tk - 298))

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""Thermal conductivity in W/m-K from IAEA TE 1450."""
        return 6.20

    def meltingPoint(self):
        r"""Melting point in K from IAEA TE 1450."""
        return 3643.0

    def density(self, Tk=None, Tc=None):
        return Material.density(self, Tk, Tc) * self.getTD()


class ThO2(ThoriumOxide):
    """Another name for ThoriumOxide."""

    pass
