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
ARMI Database implementation, version 3.4.

A reactor model should be fully recoverable from the database; all the way down to the component level. As a result, the
structure of the underlying data is bound to the hierarchical Composite Reactor Model. Furthermore, this database format
is intended to be more dynamic, permitting as-yet undeveloped levels and classes in the Composite Reactor Model to be
supported as they are added. More high-level discussion is contained in :ref:`database-file`.

The :py:class:`Database` class contains most of the functionality for interacting with the underlying data. This
includes things like dumping a Reactor state to the database and loading it back again, as well as extracting historical
data for a given object or collection of object from the database file. However, for the nitty-gritty details of how the
hierarchical Composite Reactor Model is translated to the flat file database, please refer to
:py:mod:`armi.bookkeeping.db.layout`.

Refer to :py:mod:`armi.bookkeeping.db` for information about versioning.
"""

import collections
import copy
import gc
import io
import itertools
import os
import pathlib
import re
import shutil
import subprocess
import sys
from platform import uname
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

import h5py
import numpy as np

from armi import context, getApp, getPluginManagerOrFail, meta, runLog, settings
from armi.bookkeeping.db.jaggedArray import JaggedArray
from armi.bookkeeping.db.layout import (
    DB_VERSION,
    LOC_COORD,
    Layout,
    replaceNonesWithNonsense,
    replaceNonsenseWithNones,
)
from armi.bookkeeping.db.typedefs import Histories, History
from armi.nucDirectory import nuclideBases
from armi.physics.neutronics.settings import CONF_LOADING_FILE
from armi.reactor import grids, parameters
from armi.reactor.assemblies import Assembly
from armi.reactor.blocks import Block
from armi.reactor.components import Component
from armi.reactor.composites import ArmiObject
from armi.reactor.parameters import parameterCollections
from armi.reactor.reactorParameters import makeParametersReadOnly
from armi.reactor.reactors import Core, Reactor
from armi.settings.fwSettings.globalSettings import (
    CONF_GROW_TO_FULL_CORE_AFTER_LOAD,
    CONF_SORT_REACTOR,
)
from armi.utils import getNodesPerCycle, safeCopy, safeMove
from armi.utils.textProcessors import resolveMarkupInclusions

# CONSTANTS
_SERIALIZER_NAME = "serializerName"
_SERIALIZER_VERSION = "serializerVersion"


def getH5GroupName(cycle: int, timeNode: int, statePointName: str = None) -> str:
    """
    Naming convention specifier.

    ARMI defines the naming convention cXXnYY for groups of simulation data. That is, data is grouped by cycle and time
    node information during a simulated run.
    """
    return "c{:0>2}n{:0>2}{}".format(cycle, timeNode, statePointName or "")


class Database:
    """
    ARMI Database, handling serialization and loading of Reactor states.

    This implementation of the database pushes all objects in the Composite Reactor Model into the database. This
    process is aided by the ``Layout`` class, which handles the packing and unpacking of the structure of the objects,
    their relationships, and their non-parameter attributes.

    .. impl:: The database files are H5, and thus language agnostic.
        :id: I_ARMI_DB_H51
        :implements: R_ARMI_DB_H5

        This class implements a light wrapper around H5 files, so they can be used to store ARMI outputs. H5 files are
        commonly used in scientific applications in Fortran and C++. As such, they are entirely language agnostic binary
        files. The implementation here is that ARMI wraps the ``h5py`` library, and uses its extensive tooling, instead
        of re-inventing the wheel.

    See Also
    --------
    `doc/user/outputs/database` for more details.
    """

    # Allows matching for, e.g., c01n02EOL
    timeNodeGroupPattern = re.compile(r"^c(\d\d)n(\d\d).*$")

    def __init__(self, fileName: os.PathLike, permission: str):
        """
        Create a new Database object.

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

        # Allows context management on open files. If context management is used on a file that is already open, it will
        # not reopen and it will also not close after leaving that context. This allows the treatment of all databases
        # the same whether they are open or closed.
        self._openCount: int = 0

        if permission == "w":
            self.version = DB_VERSION
        else:
            # will be set upon read
            self._version = None
            self._versionMajor = None
            self._versionMinor = None

    @property
    def version(self) -> str:
        return self._version

    @version.setter
    def version(self, value: str):
        self._version = value
        self._versionMajor, self._versionMinor = (int(v) for v in value.split("."))
        if self.versionMajor != 3:
            raise ValueError(f"This version of ARMI only supports version 3 of the ARMI DB, found {self.versionMajor}.")

    @property
    def versionMajor(self):
        return self._versionMajor

    @property
    def versionMinor(self):
        return self._versionMinor

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, repr(self.h5db).replace("<", "").replace(">", ""))

    def open(self):
        if self.h5db is not None:
            raise ValueError("This database is already open; make sure to close it before trying to open it again.")

        filePath = self._fileName
        self._openCount += 1

        if self._permission in {"r", "a"}:
            self._fullPath = os.path.abspath(filePath)
            self.h5db = h5py.File(filePath, self._permission)
            self.version = self.h5db.attrs["databaseVersion"]
            return

        if self._permission == "w":
            # assume fast path!
            filePath = os.path.join(context.getFastPath(), filePath)
            self._fullPath = os.path.abspath(filePath)

        else:
            runLog.error(f"Unrecognized file permissions `{self._permission}`")
            raise ValueError(f"Cannot open database with permission `{self._permission}`")

        # open the database, and write a bunch of metadata to it
        runLog.info("Opening database file at {}".format(os.path.abspath(filePath)))
        self.h5db = h5py.File(filePath, self._permission)
        self.h5db.attrs["successfulCompletion"] = False
        self.h5db.attrs["version"] = meta.__version__
        self.h5db.attrs["databaseVersion"] = self.version
        self.writeSystemAttributes(self.h5db)

        # store app and plugin data
        app = getApp()
        self.h5db.attrs["appName"] = app.name
        plugins = app.pluginManager.list_name_plugin()
        ps = [(os.path.abspath(sys.modules[p[1].__module__].__file__), p[1].__name__) for p in plugins]
        ps = np.array([str(p[0]) + ":" + str(p[1]) for p in ps]).astype("S")
        self.h5db.attrs["pluginPaths"] = ps
        self.h5db.attrs["localCommitHash"] = Database.grabLocalCommitHash()

    def isOpen(self):
        return self.h5db is not None

    @staticmethod
    def writeSystemAttributes(h5db):
        """Write system attributes to the database.

        .. impl:: Add system attributes to the database.
            :id: I_ARMI_DB_QA
            :implements: R_ARMI_DB_QA

            This method writes some basic system information to the H5 file. This is designed as a starting point, so
            users can see information about the system their simulations were run on. As ARMI is used on Windows and
            Linux, the tooling here has to be platform independent. The two major sources of information are the ARMI
            :py:mod:`context <armi.context>` module and the Python standard library ``platform``.
        """
        h5db.attrs["user"] = context.USER
        h5db.attrs["python"] = sys.version
        h5db.attrs["armiLocation"] = os.path.dirname(context.ROOT)
        h5db.attrs["startTime"] = context.START_TIME
        h5db.attrs["machines"] = np.array(context.MPI_NODENAMES).astype("S")

        # store platform data
        platform_data = uname()
        h5db.attrs["platform"] = platform_data.system
        h5db.attrs["hostname"] = platform_data.node
        h5db.attrs["platformRelease"] = platform_data.release
        h5db.attrs["platformVersion"] = platform_data.version
        h5db.attrs["platformArch"] = platform_data.processor

    @staticmethod
    def grabLocalCommitHash():
        """
        Try to determine the local Git commit.

        We have to be sure to handle the errors where the code is run on a system that doesn't have Git installed. Or if
        the code is simply not run from inside a repo.

        Returns
        -------
        str
            The commit hash if it exists, otherwise "unknown".
        """
        unknown = "unknown"
        if not shutil.which("git"):
            # no git available. cannot check git info
            return unknown
        repo_exists = (
            subprocess.run(
                "git rev-parse --git-dir".split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
            and subprocess.run(
                ["git", "describe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        )
        if repo_exists:
            try:
                commit_hash = subprocess.check_output(["git", "describe"])
                return commit_hash.decode("utf-8").strip()
            except Exception:
                return unknown
        else:
            return unknown

    def close(self, completedSuccessfully=False):
        """Close the DB and perform cleanups and auto-conversions."""
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
            newPath = safeMove(self._fullPath, self._fileName)
            self._fullPath = os.path.abspath(newPath)

    def splitDatabase(self, keepTimeSteps: Sequence[Tuple[int, int]], label: str) -> str:
        """
        Discard all data except for specific time steps, retaining old data in a separate file.

        This is useful when performing more exotic analyses, where each "time step" may not represent a specific point
        in time, but something more nuanced. For example, equilibrium cases store a new "cycle" for each iteration as it
        attempts to converge the equilibrium cycle. At the end of the run, the last "cycle" is the converged equilibrium
        cycle, whereas the previous cycles constitute the path to convergence, which we typically wish to discard before
        further analysis.

        Parameters
        ----------
        keepTimeSteps
            A collection of the time steps to retain
        label
            An informative label for the backed-up database. Usually something like "-all-iterations". Will be
            interposed between the source name and the ".h5" extension.

        Returns
        -------
        str
            The name of the new, backed-up database file.
        """
        if self.h5db is None:
            raise ValueError("There is no open database to split.")

        self.h5db.close()

        backupDBPath = os.path.abspath(label.join(os.path.splitext(self._fileName)))
        runLog.info(f"Retaining full database history in {backupDBPath}")
        if self._fullPath is not None:
            safeMove(self._fullPath, backupDBPath)

        self.h5db = h5py.File(self._fullPath, self._permission)
        dbOut = self.h5db

        with h5py.File(backupDBPath, "r") as dbIn:
            dbOut.attrs.update(dbIn.attrs)

            # Copy everything except time node data
            timeSteps = set()
            for groupName, _ in dbIn.items():
                m = self.timeNodeGroupPattern.match(groupName)
                if m:
                    timeSteps.add((int(m.group(1)), int(m.group(2))))
                else:
                    dbIn.copy(groupName, dbOut)

            if not set(keepTimeSteps).issubset(timeSteps):
                raise ValueError(f"Not all desired time steps ({keepTimeSteps}) are even present in the database")

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

    def loadCS(self, handleInvalids=True):
        """Attempt to load settings from the database file.

        Parameters
        ----------
        handleInvalids : bool
            Whether to check for invalid settings. Default True.

        Notes
        -----
        There are no guarantees here. If the database was written from a different version of ARMI than you are using,
        these results may not be usable. Or if the database was written using a custom Application you do not have
        access to, the DB may not be usable.
        """
        cs = settings.Settings()
        cs.path = self.fileName
        cs.loadFromString(self.h5db["inputs/settings"].asstr()[()], handleInvalids=handleInvalids)

        return cs

    def loadBlueprints(self, cs=None):
        """Attempt to load reactor blueprints from the database file.

        Notes
        -----
        There are no guarantees here. If the database was written from a different version of ARMI than you are using,
        these results may not be usable. Or if the database was written using a custom Application you do not have
        access to, the DB may not be usable.
        """
        # Blueprints use the yamlize package, which uses class attributes to define much of the class's behavior through
        # metaclassing. Therefore, we need to be able to import all plugins before importing blueprints.
        from armi.reactor.blueprints import Blueprints

        bpString = None

        try:
            bpString = self.h5db["inputs/blueprints"].asstr()[()]
            # Need to update the blueprint file to be the database so that its not pointing at a source that doesn't
            # exist anymore (the original blueprints yaml).
            if cs:
                # Update the settings to point at where the file was actually read from
                cs[CONF_LOADING_FILE] = os.path.basename(self.fileName)
        except KeyError:
            # not all reactors need to be created from blueprints, so they may not exist
            pass

        if not bpString:
            # looks like no blueprints contents
            return None

        stream = io.StringIO(bpString)
        stream = Blueprints.migrate(stream)
        return Blueprints.load(stream)

    def writeInputsToDB(self, cs, csString=None, bpString=None):
        """
        Write inputs into the database based the Settings.

        This is not DRY on purpose. The goal is that any particular Database implementation should be very stable, so we
        dont want it to be easy to change one Database implementation's behavior when trying to change another's.

        .. impl:: The run settings are saved the settings file.
            :id: I_ARMI_DB_CS
            :implements: R_ARMI_DB_CS

            A ``Settings`` object is passed into this method, and then the settings are converted into a YAML string
            stream. That stream is then written to the H5 file. Optionally, this method can take a pre-build settings
            string to be written directly to the file.

        .. impl:: The reactor blueprints are saved the settings file.
            :id: I_ARMI_DB_BP
            :implements: R_ARMI_DB_BP

            A ``Blueprints`` string is optionally passed into this method, and then written to the H5 file. If it is not
            passed in, this method will attempt to find the blueprints input file in the settings, and read the contents
            of that file into a stream to be written to the H5 file.

        Notes
        -----
        This is hard-coded to read the entire file contents into memory and write that directly into the database. We
        could have the cs/blueprints/geom write to a string, however the ARMI log file contains a hash of each files'
        contents. In the future, we should be able to reproduce a calculation with confidence that the inputs are
        identical.
        """
        caseTitle = cs.caseTitle if cs is not None else os.path.splitext(self.fileName)[0]
        self.h5db.attrs["caseTitle"] = caseTitle
        if csString is None:
            # Don't read file; use what's in the cs now. Sometimes settings are modified in tests.
            stream = io.StringIO()
            cs.writeToYamlStream(stream)
            stream.seek(0)
            csString = stream.read()

        if bpString is None:
            bpPath = pathlib.Path(cs.inputDirectory) / cs[CONF_LOADING_FILE]
            if bpPath.suffix.lower() in (".h5", ".hdf5"):
                # The blueprints are in a database file, they need to be read
                try:
                    db = h5py.File(bpPath, "r")
                    bpString = db["inputs/blueprints"].asstr()[()]
                except KeyError:
                    # not all reactors need to be created from blueprints, so they may not exist
                    bpString = ""
            else:
                # The blueprints are a standard blueprints yaml that can be read.
                if bpPath.exists() and bpPath.is_file():
                    # Only store blueprints if we actually loaded from them. Ensure that the input as stored in the DB
                    # is complete
                    bpString = resolveMarkupInclusions(pathlib.Path(cs.inputDirectory) / cs[CONF_LOADING_FILE]).read()
                else:
                    bpString = ""

        self.h5db["inputs/settings"] = csString
        self.h5db["inputs/blueprints"] = bpString

    def readInputsFromDB(self):
        return (
            self.h5db["inputs/settings"].asstr()[()],
            self.h5db["inputs/blueprints"].asstr()[()],
        )

    def mergeHistory(self, inputDB, startCycle, startNode):
        """
        Copy time step data up to, but not including the passed cycle and node.

        Notes
        -----
        This is used for restart runs with the standard operator for example. The current time step (being loaded from)
        should not be copied, as that time steps data will be written at the end of the time step.
        """
        if self.versionMajor != 3:
            raise ValueError(f"Only version 3 of the ARMI DB is supported, found {self.versionMajor}.")

        # iterate over the top level H5Groups and copy
        for time, h5ts in zip(inputDB.genTimeSteps(), inputDB.genTimeStepGroups()):
            cyc, tn = time
            if cyc == startCycle and tn == startNode:
                # all data up to current state are merged
                return
            self.h5db.copy(h5ts, h5ts.name)

            if inputDB.versionMinor < 2:
                # The source database may have object references in some attributes. Make sure to link those up using
                # our manual path strategy.
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
        """Context management support."""
        if self._openCount == 0:
            # open also increments _openCount
            self.open()
        else:
            self._openCount += 1
        return self

    def __exit__(self, type, value, traceback):
        """Typically we don't care why it broke but we want the DB to close."""
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
        """Returns a generator of HDF5 Groups for all time nodes, or for the passed selection."""
        assert self.h5db is not None, "Must open the database before calling genTimeStepGroups"
        if timeSteps is None:
            for groupName, h5TimeNodeGroup in sorted(self.h5db.items()):
                match = self.timeNodeGroupPattern.match(groupName)
                if match:
                    yield h5TimeNodeGroup
        else:
            for step in timeSteps:
                yield self.h5db[getH5GroupName(*step)]

    def getLayout(self, cycle, node):
        """Return a Layout object representing the requested cycle and time node."""
        version = (self._versionMajor, self._versionMinor)
        timeGroupName = getH5GroupName(cycle, node)

        return Layout(version, self.h5db[timeGroupName])

    def genTimeSteps(self) -> Generator[Tuple[int, int], None, None]:
        """Returns a generator of (cycle, node) tuples that are present in the DB."""
        assert self.h5db is not None, "Must open the database before calling genTimeSteps"
        for groupName in sorted(self.h5db.keys()):
            match = self.timeNodeGroupPattern.match(groupName)
            if match:
                cycle = int(match.groups()[0])
                node = int(match.groups()[1])
                yield (cycle, node)

    def genAuxiliaryData(self, ts: Tuple[int, int]) -> Generator[str, None, None]:
        """Returns a generator of names of auxiliary data on the requested time point."""
        assert self.h5db is not None, "Must open the database before calling genAuxiliaryData"
        cycle, node = ts
        groupName = getH5GroupName(cycle, node)
        timeGroup = self.h5db[groupName]
        exclude = set(ArmiObject.TYPES.keys())
        exclude.add("layout")
        return (groupName + "/" + key for key in timeGroup.keys() if key not in exclude)

    @staticmethod
    def getAuxiliaryDataPath(ts: Tuple[int, int], name: str) -> str:
        return getH5GroupName(*ts) + "/" + name

    def keys(self):
        return (g.name for g in self.genTimeStepGroups())

    def getH5Group(self, r, statePointName=None):
        """
        Get the H5Group for the current ARMI timestep.

        This method can be used to allow other interfaces to place data into the database at the correct timestep.
        """
        groupName = getH5GroupName(r.p.cycle, r.p.timeNode, statePointName)
        if groupName in self.h5db:
            return self.h5db[groupName]
        else:
            group = self.h5db.create_group(groupName, track_order=True)
            group.attrs["cycle"] = r.p.cycle
            group.attrs["timeNode"] = r.p.timeNode
            return group

    def hasTimeStep(self, cycle, timeNode, statePointName=""):
        """Returns True if (cycle, timeNode, statePointName) is contained in the database."""
        return getH5GroupName(cycle, timeNode, statePointName) in self.h5db

    def writeToDB(self, reactor, statePointName=None):
        assert self.h5db is not None, "Database must be open before writing."
        # _createLayout is recursive
        h5group = self.getH5Group(reactor, statePointName)
        runLog.info("Writing to database for statepoint: {}".format(h5group.name))
        layout = Layout((self.versionMajor, self.versionMinor), comp=reactor)
        layout.writeToDB(h5group)
        groupedComps = layout.groupedComps

        for comps in groupedComps.values():
            self._writeParams(h5group, comps)

    def syncToSharedFolder(self):
        """
        Copy DB to run working directory.

        Needed when multiple MPI processes need to read the same db, for example when a history is needed from
        independent runs (e.g. for fuel performance on a variety of assemblies).

        Notes
        -----
        At some future point, we may implement a client-server like DB system which would render this kind of operation
        unnecessary.
        """
        runLog.extra("Copying DB to shared working directory.")
        self.h5db.flush()

        # Close the h5 file so it can be copied
        self.h5db.close()
        self.h5db = None
        safeCopy(self._fullPath, self._fileName)

        # Garbage collect so we don't have multiple databases hanging around in memory
        gc.collect()

        # Reload the file in append mode and continue on our merry way
        self.h5db = h5py.File(self._fullPath, "r+")

    def load(
        self,
        cycle,
        node,
        cs=None,
        bp=None,
        statePointName=None,
        allowMissing=False,
        handleInvalids=True,
        callReactorConstructionHook=False,
    ):
        """Load a new reactor from a DB at (cycle, node).

        Case settings and blueprints can be provided, or read from the database. Providing  can be useful for snapshot
        runs or when you want to change settings mid-simulation. Geometry is read from the database.

        .. impl:: Users can load a reactor from a DB.
            :id: I_ARMI_DB_TIME1
            :implements: R_ARMI_DB_TIME

            This method creates a ``Reactor`` object by reading the reactor state out of an ARMI database file. This is
            done by passing in mandatory arguments that specify the exact place in time you want to load the reactor
            from. (That is, the cycle and node numbers.) Users can either pass the settings and blueprints directly into
            this method, or it will attempt to read them from the database file. The primary work done here is to read
            the hierarchy of reactor objects from the data file, then reconstruct them in the correct order.

        Parameters
        ----------
        cycle : int
            Cycle number
        node : int
            Time node. If value is negative, will be indexed from EOC backwards like a list.
        cs : armi.settings.Settings, optional
            If not provided one is read from the database
        bp : armi.reactor.Blueprints, optional
            If not provided one is read from the database
        statePointName : str, optional
            Statepoint name (e.g., "special" for "c00n00-special/")
        allowMissing : bool, optional
            Whether to emit a warning, rather than crash if reading a database
            with undefined parameters. Default False.
        handleInvalids : bool
            Whether to check for invalid settings. Default True.
        callReactorConstructionHook : bool
            Flag for whether the beforeReactorConstruction plugin hook should be executed. Default is False.

        Returns
        -------
        root : Reactor
            The top-level object stored in the database; a Reactor.
        """
        runLog.info(f"Loading reactor state for time node ({cycle}, {node})")

        cs = cs or self.loadCS(handleInvalids=handleInvalids)
        bp = bp or self.loadBlueprints(cs)

        if callReactorConstructionHook:
            getPluginManagerOrFail().hook.beforeReactorConstruction(cs=cs)

        if node < 0:
            numNodes = getNodesPerCycle(cs)[cycle]
            if (node + numNodes) < 0:
                raise ValueError(f"Node {node} specified does not exist for cycle {cycle}")
            node = numNodes + node

        h5group = self.h5db[getH5GroupName(cycle, node, statePointName)]

        layout = Layout((self.versionMajor, self.versionMinor), h5group=h5group)
        comps, groupedComps = layout._initComps(cs.caseTitle, bp)

        # populate data onto initialized components
        for compType, compTypeList in groupedComps.items():
            self._readParams(h5group, compType, compTypeList, allowMissing=allowMissing)

        # assign params from blueprints
        if bp is not None:
            self._assignBlueprintsParams(bp, groupedComps)

        # stitch together
        self._compose(iter(comps), cs)

        # also, make sure to update the global serial number so we don't reuse a number
        parameterCollections.GLOBAL_SERIAL_NUM = max(parameterCollections.GLOBAL_SERIAL_NUM, layout.serialNum.max())
        root = comps[0][0]

        # return a Reactor object
        if cs[CONF_SORT_REACTOR]:
            root.sort()
        else:
            runLog.warning(
                "DeprecationWarning: This Reactor is not being sorted on DB load. Due to the setting "
                f"{CONF_SORT_REACTOR}, this Reactor is unsorted. But this feature is temporary and will be removed by "
                "2024."
            )

        if cs[CONF_GROW_TO_FULL_CORE_AFTER_LOAD] and not root.core.isFullCore:
            root.core.growToFullCore(cs)

        return root

    def loadReadOnly(self, cycle, node, statePointName=None):
        """Load a new reactor, in read-only mode from a DB at (cycle, node).

        Parameters
        ----------
        cycle : int
            Cycle number
        node : int
            Time node. If value is negative, will be indexed from EOC backwards like a list.
        statePointName : str, optional
            Statepoint name (e.g., "special" for "c00n00-special/")

        Returns
        -------
        Reactor
            The top-level object stored in the database; a Reactor.
        """
        r = self.load(cycle, node, statePointName=statePointName, allowMissing=True)
        self._setParamsBeforeFreezing(r)
        makeParametersReadOnly(r)
        return r

    @staticmethod
    def _setParamsBeforeFreezing(r: Reactor):
        """Set some special case parameters before they are made read-only."""
        for child in r.iterChildren(deep=True, predicate=lambda c: isinstance(c, Component)):
            # calling Component.getVolume() sets the volume parameter
            child.getVolume()

    @staticmethod
    def _assignBlueprintsParams(blueprints, groupedComps):
        for compType, designs in (
            (Block, blueprints.blockDesigns),
            (Assembly, blueprints.assemDesigns),
        ):
            paramsToSet = {pDef.name for pDef in compType.pDefs.inCategory(parameters.Category.assignInBlueprints)}

            for comp in groupedComps[compType]:
                design = designs[comp.p.type]
                for pName in paramsToSet:
                    val = getattr(design, pName)
                    if val is not None:
                        comp.p[pName] = val

    def _compose(self, comps, cs, parent=None):
        """Given a flat collection of all of the ArmiObjects in the model, reconstitute the hierarchy."""
        comp, _, numChildren, location, locationType = next(comps)

        # attach the parent early, if provided; some cases need the parent attached for the rest of _compose to work
        # properly.
        comp.parent = parent

        # The Reactor adds a Core child by default, this is not ideal
        for spontaneousChild in list(comp):
            comp.remove(spontaneousChild)

        if isinstance(comp, Core):
            pass
        elif isinstance(comp, Assembly):
            # Assemblies force their name to be something based on assemNum. When the assembly is created it gets a new
            # assemNum, and throws out the correct name read from the DB.
            comp.name = comp.makeNameFromAssemNum(comp.p.assemNum)
            comp.lastLocationLabel = Assembly.DATABASE

        # set the spatialLocators on each component
        if location is not None:
            if parent is not None and parent.spatialGrid is not None:
                if locationType != LOC_COORD:
                    # We can directly index into the spatial grid for IndexLocation and MultiIndexLocators to get
                    # equivalent spatial locators
                    comp.spatialLocator = parent.spatialGrid[location]
                else:
                    comp.spatialLocator = grids.CoordinateLocation(
                        location[0], location[1], location[2], parent.spatialGrid
                    )
            else:
                comp.spatialLocator = grids.CoordinateLocation(location[0], location[1], location[2], None)

        # Need to keep a collection of Component instances for linked dimension resolution, before they can be add()ed
        # to their parents. Not just filtering out of `children`, since resolveLinkedDims() needs a dict
        childComponents = collections.OrderedDict()
        children = []

        for _ in range(numChildren):
            child = self._compose(comps, cs, parent=comp)
            children.append(child)
            if isinstance(child, Component):
                childComponents[child.name] = child

        for _childName, child in childComponents.items():
            child.resolveLinkedDims(childComponents)

        for child in children:
            comp.add(child)

        if isinstance(comp, Core):
            comp.processLoading(cs, dbLoad=True)
        elif isinstance(comp, Assembly):
            comp.calculateZCoords()
        elif isinstance(comp, Component):
            comp.finalizeLoadingFromDB()

        return comp

    @staticmethod
    def _getArrayShape(arr: Union[np.ndarray, List, Tuple]):
        """Get the shape of a np.ndarray, list, or tuple."""
        if isinstance(arr, np.ndarray):
            return arr.shape
        elif isinstance(arr, (list, tuple)):
            return (len(arr),)
        else:
            # not a list, tuple, or array (likely int, float, or None)
            return 1

    def _writeParams(self, h5group, comps) -> tuple:
        c = comps[0]
        groupName = c.__class__.__name__
        if groupName not in h5group:
            # Only create the group if it doesn't already exist. This happens when re-writing params in the same time
            # node (e.g. something changed between EveryNode and EOC).
            g = h5group.create_group(groupName, track_order=True)
        else:
            g = h5group[groupName]

        for paramDef in c.p.paramDefs.toWriteToDB():
            attrs = {}

            if hasattr(c, "DIMENSION_NAMES") and paramDef.name in c.DIMENSION_NAMES:
                linkedDims = []
                data = []

                for _, c in enumerate(comps):
                    val = c.p[paramDef.name]
                    if isinstance(val, tuple):
                        linkedDims.append("{}.{}".format(val[0].name, val[1]))
                        data.append(val[0].getDimension(val[1]))
                    else:
                        linkedDims.append("")
                        data.append(val)

                data = np.array(data)
                if any(linkedDims):
                    attrs["linkedDims"] = np.array(linkedDims).astype("S")
            else:
                # NOTE: after loading, the previously unset values will be defaulted
                temp = [c.p.get(paramDef.name, paramDef.default) for c in comps]
                if paramDef.serializer is not None:
                    data, sAttrs = paramDef.serializer.pack(temp)
                    assert data.dtype.kind != "O", "{} failed to convert {} to a numpy-supported type.".format(
                        paramDef.serializer.__name__, paramDef.name
                    )
                    attrs.update(sAttrs)
                    attrs[_SERIALIZER_NAME] = paramDef.serializer.__name__
                    attrs[_SERIALIZER_VERSION] = paramDef.serializer.version
                else:
                    # check if temp is a jagged array
                    if any(isinstance(x, (np.ndarray, list)) for x in temp):
                        jagged = len(set([self._getArrayShape(x) for x in temp])) != 1
                    else:
                        jagged = False
                    data = JaggedArray(temp, paramDef.name) if jagged else np.array(temp)
                    del temp

            # - Check to see if the array is jagged. If so, flatten, store the data offsets and array shapes, and None
            #   locations as attrs.
            # - If not jagged, all top-level ndarrays are the same shape, so it is easier to replace Nones with ndarrays
            #   filled with special values.
            if isinstance(data, JaggedArray):
                data, specialAttrs = packSpecialData(data, paramDef.name)
                attrs.update(specialAttrs)

            else:  # np.ndarray
                # Convert Unicode to byte-string
                if data.dtype.kind == "U":
                    data = data.astype("S")

                if data.dtype.kind == "O":
                    # Something was added to the data array that caused np to want to treat it as a general-purpose
                    # Object array. This usually happens because:
                    # - the data contain NoDefaults
                    # - the data contain one or more Nones,
                    # - the data contain special types like tuples, dicts, etc
                    # - there is some sort of honest-to-goodness weird object
                    # We want to support the first two cases with minimal intrusion, since these should be pretty easy
                    # to faithfully represent in the db. The last case isn't really worth supporting.
                    if parameters.NoDefault in data:
                        data = None
                    else:
                        data, specialAttrs = packSpecialData(data, paramDef.name)
                        attrs.update(specialAttrs)

            if data is None:
                continue

            try:
                if paramDef.name in g:
                    raise ValueError(f"`{paramDef.name}` was already in `{g}`. This time node should have been empty")

                dataset = g.create_dataset(paramDef.name, data=data, compression="gzip", track_order=True)
                if any(attrs):
                    Database._writeAttrs(dataset, h5group, attrs)
            except Exception:
                runLog.error(f"Failed to write {paramDef.name} to database. Data: {data}")
                raise

        if isinstance(c, Block):
            self._addHomogenizedNumberDensityParams(comps, g)

    @staticmethod
    def _addHomogenizedNumberDensityParams(blocks, h5group):
        """
        Create on-the-fly block homog. number density params for XTVIEW viewing.

        See Also
        --------
        collectBlockNumberDensities
        """
        nDens = collectBlockNumberDensities(blocks)

        for nucName, numDens in nDens.items():
            h5group.create_dataset(nucName, data=numDens, compression="gzip", track_order=True)

    @staticmethod
    def _readParams(h5group, compTypeName, comps, allowMissing=False):
        g = h5group[compTypeName]

        renames = getApp().getParamRenames()

        pDefs = comps[0].pDefs

        # this can also be made faster by specializing the method by type
        for paramName, dataSet in g.items():
            # Honor historical databases where the parameters may have changed names since.
            while paramName in renames:
                paramName = renames[paramName]

            try:
                pDef = pDefs[paramName]
            except KeyError:
                if re.match(r"^n[A-Z][a-z]?\d*", paramName):
                    # This is a temporary viz param (number density) made by _addHomogenizedNumberDensityParams ignore
                    # it safely
                    continue
                else:
                    # If a parameter exists in the database but not in the application reading it, we can technically
                    # keep going. Since this may lead to potential correctness issues, raise a warning
                    if allowMissing:
                        runLog.warning(
                            "Found `{}` parameter `{}` in the database, which is not defined. Ignoring it.".format(
                                compTypeName, paramName
                            )
                        )
                        continue
                    else:
                        raise

            data = dataSet[:]
            attrs = Database._resolveAttrs(dataSet.attrs, h5group)

            if pDef.serializer is not None:
                assert _SERIALIZER_NAME in dataSet.attrs
                assert dataSet.attrs[_SERIALIZER_NAME] == pDef.serializer.__name__
                assert _SERIALIZER_VERSION in dataSet.attrs

                data = np.array(pDef.serializer.unpack(data, dataSet.attrs[_SERIALIZER_VERSION], attrs))

            # nuclides are a special case where we want to keep in np.bytes_ format
            if data.dtype.type is np.bytes_ and "nuclides" not in paramName.lower():
                data = np.char.decode(data)

            if attrs.get("specialFormatting", False):
                data = unpackSpecialData(data, attrs, paramName)

            linkedDims = []
            if "linkedDims" in attrs:
                linkedDims = np.char.decode(attrs["linkedDims"])

            unpackedData = data.tolist()
            if len(comps) != len(unpackedData):
                msg = (
                    "While unpacking special data for {}, encountered composites and parameter "
                    "data with unmatched sizes.\nLength of composites list = {}\nLength of data "
                    "list = {}\nThis could indicate an error in data unpacking, which could "
                    "result in faulty data on the resulting reactor model.".format(
                        paramName, len(comps), len(unpackedData)
                    )
                )
                runLog.error(msg)
                raise ValueError(msg)

            if paramName == "numberDensities" and attrs.get("dict", False):
                Database._applyComponentNumberDensitiesMigration(comps, unpackedData)
            else:
                # iterating of np is not fast...
                for c, val, linkedDim in itertools.zip_longest(comps, unpackedData, linkedDims, fillvalue=""):
                    try:
                        if linkedDim != "":
                            c.p[paramName] = linkedDim
                        else:
                            c.p[paramName] = val
                    except AssertionError as ae:
                        # happens when a param was deprecated but being loaded from old DB
                        runLog.warning(
                            f"{str(ae)}\nSkipping load of invalid param `{paramName}` (possibly loading from old DB)\n"
                        )

    def getHistoryByLocation(
        self,
        comp: ArmiObject,
        params: Optional[List[str]] = None,
        timeSteps: Optional[Sequence[Tuple[int, int]]] = None,
    ) -> History:
        """Get the parameter histories at a specific location."""
        return self.getHistoriesByLocation([comp], params=params, timeSteps=timeSteps)[comp]

    def getHistoriesByLocation(
        self,
        comps: Sequence[ArmiObject],
        params: Optional[List[str]] = None,
        timeSteps: Optional[Sequence[Tuple[int, int]]] = None,
    ) -> Histories:
        """
        Get the parameter histories at specific locations.

        This has a number of limitations, which should in practice not be too limiting:
         - The passed objects must have IndexLocations. This type of operation doesn't make much sense otherwise.
         - The passed objects must exist in a hierarchy that leads to a Core object, which serves as an anchor that can
           fully define all index locations. This could possibly be made more general by extending grids, but that gets
           a little more complicated.
         - All requested objects must exist under the **same** anchor object, and at the same depth below it.
         - All requested objects must have the same type.

        Parameters
        ----------
        comps : list of ArmiObject
            The components/composites that currently occupy the location that you want histories at. ArmiObjects are
            passed, rather than locations, because this makes it easier to figure out things related to layout.
        params : List of str, optional
            The parameter names for the parameters that we want the history of. If None, all parameter history is given.
        timeSteps : List of (cycle, node) tuples, optional
            The time nodes that you want history for. If None, all available time nodes will be returned.
        """
        if self.versionMajor != 3:
            raise ValueError(f"This version of ARMI only supports version 3 of the ARMI DB, found {self.versionMajor}.")
        elif self.versionMinor < 4:
            raise ValueError(
                "Location-based histories are only supported for db version 3.4 and greater. This database is version "
                f"{self.versionMajor}, {self.versionMinor}."
            )

        locations = [c.spatialLocator.getCompleteIndices() for c in comps]

        histData: Histories = {c: collections.defaultdict(collections.OrderedDict) for c in comps}

        # Check our assumptions about the passed locations: All locations must have the same parent and bear the same
        # relationship to the anchor object.
        anchors = {obj.getAncestorAndDistance(lambda a: isinstance(a, Core)) for obj in comps}

        if len(anchors) != 1:
            raise ValueError(
                "The passed objects do not have the same anchor or distance to that anchor; encountered the following: "
                f"{anchors}"
            )

        anchorInfo = anchors.pop()
        if anchorInfo is not None:
            anchor, anchorDistance = anchorInfo
        else:
            raise ValueError("Could not determine an anchor object for the passed components")

        anchorSerialNum = anchor.p.serialNum

        # All objects of the same type
        objectTypes = {type(obj) for obj in comps}
        if len(objectTypes) != 1:
            raise TypeError(f"The passed objects must be the same type; got objects of types `{objectTypes}`")

        compType = objectTypes.pop()
        objClassName = compType.__name__

        locToComp = {c.spatialLocator.getCompleteIndices(): c for c in comps}

        for h5TimeNodeGroup in self.genTimeStepGroups(timeSteps):
            if "layout" not in h5TimeNodeGroup:
                # Layout hasn't been written for this time step, so we can't get anything useful here. Perhaps the
                # current value is of use, in which case the DatabaseInterface should be used.
                continue

            cycle = h5TimeNodeGroup.attrs["cycle"]
            timeNode = h5TimeNodeGroup.attrs["timeNode"]
            layout = Layout((self.versionMajor, self.versionMinor), h5group=h5TimeNodeGroup)
            ancestors = layout.computeAncestors(layout.serialNum, layout.numChildren, depth=anchorDistance)

            lLocation = layout.location
            # filter for objects that live under the desired ancestor and at a desired location
            objectIndicesInLayout = np.array(
                [
                    i
                    for i, (ancestor, loc) in enumerate(zip(ancestors, lLocation))
                    if ancestor == anchorSerialNum and loc in locations
                ]
            )

            # This could also be way more efficient if lLocation were a numpy array
            objectLocationsInLayout = [lLocation[i] for i in objectIndicesInLayout]
            objectIndicesInData = np.array(layout.indexInData)[objectIndicesInLayout].tolist()

            try:
                h5GroupForType = h5TimeNodeGroup[objClassName]
            except KeyError as ee:
                runLog.error(f"{objClassName} not found in {h5TimeNodeGroup} of {self}")
                raise ee

            for paramName in params or h5GroupForType.keys():
                if paramName == "location":
                    # location is special, since it is stored in layout/
                    data = np.array(layout.location)[objectIndicesInLayout]
                elif paramName in h5GroupForType:
                    dataSet = h5GroupForType[paramName]
                    try:
                        data = dataSet[objectIndicesInData]
                    except:
                        runLog.error(f"Failed to load index {objectIndicesInData} from {dataSet}@{(cycle, timeNode)}")
                        raise

                    if data.dtype.type is np.bytes_:
                        data = np.char.decode(data)

                    if dataSet.attrs.get("specialFormatting", False):
                        if dataSet.attrs.get("nones", False):
                            data = replaceNonsenseWithNones(data, paramName)
                        else:
                            raise ValueError(
                                "History tracking for non-None, special-formatted parameters is not supported: "
                                "{}, {}".format(paramName, {k: v for k, v in dataSet.attrs.items()})
                            )
                else:
                    # Nothing in the database for this param, so use the default value
                    data = np.repeat(
                        parameters.byNameAndType(paramName, compType).default,
                        len(comps),
                    )

                # store data to the appropriate comps. This is where taking components as the argument (rather than
                # locations) is a little bit peculiar.
                #
                # At this point, `data` are arranged by the order of elements in `objectIndicesInData`, which
                # corresponds to the order of `objectIndicesInLayout`
                for loc, val in zip(objectLocationsInLayout, data.tolist()):
                    comp = locToComp[loc]
                    histData[comp][paramName][cycle, timeNode] = val

        return histData

    def getHistory(
        self,
        comp: ArmiObject,
        params: Optional[Sequence[str]] = None,
        timeSteps: Optional[Sequence[Tuple[int, int]]] = None,
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
        return self.getHistories([comp], params, timeSteps)[comp]

    def getHistories(
        self,
        comps: Sequence[ArmiObject],
        params: Optional[Sequence[str]] = None,
        timeSteps: Optional[Sequence[Tuple[int, int]]] = None,
    ) -> Histories:
        """
        Get the parameter histories for a sequence of ARMI Objects.

        This implementation is unaware of the state of the reactor outside of the database itself, and is therefore not
        usually what client code should be calling directly during normal ARMI operation. It only knows about historical
        data that have actually been written to the database. Usually one wants to be able to get historical, plus
        current data, for which the similar method on the DatabaseInterface may be more useful.

        Parameters
        ----------
        comps
            Something that is iterable multiple times
        params
            parameters to gather.
        timeSteps
            Selection of time nodes to get data for. If omitted, return full history

        Returns
        -------
        dict
            Dictionary ArmiObject (input): dict of str/list pairs containing ((cycle, node), value).
        """
        histData: Histories = {c: collections.defaultdict(collections.OrderedDict) for c in comps}
        types = {c.__class__ for c in comps}
        compsByTypeThenSerialNum: Dict[Type[ArmiObject], Dict[int, ArmiObject]] = {t: dict() for t in types}

        for c in comps:
            compsByTypeThenSerialNum[c.__class__][c.p.serialNum] = c

        for h5TimeNodeGroup in self.genTimeStepGroups(timeSteps):
            if "layout" not in h5TimeNodeGroup:
                # Layout hasn't been written for this time step, so whatever is in there didn't come from the
                # DatabaseInterface. Probably because it's the current time step and something has created the group to
                # store aux data
                continue

            # might save as int or np.int64, so forcing int keeps things predictable
            cycle = int(h5TimeNodeGroup.attrs["cycle"])
            timeNode = int(h5TimeNodeGroup.attrs["timeNode"])
            layout = Layout((self.versionMajor, self.versionMinor), h5group=h5TimeNodeGroup)

            for compType, compsBySerialNum in compsByTypeThenSerialNum.items():
                compTypeName = compType.__name__
                try:
                    h5GroupForType = h5TimeNodeGroup[compTypeName]
                except KeyError as ee:
                    runLog.error("{} not found in {} of {}".format(compTypeName, h5TimeNodeGroup, self))
                    raise ee
                layoutIndicesForType = np.where(layout.type == compTypeName)[0]
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

                # note this is very similar to _readParams but there are some important differences.
                # 1) we are not assigning to p[paramName]
                # 2) not using linkedDims at all
                # 3) not performing parameter renaming. This may become necessary
                for paramName in params or h5GroupForType.keys():
                    if paramName == "location":
                        locs = []
                        for id in indexInData:
                            locs.append((layout.location[layoutIndicesForType[id]]))
                        data = np.array(locs)
                    elif paramName in h5GroupForType:
                        dataSet = h5GroupForType[paramName]
                        try:
                            data = dataSet[indexInData]
                        except:
                            runLog.error(
                                "Failed to load index {} from {}@{}".format(indexInData, dataSet, (cycle, timeNode))
                            )
                            raise

                        if data.dtype.type is np.bytes_:
                            data = np.char.decode(data)

                        if dataSet.attrs.get("specialFormatting", False):
                            if dataSet.attrs.get("nones", False):
                                data = replaceNonsenseWithNones(data, paramName)
                            else:
                                raise ValueError(
                                    "History tracking for non-none special formatting not supported: {}, {}".format(
                                        paramName,
                                        {k: v for k, v in dataSet.attrs.items()},
                                    )
                                )
                    else:
                        # Nothing in the database, so use the default value
                        data = np.repeat(
                            parameters.byNameAndType(paramName, compType).default,
                            len(reorderedComps),
                        )

                    # iterating of np is not fast..
                    for c, val in zip(reorderedComps, data.tolist()):
                        if paramName == "location":
                            val = tuple(val)
                        elif isinstance(val, list):
                            val = np.array(val)

                        histData[c][paramName][cycle, timeNode] = val

        r = comps[0].getAncestor(lambda c: isinstance(c, Reactor))
        cycleNode = r.p.cycle, r.p.timeNode
        for c, paramHistories in histData.items():
            for paramName, hist in paramHistories.items():
                if cycleNode not in hist:
                    try:
                        hist[cycleNode] = c.p[paramName]
                    except Exception:
                        if paramName == "location":
                            hist[cycleNode] = c.spatialLocator.indices

        return histData

    @staticmethod
    def _writeAttrs(obj, group, attrs):
        """
        Handle safely writing attributes to a dataset, handling large data if necessary.

        This will attempt to store attributes directly onto an HDF5 object if possible, falling back to proper datasets
        and reference attributes if necessary. This is needed because HDF5 tries to fit attributes into the object
        header, which has limited space. If an attribute is too large, h5py raises a RuntimeError. In such cases, this
        will store the attribute data in a proper dataset and place a reference to that dataset in the attribute
        instead.

        In practice, this takes ``linkedDims`` attrs from a particular component type (like ``c00n00/Circle/id``) and
        stores them in new datasets (like ``c00n00/attrs/1_linkedDims``, ``c00n00/attrs/2_linkedDims``) and then sets
        the object's attrs to links to those datasets.
        """
        for key, value in attrs.items():
            try:
                obj.attrs[key] = value
            except RuntimeError as err:
                if "object header message is too large" not in err.args[0]:
                    raise

                runLog.info(f"Storing attribute `{key}` for `{obj}` into it's own dataset within `{group}/attrs`")

                if "attrs" not in group:
                    attrGroup = group.create_group("attrs")
                else:
                    attrGroup = group["attrs"]
                dataName = str(len(attrGroup)) + "_" + key
                attrGroup[dataName] = value

                # using a soft link here allows us to cheaply copy time nodes without needing to crawl through and
                # update object references.
                linkName = attrGroup[dataName].name
                obj.attrs[key] = "@{}".format(linkName)

    @staticmethod
    def _resolveAttrs(attrs, group):
        """
        Reverse the action of _writeAttrs.

        This reads actual attrs and looks for the real data in the datasets that the attrs were pointing to.
        """
        attr_link = re.compile("^@(.*)$")

        resolved = {}
        for key, val in attrs.items():
            try:
                if isinstance(val, h5py.h5r.Reference):
                    # Old style object reference. If this cannot be dereferenced, it is likely because mergeHistory was
                    # used to get the current database, which does not preserve references.
                    resolved[key] = group[val]
                elif isinstance(val, str):
                    m = attr_link.match(val)
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

    @staticmethod
    def _applyComponentNumberDensitiesMigration(comps, unpackedData):
        """
        Special migration from <= v0.5.1 component numberDensities parameter data type.

        old format: dict[str: float]
        new format: two numpy arrays
        - nuclides = np.array(dtype="S6")
        - numberDensities = np.array(dtype=np.float64)
        """
        for c, ndensDict in zip(comps, unpackedData):
            nuclides = np.array(list(ndensDict.keys()), dtype="S6")
            numberDensities = np.array(list(ndensDict.values()), dtype=np.float64)
            c.p["nuclides"] = nuclides
            c.p["numberDensities"] = numberDensities

    @staticmethod
    def getCycleNodeAtTime(dbPath, startTime, endTime, errorIfNotExactlyOne=True):
        """Given the path to an ARMI database file and a start and end time (in years), return the full set of all time
        nodes that correspond to that time period in the database.

        Parameters
        ----------
        dbPath : str
            File path to an ARMI database.
        startTime : int
            In years, start of the desired interval.
        endTime : int
            In years, end of the desired interval.
        errorIfNotExactlyOne : boolean
            Raise an error if more than one cycle/node combination is returned. Default is True.

        Returns
        -------
        list of strings
            A list of strings to the desired time interval, e.g.: ["c01n08", "c14n18EOL"]
        """
        # basic sanity checks
        assert startTime >= 0.0, f"The start time cannot be negative: {startTime}."
        assert endTime >= startTime, f"The end time ({endTime}) is not greater than the start time ({startTime})."

        # open the H5 file directly
        with h5py.File(dbPath, "r") as h5:
            # read time steps in H5 file
            thisTime = 0.0
            cycleNodes = []
            for h5Key in h5.keys():
                if h5Key == "inputs":
                    continue

                thisTime = h5[h5Key]["Reactor"]["time"][0]
                if thisTime >= endTime:
                    cycleNodes.append(h5Key)
                    break
                elif thisTime >= startTime:
                    cycleNodes.append(h5Key)

        # more validation
        if not cycleNodes:
            raise ValueError(f"Provided start time ({startTime}) was greater than the modeled period: {thisTime}.")
        elif errorIfNotExactlyOne and len(cycleNodes) != 1:
            raise ValueError(f"Did not find exactly one cycle/node pair: {cycleNodes}")

        return cycleNodes


def packSpecialData(
    arrayData: [np.ndarray, JaggedArray], paramName: str
) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
    """
    Reduce data that wouldn't otherwise play nicely with HDF5/numpy arrays to a format that will.

    This is the main entry point for conforming "strange" data into something that will both fit
    into a numpy array/HDF5 dataset, and be recoverable to its original-ish state when reading it
    back in. This is accomplished by detecting a handful of known offenders and using various HDF5
    attributes to store necessary auxiliary data. It is important to keep in mind that the data that
    is passed in has already been converted to a numpy array, so the top dimension is always
    representing the collection of composites that are storing the parameters. For instance, if we
    are dealing with a Block parameter, the first index in the numpy array of data is the block
    index; so if each block has a parameter that is a dictionary, ``data`` would be a ndarray,
    where each element is a dictionary. This routine supports a number of different things:

    * Dict[str, float]: These are stored by finding the set of all keys for all instances, and
      storing those keys as a list in an attribute. The data themselves are stored as arrays indexed
      by object, then key index. Dictionaries lacking data for a key store a nan in it's place. This
      will work well in instances where most objects have data for most keys.
    * Jagged arrays: These are stored by concatenating all of the data into a single, one-
      dimensional array, and storing attributes to describe the shapes of each object's data, and an
      offset into the beginning of each object's data.
    * Arrays with ``None`` in them: These are stored by replacing each instance of ``None`` with a
      magical value that shouldn't be encountered in realistic scenarios.

    Parameters
    ----------
    arrayData
        An ndarray or JaggedArray object storing the data that we want to stuff into the database.
        If the data is jagged, a special JaggedArray instance is passed in, which contains a 1D
        array with offsets and shapes.
    paramName
        The parameter name that we are trying to store. This is mostly used for diagnostics.

    See Also
    --------
    unpackSpecialData
    """
    if isinstance(arrayData, JaggedArray):
        data = arrayData.flattenedArray
    else:
        # Check to make sure that we even need to do this. If the numpy data type is not "O",
        # chances are we have nice, clean data.
        if arrayData.dtype != "O":
            return arrayData, {}
        else:
            data = arrayData

    attrs: Dict[str, Any] = {"specialFormatting": True}

    # make a copy of the data, so that the original is unchanged
    data = copy.copy(data)

    # Find locations of Nones.
    nones = np.where([d is None for d in data])[0]
    if len(nones) == data.shape[0]:
        # Everything is None, so why bother?
        return None, attrs

    if len(nones) > 0:
        attrs["nones"] = True

    # Pack different types of data
    if any(isinstance(d, dict) for d in data):
        # We're assuming that a dict is {str: float}.
        attrs["dict"] = True
        keys = sorted({k for d in data for k in d})
        data = np.array([[d.get(k, np.nan) for k in keys] for d in data])
        if data.dtype == "O":
            raise TypeError(f"Unable to coerce dictionary data into usable numpy array for {paramName}")
        # We store the union of all of the keys for all of the objects as a special "keys"
        # attribute, and store a value for all of those keys for all objects, whether or not there
        # is actually data associated with that key
        attrs["keys"] = np.array(keys).astype("S")

        return data, attrs
    elif isinstance(arrayData, JaggedArray):
        attrs["jagged"] = True
        attrs["offsets"] = arrayData.offsets
        attrs["shapes"] = arrayData.shapes
        attrs["noneLocations"] = arrayData.nones
        return data, attrs

    # conform non-numpy arrays to numpy
    for i, val in enumerate(data):
        if isinstance(val, (list, tuple)):
            data[i] = np.array(val)

    if not any(isinstance(d, np.ndarray) for d in data):
        # looks like 1-D plain-old-data
        data = replaceNonesWithNonsense(data, paramName, nones)
        return data, attrs
    elif any(isinstance(d, (tuple, list, np.ndarray)) for d in data):
        data = replaceNonesWithNonsense(data, paramName, nones)
        return data, attrs

    if len(nones) == 0:
        raise TypeError(f"Cannot write {paramName} to the database, it did not resolve to a numpy/HDF5 type.")

    runLog.error(f"Data unable to find special none value: {data}")
    raise TypeError(f"Failed to process special data for {paramName}")


def unpackSpecialData(data: np.ndarray, attrs, paramName: str) -> np.ndarray:
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
    np.ndarray
        An ndarray containing the closest possible representation of the data that was originally written to the
        database.

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
        nones = attrs["noneLocations"]
        data = JaggedArray.fromH5(data, offsets, shapes, nones, data.dtype, paramName)
        return data
    if attrs.get("dict", False):
        keys = np.char.decode(attrs["keys"])
        unpackedData = []
        assert data.ndim == 2
        for d in data:
            unpackedData.append({key: value for key, value in zip(keys, d) if not np.isnan(value)})
        return np.array(unpackedData)

    raise ValueError(
        "Do not recognize the type of special formatting that was applied to {}. Attrs: {}".format(
            paramName, {k: v for k, v in attrs.items()}
        )
    )


def collectBlockNumberDensities(blocks) -> Dict[str, np.ndarray]:
    """
    Collect block-by-block homogenized number densities for each nuclide.

    Long ago, composition was stored on block params. No longer; they are on the component numberDensity params. These
    block-level params, are still useful to see compositions in some visualization tools. Rather than keep them on the
    reactor model, we dynamically compute them here and slap them in the database. These are ignored upon reading and
    will not affect the results.

    Remove this once a better viz tool can view composition distributions. Also remove the try/except in ``_readParams``
    """
    nucNames = sorted(list(set(nucName for b in blocks for nucName in b.getNuclides())))
    nucBases = [nuclideBases.byName[nn] for nn in nucNames]
    # It's faster to loop over blocks first and get all number densities from each than it is to get one nuclide at a
    # time from each block because of area fraction calculations. So we use some RAM here instead.
    nucDensityMatrix = []
    for block in blocks:
        nucDensityMatrix.append(block.getNuclideNumberDensities(nucNames))
    nucDensityMatrix = np.array(nucDensityMatrix)

    dataDict = dict()
    for ni, nb in enumerate(nucBases):
        # the nth column is a vector of nuclide densities for this nuclide across all blocks
        dataDict[nb.getDatabaseName()] = nucDensityMatrix[:, ni]

    return dataDict
