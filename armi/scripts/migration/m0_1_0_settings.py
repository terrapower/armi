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

"""Migrate ARMI settings from old XML to new yaml."""
import io

from armi import runLog
from armi.settings import caseSettings
from armi.scripts.migration.base import SettingsMigration
from armi.settings import settingsIO


class ConvertXmlSettingsToYaml(SettingsMigration):
    """Convert XML settings to YAML settings"""

    fromVersion = "0.0.0"
    toVersion = "0.0.0"

    def _applyToStream(self):
        """Convert stream to yaml stream"""
        cs = caseSettings.Settings()
        reader = settingsIO.SettingsReader(cs)
        reader.readFromStream(self.stream)

        if reader.invalidSettings:
            runLog.info(
                "The following deprecated settings will be deleted:\n  * {}"
                "".format("\n  * ".join(list(reader.invalidSettings)))
            )

        _modify_settings(cs)
        writer = settingsIO.SettingsWriter(cs)
        newStream = io.StringIO()
        writer.writeYaml(newStream)
        newStream.seek(0)
        return newStream

    def _writeNewFile(self, newStream):
        if self.path.endswith(".xml"):
            self.path = self.path.replace(".xml", ".yaml")
        SettingsMigration._writeNewFile(self, newStream)


def _modify_settings(cs):
    if cs["runType"] == "Rx. Coeffs":
        runLog.info(
            "Converting deprecated Rx. Coeffs ``runType` setting to Snapshots. "
            "You may need to manually disable modules you don't want to run"
        )
        cs["runType"] = "Snapshots"
