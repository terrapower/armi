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

"""
The database interface provides a way to save the reactor state to a file, throughout
a simulation.
"""
import copy
import os
import pathlib
import time
from typing import (
    Optional,
    Tuple,
    Sequence,
    MutableSequence,
)

from armi import context
from armi import interfaces
from armi import runLog
from armi.bookkeeping.db.database3 import Database3, getH5GroupName
from armi.reactor.parameters import parameterDefinitions
from armi.reactor.composites import ArmiObject
from armi.bookkeeping.db.typedefs import History, Histories
from armi.utils import getPreviousTimeNode, getStepLengths
from armi.settings.fwSettings.databaseSettings import (
    CONF_SYNC_AFTER_WRITE,
    CONF_FORCE_DB_PARAMS,
)


ORDER = interfaces.STACK_ORDER.BOOKKEEPING


def describeInterfaces(cs):
    """Function for exposing interface(s) to other code"""
    return (DatabaseInterface, {"enabled": cs["db"]})


class DatabaseInterface(interfaces.Interface):
    """
    Handles interactions between the ARMI data model and the persistent data storage
    system.

    This reads/writes the ARMI state to/from the database and helps derive state
    information that can be derived.
    """

    name = "database"

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)
        self._db = None
        self._dbPath: Optional[pathlib.Path] = None

        if cs[CONF_FORCE_DB_PARAMS]:
            toSet = {paramName: set() for paramName in cs[CONF_FORCE_DB_PARAMS]}
            for (name, _), pDef in parameterDefinitions.ALL_DEFINITIONS.items():
                if name in toSet.keys():
                    toSet[name].add(pDef)

            for name, pDefs in toSet.items():
                runLog.info(
                    "Forcing parameter {} to be written to the database, per user "
                    "input".format(name)
                )
                for pDef in pDefs:
                    pDef.saveToDB = True

    def __repr__(self):
        return "<{} '{}' {} >".format(
            self.__class__.__name__, self.name, repr(self._db)
        )

    @property
    def database(self):
        """
        Presents the internal database object, if it exists.
        """
        if self._db is not None:
            return self._db
        else:
            raise RuntimeError(
                "The Database interface has not yet created a database "
                "object. InteractBOL or loadState must be called first."
            )

    def interactBOL(self):
        """Initialize the database if the main interface was not available. (Begining of Life)"""
        if not self._db:
            self.initDB()

    def initDB(self, fName: Optional[os.PathLike] = None):
        """
        Open the underlying database to be written to, and write input files to DB.

        Notes
        -----
        Main Interface calls this so that the database is available as early as
        possible in the run. The database interface interacts near the end of the
        interface stack (so that all the parameters have been updated) while the Main
        Interface interacts first.
        """
        if fName is None:
            self._dbPath = pathlib.Path(self.cs.caseTitle + ".h5")
        else:
            self._dbPath = pathlib.Path(fName)

        if self.cs["reloadDBName"].lower() == str(self._dbPath).lower():
            raise ValueError(
                "It appears that reloadDBName is the same as the case "
                "title. This could lead to data loss! Rename the reload DB or the "
                "case."
            )
        self._db = Database3(self._dbPath, "w")
        self._db.open()

        # Grab geomString here because the DB-level has no access to the reactor or
        # blueprints or anything.
        # There's not always a geomFile; we are moving towards the core grid definition
        # living in the blueprints themselves. In this case, the db doesnt need to store
        # a geomFile at all.
        if self.cs["geomFile"]:
            with open(os.path.join(self.cs.inputDirectory, self.cs["geomFile"])) as f:
                geomString = f.read()
        else:
            geomString = ""
        self._db.writeInputsToDB(self.cs, geomString=geomString)

    def interactEveryNode(self, cycle, node):
        """
        Write to database.

        DBs should receive the state information of the run at each node.

        Notes
        -----
        - if tight coupling is enabled, the DB will be written in operator.py::Operator::_timeNodeLoop
          via writeDBEveryNode
        """
        if self.o.cs["tightCoupling"]:
            # h5 cant handle overwriting so we skip here and write once the tight coupling loop has completed
            return
        self.writeDBEveryNode(cycle, node)

    def writeDBEveryNode(self, cycle, node):
        """write the database at the end of the time node"""
        # skip writing for last burn step since it will be written at interact EOC
        if node < self.o.burnSteps[cycle]:
            self.r.core.p.minutesSinceStart = (
                time.time() - self.r.core.timeOfStart
            ) / 60.0
            self._db.writeToDB(self.r)
            if self.cs[CONF_SYNC_AFTER_WRITE]:
                self._db.syncToSharedFolder()

    def interactEOC(self, cycle=None):
        """In case anything changed since last cycle (e.g. rxSwing), update DB. (End of Cycle)"""
        # We cannot presume whether we are at EOL based on cycle and cs["nCycles"],
        # since cs["nCycles"] is not a difinitive indicator of EOL; ultimately the
        # Operator has the final say.
        if not self.o.atEOL:
            self.r.core.p.minutesSinceStart = (
                time.time() - self.r.core.timeOfStart
            ) / 60.0
            self._db.writeToDB(self.r)

    def interactEOL(self):
        """DB's should be closed at run's end. (End of Life)"""
        # minutesSinceStarts should include as much of the ARMI run as possible so EOL
        # is necessary, too.
        self.r.core.p.minutesSinceStart = (time.time() - self.r.core.timeOfStart) / 60.0
        self._db.writeToDB(self.r)
        self._db.close(True)

    def interactError(self):
        r"""Get shutdown state information even if the run encounters an error"""
        try:
            self.r.core.p.minutesSinceStart = (
                time.time() - self.r.core.timeOfStart
            ) / 60.0

            # this can result in a double-error if the error occurred in the database
            # writing
            self._db.writeToDB(self.r, "error")
            self._db.close(False)
        except:  # pylint: disable=bare-except; we're already responding to an error
            pass

    def interactDistributeState(self) -> None:
        """
        Reconnect to pre-existing database.

        DB is created and managed by the primary node only but we can still connect to it
        from workers to enable things like history tracking.
        """
        if context.MPI_RANK > 0:
            # DB may not exist if distribute state is called early.
            if self._dbPath is not None and os.path.exists(self._dbPath):
                self._db = Database3(self._dbPath, "r")
                self._db.open()

    def distributable(self):
        return self.Distribute.SKIP

    def prepRestartRun(self):
        """
        Load the data history from the database requested in the case setting
        `reloadDBName`.

        Reactor state is put at the cycle/node requested in the case settings
        `startCycle` and `startNode`, having loaded the state from all cycles prior
        to that in the requested database.

        Notes
        -----
        Mixing the use of simple vs detailed cycles settings is allowed, provided
        that the cycle histories prior to `startCycle`/`startNode` are equivalent.
        """
        reloadDBName = self.cs["reloadDBName"]
        runLog.info(
            f"Merging database history from {reloadDBName} for restart analysis."
        )
        startCycle = self.cs["startCycle"]
        startNode = self.cs["startNode"]

        with Database3(reloadDBName, "r") as inputDB:
            loadDbCs = inputDB.loadCS()

            # pull the history up to the cycle/node prior to `startCycle`/`startNode`
            dbCycle, dbNode = getPreviousTimeNode(
                startCycle,
                startNode,
                self.cs,
            )

            # check that cycle histories are equivalent up to this point
            self._checkThatCyclesHistoriesAreEquivalentUpToRestartTime(
                loadDbCs, dbCycle, dbNode
            )

            self._db.mergeHistory(inputDB, startCycle, startNode)
        self.loadState(dbCycle, dbNode)

    def _checkThatCyclesHistoriesAreEquivalentUpToRestartTime(
        self, loadDbCs, dbCycle, dbNode
    ):
        dbStepLengths = getStepLengths(loadDbCs)
        currentCaseStepLengths = getStepLengths(self.cs)
        dbStepHistory = []
        currentCaseStepHistory = []
        try:
            for cycleIdx in range(dbCycle + 1):
                if cycleIdx == dbCycle:
                    # truncate it at dbNode
                    dbStepHistory.append(dbStepLengths[cycleIdx][:dbNode])
                    currentCaseStepHistory.append(
                        currentCaseStepLengths[cycleIdx][:dbNode]
                    )
                else:
                    dbStepHistory.append(dbStepLengths[cycleIdx])
                    currentCaseStepHistory.append(currentCaseStepLengths[cycleIdx])
        except IndexError:
            runLog.error(
                f"DB cannot be loaded to this time: cycle={dbCycle}, node={dbNode}"
            )
            raise

        if dbStepHistory != currentCaseStepHistory:
            raise ValueError(
                "The cycle history up to the restart cycle/node must be equivalent."
            )

    # TODO: The use of "yield" here is suspect.
    def _getLoadDB(self, fileName):
        """
        Return the database to load from in order of preference.

        Notes
        -----
        If filename is present only returns one database since specifically instructed
        to load from that database.
        """
        if fileName is not None:
            # only yield 1 database if the file name is specified
            if self._db is not None and fileName == self._db._fileName:
                yield self._db
            elif os.path.exists(fileName):
                yield Database3(fileName, "r")
        else:
            if self._db is not None:
                yield self._db
            if os.path.exists(self.cs["reloadDBName"]):
                yield Database3(self.cs["reloadDBName"], "r")

    def loadState(
        self, cycle, timeNode, timeStepName="", fileName=None, updateGlobalAssemNum=True
    ):
        """
        Loads a fresh reactor and applies it to the Operator.

        Notes
        -----
        Will load preferentially from the `fileName` if passed. Otherwise will load from
        existing database in memory or `cs["reloadDBName"]` in that order.

        Raises
        ------
        RuntimeError
            If fileName is specified and that  file does not have the time step.
            If fileName is not specified and neither the database in memory, nor the
            `cs["reloadDBName"]` have the time step specified.
        """
        for potentialDatabase in self._getLoadDB(fileName):
            with potentialDatabase as loadDB:
                if loadDB.hasTimeStep(cycle, timeNode, statePointName=timeStepName):
                    newR = loadDB.load(
                        cycle,
                        timeNode,
                        statePointName=timeStepName,
                        cs=self.cs,
                        allowMissing=True,
                        updateGlobalAssemNum=updateGlobalAssemNum,
                    )
                    self.o.reattach(newR, self.cs)
                    break
        else:
            # reactor was never set so fail
            if fileName:
                raise RuntimeError(
                    "Cannot load state from specified file {} @ {}".format(
                        fileName, getH5GroupName(cycle, timeNode, timeStepName)
                    )
                )
            raise RuntimeError(
                "Cannot load state from <unspecified file> @ {}".format(
                    getH5GroupName(cycle, timeNode, timeStepName)
                )
            )

    def getHistory(
        self,
        comp: ArmiObject,
        params: Optional[Sequence[str]] = None,
        timeSteps: Optional[MutableSequence[Tuple[int, int]]] = None,
        byLocation: bool = False,
    ) -> History:
        """
        Get historical parameter values for a single object.

        This is mostly a wrapper around the same function on the ``Database3`` class,
        but knows how to return the current value as well.

        See Also
        --------
        Database3.getHistory
        """
        # make a copy so that we can potentially remove timesteps without affecting the
        # caller
        timeSteps = copy.copy(timeSteps)
        now = (self.r.p.cycle, self.r.p.timeNode)
        nowRequested = timeSteps is None
        if timeSteps is not None and now in timeSteps:
            nowRequested = True
            timeSteps.remove(now)

        if byLocation:
            history = self.database.getHistoryByLocation(comp, params, timeSteps)
        else:
            history = self.database.getHistory(comp, params, timeSteps)

        if nowRequested:
            for param in params or history.keys():
                if param == "location":
                    history[param][now] = tuple(comp.spatialLocator.indices)
                else:
                    history[param][now] = comp.p[param]

        return history

    def getHistories(
        self,
        comps: Sequence[ArmiObject],
        params: Optional[Sequence[str]] = None,
        timeSteps: Optional[MutableSequence[Tuple[int, int]]] = None,
        byLocation: bool = False,
    ) -> Histories:
        """
        Get historical parameter values for one or more objects.

        This is mostly a wrapper around the same function on the ``Database3`` class,
        but knows how to return the current value as well.

        See Also
        --------
        Database3.getHistories
        """
        now = (self.r.p.cycle, self.r.p.timeNode)
        nowRequested = timeSteps is None
        if timeSteps is not None:
            # make a copy so that we can potentially remove timesteps without affecting
            # the caller
            timeSteps = copy.copy(timeSteps)
        if timeSteps is not None and now in timeSteps:
            nowRequested = True
            timeSteps.remove(now)

        if byLocation:
            histories = self.database.getHistoriesByLocation(comps, params, timeSteps)
        else:
            histories = self.database.getHistories(comps, params, timeSteps)

        if nowRequested:
            for c in comps:
                for param in params or histories[c].keys():
                    if param == "location":
                        histories[c][param][now] = c.spatialLocator.indices
                    else:
                        histories[c][param][now] = c.p[param]

        return histories
