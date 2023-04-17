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
Sodium Chloride salt

.. note:: This is a very simple description of this material.
"""
from armi.materials.material import SimpleSolid
from armi.utils.units import getTk


class NaCl(SimpleSolid):
    name = "NaCl"

    def setDefaultMassFracs(self):
        self.setMassFrac("NA23", 0.3934)
        self.setMassFrac("CL35", 0.4596)
        self.setMassFrac("CL37", 0.1470)

    def density(self, Tk=None, Tc=None):
        """
        Return the density of Sodium Chloride.

        Notes
        -----
        From equation 10 of Thermophysical Properties of NaCl
        NaBr and NaF by y-ray attenuation technique
        """
        Tk = getTk(Tc, Tk)
        return -3.130e-04 * Tk + 2.23
