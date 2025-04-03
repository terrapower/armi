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

import pathlib
from typing import Optional

import h5py

from armi.bookkeeping.db import permissions
from armi.bookkeeping.db.database import Database


def databaseFactory(dbName: str, permission: str, version: Optional[str] = None):
    """
    Return an appropriate object for interacting with a database file.

    Parameters
    ----------
    dbName: str
        Path to db file, e.g. `baseCase.h5`
    permission: str
        String defining permission, `r` for read only. See armi.bookkeeping.db.permissions
    version: str, optional
        Version of database you want to read or write. In most cases ARMI will
        auto-detect. For advanced users.

    Notes
    -----
    This is not a proper factory, as the different database versions do not present a
    common interface. However, this is useful code, since it at least creates an object
    based on some knowledge of how to probe around. This allows client code to just
    interrogate the type of the returned object to figure out to do based on whatever it
    needs.
    """
    dbPath = pathlib.Path(dbName)

    # if it's not an hdf5 file, we dont even know where to start...
    if dbPath.suffix != ".h5":
        raise RuntimeError("Unknown database format for {}".format(dbName))

    if permission in permissions.Permissions.read:
        if version is not None:
            raise ValueError("Cannot specify version when reading a database.")

        if not dbPath.exists() or not dbPath.is_file():
            raise ValueError(
                "Database file `{}` does not appear to be a " "file.".format(dbName)
            )

        # probe for the database version. We started adding these with "database 3", so if
        # databaseVersion is not present, assume it's the "old" version
        version = "2"
        tempDb = h5py.File(dbPath, "r")
        if "databaseVersion" in tempDb.attrs:
            version = tempDb.attrs["databaseVersion"]
        del tempDb

        majorversion = version.split(".")[0] if version else "2"
        if majorversion == "2":
            raise ValueError(
                'Database version 2 ("XTView database") is no longer '
                "supported. To migrate to a newer version, use version 0.1.5."
            )

        if majorversion == "3":
            return Database(dbPath, permission)

        raise ValueError("Unable to determine Database version for {}".format(dbName))
    elif permission in permissions.Permissions.write:
        majorversion = version.split(".")[0] if version else "3"
        if majorversion == "2":
            raise ValueError(
                'Database version 2 ("XTView database") is no longer '
                "supported. To migrate to a newer version, use version 0.1.5 to migrate."
            )
        if majorversion == "3":
            return Database(dbPath, permission)

    return None
