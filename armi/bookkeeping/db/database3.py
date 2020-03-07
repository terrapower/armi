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
ARMI Database implementation, version 3.

This Implementation of the database is a significant departure from the previous. One of
the foundational concepts in this version is that a reactor model should be fully
recoverable from the database itself; all the way down to the component level. As a
result, the structure of the underlying data is bound to the hierarchical Composite
Reactor Model, rather than an ad hoc collection of Block parameter fields and other
parameters. Furthermore, this format is intended to be more dynamic, permitting as-yet
undeveloped levels and classes in the Composite Reactor Model to be supported as they
are added. More high-level discussion is contained in :doc:`/user/outputs/database`.

The most important contents of this module are the :py:class:`DatabaseInterface`, the
:py:class:`Database3` class, the :py:class:`Layout` class, and the special data
packing/unpacking functions. The ``Database3`` class contains most of the functionality
for interacting with the underlying data. This includes things like dumping a Reactor
state to the database and loading it back again, as well as extracting historical data
for a given object or collection of object from the database file. When interacting with
the database file, the ``Layout`` class is used to help map the hierarchical Composite
Reactor Model to the flat representation in the database.

Minor revision changelog
------------------------
 - 3.1: Improve the handling of reading/writing grids.

 - 3.2: Change the strategy for storing large attributes from using an Object Reference
   to an external dataset to using a special string starting with an "@" symbol (e.g.,
   "@/c00n00/attrs/5_linkedDims"). This was done to support copying time node datasets
   from one file to another without invalidating the references. Support is maintained
   for reading previous versions, and for performing a ``mergeHistory()`` and converting
   to the new reference strategy, but the old version cannot be written.

"""
import collections
import copy
import io
import itertools
import os
import pathlib
import re
import sys
import time
import shutil
from typing import (
    Optional,
    Tuple,
    Dict,
    Any,
    List,
    Sequence,
    MutableSequence,
    Generator,
)

import numpy
import h5py

import armi
from armi import interfaces
from armi import runLog
from armi import settings
from armi.reactor import parameters
from armi.reactor.parameters import parameterCollections
from armi.reactor.flags import Flags
from armi.reactor.reactors import Reactor, Core
from armi.reactor import assemblies
from armi.reactor.assemblies import Assembly
from armi.reactor.blocks import Block
from armi.reactor.components import Component
from armi.reactor.composites import ArmiObject
from armi.reactor import grids
from armi.bookkeeping.db.types import History, Histories
from armi.bookkeeping.db import database
from armi.reactor import geometry
from armi.utils.textProcessors import resolveMarkupInclusions

ORDER = interfaces.STACK_ORDER.BOOKKEEPING
DB_VERSION = "3.2"

ATTR_LINK = re.compile("^@(.*)$")

_SERIALIZER_NAME = "serializerName"
_SERIALIZER_VERSION = "serializerVersion"


def getH5GroupName(cycle, timeNode, statePointName=None):
    return "c{:0>2}n{:0>2}{}".format(cycle, timeNode, statePointName or "")


def describeInterfaces(cs):
    """Function for exposing interface(s) to other code"""
    return (DatabaseInterface, {"enabled": cs["db"]})


def updateGlobalAssemblyNum(r):
    assemNum = r.core.p.maxAssemNum
    if assemNum is not None:
        assemblies.setAssemNumCounter(int(assemNum + 1))
    else:
        raise ValueError("Could not load maxAssemNum from the database")


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
        """Initialize the database if the main interface was not available."""
        if not self._db:
            self.initDB()

    def initDB(self):
        """
        Open the underlying database to be written to, and write input files to DB.

        Notes
        -----
        Main Interface calls this so that the database is available as early as
        possible in the run. The database interface interacts near the end of the
        interface stack (so that all the parameters have been updated) while the Main
        Interface interacts first.
        """
        if self.cs["reloadDBName"].lower() == (self.cs.caseTitle + ".h5").lower():
            raise ValueError(
                "It appears that reloadDBName is the same as the case "
                "title. This could lead to data loss! Rename the reload DB or the "
                "case."
            )
        self._db = Database3(self.cs.caseTitle + ".h5", "w")
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
        """
        # skip writing for last burn step since it will be written at interact EOC
        if node < self.cs["burnSteps"]:
            self.r.core.p.minutesSinceStart = (
                time.time() - self.r.core.timeOfStart
            ) / 60.0
            self._db.writeToDB(self.r)

    def interactEOC(self, cycle=None):
        """In case anything changed since last cycle (e.g. rxSwing), update DB. """
        # We cannot presume whether we are at EOL based on cycle and cs["nCycles"],
        # since cs["nCycles"] is not a difinitive indicator of EOL; ultimately the
        # Operator has the final say.
        if not self.o.atEOL:
            self.r.core.p.minutesSinceStart = (
                time.time() - self.r.core.timeOfStart
            ) / 60.0
            self._db.writeToDB(self.r)

    def interactEOL(self):
        """DB's should be closed at run's end. """
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

    def distributable(self):
        return self.Distribute.SKIP

    def prepRestartRun(self, dbCycle, dbNode):
        """Load the data history from the database being restarted from."""
        reloadDBName = self.cs["reloadDBName"]
        runLog.info(
            f"Merging database history from {reloadDBName} for restart analysis."
        )
        with Database3(reloadDBName, "r") as inputDB:
            loadDbCs = inputDB.loadCS()

            # Not beginning or end of cycle so burnSteps matter to get consistent time.
            isMOC = self.cs["startNode"] not in (0, loadDbCs["burnSteps"])
            if loadDbCs["burnSteps"] != self.cs["burnSteps"] and isMOC:
                raise ValueError(
                    "Time nodes per cycle are inconsistent between loadDB and "
                    "current case settings. This will create a mismatch in the "
                    "total time per cycle for the load cycle. Change current case "
                    "settings to {0} steps per node, or set `startNode` == 0 or {0} "
                    "so that it loads the BOC or EOC of the load database."
                    "".format(loadDbCs["burnSteps"])
                )

            self._db.mergeHistory(inputDB, self.cs["startCycle"], self.cs["startNode"])
        self.loadState(dbCycle, dbNode)

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
                        bp=self.r.blueprints,
                    )
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
                "Cannot load state @ {}".format(
                    getH5GroupName(cycle, timeNode, timeStepName)
                )
            )

        if updateGlobalAssemNum:
            updateGlobalAssemblyNum(newR)

        self.o.reattach(newR, self.cs)

    def getHistory(
        self,
        comp: ArmiObject,
        params: Optional[Sequence[str]] = None,
        timeSteps: Optional[MutableSequence[Tuple[int, int]]] = None,
    ) -> History:
        """
        Get historical parameter values for a single object.

        This is mostly a wrapper around the same function on the ``Database3`` class,
        but knows how to return the current value as well.

        See Also
        --------
        Database3.getHistory
        """
        now = (self.r.p.cycle, self.r.p.timeNode)
        nowRequested = timeSteps is None
        if timeSteps is not None and now in timeSteps:
            nowRequested = True
            timeSteps.remove(now)

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
    ) -> Histories:
        """
        Get historical parameter values for one or more objects.

        This is mostly a wrapper around the same fumction on the ``Database3`` class,
        but knows how to return the current value as well.

        See Also
        --------
        Database3.getHistories
        """
        now = (self.r.p.cycle, self.r.p.timeNode)
        nowRequested = timeSteps is None
        if timeSteps is not None:
            timeSteps = copy.copy(timeSteps)
        if timeSteps is not None and now in timeSteps:
            nowRequested = True
            timeSteps.remove(now)

        histories = self.database.getHistories(comps, params, timeSteps)

        if nowRequested:
            for c in comps:
                for param in params or histories[c].keys():
                    if param == "location":
                        histories[c][param][now] = c.spatialLocator.indices
                    else:
                        histories[c][param][now] = c.p[param]

        return histories


