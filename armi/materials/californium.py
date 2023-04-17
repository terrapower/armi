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
Californium is a synthetic element made in nuclear reactors.

It is interesting in that it has a large spontaneous fission decay mode that
produces lots of neutrons. It's often used as a neutron source.
"""

from armi.materials.material import SimpleSolid


class Californium(SimpleSolid):

    name = "Californium"

    def setDefaultMassFracs(self):
        self.setMassFrac("CF252", 1.0)

    def density(self, Tk=None, Tc=None):
        """
        https://en.wikipedia.org/wiki/Californium
        """
        return 15.1  # g/cm3
