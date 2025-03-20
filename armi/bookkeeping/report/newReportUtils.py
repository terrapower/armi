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
import collections
import os

import numpy as np

from armi import runLog
from armi.bookkeeping.report import newReports
from armi.materials import custom
from armi.physics.fuelCycle.settings import CONF_SHUFFLE_LOGIC
from armi.reactor.components import component
from armi.reactor.flags import Flags
from armi.utils import (
    getAvailabilityFactors,
    getCycleLengths,
    getStepLengths,
    iterables,
    plotting,
    units,
)


def insertBlueprintContent(r, cs, report, blueprint):
    insertCoreDesignReport(r.core, cs, report)
    insertCoreAndAssemblyMaps(r, cs, report, blueprint),
    insertBlockDiagrams(cs, blueprint, report, True)
    insertBlockDesignReport(blueprint, report, cs)


def insertGeneralReportContent(cs, r, report, stage):
    """
    Creates Report content that is not plugin specific. Various things for the Design
    and Comprehensive sections of the report.

    Parameters
    ----------
        cs : case settings
        r : reactor
        report : ReportContents object
        blueprint : blueprint
    """
    # These items only happen once at BOL
    if stage == newReports.ReportStage.Begin:
        comprehensiveBOLContent(cs, r, report)
        insertDesignContent(r, report)


def comprehensiveBOLContent(cs, r, report):
    """Adds BOL content to the Comprehensive section of the report.

    Parameters
    ----------
    cs: Case Settings
    r: Reactor
    report: ReportContent
    """
    insertMetaTable(cs, report)
    first_fuel_block = r.core.getFirstBlock(Flags.FUEL)
    if first_fuel_block is not None:
        report[COMPREHENSIVE_REPORT][ASSEMBLY_AREA] = newReports.Table(
            "Assembly Area Fractions (of First Fuel Block)",
            header=["Component", "Area (cm<sup>2</sup>)", "Fraction"],
        )
        insertAreaFractionsReport(first_fuel_block, report)

    insertSettingsData(cs, report)


def insertDesignContent(r, report):
    """Adds Beginning of Life content to the Design section of the report.

    Parameters
    ----------
    r: reactor
    report: ReportContent

    """
    report[DESIGN][PIN_ASSEMBLY_DESIGN_SUMMARY] = getPinDesignTable(r.core)

    first_fuel_block = r.core.getFirstBlock(Flags.FUEL)
    if first_fuel_block is not None:
        report[DESIGN]["Dimensions in First Fuel Block"] = newReports.Section(
            "Dimensions in First Fuel Block"
        )

        for component_ in sorted(first_fuel_block):
            report[DESIGN]["Dimensions in First Fuel Block"].addChildElement(
                element=createDimensionReport(component_),
                heading=str(component_.name) + "dimensionReport",
                subheading=None,
            )


def insertBlockDesignReport(blueprint, report, cs):
    r"""Summarize the block designs from the loading file.

    Parameters
    ----------
    blueprint : Blueprint
    report: ReportContent
    cs: Case Settings

    """
    report[DESIGN]["Block Summaries"] = newReports.Section("Block Summaries")

    for bDesign in blueprint.blockDesigns:
        loadingFileTable = newReports.Table(
            "Summary Of Block: {}".format(bDesign.name), "block contents"
        )
        loadingFileTable.header = ["", "Input Parameter"]
        constructedBlock = bDesign.construct(cs, blueprint, 0, 1, 0, "A", dict())
        loadingFileTable.addRow(["Number of Components", len(bDesign)])
        lst = [i for i in range(len(bDesign))]
        for i, cDesign, c in zip(lst, bDesign, constructedBlock):
            cType = cDesign.name
            componentSplitter = (i + 1) * " " + "\n"
            loadingFileTable.addRow([componentSplitter, ""])
            loadingFileTable.addRow(
                [
                    "{} {}".format(cType, "Shape"),
                    "{} {}".format(cDesign.shape, ""),
                ]
            )
            loadingFileTable.addRow(
                [
                    "{} {}".format(cType, "Material"),
                    "{} {}".format(cDesign.material, ""),
                ]
            )
            loadingFileTable.addRow(
                [
                    "{} {}".format(cType, "Hot Temperature"),
                    "{} {}".format(cDesign.Thot, ""),
                ]
            )
            loadingFileTable.addRow(
                [
                    "{} {}".format(cType, "Cold Temperature"),
                    "{} {}".format(cDesign.Tinput, ""),
                ]
            )
            for pd in c.pDefs:
                if pd.name in c.DIMENSION_NAMES:
                    value = c.getDimension(pd.name, cold=True)
                    unit = ""
                    if pd.units is not None:
                        unit = pd.units
                    if value is not None:
                        loadingFileTable.addRow(
                            [
                                "{} {}".format(cType, pd.name),
                                "{} {}".format(value, unit),
                            ]
                        )
        loadingFileTable.title = "Summary of Block: {}".format(bDesign.name)
        report[DESIGN]["Block Summaries"].addChildElement(
            loadingFileTable, loadingFileTable.title
        )


