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
The db package is responsible for reading and writing the state of the reactor to/from disk.

As an ARMI run progresses, this is periodically updated as the primary output file.
It can also be an input file for follow-on analysis or restart runs.

This module contains factories for selecting and building DB-related objects.

When updating a db version
--------------------------
The code associated with reading and writing database files may not benefit from Don't
Repeat Yourself (DRY) practices in the same way as other code. Therefore, do not share
code between different major versions of the databases. Create a new module if you are
creating a new major database version.


Database revision changelog
---------------------------
 - 1: Originally, calculation results were stored in a SQL database.

 - 2: The storage format was changed to HDF5. This required less external
   infrastructure than SQL. However, the implementation did not store a complete
   model of a reactor, but a ghost of assembly, block, and reactor parameters that
   could be applied to an existing reactor model (so long as the dimensions were
   consistent). This was inconvenient and error prone.

 - 3: The HDF5 format was kept, but the schema was made more flexible to permit
   storing the entire reactor model. All objects in the ARMI Composite Model are
   written to the database, and the model can be completely recovered from just the
   HDF5 file.

     - 3.1: Improved the handling of reading/writing grids.

     - 3.2: Changed the strategy for storing large attributes to using a special
       string starting with an "@" symbol (e.g., "@/c00n00/attrs/5_linkedDims"). This
       was done to support copying time node datasets from one file to another without
       invalidating the references. Support was maintained for reading previous
       versions, by performing a ``mergeHistory()`` and converting to the new naming
       strategy, but the old version cannot be written.

     - 3.3: Compressed the way locations are stored in the database and allow
       MultiIndex locations to be read and written.

     - 3.4: Modified the way locations are stored in the database to include complete
       indices for indices that can be composed from multiple grids. Having complete
       indices allows for more efficient means of extracting information based on
       location, without having to compose the full model.
