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
Migrate input/output from one version of ARMI to another.

Users want to be able to upgrade to the latest version of the code without having to
invest a bunch of time in updating their previous input and output files. Users have up
to thousands of inputs that they want to keep working. Even more serious, follow-on
analysts who got an output database (including associated inputs) from an ARMI
power-user strongly prefer to be able to migrate old cases. Oftentimes, an output
database can be many GB large and be the result of many CPU-weeks, so there's monetary
and temporal value to be preserved.

Meanwhile, developers want to be able to make upgrades to the input and/or output to fix
bugs, ease the training and cognitive burden of new users, and so on.

Migrations are key to getting both of these big needs.

Migrations should generally happen in the background from the user's perspective, just
like happens in mainstream applications like word processors and spreadsheets.
"""

from . import (
    m0_1_0_settings,
    m0_1_3,
    m0_1_0_newDbFormat,
    crossSectionBlueprintsToSettings,
)

ACTIVE_MIGRATIONS = [
    m0_1_0_settings.ConvertXmlSettingsToYaml,
    m0_1_0_newDbFormat.ConvertDB2toDB3,
    m0_1_3.RemoveCentersFromBlueprints,
    m0_1_3.UpdateElementalNuclides,
    crossSectionBlueprintsToSettings.MoveCrossSectionsFromBlueprints,
]
