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

from armi.physics.fuelCycle.fuelHandlers import FuelHandler


class EquilibriumShuffler(FuelHandler):
    r"""
    Convergent divergent equilibrium shuffler
    """

    def chooseSwaps(self, factorList):
        cycleMoves = [
            [(2, 1), (3, 3), (4, 2), (5, 1), (6, 7)],
            [(2, 2), (3, 2), (4, 1), (5, 4), (6, 4)],
            [(2, 1), (3, 1), (4, 3), (5, 2), (6, 7)],
        ]
        cascade = []
        for ring, pos in cycleMoves[self.cycle]:
            a = self.r.core.whichAssemblyIsIn(ring, pos)
            if not a:
                raise RuntimeError("No assembly in {0} {1}".format(ring, pos))
            cascade.append(a)
        self.swapCascade(cascade)
        fresh = self.r.blueprints.constructAssem(
            self.r.core.geomType, self.cs, name="igniter fuel"
        )
        self.dischargeSwap(fresh, cascade[0])
        if self.cycle > 0:
            # do a swap where the assembly comes from the sfp
            incoming = self.r.core.sfp.getChildren().pop(0)
            if not incoming:
                raise RuntimeError(
                    "No assembly in SFP {0}".format(self.r.core.sfp.getChildren())
                )
            self.dischargeSwap(
                incoming, self.r.core.whichAssemblyIsIn(5, 2 + self.cycle)
            )


def getFactorList(cycle, cs=None, fallBack=False):

    # prefer to keep these 0 through 1 since this is what the branch search can do.
    defaultFactorList = {}
    factorSearchFlags = []
    defaultFactorList["divergentConvergent"] = 1

    return defaultFactorList, factorSearchFlags
