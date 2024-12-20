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

"""Settings related to fuel performance."""

from armi.settings import setting
from armi.settings.settingsValidation import Query

CONF_AXIAL_EXPANSION = "axialExpansion"
CONF_BOND_REMOVAL = "bondRemoval"
CONF_CLADDING_STRAIN = "claddingStrain"
CONF_CLADDING_WASTAGE = "claddingWastage"
CONF_FGR_REMOVAL = "fgRemoval"
CONF_FGYF = "fissionGasYieldFraction"
CONF_FUEL_PERFORMANCE_ENGINE = "fuelPerformanceEngine"


def defineSettings():
    """Define generic fuel performance settings."""
    settings = [
        setting.Setting(
            CONF_FUEL_PERFORMANCE_ENGINE,
            default="",
            label="Fuel Performance Engine",
            description=(
                "Fuel performance engine that determines fission gas removal, bond removal,"
                " axial growth, wastage, and cladding strain."
            ),
            options=[""],
        ),
        setting.Setting(
            CONF_FGYF,
            default=0.25,
            label="Fission Gas Yield Fraction",
            description=(
                "The fraction of gaseous atoms produced per fission event, assuming a "
                "fission product yield of 2.0"
            ),
        ),
        setting.Setting(
            CONF_AXIAL_EXPANSION,
            default=False,
            label="Fuel Axial Expansion",
            description="Perform axial fuel expansion. This will adjust fuel block lengths.",
        ),
        setting.Setting(
            CONF_BOND_REMOVAL,
            default=False,
            label="Thermal Bond Removal",
            description="Toggles fuel performance bond removal. This will remove thermal bond from the fuel.",
        ),
        setting.Setting(
            CONF_FGR_REMOVAL,
            default=False,
            label="Fission Gas Removal",
            description="Toggles fuel performance fission gas removal.  This will remove fission gas from the fuel.",
        ),
        setting.Setting(
            CONF_CLADDING_WASTAGE,
            default=False,
            label="Cladding Wastage",
            description="Evaluate cladding wastage. ",
        ),
        setting.Setting(
            CONF_CLADDING_STRAIN,
            default=False,
            label="Cladding Strain",
            description="Evaluate cladding strain. ",
        ),
    ]
    return settings


def defineValidators(inspector):
    return [
        Query(
            lambda: (
                inspector.cs[CONF_AXIAL_EXPANSION]
                or inspector.cs[CONF_BOND_REMOVAL]
                or inspector.cs[CONF_FGR_REMOVAL]
                or inspector.cs[CONF_CLADDING_WASTAGE]
                or inspector.cs[CONF_CLADDING_STRAIN]
            )
            and inspector.cs[CONF_FUEL_PERFORMANCE_ENGINE] == "",
            "A fuel performance behavior has been selected but no fuel performance engine is selected.",
            "",
            inspector.NO_ACTION,
        ),
        Query(
            lambda: (
                inspector.cs[CONF_AXIAL_EXPANSION]
                or inspector.cs[CONF_BOND_REMOVAL]
                or inspector.cs[CONF_FGR_REMOVAL]
                or inspector.cs[CONF_CLADDING_WASTAGE]
                or inspector.cs[CONF_CLADDING_STRAIN]
            )
            and not inspector.cs["doTH"],
            "A fuel performance behavior has been selected which may require thermal-hydraulics.",
            "Would you like to turn the TH option on?",
            lambda: inspector._assignCS("doTH", True),
        ),
    ]
