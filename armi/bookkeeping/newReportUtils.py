import collections


from numpy import ComplexWarning
from framework.armi import runLog
from armi.reactor.flags import Flags
from armi.bookkeeping import newReports

import os
import matplotlib.pyplot as plt
from htmltree import *


def createGeneralReportContent(cs, r, report, blueprint, stage):
    from armi.cli.reportsEntryPoint import ReportStage

    """ 
    Creates Report content that is not plugin specific. Various things for the Design
    and Comprehensive sections of the report.

    Parameters:
        cs : case settings
        r : reactor
        report : ReportContents object
        blueprint : blueprint

    """
    # These items only happen once at BOL
    if stage == ReportStage.Begin:
        comprehensiveBOLContent(cs, r, report)
        designBOLContent(cs, r, report, blueprint)

    return report


def comprehensiveBOLContent(cs, r, report):

    if COMPREHENSIVE_REPORT not in report.sections:
        report.sections[COMPREHENSIVE_REPORT] = dict()

    report.sections[COMPREHENSIVE_REPORT][RUNMETA] = generateMetaTable(cs, report)
    first_fuel_block = r.core.getFirstBlock(Flags.FUEL)
    if first_fuel_block is not None:
        report.sections[COMPREHENSIVE_REPORT][ASSEMBLY_AREA] = newReports.TableSection(
            "Assembly Area Fractions (of First Fuel Block)",
            "Of First Block",
            header=["Component", "Area (cm<sup>2</sup>)", "Fraction"],
        )
        setAreaFractionsReport(first_fuel_block, report)

    if CASE_PARAMETERS not in report.sections[COMPREHENSIVE_REPORT]:
        settingsData(cs, report)


def designBOLContent(cs, r, report, blueprint):
    from armi.bookkeeping.report import reportingUtils

    report.sections[DESIGN] = dict()
    reportingUtils.makeCoreDesignReport2(r.core, cs, report)
    core = r.core
    report.sections[DESIGN][CORE_MAP] = newReports.ImageSection(
        "Core Map",
        "Map of the Core at BOL",
        makeCoreAndAssemblyMaps(r, cs, report, blueprint),
    )
    reportBlockDiagrams(cs, blueprint, report, True)
    report.sections[DESIGN][PIN_ASSEMBLY_DESIGN_SUMMARY] = summarizePinDesign(core)
    first_fuel_block = r.core.getFirstBlock(Flags.FUEL)
    if first_fuel_block is not None:
        for component_ in sorted(first_fuel_block):
            report.sections[DESIGN][
                component_.getName().capitalize() + " Dimensions"
            ] = setDimensionReport(component_)

    reportingUtils.makeBlockDesignReport2(blueprint, report, cs)


def getEndOfLifeContent(r, cs, report):
    from armi.utils import plotting
    from armi.utils import units

    fName2 = "powerMap.png"
    dataForTotalPower = [a.getMaxParam("power") / units.WATTS_PER_MW for a in r.core]
    plotting.plotFaceMap(
        r.core,
        param="power",
        data=dataForTotalPower,
        fName=fName2,
        cmapName="RdYlBu_r",
        axisEqual=True,
        bare=True,
        titleSize=10,
        fontSize=8,
        makeColorBar=True,
    )

    report.sections[DESIGN][TOTAL_POWER_EOL] = newReports.ImageSection(
        "Power Map", "Total Assembly Power at EOL in MWt", os.path.abspath(fName2)
    )


def reportBlockDiagrams(cs, blueprint, report, temp):
    from armi.utils import plotting

    for ai, bDesign in enumerate(blueprint.blockDesigns):
        block = bDesign.construct(cs, blueprint, 0, 1, 0, "A", dict())
        fileName = plotting.plotBlockDiagram(block, "RdYlBu_r", ai, temp)
        if fileName is not None:
            report.sections[DESIGN][
                "Block Diagram {} for {}".format(ai, bDesign.name)
            ] = newReports.ImageSection(
                "Block Diagram",
                "Diagram of Block at Cold Temperature",
                fileName,
            )


def generateMetaTable(cs, report):
    """Generates part of the Runmeta table"""
    from armi.bookkeeping import newReports

    if RUNMETA in report.sections[COMPREHENSIVE_REPORT]:
        tableList = report.sections[COMPREHENSIVE_REPORT][RUNMETA]
    else:
        tableList = newReports.TableSection("Run Meta", "General overview of the run")
    tableList.addRow(["outputFileExtension", cs["outputFileExtension"]])
    tableList.addRow(["Total Core Power", "%8.5E MWt" % (cs["power"] / 1.0e6)])
    if not cs["cycleLengths"]:
        tableList.addRow(["Cycle Length", "%8.5f days" % cs["cycleLength"]])
    tableList.addRow(["BU Groups", str(cs["buGroups"])])
    return tableList


