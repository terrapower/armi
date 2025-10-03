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
Lithium.

.. WARNING:: Whenever you irradiate lithium you will get tritium.
"""

from armi import runLog
from armi.materials import material
from armi.utils.mathematics import getFloat


class Lithium(material.Fluid):
    references = {"density": "Wikipedia"}
    enrichedNuclide = "LI6"

    def applyInputParams(self, LI_wt_frac=None, LI6_wt_frac=None, *args, **kwargs):
        if LI_wt_frac is not None:
            runLog.warning(
                "The 'LI_wt_frac' material modification for Lithium will be deprecated"
                " Update your inputs to use 'LI6_wt_frac' instead.",
                single=True,
                label="Lithium applyInputParams 1",
            )
            if LI6_wt_frac is not None:
                runLog.warning(
                    f"Both 'LI_wt_frac' and 'LI6_wt_frac' are specified for {self}. 'LI6_wt_frac' will be used.",
                    single=True,
                    label="Lithium applyInputParams 2",
                )

        LI6_wt_frac = LI6_wt_frac or LI_wt_frac

        enrich = getFloat(LI6_wt_frac)
        # allow 0.0 to pass in!
        if enrich is not None:
            self.adjustMassEnrichment(LI6_wt_frac)

    def pseudoDensity(self, Tk=None, Tc=None):
        r"""Density (g/cc) from Wikipedia.

        Will be liquid above 180C.

        Notes
        -----
        In ARMI, we define pseudoDensity() and density() as the same for Fluids.
        """
        return 0.512

    def setDefaultMassFracs(self):
        self.setMassFrac("LI6", 0.0759)
        self.setMassFrac("LI7", 0.92410004)

    def meltingPoint(self):
        return 453.69  # K

    def boilingPoint(self):
        return 1615.0  # K

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""Wikipedia."""
        return 84.8  # W/m-K

    def heatCapacity(self, Tk=None, Tc=None):
        return 3570.0
