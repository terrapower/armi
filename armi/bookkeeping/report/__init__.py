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

"""Package for generating reports as printable groups and HTML in ARMI."""

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
        raise AttributeError(f"Given name {name} not acceptable.")

    group = group or UNGROUPED
    if not isinstance(group, data.Group):
        raise AttributeError(f"Given group {group} not acceptable/approved.")

    reports = reports or []
    if not isinstance(reports, (list, set, tuple)):
        reports = [reports]
    if ALL not in reports:
        reports.append(ALL)
    if not all(isinstance(tag, data.Report) for tag in reports):
        raise AttributeError(f"Unapproved reports for {name}")

    for report in reports:
        if report not in ReportInterface.reports:
            ReportInterface.reports.add(report)
        report.addToReport(group, name, value)


# --------------------------------------------
#               GROUP DEFINITIONS
# --------------------------------------------
BLOCK_AREA_FRACS = data.Table(
    "Assembly Area Fractions",
    " Of First Fuel Block",
    header=["Component", "Area (cm^2)", "Fraction"],
)
BOND_DIMS = data.Table("Bond Dimensions", " Of First Fuel Block")
CASE_CONTROLS = data.Table("Case Controls")
CASE_PARAMETERS = data.Table("Case Parameters")
CLAD_DIMS = data.Table("Cladding Dimensions", " Of First Fuel Block")
COOLANT_DIMS = data.Table("Coolant Dimensions", " Of First Fuel Block")
DUCT_DIMS = data.Table("Duct Dimensions", " Of First Fuel Block")
FUEL_DIMS = data.Table("Fuel Dimensions", " Of First Fuel Block")
GAP_DIMS = data.Table("Gap Dimensions", " Of First Fuel Block")
INTERCOOLANT_DIMS = data.Table("Intercoolant Dimensions", " Of First Fuel Block")
LINER_DIMS = data.Table("Liner Dimensions", " Of First Fuel Block")
NEUT_LOSS = data.Table("Neutron Loss")
NEUT_PROD = data.Table("Full Core Neutron Production", header=["", "n/s"])
PIN_ASSEM_DESIGN = data.Table("Pin/Assembly Design Summary (averages)")
RUN_META = data.Table("Run Meta")
UNGROUPED = data.Table("Ungrouped", "No grouping specified for the following information.")
WIRE_DIMS = data.Table("Wire Dimensions", " Of First Fuel Block")

# -----------------------------------------

ASSEM_TYPES = data.Image(
    "Assembly Types",
    "The axial block and enrichment distributions of assemblies in the core at "
    "beginning of life. The percentage represents the block enrichment (U-235 or B-10), where as "
    "the additional character represents the cross section id of the block. "
    "The number of fine-mesh subdivisions are provided on the secondary y-axis.",
)
FACE_MAP = data.Image("Reactor Face Map", "The surface map of the reactor.")
FLUX_PLOT = data.Image("Plot of flux", "flux plot")
KEFF_PLOT = data.Image("Plot of K-Effective vs. Time", "k-eff vs. time")
MOVES_PLOT = data.Image("Plot of Moves vs. Time", "moves vs. time")
TIME_PLOT = data.Image("Plot of Value vs. Time", "value vs. time")
TIMELINE = data.Image("Timeline", "Time occupied by certain method invocations in run")
XS_PLOT = data.Image("Plot of Xs vs. Time", "xs vs. time")


# --------------------------------------------
#               REPORT DEFINITIONS
# --------------------------------------------
ALL = data.Report(
    "Comprehensive Core Report",
    "Every piece of reported information about the ARMI run.",
)
DESIGN = data.Report("Core Design Report", "Information related to the core design parameters")


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

# This a grouping of components which span the entire html page rather than being sectioned into
# smaller columns.
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