def settingsData(cs, report):
    """Creates tableSections of Parameters (Case Parameters, Reactor Parameters, Case Controls and Snapshots of the run"""
    report.sections[COMPREHENSIVE_REPORT][CASE_PARAMETERS] = newReports.TableSection(
        "Case Parameters", "Summary of the case parameters"
    )
    report.sections[COMPREHENSIVE_REPORT][REACTOR_PARAMS] = newReports.TableSection(
        "Reactor Parameters", "Table of the Reactor Parameters"
    )
    report.sections[COMPREHENSIVE_REPORT][CASE_CONTROLS] = newReports.TableSection(
        "Case Controls", "Case Controls"
    )
    report.sections[COMPREHENSIVE_REPORT][SNAPSHOT] = newReports.TableSection(
        "Snapshot", "Snapshot of the Reactor"
    )
    report.sections[COMPREHENSIVE_REPORT][BURNUP_GROUPS] = newReports.TableSection(
        "Burn Up Groups", "Burn Up Groups"
    )

    for key in [
        "nCycles",
        "burnSteps",
        "skipCycles",
        "cycleLength",
        "numProcessors",
    ]:
        report.sections[COMPREHENSIVE_REPORT][CASE_PARAMETERS].addRow([key, cs[key]])

    """for key in cs.environmentSettings:
        report.setData(key, cs[key], report.RUN_META, [report.ENVIRONMENT])
    """

    for key in ["reloadDBName", "startCycle", "startNode"]:
        report.sections[COMPREHENSIVE_REPORT][SNAPSHOT].addRow([key, cs[key]])

    for key in ["power", "Tin", "Tout"]:
        report.sections[COMPREHENSIVE_REPORT][REACTOR_PARAMS].addRow([key, cs[key]])


def tableOfContents(elements):
    """Creates a Table of Contents at the top of the document that links to later Sections"""
    main = Main(id="toc")
    main.C.append(P("Contents"))
    outerList = Ul()
    for group in elements:
        outerList.C.append(Li(A(group, href="#{}".format(group)), id="section"))

        ul = Ul()
        for subgroup in elements[group]:
            ul.C.append(Li(A(subgroup, href="#{}".format(subgroup)), id="subsection"))
        outerList.C.append(ul)

    main.C.append(outerList)
    return main


def tableToHTML(tableRows):
    """Converts a TableSection object into a html table representation htmltree element"""
    table = Table()
    # runLog.info(tableRows.header)
    if tableRows.header is not None:
        titleRow = Tr()
        for heading in tableRows.header:
            titleRow.C.append(Th(heading))
        table.C.append(titleRow)
    for row in tableRows.rows:
        htmlRow = Tr()
        for element in row:
            htmlRow.C.append(Td(element))
        table.C.append(htmlRow)
    return table


