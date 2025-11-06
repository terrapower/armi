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

"""Inconel PE16.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

from armi import runLog
from armi.materials.material import SimpleSolid


class InconelPE16(SimpleSolid):
    references = {
        "mass fractions": r"http://www.specialmetals.com/assets/documents/alloys/nimonic/nimonic-alloy-pe16.pdf",
        "density": r"http://www.specialmetals.com/assets/documents/alloys/nimonic/nimonic-alloy-pe16.pdf",
    }

    def setDefaultMassFracs(self):
        massFracs = {
            "C": 0.0006,
            "SI": 0.0025,
            "MN55": 0.001,
            "S": 0.000075,
            "AG107": 0.0000025 * 0.51839001,
            "AG109": 0.0000025 * 0.48160999,
            "AL27": 0.012,
            "B10": 0.000025 * 0.19799999,
            "B11": 0.000025 * 0.80199997,
            "BI209": 0.0000005,
            "CO59": 0.01,
            "CR": 0.165,
            "CU": 0.0025,
            "MO": 0.033,
            "NI": 0.425,
            "PB": 0.0000075,
            "TI": 0.012,
            "ZR": 0.0003,
        }
        massFracs["FE"] = 1 - sum(massFracs.values())  # balance*

        # *Reference to the 'balance' of a composition does not guarantee this is exclusively of the element mentioned
        # but that it predominates and others are present only in minimal quantities.

        for element, massFrac in massFracs.items():
            self.setMassFrac(element, massFrac)

    def density(self, Tk=None, Tc=None):
        runLog.warning(
            "PE16 mass density is not temperature dependent, using room temperature value",
            single=True,
            label="InconelPE16 density",
        )
        return 8.00
