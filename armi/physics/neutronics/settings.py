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
import os

from armi import runLog
from armi.physics.neutronics import LatticePhysicsFrequency
from armi.physics.neutronics.const import NEUTRON
from armi.physics.neutronics.energyGroups import GROUP_STRUCTURE
from armi.settings import setting
from armi.settings import settingsValidation
from armi.utils import directoryChangers
from armi.settings.fwSettings.globalSettings import (
    CONF_DETAILED_AXIAL_EXPANSION,
    CONF_NON_UNIFORM_ASSEM_FLAGS,
    CONF_RUN_TYPE,
)


CONF_BC_COEFFICIENT = "bcCoefficient"
CONF_BOUNDARIES = "boundaries"
CONF_DPA_PER_FLUENCE = "dpaPerFluence"
CONF_EIGEN_PROB = "eigenProb"
CONF_EPS_EIG = "epsEig"
CONF_EPS_FSAVG = "epsFSAvg"
CONF_EPS_FSPOINT = "epsFSPoint"
CONF_EXISTING_FIXED_SOURCE = "existingFixedSource"
CONF_GEN_XS = "genXS"  # gamma stuff and neutronics plugin/lattice physics
CONF_GLOBAL_FLUX_ACTIVE = "globalFluxActive"
CONF_GROUP_STRUCTURE = "groupStructure"
CONF_INNERS_ = "inners"
CONF_LOADING_FILE = "loadingFile"
CONF_NEUTRONICS_KERNEL = "neutronicsKernel"
CONF_MCNP_LIB_BASE = "mcnpLibraryBaseName"
CONF_NEUTRONICS_TYPE = "neutronicsType"
CONF_NUMBER_MESH_PER_EDGE = "numberMeshPerEdge"
CONF_OUTERS_ = "outers"
CONF_RESTART_NEUTRONICS = "restartNeutronics"

# Used for dpa/dose analysis.
# TODO: These should be relocated to more design-specific places
CONF_ACLP_DOSE_LIMIT = "aclpDoseLimit"
CONF_DPA_XS_SET = "dpaXsSet"
CONF_GRID_PLATE_DPA_XS_SET = "gridPlateDpaXsSet"
CONF_LOAD_PAD_ELEVATION = "loadPadElevation"
CONF_LOAD_PAD_LENGTH = "loadPadLength"

CONF_OPT_DPA = [
    "",
    "dpa_EBRII_INC600",
    "dpa_EBRII_INCX750",
    "dpa_EBRII_HT9",
    "dpa_EBRII_PE16",
    "dpa_EBRII_INC625",
]

# moved from xsSettings
CONF_CLEAR_XS = "clearXS"
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
CONF_LATTICE_PHYSICS_FREQUENCY = "latticePhysicsFrequency"