def insertCoreDesignReport(core, cs, report):
    r"""Builds report to summarize core design inputs.

    Parameters
    ----------
    core:  armi.reactor.reactors.Core
    cs: armi.settings.caseSettings.Settings
    """
    coreDesignTable = newReports.Table("Core Report Table")
    coreDesignTable.header = ["", "Input Parameter"]
    report["Design"]["Core Design Table"] = coreDesignTable

    _setGeneralCoreDesignData(cs, coreDesignTable)

    _setGeneralCoreParametersData(core, cs, coreDesignTable)

    _setGeneralSimulationData(core, cs, coreDesignTable)


def _setGeneralCoreDesignData(cs, coreDesignTable):
    from armi.physics.neutronics.settings import CONF_LOADING_FILE

    coreDesignTable.addRow(["Case Title", "{}".format(cs.caseTitle)])
    coreDesignTable.addRow(["Run Type", "{}".format(cs["runType"])])
    coreDesignTable.addRow(["Loading File", "{}".format(cs[CONF_LOADING_FILE])])
    coreDesignTable.addRow(
        ["Fuel Shuffling Logic File", "{}".format(cs[CONF_SHUFFLE_LOGIC])]
    )
    coreDesignTable.addRow(["Reactor State Loading", "{}".format(cs["loadStyle"])])
    if cs["loadStyle"] == "fromDB":
        coreDesignTable.addRow(["Database File", "{}".format(cs["reloadDBName"])])
        coreDesignTable.addRow(["Starting Cycle", "{}".format(cs["startCycle"])])
        coreDesignTable.addRow(["Starting Node", "{}".format(cs["startNode"])])


