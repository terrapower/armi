import os
from collections import defaultdict

# parts of report for neutronics
import base64
from armi.cli.reportsEntryPoint import ReportStage

from htmltree import *
from armi import runLog, settings
import matplotlib.pyplot as plt
from armi.physics.neutronics import reportConstants
from armi.bookkeeping import newReportUtils


def generateNeutronicsReport(r, cs, report, stage):
    from armi.bookkeeping import newReports
    from armi.reactor.flags import Flags

    if newReportUtils.COMPREHENSIVE_REPORT not in report.sections:
        report.sections[newReportUtils.COMPREHENSIVE_REPORT] = dict()
    if reportConstants.NEUTRONICS_SECTION not in report.sections:
        report.sections[reportConstants.NEUTRONICS_SECTION] = dict()

    # Now want to check if these sections already exist and if so then these are one time
    # So we shouldn't make them again.
    if stage == ReportStage.Begin:

        for key in ["boundaries", "neutronicsKernel", "neutronicsType", "fpModel"]:
            if (
                newReportUtils.RUNMETA
                not in report.sections[newReportUtils.COMPREHENSIVE_REPORT]
            ):
                report.sections[newReportUtils.COMPREHENSIVE_REPORT][
                    newReportUtils.RUNMETA
                ] = newReports.TableSection("Run Meta", "Overview of the Run")

            report.sections[newReportUtils.COMPREHENSIVE_REPORT][
                newReportUtils.RUNMETA
            ].addRow([key, cs[key]])

        initialCoreFuelAssem(r, report)
        """report.sections[reportConstants.NEUTRONICS_SECTION][
            "Initial Core Resource Requirements"
        ] = newReports.TableSection(
            "Initial Core Resource Requirements",
            "Summary of core resource requirements",
            header=["Enrichment %", "Heavy Mass (MT)"],
        )"""

    else:
        labels = ["k-effective"]
        if (
            reportConstants.KEFF_PLOT
            not in report.sections[reportConstants.NEUTRONICS_SECTION]
        ):
            report.sections[reportConstants.NEUTRONICS_SECTION][
                reportConstants.KEFF_PLOT
            ] = newReports.TimeSeries(
                "Plot of K-Effective", r.name, labels, "K-eff value", "keff"
            )
            # To create the keff section and start populating it's points...
        differentLines = [r.core.p.keff]
        lineUncertainties = [r.core.p.keffUnc]
        report.sections[reportConstants.NEUTRONICS_SECTION][
            reportConstants.KEFF_PLOT
        ].add(r.p.time, differentLines, lineUncertainties)
        if PD_PLOT not in report.sections[reportConstants.NEUTRONICS_SECTION]:
            report.sections[reportConstants.NEUTRONICS_SECTION][
                PD_PLOT
            ] = newReports.TimeSeries(
                "Max Areal PD vs. Time",
                r.name,
                ["max pd"],
                "Max Areal PD (MW/m^2)",
                "maxpd",
            )
        report.sections[reportConstants.NEUTRONICS_SECTION][PD_PLOT].add(
            r.p.time, [r.core.p.maxPD], [None]
        )
        generateLinePlot(DPA_PLOT, r, report, "Displacement per Atom (DPA)", "dpaplot")
        generateLinePlot(BURNUP_PLOT, r, report, "Peak Burnup (%FIMA)", "burnupplot")
        # report.sections["keff plot"] = Img(reports.generatePlot(r))


def initialCoreFuelAssem(r, report):
    from armi.reactor.flags import Flags
    from armi.bookkeeping import newReports

    """ Creates table of initial core fuel assemblies """
    report.sections[reportConstants.NEUTRONICS_SECTION][
        reportConstants.INITIAL_CORE_FUEL_ASSEMBLY
    ] = newReports.TableSection(
        reportConstants.INITIAL_CORE_FUEL_ASSEMBLY,
        "Summary of Initial Core Fuel Assembly",
        header=[
            "Assembly Name",
            "Enrichment %",
            "# of Assemblies at BOL",
        ],
    )
    assemTypes = defaultdict(float)
    enrichment = defaultdict(float)
    for assem in r.core.getAssemblies(Flags.FUEL):
        enrichment[assem.p.type] = assem.getFissileMassEnrich() * 100
        assemTypes[assem.p.type] = assemTypes[assem.p.type] + 1.0
    for typeA in assemTypes:
        report.sections[reportConstants.NEUTRONICS_SECTION][
            reportConstants.INITIAL_CORE_FUEL_ASSEMBLY
        ].addRow(
            [
                typeA,
                enrichment[typeA],
                assemTypes[typeA],
            ]
        )


def generateLinePlot(subsectionHeading, r, report, yaxis, extension):
    """ Creates the TimeSeries in the Report for finding peak values vs. time """
    from armi.reactor.flags import Flags
    from armi.bookkeeping import newReports
    from armi.reactor import assemblyParameters
    from armi.utils import runLog

    if subsectionHeading not in report.sections[reportConstants.NEUTRONICS_SECTION]:
        labels = []
        for a in r.core.getAssemblies(Flags.FUEL):
            if a.p.type not in labels:
                labels.append(a.p.type)
        report.sections[reportConstants.NEUTRONICS_SECTION][
            subsectionHeading
        ] = newReports.TimeSeries(
            subsectionHeading,
            r.name,
            labels,
            yaxis,
            extension,
        )
        dataAndTimes = report.sections[reportConstants.NEUTRONICS_SECTION][
            subsectionHeading
        ]
    else:
        dataAndTimes = report.sections[reportConstants.NEUTRONICS_SECTION][
            subsectionHeading
        ]
    maxValue = defaultdict(float)
    # dictionary for a specific time step.
    for a in r.core.getAssemblies(Flags.FUEL):
        if BURNUP_PLOT == subsectionHeading:
            maxValue[a.p.type] = max(maxValue[a.p.type], a.p.maxPercentBu)
        else:
            maxValue[a.p.type] = max(maxValue[a.p.type], a.p.maxDpaPeak)
    data = [0] * len(dataAndTimes.labels)
    for key in maxValue:
        data[dataAndTimes.labels.index(key)] = maxValue[key]
    report.sections[reportConstants.NEUTRONICS_SECTION][subsectionHeading].add(
        r.p.time, data, [None]
    )


def encode64(file_path):
    """Return the embedded HTML src attribute for an image in base64"""
    xtn = os.path.splitext(file_path)[1][1:]  # [1:] to cut out the period
    if xtn == "pdf":
        from armi import runLog

        runLog.warning(
            "'.pdf' images cannot be embedded into this HTML report. {} will not be inserted.".format(
                file_path
            )
        )
        return "Faulty PDF image inclusion: {} attempted to be inserted but no support is currently offered for such.".format(
            file_path
        )
    with open(file_path, "rb") as img_src:
        return r"data:image/{};base64,{}".format(
            xtn, base64.b64encode(img_src.read()).decode()
        )


"""Subsections """
BURNUP_PLOT = "Peak Burn Up vs. Time"
DPA_PLOT = "Peak DPA vs. Time"
PD_PLOT = "Max Areal PD vs. Time"