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
Uranium metal

Much info is from [AAAFuels]_.

.. [AAAFuels]  Kim, Y S, and Hofman, G L. AAA fuels handbook.. United States: N. p., 2003. Web. doi:10.2172/822554. .
"""

from armi.utils.units import getTk
from armi.materials.material import Material


class Uranium(Material):
    name = "Uranium"
    references = {
        "thermal conductivity": ["AAA Fuels Handbook by YS Kim and G.L. Hofman, ANL"]
    }

    materialIntro = ""

    propertyUnits = {"thermal conductivity": "W/m-K"}

    propertyNotes = {"thermal conductivity": ""}

    propertyRawData = {"thermal conductivity": ""}

    propertyEquation = {
        "thermal conductivity": "21.73 + 0.01591T + 5.907&#215;10<super>-6</super>T<super>2</super>"
    }

    propertyValidTemperature = {"thermal conductivity": ((255.4, 1173.2), "K")}

    def thermalConductivity(self, Tk: float = None, Tc: float = None) -> float:
        """The thermal conductivity of pure U in W-m/K."""
        Tk = getTk(Tc, Tk)
        (TLowerLimit, TUpperLimit) = self.propertyValidTemperature[
            "thermal conductivity"
        ][0]
        self.checkTempRange(TLowerLimit, TUpperLimit, Tk, "thermal conductivity")
        kU = 21.73 + (0.01591 * Tk) + (0.000005907 * Tk ** 2)
        return kU
