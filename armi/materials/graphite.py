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

"""Graphite is often used as a moderator in gas-cooled nuclear reactors."""

from armi.materials.material import Material
from armi.nucDirectory import nuclideBases as nb
from armi.nucDirectory import thermalScattering as tsl
from armi.utils import units


class Graphite(Material):
    """
    Graphite.

    .. [INL-EXT-16-38241] McEligot, Donald, Swank, W. David, Cottle, David L., and Valentin,
        Francisco I. Thermal Properties of G-348 Graphite. United States: N. p., 2016. Web. doi:10.2172/1330693.
        https://www.osti.gov/biblio/1330693
    """

    thermalScatteringLaws = (tsl.byNbAndCompound[nb.byName["C"], tsl.GRAPHITE_10P],)

    def setDefaultMassFracs(self):
        """
        Set graphite to carbon.

        Room temperature density from [INL-EXT-16-38241]_, table 2.
        """
        self.setMassFrac("C", 1.0)
        self.refDens = 1.8888

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """
        This is dL/L0 for graphite.

        From  [INL-EXT-16-38241]_, page 4.
        """
        Tc = units.getTc(Tc, Tk)
        return 100 * (-1.454e-4 + 4.812e-6 * Tc + 1.145e-9 * Tc**2)
