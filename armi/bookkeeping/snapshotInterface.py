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
Controls points during a calculation where snapshots will be triggered, signaling more detailed treatments.

Snapshots are user-defined cycle/timenode points where something special is to be done.
What in particular is done is dependent on the case settings and the collection of active plugins

* At the very basic level,
  third-party code input files are dumped out and stored in special snapshot folders at these times.
  This can be useful when you are sharing third-party input files with another party (e.g. for review or
  collaboration).
* You may want to run extra long-running physics simulations only at a few time points (e.g. BOL, EOL). This
  is useful for detailed transient analysis, or other follow-on analysis.

Snapshots can be requested through the settings: ``dumpSnapshot`` and/or ``defaultSnapshots``.
"""
from armi import interfaces
from armi import runLog
from armi.reactor import locations
from armi import operators


ORDER = interfaces.STACK_ORDER.POSTPROCESSING


def describeInterfaces(cs):
    """Function for exposing interface(s) to other code"""
    return (SnapshotInterface, {})


class SnapshotInterface(interfaces.Interface):
    """Snapshot managerial interface"""

    name = "snapshot"

    def interactBOL(self):
        interfaces.Interface.interactBOL(self)
        if self.cs["defaultSnapshots"]:
            self.activateDefaultSnapshots()

    def interactEveryNode(self, cycle, node):
        snapText = getCycleNodeStamp(cycle, node)  # CCCNNN
        if self.cs["dumpSnapshot"] and snapText in self.cs["dumpSnapshot"]:
            self.o.snapshotRequest(cycle, node)
        if self.cs["dumpLocationSnapshot"]:
            self._dumpLocationSnapshot(cycle, node)

    def activateDefaultSnapshots(self):
        """Figure out and assign some default snapshots (BOL, MOL, EOL)."""
        if self.cs["runType"] == operators.RunTypes.EQUILIBRIUM:
            snapTimeCycleNodePairs = self._getSnapTimesEquilibrium()
        else:
            snapTimeCycleNodePairs = self._getSnapTimesNormal()

        snapText = ["{0:03d}{1:03d}".format(c, n) for c, n in snapTimeCycleNodePairs]

        for snapT in snapText:
            if snapT not in self.cs["dumpSnapshot"]:
                runLog.info(
                    "Adding default snapshot {0} to snapshot queue.".format(snapT)
                )
                self.cs["dumpSnapshot"] = self.cs["dumpSnapshot"] + [snapT]

    def _getSnapTimesEquilibrium(self):
        """Set BOEC, MOEC, EOEC snapshots."""
        if not self.cs["eqToDatabaseOnlyWhenConverged"]:
            raise ValueError(
                "Cannot create default snapshots when `eqToDatabaseOnlyWhenConverged` setting is active"
            )
        return [(0, 0), (0, self.cs["burnSteps"] // 2), (0, self.cs["burnSteps"])]

    def _getSnapTimesNormal(self):
        try:
            curCycle = self.r.p.cycle
        except AttributeError:  # none has no attribute getParam (no reactor for whatever reason)
            curCycle = 0
        eolCycle = self.cs["nCycles"] - 1

        molCycle = eolCycle // 2
        bolCycle = 0

        snapTimeCycleNodePairs = []
        if bolCycle >= curCycle:
            snapTimeCycleNodePairs.append([bolCycle, 0])
        if molCycle >= curCycle:
            snapTimeCycleNodePairs.append([molCycle, 0])
        if eolCycle >= curCycle:
            snapTimeCycleNodePairs.append([eolCycle, self.cs["burnSteps"]])
        return snapTimeCycleNodePairs

    def _dumpLocationSnapshot(self, cycle, node):
        r"""Debugging ability to dump whatever assembly is in a certain location at a certain time
        to a pickled assembly. """
        snapText = "{0:03d}{1:03d}".format(cycle, node)
        for locSnapTxt in self.cs["dumpLocationSnapshot"]:
            locLabel, cnLabel = locSnapTxt.split("_")
            if cnLabel != snapText:
                continue
            runLog.extra(
                "Dumping requested location snapshot to " + locSnapTxt + ".dat "
            )
            locObj = locations.locationFactory(self.r.core.geomType)()
            locObj.fromLabel(locLabel)
            a = self.r.core.whichAssemblyIsIn(locObj.i1, locObj.i2)
            a.dump(locSnapTxt + ".dat")  # pylint: disable=no-member


def extractCycleNodeFromStamp(stamp):
    """
    Returns cycle and node from a CCCNNN stamp

    See Also
    --------
    getCycleNodeStamp : the opposite
    """
    cycle = int(stamp[:3])
    node = int(stamp[3:])
    return cycle, node


def getCycleNodeStamp(cycle, node):
    """
    Returns a CCCNNN stamp for this cycle and node.

    Useful for comparing the current cycle/node with requested snapshots in the settings

    See Also
    --------
    isRequestedDetailPoint : compares a cycle,node to the dumpSnapshots list.
    extractCycleNodeFromStamp : does the opposite
    """
    snapText = "{0:03d}{1:03d}".format(cycle, node)
    return snapText
