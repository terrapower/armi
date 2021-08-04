from armi.utils import directoryChangers
import collections


from numpy import ComplexWarning
from armi.reactor.flags import Flags
from armi.bookkeeping import newReports
from armi.reactor import blueprints
import os
import matplotlib.pyplot as plt
import htmltree
from htmltree import Table as HtmlTable


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
        designBOLContent(r, report)

    return report


def comprehensiveBOLContent(cs, r, report):
    """Adds BOL content to the Comprehensive section of the report

    Parameters
    ----------
    cs: Case Settings
    r: Reactor
    report: ReportContent
    """

    generateMetaTable(cs, report)
    first_fuel_block = r.core.getFirstBlock(Flags.FUEL)
    if first_fuel_block is not None:
        report[COMPREHENSIVE_REPORT][ASSEMBLY_AREA] = newReports.Table(
            "Assembly Area Fractions (of First Fuel Block)",
            header=["Component", "Area (cm<sup>2</sup>)", "Fraction"],
        )
        setAreaFractionsReport(first_fuel_block, report)

    settingsData(cs, report)


def designBOLContent(r, report):
    """Adds Beginning of Life content to the Design section of the report.

    Parameters
    ----------
    r: reactor
    report: ReportContent

    """

    report[DESIGN][PIN_ASSEMBLY_DESIGN_SUMMARY] = summarizePinDesign(r.core)

    first_fuel_block = r.core.getFirstBlock(Flags.FUEL)
    if first_fuel_block is not None:
        report[DESIGN]["Dimensions in First Fuel Block"] = newReports.Section(
            "Dimensions in First Fuel Block"
        )

        for component_ in sorted(first_fuel_block):
            report[DESIGN]["Dimensions in First Fuel Block"].addChildElement(
                element=setDimensionReport(component_),
                heading=str(component_.name) + "dimensionReport",
                subheading=None,
            )


def blueprintContent(r, cs, report, blueprint):
    from armi.bookkeeping.report import reportingUtils

    reportingUtils.makeCoreDesignReport2(r.core, cs, report)
    report[DESIGN][CORE_MAP] = newReports.Image(
        "Map of the Core at BOL",
        makeCoreAndAssemblyMaps(r, cs, report, blueprint),
    )
    reportBlockDiagrams(cs, blueprint, report, True)
    reportingUtils.makeBlockDesignReport2(blueprint, report, cs)


def getEndOfLifeContent(r, report):
    """Generate End of Life Content for the report

    Parameters:
    r: Reactor
    report: ReportContent
        The report to be added to.

    """
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

    report[DESIGN][TOTAL_POWER_EOL] = newReports.Image(
        "Total Assembly Power at EOL in MWt",
        os.path.abspath(fName2),
    )


def reportBlockDiagrams(cs, blueprint, report, cold):
    """Adds Block Diagrams to the report

    Parameters
    ----------
    cs: Case Settings
    blueprint: Blueprint
    report: ReportContent
    cold: boolean
        True for dimensions at cold temps
    """
    from armi.utils import plotting

    materialList = []
    for bDesign in blueprint.blockDesigns:
        block = bDesign.construct(cs, blueprint, 0, 1, 0, "A", dict())
        for component in block:
            if component.material.name not in materialList:
                materialList.append(component.material.name)

    report[DESIGN]["Block Diagrams"] = newReports.Section("Block Diagrams")
    for bDesign in blueprint.blockDesigns:
        block = bDesign.construct(cs, blueprint, 0, 1, 0, "A", dict())
        fileName = plotting.plotBlockDiagram(
            block, "{}.svg".format(bDesign.name), cold, materialList=materialList
        )
        plotting.close()
        if fileName is not None:
            report[DESIGN]["Block Diagrams"][
                bDesign.name.capitalize()
            ] = newReports.Image(
                "Diagram of {} Block at Cold Temperature".format(
                    bDesign.name.capitalize()
                ),
                fileName,
                "{}".format(bDesign.name.capitalize()),
            )


def generateMetaTable(cs, report):
    """Generates part of the Settings table

    Parameters
    ----------
    cs: Case Settings
    report: ReportContent

    """
    from armi.bookkeeping import newReports

    section = report[COMPREHENSIVE_REPORT]
    tableList = section.get(
        SETTINGS, newReports.Table("Settings", "General overview of the run")
    )
    tableList.addRow(["outputFileExtension", cs["outputFileExtension"]])
    tableList.addRow(["Total Core Power", "%8.5E MWt" % (cs["power"] / 1.0e6)])
    if not cs["cycleLengths"]:
        tableList.addRow(["Cycle Length", "%8.5f days" % cs["cycleLength"]])
    tableList.addRow(["BU Groups", str(cs["buGroups"])])


def settingsData(cs, report):
    """Creates tableSections of Parameters (Case Parameters, Reactor Parameters, Case Controls and Snapshots of the run

    Parameters
    ----------
    cs: Case Settings
    report: ReportContent
        The report to be added to
    """

    report[COMPREHENSIVE_REPORT][CASE_PARAMETERS] = newReports.Table("Case Parameters")
    report[COMPREHENSIVE_REPORT][REACTOR_PARAMS] = newReports.Table(
        "Reactor Parameters"
    )
    report[COMPREHENSIVE_REPORT][CASE_CONTROLS] = newReports.Table("Case Controls")
    report[COMPREHENSIVE_REPORT][SNAPSHOT] = newReports.Table("Snapshot")
    report[COMPREHENSIVE_REPORT][BURNUP_GROUPS] = newReports.Table("Burn Up Groups")
    for key in [
        "nCycles",
        "burnSteps",
        "skipCycles",
        "cycleLength",
        "numProcessors",
    ]:
        report[COMPREHENSIVE_REPORT][CASE_PARAMETERS].addRow([key, cs[key]])

    for key in cs.environmentSettings:

        report[COMPREHENSIVE_REPORT][SETTINGS].addRow([key, str(cs[key])])
    for key in ["reloadDBName", "startCycle", "startNode"]:
        report[COMPREHENSIVE_REPORT][SNAPSHOT].addRow([key, cs[key]])

    for key in ["power", "Tin", "Tout"]:
        report[COMPREHENSIVE_REPORT][REACTOR_PARAMS].addRow([key, cs[key]])

    for key in ["genXS", "neutronicsKernel"]:
        report[COMPREHENSIVE_REPORT][CASE_CONTROLS].addRow([key, str(cs[key])])

    for key in ["buGroups"]:
        report[COMPREHENSIVE_REPORT][BURNUP_GROUPS].addRow([key, str(cs[key])])


