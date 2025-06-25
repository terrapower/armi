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

from armi import runLog
from armi.bookkeeping.db.compareDB3 import compareDatabases

# re-export package components for easier import
from armi.bookkeeping.db.database import Database
from armi.bookkeeping.db.databaseInterface import DatabaseInterface
from armi.bookkeeping.db.factory import databaseFactory

__all__ = [
    "Database",
    "DatabaseInterface",
    "compareDatabases",
    "databaseFactory",
]


def loadOperator(
    pathToDb,
    loadCycle,
    loadNode,
    statePointName=None,
    allowMissing=False,
    handleInvalids=True,
    callReactorConstructionHook=False,
):
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
    statePointName: str
        State point name at the end, E.G. `EOC` or `EOL`.
        Full name would be C0N2EOC, see database.getH5GroupName
    allowMissing : bool
        Whether to emit a warning, rather than crash if reading a database
        with undefined parameters. Default False.
    handleInvalids : bool
        Whether to check for invalid settings. Default True.
    callReactorConstructionHook : bool
        Flag for whether the beforeReactorConstruction plugin hook should be executed. Default is False.

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

    db = Database(pathToDb, "r")
    with db:
        # init Case here as it keeps track of execution time and assigns a reactor
        # attribute. This attribute includes the time it takes to initialize the reactor
        # so creating a reactor from the database should be included.
        cs = db.loadCS(handleInvalids=handleInvalids)
        thisCase = cases.Case(cs)
        r = db.load(
            loadCycle,
            loadNode,
            cs=cs,
            statePointName=statePointName,
            allowMissing=allowMissing,
            handleInvalids=handleInvalids,
            callReactorConstructionHook=callReactorConstructionHook,
        )

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
    if isinstance(db, Database):
        return db.h5db
    else:
        raise TypeError("Unsupported Database type ({})!".format(type(db)))