def defineSettings():
    """Standard function to define settings; for neutronics.

    .. impl:: Users to select if gamma cross sections are generated.
        :id: I_ARMI_GAMMA_XS
        :implements: R_ARMI_GAMMA_XS

        A single boolean setting can be used to turn on/off the calculation of gamma
        cross sections. This is implemented with the usual boolean ``Setting`` logic.
        The goal here is performance; save the compute time if the analyst doesn't need
        those cross sections.
    """
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
                "ANL116",
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
            "tab). When not set, the XS library will be auto-loaded from an existing "
            "ISOTXS in the working directory, but fail if there is no ISOTXS.",
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
            description="Value for the parameter A of the generalized boundary "
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
            enforcedOptions=True,
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
            CONF_MCNP_LIB_BASE,
            default="ENDF/B-VII.1",
            description=(
                "Library name for MCNP cross sections. "
                "ENDF/B-VII.1 is the default library. "
            ),
            label="Default base library name",
            options=["ENDF/B-VII.0", "ENDF/B-VII.1", "ENDF/B-VIII.0"],
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
            description="Is this a eigenvalue problem or a fixed source problem?",
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
            description="Convergence criteria for calculating the eigenvalue in the "
            "global flux solver",
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
                "from the bottom of the upper grid plate. Used for calculating the "
                "load pad dose"
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
            description="Dose limit in dpa used to position the above-core load pad"
            "(if one exists)",
        ),
        setting.Setting(
            CONF_RESTART_NEUTRONICS,
            default=False,
            label="Restart neutronics",
            description="Restart global flux case using outputs from last time as a guess",
        ),
        setting.Setting(
            CONF_OUTERS_,
            default=100,
            label="Max Outer Iterations",
            description="XY and Axial partial current sweep max outer iterations.",
        ),
        setting.Setting(
            CONF_INNERS_,
            default=0,
            label="Inner Iterations",
            description="XY and Axial partial current sweep inner iterations. 0 lets "
            "the neutronics code pick a default.",
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
        setting.Setting(
            CONF_CLEAR_XS,
            default=False,
            label="Clear XS",
            description="Delete all cross section libraries before regenerating them.",
        ),
        setting.Setting(
            CONF_MINIMUM_FISSILE_FRACTION,
            default=0.045,
            label="Minimum Fissile Fraction",
            description="Minimum fissile fraction (fissile number densities / heavy "
            "metal number densities).",
            oldNames=[("mc2.minimumFissileFraction", None)],
        ),
        setting.Setting(
            CONF_MINIMUM_NUCLIDE_DENSITY,
            default=1e-15,
            label="Minimum nuclide density",
            description="Density to use for nuclides and fission products at infinite "
            "dilution. This is also used as the minimum density considered for "
            "computing macroscopic cross sections. It can also be passed to physics "
            "plugins.",
        ),
        setting.Setting(
            CONF_INFINITE_DILUTE_CUTOFF,
            default=1e-10,
            label="Infinite Dillute Cutoff",
            description="Do not model nuclides with density less than this cutoff. "
            "Used with PARTISN and SERPENT.",
        ),
        setting.Setting(
            CONF_TOLERATE_BURNUP_CHANGE,
            default=0.0,
            label="Cross Section Burnup Group Tolerance",
            description="Burnup window for computing cross sections. If the prior "
            "cross sections were computed within the window, new cross sections will "
            "not be generated and the prior calculated cross sections will be used.",
        ),
        setting.Setting(
            CONF_XS_BLOCK_REPRESENTATION,
            default="Average",
            label="Cross Section Block Averaging Method",
            description="The type of averaging to perform when creating cross "
            "sections for a group of blocks",
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
            description="Use all blocks in a cross section group when generating a "
            "representative block. When this is disabled only `fuel` blocks will be "
            "considered",
        ),
        setting.Setting(
            CONF_XS_KERNEL,
            default="MC2v3",
            label="Lattice Physics Kernel",
            description="Method to determine broad group cross sections for assemblies",
            options=["", "MC2v2", "MC2v3", "MC2v3-PARTISN", "SERPENT"],
        ),
        setting.Setting(
            CONF_LATTICE_PHYSICS_FREQUENCY,
            default="BOC",
            label="Frequency of lattice physics updates",
            description="Define the frequency at which cross sections are updated with "
            "new lattice physics interactions.",
            options=[opt.name for opt in list(LatticePhysicsFrequency)],
            enforcedOptions=True,
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
            description="Convergence criteria for the buckling iteration if it is "
            "available in the lattice physics solver",
            oldNames=[
                ("mc2BucklingConvergence", None),
                ("bucklingConvergence", None),
            ],
        ),
        setting.Setting(
            CONF_XS_EIGENVALUE_CONVERGENCE,
            default=1e-05,
            label="Eigenvalue Convergence Criteria",
            description="Convergence criteria for the eigenvalue in the lattice "
            "physics kernel",
        ),
    ]

    return settings


def _blueprintsHasOldXSInput(inspector):
    path = inspector.cs[CONF_LOADING_FILE]
    with directoryChangers.DirectoryChanger(inspector.cs.inputDirectory):
        with open(os.path.expandvars(path)) as f:
            for line in f:
                if line.startswith("cross sections:"):
                    return True

    return False


