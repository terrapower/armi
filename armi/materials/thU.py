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
Thorium Uranium metal.

Data is from [IAEA-TECDOC-1450]_.

"""

from armi import runLog
from armi.materials.material import FuelMaterial
from armi.utils.units import getTk


class ThU(FuelMaterial):
    enrichedNuclide = "U233"
    propertyValidTemperature = {"linear expansion": ((30, 600), "K")}

    def __init__(self):
        FuelMaterial.__init__(self)
        # density in g/cc from IAEA TE 1450
        self.refDens = 11.68

    def getEnrichment(self):
        return self.getMassFrac("U233") / (self.getMassFrac("U233") + self.getMassFrac("TH232"))

    def applyInputParams(self, U233_wt_frac=None, *args, **kwargs):
        runLog.warning(
            "Material {} has not yet been tested for accuracy".format("ThU"),
            single=True,
            label="ThU applyInputParams",
        )

        if U233_wt_frac is not None:
            self.adjustMassEnrichment(U233_wt_frac)

        FuelMaterial.applyInputParams(self, *args, **kwargs)

    def setDefaultMassFracs(self):
        self.setMassFrac("TH232", 1.0)
        self.setMassFrac("U233", 0.0)

    def linearExpansion(self, Tk=None, Tc=None):
        """Linear expansion in m/m/K from IAEA TE 1450."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion", Tk)
        return 11.9e-6

    def thermalConductivity(self, Tk=None, Tc=None):
        """Thermal conductivity in W/m-K from IAEA TE 1450."""
        Tk = getTk(Tc, Tk)
        return 43.1

    def meltingPoint(self):
        """Melting point in K from IAEA TE 1450."""
        return 2025.0