class Database3(database.Database):
    """
    Version 3 of the ARMI Database, handling serialization and loading of Reactor states.

    This implementation of the database pushes all objects in the Composite Reactor
    Model into the database. This process is aided by the ``Layout`` class, which
    handles the packing and unpacking of the structure of the objects, their
    relationships, and their non-parameter attributes.

    See Also
    --------
    `doc/user/outputs/database` for more details.
    """

    timeNodeGroupPattern = re.compile(r"^c(\d\d)n(\d\d)$")

    def __init__(self, fileName: str, permission: str):
        """
        Create a new Database3 object.

        Parameters
        ----------
        fileName:
            name of the file

        permission:
            file permissions, write ("w") or read ("r")
        """
        self._fileName = fileName
        # No full path yet; we will determine this based on FAST_PATH and permissions
        self._fullPath: Optional[str] = None
        self._permission = permission
        self.h5db: Optional[h5py.File] = None

        # Allows context management on open files.
        # If context management is used on a file that is already open, it will not reopen
        # and it will also not close after leaving that context.
        # This allows the treatment of all databases the same whether they are open or
        # closed.
        self._openCount: int = 0

        if permission == "w":
            self.version = DB_VERSION
        else:
            # will be set upon read
            self._version = None
            self._versionMajor = None
            self._versionMinor = None

    @property
    def version(self):
        return self._version

    @version.setter
    def version(self, value):
        self._version = value
        self._versionMajor, self._versionMinor = (int(v) for v in value.split("."))

    @property
    def versionMajor(self):
        return self._versionMajor

    @property
    def versionMinor(self):
        return self._versionMinor

    def __repr__(self):
        return "<{} {}>".format(
            self.__class__.__name__, repr(self.h5db).replace("<", "").replace(">", "")
        )

    def open(self):
        if self.h5db is not None:
            raise ValueError(
                "This database is already open; make sure to close it "
                "before trying to open it again."
            )
        filePath = self._fileName
        self._openCount += 1

        if self._permission in {"r", "a"}:
            self._fullPath = os.path.abspath(filePath)
            self.h5db = h5py.File(filePath, self._permission)
            self.version = self.h5db.attrs["databaseVersion"]
            return

        if self._permission == "w":
            # assume fast path!
            filePath = os.path.join(armi.FAST_PATH, filePath)
            self._fullPath = os.path.abspath(filePath)

        else:
            runLog.error("Unrecognized file permissions `{}`".format(self._permission))
            raise ValueError(
                "Cannot open database with permission `{}`".format(self._permission)
            )

        runLog.info("Opening database file at {}".format(os.path.abspath(filePath)))
        self.h5db = h5py.File(filePath, self._permission)
        self.h5db.attrs["successfulCompletion"] = False
        self.h5db.attrs["version"] = armi.__version__
        self.h5db.attrs["databaseVersion"] = self.version
        self.h5db.attrs["user"] = armi.USER
        self.h5db.attrs["python"] = sys.version
        self.h5db.attrs["armiLocation"] = os.path.dirname(armi.ROOT)
        self.h5db.attrs["startTime"] = armi.START_TIME
        self.h5db.attrs["machines"] = numpy.array(armi.MPI_NODENAMES).astype("S")

    def close(self, completedSuccessfully=False):
        """
        Close the DB and perform cleanups and auto-conversions.
        """
        self._openCount = 0
        if self.h5db is None:
            return

        if self._permission == "w":
            self.h5db.attrs["successfulCompletion"] = completedSuccessfully
            # a bit redundant to call flush, but with unreliable IO issues, why not?
            self.h5db.flush()

        self.h5db.close()
        self.h5db = None

        if self._permission == "w":
            # move out of the FAST_PATH and into the working directory
            shutil.move(self._fullPath, self._fileName)

    def splitDatabase(
        self, keepTimeSteps: Sequence[Tuple[int, int]], label: str
    ) -> str:
        """
        Discard all data except for specific time steps, retaining old data in a separate file.

        This is useful when performing more exotic analyses, where each "time step" may
        not represent a specific point in time, but something more nuanced. For example,
        equilibrium cases store a new "cycle" for each iteration as it attempts to
        converge the equilibrium cycle. At the end of the run, the last "cycle" is the
        converged equilibrium cycle, whereas the previous cycles constitute the path to
        convergence, which we typically wish to discard before further analysis.

        Parameters
        ----------
        keepTimeSteps
            A collection of the time steps to retain

        label
            An informative label for the backed-up database. Usually something like
            "-all-iterations". Will be interposed between the source name and the ".h5"
            extension.


        Returns
        -------
        str
            The name of the new, backed-up database file.
        """
        if self.h5db is None:
            raise ValueError("There is no open database to split.")

        self.h5db.close()

        backupDBPath = os.path.abspath(label.join(os.path.splitext(self._fileName)))
        runLog.info("Retaining full database history in {}".format(backupDBPath))
        if self._fullPath is not None:
            shutil.move(self._fullPath, backupDBPath)

        self.h5db = h5py.File(self._fullPath, self._permission)
        dbOut = self.h5db

        with h5py.File(backupDBPath, "r") as dbIn:
            dbOut.attrs.update(dbIn.attrs)

            # Copy everything except time node data
            timeSteps = set()
            for groupName, group in dbIn.items():
                m = self.timeNodeGroupPattern.match(groupName)
                if m:
                    timeSteps.add((int(m.group(1)), int(m.group(2))))
                else:
                    dbIn.copy(groupName, dbOut)

            if not set(keepTimeSteps).issubset(timeSteps):
                raise ValueError(
                    "Not all desired time steps ({}) are even present in the "
                    "database".format(keepTimeSteps)
                )

            minCycle = next(iter(sorted(keepTimeSteps)))[0]
            for cycle, node in keepTimeSteps:
                offsetCycle = cycle - minCycle
                offsetGroupName = getH5GroupName(offsetCycle, node)
                dbIn.copy(getH5GroupName(cycle, node), dbOut, name=offsetGroupName)
                dbOut[offsetGroupName + "/Reactor/cycle"][()] = offsetCycle

        return backupDBPath

    @property
    def fileName(self):
        return self._fileName

    @fileName.setter
    def fileName(self, fName):
        if self.h5db is not None:
            raise RuntimeError("Cannot change Database file name while it's opened!")
        self._fileName = fName

    def loadCS(self):
        from armi import settings

        cs = settings.Settings()
        cs.caseTitle = os.path.splitext(os.path.basename(self.fileName))[0]
        cs.loadFromString(self.h5db["inputs/settings"][()])
        return cs

    def loadBlueprints(self):
        from armi.reactor import blueprints

        stream = io.StringIO(self.h5db["inputs/blueprints"][()])
        stream = blueprints.Blueprints.migrate(stream)
        bp = blueprints.Blueprints.load(stream)
        return bp

    def loadGeometry(self):
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromStream(io.StringIO(self.h5db["inputs/geomFile"][()]))
        return geom

    def writeInputsToDB(self, cs, csString=None, geomString=None, bpString=None):
        """
        Write inputs into the database based the CaseSettings.

        This is not DRY on purpose. The goal is that any particular Database
        implementation should be very stable, so we dont want it to be easy to change
        one Database implementation's behavior when trying to change another's.

        Notes
        -----
        This is hard-coded to read the entire file contents into memory and write that
        directly into the database. We could have the cs/blueprints/geom write to a
        string, however the ARMI log file contains a hash of each files' contents. In
        the future, we should be able to reproduce a calculation with confidence that
        the inputs are identical.
        """
        caseTitle = (
            cs.caseTitle if cs is not None else os.path.splitext(self.fileName)[0]
        )
        self.h5db.attrs["caseTitle"] = caseTitle
        if csString is None:
            # don't read file; use what's in the cs now.
            # Sometimes settings are modified in tests.
            stream = io.StringIO()
            cs.writeToYamlStream(stream)
            stream.seek(0)
            csString = stream.read()

        if bpString is None:
            # Ensure that the input as stored in the DB is complete
            bpString = resolveMarkupInclusions(
                pathlib.Path(cs.inputDirectory) / cs["loadingFile"]
            ).read()

        self.h5db["inputs/settings"] = csString
        self.h5db["inputs/geomFile"] = geomString
        self.h5db["inputs/blueprints"] = bpString

    def readInputsFromDB(self):
        return (
            self.h5db["inputs/settings"][()],
            self.h5db["inputs/geomFile"][()],
            self.h5db["inputs/blueprints"][()],
        )

    def mergeHistory(self, inputDB, startCycle, startNode):
        """
        Copy time step data up to, but not including the passed cycle and node.

        Notes
        -----
        This is used for restart runs with the standard operator for example.
        The current time step (being loaded from) should not be copied, as that
        time steps data will be written at the end of the time step.
        """
        # iterate over the top level H5Groups and copy
        for time, h5ts in zip(inputDB.genTimeSteps(), inputDB.genTimeStepGroups()):
            cyc, tn = time
            if cyc == startCycle and tn == startNode:
                # all data up to current state are merged
                return
            self.h5db.copy(h5ts, h5ts.name)

            if inputDB.versionMinor < 2:
                # The source database may have object references in some attributes.
                # make sure to link those up using our manual path strategy.
                references = []

                def findReferences(name, obj):
                    for key, attr in obj.attrs.items():
                        if isinstance(attr, h5py.h5r.Reference):
                            references.append((name, key, inputDB.h5db[attr].name))

                h5ts.visititems(findReferences)

                for key, attr, path in references:
                    destTs = self.h5db[h5ts.name]
                    destTs[key].attrs[attr] = "@{}".format(path)

    def __enter__(self):
        """Context management support"""
        if self._openCount == 0:
            # open also increments _openCount
            self.open()
        else:
            self._openCount += 1
        return self

    def __exit__(self, type, value, traceback):
        """Typically we don't care why it broke but we want the DB to close"""
        self._openCount -= 1
        # always close if there is a traceback.
        if self._openCount == 0 or traceback:
            self.close(all(i is None for i in (type, value, traceback)))

    def __del__(self):
        if self.h5db is not None:
            self.close(False)

    def __delitem__(self, tn: Tuple[int, int, Optional[str]]):
        cycle, timeNode, statePointName = tn
        name = getH5GroupName(cycle, timeNode, statePointName)
        if self.h5db is not None:
            del self.h5db[name]

    def genTimeStepGroups(
        self, timeSteps: Sequence[Tuple[int, int]] = None
    ) -> Generator[h5py._hl.group.Group, None, None]:
        """
        Returns a generator of HDF5 Groups for all time nodes, or for the passed selection.
        """
        assert (
            self.h5db is not None
        ), "Must open the database before calling genTimeStepGroups"
        if timeSteps is None:
            for groupName, h5TimeNodeGroup in sorted(self.h5db.items()):
                match = self.timeNodeGroupPattern.match(groupName)
                if match:
                    yield h5TimeNodeGroup
        else:
            for step in timeSteps:
                yield self.h5db[getH5GroupName(*step)]

    def genTimeSteps(self) -> Generator[Tuple[int, int], None, None]:
        """
        Returns a generator of (cycle, node) tuples that are present in the DB.
        """
        assert (
            self.h5db is not None
        ), "Must open the database before calling genTimeSteps"
        for groupName in sorted(self.h5db.keys()):
            match = self.timeNodeGroupPattern.match(groupName)
            if match:
                cycle = int(match.groups()[0])
                node = int(match.groups()[1])
                yield (cycle, node)

    def genAuxiliaryData(self, ts: Tuple[int, int]) -> Generator[str, None, None]:
        """
        Returns a generator of names of auxiliary data on the requested time point.
        """
        assert (
            self.h5db is not None
        ), "Must open the database before calling genAuxiliaryData"
        cycle, node = ts
        groupName = getH5GroupName(cycle, node)
        timeGroup = self.h5db[groupName]
        exclude = set(ArmiObject.TYPES.keys())
        exclude.add("layout")
        return (groupName + "/" + key for key in timeGroup.keys() if key not in exclude)

    def getAuxiliaryDataPath(self, ts: Tuple[int, int], name: str) -> str:
        return getH5GroupName(*ts) + "/" + name

    def keys(self):
        return (g.name for g in self.genTimeStepGroups())

    def getH5Group(self, r, statePointName=None):
        """
        Get the H5Group for the current ARMI timestep.

        This method can be used to allow other interfaces to place data into the database
        at the correct timestep.
        """
        groupName = getH5GroupName(r.p.cycle, r.p.timeNode, statePointName)
        if groupName in self.h5db:
            return self.h5db[groupName]
        else:
            group = self.h5db.create_group(groupName)
            group.attrs["cycle"] = r.p.cycle
            group.attrs["timeNode"] = r.p.timeNode
            return group

    def hasTimeStep(self, cycle, timeNode, statePointName=""):
        """
        Returns True if (cycle, timeNode, statePointName) is contained in the database.
        """
        return getH5GroupName(cycle, timeNode, statePointName) in self.h5db

    def writeToDB(self, reactor, statePointName=None):
        assert self.h5db is not None, "Database must be open before writing."
        # _createLayout is recursive
        h5group = self.getH5Group(reactor, statePointName)
        runLog.info("Writing to database for statepoint: {}".format(h5group.name))
        layout = Layout(comp=reactor)
        layout.writeToDB(h5group)
        groupedComps = layout.groupedComps

        for comps in groupedComps.values():
            self._writeParams(h5group, comps)

    def load(self, cycle, node, cs=None, bp=None, statePointName=None):
        """Load a new reactor from (cycle, node).

        Case settings, blueprints, and geom can be provided by the client, or read from
        the database itself. Providing these from the client could be useful when
        performing snapshot runs or the like, where it is expected to use results from a
        run using different settings, then continue with new settings. Even in this
        case, the blueprints and geom should probably be the same as the original run.

        Parameters
        ----------
        cycle : int
            cycle number
        node : int
            time node
        cs : armi.settings.Settings (optional)
            if not provided one is read from the database
        bp : armi.reactor.Blueprints (Optional)
            if not provided one is read from the database

        Returns
        -------
        root : ArmiObject
            The top-level object stored in the database; usually a Reactor.
        """
        runLog.info("Loading reactor state for time node ({}, {})".format(cycle, node))

        cs = cs or self.loadCS()
        # apply to avoid defaults in getMasterCs calls
        settings.setMasterCs(cs)
        bp = bp or self.loadBlueprints()

        h5group = self.h5db[getH5GroupName(cycle, node, statePointName)]

        layout = Layout(h5group=h5group)
        comps, groupedComps = layout._initComps(cs, bp)

        # populate data onto initialized components
        for compType, compTypeList in groupedComps.items():
            self._readParams(h5group, compType, compTypeList)

        # assign params from blueprints
        self._assignBlueprintsParams(bp, groupedComps)

        # stitch together
        self._compose(iter(comps), cs)

        # also, make sure to update the global serial number so we don't re-use a number
        parameterCollections.GLOBAL_SERIAL_NUM = max(
            parameterCollections.GLOBAL_SERIAL_NUM, layout.serialNum.max()
        )
        root = comps[0][0]
        return root  # usually reactor object

    @staticmethod
    def _assignBlueprintsParams(blueprints, groupedComps):
        for compType, designs in (
            (Block, blueprints.blockDesigns),
            (Assembly, blueprints.assemDesigns),
        ):
            paramsToSet = {
                pDef.name
                for pDef in compType.pDefs.inCategory(
                    parameters.Category.assignInBlueprints
                )
            }

            for comp in groupedComps[compType]:
                design = designs[comp.p.type]
                for pName in paramsToSet:
                    val = getattr(design, pName)
                    if val is not None:
                        comp.p[pName] = val
        return

    def _compose(self, comps, cs, parent=None):
        """
        Given a flat collection of all of the ArmiObjects in the model, reconstitute the
        hierarchy.
        """

        comp, serialNum, numChildren, location = next(comps)

        # attach the parent early, if provided; some cases need the parent attached for
        # the rest of _compose to work properly.
        comp.parent = parent

        # The Reactor adds a Core child by default, this is not ideal
        for spontaneousChild in list(comp):
            comp.remove(spontaneousChild)

        if isinstance(comp, Core):
            pass
        elif isinstance(comp, Assembly):
            # Assemblies force their name to be something based on assemNum. When the
            # assembly is created it gets a new assemNum, and throws out the correct
            # name that we read from the DB
            comp.name = comp.makeNameFromAssemNum(comp.p.assemNum)
            comp.lastLocationLabel = Assembly.DATABASE

        if location is not None:
            if parent is not None and parent.spatialGrid is not None:
                comp.spatialLocator = parent.spatialGrid[location]
            else:
                comp.spatialLocator = grids.CoordinateLocation(
                    location[0], location[1], location[2], None
                )

        # Need to keep a collection of Component instances for linked dimension
        # resolution, before they can be add()ed to their parents. Not just filtering
        # out of `children`, since _resolveLinkedDims() needs a dict
        childComponents = collections.OrderedDict()
        children = []

        for _ in range(numChildren):
            child = self._compose(comps, cs, parent=comp)
            children.append(child)
            if isinstance(child, Component):
                childComponents[child.name] = child

        for childName, child in childComponents.items():
            child._resolveLinkedDims(childComponents)

        for child in children:
            comp.add(child)

        if isinstance(comp, Core):
            # TODO: This is also an issue related to geoms and which core is "The Core".
            # We only have a good geom for the main core, so can't do process loading on
            # the SFP, etc.
            if comp.hasFlags(Flags.CORE):
                comp.processLoading(cs)
        elif isinstance(comp, Assembly):
            comp.calculateZCoords()

        return comp

    def _writeParams(self, h5group, comps):
        c = comps[0]
        groupName = c.__class__.__name__
        if groupName not in h5group:
            # Only create the group if it doesnt already exist. This happens when
            # re-writing params in the same time node (e.g. something changed between
            # EveryNode and EOC)
            g = h5group.create_group(groupName)
        else:
            g = h5group[groupName]

        for paramDef in c.p.paramDefs.toWriteToDB(
            parameters.SINCE_LAST_DB_TRANSMISSION
        ):
            attrs = {}

            if hasattr(c, "DIMENSION_NAMES") and paramDef.name in c.DIMENSION_NAMES:
                linkedDims = []
                data = []

                for i, c in enumerate(comps):
                    val = c.p[paramDef.name]
                    if isinstance(val, tuple):
                        linkedDims.append("{}.{}".format(val[0].name, val[1]))
                        data.append(val[0].getDimension(val[1]))
                    else:
                        linkedDims.append("")
                        data.append(val)

                data = numpy.array(data)
                if any(linkedDims):
                    attrs["linkedDims"] = numpy.array(linkedDims).astype("S")
            else:
                # XXX: side effect is that after loading previously unset values will be
                # the default
                temp = [c.p.get(paramDef.name, paramDef.default) for c in comps]
                if paramDef.serializer is not None:
                    data, sAttrs = paramDef.serializer.pack(temp)
                    assert (
                        data.dtype.kind != "O"
                    ), "{} failed to convert {} to a numpy-supported type.".format(
                        paramDef.serializer.__name__, paramDef.name
                    )
                    attrs.update(sAttrs)
                    attrs[_SERIALIZER_NAME] = paramDef.serializer.__name__
                    attrs[_SERIALIZER_VERSION] = paramDef.serializer.version
                else:
                    data = numpy.array(temp)
                    del temp

            # Convert Unicode to byte-string
            if data.dtype.kind == "U":
                data = data.astype("S")

            if data.dtype.kind == "O":
                # Something was added to the data array that caused numpy to want to
                # treat it as a general-purpose Object array. This usually happens
                # because:
                # - the data contain NoDefaults
                # - the data contain one or more Nones,
                # - the data contain special types like tuples, dicts, etc
                # - the data are composed of arrays that numpy would otherwise happily
                # convert to a higher-order array, but the dimensions of the sub-arrays
                # are inconsistent ("jagged")
                # - there is some sort of honest-to-goodness weird object
                # We want to support the first two cases with minimal intrusion, since
                # these should be pretty easy to faithfully represent in the db. The
                # jagged case should be supported as well, but may require a less
                # faithful representation (e.g. flattened), but the last case isn't
                # really worth supporting.

                # Here is one proposal:
                # - Check to see if the array is jagged. all(shape == shape[0]). If not,
                # flatten, store the data offsets and array shapes, and None locations
                # as attrs
                # - If not jagged, all top-level ndarrays are the same shape, so it is
                # probably easier to replace Nones with ndarrays filled with special
                # values.
                if parameters.NoDefault in data:
                    data = None
                else:
                    data, specialAttrs = packSpecialData(data, paramDef.name)
                    attrs.update(specialAttrs)

            if data is None:
                continue

            try:
                if paramDef.name in g:
                    raise ValueError(
                        "`{}` was already in `{}`. This time node "
                        "should have been empty".format(paramDef.name, g)
                    )
                else:
                    dataset = g.create_dataset(
                        paramDef.name, data=data, compression="gzip"
                    )
                if any(attrs):
                    _writeAttrs(dataset, h5group, attrs)
            except Exception as e:
                runLog.error(
                    "Failed to write {} to database. Data: "
                    "{}".format(paramDef.name, data)
                )
                raise

    @staticmethod
    def _readParams(h5group, compTypeName, comps):
        g = h5group[compTypeName]

        renames = armi.getApp().getParamRenames()

        pDefs = comps[0].pDefs

        # this can also be made faster by specializing the method by type
        for paramName, dataSet in g.items():
            # Honor historical databases where the parameters may have changed names
            # since.
            while paramName in renames:
                paramName = renames[paramName]

            pDef = pDefs[paramName]

            data = dataSet[:]
            attrs = _resolveAttrs(dataSet.attrs, h5group)

            if pDef.serializer is not None:
                assert _SERIALIZER_NAME in dataSet.attrs
                assert dataSet.attrs[_SERIALIZER_NAME] == pDef.serializer.__name__
                assert _SERIALIZER_VERSION in dataSet.attrs

                data = numpy.array(
                    pDef.serializer.unpack(
                        data, dataSet.attrs[_SERIALIZER_VERSION], attrs
                    )
                )

            if data.dtype.type is numpy.string_:
                data = numpy.char.decode(data)

            if attrs.get("specialFormatting", False):
                data = unpackSpecialData(data, attrs, paramName)

            linkedDims = []
            if "linkedDims" in attrs:
                linkedDims = numpy.char.decode(attrs["linkedDims"])

            # iterating of numpy is not fast...
            for c, val, linkedDim in itertools.zip_longest(
                comps, data.tolist(), linkedDims, fillvalue=""
            ):
                try:
                    if linkedDim != "":
                        c.p[paramName] = linkedDim
                    else:
                        c.p[paramName] = val
                except AssertionError as ae:
                    # happens when a param was deprecated but being loaded from old DB
                    runLog.warning(
                        f"{str(ae)}\nSkipping load of invalid param `{paramName}`"
                        " (possibly loading from old DB)\n"
                    )

    def getHistory(
        self,
        comp: ArmiObject,
        params: Sequence[str] = None,
        timeSteps: Sequence[Tuple[int, int]] = None,
    ) -> History:
        """
        Get parameter history for a single ARMI Object.

        Parameters
        ----------
        comps
            An individual ArmiObject
        params
            parameters to gather

        Returns
        -------
        dict
            Dictionary of str/list pairs.
        """
        # XXX: this can be optimized significantly
        return self.getHistories([comp], params, timeSteps)[comp]

    def getHistories(
        self,
        comps: Sequence[ArmiObject],
        params: Optional[Sequence[str]] = None,
        timeSteps: Optional[Sequence[Tuple[int, int]]] = None,
    ) -> Histories:
        """
        Get the parameter histories for a sequence of ARMI Objects.

        This implementation is unaware of the state of the reactor outside of the
        database itself, and is therefore not usually what client code should be calling
        directly. It only knows about historical data that actually exists in the
        database. Usually one wants to be able to get historical, plus current data, for
        which the similar method on the DatabaseInterface is more useful.

        Parameters
        ==========
        comps
            Something that is iterable multiple times
        params
            parameters to gather.
        timeSteps
            Selection of time nodes to get data for. If omitted, return full history

        Returns
        =======
        dict
            Dictionary ArmiObject (input): dict of str/list pairs containing ((cycle,
            node), value).
        """
        histData: Histories = {
            c: collections.defaultdict(collections.OrderedDict) for c in comps
        }
        types = {c.__class__ for c in comps}
        compsByTypeThenSerialNum: Dict[Type[ArmiObject], Dict[int, ArmiObject]] = {
            t: dict() for t in types
        }

        for c in comps:
            compsByTypeThenSerialNum[c.__class__][c.p.serialNum] = c

        for h5TimeNodeGroup in self.genTimeStepGroups(timeSteps):
            if "layout" not in h5TimeNodeGroup:
                # Layout hasn't been written for this time step, so whatever is in there
                # didn't come from the DatabaseInterface. Probably because it's the
                # current time step and something has created the group to store aux
                # data
                continue

            cycle = h5TimeNodeGroup.attrs["cycle"]
            timeNode = h5TimeNodeGroup.attrs["timeNode"]
            layout = Layout(h5group=h5TimeNodeGroup)

            for compType, compsBySerialNum in compsByTypeThenSerialNum.items():
                compTypeName = compType.__name__
                try:
                    h5GroupForType = h5TimeNodeGroup[compTypeName]
                except KeyError:
                    runLog.error(
                        "{} not found in {} of {}".format(
                            compTypeName, h5TimeNodeGroup, self
                        )
                    )
                layoutIndicesForType = numpy.where(layout.type == compTypeName)[0]
                serialNumsForType = layout.serialNum[layoutIndicesForType].tolist()
                layoutIndexInData = layout.indexInData[layoutIndicesForType].tolist()

                indexInData = []
                reorderedComps = []

                for ii, sn in zip(layoutIndexInData, serialNumsForType):
                    d = compsBySerialNum.get(sn, None)
                    if d is not None:
                        indexInData.append(ii)
                        reorderedComps.append(d)
                if not indexInData:
                    continue

                # note this is very similar to _readParams, but there are some important
                # differences.
                # 1) we are not assigning to p[paramName]
                # 2) not using linkedDims at all
                # 3) not performing parameter renaming. This may become necessary
                for paramName in params or h5GroupForType.keys():
                    if paramName == "location":
                        # cast to a numpy array so that we can use list indices
                        data = numpy.array(layout.location)[layoutIndicesForType][
                            indexInData
                        ]
                    elif paramName in h5GroupForType:
                        dataSet = h5GroupForType[paramName]
                        try:
                            data = dataSet[indexInData]
                        except:
                            runLog.error(
                                "Failed to load index {} from {}@{}".format(
                                    indexInData, dataSet, (cycle, timeNode)
                                )
                            )
                            raise

                        if data.dtype.type is numpy.string_:
                            data = numpy.char.decode(data)

                        if dataSet.attrs.get("specialFormatting", False):
                            if dataSet.attrs.get("nones", False):
                                data = replaceNonsenseWithNones(data, paramName)
                            else:
                                raise ValueError(
                                    "History tracking for non-none special formatting "
                                    "not supported: {}, {}".format(
                                        paramName,
                                        {k: v for k, v in dataSet.attrs.items()},
                                    )
                                )
                    else:
                        # Nothing in the database, so use the default value
                        data = numpy.repeat(
                            parameters.byNameAndType(paramName, compType).default,
                            len(reorderedComps),
                        )

                    # iterating of numpy is not fast..
                    for c, val in zip(reorderedComps, data.tolist()):

                        if isinstance(val, list):
                            val = numpy.array(val)

                        histData[c][paramName][cycle, timeNode] = val

        r = comps[0].getAncestorWithFlags(Flags.REACTOR)
        cycleNode = r.p.cycle, r.p.timeNode
        for c, paramHistories in histData.items():
            for paramName, hist in paramHistories.items():
                if cycleNode not in hist:
                    try:
                        hist[cycleNode] = c.p[paramName]
                    except:
                        if paramName == "location":
                            hist[cycleNode] = c.spatialLocator.indices

        return histData


