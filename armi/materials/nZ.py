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
Niobium Zirconium Alloy
"""

from armi.materials.material import Material


class NZ(Material):
    name = "NZ"

    def setDefaultMassFracs(self):
        self.setMassFrac("NB93", 0.99)
        self.setMassFrac("ZR", 0.01)

    def density(self, Tk=None, Tc=None):
        return 8.66  # g/cc
