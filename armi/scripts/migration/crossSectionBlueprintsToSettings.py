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
Migrate compound cross section settings from blueprints file to settings file.

This setting was originally stored in blueprints just because yaml was more
conducive than XML for a compound setting. After we migrated the settings
system to YAML, it was much more natural to put this setting in the settings 
file. Along the way, we renamed some of the input fields as well. 

This deletes the ``cross sections`` section from the blueprints file
and adds a valid one into the settings file. 

It manually reads the blueprints file rather than parsing it to ensure
round-trippiness even with yaml-native links. 
"""

import io
import shutil
import os

from ruamel.yaml import YAML

from armi import runLog
from armi.settings import caseSettings
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.physics.neutronics.crossSectionSettings import *
from armi.scripts.migration.base import SettingsMigration
from armi.settings import settingsIO


class MoveCrossSectionsFromBlueprints(SettingsMigration):
    """
    Move cross sections settings from blueprints to settings.

    This modifies both settings and blueprints.
    """

    fromVersion = "0.0.0"
    toVersion = "0.1.0"

    def _applyToStream(self):
        cs = caseSettings.Settings()
        reader = settingsIO.SettingsReader(cs)
        reader.readFromStream(self.stream)
        self.stream.close()
        cs.path = self.path

        migrateCrossSectionsFromBlueprints(cs)
        writer = settingsIO.SettingsWriter(cs)
        newStream = io.StringIO()
        writer.writeYaml(newStream)
        newStream.seek(0)
        return newStream

    def _backupOriginal(self):
        """Don't actually back up because it's done below."""

    def _writeNewFile(self, newStream):
        """Skip writing new file since it's handled below."""


def migrateCrossSectionsFromBlueprints(settingsObj):
    settingsPath = settingsObj.path
    runLog.info(
        "Migrating cross section settings from blueprints file to settings file ({})...".format(
            settingsPath
        )
    )
    cs = caseSettings.Settings()
    cs.loadFromInputFile(settingsPath)

    fullBlueprintsPath = os.path.join(cs.inputDirectory, cs["loadingFile"])
    origXsInputLines = _convertBlueprints(fullBlueprintsPath)
    if not origXsInputLines:
        runLog.warning(
            "No old input found in {}. Aborting migration.".format(fullBlueprintsPath)
        )
        return cs
    newXsData = _migrateInputData(origXsInputLines)
    _writeNewSettingsFile(cs, newXsData)
    # cs now has a proper crossSection setting

    _finalize(fullBlueprintsPath, settingsPath)
    # update the existing cs with the new setting in memory so the GUI doesn't wipe it out!
    settingsObj[CONF_CROSS_SECTION] = cs.settings[CONF_CROSS_SECTION].dump()
    return cs


def _convertBlueprints(bpPath):
    origXsInput = []
    active = False
    with open(bpPath) as bpIn, open(bpPath + ".new", "w") as bpOut:
        for line in bpIn:
            if line.startswith("cross sections:"):
                active = True
            elif active and not line.startswith(" "):
                active = False

            if active:
                origXsInput.append(line)
            else:
                bpOut.write(line)
    return origXsInput


def _migrateInputData(origXsInputLines):
    """Take spaces in labels out and return dict."""
    conversions = {
        "critical buckling": CONF_BUCKLING,
        "block representation": CONF_BLOCK_REPRESENTATION,
        "driver id": CONF_DRIVER,
        "nuclear reaction driver": CONF_REACTION_DRIVER,
        "valid block types": CONF_BLOCKTYPES,
        "external driver": CONF_EXTERNAL_DRIVER,
        "use homogenized block composition": CONF_HOMOGBLOCK,
        "internal rings": CONF_INTERNAL_RINGS,
        "external rings": CONF_EXTERNAL_RINGS,
        "merge into clad": CONF_MERGE_INTO_CLAD,
        "file location": CONF_FILE_LOCATION,
        "mesh points per cm": CONF_MESH_PER_CM,
    }
    yaml = YAML()
    oldXsData = yaml.load(io.StringIO("\n".join(origXsInputLines)))
    newXsData = {}
    for xsID, xsIdData in oldXsData["cross sections"].items():
        newIdData = {}
        for label, val in xsIdData.items():
            newIdData[conversions.get(label, label)] = val
        newXsData[xsID] = newIdData
    return newXsData


def _writeNewSettingsFile(cs, newXsInput):
    cs[CONF_CROSS_SECTION] = newXsInput
    cs.writeToYamlFile(cs.path + ".new")


def _finalize(bpPath, csPath):
    """
    Actually overwrite the original files if previous steps completed.

    This ensures we don't get partially migrated and then crash.
    """
    shutil.move(bpPath, bpPath + "-migrated")
    shutil.move(bpPath + ".new", bpPath)

    shutil.move(csPath, csPath + "-migrated")
    shutil.move(csPath + ".new", csPath)


if __name__ == "__main__":
    import sys

    cs = caseSettings.Settings()
    cs.loadFromInputFile(sys.argv[1])
    migrateCrossSectionsFromBlueprints(cs)
