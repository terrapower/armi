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
Lithium.

.. WARNING:: Whenever you irradiate lithium you will get tritium.
"""

from armi import utils
from armi.materials import material


class Lithium(material.Fluid):
    name = "Lithium"
    references = {"density": "Wikipedia"}
    enrichedNuclide = "LI6"

    def applyInputParams(self, LI_wt_frac=None, *args, **kwargs):
        enrich = utils.getFloat(LI_wt_frac)
        # allow 0.0 to pass in!
        if enrich is not None:
            self.adjustMassEnrichment(LI_wt_frac)

    def density(self, Tk=None, Tc=None):
        r"""
        Wikipedia.

        Will be liquid above 180C.
        """
        return 0.512  # g/cc

    def setDefaultMassFracs(self):
        self.setMassFrac("LI6", 0.075)
        self.setMassFrac("LI7", 0.925)

    def meltingPoint(self):
        return 453.69  # K

    def boilingPoint(self):
        return 1615.0  # K

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""
        Wikipedia
        """
        return 84.8  # W/m-K

    def heatCapacity(self, Tk=None, Tc=None):
        return 3570.0
