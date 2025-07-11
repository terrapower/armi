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

"""Snapshot Operator."""

from armi import runLog
from armi.operators import operatorMPI


class OperatorSnapshots(operatorMPI.OperatorMPI):
    """
    This operator just loops over the requested snapshots and computes at them.

    These may add CR worth curves, rx coefficients, transient runs etc at these snapshots.
    This operator can be run as a restart, adding new physics to a previous run.
    """

    def __init__(self, cs):
        super().__init__(cs)

        # disable fuel management and optimization
        # disable depletion because we don't want to change number densities for tn's >0 (or any)
        self.disabledInterfaces = ["depletion", "fuelHandler", "optimize"]

    def createInterfaces(self):
        operatorMPI.OperatorMPI.createInterfaces(self)

        for toDisable in self.disabledInterfaces:
            i = self.getInterface(name=toDisable, purpose=toDisable)
            if i:
                i.enabled(False)

    def _mainOperate(self):
        """
        General main loop for ARMI snapshot case.

        Instead of going through all cycles, this goes through just the snapshots.

        See Also
        --------
        Operator._mainOperate : The primary ARMI loop for non-restart cases.
        """
        runLog.important("---- Beginning Snapshot (restart) ARMI Operator Loop ------")

        # run things that happen before a calculation.
        # setups, etc.
        self.interactAllBOL()

        # figure out which snapshots to run in. Parse the CCCNNN settings
        snapshots = [(int(i[:3]), int(i[3:])) for i in self.cs["dumpSnapshot"]]

        # update the snapshot requests if the user chose to load from a specific cycle/node
        dbi = self.getInterface("database")
        # database is excluded since SS writes by itself
        excludeDB = ("database",)
        for ssCycle, ssNode in snapshots:
            runLog.important("Beginning snapshot ({0:02d}, {1:02d})".format(ssCycle, ssNode))
            dbi.loadState(ssCycle, ssNode)

            # need to update reactor power after the database load
            # this is normally handled in operator._cycleLoop
            self.r.core.p.power = self.cs["power"]
            self.r.core.p.powerDensity = self.cs["powerDensity"]

            halt = self.interactAllBOC(self.r.p.cycle)
            if halt:
                break

            # database is excluded since it writes after coupled
            self.interactAllEveryNode(ssCycle, ssNode, excludedInterfaceNames=excludeDB)
            self._performTightCoupling(ssCycle, ssNode, writeDB=False)
            # tight coupling is done, now write to DB
            dbi.writeDBEveryNode()

            self.interactAllEOC(self.r.p.cycle)

        # run things that happen at EOL, like reports, plotters, etc.
        self.interactAllEOL(excludedInterfaceNames=excludeDB)
        dbi.closeDB()  # dump the database to file
        runLog.important("Done with ARMI snapshots case.")

    @staticmethod
    def setStateToDefault(cs):
        """Update the state of ARMI to fit the kind of run this operator manages."""
        from armi.operators.runTypes import RunTypes

        return cs.modified(newSettings={"runType": RunTypes.STANDARD})

    @property
    def atEOL(self):
        """
        Notes
        -----
        This operator's atEOL method behaves very differently than other operators.
        The idea is that snapshots don't really have an EOL since they are independent of
        chrological order and may or may not contain the last time node from the load database.
        """
        return False
