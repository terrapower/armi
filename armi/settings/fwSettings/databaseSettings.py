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
CONF_DB_STORAGE_AFTER_CYCLE = "dbStorageAfterCycle"
CONF_ZERO_OUT_NUCLIDES_NOT_IN_DB = "zeroOutNuclidesNotInDB"
CONF_SYNC_AFTER_WRITE = "syncDbAfterWrite"


def defineSettings():
    settings = [
        setting.Setting(
            CONF_DB,
            default=True,
            label="Activate Database",
            description="Write the state information to a database at every timestep.",
        ),
        setting.Setting(CONF_DEBUG_DB, default=False, label="Debug DB"),
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
            CONF_DB_STORAGE_AFTER_CYCLE,
            default=0,
            label="DB Storage After Cycle",
            description="Only store cycles after this cycle in the DB (to save storage space)",
        ),
        setting.Setting(
            CONF_ZERO_OUT_NUCLIDES_NOT_IN_DB,
            default=True,
            label="Load Nuclides not in Database",
            description="If a nuclide was added to the problem after a previous case was run, deactivate this to let it survive in a restart run",
        ),
        setting.Setting(
            CONF_SYNC_AFTER_WRITE,
            default=False,
            label="Sync DB after write",
            description=(
                "Copy the output DB from the fast scratch space to the shared network drive "
                "after each write."
            ),
        ),
    ]
    return settings