class Layout(object):
    """
    The Layout class describes the hierarchical layout of the composite structure in a flat representation.

    A Layout is built up by starting at the root of a composite tree and recursively
    appending each node in the tree to the list of data. So for a typical Reactor model,
    the data will be ordered something like [r, c, a1, a1b1, a1b1c1, a1b1c2, a1b2,
    a1b2c1, ..., a2, ...]

    The layout is also responsible for storing Component attributes, like location,
    material, and temperatures (from blueprints), which aren't stored as Parameters.
    Temperatures, specifically, are rather complicated beasts in ARMI, and more
    fundamental changes to how we deal with them may allow us to remove them from
    Layout.
    """

    def __init__(self, h5group=None, comp=None):
        self.type = []
        self.name = []
        self.serialNum = []
        self.indexInData = []
        self.numChildren = []
        self.locationType = []
        self.location = []
        self.gridIndex = []
        self.temperatures = []
        self.material = []
        # set of grid parameters that have been seen in _createLayout. For efficient
        # checks for uniqueness
        self._seenGridParams = dict()
        # actual list of grid parameters, with stable order for safe indexing
        self.gridParams = []

        self.groupedComps = collections.defaultdict(list)

        if comp is not None:
            self._createLayout(comp)
        else:
            self._readLayout(h5group)

        self._snToLayoutIndex = {sn: i for i, sn in enumerate(self.serialNum)}

    def __getitem__(self, sn):
        layoutIndex = self._snToLayoutIndex[sn]
        return (
            self.type[layoutIndex],
            self.name[layoutIndex],
            self.serialNum[layoutIndex],
            self.indexInData[layoutIndex],
            self.numChildren[layoutIndex],
            self.locationType[layoutIndex],
            self.location[layoutIndex],
            self.temperatures[layoutIndex],
            self.material[layoutIndex],
        )

    def _createLayout(self, comp):
        """Recursive function to populate a hierarchical representation and group the
        items by type."""
        compList = self.groupedComps[type(comp)]
        compList.append(comp)

        self.type.append(comp.__class__.__name__)
        self.name.append(comp.name)
        self.serialNum.append(comp.p.serialNum)
        self.indexInData.append(len(compList) - 1)
        self.numChildren.append(len(comp))
        if comp.spatialGrid is not None:
            gridType = type(comp.spatialGrid).__name__
            gridParams = (gridType, comp.spatialGrid.reduce())
            if gridParams not in self._seenGridParams:
                self._seenGridParams[gridParams] = len(self.gridParams)
                self.gridParams.append(gridParams)
            self.gridIndex.append(self._seenGridParams[gridParams])
        else:
            self.gridIndex.append(None)

        if comp.spatialLocator is None:
            self.locationType.append("None")
            self.location.append((0.0, 0.0, 0.0))
        else:
            self.locationType.append(comp.spatialLocator.__class__.__name__)
            self.location.append(comp.spatialLocator.indices)

        try:
            self.temperatures.append((comp.inputTemperatureInC, comp.temperatureInC))
            self.material.append(comp.material.__class__.__name__)
        except:
            self.temperatures.append((-900, -900))  # an impossible temperature
            self.material.append("")

        try:
            comps = sorted([c for c in comp])
        except ValueError:
            runLog.error(
                "Failed to sort some collection of ArmiObjects for database output: {} "
                "value {}".format(type(comp), [c for c in comp])
            )
            raise

        for c in comps:
            self._createLayout(c)

    def _readLayout(self, h5group):
        try:
            # location is either an index, or a point
            # iter over list is faster
            locations = h5group["layout/location"][:].tolist()
            self.locationType = numpy.char.decode(
                h5group["layout/locationType"][:]
            ).tolist()
            self.location = locs = []
            for l, lt in zip(locations, self.locationType):
                if lt == "None":
                    locs.append(None)
                elif lt == "IndexLocation":
                    # the data is stored as float, so cast back to int
                    locs.append(tuple(int(i) for i in l))
                else:
                    locs.append(tuple(l))

            self.type = numpy.char.decode(h5group["layout/type"][:])
            self.name = numpy.char.decode(h5group["layout/name"][:])
            self.serialNum = h5group["layout/serialNum"][:]
            self.indexInData = h5group["layout/indexInData"][:]
            self.numChildren = h5group["layout/numChildren"][:]
            self.material = numpy.char.decode(h5group["layout/material"][:])
            self.temperatures = h5group["layout/temperatures"][:]
            self.gridIndex = replaceNonsenseWithNones(
                h5group["layout/gridIndex"][:], "layout/gridIndex"
            )

            gridGroup = h5group["layout/grids"]
            gridTypes = [t.decode() for t in gridGroup["type"][:]]

            self.gridParams = []
            for iGrid, gridType in enumerate(gridTypes):
                thisGroup = gridGroup[str(iGrid)]

                unitSteps = thisGroup["unitSteps"][:]
                bounds = []
                for ibound in range(3):
                    boundName = "bounds_{}".format(ibound)
                    if boundName in thisGroup:
                        bounds.append(thisGroup[boundName][:])
                    else:
                        bounds.append(None)
                unitStepLimits = thisGroup["unitStepLimits"][:]
                offset = thisGroup["offset"][:] if thisGroup.attrs["offset"] else None
                geomType = (
                    thisGroup["geomType"][()] if "geomType" in thisGroup else None
                )
                symmetry = (
                    thisGroup["symmetry"][()] if "symmetry" in thisGroup else None
                )

                self.gridParams.append(
                    (
                        gridType,
                        grids.GridParameters(
                            unitSteps,
                            bounds,
                            unitStepLimits,
                            offset,
                            geomType,
                            symmetry,
                        ),
                    )
                )

        except KeyError as e:
            runLog.error(
                "Failed to get layout information from group: {}".format(h5group.name)
            )
            raise e

    def _initComps(self, cs, bp):
        comps = []
        groupedComps = collections.defaultdict(list)

        # initialize
        for (
            compType,
            name,
            serialNum,
            indexInData,
            numChildren,
            location,
            material,
            temperatures,
            gridIndex,
        ) in zip(
            self.type,
            self.name,
            self.serialNum,
            self.indexInData,
            self.numChildren,
            self.location,
            self.material,
            self.temperatures,
            self.gridIndex,
        ):
            Klass = ArmiObject.TYPES[compType]

            if issubclass(Klass, Reactor):
                comp = Klass(cs.caseTitle, bp)
            elif issubclass(Klass, Core):
                comp = Klass(name)
            elif issubclass(Klass, Component):
                # XXX: initialize all dimensions to 0, they will be loaded and assigned
                # after load
                kwargs = dict.fromkeys(Klass.DIMENSION_NAMES, 0)
                kwargs["material"] = material
                kwargs["name"] = name
                kwargs["Tinput"] = temperatures[0]
                kwargs["Thot"] = temperatures[1]
                comp = Klass(**kwargs)
            else:
                comp = Klass(name)

            if gridIndex is not None:
                gridParams = self.gridParams[gridIndex]
                comp.spatialGrid = GRID_CLASSES[gridParams[0]](
                    *gridParams[1], armiObject=comp
                )

            comps.append((comp, serialNum, numChildren, location))
            groupedComps[compType].append(comp)

        return comps, groupedComps

    def writeToDB(self, h5group):
        if "layout/type" in h5group:
            # It looks like we have already written the layout to DB, skip for now
            return
        try:
            h5group.create_dataset(
                "layout/type",
                data=numpy.array(self.type).astype("S"),
                compression="gzip",
            )
            h5group.create_dataset(
                "layout/name",
                data=numpy.array(self.name).astype("S"),
                compression="gzip",
            )
            h5group.create_dataset(
                "layout/serialNum", data=self.serialNum, compression="gzip"
            )
            h5group.create_dataset(
                "layout/indexInData", data=self.indexInData, compression="gzip"
            )
            h5group.create_dataset(
                "layout/numChildren", data=self.numChildren, compression="gzip"
            )
            h5group.create_dataset(
                "layout/location", data=self.location, compression="gzip"
            )
            h5group.create_dataset(
                "layout/locationType",
                data=numpy.array(self.locationType).astype("S"),
                compression="gzip",
            )
            h5group.create_dataset(
                "layout/material",
                data=numpy.array(self.material).astype("S"),
                compression="gzip",
            )
            h5group.create_dataset(
                "layout/temperatures", data=self.temperatures, compression="gzip"
            )

            h5group.create_dataset(
                "layout/gridIndex",
                data=replaceNonesWithNonsense(
                    numpy.array(self.gridIndex), "layout/gridIndex"
                ),
                compression="gzip",
            )

            gridsGroup = h5group.create_group("layout/grids")
            gridsGroup.attrs["nGrids"] = len(self.gridParams)
            gridsGroup.create_dataset(
                "type", data=numpy.array([gp[0] for gp in self.gridParams]).astype("S")
            )

            for igrid, gridParams in enumerate(gp[1] for gp in self.gridParams):
                thisGroup = gridsGroup.create_group(str(igrid))
                thisGroup.create_dataset("unitSteps", data=gridParams.unitSteps)

                for ibound, bound in enumerate(gridParams.bounds):
                    if bound is not None:
                        bound = numpy.array(bound)
                        thisGroup.create_dataset("bounds_{}".format(ibound), data=bound)

                thisGroup.create_dataset(
                    "unitStepLimits", data=gridParams.unitStepLimits
                )

                offset = gridParams.offset
                thisGroup.attrs["offset"] = offset is not None
                if offset is not None:
                    thisGroup.create_dataset("offset", data=offset)
                thisGroup.create_dataset("geomType", data=gridParams.geomType)
                thisGroup.create_dataset("symmetry", data=gridParams.symmetry)
        except RuntimeError:
            runLog.error("Failed to create datasets in: {}".format(h5group))
            raise