def getNeutronicsSettingValidators(inspector):
    """The standard helper method, to provide validators to neutronics settings."""
    queries = []

    def migrateXSOption(name0):
        """
        The `genXS` and `globalFluxActive` settings used to take True/False as inputs,
        this helper method migrates those to the new values.
        """
        value = inspector.cs[name0]
        if value == "True":
            value = NEUTRON
        elif value == "False":
            value = ""

        inspector.cs = inspector.cs.modified(newSettings={name0: value})

    def migrateXSOptionGenXS():
        """pass-through to migrateXSOption(), because Query functions cannot take arguements."""
        migrateXSOption(CONF_GEN_XS)

    def migrateXSOptionGlobalFluxActive():
        """pass-through to migrateXSOption(), because Query functions cannot take arguements."""
        migrateXSOption(CONF_GLOBAL_FLUX_ACTIVE)

    queries.append(
        settingsValidation.Query(
            lambda: inspector.cs[CONF_GEN_XS] in ("True", "False"),
            "The {0} setting cannot not take `True` or `False` as an exact value any more.",
            'Would you like to auto-correct {0} to the correct value? ("" or {1})'.format(
                CONF_GEN_XS, NEUTRON
            ),
            migrateXSOptionGenXS,
        )
    )

    queries.append(
        settingsValidation.Query(
            lambda: inspector.cs[CONF_GLOBAL_FLUX_ACTIVE] in ("True", "False"),
            "The {0} setting cannot not take `True` or `False` as an exact value any more.",
            'Would you like to auto-correct {0} to the correct value? ("" or {1})'.format(
                CONF_GLOBAL_FLUX_ACTIVE, NEUTRON
            ),
            migrateXSOptionGlobalFluxActive,
        )
    )

    def migrateNormalBCSetting():
        """The `boundary` setting is migrated from `Normal` to `Extrapolated`."""
        inspector.cs = inspector.cs.modified(
            newSettings={CONF_BOUNDARIES: "Extrapolated"}
        )

    queries.append(
        settingsValidation.Query(
            lambda: inspector.cs[CONF_BOUNDARIES] == "Normal",
            "The {0} setting now takes `Extrapolated` instead of `Normal` as a value.".format(
                CONF_BOUNDARIES
            ),
            "Would you like to auto-correct {0} from `Normal` to `Extrapolated`?".format(
                CONF_BOUNDARIES
            ),
            migrateNormalBCSetting,
        )
    )

    def updateXSGroupStructure():
        """Trying to migrate to a valid XS group structure name."""
        value = inspector.cs[CONF_GROUP_STRUCTURE]
        newValue = value.upper()

        if newValue in GROUP_STRUCTURE:
            runLog.info(
                "Updating the cross section group structure from {} to {}".format(
                    value, newValue
                )
            )
        else:
            newValue = inspector.cs.getSetting(CONF_GROUP_STRUCTURE).default
            runLog.info(
                "Unable to automatically convert the {} setting of {}. Defaulting to {}".format(
                    CONF_GROUP_STRUCTURE, value, newValue
                )
            )

        inspector.cs = inspector.cs.modified(
            newSettings={CONF_GROUP_STRUCTURE: newValue}
        )

    queries.append(
        settingsValidation.Query(
            lambda: inspector.cs[CONF_GROUP_STRUCTURE] not in GROUP_STRUCTURE,
            "The given group structure {0} was not recognized.".format(
                inspector.cs[CONF_GROUP_STRUCTURE]
            ),
            "Would you like to auto-correct the group structure value?",
            updateXSGroupStructure,
        )
    )

    def migrateDpa(name0):
        """Migrating some common shortened names for dpa XS sets."""
        value = inspector.cs[name0]
        if value == "dpaHT9_33":
            value = "dpaHT9_ANL33_TwrBol"
        elif value == "dpa_SS316":
            value = "dpaSS316_ANL33_TwrBol"

        inspector.cs = inspector.cs.modified(newSettings={name0: value})

    def migrateDpaDpaXsSet():
        """Pass-through to migrateDpa(), because Query functions cannot take arguements."""
        migrateDpa(CONF_DPA_XS_SET)

    def migrateDpaGridPlate():
        """Pass-through to migrateDpa(), because Query functions cannot take arguements."""
        migrateDpa(CONF_GRID_PLATE_DPA_XS_SET)

    queries.append(
        settingsValidation.Query(
            lambda: inspector.cs[CONF_DPA_XS_SET] in ("dpaHT9_33", "dpa_SS316"),
            "It appears you are using a shortened version of the {0}.".format(
                CONF_DPA_XS_SET
            ),
            "Would you like to auto-correct this to the full name?",
            migrateDpaDpaXsSet,
        )
    )

    queries.append(
        settingsValidation.Query(
            lambda: inspector.cs[CONF_GRID_PLATE_DPA_XS_SET]
            in ("dpaHT9_33", "dpa_SS316"),
            "It appears you are using a shortened version of the {0}.".format(
                CONF_GRID_PLATE_DPA_XS_SET
            ),
            "Would you like to auto-correct this to the full name?",
            migrateDpaGridPlate,
        )
    )

    queries.append(
        settingsValidation.Query(
            lambda: inspector.cs[CONF_DETAILED_AXIAL_EXPANSION]
            and inspector.cs[CONF_NON_UNIFORM_ASSEM_FLAGS],
            f"The use of {CONF_DETAILED_AXIAL_EXPANSION} and {CONF_NON_UNIFORM_ASSEM_FLAGS} is not supported.",
            "Automatically set non-uniform assembly treatment to its default?",
            lambda: inspector._assignCS(
                CONF_NON_UNIFORM_ASSEM_FLAGS,
                inspector.cs.getSetting(CONF_NON_UNIFORM_ASSEM_FLAGS).default,
            ),
        )
    )

    queryMsg = (
        "A Snapshots case is selected but the `latticePhysicsFrequency` "
        "{0} is less than `firstCoupledIteration`. `firstCoupledIteration`"
        " or `all` is recommended for Snapshots when they involve large changes "
        "in power or flow compared to the loaded state."
    ).format(inspector.cs[CONF_LATTICE_PHYSICS_FREQUENCY])
    queryPrompt = (
        "Would you like to update `latticePhysicsFrequency` from "
        f"{inspector.cs[CONF_LATTICE_PHYSICS_FREQUENCY]} to `firstCoupledIteration`?"
    )
    queries.append(
        settingsValidation.Query(
            lambda: inspector.cs[CONF_RUN_TYPE] == "Snapshots"
            and not LatticePhysicsFrequency[
                inspector.cs[CONF_LATTICE_PHYSICS_FREQUENCY]
            ]
            >= LatticePhysicsFrequency.firstCoupledIteration,
            queryMsg,
            queryPrompt,
            lambda: inspector._assignCS(
                CONF_LATTICE_PHYSICS_FREQUENCY, "firstCoupledIteration"
            ),
        )
    )

    return queries
