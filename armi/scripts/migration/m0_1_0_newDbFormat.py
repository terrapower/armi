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
Migrate ARMI databases to newer versions.

Oftentimes, code changes cause databases from previous versions
to become invalid, yet users still want to be able to load from
the old cases. These scripts assist in converting old
databases to new ones.

This is expected to be extended with version-dependent chains.
"""
import os
import io

import h5py

import armi
from armi import runLog
from armi import utils
from armi.reactor import geometry

from armi.scripts.migration.base import DatabaseMigration


class ConvertDB2toDB3(DatabaseMigration):
    """Convert ARMI DB version 2 to DB version 3."""

    def __init__(self, stream=None, path=None):
        DatabaseMigration.__init__(self, stream=stream, path=path)
        if stream:
            raise ValueError("Can only migrate database by path.")

    def apply(self):
        _migrateDatabase(self.path, _preCollector, _visit, _postApplier)


def _migrateDatabase(databasePath, preCollector, visitor, postApplier):
    """
    Generic database-traversing system to apply custom version-specific migrations.

    Parameters
    ----------
    databasePath : str
        Path to DB file to be converted
    preCollector : callable
        Function that acts on oldDB and produces some generic data object
    visitor : callable
        Function that will be called on each dataset of the old HDF5 database.
        This should map information into the new DB.
    postApplier : callable
        Function that will run after all visiting is done. Will have acecss
        to the pre-collected data.

    Raises
    ------
    OSError
        When database is not found.
    """
    if not os.path.exists(databasePath):
        raise OSError("Database file {} does not exist".format(databasePath))

    runLog.info("Migrating database file: {}".format(databasePath))
    runLog.info("Generating SHA-1 hash for original database: {}".format(databasePath))
    shaHash = utils.getFileSHA1Hash(databasePath)
    runLog.info("    Database: {}\n" "    SHA-1: {}".format(databasePath, shaHash))
    _remoteFolder, remoteDbName = os.path.split(databasePath)  # make new DB locally
    root, ext = os.path.splitext(remoteDbName)
    newDBName = root + "_migrated" + ext
    runLog.info("Copying database from {} to {}".format(databasePath, newDBName))
    with h5py.File(newDBName, "w") as newDB, h5py.File(databasePath, "r") as oldDB:

        preCollection = preCollector(oldDB)

        def closure(name, dataset):
            visitor(newDB, preCollection, name, dataset)

        oldDB.visititems(closure)

        # Copy all old database attributes to the new database (h5py AttributeManager has no update method)
        for key, val in oldDB.attrs.items():
            newDB.attrs[key] = val

        newDB.attrs["original-armi-version"] = oldDB.attrs["version"]
        newDB.attrs["original-db-hash"] = shaHash
        newDB.attrs["original-databaseVersion"] = oldDB.attrs["databaseVersion"]
        newDB.attrs["version"] = armi.__version__

        postApplier(oldDB, newDB, preCollection)

    runLog.info("Successfully generated migrated database file: {}".format(newDBName))


def _visit(newDB, preCollection, name, dataset):

    updated = False
    # runLog.important(f"Visiting Dataset {name}")
    path = name.split("/")
    if path[0] == "inputs":
        pass
    elif len(path) > 1 and path[1] == "layout":
        updated = _updateLayout(newDB, preCollection, name, dataset)
    elif len(path) == 3:
        updated = _updateParams(newDB, preCollection, name, dataset)

    if not updated:
        if isinstance(dataset, h5py.Group):
            # Skip groups because they come along with copied datasets
            msg = "Skipped"
        else:
            newDB.copy(dataset, dataset.name)
            msg = "Copied"
    else:
        msg = "Updated"

    runLog.important(f"{msg} Dataset {name}")


def _preCollector(oldDB):
    preCollection = {}
    preCollection.update(_collectParamRenames())
    preCollection.update(_collectSymmetry(oldDB))
    return preCollection


def _postApplier(oldDB, newDB, preCollection):
    pass


def _updateLayout(newDB, preCollection, name, dataset):
    path = name.split("/")
    if len(path) == 4 and path[2] == "grids" and path[3] != "type":
        # node/layout/grids/4
        if "symmetry" not in dataset:
            newDB.create_dataset(f"{name}/symmetry", data=preCollection["symmetry"])
        if "geomType" not in dataset:
            newDB.create_dataset(f"{name}/geomType", data=preCollection["geomType"])

        # maintain attrs on group if we just made it
        gridGroup = newDB[f"{name}"]
        for key, val in dataset.attrs.items():
            gridGroup.attrs[key] = val

        return True
    return False


def _updateParams(newDB, preCollection, name, dataset):
    """
    Visit parameters and apply migration transformations.
    
    Does not affect input or layout.
    """
    renames = preCollection["paramRenames"]
    updated = _applyRenames(newDB, renames, name, dataset)
    return updated


def _collectParamRenames():
    return {"paramRenames": armi.getApp().getParamRenames()}


def _collectSymmetry(oldDB):
    """Read symmetry and geomType off old-style geometry input str in DB."""
    geomPath = "/inputs/geomFile"
    if geomPath in oldDB:
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromStream(io.StringIO(oldDB["inputs/geomFile"][()]))
    return {"symmetry": geom.symmetry, "geomType": geom.geomType}


def _applyRenames(newDB, renames, name, dataset):
    node, paramType, paramName = name.split("/")
    if paramName in renames:
        runLog.important("Renaming `{}` -> `{}`.".format(paramName, renames[paramName]))
        paramName = renames[paramName]
        newDB.copy(dataset, "{}/{}/{}".format(node, paramType, paramName))
        return True
    return False
