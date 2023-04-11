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
Inconel is a austenitic nickel-chromium superalloy.
"""

from armi.materials.material import SimpleSolid


class Inconel(SimpleSolid):
    name = "Inconel"
    references = {
        "mass fractions": "https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-617.pdf",
        "density": "https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-617.pdf",
    }

    def setDefaultMassFracs(self):
        self.setMassFrac("NI", 0.52197)
        self.setMassFrac("CR", 0.22)
        self.setMassFrac("CO59", 0.125)
        self.setMassFrac("MO", 0.09)
        self.setMassFrac("AL27", 0.0115)
        self.setMassFrac("C", 0.001)
        self.setMassFrac("FE", 0.015)
        self.setMassFrac("MN55", 0.005)
        self.setMassFrac("SI", 0.005)
        self.setMassFrac("TI", 0.003)
        self.setMassFrac("CU", 0.0025)
        self.setMassFrac("B10", 0.00003 * 0.1997)
        self.setMassFrac("B11", 0.00003 * (1.0 - 0.1997))

    def density(self, Tk=None, Tc=None):
        return 8.3600


class Inconel617(Inconel):
    """
    Note: historically the 'Inconel' material represented the high-nickel alloy
    Inconel 617. This material enables the user to know with certainty that
    this material represents Inconel 617 and doesn't break any older models
    """

    name = "Inconel617"
