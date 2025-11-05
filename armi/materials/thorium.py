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
Thorium Metal.

Data is from [IAEA-TECDOC-1450]_.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

from armi.materials.material import FuelMaterial
from armi.utils.units import getTk


class Thorium(FuelMaterial):
    propertyValidTemperature = {"linear expansion": ((30, 600), "K")}

    def __init__(self):
        FuelMaterial.__init__(self)
        self.refDens = 11.68

    def setDefaultMassFracs(self):
        self.setMassFrac("TH232", 1.0)

    def linearExpansion(self, Tk=None, Tc=None):
        r"""Linear Expansion in m/m/K from IAEA TECDOC 1450."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion", Tk)

        return 11.9e-6

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""W/m-K from IAEA TE 1450."""
        return 43.1

    def meltingPoint(self):
        """Melting point in K from IAEA TE 1450."""
        return 2025.0
