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
Thorium Uranium metal

Data is from [#IAEA-TECDOCT-1450]_.

.. [#IAEA-TECDOCT-1450] Thorium fuel cycle -- Potential benefits and challenges, IAEA-TECDOC-1450 (2005).
    https://www-pub.iaea.org/mtcd/publications/pdf/te_1450_web.pdf
"""

from armi.utils.units import getTk
from armi.materials import material
from armi import runLog


class ThU(material.Material):
    name = "ThU"
    enrichedNuclide = "U233"

    def getEnrichment(self):
        return self.getMassFrac("U233") / (
            self.getMassFrac("U233") + self.getMassFrac("TH232")
        )

    def applyInputParams(self, U233_wt_frac=None, *args, **kwargs):
        runLog.warning("Material {} has not yet been tested for accuracy".format("ThU"))

        if U233_wt_frac:
            self.adjustMassEnrichment(U233_wt_frac)
        material.FuelMaterial.applyInputParams(self, *args, **kwargs)

    def setDefaultMassFracs(self):
        self.setMassFrac("TH232", 1.0)
        self.setMassFrac("U233", 0.0)

    def density(self, Tk=None, Tc=None):
        Tk = getTk(Tc, Tk)
        """g/cc from IAEA TE 1450"""
        return 11.68

    def linearExpansion(self, Tk=None, Tc=None):
        r"""m/m/K from IAEA TE 1450"""
        Tk = getTk(Tc, Tk)
        self.checkTempRange(30, 600, Tk, "linear expansionn")
        return 11.9e-6

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""W/m-K from IAEA TE 1450"""
        Tk = getTk(Tc, Tk)
        return 43.1

    def meltingPoint(self):
        r"""melting point in K from IAEA TE 1450"""
        return 2025.0