def allSubclasses(cls):
    """This currently include Materials... and it should not."""
    return set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in allSubclasses(c)]
    )


# TODO: This will likely become an issue with extensibility via plugins. There are a
# couple of options to resolve this:
# - Perform this operation each time we make a Layout. Wasteful, but robust
# - Scrape all of these names off of a set of Composites that register with a base
#   metaclass. Less wasteful, but probably equally robust. Downside is it's metaclassy
#   and Madjickal.
GRID_CLASSES = {c.__name__: c for c in allSubclasses(grids.Grid)}
GRID_CLASSES["Grid"] = grids.Grid


NONE_MAP = {float: float("nan"), str: "<!None!>"}

# XXX: we're going to assume no one assigns min(int)+2 as a meaningful value
NONE_MAP.update(
    {
        intType: numpy.iinfo(intType).min + 2
        for intType in (
            int,
            numpy.int,
            numpy.int8,
            numpy.int16,
            numpy.int32,
            numpy.int64,
        )
    }
)
NONE_MAP.update(
    {
        intType: numpy.iinfo(intType).max - 2
        for intType in (
            numpy.uint,
            numpy.uint8,
            numpy.uint16,
            numpy.uint32,
            numpy.uint64,
        )
    }
)
NONE_MAP.update(
    {floatType: floatType("nan") for floatType in (numpy.float, numpy.float64)}
)


