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

from armi.operators import operatorMPI
from armi import runLog
from armi import utils


class OperatorSnapshots(operatorMPI.OperatorMPI):
    """
    This operator just loops over the requested snapshots and computes at them.

    These may add CR worth curves, rx coefficients, transient runs etc at these snapshots.
    This operator can be run as a restart, adding new physics to a previous run.

    """

    def createInterfaces(self):
        operatorMPI.OperatorMPI.createInterfaces(self)
        # disable fuel management and optimization
        # disable depletion because we don't want to change number densities for tn's >0 (or any)
        for toDisable in ["fuelHandler", "optimize", "depletion"]:
            i = self.getInterface(toDisable)
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

        lastTimeStep = snapshots[-1]
        for ssCycle, ssNode in snapshots:
            runLog.important(
                "Beginning snapshot ({0:02d}, {1:02d})".format(ssCycle, ssNode)
            )
            dbi.loadState(ssCycle, ssNode)
            halt = self.interactAllBOC(self.r.p.cycle)
            if halt:
                break

            # database is excluded since it writes at EOC
            self.interactAllEveryNode(
                ssCycle, ssNode, excludedInterfaceNames=("database",)
            )

            # database is excluded at last snapshot since it writes at EOL
            exclude = ("database",) if (ssCycle, ssNode) == lastTimeStep else ()
            self.interactAllEOC(self.r.p.cycle, excludedInterfaceNames=exclude)

        # run things that happen at EOL
        # like reports, plotters, etc.
        self.interactAllEOL()
        runLog.important("Done with ARMI snapshots case.")

    @staticmethod
    def setStateToDefault(cs):
        """Update the state of ARMI to fit the kind of run this operator manages"""
        from armi import operators

        cs["runType"] = operators.RunTypes.SNAPSHOTS
