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

"""Migrate ARMI Inputs to the Latest Code Base."""
import collections
import os
import re

import h5py

import armi
from armi import runLog
from armi.reactor import geometry
from armi.settings import caseSettings

# Order required to populate the parameters.DEFINITIONS
from armi.reactor import (
    reactorParameters,
    blockParameters,
    assemblyParameters,
)  # pylint: disable=unused-import
from armi.reactor import reactors, blocks, assemblies
from armi.reactor import parameters
from armi import utils

VALID_PARAMETERS_BY_GROUP = collections.defaultdict(
    lambda: None
)  # Return None when key does not exist


def migrate_settings(settings_path):
    """Migrate a settings file to be compatible with the latest ARMI code base."""
    if not os.path.exists(settings_path):
        raise ValueError("Case settings file {} does not exist".format(settings_path))

    runLog.info("Migrating case settings: {}".format(settings_path))
    shaHash = utils.getFileSHA1Hash(settings_path)
    runLog.info("\Settings: {}\n" "\tSHA-1: {}".format(settings_path, shaHash))
    cs = caseSettings.Settings()
    reader = cs.loadFromInputFile(settings_path, handleInvalids=False)
    if reader.invalidSettings:
        runLog.info(
            "The following deprecated settings will be deleted:\n  * {}"
            "".format("\n  * ".join(list(reader.invalidSettings)))
        )

    _modify_settings(cs)
    newSettingsInput = cs.caseTitle + "_migrated.yaml"
    cs.writeToYamlFile(newSettingsInput)
    runLog.info(
        "Successfully generated migrated settings file: {}".format(newSettingsInput)
    )


def _modify_settings(cs):
    if cs["runType"] == "Rx. Coeffs":
        runLog.info(
            "Converting deprecated Rx. Coeffs ``runType` setting to Snapshots. "
            "You may need to manually disable modules you don't want to run"
        )
        cs["runType"] = "Snapshots"


def migrate_database(database_path):
    """Migrate the database to be compatible with the latest ARMI code base."""
    if not os.path.exists(database_path):
        raise ValueError("Database file {} does not exist".format(database_path))

    runLog.info("Migrating database file: {}".format(database_path))
    runLog.info("Generating SHA-1 hash for original database: {}".format(database_path))
    shaHash = utils.getFileSHA1Hash(database_path)
    runLog.info("    Database: {}\n" "    SHA-1: {}".format(database_path, shaHash))
    _remoteFolder, remoteDbName = os.path.split(database_path)  # make new DB locally
    root, ext = os.path.splitext(remoteDbName)
    newDBName = root + "_migrated" + ext
    runLog.info("Copying database from {} to {}".format(database_path, newDBName))
    with h5py.File(newDBName, "w") as newDB, h5py.File(database_path, "r") as oldDB:

        typeNames = _getTypeNames(oldDB)

        def closure(name, dataset):
            _copyValidDatasets(newDB, typeNames, name, dataset)

        oldDB.visititems(closure)

        # Copy all old database attributes to the new database (h5py AttributeManager has no update method)
        for key, val in oldDB.attrs.items():
            newDB.attrs[key] = val

        newDB.attrs["original-db-version"] = oldDB.attrs["version"]
        newDB.attrs["original-db-hash"] = shaHash
        newDB.attrs["version"] = armi.__version__

        _writeAssemType(oldDB, newDB, typeNames)

    runLog.info("Successfully generated migrated database file: {}".format(newDBName))