"""
import os
from typing import Optional, List, Tuple

from armi import settings
from armi.utils import pathTools
from armi import runLog
from armi.reactor import reactors

# re-export package components for easier import
from .permissions import Permissions
from .database3 import Database3, updateGlobalAssemblyNum
from .databaseInterface import DatabaseInterface
from .compareDB3 import compareDatabases
from .factory import databaseFactory


__all__ = [
    "Database3",
    "DatabaseInterface",
    "compareDatabases",
    "databaseFactory",
]


def loadOperator(pathToDb, loadCycle, loadNode, allowMissing=False):
    """
    Return an operator given the path to a database.

    Parameters
    ----------
    pathToDb : str
        The path of the database to load from.
    loadCycle : int
        The cycle to load the reactor state from.
    loadNode : int
        The time node to load the reactor from.
    allowMissing : bool
        Whether to emit a warning, rather than crash if reading a database
        with undefined parameters. Default False.

    See Also
    --------
    armi.operator.Operator.loadState:
        A method for loading reactor state that is useful if you already have an
        operator and a reactor object. loadOperator varies in that it supplies these
        given only a database file. loadState should be used if you are in the
        middle of an ARMI calculation and need load a different time step.

    Notes
    -----
    The operator will have a reactor attached that is loaded to the specified cycle
    and node. The operator will not be in the same state that it was at that cycle and
    node, only the reactor.

    Examples
    --------
    >>> o = db.loadOperator(r"pathToDatabase", 0, 1)
    >>> r = o.r
    >>> cs = o.cs
    >>> r.p.timeNode
    1
    >>> r.getFPMass()  # Note since it is loaded from step 1 there are fission products.
    12345.67
    """
    # `import armi` doesn't work if imported at top
    from armi import cases

    if not os.path.exists(pathToDb):
        raise ValueError(
            f"Specified database at path {pathToDb} does not exist. \n\n"
            "Double check that escape characters were correctly processed.\n"
            "Consider sending the full path, or change directory to be the directory "
            "of the database."
        )

    db = Database3(pathToDb, "r")
    with db:
        # init Case here as it keeps track of execution time and assigns a reactor
        # attribute. This attribute includes the time it takes to initialize the reactor
        # so creating a reactor from the database should be included.
        cs = db.loadCS()
        thisCase = cases.Case(cs)

        r = db.load(loadCycle, loadNode, allowMissing=allowMissing)

    settings.setMasterCs(cs)

    # Update the global assembly number because, if the user is loading a reactor from
    # blueprints and does not have access to an operator, it is unlikely that there is
    # another reactor that has alter the global assem num. Fresh cases typically want
    # this updated.
    updateGlobalAssemblyNum(r)

    o = thisCase.initializeOperator(r=r)
    runLog.important(
        "The operator will not be in the same state that it was at that cycle and "
        "node, only the reactor.\n"
        "The operator should have access to the same interface stack, but the "
        "interfaces will not be in the same state (they will be fresh instances "
        "of each interface as if __init__ was just called rather than the state "
        "during the run at this time node.)\n"
        "ARMI does not support loading operator states, as they are not stored."
    )
    return o


def convertDatabase(
    inputDBName: str,
    outputDBName: Optional[str] = None,
    outputVersion: Optional[str] = None,
    nodes: Optional[List[Tuple[int, int]]] = None,
):
    """
    Convert database files between different versions.

    Parameters
    ----------
    inputDB
        name of the complete hierarchy database
    outputDB
        name of the output database that should be consistent with XTView
    outputVersion
        version of the database to convert to. Defaults to latest version
    nodes
        optional list of specific (cycle,node)s to convert
    """
    dbIn = databaseFactory(inputDBName, permission=Permissions.READ_ONLY_FME)

    if dbIn.version == outputVersion:
        runLog.important(
            "The input database ({}) appears to already be in the desired "
            "format ({})".format(inputDBName, dbIn.version)
        )
        return

    outputDBName = outputDBName or "-converted".join(os.path.splitext(inputDBName))
    dbOut = databaseFactory(
        outputDBName, permission=Permissions.CREATE_FILE_TIE, version=outputVersion
    )
    # each DB load resets the verbosity to that of the run. Here we allow
    # conversion users to overpower it.
    conversionVerbosity = runLog.getVerbosity()
    runLog.extra(f"Converting {dbIn} to DB version {outputVersion}")
    with dbIn, dbOut:
        dbNodes = list(dbIn.genTimeSteps())

        if nodes is not None and any(node not in dbNodes for node in nodes):
            raise RuntimeError(
                "Some of the requested nodes are not in the source database.\n"
                "Requested: {}\n"
                "Present: {}".format(nodes, dbNodes)
            )

        # Making the bold assumption that we are working with HDF5
        h5In = _getH5File(dbIn)
        h5Out = _getH5File(dbOut)
        dbOut.writeInputsToDB(None, *dbIn.readInputsFromDB())

        for cycle, timeNode in dbNodes:
            if nodes is not None and (cycle, timeNode) not in nodes:
                continue
            runLog.extra(f"Converting cycle={cycle}, timeNode={timeNode}")
            timeStepsInOutDB = set(dbOut.genTimeSteps())
            r = dbIn.load(cycle, timeNode)
            if (r.p.cycle, r.p.timeNode) in timeStepsInOutDB:
                runLog.warning(
                    "Time step ({}, {}) is already in the output DB. This "
                    "is probably due to repeated cycle/timeNode in the source DB; "
                    "deleting the existing time step and re-writing".format(
                        r.p.cycle, r.p.timeNode
                    )
                )
                del dbOut[r.p.cycle, r.p.timeNode, None]
            runLog.setVerbosity(conversionVerbosity)
            dbOut.writeToDB(r)

            for auxPath in dbIn.genAuxiliaryData((cycle, timeNode)):
                name = next(reversed(auxPath.split("/")))
                auxOutPath = dbOut.getAuxiliaryDataPath((cycle, timeNode), name)
                runLog.important(
                    "Copying auxiliary data for time ({}, {}): {} -> {}".format(
                        cycle, timeNode, auxPath, auxOutPath
                    )
                )
                h5In.copy(auxPath, h5Out, name=auxOutPath)


def _getH5File(db):
    """Return the underlying h5py File that provides the backing storage for a database.

    This is done here because HDF5 isn't an official aspect of the base Database
    abstraction, and thus making this part of the base Database class interface wouldn't
    be ideal. **However**, we violate this assumption when working with "auxiliary"
    data, which use HDF5 features directly. To be able to convert, we need to be able to
    access and copy these groups, so we need access to the HDF5 file under the hood. To
    avoid this, we would need to come up with our own formalization of what a
    storage-agnostic aux data concept looks like. We can tackle that if/when we decode
    that we want to start using protobufs or whatever.

    All this being said, we are probably violating this already with genAuxiliaryData,
    but we have to start somewhere.
    """
    if isinstance(db, Database3):
        return db.h5db
    else:
        raise TypeError("Unsupported Database type ({})!".format(type(db)))
