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
Framework-wide settings definitions and constants.

This should contain Settings definitions for general-purpose "framework" settings. These
should only include settings that are not related to any particular physics or plugins.

TODO: There are lots of settings in here that violate the above rule, which still need
to be migrated to their respective plugins.
"""
import os
from typing import List

import voluptuous as vol

from armi import context
from armi.settings import setting2 as setting


# Framework settings
CONF_NUM_PROCESSORS = "numProcessors"
CONF_BURN_CHAIN_FILE_NAME = "burnChainFileName"
CONF_ZONING_STRATEGY = "zoningStrategy"
CONF_AXIAL_MESH_REFINEMENT_FACTOR = "axialMeshRefinementFactor"
CONF_CONDITIONAL_MODULE_NAME = "conditionalModuleName"
CONF_AUTOMATIC_VARIABLE_MESH = "automaticVariableMesh"
CONF_TRACE = "trace"
CONF_PROFILE = "profile"
CONF_COVERAGE = "coverage"
CONF_MIN_MESH_SIZE_RATIO = "minMeshSizeRatio"
CONF_CYCLE_LENGTH = "cycleLength"
CONF_CYCLE_LENGTHS = "cycleLengths"
CONF_AVAILABILITY_FACTOR = "availabilityFactor"
CONF_AVAILABILITY_FACTORS = "availabilityFactors"
CONF_POWER_FRACTIONS = "powerFractions"
CONF_BURN_STEPS = "burnSteps"
CONF_BETA = "beta"
CONF_BRANCH_VERBOSITY = "branchVerbosity"
CONF_BU_GROUPS = "buGroups"
CONF_BURNUP_PEAKING_FACTOR = "burnupPeakingFactor"
CONF_CIRCULAR_RING_PITCH = "circularRingPitch"
CONF_COMMENT = "comment"
CONF_COPY_FILES_FROM = "copyFilesFrom"
CONF_COPY_FILES_TO = "copyFilesTo"
CONF_CREATE_ASSEMBLY_TYPE_ZONES = "createAssemblyTypeZones"
CONF_DEBUG = "debug"
CONF_DEBUG_MEM = "debugMem"
CONF_DEBUG_MEM_SIZE = "debugMemSize"
CONF_DEFAULT_SNAPSHOTS = "defaultSnapshots"
CONF_DETAIL_ALL_ASSEMS = "detailAllAssems"
CONF_DETAIL_ASSEM_LOCATIONS_BOL = "detailAssemLocationsBOL"
CONF_DETAIL_ASSEM_NUMS = "detailAssemNums"
CONF_DUMP_LOCATION_SNAPSHOT = "dumpLocationSnapshot"
CONF_DUMP_SNAPSHOT = "dumpSnapshot"
CONF_DO_ORIFICED_TH = "doOrificedTH"  # zones
CONF_EQ_DIRECT = "eqDirect"  # fuelCycle/equilibrium coupling
CONF_FRESH_FEED_TYPE = "freshFeedType"
CONF_GEOM_FILE = "geomFile"
CONF_GROW_TO_FULL_CORE_AFTER_LOAD = "growToFullCoreAfterLoad"
CONF_FUEL_HANDLER_NAME = "fuelHandlerName"  # fuel handler
CONF_JUMP_RING_NUM = "jumpRingNum"  # fuel handler
CONF_LEVELS_PER_CASCADE = "levelsPerCascade"  # fuel handler
CONF_START_CYCLE = "startCycle"
CONF_LOADING_FILE = "loadingFile"
CONF_START_NODE = "startNode"
CONF_LOAD_STYLE = "loadStyle"
CONF_LOW_POWER_REGION_FRACTION = "lowPowerRegionFraction"  # reports
CONF_MEM_PER_NODE = "memPerNode"
CONF_MPI_TASKS_PER_NODE = "mpiTasksPerNode"
CONF_N_CYCLES = "nCycles"
CONF_NUM_CONTROL_BLOCKS = "numControlBlocks"  # dif3d
CONF_NUM_COUPLED_ITERATIONS = "numCoupledIterations"
CONF_OPERATOR_LOCATION = "operatorLocation"
CONF_OUTPUT_FILE_EXTENSION = "outputFileExtension"
CONF_PLOTS = "plots"
CONF_POWER = "power"
CONF_REMOVE_PER_CYCLE = "removePerCycle"  # fuel handler
CONF_RUN_TYPE = "runType"
CONF_EXPLICIT_REPEAT_SHUFFLES = "explicitRepeatShuffles"
CONF_SKIP_CYCLES = "skipCycles"
CONF_SMALL_RUN = "smallRun"
CONF_REALLY_SMALL_RUN = "reallySmallRun"
CONF_STATIONARY_BLOCKS = "stationaryBlocks"
CONF_TARGET_K = "targetK"  # lots of things use this; not clear who should own
CONF_TRACK_ASSEMS = "trackAssems"
CONF_VERBOSITY = "verbosity"
CONF_ZONE_DEFINITIONS = "zoneDefinitions"
CONF_ACCEPTABLE_BLOCK_AREA_ERROR = "acceptableBlockAreaError"
CONF_RING_ZONES = "ringZones"
CONF_SPLIT_ZONES = "splitZones"
CONF_FLUX_RECON = "fluxRecon"  # strange coupling in fuel handlers
CONF_INDEPENDENT_VARIABLES = "independentVariables"
CONF_HCF_CORETYPE = "HCFcoretype"
CONF_LOOSE_COUPLING = "looseCoupling"
CONF_T_IN = "Tin"
CONF_T_OUT = "Tout"
CONF_USE_INPUT_TEMPERATURES_ON_DBLOAD = "useInputTemperaturesOnDBLoad"
CONF_DEFERRED_INTERFACES_CYCLE = "deferredInterfacesCycle"
CONF_DEFERRED_INTERFACE_NAMES = "deferredInterfaceNames"
CONF_OUTPUT_CACHE_LOCATION = "outputCacheLocation"
CONF_MATERIAL_NAMESPACE_ORDER = "materialNamespaceOrder"
CONF_DETAILED_AXIAL_EXPANSION = "detailedAxialExpansion"
CONF_HEX_RING_GEOMETRY_CONVERSION = "hexRingGeometryConversion"


def defineSettings() -> List[setting.Setting]:
    """Return a list of global framework settings."""

    settings = [
        setting.Setting(
            CONF_NUM_PROCESSORS,
            default=1,
            label="CPUs",
            description="Number of CPUs to request on the cluster",
        ),
        setting.Setting(
            CONF_BURN_CHAIN_FILE_NAME,
            default=os.path.join(context.RES, "burn-chain.yaml"),
            label="Burn Chain File",
            description="Path to YAML file that has the depletion chain defined in it",
        ),
        setting.Setting(
            CONF_ZONING_STRATEGY,
            default="byRingZone",
            label="Automatic core zone creation strategy",
            description="Channel Grouping Options for Safety;"
            "everyFA: every FA is its own channel, "
            "byRingZone: based on ringzones, "
            "byFuelType: based on fuel type, "
            "Manual: you must specify 'zoneDefinitions' setting",
            options=["byRingZone", "byOrifice", "byFuelType", "everyFA", "manual"],
        ),
        setting.Setting(
            CONF_AXIAL_MESH_REFINEMENT_FACTOR,
            default=1,
            label="Axial Mesh Refinement Factor",
            description="Multiplicative factor on the Global Flux number of mesh per "
            "block. Used for axial mesh refinement.",
        ),
        setting.Setting(
            CONF_DETAILED_AXIAL_EXPANSION,
            default=False,
            label="Detailed Axial Expansion",
            description=(
                "Allow each assembly to expand independently of the others. Results in non-uniform "
                "axial mesh. Neutronics kernel must be able to handle."
            ),
        ),
        setting.Setting(
            CONF_CONDITIONAL_MODULE_NAME,
            default="",
            label="",
            description="This is file name -- directory not included -- of the python "
            "module that contains a conditional function to determine the end of burn "
            "cycles",
        ),
        setting.Setting(
            CONF_AUTOMATIC_VARIABLE_MESH,
            default=False,
            label="",
            description="This is a flag to let armi add additional mesh points if the "
            "dif3d mesh is too irregular",
        ),
        setting.Setting(
            CONF_TRACE,
            default=False,
            label="Use the Python tracer",
            description="Activate Python trace module to print out each line as its "
            "executed",
            isEnvironment=True,
        ),
        setting.Setting(
            CONF_PROFILE,
            default=False,
            label="turn on the profiler",
            description="Turn on the profiler for the submitted case. The profiler "
            "results will not include all import times.",
            isEnvironment=True,
        ),
        setting.Setting(
            CONF_COVERAGE,
            default=False,
            label="turn on coverage report generation",
            description="Turn on coverage report generation which tracks all the lines "
            "of code that execute during a run",
            isEnvironment=True,
        ),
        setting.Setting(
            CONF_MIN_MESH_SIZE_RATIO,
            default=0.15,
            label="",
            description="This is the minimum ratio of mesh sizes (dP1/(dP1 + dP2)) "
            "allowable -- only active if automaticVariableMesh flag is set to True",
        ),
        setting.Setting(
            CONF_CYCLE_LENGTH,
            default=365.242199,
            label="Cycle Length",
            description="Duration of one single cycle. If availability factor is below "
            "1, the reactor will be at power less than this. If variable, use "
            "cycleLengths setting.",
        ),
        setting.Setting(
            CONF_CYCLE_LENGTHS,
            default=[],
            label="Cycle durations",
            description="List of durations of each cycle in days. The at-power "
            "duration will be affected by the availability factor. R is repeat. For "
            "example [100, 150, '9R'] is 1 100 day cycle followed by 10 150 day "
            "cycles. Empty list is constant duration set by 'cycleLength'.",
            schema=vol.Schema([vol.Coerce(str)]),
        ),
        setting.Setting(
            CONF_AVAILABILITY_FACTOR,
            default=1.0,
            label="Plant Availability Factor",
            description="Availability factor of the plant. This is the fraction of the "
            "time that the plant is operating. If variable, use availabilityFactors "
            "setting.",
        ),
        setting.Setting(
            CONF_AVAILABILITY_FACTORS,
            default=[],
            label="Availability factors",
            description="List of availability factor of each cycle as a fraction "
            "(fraction of time plant is not in an outage). R is repeat. For example "
            "[0.5, 1.0, '9R'] is 1 50% CF followed by 10 100 CF. Empty list is "
            "constant duration set by 'availabilityFactor'.",
            schema=vol.Schema([vol.Coerce(str)]),
        ),
        setting.Setting(
            CONF_POWER_FRACTIONS,
            default=[],
            label="Power fractions",
            description="List of power fractions at each cycle (fraction of rated "
            "thermal power the plant achieves). R is repeat. For example [0.5, 1.0, "
            "'9R'] is 1 50% PF followed by 10 100% PF. Specify zeros to indicate "
            "decay-only cycles (i.e. for decay heat analysis). Empty list implies "
            "always full rated power.",
            schema=vol.Schema([vol.Coerce(str)]),
        ),
        setting.Setting(
            CONF_BURN_STEPS,
            default=4,
            label="Burnup Steps per Cycle",
            description="Number of depletion substeps in one cycle, n. Note: There "
            "will be n+1 time nodes so the burnup step time will be computed as cycle "
            "length/n+1.",
        ),
        setting.Setting(
            CONF_BETA,
            default=0.0,
            label="Effective delayed neutron fraction",
            description="Effective delayed neutron fraction. You may need to enter the "
            "precursor groups in detail elsewhere to do kinetics.",
        ),
        setting.Setting(
            CONF_BRANCH_VERBOSITY,
            default="error",
            label="Worker Log Verbosity",
            description="Verbosity of the non-master MPI nodes",
            options=[
                "debug",
                "extra",
                "info",
                "important",
                "prompt",
                "warning",
                "error",
            ],
            isEnvironment=True,
        ),
        setting.Setting(
            CONF_BU_GROUPS,
            default=[10, 20, 30, 100],
            label="Burnup Groups",
            description="The range of burnups where cross-sections will be the same "
            "for a given assembly type",
            schema=vol.Schema([int]),
        ),
        setting.Setting(
            CONF_BURNUP_PEAKING_FACTOR,
            default=0.0,
            label="Burn-up Peaking Factor",
            description="None",
        ),
        setting.Setting(
            CONF_CIRCULAR_RING_PITCH,
            default=1.0,
            label="Circular ring relative pitch",
            description="The relative pitch to be used to define a single circular "
            "ring in circular shuffling. ",
        ),
        setting.Setting(
            CONF_COMMENT,
            default="",
            label="Case Comments",
            description="A comment describing this case.",
        ),
        setting.Setting(
            CONF_COPY_FILES_FROM, default=[], label="None", description="None"
        ),
        setting.Setting(
            CONF_COPY_FILES_TO, default=[], label="None", description="None"
        ),
        setting.Setting(
            CONF_CREATE_ASSEMBLY_TYPE_ZONES,
            default=False,
            label="Create fuel zones automatically",
            description="Let ARMI create zones based on fuel type automatically ",
        ),
        setting.Setting(
            CONF_DEBUG, default=False, label="Python Debug Mode", description="None"
        ),
        setting.Setting(
            CONF_DEBUG_MEM,
            default=False,
            label="Debug Memory",
            description="Turn on memory debugging options to help find problems with "
            "the code",
        ),
        setting.Setting(
            CONF_DEBUG_MEM_SIZE,
            default=False,
            label="Debug Memory Size",
            description="Show size of objects during memory debugging",
        ),
        setting.Setting(
            CONF_DEFAULT_SNAPSHOTS,
            default=False,
            label="Basic Reactor Snapshots",
            description="Generate snapshots at BOL, MOL, and EOL.",
        ),
        setting.Setting(
            CONF_DETAIL_ALL_ASSEMS,
            default=False,
            label="Detailed Assems - All",
            description="All assemblies will have 'detailed' treatment. Note: This "
            "option is interpreted differently by different modules.",
        ),
        setting.Setting(
            CONF_DETAIL_ASSEM_LOCATIONS_BOL,
            default=[],
            label="Detailed Assems - BOL Location",
            description="Assembly locations for assemblies that will have 'detailed' "
            "treatment. This option will track assemblies in the core at BOL. Note: "
            "This option is interpreted differently by different modules.",
        ),
        setting.Setting(
            CONF_DETAIL_ASSEM_NUMS,
            default=[],
            label="Detailed Assems - ID",
            description="Assembly numbers(IDs) for assemblies that will have "
            "'detailed' treatment. This option will track assemblies that not in the "
            "core at BOL. Note: This option is interpreted differently by different "
            "modules.",
            schema=vol.Schema([int]),
        ),
        setting.Setting(
            CONF_DUMP_LOCATION_SNAPSHOT,
            default=[],
            label="Detailed Assems - Snapshot Locations",
            description="Assembly locations and snapshots to dump detailed assembly "
            "data.",
        ),
        setting.Setting(
            CONF_DUMP_SNAPSHOT,
            default=[],
            label="Detailed Reactor Snapshots",
            description="List of snapshots to dump detailed reactor analysis data. Can "
            "be used to perform follow-on analysis (i.e., Reactivity coefficient "
            "generation).",
        ),
        setting.Setting(
            CONF_DO_ORIFICED_TH,
            default=False,
            label="Perform Core Orificing",
            description="Perform orificed thermal hydraulics (requires bounds file "
            "from a previous case).",
        ),
        setting.Setting(
            CONF_EQ_DIRECT,
            default=False,
            label="Direct Eq Shuffling",
            description="Does the equilibrium search with repetitive shuffing but with "
            "direct shuffling rather than the fast way.",
        ),
        setting.Setting(
            CONF_FLUX_RECON,
            default=False,
            label="Flux/Power Reconstruction",
            description="Perform detailed flux and power reconstruction",
        ),
        setting.Setting(
            CONF_FRESH_FEED_TYPE,
            default="feed fuel",
            label="Fresh Feed Type",
            description="None",
            options=["feed fuel", "igniter fuel", "inner driver fuel"],
        ),
        setting.Setting(
            CONF_FUEL_HANDLER_NAME,
            default="",
            label="Fuel Handler Name",
            description="None",
        ),
        setting.Setting(
            CONF_GEOM_FILE,
            default="",
            label="Core Map Input File",
            description="Input file containing BOL core map.",
        ),
        setting.Setting(
            CONF_GROW_TO_FULL_CORE_AFTER_LOAD,
            default=False,
            label="Expand to Full Core on Snapshot Load",
            description="Grows from 1/3 to full core after loading from a 1/3 "
            "symmetric snapshot. Note: This is needed when a full core model is needed "
            "and the database was produced using a third core model",
        ),
        setting.Setting(
            CONF_JUMP_RING_NUM, default=8, label="Jump Ring Number", description="None"
        ),
        setting.Setting(
            CONF_LEVELS_PER_CASCADE,
            default=14,
            label="Move per cascade",
            description="None",
        ),
        setting.Setting(
            CONF_START_CYCLE,
            default=0,
            label="Start Cycle",
            description="Cycle number to continue calculation from. Database will "
            "load from the time step just before. For snapshots use `dumpSnapshot`",
        ),
        setting.Setting(
            CONF_LOADING_FILE,
            default="",
            label="Blueprints File",
            description="Browse for the blueprints/loading input file containing "
            "component dimensions, materials, etc.",
        ),
        setting.Setting(
            CONF_START_NODE,
            default=0,
            label="StartNode",
            description="Timenode number (0 for BOC, etc.) to continue calulation from. "
            "Database will load from the time step just before.",
        ),
        setting.Setting(
            CONF_LOAD_STYLE,
            default="fromInput",
            label="Load Style",
            description="Description of how the ARMI case will be initialized",
            options=["fromInput", "fromDB"],
        ),
        setting.Setting(
            CONF_LOW_POWER_REGION_FRACTION,
            default=0.05,
            label="low power region fraction",
            description="Description Needed",
        ),
        setting.Setting(
            CONF_MEM_PER_NODE,
            default=2000,
            label="Memory per node",
            description="Memory requested per cluster node",
        ),
        setting.Setting(
            CONF_MPI_TASKS_PER_NODE,
            default=0,
            label="mpiTasksPerNode",
            description="Number of independent processes that are allocated to each "
            "cluster node. 0 means 1 process per CPU (or 12 per node on some "
            "clusters). Set between 1-12 to increase RAM and number of cores needed "
            "for large problems. ",
        ),
        setting.Setting(
            CONF_N_CYCLES,
            default=1,
            label="Number of cycles",
            description="Number of cycles that will be simulated. Fuel management "
            "happens at the beginning of each cycle. Can include active (full-power) "
            "cycles as well as post-shutdown decay-heat steps.",
        ),
        setting.Setting(
            CONF_NUM_CONTROL_BLOCKS,
            default=6,
            label="numControlBlocks",
            description="Number of blocks with control for a REBUS poison search",
        ),
        setting.Setting(
            CONF_NUM_COUPLED_ITERATIONS,
            default=0,
            label="Tight Coupling Iterations",
            description="Number of tight coupled physics iterations to occur at each "
            "timestep.",
        ),
        setting.Setting(
            CONF_OPERATOR_LOCATION,
            default="",
            label="Operator Location",
            description="The path to the operator code to execute for this run (for "
            "custom behavior)",
        ),
        setting.Setting(
            CONF_OUTPUT_FILE_EXTENSION,
            default="jpg",
            label="Plot file extension",
            description="The default extension for plots",
            options=["jpg", "png", "svg", "pdf"],
        ),
        setting.Setting(
            CONF_PLOTS,
            default=False,
            label="Plot Results",
            description="Generate additional plots throughout the ARMI analysis",
        ),
        setting.Setting(
            CONF_POWER,
            default=0.0,
            label="Reactor Thermal Power (W)",
            description="Nameplate thermal power of the reactor. Can be varied by "
            "setting the powerFraction setting.",
        ),
        setting.Setting(
            CONF_REMOVE_PER_CYCLE, default=3, label="Move per cycle", description="None"
        ),
        setting.Setting(
            CONF_RUN_TYPE,
            default="Standard",
            label="Run Type",
            description="Type of run that this is, e.g. a normal run through all "
            "cycles, a snapshot loaded rx. coefficient run, etc.",
            options=["Standard", "Equilibrium", "Snapshots"],
        ),
        setting.Setting(
            CONF_EXPLICIT_REPEAT_SHUFFLES,
            default="",
            label="Browse for shuffle history to repeat",
            description="Path to file that contains a detailed shuffling history that "
            "is to be repeated exactly.",
        ),
        setting.Setting(
            CONF_SKIP_CYCLES,
            default=0,
            label="Number of Cycles to Skip",
            description="Number of cycles to be skipped during the calculation. Note: "
            "This is typically used when repeating only a portion of a calculation or "
            "repeating a run.",
        ),
        setting.Setting(
            CONF_SMALL_RUN,
            default=False,
            label="Clean up Files at EOL",
            description="Clean up intermediate files after the run completes (EOL)",
        ),
        setting.Setting(
            CONF_REALLY_SMALL_RUN,
            default=False,
            label="Clean up Files at BOC",
            description="Clean up files at the beginning of each cycle (BOC)",
        ),
        setting.Setting(
            CONF_STATIONARY_BLOCKS,
            default=[],
            label="stationary Blocks",
            description="blocks with these indices (int values) will not move in "
            "moves.",
        ),
        setting.Setting(
            CONF_TARGET_K,
            default=1.005,
            label="Criticality Search Target (k-effective)",
            description="Target criticality (k-effective) for cycle length, branch, "
            "and equilibrium search",
        ),
        setting.Setting(
            CONF_TRACK_ASSEMS,
            default=True,
            label="Save discharged assems",
            description="track assemblies for detailed fuel histories. Disable in case "
            "you get memory errors.",
        ),
        setting.Setting(
            CONF_VERBOSITY,
            default="info",
            label="Master Log Verbosity",
            description="How verbose the output will be",
            options=[
                "debug",
                "extra",
                "info",
                "important",
                "prompt",
                "warning",
                "error",
            ],
            isEnvironment=True,
        ),
        setting.Setting(
            CONF_ZONE_DEFINITIONS,
            default=[],
            label="Zone Definitions",
            description="definitions of zones as lists of assembly locations (e.g. "
            "'zoneName: loc1, loc2, loc3') . Zones are groups of assemblies used by "
            "various summary and calculation routines",
        ),
        setting.Setting(
            CONF_ACCEPTABLE_BLOCK_AREA_ERROR,
            default=1e-05,
            label="",
            description="This is the limit of error in between the block's cross "
            "sectional area and the reference block used during the assembly area "
            "consistency check",
        ),
        setting.Setting(
            CONF_RING_ZONES,
            default=[],
            label="Ring Zones",
            description="Define zones by concentric radial rings. Each zone will get "
            "independent reactivity coefficients.",
            schema=vol.Schema([int]),
        ),
        setting.Setting(
            CONF_SPLIT_ZONES,
            default=True,
            label="Split Zones",
            description="Automatically split defined zones further based on number of "
            "blocks and assembly types.",
        ),
        setting.Setting(
            CONF_INDEPENDENT_VARIABLES,
            default=[],
            label="Indep. Vars",
            description="List of (independentVarName, value) tuples to inform optimization post-processing.",
        ),
        setting.Setting(
            CONF_HCF_CORETYPE,
            default="TWRC",
            label="Hot Channel Factor Set",
            description="Switch to apply different sets of hot channel factors based  on design being analyzed",
            options=["TWRC", "TWRP", "TWRC-HEX"],
        ),
        setting.Setting(
            CONF_LOOSE_COUPLING,
            default=False,
            label="Activate Loose Physics Coupling",
            description="Update material densities and dimensions after running thermal-hydraulics. Note: Thermal-hydraulics calculation is needed to perform the loose physics coupling calculation.",
        ),
        setting.Setting(
            CONF_T_IN,
            default=360.0,
            label="Inlet T (C)",
            description="The inlet temperature of the reactor in C",
        ),
        setting.Setting(
            CONF_T_OUT,
            default=510.0,
            label="Outlet T (C)",
            description="The outlet temperature of the reactor in C",
        ),
        setting.Setting(
            CONF_USE_INPUT_TEMPERATURES_ON_DBLOAD,
            default=False,
            label="Temperatures from Input on DB Load",
            description="when loading from a database, first set all component temperatures to the input temperatures. Required when a coupled TH case is being derived from a case without any coupled TH.",
        ),
        setting.Setting(
            CONF_DEFERRED_INTERFACES_CYCLE,
            default=0,
            label="Deferred Interface Start Cycle",
            description="The supplied list of interface names in deferredInterfaceNames will begin normal operations on this cycle number.",
        ),
        setting.Setting(
            CONF_DEFERRED_INTERFACE_NAMES,
            default=[],
            label="Deferred Interface Names",
            description="Interfaces to delay the normal operations of for special circumstance problem avoidance",
        ),
        setting.Setting(
            CONF_OUTPUT_CACHE_LOCATION,
            default="",
            label="Location of output cache",
            description="Location where cached calculations are stored and "
            "retrieved if exactly the same as the calculation requested. Empty "
            "string will not cache",
            isEnvironment=True,
        ),
        setting.Setting(
            CONF_MATERIAL_NAMESPACE_ORDER,
            default=[],
            label="Material namespace order",
            description=(
                "Ordered list of Python namespaces for finding materials by class name. "
                "This allows users to choose between different implementations of reactor "
                "materials. For example, the framework comes with a basic UZr material, "
                "but power users will want to override it with their own UZr subclass. "
                "This allows users to specify to get materials out of a plugin rather "
                "than from the framework."
            ),
        ),
        setting.Setting(
            CONF_HEX_RING_GEOMETRY_CONVERSION,
            default=False,
            label="Convert Using Hexagonal Ring Zones",
            description="Convert the core geometry model to RZ/RZT using hexagonal ring zones. Note: If this is disabled, circular ring zones will be used.",
        ),
    ]
    return settings