def tableOfContents(elements):
    """Creates a Table of Contents at the top of the document that links to later Sections

    Parameters
    ----------
    elements: ReportContent
        Contains sections of subsections that make up the report.
    """

    main = htmltree.Main(id="toc")
    main.C.append(htmltree.P("Contents"))
    outerList = htmltree.Ul()
    for group in elements:
        outerList.C.append(
            htmltree.Ul(
                htmltree.A(elements[group].title, href="#{}".format(group)),
                _class="section",
            )
        )

        ul = htmltree.Ul(_class="subsection")
        # Subgroup is either a ReportNode or an Element...
        for subKey in elements[group].childContents:
            subgroup = elements[group].childContents[subKey]
            if type(subgroup) is newReports.Section:
                sectionHeading = htmltree.Li(
                    htmltree.A(
                        subgroup.title, href="#{}".format(str(group) + str(subKey))
                    ),
                    _class="nestedSection",
                )
                ul.C.append(sectionHeading)

                ul2 = htmltree.Ul(_class="nestedSubsection")
                for key in subgroup.childContents:
                    element = subgroup.childContents[key]
                    if element.title is not None:
                        ul2.C.append(
                            htmltree.Li(
                                htmltree.A(
                                    element.title,
                                    href="#{}".format(
                                        str(group) + str(subKey) + str(key)
                                    ),
                                )
                            )
                        )
                    else:
                        sectionHeading.A.update({"class": "subsection"})
                ul.C.append(ul2)
            elif type(subgroup) is not htmltree.HtmlElement:
                ul.C.append(
                    htmltree.Li(htmltree.A(subKey, href="#{}".format(group + subKey)))
                )

        outerList.C.append(ul)

    main.C.append(outerList)
    return main


def summarizePinDesign(core):
    """Summarizes Pin and Assembly Design for the input

    Parameters
    ----------
    core: Core
    """
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
        tableRows = newReports.Table("Pin Design", "Summarizes pin design", header=None)
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
    """Adds to an Assembly Area Fractions table subsection of the Comprehensive Section
    of the report.

        Parameters
        ----------
        block: Block
        report: ReportContent

    """
    from armi.bookkeeping import newReportUtils
    from armi.bookkeeping import newReports

    for c, frac in block.getVolumeFractions():

        report[newReportUtils.COMPREHENSIVE_REPORT][ASSEMBLY_AREA].addRow(
            [c.getName(), "{0:10f}".format(c.getArea()), "{0:10f}".format(frac)]
        )


def setDimensionReport(comp):
    """Gives a report of the dimensions of this component.

    Parameters
    ----------
    comp: Component
    """
    from armi.utils import runLog
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
            reportGroup = newReports.Table(componentType.capitalize() + " Dimensions")
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
            runLog.info(
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
        if xtn == "svg":
            return r"data:image/{};base64,{}".format(
                xtn + "+xml", base64.b64encode(img_src.read()).decode()
            )

        return r"data:image/{};base64,{}".format(
            xtn, base64.b64encode(img_src.read()).decode()
        )


def makeCoreAndAssemblyMaps(
    r, cs, report, blueprint, generateFullCoreMap=False, showBlockAxMesh=True
):
    from armi.utils import iterables
    from armi.utils import plotting, runLog
    from armi.bookkeeping import newReports

    r"""Create core and assembly design plots

    Parameters
    ----------
    r : armi.reactor.reactors.Reactor
    cs: armi.settings.caseSettings.Settings
    report : armi.bookkeeping.newReports.ReportContent
    blueprint: Blueprint
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
    report[DESIGN]["Assembly Designs"] = newReports.Section("Assembly Designs")
    currentSection = report[DESIGN]["Assembly Designs"]
    for plotNum, assemBatch in enumerate(
        iterables.chunk(list(assemPrototypes), MAX_ASSEMS_PER_ASSEM_PLOT), start=1
    ):
        assemPlotImage = newReports.Image(
            "The axial block and enrichment distributions of assemblies in the core at "
            "beginning of life. The percentage represents the block enrichment (U-235 or B-10), where as "
            "the additional character represents the cross section id of the block. "
            "The number of fine-mesh subdivisions are provided on the secondary y-axis.",
            os.path.abspath(f"{core.name}AssemblyTypes{plotNum}.png"),
        )
        assemPlotName = os.path.abspath(f"{core.name}AssemblyTypes{plotNum}.png")
        plotting.plotAssemblyTypes(
            blueprint,
            assemPlotName,
            assemBatch,
            maxAssems=MAX_ASSEMS_PER_ASSEM_PLOT,
            showBlockAxMesh=showBlockAxMesh,
        )
        currentSection.addChildElement(assemPlotImage, assemPlotName)

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

SETTINGS = "Settings"
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
