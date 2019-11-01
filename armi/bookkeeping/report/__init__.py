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
Package for generating reports as printable groups and HTML in ARMI.
"""
from armi import settings, runLog
from armi.bookkeeping.report import data


def setData(name, value, group=None, reports=None):
    """
    Stores data in accordance with the specified parameters for use later.

    Parameters
    ----------
    name : str
    value : Object
        Any value desired.
    group : data.Group
    reports : data.Report

    """
    from armi.bookkeeping.report.reportInterface import ReportInterface

    if not name or not isinstance(name, str):
        raise AttributeError("Given name {} not acceptable.".format(name))

    group = group or UNGROUPED
    if not isinstance(group, data.Group):
        raise AttributeError("Given group {} not acceptable/approved.".format(group))

    reports = reports or []
    if not isinstance(reports, (list, set, tuple)):
        reports = [reports]
    if ALL not in reports:
        reports.append(ALL)
    if not all(isinstance(tag, data.Report) for tag in reports):
        raise AttributeError("Unapproved reports for {}".format(name))

    for report in reports:
        if report not in ReportInterface.reports:
            ReportInterface.reports.add(report)
        report.addToReport(group, name, value)


# --------------------------------------------
#               GROUP DEFINITIONS
# --------------------------------------------
UNGROUPED = data.Table(
    "Ungrouped", "No grouping specified for the following information."
)
RUN_META = data.Table("Run Meta")
CASE_PARAMETERS = data.Table("Case Parameters")
CASE_CONTROLS = data.Table("Case Controls")
PLANT_META = data.Table("Plant Meta")
REACTOR_PARAMS = data.Table("Reactor Params")
BURNUP_GROUPS = data.Table("Burnup Groups")
SNAPSHOT = data.Table("Snapshot", "Information regarding the loaded snapshot")
COST_ASSUMPTIONS = data.Table(
    "Cost Assumptions", "Values affecting primarily the business aspect of the reactor"
)
CORE_RESOURCES = data.Table(
    "Initial Core Resources",
    "Cost of the fuel in the core",
    header=["Required Resources", "???", "Cost ($)"],
)
CORE_AVG_ENRICH = data.Table("Core Average HM Enrichment")
STRUCT_RESOURCES = data.Table("Structural Resources")
PIN_ASSEM_DESIGN = data.Table("Pin/Assembly Design Summary (averages)")

BLOCK_AREA_FRACS = data.Table(
    "Assembly Area Fractions",
    " Of First Fuel Block",
    header=["Component", "Area (cm^2)", "Fraction"],
)

CLAD_DIMS = data.Table("Cladding Dimensions", " Of First Fuel Block")
WIRE_DIMS = data.Table("Wire Dimensions", " Of First Fuel Block")
DUCT_DIMS = data.Table("Duct Dimensions", " Of First Fuel Block")
COOLANT_DIMS = data.Table("Coolant Dimensions", " Of First Fuel Block")
INTERCOOLANT_DIMS = data.Table("Intercoolant Dimensions", " Of First Fuel Block")
FUEL_DIMS = data.Table("Fuel Dimensions", " Of First Fuel Block")
BOND_DIMS = data.Table("Bond Dimensions", " Of First Fuel Block")
LINER_DIMS = data.Table("Liner Dimensions", " Of First Fuel Block")
GAP_DIMS = data.Table("Gap Dimensions", " Of First Fuel Block")

NEUT_PROD = data.Table("Full Core Neutron Production", header=["", "n/s"])
NEUT_LOSS = data.Table("Neutron Loss")

# -----------------------------------------

FUEL_CYC_COST = data.Image("Fuel Cycle Cost", "Cost of fuel cycle")
FACE_MAP = data.Image("Reactor Face Map", "The surface map of the reactor.")
ASSEM_TYPES = data.Image(
    "Assembly Types",
    "The axial block and enrichment distributions of assemblies in the core at "
    "beginning of life. The percentage represents the block enrichment (U-235 or B-10), where as "
    "the additional character represents the cross section id of the block. "
    "The number of fine-mesh subdivisions are provided on the secondary y-axis.",
)

KEFF_PLOT = data.Image("Plot of K-Effective vs. Time", "k-eff vs. time")
TIME_PLOT = data.Image("Plot of Value vs. Time", "value vs. time")
BURNUP_PLOT = data.Image("Plot of Burnup vs. Time", "bu vs. time")
DISTORTION_PLOT = data.Image("Plot of Distortion vs. Time", "distortion vs. time")
TEMPERATURE_PLOT = data.Image(
    "Plot of Peak Temperature vs. Time", "temperature vs. time"
)
XS_PLOT = data.Image("Plot of Xs vs. Time", "xs vs. time")
MOVES_PLOT = data.Image("Plot of Moves vs. Time", "moves vs. time")
FLUX_PLOT = data.Image("Plot of flux", "flux plot")

TIMELINE = data.Image("Timeline", "Time occupied by certain method invocations in run")


# --------------------------------------------
#               REPORT DEFINITIONS
# --------------------------------------------
ALL = data.Report(
    "Comprehensive Core Report",
    "Every piece of reported information about the ARMI run.",
)
DESIGN = data.Report(
    "Core Design Report", "Information related to the core design parameters"
)
ECONOMICS = data.Report(
    "Economics Core Report",
    "Information regarding the costs of the reactor in the simulation",
)
ENVIRONMENT = data.Report(
    "Environment Core Report", "ARMI Code environment information"
)
NEUTRONICS = data.Report("Neutronics Core Report", "Neutronics information")
THERMALHYDRAULICS = data.Report(
    "ThermalHydraulic Core Report", "ThermalHydraulic information"
)

DEVELOPER = data.Report(
    "ARMI Developer Run Report", "Run detail information meant for code developers"
)


# --------------------------------------------
#               FURTHER STYLIZATION
# --------------------------------------------

# have every report render these in the following order if present
data.Report.groupsOrderFirst = [
    FACE_MAP,
    RUN_META,
    CASE_PARAMETERS,
    CASE_CONTROLS,
    ASSEM_TYPES,
]

# This a grouping of components which span the entire html page rather than being sectioned into smaller columns
data.Report.componentWellGroups = [
    FACE_MAP,
    ASSEM_TYPES,
    CLAD_DIMS,
    WIRE_DIMS,
    DUCT_DIMS,
    COOLANT_DIMS,
    INTERCOOLANT_DIMS,
    FUEL_DIMS,
    BOND_DIMS,
]