def summarizePinDesign(core):
    """Summarizes Pin and Assembly Design for the input"""
    import collections
    import numpy
    from armi import runLog
    from armi.reactor.flags import Flags
    from armi.bookkeeping import newReports

    designInfo = collections.defaultdict(list)

    try:
        for b in core.getBlocks(Flags.FUEL):
            fuel = b.getComponent(Flags.FUEL)
            duct = b.getComponent(Flags.DUCT)
            clad = b.getComponent(Flags.CLAD)
            wire = b.getComponent(Flags.WIRE)
            designInfo["hot sd"].append(b.getSmearDensity(cold=False))
            designInfo["sd"].append(b.getSmearDensity())
            designInfo["ductThick"].append(
                (duct.getDimension("op") - duct.getDimension("ip")) * 5.0
            )  # convert to mm and divide by 2
            designInfo["cladThick"].append(
                (clad.getDimension("od") - clad.getDimension("id")) * 5.0
            )
            pinOD = clad.getDimension("od") * 10.0
            wireOD = wire.getDimension("od") * 10.0
            pitch = pinOD + wireOD  # pitch has half a wire on each side.
            assemPitch = b.getPitch() * 10  # convert cm to mm.
            designInfo["pinOD"].append(pinOD)
            designInfo["wireOD"].append(wireOD)
            designInfo["pin pitch"].append(pitch)
            pinToDuctGap = b.getPinToDuctGap()
            if pinToDuctGap is not None:
                designInfo["pinToDuct"].append(b.getPinToDuctGap() * 10.0)
            designInfo["assemPitch"].append(assemPitch)
            designInfo["duct gap"].append(assemPitch - duct.getDimension("op") * 10.0)
            designInfo["nPins"].append(b.p.nPins)
            designInfo["zrFrac"].append(fuel.getMassFrac("ZR"))

        # assumption made that all lists contain only numerical data
        designInfo = {key: numpy.average(data) for key, data in designInfo.items()}
        tableRows = newReports.TableSection(
            "Pin Design", "Summarizes pin design", header=None
        )
        dimensionless = {"sd", "hot sd", "zrFrac", "nPins"}
        for key, average_value in designInfo.items():
            dim = "{0:10s}".format(key)
            val = "{0:.4f}".format(average_value)
            if key not in dimensionless:
                val += " mm"
            # want to basically add a row to a table with dim ---> val
            tableRows.addRow([dim, val])

        a = core.refAssem
        tableRows.addRow(
            ["Fuel Height (cm):", "{0:.2f}".format(a.getHeight(Flags.FUEL))]
        )
        tableRows.addRow(
            ["Plenum Height (cm):", "{0:.2f}".format(a.getHeight(Flags.PLENUM))]
        )

        return tableRows
    except Exception as error:  # pylint: disable=broad-except
        runLog.warning("Pin summarization failed to work")
        runLog.warning(error)


def setAreaFractionsReport(block, report):
    from armi.bookkeeping import newReportUtils
    from armi.bookkeeping import newReports

    for c, frac in block.getVolumeFractions():

        report.sections[newReportUtils.COMPREHENSIVE_REPORT][ASSEMBLY_AREA].addRow(
            [c.getName(), "{0:10f}".format(c.getArea()), "{0:10f}".format(frac)]
        )


def setDimensionReport(comp):
    """Gives a report of the dimensions of this component."""
    from armi.reactor.components import component
    from armi.bookkeeping import newReportUtils
    from armi.bookkeeping import newReports

    REPORT_GROUPS = {
        "intercoolant": newReportUtils.INTERCOOLANT_DIMS,
        "bond": newReportUtils.BOND_DIMS,
        "duct": newReportUtils.DUCT_DIMS,
        "coolant": newReportUtils.COOLANT_DIMS,
        "clad": newReportUtils.CLAD_DIMS,
        "fuel": newReportUtils.FUEL_DIMS,
        "wire": newReportUtils.WIRE_DIMS,
        "liner": newReportUtils.LINER_DIMS,
        "gap": newReportUtils.GAP_DIMS,
    }
    reportGroup = None
    for componentType, componentReport in REPORT_GROUPS.items():
        if componentType in comp.getName():
            reportGroup = newReports.TableSection(componentReport, componentType)
            break
    if not reportGroup:
        return "No report group designated for {} component.".format(comp.getName())
    # reportGroup must be of type TableSection...
    reportGroup.header = [
        "",
        "Tcold ({0})".format(comp.inputTemperatureInC),
        "Thot ({0})".format(comp.temperatureInC),
    ]

    dimensions = {
        k: comp.p[k]
        for k in comp.DIMENSION_NAMES
        if k not in ("modArea", "area") and comp.p[k] is not None
    }  # py3 cannot format None
    # Set component name and material
    reportGroup.addRow(["Name", comp.getName(), ""])
    reportGroup.addRow(["Material", comp.getProperties().name, ""])

    for dimName in dimensions:
        niceName = component._NICE_DIM_NAMES.get(dimName, dimName)
        refVal = comp.getDimension(dimName, cold=True)
        hotVal = comp.getDimension(dimName)
        try:
            reportGroup.addRow([niceName, refVal, hotVal])
        except ValueError:
            runLog.warning(
                "{0} has an invalid dimension for {1}. refVal: {2} hotVal: {3}".format(
                    comp, dimName, refVal, hotVal
                )
            )

    # calculate thickness if applicable.
    suffix = None
    if "id" in dimensions:
        suffix = "d"
    elif "ip" in dimensions:
        suffix = "p"

    if suffix:
        coldIn = comp.getDimension("i{0}".format(suffix), cold=True)
        hotIn = comp.getDimension("i{0}".format(suffix))
        coldOut = comp.getDimension("o{0}".format(suffix), cold=True)
        hotOut = comp.getDimension("o{0}".format(suffix))

    if suffix and coldIn > 0.0:
        hotThick = (hotOut - hotIn) / 2.0
        coldThick = (coldOut - coldIn) / 2.0
        vals = (
            "Thickness (cm)",
            "{0:.7f}".format(coldThick),
            "{0:.7f}".format(hotThick),
        )
        reportGroup.addRow([vals[0], vals[1], vals[2]])
    return reportGroup