def _copyValidDatasets(newDB, typeNames, name, dataset):
    renames = armi.getApp().getParamRenames()
    if isinstance(dataset, h5py.Group):
        runLog.important("Skipping Group {}".format(dataset))
        return

    elif name.startswith("StringMappings"):
        runLog.important("Skipping dataset {}".format(dataset))
        return

    runLog.important("Visiting Dataset {}".format(name))
    try:
        # '0/blocks/nNa' -> _node = '0', paramType = 'blocks', paramName = 'nNa'
        node, paramType, paramName = name.split("/")
        validParameters = VALID_PARAMETERS_BY_GROUP[paramType]

        if validParameters is None:
            runLog.warning(
                "Unexpected entry in database `{}` being copied.".format(name)
            )

        elif paramName in renames:
            while paramName in renames:
                runLog.important(
                    "Renaming `{}` -> `{}`.".format(
                        paramName, renames[paramName]
                    )
                )
                paramName = renames[paramName]

        elif paramName in {"typeNumBlock"}:
            newName = "type"
            runLog.important("Renaming `{}` -> `{}`.".format(paramName, newName))
            newDB["{}/{}/{}".format(node, paramType, newName)] = [
                typeNames[paramName][oldVal] for oldVal in dataset.value[:]
            ]
            return

        elif paramName not in validParameters:
            runLog.warning(
                "Invalid Parameter {} in the Database. Deleting Parameter `{}` from Dataset `{}`".format(
                    paramName, paramName, dataset.name
                )
            )
            return

        newDB.copy(dataset, "{}/{}/{}".format(node, paramType, paramName))
    except ValueError:
        # Skip checking for an invalid parameter if the structure is not correct (i.e., not length 3)
        newDB.copy(dataset, dataset.name)


def _getTypeNames(oldDB):
    if "StringMappings" not in oldDB:
        return

    index = oldDB["StringMappings/Classifier"][:]
    assemIndices = index == "AN"
    blockIndices = index == "BN"

    values = oldDB["StringMappings/Val"][:]
    strings = oldDB["StringMappings/String"][:]

    typeNames = {}
    typeNames["typeNumAssem"] = dict(zip(values[assemIndices], strings[assemIndices]))
    typeNames["typeNumBlock"] = dict(zip(values[blockIndices], strings[blockIndices]))

    return typeNames


def _writeAssemType(oldDB, newDB, typeNames):
    """
    Write TN/assemblies/type strings and TN/reactors/symmetry.

    assemblies/assemType was not a thing, need to find the blocks/assemTypeNum and map back to assemblies/type.
    """
    if "Materials" not in oldDB:
        runLog.important(
            "oldDB does not have a /Materials group, assuming assembly type set properly"
        )
        return

    ringPosToBlockIndex = {}

    for blockIndex, locationUniqueInt in enumerate(oldDB["Materials/Material"][:]):
        # block data is in a constant order, defined by Materials/Material which is an old-style location string
        uniqueIntAsString = "{:9d}".format(locationUniqueInt)
        ring = int(uniqueIntAsString[:-5])
        pos = int(uniqueIntAsString[-5:-2])
        axial = int(uniqueIntAsString[-2:])

        if axial != 0:  # assume the bottom is grid plate and might have incorrect type
            ringPosToBlockIndex[(ring, pos)] = blockIndex

    for timestep in (k for k in newDB.keys() if re.match(r"^\d+$", k)):
        rings = newDB["{}/assemblies/Ring".format(timestep)][:]
        positions = newDB["{}/assemblies/Pos".format(timestep)][:]
        assemTypes = []

        # so, we could use newDB['{}/blocks/assemType'], which would be more direct, but computing from the original may
        # be more forward compatible in that there may not be a need for blocks to have assemType in the future
        blockTypeNums = oldDB["{}/blocks/typeNumAssem".format(timestep)][:]
        fullCore = False
        for ring, pos in zip(rings, positions):
            if (ring, pos) == (3, 5):
                fullCore = True
            assemTypes.append(
                typeNames["typeNumAssem"][blockTypeNums[ringPosToBlockIndex[ring, pos]]]
            )

        runLog.important("writing {}/assemblies/type".format(timestep))
        newDB["{}/assemblies/type".format(timestep)] = assemTypes

        # dynamically determining the symmetry is a bit awkward, since we have no way to know what the boundary
        # condition was without the original inputs (presumably they exist...)
        symmetry = (
            geometry.FULL_CORE if fullCore else geometry.THIRD_CORE + geometry.PERIODIC
        )
        newDB["{}/reactors/symmetry".format(timestep)] = [symmetry]
        runLog.warning(
            "Determined {}/reactors/symmetry to be `{}`.".format(timestep, symmetry)
        )


if __name__ == "__main__":
    runLog.important(
        "Run migration script through the ARMI migrate input entry point.\n"
        "python -m armi migrate_inputs --settings_path path_to_settings.yaml "
        "--database path_to_database.h5"
    )
