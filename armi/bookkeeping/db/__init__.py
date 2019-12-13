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

The database can be visualized through various tools such as XTVIEW.

This module contains factories for selecting and building DB-related objects
"""
import os
from typing import Optional

import armi
from armi import settings
from armi.utils import pathTools
from armi import runLog
from armi.reactor import reactors

# these imports flatten the required imports so that someone only needs to use `from
# armi.bookkeeping import db`
from . import database3
from .permissions import Permissions
from .database3 import Database3, DatabaseInterface
from .xtviewDB import XTViewDatabase
from .compareDB3 import compareDatabases
from .factory import databaseFactory


def loadOperator(pathToDb, loadCycle, loadNode):
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
    from armi import settings

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

        r = db.load(loadCycle, loadNode)
    settings.setMasterCs(cs)

    # Update the global assembly number because, if the user is loading a reactor from
    # blueprints and does not have access to an operator, it is unlikely that there is
    # another reactor that has alter the global assem num. Fresh cases typically want
    # this updated.
    database3.updateGlobalAssemblyNum(r)

    o = thisCase.initializeOperator(r=r)
    runLog.warning(
        "The operator provided is not in the same state as the operator was.\n"
        "When the reactor was at the prescribed cycle and node, it should have\n"
        "access to the same interface stack, but the interfaces will also not be in the "
        "same state.\n"
        "ARMI does not support loading operator states, as they are not stored."
    )
    return o


def copyDatabase(r, srcDB, tarDB):
    """Write the information stored in the source database to the target database

    Parameters
    ----------
    r : reactor
        This reactor should correspond to the data model housed in the srcDB
    srcDB : database
        Any implementation of the database in ARMI
    tarDB : database
        Any implementation of the database in ARMI

    """
    runLog.important(
        "Transfering data\n\tstored in {}\n\tacross {}\n\tto target {}".format(
            srcDB, r, tarDB
        )
    )
    tarDB._initDatabaseContact = True  # pylint: disable=protected-access
    for ts in range(srcDB.numTimeSteps):
        srcDB.updateFromDB(r, ts)
        tarDB.writeStateToDB(r)

    for misc in srcDB._getDataNamesToCompare():  # pylint: disable=protected-access
        data = srcDB.readDataFromDB(misc)
        tarDB.writeDataToDB(misc, data)
    runLog.important("Transfer complete")


def convertDatabase(
    inputDBName: str,
    outputDBName: Optional[str] = None,
    outputVersion: Optional[str] = None,
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
        # Making the bold assumption that we are working with HDF5
        h5In = _getH5File(dbIn)
        h5Out = _getH5File(dbOut)
        dbOut.writeInputsToDB(None, *dbIn.readInputsFromDB())

        for cycle, timeNode in dbIn.genTimeSteps():
            runLog.extra(f"Converting cycle={cycle}, timeNode={timeNode}")
            r = dbIn.load(cycle, timeNode)
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
    elif isinstance(db, XTViewDatabase):
        return db._hdf_file
    else:
        raise TypeError("Unsupported Database type ({})!".format(type(db)))
