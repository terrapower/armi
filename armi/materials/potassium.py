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
Potassium
"""

from armi.utils.units import getTc, getTk
from armi.materials import material


class Potassium(material.Fluid):
    """
    Molten pure Potassium.

    From Foust, O.J. Sodium-NaK Engineering Handbook Vol. 1. New York: Gordon and Breach, 1972.
    """

    name = "Potassium"

    def density(self, Tk=None, Tc=None, check_range=True):
        r"""
        Calculates the density of molten Potassium in g/cc
        From Foust, O.J. Sodium-NaK Engineering Handbook Vol. 1. New York: Gordon and Breach, 1972.
        Page 18.
        """
        Tc = getTc(Tc, Tk)
        Tk = getTk(Tc, Tk)
        if check_range:
            self.checkTempRange(63.38, 759, Tk, "density")
        return 0.8415 - 2.172e-4 * Tc - 2.70e-8 * Tc ** 2 + 4.77e-12 * Tc ** 3