def valueVsTime(timePoints, ymin=None):
    """Creates a Value vs. Time graph for input"""
    import numpy

    import matplotlib.pyplot as plt
    import matplotlib.path
    import matplotlib.spines
    import matplotlib.projections.polar
    import matplotlib.cm as cm
    import matplotlib.colors as mpltcolors

    from armi import settings

    r"""
    Plots a value vs. time with a standard graph format

    Parameters
    ----------
    reactor : armi.reactor.reactors object

    reportGroup : armi.bookkeeping.report.data.Group object

    x : timePoints is a TimeSeries object collection of points

    """
    plt.figure()
    # x is now a list of lists...

    for num in range(len(timePoints.datapoints)):

        if any(timePoints.uncertainties[num]):
            plt.errorbar(
                timePoints.times,
                timePoints.datapoints[num],
                yerr=timePoints.uncertainties[num],
                label=timePoints.labels[num],
            )
        else:
            plt.plot(
                timePoints.times,
                timePoints.datapoints[num],
                ".-",
                label=timePoints.labels[num],
            )
    plt.xlabel("Time (yr)")
    plt.legend()
    plt.ylabel(timePoints.yaxis)
    plt.grid(color="0.70")
    plt.title(timePoints.title + " for {0}".format(timePoints.caption))
    if ymin is not None and all([yi > ymin for yi in timePoints.datapoints]):
        # set ymin all values are greater than it and it exists.
        ax = plt.gca()
        ax.set_ylim(bottom=ymin)

    figName = (
        timePoints.caption
        + "."
        + timePoints.key
        + "."
        + settings.getMasterCs()["outputFileExtension"]
    )
    plt.savefig(figName)
    plt.close(1)

    return Img(
        src=encode64(os.path.abspath(figName)), alt="{}_image".format(timePoints.title)
    )


def encode64(file_path):
    """Encodes the file path"""
    import base64

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


def makeCoreAndAssemblyMaps(
    r, cs, report, blueprint, generateFullCoreMap=False, showBlockAxMesh=True
):
    from armi.utils import iterables
    from armi.utils import plotting
    from armi.bookkeeping import newReports

    r"""Create core and assembly design plots

    Parameters
    ----------
    r : armi.reactor.reactors.Reactor
    cs: armi.settings.caseSettings.Settings
    report : armi.bookkeeping.newReports.ReportContent
    generateFullCoreMap : bool, default False
    showBlockAxMesh : bool, default True
    """

    assemPrototypes = set()
    for aKey in blueprint.assemDesigns.keys():
        assemPrototypes.add(blueprint.constructAssem(cs, name=aKey))

    counts = {
        assemDesign.name: len(r.core.getChildrenOfType(assemDesign.name))
        for assemDesign in blueprint.assemDesigns
    }

    core = r.core
    for plotNum, assemBatch in enumerate(
        iterables.chunk(list(assemPrototypes), MAX_ASSEMS_PER_ASSEM_PLOT), start=1
    ):
        assemPlotImage = newReports.ImageSection(
            "Assembly Types",
            "The axial block and enrichment distributions of assemblies in the core at "
            "beginning of life. The percentage represents the block enrichment (U-235 or B-10), where as "
            "the additional character represents the cross section id of the block. "
            "The number of fine-mesh subdivisions are provided on the secondary y-axis.",
            os.path.abspath(f"{core.name}AssemblyTypes{plotNum}.png"),
        )
        assemPlotImage.title = assemPlotImage.title + " ({})".format(plotNum)
        assemPlotName = os.path.abspath(f"{core.name}AssemblyTypes{plotNum}.png")
        plotting.plotAssemblyTypes(
            blueprint,
            assemPlotName,
            assemBatch,
            maxAssems=MAX_ASSEMS_PER_ASSEM_PLOT,
            showBlockAxMesh=showBlockAxMesh,
        )
        report.sections[COMPREHENSIVE_REPORT][
            f"Assembly Design{plotNum}"
        ] = assemPlotImage

    # Create radial core map
    if generateFullCoreMap:
        core.growToFullCore(cs)
    assemList = [a.p.type for a in assemPrototypes]
    # Sort so it has the same colors each time.
    assemList.sort()
    assemTypeMap = {specifier: i for i, specifier in enumerate(assemList)}

    data = [assemTypeMap[a.p.type] for a in core]
    labels = [blueprint.assemDesigns[a.p.type].specifier for a in core]

    legendMap = [
        (
            assemTypeMap[assemDesign.name],
            assemDesign.specifier,
            "{} ({})".format(assemDesign.name, counts[assemDesign.name]),
        )
        for ai, assemDesign in enumerate(blueprint.assemDesigns)
        if counts[assemDesign.name] > 0
    ]

    fName = "".join([cs.caseTitle, "RadialCoreMap.", cs["outputFileExtension"]])
    plotting.plotFaceMap(
        core,
        title="{} Radial Core Map".format(cs.caseTitle),
        fName=fName,
        cmapName="RdYlBu",
        data=data,
        labels=labels,
        legendMap=legendMap,
        axisEqual=True,
        bare=True,
        titleSize=10,
        fontSize=8,
    )

    plotting.close()

    return os.path.abspath(fName)