def packSpecialData(
    data: numpy.ndarray, paramName: str
) -> Tuple[Optional[numpy.ndarray], Dict[str, Any]]:
    """
    Reduce data that wouldn't otherwise play nicely with HDF5/numpy arrays to a format
    that will.

    This is the main entry point for conforming "strange" data into something that will
    both fit into a numpy array/HDF5 dataset, and be recoverable to its original-ish
    state when reading it back in. This is accomplished by detecting a handful of known
    offenders and using various HDF5 attributes to store necessary auxiliary data. It is
    important to keep in mind that the data that is passed in has already been converted
    to a numpy array, so the top dimension is always representing the collection of
    composites that are storing the parameters. For instance, if we are dealing with a
    Block parameter, the first index in the numpy array of data is the block index; so
    if each block has a parameter that is a dictionary, ``data`` would be a ndarray,
    where each element is a dictionary. This routine supports a number of different
    "strange" things:
    * Dict[str, float]: These are stored by finding the set of all keys for all
      instances, and storing those keys as a list in an attribute. The data themselves
      are stored as arrays indexed by object, then key index. Dictionaries lacking data
      for a key store a nan in it's place. This will work well in instances where most
      objects have data for most keys.
    * Jagged arrays: These are stored by concatenating all of the data into a single,
      one-dimensional array, and storing attributes to describe the shapes of each
      object's data, and an offset into the beginning of each object's data.
    * Arrays with ``None`` in them: These are stored by replacing each instance of
      ``None`` with a magical value that shouldn't be encountered in realistic
      scenarios.


    Parameters
    ----------
    data
        An ndarray storing the data that we want to stuff into the database. These are
        usually dtype=Object, which is how we usually end up here in the first place.

    paramName
        The parameter name that we are trying to store data for. This is mostly used for
        diagnostics.

    See Also
    --------
    unpackSpecialData

    """

    # Check to make sure that we even need to do this. If the numpy data type is
    # not "O", chances are we have nice, clean data.
    if data.dtype != "O":
        return data, {}

    attrs: Dict[str, Any] = {"specialFormatting": True}

    # make a copy of the data, so that the original is unchanged
    data = copy.copy(data)

    # find locations of Nones. The below works for ndarrays, whereas `data == None`
    # gives a single True/False value
    nones = numpy.where([d is None for d in data])[0]

    if len(nones) == data.shape[0]:
        # Everything is None, so why bother?
        return None, attrs

    if len(nones) > 0:
        attrs["nones"] = True

    # XXX: this whole if/then/elif/else can be optimized by looping once and then
    #      determining the correct action
    # A robust solution would need
    # to do this on a case-by-case basis, and re-do it any time we want to
    # write, since circumstances may change. Not only that, but we may need
    # to do perform more that one of these operations to get to an array
    # that we want to put in the database.
    if any(isinstance(d, dict) for d in data):
        # we're assuming that a dict is {str: float}. We store the union of
        # all of the keys for all of the objects as a special "keys"
        # attribute, and store a value for all of those keys for all
        # objects, whether or not there is actually data associated with
        # that key (storing a nan when no data). This makes for a simple
        # approach that is somewhat digestible just looking at the db, and
        # should be quite efficient in the case where most objects have data
        # for most keys.
        attrs["dict"] = True
        keys = sorted({k for d in data for k in d})
        data = numpy.array([[d.get(k, numpy.nan) for k in keys] for d in data])
        if data.dtype == "O":
            # The data themselves are nasty. We could support this, but best to wait for
            # a credible use case.
            raise TypeError(
                "Unable to coerce dictionary data into usable numpy array for "
                "{}".format(paramName)
            )
        attrs["keys"] = numpy.array(keys).astype("S")

        return data, attrs

    # conform non-numpy arrays to numpy
    for i, val in enumerate(data):
        if isinstance(val, (list, tuple)):
            data[i] = numpy.array(val)

    if not any(isinstance(d, numpy.ndarray) for d in data):
        # looks like 1-D plain-old-data
        data = replaceNonesWithNonsense(data, paramName, nones)
        return data, attrs

    # check if data is jagged
    candidate = next((d for d in data if d is not None))
    shape = candidate.shape
    ndim = candidate.ndim
    isJagged = (
        not all(d.shape == shape for d in data if d is not None) or candidate.size == 0
    )

    if isJagged:
        assert all(
            val.ndim == ndim for val in data if val is not None
        ), "Inconsistent dimensions in jagged array for: {}\nDimensions: {}".format(
            paramName, [val.ndim for val in data if val is not None]
        )
        attrs["jagged"] = True

        # offsets[i] is the index of the zero-th element of sub-array i
        offsets = numpy.array(
            [0]
            + list(
                itertools.accumulate(val.size if val is not None else 0 for val in data)
            )[:-1]
        )

        # shapes[i] is the shape of the i-th sub-array. Nones are represented by all
        # zeros
        shapes = numpy.array(
            list(val.shape if val is not None else ndim * (0,) for val in data)
        )

        data = numpy.delete(data, nones)

        data = numpy.concatenate(data, axis=None)

        attrs["offsets"] = offsets
        attrs["shapes"] = shapes
        attrs["noneLocations"] = nones
        return data, attrs

    if any(isinstance(d, (tuple, list, numpy.ndarray)) for d in data):
        data = replaceNonesWithNonsense(data, paramName, nones)
        return data, attrs

    if len(nones) == 0:
        raise TypeError(
            "Cannot write {} to the database, it did not resolve to a numpy/HDF5 "
            "type.".format(paramName)
        )

    runLog.error("Data unable to find special none value: {}".format(data))
    raise TypeError("Failed to process special data for {}".format(paramName))


