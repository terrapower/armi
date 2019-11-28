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
Entry point into ARMI to migrate inputs to the latest version of ARMI.
"""

import os

from armi.cli.entryPoint import EntryPoint
from armi.scripts.migration import ACTIVE_MIGRATIONS, base
from armi.utils import directoryChangers


class MigrateInputs(EntryPoint):
    """Migrate ARMI Inputs and/or outputs to Latest ARMI Code Base"""

    name = "migrate-inputs"

    def addOptions(self):
        self.parser.add_argument(
            "--settings-path",
            "--cs",
            help="Migrate a case settings file to be compatible with the latest ARMI code base",
            type=str,
        )
        self.parser.add_argument(
            "--database-path",
            "--db",
            help="Migrate a database file to be compatible with the latest ARMI code base",
            type=str,
        )

    def invoke(self):
        """
        Run the entry point
        """
        if self.args.settings_path:
            path, _fname = os.path.split(self.args.settings_path)
            with directoryChangers.DirectoryChanger(path):
                self._migrate(self.args.settings_path, self.args.database_path)
        else:
            self._migrate(self.args.settings_path, self.args.database_path)

    def _migrate(self, settingsPath, dbPath):
        """
        Run all migrations.

        Notes
        -----
        Some migrations change the paths so we update them one by one.
        For example, a migration converts a settings file from xml to yaml.
        """
        for migrationI in ACTIVE_MIGRATIONS:
            if (
                issubclass(
                    migrationI, (base.SettingsMigration, base.BlueprintsMigration)
                )
                and settingsPath
            ):
                mig = migrationI(path=settingsPath)
                mig.apply()
                if issubclass(migrationI, base.SettingsMigration):
                    # don't update on blueprints migration paths, that's not settings!
                    settingsPath = mig.path
            elif issubclass(migrationI, base.DatabaseMigration) and dbPath:
                mig = migrationI(path=dbPath)
                mig.apply()
                dbPath = mig.path
