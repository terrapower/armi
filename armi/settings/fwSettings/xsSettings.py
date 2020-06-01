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

"""Settings related to the cross section."""

from armi.settings import setting


CONF_CLEAR_XS = "clearXS"
CONF_PRELOAD_CORE_XS = "preloadCoreXS"
CONF_DPA_XS_DIRECTORY_PATH = "DPAXSDirectoryPath"
CONF_MINIMUM_FISSILE_FRACTION = "minimumFissileFraction"
CONF_MINIMUM_NUCLIDE_DENSITY = "minimumNuclideDensity"
CONF_INFINITE_DILUTE_CUTOFF = "infiniteDiluteCutoff"
CONF_TOLERATE_BURNUP_CHANGE = "tolerateBurnupChange"
CONF_XS_BLOCK_REPRESENTATION = "xsBlockRepresentation"
CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION = (
    "disableBlockTypeExclusionInXsGeneration"
)
CONF_XS_KERNEL = "xsKernel"
CONF_XS_SCATTERING_ORDER = "xsScatteringOrder"
CONF_XS_BUCKLING_CONVERGENCE = "xsBucklingConvergence"
CONF_XS_EIGENVALUE_CONVERGENCE = "xsEigenvalueConvergence"


def defineSettings():
    settings = [
        setting.Setting(
            CONF_CLEAR_XS,
            default=False,
            label="Clear XS",
            description="Delete all cross section libraries before regenerating them.",
        ),
        setting.Setting(
            CONF_PRELOAD_CORE_XS,
            default=False,
            label="Preload Core XS",
            description=(
                "When enabled, the ISOTXS in the working directory will be loaded onto the core. "
                "This is useful when a XS set is not being generated explicitly, but XS data is still needed for the analysis. "
            ),
        ),
        setting.Setting(
            CONF_DPA_XS_DIRECTORY_PATH,
            default="\\\\albert\\apps\\dev\\mc2\\3.2.2\\libraries\\endfb-vii.0\\damage_xs",
            label="DPA XS Directory Path",
            description="DPA XS Directory Path",
            options=[
                "\\\\albert\\apps\\dev\\mc2\\3.2.2\\libraries\\endfb-vii.0\\damage_xs"
            ],
        ),
        setting.Setting(
            CONF_MINIMUM_FISSILE_FRACTION,
            default=0.045,
            label="Minimum Fissile Fraction",
            description="Minimum fissile fraction (fissile number densities / heavy metal number densities).",
        ),
        setting.Setting(
            CONF_MINIMUM_NUCLIDE_DENSITY,
            default=1e-15,
            label="Minimum nuclide density",
            description="Density to use for nuclides and fission products at infinite dilution. This is also used as the minimum density.",
        ),
        setting.Setting(
            CONF_INFINITE_DILUTE_CUTOFF,
            default=1e-10,
            label="Infinite Dillute Cutoff",
            description="Do not model nuclides with density less than this cutoff. Used with PARTISN and SERPENT.",
        ),
        setting.Setting(
            CONF_TOLERATE_BURNUP_CHANGE,
            default=0.0,
            label="Cross Section Burnup Group Tolerance",
            description="Burnup window for computing cross sections. If the prior cross sections were computed within the window, new cross sections will not be generated and the prior calculated cross sections will be used.",
        ),
        setting.Setting(
            CONF_XS_BLOCK_REPRESENTATION,
            default="FluxWeightedAverage",
            label="Cross Section Block Averaging Method",
            description="The type of averaging to perform when creating cross sections for a group of blocks",
            options=[
                "Median",
                "Average",
                "FluxWeightedAverage",
                "ComponentAverage1DSlab",
            ],
        ),
        setting.Setting(
            CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION,
            default=False,
            label="Include All Block Types in XS Generation",
            description="Use all blocks in a cross section group when generating a representative block. When this is disabled only `fuel` blocks will be considered",
        ),
        setting.Setting(
            CONF_XS_KERNEL,
            default="MC2v3",
            label="Lattice Physics Kernel",
            description="Method to determine broad group cross sections for assemblies",
            options=["", "MC2v2", "MC2v3", "MC2v3-PARTISN", "SERPENT"],
        ),
        setting.Setting(
            CONF_XS_SCATTERING_ORDER,
            default=3,
            label="Scattering Order",
            description="Scattering order for the lattice physics calculation",
        ),
        setting.Setting(
            CONF_XS_BUCKLING_CONVERGENCE,
            default=1e-05,
            label="Buckling Convergence Criteria",
            description="The convergence criteria for the buckling iteration if it is available in the lattice physics solver",
        ),
        setting.Setting(
            CONF_XS_EIGENVALUE_CONVERGENCE,
            default=1e-05,
            label="Eigenvalue Convergence Criteria",
            description="The convergence criteria for the eigenvalue",
        ),
    ]
    return settings