def unpackSpecialData(data: numpy.ndarray, attrs, paramName: str) -> numpy.ndarray:
    """
    Extract data from a specially-formatted HDF5 dataset into a numpy array.

    This should invert the operations performed by :py:func:`packSpecialData`.

    Parameters
    ----------
    data
        Specially-formatted data array straight from the database.

    attrs
        The attributes associated with the dataset that contained the data.

    paramName
        The name of the parameter that is being unpacked. Only used for diagnostics.

    Returns
    -------
    numpy.ndarray
        An ndarray containing the closest possible representation of the data that was
        originally written to the database.


    See Also
    --------
    packSpecialData
    """
    if not attrs.get("specialFormatting", False):
        # The data were not subjected to any special formatting; short circuit.
        assert data.dtype != "O"
        return data

    unpackedData: List[Any]
    if attrs.get("nones", False) and not attrs.get("jagged", False):
        data = replaceNonsenseWithNones(data, paramName)
        return data
    if attrs.get("jagged", False):
        offsets = attrs["offsets"]
        shapes = attrs["shapes"]
        ndim = len(shapes[0])
        emptyArray = numpy.ndarray(ndim * (0,), dtype=data.dtype)
        unpackedData: List[Optional[numpy.ndarray]] = []
        for offset, shape in zip(offsets, shapes):
            if tuple(shape) == ndim * (0,):
                # Start with an empty array. This may be replaced with a None later
                unpackedData.append(emptyArray)
            else:
                unpackedData.append(
                    numpy.ndarray(shape, dtype=data.dtype, buffer=data[offset:])
                )
        for i in attrs["noneLocations"]:
            unpackedData[i] = None

        return numpy.array(unpackedData)
    if attrs.get("dict", False):
        keys = numpy.char.decode(attrs["keys"])
        unpackedData = []
        assert data.ndim == 2
        for d in data:
            unpackedData.append(
                {key: value for key, value in zip(keys, d) if not numpy.isnan(value)}
            )
        return numpy.array(unpackedData)

    raise ValueError(
        "Do not recognize the type of special formatting that was applied "
        "to {}. Attrs: {}".format(paramName, {k: v for k, v in attrs.items()})
    )


