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
from armi.settings.settingsRules import include_as_rule
from armi import runLog

from .const import NEUTRON
from .const import NEUTRONGAMMA
from .const import ALL

from .energyGroups import getGroupStructure


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

# moved from xsSettings
CONF_CLEAR_XS = "clearXS"
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
        # moved from XSsettings
        setting.Setting(
            CONF_CLEAR_XS,
            default=False,
            label="Clear XS",
            description="Delete all cross section libraries before regenerating them.",
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
            oldNames=[("mc2.minimumFissileFraction", None)],
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
            oldNames=[
                ("mc2BucklingConvergence", None),
                ("bucklingConvergence", None),
            ],
        ),
        setting.Setting(
            CONF_XS_EIGENVALUE_CONVERGENCE,
            default=1e-05,
            label="Eigenvalue Convergence Criteria",
            description="The convergence criteria for the eigenvalue",
        ),
    ]

    return settings


## OLD STYLE settings rules from settingsRules.py. Prefer validators moving forward.


@include_as_rule("genXS")
def newGenXSOptions(_cs, name, value):
    """
    Set new values of 'genXS' setting based on previous setting values.

    Arguments
    ---------
    cs : setting object
        ARMi object containing the default and user-specified settings.

    name : str
        Setting name to be modified by this rule.

    value : str
        Value of the setting identified by name.

    Returns
    -------
    dict : dict
        Updated setting name and or value.
    """
    if value == "True":
        newValue = NEUTRON
    elif value == "False":
        newValue = ""
    else:
        newValue = value

    if value != newValue:
        runLog.info("The `genXS` setting has been set to {}.".format(newValue))
    return {name: newValue}


@include_as_rule("existingFIXSRC")
def newFixedSourceOption(cs, _name, value):
    """
    Migrate the deprecated setting 'existingFIXSRC' to 'existingFixedSource'.

    Arguments
    ---------
    cs : setting object
        ARMi object containing the default and user-specified settings.

    name : str
        Setting name to be modified by this rule.

    value : str
        Value of the setting identified by name.

    Returns
    -------
    dict : dict
        Updated setting name and or value.
    """
    newName = "existingFixedSource"
    if value == "True":
        newValue = "FIXSRC"
    else:
        newValue = ""

    if value != newValue:
        runLog.info(
            "The `existingFixedSource` setting has been set to {} based on deprecated "
            "`existingFIXSRC`.".format(newValue)
        )

    return {newName: newValue}


@include_as_rule("boundaries")
def migrateNormalBCSetting(_cs, name, value):
    """
    Boundary setting is migrated from `Normal` to `Extrapolated`.
    """
    newValue = value
    if value == "Normal":
        newValue = "Extrapolated"

    return {name: newValue}


@include_as_rule("asymptoticExtrapolationPowerIters")
def deprecateAsymptoticExtrapolationPowerIters(_cs, _name, _value):
    """
    The setting `asymptoticExtrapolationPowerIters` has been deprecated and replaced by
    three settings to remove confusion and ensure proper use.

    The three new settings are:
        - numOuterIterPriorAsympExtrap
        - asympExtrapOfOverRelaxCalc
        - asympExtrapOfNodalCalc
    """
    runLog.error(
        "The setting `asymptoticExtrapolationPowerIters` has been deprecated and replaced "
        "with `numOuterIterPriorAsympExtrap`, `asympExtrapOfOverRelaxCalc`, "
        "`asympExtrapOfNodalCalc`. Please use these settings for intended behavior."
    )

    raise ValueError(
        "Setting `asymptoticExtrapolationPowerIters` has been deprecated. "
        "See stdout for more details."
    )


@include_as_rule("groupStructure")
def updateXSGroupStructure(cs, name, value):

    try:
        getGroupStructure(value)
        return {name: value}
    except KeyError:
        try:
            newValue = value.upper()
            getGroupStructure(newValue)
            runLog.info(
                "Updating the cross section group structure from {} to {}".format(
                    value, newValue
                )
            )
            return {name: newValue}
        except KeyError:
            runLog.info(
                "Unable to automatically convert the `groupStructure` setting of {}. Defaulting to {}".format(
                    value, cs.settings["groupStructure"].default
                )
            )
            return {name: cs.settings["groupStructure"].default}


def _migrateDpa(_cs, name, value):
    newValue = value
    if value == "dpaHT9_33":
        newValue = "dpaHT9_ANL33_TwrBol"
    elif value == "dpa_SS316":
        newValue = "dpaSS316_ANL33_TwrBol"

    return {name: newValue}


@include_as_rule("gridPlateDpaXsSet")
def migrateGridPlateDpa(_cs, name, value):
    """Got more rigorous in dpa XS names."""
    return _migrateDpa(_cs, name, value)


@include_as_rule("dpaXsSet")
def migrateDpaXs(_cs, name, value):
    return _migrateDpa(_cs, name, value)


@include_as_rule("saveNeutronicsOutputs")
def resetNeutronicsOutputsToSaveAfterRename(_cs, _name, value):
    """
    Reset the values of 'saveNeutronicsOutputs' setting after it was migrated to 'neutronicsOutputsToSave'.

    Arguments
    ---------
    cs : setting object
        ARMi object containing the default and user-specified settings.

    name : str
        Setting name to be modified by this rule.

    value : str
        Value of the setting identified by name.

    Returns
    -------
    dict : dict
        Updated setting name and or value.
    """
    newName = "neutronicsOutputsToSave"
    if value == "True":
        newValue = ALL
    elif value == "False":
        newValue = ""

    runLog.info(
        "The `neutronicsOutputsToSave` setting has been set to {} based on deprecated "
        "`saveNeutronicsOutputs`.".format(newValue)
    )
    return {newName: newValue}


@include_as_rule("gammaTransportActive")
def removeGammaTransportActive(cs, _name, value):
    """
    Remove 'gammaTransportActive' and set values of 'globalFluxActive' for the same functionality.

    Arguments
    ---------
    cs : setting object
        ARMi object containing the default and user-specified settings.

    name : str
        Setting name to be modified by this rule.

    value : str
        Value of the setting identified by name.
    """
    if value == "True":
        newValue = NEUTRONGAMMA
    elif value == "False":
        newValue = NEUTRON

    cs["globalFluxActive"] = newValue
    runLog.info(
        "The `globalFluxActive` setting has been set to {} based on deprecated "
        "`gammaTransportActive`.".format(newValue)
    )


@include_as_rule("globalFluxActive")
def newGlobalFluxOptions(_cs, name, value):
    """
    Set new values of 'globalFluxActive' setting based on previous setting values.

    Arguments
    ---------
    cs : setting object
        ARMi object containing the default and user-specified settings.

    name : str
        Setting name to be modified by this rule.

    value : str
        Value of the setting identified by name.

    Returns
    -------
    dict : dict
        Updated setting name and or value.
    """
    if value == "True":
        newValue = NEUTRON
    elif value == "False":
        newValue = ""
    else:
        newValue = value

    if value != newValue:
        runLog.info(
            "The `globalFluxActive` setting has been set to {}.".format(newValue)
        )
    return {name: newValue}
