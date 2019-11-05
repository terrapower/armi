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

import os
from typing import Optional

from armi.bookkeeping.db.database3 import Database3
from armi.bookkeeping.db import permissions
from armi.bookkeeping.db.xtviewDB import XTViewDatabase


def databaseFactory(dbName: str, permission: str, version: Optional[str] = None):
    """
    Return an appropriate object for interacting with a database file.

    This is not a proper factory, as the different database versions do not present a
    common interface. However, this is useful code, since it at least creates an object
    based on some knowledge of how to probe around. This allows client code to just
    interrogate the type of the returned object to figure out to do based on whatever it
    needs.
    """

    import h5py

    # if it's not an hdf5 file, we dont even know where to start...
    if os.path.splitext(dbName)[1] != ".h5":
        raise RuntimeError("Unknown database format for {}".format(dbName))

    if permission in permissions.Permissions.read:
        if version is not None:
            raise ValueError("Cannot specify version when reading a database.")

        # probe for the database version. We started adding these with "database 3", so if
        # databaseVersion is not present, assume it's the "old" version
        version = "2"
        tempDb = h5py.File(dbName, "r")
        if "databaseVersion" in tempDb.attrs:
            version = tempDb.attrs["databaseVersion"]
        del tempDb

        majorversion = version.split(".")[0] if version else "2"
        if majorversion == "2":
            return XTViewDatabase(dbName, permission)

        if majorversion == "3":
            return Database3(dbName, permission)

        raise ValueError("Unable to determine Database version for {}".format(dbName))

    elif permission in permissions.Permissions.write:
        majorversion = version.split(".")[0] if version else "3"
        if majorversion == "2":
            return XTViewDatabase(dbName, permission)
        if majorversion == "3":
            return Database3(dbName, permission)
