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

"""Some generic neutronics-related settings."""
from armi.settings import setting


CONF_NEUTRONICS_KERNEL = "neutronicsKernel"
CONF_NEUTRONICS_TYPE = "neutronicsType"

CONF_BOUNDARIES = "boundaries"
CONF_BC_COEFFICIENT = "bcCoefficient"
CONF_DPA_PER_FLUENCE = "dpaPerFluence"
CONF_GEN_XS = "genXS"  # gamma stuff and neutronics plugin/lattice physics
CONF_GLOBAL_FLUX_ACTIVE = "globalFluxActive"
CONF_GROUP_STRUCTURE = "groupStructure"
CONF_EIGEN_PROB = "eigenProb"
CONF_EXISTING_FIXED_SOURCE = "existingFixedSource"
CONF_NUMBER_MESH_PER_EDGE = "numberMeshPerEdge"
CONF_RESTART_NEUTRONICS = "restartNeutronics"

CONF_EPS_EIG = "epsEig"
CONF_EPS_FSAVG = "epsFSAvg"
CONF_EPS_FSPOINT = "epsFSPoint"

# used for dpa/dose analysis. These should be relocated to more
# design-specific places
CONF_LOAD_PAD_ELEVATION = "loadPadElevation"
CONF_LOAD_PAD_LENGTH = "loadPadLength"
CONF_ACLP_DOSE_LIMIT = "aclpDoseLimit"
CONF_DPA_XS_SET = "dpaXsSet"
CONF_GRID_PLATE_DPA_XS_SET = "gridPlateDpaXsSet"

CONF_OPT_DPA = [
    "",
    "dpa_EBRII_INC600",
    "dpa_EBRII_INCX750",
    "dpa_EBRII_HT9",
    "dpa_EBRII_PE16",
    "dpa_EBRII_INC625",
]


def defineSettings():
    settings = [
        setting.Setting(
            CONF_GROUP_STRUCTURE,
            default="ANL33",
            label="Number of Energy Groups",
            description="Energy group structure to use in neutronics simulations",
            options=[
                "ANL9",
                "ANL33",
                "ANL70",
                "ANL230",
                "ANL703",
                "ANL1041",
                "ANL2082",
                "ARMI33",
                "ARMI45",
                "CINDER63",
                "348",
            ],
        ),
        setting.Setting(
            CONF_GLOBAL_FLUX_ACTIVE,
            default="Neutron",
            label="Global Flux Calculation",
            description="Calculate the global flux at each timestep for the selected "
            "particle type(s) using the specified neutronics kernel (see Global Flux "
            "tab).",
            options=["", "Neutron", "Neutron and Gamma"],
        ),
        setting.Setting(
            CONF_GEN_XS,
            default="",
            label="Multigroup Cross Sections Generation",
            description="Generate multigroup cross sections for the selected particle "
            "type(s) using the specified lattice physics kernel (see Lattice Physics "
            "tab). When not set, the XS library will be auto-loaded from an existing ISOTXS "
            "within then working directory and fail if the ISOTXS does not exist.",
            options=["", "Neutron", "Neutron and Gamma"],
        ),
        setting.Setting(
            CONF_DPA_PER_FLUENCE,
            default=4.01568627451e-22,
            label="DPA Per Fluence",
            description="A quick and dirty conversion that is used to get "
            "dpaPeak by multiplying the factor and fastFluencePeak",
        ),
        setting.Setting(
            CONF_BC_COEFFICIENT,
            default=0.0,
            label="Parameter A for generalized BC",
            description="Value for the parameter A of the DIF3D generalized boundary "
            "condition.",
        ),
        setting.Setting(
            CONF_BOUNDARIES,
            default="Extrapolated",
            label="Neutronic BCs",
            description="External Neutronic Boundary Conditions. Reflective does not "
            "include axial.",
            options=[
                "Extrapolated",
                "Reflective",
                "Infinite",
                "ZeroSurfaceFlux",
                "ZeroInwardCurrent",
                "Generalized",
            ],
        ),
        setting.Setting(
            CONF_NEUTRONICS_KERNEL,
            default="",
            label="Neutronics Kernel",
            description="The neutronics / depletion solver for global flux solve.",
            options=[],
            enforcedOptions=True,
        ),
        setting.Setting(
            CONF_NEUTRONICS_TYPE,
            default="real",
            label="Neutronics Type",
            description="The type of neutronics solution that is desired.",
            options=["real", "adjoint", "both"],
        ),
        setting.Setting(
            CONF_EIGEN_PROB,
            default=True,
            label="Eigenvalue Problem",
            description="Whether this is a eigenvalue problem or a fixed source problem",
        ),
        setting.Setting(
            CONF_EXISTING_FIXED_SOURCE,
            default="",
            label="Existing fixed source input",
            description="Specify an exiting fixed source input file.",
            options=["", "FIXSRC", "VARSRC"],
        ),
        setting.Setting(
            CONF_NUMBER_MESH_PER_EDGE,
            default=1,
            label="Number of Mesh per Edge",
            description="Number of mesh per block edge for finite-difference planar "
            "mesh refinement.",
            oldNames=[("hexSideSubdivisions", None)],
        ),
        setting.Setting(
            CONF_EPS_EIG,
            default=1e-07,
            label="Eigenvalue Epsilon",
            description="convergence criterion for calculating the eigenvalue",
        ),
        setting.Setting(
            CONF_EPS_FSAVG,
            default=1e-05,
            label="FS Avg. epsilon",
            description="Convergence criteria for average fission source",
        ),
        setting.Setting(
            CONF_EPS_FSPOINT,
            default=1e-05,
            label="FS Point epsilon",
            description="Convergence criteria for point fission source",
        ),
        setting.Setting(
            CONF_LOAD_PAD_ELEVATION,
            default=0.0,
            label="Load pad elevation (cm)",
            description=(
                "The elevation of the bottom of the above-core load pad (ACLP) in cm "
                "from the bottom of the upper grid plate. Used for calculating the load "
                "pad dose"
            ),
        ),
        setting.Setting(
            CONF_LOAD_PAD_LENGTH,
            default=0.0,
            label="Load pad length (cm)",
            description="The length of the load pad. Used to compute average and peak dose.",
        ),
        setting.Setting(
            CONF_ACLP_DOSE_LIMIT,
            default=80.0,
            label="ALCP dose limit",
            description="Dose limit in dpa used to position the above-core load pad (if one exists)",
        ),
        setting.Setting(
            CONF_RESTART_NEUTRONICS,
            default=False,
            label="Restart neutronics",
            description="Restart global flux case using outputs from last time as a guess",
        ),
        setting.Setting(
            CONF_GRID_PLATE_DPA_XS_SET,
            default="dpa_EBRII_HT9",
            label="Grid plate DPA XS",
            description=(
                "The cross sections to use for grid plate blocks DPA when computing "
                "displacements per atom."
            ),
            options=CONF_OPT_DPA,
        ),
        setting.Setting(
            CONF_DPA_XS_SET,
            default="dpa_EBRII_HT9",
            label="DPA Cross Sections",
            description="The cross sections to use when computing displacements per atom.",
            options=CONF_OPT_DPA,
        ),
    ]

    return settings