def replaceNonsenseWithNones(data: numpy.ndarray, paramName: str) -> numpy.ndarray:
    """
    Replace special nonsense values with ``None``.

    This essentially reverses the operations performed by
    :py:func:`replaceNonesWithNonsense`.

    Parameters
    ----------
    data
        The array from the database that contains special ``None`` nonsense values.

    paramName
        The param name who's data we are dealing with. Only used for diagnostics.

    See Also
    --------
    replaceNonesWithNonsense
    """
    # TODO: This is super closely-related to the NONE_MAP collection, and should
    # probably use it somehow.
    if numpy.issubdtype(data.dtype, numpy.floating):
        isNone = numpy.isnan(data)
    elif numpy.issubdtype(data.dtype, numpy.integer):
        isNone = data == numpy.iinfo(data.dtype).min + 2
    elif numpy.issubdtype(data.dtype, numpy.str_):
        isNone = data == "<!None!>"
    else:
        raise TypeError(
            "Unable to resolve values that should be None for `{}`".format(paramName)
        )

    if data.ndim > 1:
        result = numpy.ndarray(data.shape[0], dtype=numpy.dtype("O"))
        for i in range(data.shape[0]):
            if isNone[i].all():
                result[i] = None
            elif isNone[i].any():
                # TODO: This is not symmetric with the replaceNonesWithNonsense impl.
                # That one assumes that Nones apply only at the highest dimension, and
                # that the lower dimensions will be filled with the magic None value.
                # Non-none entries below the top level fail to coerce to a serializable
                # numpy array and would raise an exception when trying to write. TL;DR:
                # this is a dead branch until the replaceNonesWithNonsense impl is more
                # sophisticated.
                result[i] = numpy.array(data[i], dtype=numpy.dtype("O"))
                result[i][isNone[i]] = None
            else:
                result[i] = data[i]

    else:
        result = numpy.ndarray(data.shape, dtype=numpy.dtype("O"))
        result[:] = data
        result[isNone] = None

    return result


