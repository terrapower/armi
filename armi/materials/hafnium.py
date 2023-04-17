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
Hafnium is an element that has high capture cross section across multiple isotopes.
"""

from armi.nucDirectory import nucDir
from armi.materials.material import SimpleSolid


class Hafnium(SimpleSolid):
    name = "Hafnium"

    def setDefaultMassFracs(self):
        for a, abund in nucDir.getNaturalMassIsotopics("HF"):
            self.setMassFrac("HF{0}".format(a), abund)

    def density(self, Tk=None, Tc=None):
        r"""
        http://www.lenntech.com/periodic/elements/hf.htm
        """
        return 13.07
