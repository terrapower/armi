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

from armi.cli.entryPoint import EntryPoint


class MigrateInputs(EntryPoint):
    """Migrate ARMI Inputs to Latest ARMI Code Base"""

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
        from armi.scripts.migration import migrate_inputs

        if self.args.settings_path:
            migrate_inputs.migrate_settings(self.args.settings_path)
        if self.args.database_path:
            migrate_inputs.migrate_database(self.args.database_path)