def replaceNonesWithNonsense(
    data: numpy.ndarray, paramName: str, nones: numpy.ndarray = None
) -> numpy.ndarray:
    """
    Replace instances of ``None`` with nonsense values that can be detected/recovered
    when reading.

    Parameters
    ----------
    data
        The numpy array containing ``None`` values that need to be replaced.

    paramName
        The name of the parameter who's data we are treating. Only used for diagnostics.

    nones
        An array containing the index locations on the ``None`` elements. It is a little
        strange to pass these, in but we find these indices to determine whether we need
        to call this function in the first place, so might as well pass it in, so that
        we don't need to perform the operation again.

    Notes
    -----
    This only supports situations where the data is a straight-up ``None``, or a valid,
    database-storable numpy array (or easily convertable to one (e.g. tuples/lists with
    numerical values)). This does not support, for instance, a numpy ndarray with some
    Nones in it.

    For example, the following is supported::

        [[1, 2, 3], None, [7, 8, 9]]

    However, the following is not::

        [[1, 2, 3], [4, None, 6], [7, 8, 9]]

    See Also
    --------
    replaceNonsenseWithNones
        Reverses this operation.
    """
    if nones is None:
        nones = numpy.where([d is None for d in data])[0]

    try:
        # loop to find what the default value should be. This is the first non-None
        # value that we can find.
        defaultValue = None
        realType = None
        val = None

        for val in data:
            if isinstance(val, numpy.ndarray):
                # if multi-dimensional, val[0] could still be an array, val.flat is
                # a flattened iterator, so next(val.flat) gives the first value in
                # an n-dimensional array
                realType = type(next(val.flat))

                if realType is type(None):
                    continue

                defaultValue = numpy.reshape(
                    numpy.repeat(NONE_MAP[realType], val.size), val.shape
                )
                break
            else:
                realType = type(val)

                if realType is type(None):
                    continue

                defaultValue = NONE_MAP[realType]
                break
        else:
            # Couldn't find any non-None entries, so it really doesn't matter what type we
            # use. Using float, because NaN is nice.
            realType = float
            defaultValue = NONE_MAP[realType]

        if isinstance(val, numpy.ndarray):
            data = numpy.array([d if d is not None else defaultValue for d in data])
        else:
            data[nones] = defaultValue

    except Exception as ee:
        runLog.error(
            "Error while attempting to determine default for {}.\nvalue: {}\nError: {}".format(
                paramName, val, ee
            )
        )
        raise TypeError(
            "Could not determine None replacement for {} with type {}, val {}, default {}".format(
                paramName, realType, val, defaultValue
            )
        )

    try:
        data = data.astype(realType)
    except:
        runLog.error(
            "Could not coerce data for {} to {}, data:\n{}".format(
                paramName, realType, data
            )
        )
        raise

    if data.dtype.kind == "O":
        raise TypeError(
            "Failed to convert data to valid HDF5 type {}, data:{}".format(
                paramName, data
            )
        )

    return data


def _writeAttrs(obj, group, attrs):
    """
    Handle safely writing attributes to a dataset, handling large data if necessary.

    This will attempt to store attributes directly onto an HDF5 object if possible,
    falling back to proper datasets and reference attributes if necessary. This is
    needed because HDF5 tries to fit attributes into the object header, which has
    limited space. If an attribute is too large, h5py raises a RuntimeError.
    In such cases, this will store the attribute data in a proper dataset and
    place a reference to that dataset in the attribute instead.

    In practice, this takes ``linkedDims`` attrs from a particular component type (like
    ``c00n00/Circle/id``) and stores them in new datasets (like
    ``c00n00/attrs/1_linkedDims``, ``c00n00/attrs/2_linkedDims``) and then sets the
    object's attrs to links to those datasets.
    """
    for key, value in attrs.items():
        try:
            obj.attrs[key] = value
        except RuntimeError as err:
            if "object header message is too large" not in err.args[0]:
                raise

            runLog.info(
                "Storing attribute `{}` for `{}` into it's own dataset within "
                "`{}/attrs`".format(key, obj, group)
            )

            if "attrs" not in group:
                attrGroup = group.create_group("attrs")
            else:
                attrGroup = group["attrs"]
            dataName = str(len(attrGroup)) + "_" + key
            attrGroup[dataName] = value

            # using a soft link here allows us to cheaply copy time nodes without
            # needing to crawl through and update object references.
            linkName = attrGroup[dataName].name
            obj.attrs[key] = "@{}".format(linkName)


def _resolveAttrs(attrs, group):
    """
    Reverse the action of _writeAttrs.

    This reads actual attrs and looks for the real data
    in the datasets that the attrs were pointing to.
    """
    resolved = {}
    for key, val in attrs.items():
        try:
            if isinstance(val, h5py.h5r.Reference):
                # Old style object reference. If this cannot be dereferenced, it is
                # likely because mergeHistory was used to get the current database,
                # which does not preserve references.
                resolved[key] = group[val]
            elif isinstance(val, str):
                m = ATTR_LINK.match(val)
                if m:
                    # dereference the path to get the data out of the dataset.
                    resolved[key] = group[m.group(1)][()]
                else:
                    resolved[key] = val
            else:
                resolved[key] = val
        except ValueError:
            runLog.error(f"HDF error loading {key} : {val}\nGroup: {group}")
            raise
    return resolved
