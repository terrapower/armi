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

"""Settings related to the ARMI database."""

from armi.settings import setting

CONF_DB = "db"
CONF_DEBUG_DB = "debugDB"
CONF_RELOAD_DB_NAME = "reloadDBName"
CONF_LOAD_FROM_DB_EVERY_NODE = "loadFromDBEveryNode"
CONF_SYNC_AFTER_WRITE = "syncDbAfterWrite"
CONF_FORCE_DB_PARAMS = "forceDbParams"


def defineSettings():
    """Define settings for the interface."""
    settings = [
        setting.Setting(
            CONF_DB,
            default=True,
            label="Activate Database",
            description="Write the state information to a database at every timestep",
        ),
        setting.Setting(
            CONF_DEBUG_DB,
            default=False,
            label="Debug Database",
            description="Write state to DB with a unique timestamp or label.",
        ),
        setting.Setting(
            CONF_RELOAD_DB_NAME,
            default="",
            label="Database Input File",
            description="Name of the database file to load initial conditions from",
            oldNames=[("snapShotDB", None)],
        ),
        setting.Setting(
            CONF_LOAD_FROM_DB_EVERY_NODE,
            default=False,
            label="Load Database at EveryNode",
            description="Every node loaded from reference database",
        ),
        setting.Setting(
            CONF_SYNC_AFTER_WRITE,
            default=True,
            label="Sync Database After Write",
            description=(
                "Copy the output database from the fast scratch space to the shared network drive after each write."
            ),
        ),
        setting.Setting(
            CONF_FORCE_DB_PARAMS,
            default=[],
            label="Force Database Write of Parameters",
            description=(
                "A list of parameter names that should always be written to the "
                "database, regardless of their Parameter Definition's typical saveToDB "
                "status. This is only honored if the DatabaseInterface is used."
            ),
        ),
    ]
    return settings
