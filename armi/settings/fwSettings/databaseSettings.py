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

from armi.settings import setting2 as setting


CONF_DB = "db"
CONF_DEBUG_DB = "debugDB"
CONF_RELOAD_DB_NAME = "reloadDBName"
CONF_BLOCK_TYPES_TO_IGNORE_ON_DB_LOADING = "blockTypesToIgnoreOnDBLoading"
CONF_BLOCK_PARAMETER_NAMES_TO_IGNORE_ON_DB_LOADING = (
    "blockParameterNamesToIgnoreOnDBLoading"
)
CONF_BLOCK_PARAMETER_NAMES_TO_INCLUDE_ON_DB_LOADING = (
    "blockParameterNamesToIncludeOnDBLoading"
)
CONF_UPDATE_MASS_FRACTIONS_FROM_DB = "updateMassFractionsFromDB"
CONF_LOAD_FROM_DB_EVERY_NODE = "loadFromDBEveryNode"
CONF_UPDATE_INDIVIDUAL_ASSEMBLY_NUMBERS_ON_DB_LOAD = (
    "updateIndividualAssemblyNumbersOnDbLoad"
)
CONF_DB_STORAGE_AFTER_CYCLE = "dbStorageAfterCycle"
CONF_ZERO_OUT_NUCLIDES_NOT_IN_DB = "zeroOutNuclidesNotInDB"


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
        ),
        setting.Setting(
            CONF_BLOCK_TYPES_TO_IGNORE_ON_DB_LOADING,
            default=[],
            label="Excluded Block Types",
            description="Block types to exclude when loading the database",
        ),
        setting.Setting(
            CONF_BLOCK_PARAMETER_NAMES_TO_IGNORE_ON_DB_LOADING,
            default=[],
            label="Excluded Block Parameters",
            description="Block parameter data (names) to exclude when loading from the database",
        ),
        setting.Setting(
            CONF_BLOCK_PARAMETER_NAMES_TO_INCLUDE_ON_DB_LOADING,
            default=[],
            label="Exclusive Block Parameters",
            description="Block parameter data (names) to load from the database",
        ),
        setting.Setting(
            CONF_UPDATE_MASS_FRACTIONS_FROM_DB,
            default=True,
            label="Update Mass Fractions on Load",
            description="Update the mass fractions when loading from the database",
        ),
        setting.Setting(
            CONF_LOAD_FROM_DB_EVERY_NODE,
            default=False,
            label="Load Database at EveryNode",
            description="Every node loaded from reference database",
        ),
        setting.Setting(
            CONF_UPDATE_INDIVIDUAL_ASSEMBLY_NUMBERS_ON_DB_LOAD,
            default=True,
            label="Update Assembly Numbers on Load",
            description="When a DB is loaded, this will update assembly numbers as well as other state",
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
    ]
    return settings
