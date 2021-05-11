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
The bookkeeping package handles data persistence, reporting, and some debugging.
"""
from armi import plugins


class BookkeepingPlugin(plugins.ArmiPlugin):
    @staticmethod
    @plugins.HOOKIMPL
    def exposeInterfaces(cs):
        from armi.bookkeeping.db import database3
        from armi.bookkeeping import historyTracker
        from armi.bookkeeping import memoryProfiler
        from armi.bookkeeping import mainInterface
        from armi.bookkeeping import snapshotInterface
        from armi.bookkeeping.report import reportInterface

        interfaceInfo = []
        interfaceInfo += plugins.collectInterfaceDescriptions(mainInterface, cs)
        interfaceInfo += plugins.collectInterfaceDescriptions(database3, cs)
        interfaceInfo += plugins.collectInterfaceDescriptions(historyTracker, cs)
        interfaceInfo += plugins.collectInterfaceDescriptions(memoryProfiler, cs)
        interfaceInfo += plugins.collectInterfaceDescriptions(reportInterface, cs)
        interfaceInfo += plugins.collectInterfaceDescriptions(snapshotInterface, cs)

        return interfaceInfo

    @staticmethod
    @plugins.HOOKIMPL
    def defineEntryPoints():
        from armi.cli import database, copyDB
        from armi.bookkeeping import visualization

        entryPoints = []
        # Disabling ConvertDB because there is no other format to convert between. The
        # entry point is rather general so leaving this here so we don't forget about it
        # entryPoints.append(database.ConvertDB)
        entryPoints.append(database.ExtractInputs)
        entryPoints.append(database.InjectInputs)
        entryPoints.append(copyDB.CopyDB)
        entryPoints.append(visualization.VisFileEntryPoint)

        return entryPoints

    @staticmethod
    @plugins.HOOKIMPL
    def defineCaseDependencies(case, suite):
        if case.cs["loadStyle"] == "fromDB":
            # the ([^\/]) capture basically gets the file name portion and excludes any
            # directory separator
            return case.getPotentialParentFromSettingValue(
                case.cs["reloadDBName"],
                r"^(?P<dirName>.*[\/\\])?(?P<title>[^\/\\]+?)(\.[hH]5)?$",
            )
        return None

    @staticmethod
    @plugins.HOOKIMPL
    def mpiActionRequiresReset(cmd) -> bool:
        """
        Prevent reactor resets after certain mpi actions.

        * Memory profiling is small enough that we don't want to reset
        * distributing state would be undone by this so we don't want that.

        See Also
        --------
        armi.operators.operatorMPI.OperatorMPI.workerOperate
        """
        # pylint: disable=import-outside-toplevel ; avoid cyclic imports
        from armi.bookkeeping import memoryProfiler
        from armi import mpiActions

        if isinstance(cmd, mpiActions.MpiAction):
            for donotReset in (
                mpiActions.DistributeStateAction,
                mpiActions.DistributionAction,
                memoryProfiler.PrintSystemMemoryUsageAction,
                memoryProfiler.ProfileMemoryUsageAction,
            ):
                if isinstance(cmd, donotReset):
                    return False

        return True
