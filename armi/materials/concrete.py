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
Concrete.

Concrete is often used to provide structural support of nuclear equipment.

It can also provide radiation shielding.
"""

from armi.materials.material import Material


class Concrete(Material):
    name = "Concrete"
    """ http://jolissrch-inter.tokai-sc.jaea.go.jp/pdfdata/JAERI-Data-Code-98-004.pdf """

    def setDefaultMassFracs(self):
        self.setMassFrac("H", 0.023 / 2.302)
        self.setMassFrac("O16", 1.220 / 2.302)
        self.setMassFrac("C", 0.0023 / 2.302)
        self.setMassFrac("NA23", 0.0368 / 2.302)
        self.setMassFrac("MG", 0.005 / 2.302)
        self.setMassFrac("AL", 0.078 / 2.302)
        self.setMassFrac("SI", 0.775 / 2.302)
        self.setMassFrac("K", 0.0299 / 2.302)
        self.setMassFrac("CA", 0.100 / 2.302)
        self.setMassFrac("FE", 0.032 / 2.302)

    def density(self, Tk=None, Tc=None):
        return 2.302  # g/cc
