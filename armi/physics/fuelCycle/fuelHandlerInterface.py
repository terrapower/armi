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

"""A place for the FuelHandler's Interface."""

from armi import interfaces, runLog
from armi.physics.fuelCycle import fuelHandlerFactory
from armi.physics.fuelCycle.settings import (
    CONF_PLOT_SHUFFLE_ARROWS,
    CONF_RUN_LATTICE_BEFORE_SHUFFLING,
    CONF_SHUFFLE_LOGIC,
    CONF_SHUFFLE_SEQUENCE_FILE,
)
from armi.utils import plotting


class FuelHandlerInterface(interfaces.Interface):
    """
    Moves and/or processes fuel in a Standard Operator.

    Fuel management traditionally runs at the beginning of a cycle, before
    power or temperatures have been updated. This allows pre-run fuel management
    steps for highly customized fuel loadings. In typical runs, no fuel management
    occurs at the beginning of the first cycle and the as-input state is left as is.

    .. impl:: ARMI provides a shuffle logic interface.
        :id: I_ARMI_SHUFFLE
        :implements: R_ARMI_SHUFFLE

        This interface allows for a user to define custom shuffle logic that
        modifies to the core model. Being based on the :py:class:`~armi.interfaces.Interface`
        class, it has direct access to the current core model.

        User logic is able to be executed from within the
        :py:meth:`~armi.physics.fuelCycle.fuelHandlerInterface.FuelHandlerInterface.manageFuel` method,
        which will use the :py:meth:`~armi.physics.fuelCycle.fuelHandlerFactory.fuelHandlerFactory`
        to search for a Python file or importable module specified by the case setting ``shuffleLogic``.
        If it exists, the fuel handler with name specified by the user via the ``fuelHandlerName``
        case setting will be imported, and any actions in its ``outage`` method
        will be executed at the :py:meth:`~armi.physics.fuelCycle.fuelHandlerInterface.FuelHandlerInterface.interactBOC`
        hook.

        If no class with the name specified by the ``fuelHandlerName`` setting is found
        in the module or file specified by ``shuffleLogic``, an error is returned.

        See the user manual for how the custom shuffle logic module or file should be constructed.
    """

    name = "fuelHandler"

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)
        # assembly name key, (x, y) values. used for making shuffle arrows.
        self.oldLocations = {}
        # need order due to nature of moves but with fast membership tests
        self.moved = []
        self.cycle = 0

    @staticmethod
    def specifyInputs(cs):
        files = {
            cs.getSetting(settingName): [
                cs[settingName],
            ]
            for settingName in [CONF_SHUFFLE_LOGIC, "explicitRepeatShuffles", CONF_SHUFFLE_SEQUENCE_FILE]
            if cs[settingName]
        }
        return files

    def interactBOC(self, cycle=None):
        """
        Move and/or process fuel.

        Also, if requested, first have the lattice physics system update XS.
        """
        # if lattice physics is requested, compute it here instead of after fuel management.
        # This enables XS to exist for branch searching, etc.
        mc2 = self.o.getInterface(purpose="latticePhysics")
        xsgm = self.o.getInterface("xsGroups")
        if mc2 and self.cs[CONF_RUN_LATTICE_BEFORE_SHUFFLING]:
            runLog.extra(
                f'Running {mc2} lattice physics before fuel management due to the "{CONF_RUN_LATTICE_BEFORE_SHUFFLING}"'
                " setting being activated."
            )
            xsgm.interactBOC(cycle=cycle)
            mc2.interactBOC(cycle=cycle)

        if self.enabled() and (
            self.cs["loadStyle"] != "fromDB" or self.cs["startNode"] == 0 or (self.cs["startCycle"] != cycle)
        ):
            # in restart cases, only do this if restarting at BOC to avoid duplicating shuffles
            # the logic to accomplish this is a bit long because we don't pass the
            # timeNode into interactBOC hooks. Otherwise it would be much easier
            # to determine when to call this or not
            self.manageFuel(cycle)

    def interactEOC(self, cycle=None):
        if self.r.excore.get("sfp") is not None:
            runLog.extra(f"There are {len(self.r.excore['sfp'])} assemblies in the Spent Fuel Pool")

    def interactEOL(self):
        """Make reports at EOL."""
        self.makeShuffleReport()

    def manageFuel(self, cycle):
        """Perform the fuel management for this cycle."""
        fh = fuelHandlerFactory.fuelHandlerFactory(self.o)
        fh.prepCore()
        fh.prepShuffleMap()
        # take note of where each assembly is located before the outage
        # for mapping after the outage
        self.r.core.locateAllAssemblies()
        shuffleFactors, _ = fh.getFactorList(cycle)
        fh.outage(shuffleFactors)  # move the assemblies around

        if self.cs[CONF_PLOT_SHUFFLE_ARROWS]:
            arrows = fh.makeShuffleArrows()
            plotting.plotFaceMap(
                self.r.core,
                "percentBu",
                labelFmt=None,
                fName="{}.shuffles_{}.png".format(self.cs.caseTitle, self.r.p.cycle),
                shuffleArrows=arrows,
            )

    def makeShuffleReport(self):
        """
        Create a data file listing all the shuffles that occurred in a case.

        This can be used to export shuffling to an external code or to
        perform explicit repeat shuffling in a restart.
        It creates a ``*SHUFFLES.txt`` file based on the Reactor.moves structure

        See Also
        --------
        readMoves : reads this file and parses it.
        """
        fname = self.cs.caseTitle + "-SHUFFLES.txt"
        out = open(fname, "w")
        for cycle in range(self.cs["nCycles"]):
            # do cycle+1 because cycle 0 at t=0 isn't usually interesting
            # remember, we put cycle 0 in so we could do BOL branch searches.
            # This also syncs cycles up with external physics kernel cycles.
            out.write("Before cycle {0}:\n".format(cycle + 1))
            movesThisCycle = self.r.core.moves.get(cycle)
            if movesThisCycle is not None:
                for move in movesThisCycle:
                    enrichLine = " ".join(["{0:.8f}".format(enrich) for enrich in move.enrichList])
                    if move.fromLoc in ["Delete", "SFP"]:
                        # this is a re-entering assembly. Give extra info so repeat shuffles can handle it
                        out.write(
                            "{0} moved to {1} with assembly type {2} ANAME={4} with enrich list: {3}\n".format(
                                move.fromLoc,
                                move.toLoc,
                                move.assemType,
                                enrichLine,
                                move.nameAtDischarge,
                            )
                        )
                    else:
                        # skip extra info. regular expression in readMoves will handle it just fine.
                        out.write(
                            "{0} moved to {1} with assembly type {2} with enrich list: {3}\n".format(
                                move.fromLoc, move.toLoc, move.assemType, enrichLine
                            )
                        )
            out.write("\n")
        out.close()

    def workerOperate(self, cmd):
        """Delegate mpi command to the fuel handler object."""
        fh = fuelHandlerFactory.fuelHandlerFactory(self.o)
        return fh.workerOperate(cmd)
