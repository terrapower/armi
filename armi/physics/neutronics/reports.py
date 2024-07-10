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

from collections import defaultdict

from armi.bookkeeping.report import newReportUtils
from armi.bookkeeping.report import newReports
from armi.reactor.flags import Flags
from armi.physics.neutronics.fissionProductModel.fissionProductModelSettings import (
    CONF_FP_MODEL,
)
from armi.physics.neutronics.settings import (
    CONF_BOUNDARIES,
    CONF_NEUTRONICS_KERNEL,
    CONF_NEUTRONICS_TYPE,
)


def insertNeutronicsReport(r, cs, report, stage):
    """Generate the Neutronics section of the Report.

    Parameters
    ----------
    r: Reactor
    cs: Case Settings
    report: ReportContent
    stage: ReportStage
        Begining, Standard, or End to denote what stage of report we are
        collecting contents for.
    """
    if stage == newReports.ReportStage.Begin:
        insertNeutronicsBOLContent(r, cs, report)

    elif (
        stage == newReports.ReportStage.Standard or stage == newReports.ReportStage.End
    ):
        neutronicsPlotting(r, report, cs)


def insertNeutronicsBOLContent(r, cs, report):
    """Add BOL content to Neutronics Section of the Report
        This currently includes addtions to Comprehensive Reports
        Settings table, and an Initial Core Fuel Assembly Table.

    Parameters
    ----------
    r: Reactor
    cs: Case Settings
    report: ReportContent
    """
    section = report[newReportUtils.COMPREHENSIVE_REPORT]
    table = section.get(
        newReportUtils.SETTINGS, newReports.Table("Settings", "Overview of the Run")
    )
    for key in [
        CONF_BOUNDARIES,
        CONF_NEUTRONICS_KERNEL,
        CONF_NEUTRONICS_TYPE,
        CONF_FP_MODEL,
    ]:
        table.addRow([key, cs[key]])

    insertInitialCoreFuelAssem(r, report)


def neutronicsPlotting(r, report, cs):
    """Keeps track of plotting content which is collected when Standard Stage of the report.

    Parameters
    ----------
    r: Reactor
    report: ReportContent
    cs: Case Settings
    """
    # Make K-Effective Plot
    labels = ["k-effective", "keff-uncontrolled"]
    neutronicsSection = report[NEUTRONICS_SECTION]
    if KEFF_PLOT not in neutronicsSection:
        report[NEUTRONICS_SECTION][KEFF_PLOT] = newReports.TimeSeries(
            "Plot of K-Effective",
            r.name,
            labels,
            "K-eff value",
            "keff." + cs["outputFileExtension"],
        )
        # To create the keff section and start populating it's points...
    report[NEUTRONICS_SECTION][KEFF_PLOT].add(labels[0], r.p.time, r.core.p.keff, None)
    report[NEUTRONICS_SECTION][KEFF_PLOT].add(
        labels[1], r.p.time, r.core.p.keffUnc, None
    )

    # Make PD-Plot
    if PD_PLOT not in neutronicsSection.childContents:
        report[NEUTRONICS_SECTION][PD_PLOT] = newReports.TimeSeries(
            "Max Areal PD vs. Time",
            r.name,
            ["Max PD"],
            "Max Areal PD (MW/m^2)",
            "maxpd." + cs["outputFileExtension"],
        )
    report[NEUTRONICS_SECTION][PD_PLOT].add("Max PD", r.p.time, r.core.p.maxPD, None)

    # Make DPA_Plot
    generateLinePlot(
        DPA_PLOT,
        r,
        report,
        "Displacement per Atom (DPA)",
        "dpaplot." + cs["outputFileExtension"],
    )

    # Make Burn-Up Plot
    generateLinePlot(
        BURNUP_PLOT,
        r,
        report,
        "Peak Burnup (%FIMA)",
        "burnupplot." + cs["outputFileExtension"],
    )


def insertInitialCoreFuelAssem(r, report):
    """Creates table of initial core fuel assemblies.

    Parameters
    ----------
    r: Reactor
    report: ReportContent
    """
    report[NEUTRONICS_SECTION][INITIAL_CORE_FUEL_ASSEMBLY] = newReports.Table(
        INITIAL_CORE_FUEL_ASSEMBLY,
        "Summary of Initial Core Fuel Assembly",
        header=[
            "Assembly Name",
            "Enrichment %",
            "# of Assemblies at BOL",
        ],
    )
    assemTypes = defaultdict(int)
    enrichment = defaultdict(float)
    for assem in r.core.getAssemblies(Flags.FUEL):
        enrichment[assem.p.type] = round(assem.getFissileMassEnrich() * 100, 7)
        assemTypes[assem.p.type] = assemTypes[assem.p.type] + 1
    for typeA in assemTypes:
        report[NEUTRONICS_SECTION][INITIAL_CORE_FUEL_ASSEMBLY].addRow(
            [
                typeA,
                enrichment[typeA],
                assemTypes[typeA],
            ]
        )


def generateLinePlot(subsectionHeading, r, report, yaxis, name, caption=""):
    """Creates the TimeSeries in the Report for finding peak values vs. time.

    Parameters
    ----------
    subsectionHeading: String
                    Heading for the plot
    r: Reactor
    report: ReportContent
    yaxis: String
        Label for the y-axis
    name: String
        name for the file to have.
    """
    section = report[NEUTRONICS_SECTION]
    if subsectionHeading not in section.childContents:
        labels = []
        for a in r.core.getAssemblies(Flags.FUEL):
            if a.p.type not in labels:
                labels.append(a.p.type)
        report[NEUTRONICS_SECTION][subsectionHeading] = newReports.TimeSeries(
            subsectionHeading, r.name, labels, yaxis, name, caption
        )
    maxValue = defaultdict(float)
    # dictionary for a specific time step.
    for a in r.core.getAssemblies(Flags.FUEL):
        if subsectionHeading == BURNUP_PLOT:
            maxValue[a.p.type] = max(maxValue[a.p.type], a.p.maxPercentBu)
        else:
            maxValue[a.p.type] = max(maxValue[a.p.type], a.p.maxDpaPeak)

    for key in maxValue:
        report[NEUTRONICS_SECTION][subsectionHeading].add(
            key, r.p.time, maxValue[key], None
        )


"""Subsections """
BURNUP_PLOT = "Peak Burn Up vs. Time"
DPA_PLOT = "Peak DPA vs. Time"
PD_PLOT = "Max Areal PD vs. Time"

"""
    Constants
"""
NEUTRONICS_SECTION = "Neutronics"
KEFF_PLOT = "Keff-Plot"
INITIAL_CORE_FUEL_ASSEMBLY = "Initial Core Fuel Assembly Count"