def plotAssemblyTypes(
    blueprints,
    assems,
    fileName=None,
    maxAssems=None,
    showBlockAxMesh=True,
) -> plt.Figure:
    from ordered_set import OrderedSet
    import numpy
    import re

    """
    Generate a plot showing the axial block and enrichment distributions of each assembly type in the core.

    Parameters
    ----------
    blueprints: Blueprints
        The blueprints to plot assembly types of.

    fileName : str or None
        Base for filename to write, or None for just returning the fig

    assems: list
        list of assembly objects to be plotted.

    maxAssems: integer
        maximum number of assemblies to plot in the assems list.

    showBlockAxMesh: bool
        if true, the axial mesh information will be displayed on the right side of the assembly plot.

    Returns
    -------
    fig : plt.Figure
        The figure object created
    """

    if assems is None:
        assems = list(blueprints.assembliesDesigns)
    if not isinstance(assems, (list, set, tuple)):
        assems = [assems]
    if maxAssems is not None and not isinstance(maxAssems, int):
        raise TypeError("Maximum assemblies should be an integer")

    numAssems = len(assems)
    if maxAssems is None:
        maxAssems = numAssems

    # Set assembly/block size constants
    yBlockHeights = []
    yBlockAxMesh = OrderedSet()
    assemWidth = 5.0
    assemSeparation = 0.3
    xAssemLoc = 0.5
    xAssemEndLoc = numAssems * (assemWidth + assemSeparation) + assemSeparation

    # Setup figure
    fig, ax = plt.subplots(figsize=(15, 15), dpi=300)
    for index, assem in enumerate(assems):
        isLastAssem = True if index == (numAssems - 1) else False
        (xBlockLoc, yBlockHeights, yBlockAxMesh) = _plotBlocksInAssembly(
            ax,
            assem,
            isLastAssem,
            yBlockHeights,
            yBlockAxMesh,
            xAssemLoc,
            xAssemEndLoc,
            showBlockAxMesh,
        )
        xAxisLabel = re.sub(" ", "\n", assem.getType().upper())
        ax.text(
            xBlockLoc + assemWidth / 2.0,
            -5,
            xAxisLabel,
            fontsize=13,
            ha="center",
            va="top",
        )
        xAssemLoc += assemWidth + assemSeparation

    # Set up plot layout
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.yaxis.set_ticks_position("left")
    yBlockHeights.insert(0, 0.0)
    yBlockHeights.sort()
    yBlockHeightDiffs = numpy.diff(
        yBlockHeights
    )  # Compute differential heights between each block
    ax.set_yticks([0.0] + list(set(numpy.cumsum(yBlockHeightDiffs))))
    ax.xaxis.set_visible(False)

    ax.set_title("Assembly Designs", y=1.03)
    ax.set_ylabel("Thermally Expanded Axial Heights (cm)".upper(), labelpad=20)
    ax.set_xlim([0.0, 0.5 + maxAssems * (assemWidth + assemSeparation)])

    # Plot and save figure
    ax.plot()
    if fileName:
        fig.savefig(fileName)
        runLog.debug("Writing assem layout {} in {}".format(fileName, os.getcwd()))
        plt.close(fig)

    return fig


