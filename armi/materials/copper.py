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

"""Copper metal."""

from armi.materials.material import Material
from armi.utils.units import getTk


class Cu(Material):
    propertyValidTemperature = {"linear expansion percent": ((40.43, 788.83), "K")}

    def setDefaultMassFracs(self):
        self.setMassFrac("CU63", 0.6915)
        self.setMassFrac("CU65", 0.3085)

    def density(self, Tk=None, Tc=None):
        return 8.913  # g/cm3

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """
        Return the linear expansion percent for Copper.

        Notes
        -----
        Digitized using Engauge Digitizer from Figure 21 of
        Thrust Chamber Life Prediction - Volume I - Mechanical and Physical
        Properties of High Performance Rocket Nozzle Materials (NASA CR - 134806)
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion percent", Tk)
        return 5.0298e-07 * Tk**2 + 1.3042e-03 * Tk - 4.3097e-01
