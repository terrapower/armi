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

from armi.settings import setting2 as setting

CONF_AXIAL_DOLLARSS_PER = "axialDollarssPerK"

# used in perturbation theory
CONF_PERCENT_NA_REDUCTION = "percentNaReduction"
CONF_RADIAL_EXP_PT = "radialExpPT"
CONF_AXIAL_EXP_PT = "axialExpPT"
CONF_STRUCT_WORTH_PT = "structWorthPT"

CONF_BETA_COMPONENTS = "betaComponents"
CONF_DECAY_CONSTANTS = "decayConstants"

CONF_NUCLIDE_HALFLIFE_LIBRARY_PATH = "nuclideHalflifeLibraryPath"


def defineSettings():
    settings = [
        setting.Setting(
            CONF_AXIAL_DOLLARSS_PER,
            default=False,
            label="Axial $/K",
            description="Compute axial reactivity coefficients in $/K instead of $/kg. useful for RELAP.",
        ),
        setting.Setting(
            CONF_PERCENT_NA_REDUCTION,
            default=1.0,
            label="Density perturbation %",
            description="The percent that density will be perturbed in reactivity coefficients",
        ),
        setting.Setting(
            CONF_BETA_COMPONENTS,
            default=[],
            label="Beta Components",
            description="Manually set individual precursor group delayed neutron fractions",
        ),
        setting.Setting(
            CONF_DECAY_CONSTANTS,
            default=[],
            label="Decay Constants",
            description="Manually set individual precursor group delayed neutron decay constants",
        ),
        setting.Setting(
            CONF_RADIAL_EXP_PT,
            default=False,
            label="Radial Expansion Reactivity Coefficient",
            description="Compute the core-wide radial expansion reactivity coefficient with perturbation theory",
        ),
        setting.Setting(
            CONF_AXIAL_EXP_PT,
            default=False,
            label="Axial Expansion Reactivity Coefficient",
            description="Compute the core-wide fuel axial expansion reactivity coefficient with perturbation theory.",
        ),
        setting.Setting(
            CONF_STRUCT_WORTH_PT,
            default=False,
            label="Core wide Structure Density Reactivity Coefficient with perturbation theory",
            description="None",
        ),
        setting.Setting(
            CONF_NUCLIDE_HALFLIFE_LIBRARY_PATH,
            default="\\\\albert\\apps\\dev\\NuclearData\\RIPL\\halflives\\",
            label="Halflife Library Path",
            description="directory path to RIPL data for nuclide levels",
        ),
    ]
    return settings
