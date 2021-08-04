from armi import runLog
import os
from collections import defaultdict

# parts of report for neutronics
from armi.cli.reportsEntryPoint import ReportStage
from armi.physics import neutronics

from armi.physics.neutronics import reportConstants
from armi.bookkeeping import newReportUtils
from armi.bookkeeping import newReports
from armi.reactor.flags import Flags
from armi.bookkeeping import newReports


def generateNeutronicsReport(r, cs, report, stage):
    """Generate the Neutronics section of the Report

    Parameters
    ----------
    r: Reactor
    cs: Case Settings
    report: ReportContent
    stage: ReportStage
        Begining, Standard, or End to denote what stage of report we are
        collecting contents for.
    """

    if stage == ReportStage.Begin:
        neutronicsBOLContent(r, cs, report)

    elif stage == ReportStage.Standard:
        neutronicsPlotting(r, report, cs)


def neutronicsBOLContent(r, cs, report):
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
    for key in ["boundaries", "neutronicsKernel", "neutronicsType", "fpModel"]:
        table.addRow([key, cs[key]])

    initialCoreFuelAssem(r, report)


def neutronicsPlotting(r, report, cs):
    """Keeps track of plotting content which is collected when Standard Stage of the report

    Parameters
    ----------
    r: Reactor
    report: ReportContent
    cs: Case Settings
    """

    # Make K-Effective Plot
    labels = ["k-effective"]
    neutronicsSection = report[reportConstants.NEUTRONICS_SECTION]
    if reportConstants.KEFF_PLOT not in neutronicsSection:
        report[reportConstants.NEUTRONICS_SECTION][
            reportConstants.KEFF_PLOT
        ] = newReports.TimeSeries(
            "Plot of K-Effective",
            r.name,
            labels,
            "K-eff value",
            "keff." + cs["outputFileExtension"],
        )
        # To create the keff section and start populating it's points...
    report[reportConstants.NEUTRONICS_SECTION][reportConstants.KEFF_PLOT].add(
        labels[0], r.p.time, r.core.p.keff, r.core.p.keffUnc
    )

    # Make PD-Plot
    if PD_PLOT not in neutronicsSection.childContents:
        report[reportConstants.NEUTRONICS_SECTION][PD_PLOT] = newReports.TimeSeries(
            "Max Areal PD vs. Time",
            r.name,
            ["Max PD"],
            "Max Areal PD (MW/m^2)",
            "maxpd." + cs["outputFileExtension"],
        )
    report[reportConstants.NEUTRONICS_SECTION][PD_PLOT].add(
        "Max PD", r.p.time, r.core.p.maxPD, None
    )

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


def initialCoreFuelAssem(r, report):
    """Creates table of initial core fuel assemblies

    Parameters
    ----------
    r: Reactor
    report: ReportContent
    """
    report[reportConstants.NEUTRONICS_SECTION][
        reportConstants.INITIAL_CORE_FUEL_ASSEMBLY
    ] = newReports.Table(
        reportConstants.INITIAL_CORE_FUEL_ASSEMBLY,
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
        report[reportConstants.NEUTRONICS_SECTION][
            reportConstants.INITIAL_CORE_FUEL_ASSEMBLY
        ].addRow(
            [
                typeA,
                enrichment[typeA],
                assemTypes[typeA],
            ]
        )


def generateLinePlot(subsectionHeading, r, report, yaxis, name, caption=""):
    """Creates the TimeSeries in the Report for finding peak values vs. time

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
    section = report[reportConstants.NEUTRONICS_SECTION]
    if subsectionHeading not in section.childContents:
        labels = []
        for a in r.core.getAssemblies(Flags.FUEL):
            if a.p.type not in labels:
                labels.append(a.p.type)
        report[reportConstants.NEUTRONICS_SECTION][
            subsectionHeading
        ] = newReports.TimeSeries(
            subsectionHeading, r.name, labels, yaxis, name, caption
        )
    maxValue = defaultdict(float)
    # dictionary for a specific time step.
    for a in r.core.getAssemblies(Flags.FUEL):
        if BURNUP_PLOT == subsectionHeading:
            maxValue[a.p.type] = max(maxValue[a.p.type], a.p.maxPercentBu)
        else:
            maxValue[a.p.type] = max(maxValue[a.p.type], a.p.maxDpaPeak)

    for key in maxValue:
        report[reportConstants.NEUTRONICS_SECTION][subsectionHeading].add(
            key, r.p.time, maxValue[key], None
        )


"""Subsections """
BURNUP_PLOT = "Peak Burn Up vs. Time"
DPA_PLOT = "Peak DPA vs. Time"
PD_PLOT = "Max Areal PD vs. Time"