def _setGeneralCoreParametersData(core, cs, coreDesignTable):
    """Sets the general Core Parameter Data.

    Parameters
    ----------
    core: Core
    cs: Case Settings
    coreDesignTable: newReports.Table
        Current state of table to be added to
    """
    blocks = core.getBlocks()
    totalMass = sum(b.getMass() for b in blocks)
    fissileMass = sum(b.getFissileMass() for b in blocks)
    heavyMetalMass = sum(b.getHMMass() for b in blocks)
    totalVolume = sum(b.getVolume() for b in blocks)
    coreDesignTable.addRow([" ", ""])
    coreDesignTable.addRow(
        ["Core Power", "{:.2f} MWth".format(cs["power"] / units.WATTS_PER_MW)]
    )
    coreDesignTable.addRow(
        ["Base Capacity Factor", "{}".format(getAvailabilityFactors(cs))],
    )
    coreDesignTable.addRow(
        ["Cycle Length", "{} days".format(getCycleLengths(cs))],
    )
    coreDesignTable.addRow(
        ["Burnup Cycles", "{}".format(cs["nCycles"])],
    )
    coreDesignTable.addRow(
        [
            "Burnup Steps per Cycle",
            "{}".format([len(steps) for steps in getStepLengths(cs)]),
        ],
    )
    corePowerMult = int(core.powerMultiplier)
    coreDesignTable.addRow(
        ["Core Total Volume", "{:.2f} cc".format(totalVolume * corePowerMult)],
    )
    coreDesignTable.addRow(
        [
            "Core Fissile Mass",
            "{:.2f} kg".format(fissileMass / units.G_PER_KG * corePowerMult),
        ],
    )
    coreDesignTable.addRow(
        [
            "Core Heavy Metal Mass",
            "{:.2f} kg".format(heavyMetalMass / units.G_PER_KG * corePowerMult),
        ],
    )
    coreDesignTable.addRow(
        [
            "Core Total Mass",
            "{:.2f} kg".format(totalMass / units.G_PER_KG * corePowerMult),
        ]
    )
    coreDesignTable.addRow(
        ["Number of Assembly Rings", "{}".format(core.getNumRings())]
    )
    coreDesignTable.addRow(
        ["Number of Assemblies", "{}".format(len(core.getAssemblies() * corePowerMult))]
    )
    coreDesignTable.addRow(
        [
            "Number of Fuel Assemblies",
            "{}".format(len(core.getAssemblies(Flags.FUEL) * corePowerMult)),
        ]
    )
    coreDesignTable.addRow(
        [
            "Number of Control Assemblies",
            "{}".format(len(core.getAssemblies(Flags.CONTROL) * corePowerMult)),
        ]
    )
    coreDesignTable.addRow(
        [
            "Number of Reflector Assemblies",
            "{}".format(len(core.getAssemblies(Flags.REFLECTOR) * corePowerMult)),
        ]
    )
    coreDesignTable.addRow(
        [
            "Number of Shield Assemblies",
            "{}".format(len(core.getAssemblies(Flags.SHIELD) * corePowerMult)),
        ]
    )


def _setGeneralSimulationData(core, cs, coreDesignTable):
    from armi.physics.neutronics.settings import CONF_GEN_XS, CONF_GLOBAL_FLUX_ACTIVE

    coreDesignTable.addRow(["  ", ""])
    coreDesignTable.addRow(["Full Core Model", "{}".format(core.isFullCore)])
    coreDesignTable.addRow(
        ["Tight Physics Coupling Enabled", "{}".format(bool(cs["tightCoupling"]))]
    )
    coreDesignTable.addRow(
        ["Lattice Physics Enabled for", "{}".format(cs[CONF_GEN_XS])]
    )
    coreDesignTable.addRow(
        ["Neutronics Enabled for", "{}".format(cs[CONF_GLOBAL_FLUX_ACTIVE])]
    )


def insertEndOfLifeContent(r, report):
    """
    Generate End of Life Content for the report.

    Parameters
    ----------
    r : Reactor
        the reactor
    report : ReportContent
        The report to be added to.
    """
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


def insertBlockDiagrams(cs, blueprint, report, cold):
    """Adds Block Diagrams to the report.

    Parameters
    ----------
    cs: Case Settings
    blueprint: Blueprint
    report: ReportContent
    cold: boolean
        True for dimensions at cold temps
    """
    materialList = []
    for bDesign in blueprint.blockDesigns:
        block = bDesign.construct(cs, blueprint, 0, 1, 0, "A", dict())
        for comp in block:
            if isinstance(comp.material, custom.Custom):
                materialName = comp.p.customIsotopicsName
            else:
                materialName = comp.material.name
            if materialName not in materialList:
                materialList.append(materialName)

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


def insertMetaTable(cs, report):
    """Generates part of the Settings table.

    Parameters
    ----------
    cs: Case Settings
    report: ReportContent
    """
    section = report[COMPREHENSIVE_REPORT]
    tableList = section.get(
        SETTINGS, newReports.Table("Settings", "General overview of the run")
    )
    tableList.addRow(["outputFileExtension", cs["outputFileExtension"]])
    tableList.addRow(["Total Core Power", "%8.5E MWt" % (cs["power"] / 1.0e6)])
    if not cs["cycleLengths"]:
        tableList.addRow(["Cycle Length", "%8.5f days" % cs["cycleLength"]])
    tableList.addRow(["BU Groups", str(cs["buGroups"])])


