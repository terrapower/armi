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
from armi.settings import caseSettings

# Order required to populate the parameters.DEFINITIONS
from armi.reactor import (
    reactorParameters,
    blockParameters,
    assemblyParameters,
)  # pylint: disable=unused-import
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


if __name__ == "__main__":
    runLog.important(
        "Run migration script through the ARMI migrate input entry point.\n"
        "python -m armi migrate_inputs --settings_path path_to_settings.yaml "
        "--database path_to_database.h5"
    )
