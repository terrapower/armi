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

Concrete is often used to provide structural support of nuclear equipment. It can also provide
radiation shielding.
"""

from armi.materials.material import Material


class Concrete(Material):
    """Simple concreate material.

    https://web.archive.org/web/20221103120449/https://physics.nist.gov/cgi-bin/Star/compos.pl?matno=144
    """

    def setDefaultMassFracs(self):
        self.setMassFrac("H", 0.010000)
        self.setMassFrac("C", 0.001000)
        self.setMassFrac("O16", 0.529107)
        self.setMassFrac("NA23", 0.016000)
        self.setMassFrac("MG", 0.002000)
        self.setMassFrac("AL", 0.033872)
        self.setMassFrac("SI", 0.337021)
        self.setMassFrac("K", 0.013000)
        self.setMassFrac("CA", 0.044000)
        self.setMassFrac("FE", 0.014000)

    def density(self, Tk=None, Tc=None):
        return 2.3000  # g/cm3
