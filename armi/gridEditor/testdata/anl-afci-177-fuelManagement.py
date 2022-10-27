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

from armi.utils import units

from armi.physics.fuelCycle.fuelHandlers import FuelHandler


class SampleShuffler(FuelHandler):
    def chooseSwaps(self, shuffleParameters):
        cycleSeconds = (
            self.r.p.cycleLength * self.r.p.availabilityFactor * units.SECONDS_PER_DAY
        )
        for a in self.r.core:
            peakFluence = a.getMaxParam("fastFluence")
            peakFlux = a.getMaxParam("fastFlux")
            if peakFluence + peakFlux * cycleSeconds > 4.0e23:
                newAssem = self.r.core.createAssemblyOfType(a.getType())
                self.dischargeSwap(newAssem, a)

    def getFactorList(self, cycle, cs=None):
        """Parameters here can be used to adjust shuffling philosophy vs. cycle."""
        return {}, []
