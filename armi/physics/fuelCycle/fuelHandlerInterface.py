# Copyright 2022 TerraPower, LLC
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

"""A place for the FuelHandler's Interface"""


from armi import interfaces, runLog
from armi.utils import plotting
from armi.physics.fuelCycle import fuelHandlerFactory


class FuelHandlerInterface(interfaces.Interface):
    """
    Moves and/or processes fuel in a Standard Operator.

    Fuel management traditionally runs at the beginning of a cycle, before
    power or temperatures have been updated. This allows pre-run fuel management
    steps for highly customized fuel loadings. In typical runs, no fuel management
    occurs at the beginning of the first cycle and the as-input state is left as is.
    """

    name = "fuelHandler"

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)
        self.cycle = 0
        # assembly name key, (x, y) values. used for making shuffle arrows.
        self.oldLocations = {}
        # need order due to nature of moves but with fast membership tests
        self.moved = []
        # filled during summary of EOC time in years of each cycle (time at which shuffling occurs)
        self.cycleTime = {}

    @staticmethod
    def specifyInputs(cs):
        files = {
            cs.getSetting(settingName): [
                cs[settingName],
            ]
            for settingName in ["shuffleLogic", "explicitRepeatShuffles"]
            if cs[settingName]
        }
        return files

    def interactBOC(self, cycle=None):
        """
        Beginning of cycle hook. Initiate all cyclical fuel management processes.

        If requested, first have the lattice physics system update XS.
        """
        # if requested, compute lattice physics here instead of after fuel management.
        # This enables XS to exist for branch searching, etc.
        mc2 = self.o.getInterface(function="latticePhysics")
        if mc2 and self.cs["runLatticePhysicsBeforeShuffling"]:
            runLog.extra(
                'Running {0} lattice physics before fuel management due to the "runLatticePhysicsBeforeShuffling"'
                " setting being activated.".format(mc2)
            )
            mc2.interactBOC(cycle=cycle)

        if self.enabled():
            self.manageFuel(cycle)
        self.validateLocations()

    def interactEOC(self, cycle=None):
        """
        End of cycle hook. Record cycle time and report number of assemblies in SFP.
        """
        # keep track of the EOC time in years.
        self.cycleTime[cycle] = self.r.p.time
        runLog.extra(
            "There are {} assemblies in the Spent Fuel Pool".format(
                len(self.r.core.sfp)
            )
        )

    def interactEOL(self):
        """
        End of life hook. Generate operator life shuffle report.
        """
        self.makeShuffleReport()

    def manageFuel(self, cycle):
        """
        Perform the fuel management for a given cycle.
        """
        fh = fuelHandlerFactory.fuelHandlerFactory(self.o)
        fh.preoutage()
        ## is the factor list useful at this point?
        shuffleFactors = fh.getFactorList(cycle)
        fh.outage(shuffleFactors)

        if self.cs["plotShuffleArrows"]:
            arrows = fh.makeShuffleArrows()
            plotting.plotFaceMap(
                self.r.core,
                "percentBu",
                labelFmt=None,
                fName="{}.shuffles_{}.png".format(self.cs.caseTitle, self.r.p.cycle),
                shuffleArrows=arrows,
            )
            plotting.close()

    def validateLocations(self):
        """
        Check that all assemblies have a unique location in the core.
        """
        locations = [
            assembly.getLocation()
            for assembly in self.r.core.getAssemblies(includeAll=True)
            if assembly.getLocation()[:3].isnumeric()
        ]

        if len(locations) != len(set(locations)):
            duplicateLocations = set([i for i in locations if locations.count(i) > 1])
            raise ValueError(
                "Two or more assemblies share the same core location ({})".format(
                    duplicateLocations
                )
            )

    def makeShuffleReport(self):
        """
        Create a data file listing all the shuffles that occurred in a case.

        This can be used to export shuffling to an external code or to perform
        explicit repeat shuffling in a restart. It creates a *SHUFFLES.txt file
        based on the Reactor.moveList structure

        See Also
        --------
        readMoves : reads this file and parses it.

        """
        fname = self.cs.caseTitle + "-SHUFFLES.txt"
        out = open(fname, "w")
        for cycle in range(self.cs["nCycles"]):
            # Write cycle header to the report
            out.write("Before cycle {0}:\n".format(cycle + 1))
            # Pull move list for the cycle
            movesThisCycle = self.r.core.moveList.get(cycle)
            if movesThisCycle is not None:
                for (
                    fromLoc,
                    toLoc,
                    _,
                    _,
                    chargeEnrich,
                    assemblyType,
                    movingAssemName,
                ) in movesThisCycle:
                    if not fromLoc == toLoc:
                        enrichLine = " ".join(
                            ["{0:.8f}".format(enrich) for enrich in chargeEnrich]
                        )
                        out.write(
                            "{0} moved from {1} to {2} with assembly type {3} with enrich list: {4}\n"
                            "".format(
                                movingAssemName,
                                fromLoc,
                                toLoc,
                                assemblyType,
                                enrichLine,
                            )
                        )
                for (
                    _,
                    toLoc,
                    fromRot,
                    toRot,
                    _,
                    _,
                    movingAssemName,
                ) in movesThisCycle:
                    if not fromRot == toRot:
                        # If assembly is entering the core, provide extra information
                        out.write(
                            "{0} at {1} was rotated from {2} to {3}\n"
                            "".format(
                                movingAssemName,
                                toLoc,
                                fromRot,
                                toRot,
                            )
                        )
            out.write("\n")
        out.close()

    def workerOperate(self, cmd):
        """Delegate mpi command to the fuel handler object."""
        fh = fuelHandlerFactory.fuelHandlerFactory(self.o)
        return fh.workerOperate(cmd)