def _plotBlocksInAssembly(
    axis,
    assem,
    isLastAssem,
    yBlockHeights,
    yBlockAxMesh,
    xAssemLoc,
    xAssemEndLoc,
    showBlockAxMesh,
):
    import collections
    import matplotlib
    from armi.reactor.flags import Flags

    # Set dictionary of pre-defined block types and colors for the plot
    lightsage = "xkcd:light sage"
    blockTypeColorMap = collections.OrderedDict(
        {
            "fuel": "tomato",
            "shield": "cadetblue",
            "reflector": "darkcyan",
            "aclp": "lightslategrey",
            "plenum": "white",
            "duct": "plum",
            "control": lightsage,
            "handling socket": "lightgrey",
            "grid plate": "lightgrey",
            "inlet nozzle": "lightgrey",
        }
    )

    # Initialize block positions
    blockWidth = 5.0
    yBlockLoc = 0
    xBlockLoc = xAssemLoc
    xTextLoc = xBlockLoc + blockWidth / 20.0

    for b in assem:

        blockHeight = b.getHeight()
        blockXsId = b.p.xsType
        yBlockCenterLoc = yBlockLoc + blockHeight / 2.5

        # Get the basic text label for the block
        try:
            blockType = [
                bType
                for bType in blockTypeColorMap.keys()
                if b.hasFlags(Flags.fromString(bType))
            ][0]
            color = blockTypeColorMap[blockType]
        except IndexError:
            blockType = b.getType()
            color = "grey"

        # Get the detailed text label for the block
        dLabel = ""
        if b.hasFlags(Flags.FUEL):
            dLabel = " {:0.2f}%".format(b.getFissileMassEnrich() * 100)
        elif b.hasFlags(Flags.CONTROL):
            blockType = "ctrl"
            dLabel = " {:0.2f}%".format(b.getBoronMassEnrich() * 100)
        dLabel += " ({})".format(blockXsId)

        # Set up block rectangle
        blockPatch = matplotlib.patches.Rectangle(
            (xBlockLoc, yBlockLoc),
            blockWidth,
            blockHeight,
            facecolor=color,
            alpha=0.7,
            edgecolor="k",
            lw=1.0,
            ls="solid",
        )
        axis.add_patch(blockPatch)
        axis.text(
            xTextLoc,
            yBlockCenterLoc,
            blockType.upper() + dLabel,
            ha="left",
            fontsize=10,
        )
        yBlockLoc += blockHeight
        yBlockHeights.append(yBlockLoc)

        # Add location, block heights, and axial mesh points to ordered set
        yBlockAxMesh.add((yBlockCenterLoc, blockHeight, b.p.axMesh))

    # Add the block heights, block number of axial mesh points on the far right of the plot.
    if isLastAssem and showBlockAxMesh:
        xEndLoc = 0.5 + xAssemEndLoc
        for bCenter, bHeight, axMeshPoints in yBlockAxMesh:
            axis.text(
                xEndLoc,
                bCenter,
                "{} cm ({})".format(bHeight, axMeshPoints),
                fontsize=10,
                ha="left",
            )

    return xBlockLoc, yBlockHeights, yBlockAxMesh


"""Sections Constants"""

COMPREHENSIVE_REPORT = "Comprehensive Report"
DESIGN = "Design"

"""Subsections Constants"""

RUNMETA = "Run Meta"
CORE_MAP = "Core Map"
PIN_ASSEMBLY_DESIGN_SUMMARY = "Pin and Assembly Design Summary"
REACTOR_PARAMS = "Reactor Parameters"
CASE_PARAMETERS = "Case Parameters"
CASE_CONTROLS = "Case Controls"
SNAPSHOT = "Snapshot"
BURNUP_GROUPS = "Burn-Up Groups"
ASSEMBLY_AREA = "Assembly Area Fractions"
TOTAL_POWER_EOL = "Total Power at End Of Life"

MAX_ASSEMS_PER_ASSEM_PLOT = 6


CLAD_DIMS = "Cladding Dimensions"
WIRE_DIMS = "Wire Dimensions"
DUCT_DIMS = "Duct Dimensions"
COOLANT_DIMS = "Coolant Dimensions"
INTERCOOLANT_DIMS = "Intercoolant Dimensions"
FUEL_DIMS = "Fuel Dimensions"
BOND_DIMS = "Bond Dimensions"
LINER_DIMS = "Liner Dimensions"
GAP_DIMS = "Gap Dimensions"