def insertSettingsData(cs, report):
    """Creates tableSections of Parameters (Case Parameters, Reactor Parameters, Case Controls and Snapshots of the run.

    Parameters
    ----------
    cs: Case Settings
    report: ReportContent
        The report to be added to
    """
    from armi.physics.neutronics.settings import CONF_GEN_XS, CONF_NEUTRONICS_KERNEL

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
        "nTasks",
    ]:
        report[COMPREHENSIVE_REPORT][CASE_PARAMETERS].addRow([key, cs[key]])

    for key in cs.environmentSettings:

        report[COMPREHENSIVE_REPORT][SETTINGS].addRow([key, str(cs[key])])
    for key in ["reloadDBName", "startCycle", "startNode"]:
        report[COMPREHENSIVE_REPORT][SNAPSHOT].addRow([key, cs[key]])

    for key in ["power", "Tin", "Tout"]:
        report[COMPREHENSIVE_REPORT][REACTOR_PARAMS].addRow([key, cs[key]])

    for key in [CONF_GEN_XS, CONF_NEUTRONICS_KERNEL]:
        report[COMPREHENSIVE_REPORT][CASE_CONTROLS].addRow([key, str(cs[key])])

    for key in ["buGroups"]:
        report[COMPREHENSIVE_REPORT][BURNUP_GROUPS].addRow([key, str(cs[key])])


def getPinDesignTable(core):
    """Summarizes Pin and Assembly Design for the input.

    Parameters
    ----------
    core: Core
    """
    designInfo = collections.defaultdict(list)

    tableRows = newReports.Table("Pin Design", header=None)
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
        designInfo = {key: np.average(data) for key, data in designInfo.items()}
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
    except Exception as error:
        runLog.warning("Pin summarization failed to work")
        runLog.warning(error)

    return tableRows


def insertAreaFractionsReport(block, report):
    """
    Adds to an Assembly Area Fractions.

    Adds to the table subsection of the Comprehensive Section
    of the report.

    Parameters
    ----------
    block : Block
        The block
    report : ReportContent
        The report
    """
    for c, frac in block.getVolumeFractions():
        report[COMPREHENSIVE_REPORT][ASSEMBLY_AREA].addRow(
            [c.getName(), "{0:10f}".format(c.getArea()), "{0:10f}".format(frac)]
        )


def createDimensionReport(comp):
    """Gives a report of the dimensions of this component.

    Parameters
    ----------
    comp: Component

    Returns
    -------
    newReports.Table that corresponds to the passed componenets dimension report
    """
    REPORT_GROUPS = {
        Flags.INTERCOOLANT: INTERCOOLANT_DIMS,
        Flags.BOND: BOND_DIMS,
        Flags.DUCT: DUCT_DIMS,
        Flags.COOLANT: COOLANT_DIMS,
        Flags.CLAD: CLAD_DIMS,
        Flags.FUEL: FUEL_DIMS,
        Flags.WIRE: WIRE_DIMS,
        Flags.LINER: LINER_DIMS,
        Flags.GAP: GAP_DIMS,
    }
    reportGroup = None
    for componentType, componentReport in REPORT_GROUPS.items():

        if comp.hasFlags(componentType):
            reportGroup = newReports.Table(componentReport.capitalize())
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


def insertCoreAndAssemblyMaps(
    r, cs, report, blueprint, generateFullCoreMap=False, showBlockAxMesh=True
):
    """Create core and assembly design plots.

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
    imageCaption = (
        "The axial block and enrichment distributions of assemblies in the core at beginning of "
        + "life. The percentage represents the block enrichment (U-235 or B-10), where as the "
        + "additional character represents the cross section id of the block. The number of fine-"
        + "mesh subdivisions are provided on the secondary y-axis."
    )

    report[DESIGN]["Assembly Designs"] = newReports.Section("Assembly Designs")
    currentSection = report[DESIGN]["Assembly Designs"]
    for plotNum, assemBatch in enumerate(
        iterables.chunk(list(assemPrototypes), MAX_ASSEMS_PER_ASSEM_PLOT), start=1
    ):
        assemPlotImage = newReports.Image(
            imageCaption,
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

    report[DESIGN][CORE_MAP] = newReports.Image(
        "Map of the Core at BOL", os.path.abspath(fName)
    )


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
