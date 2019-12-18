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
Molybdenum
"""

from armi.materials.material import Material


class Molybdenum(Material):
    name = "Molybdenum"

    def setDefaultMassFracs(self):
        """Moly mass fractions."""
        self.setMassFrac("MO", 1.0)

    def density(self, Tk=None, Tc=None):
        return 10.28  # g/cc
