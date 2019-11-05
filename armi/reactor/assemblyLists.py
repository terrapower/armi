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

r"""

"""

import numpy

from armi import runLog
from armi.utils import units
from armi.reactor import grids
from armi.reactor import composites
from armi.reactor.flags import Flags


class AssemblyList(composites.Composite):
    def __init__(self, name, r=None):

        composites.Composite.__init__(self, name)
        self.parent = r
        self.spatialGrid = grids.cartesianGridFromRectangle(
            50.0, 50.0
        )  # make a Cartesian assembly rack

        # CoreParameterCollections get CORE by default; we arent ready for that yet here, so turn it
        # off.
        self.p.flags = self.p.flags & ~Flags.CORE
        # random non-zero location to be updated with user-input later
        self.spatialLocator = grids.CoordinateLocation(100.0, 100.0, 350.0, None)

    # TODO: R is currently a misnomer, since the parent of an AssemblyList is actually a Core. The
    # is not the intended final behavior is to put the SFP, etc. under the Reactor, so i think it
    # makes sense to leave this as `r`
    @property
    def r(self):
        return self.parent

    @r.setter
    def r(self, r):
        self.parent = r

    def __repr__(self):
        return "<AssemblyList object: {0}>".format(self.name)

    def getAssembly(self, name):
        for a in self.getChildren():
            if a.getName() == name:
                return a

    def count(self):
        if not self.getChildren():
            return
        runLog.important("Count:")
        totCount = 0
        thisTimeCount = 0
        a = self.getChildren()[0]
        lastTime = a.getAge() / units.DAYS_PER_YEAR + a.p.chargeTime

        for a in self.getChildren():
            thisTime = a.getAge() / units.DAYS_PER_YEAR + a.p.chargeTime

            if thisTime != lastTime:
                runLog.important(
                    "Number of assemblies moved at t={0:6.2f}: {1:04d}. Cumulative: {2:04d}".format(
                        lastTime, thisTimeCount, totCount
                    )
                )
                lastTime = thisTime
                thisTimeCount = 0
            totCount += 1
            thisTimeCount += 1


class SpentFuelPool(AssemblyList):
    """A place to put assemblies when they've been discharged. Can tell you inventory stats, etc. """

    def report(self):
        title = "{0} Report".format(self.name)
        runLog.important("-" * len(title))
        runLog.important(title)
        runLog.important("-" * len(title))
        totFis = 0.0
        for a in self.getChildren():
            runLog.important(
                "{assembly:15s} discharged at t={dTime:10f} after {residence:10f} yrs. It entered at cycle: {cycle}. "
                "It has {fiss:10f} kg (full core) fissile and peak BU={bu:.2f} %.".format(
                    assembly=a,
                    dTime=a.p.dischargeTime,
                    residence=(a.p.dischargeTime - a.p.chargeTime),
                    cycle=a.p.chargeCycle,
                    fiss=a.getFissileMass() * self.r.powerMultiplier / 1000.0,
                    bu=a.getMaxParam("percentBu"),
                )
            )
            totFis += a.getFissileMass() / 1000  # convert to kg
        runLog.important(
            "Total full-core fissile inventory of {0} is {1:.4E} MT".format(
                self, totFis * self.r.powerMultiplier / 1000.0
            )
        )


class ChargedFuelPool(AssemblyList):
    """A place to put boosters so you can see how much you added. Can tell you inventory stats, etc. """

    def report(self):
        title = "{0} Report".format(self.name)
        runLog.important("-" * len(title))
        runLog.important(title)
        runLog.important("-" * len(title))
        totFis = 0.0
        runLog.important(
            "{assembly:15s} {dTime:10s} {cycle:3s} {bu:5s} {fiss:13s} {cum:13s}".format(
                assembly="Assem. Name",
                dTime="Charge Time",
                cycle="Charge cyc",
                bu="BU",
                fiss="kg fis (full core)",
                cum="Cumulative fis (full, MT)",
            )
        )
        for a in self.getChildren():
            totFis += a.p.chargeFis * self.r.powerMultiplier / 1000.0
            runLog.important(
                "{assembly:15s} {dTime:10f} {cycle:3f} {bu:5.2f} {fiss:13.4f} {cum:13.4f}".format(
                    assembly=a,
                    dTime=a.p.chargeTime,
                    cycle=a.p.chargeCycle,
                    fiss=a.p.chargeFis * self.r.powerMultiplier,
                    bu=a.p.chargeBu,
                    cum=totFis,
                )
            )
        runLog.important(
            "Total full core fissile inventory of {0} is {1:.4E} MT".format(
                self, totFis
            )
        )
