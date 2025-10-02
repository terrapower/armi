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

"""A collection of miscellaneous functions used by ReportInterface to generate various reports."""

import collections
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
from copy import copy

import numpy as np

from armi import context, interfaces, runLog
from armi.bookkeeping import report
from armi.operators import RunTypes
from armi.reactor.components import ComponentType
from armi.reactor.flags import Flags
from armi.utils import (
    getFileSHA1Hash,
    iterables,
    plotting,
    tabulate,
    textProcessors,
    units,
)

# Set to prevent the image and text from being too small to read.
MAX_ASSEMS_PER_ASSEM_PLOT = 6

# String constants
Operator_CaseTitle = "Case Title:"
Operator_TypeOfRun = "Run Type:"
Operator_NumProcessors = "Number of Processors:"
Operator_WorkingDirectory = "Working Directory:"
Operator_CurrentUser = "Current User:"
Operator_PythonInterperter = "Python Interpreter:"
Operator_PythonExecutable = "Python Executable:"
Operator_ArmiCodebase = "ARMI Location:"
Operator_MasterMachine = "Master Machine:"
Operator_Date = "Date and Time:"
Operator_CaseDescription = "Case Description:"


def writeWelcomeHeaders(o, cs):
    """Write welcome information using the Operator and the Case Settings."""

    def _writeCaseInformation(o, cs):
        """Create a table that contains basic case information."""
        caseInfo = [
            (Operator_CaseTitle, cs.caseTitle),
            (
                Operator_CaseDescription,
                "{0}".format(textwrap.fill(cs["comment"], break_long_words=False)),
            ),
            (
                Operator_TypeOfRun,
                "{} - {}".format(cs["runType"], o.__class__.__name__),
            ),
            (Operator_CurrentUser, context.USER),
            (Operator_ArmiCodebase, context.ROOT),
            (Operator_WorkingDirectory, os.getcwd()),
            (Operator_PythonInterperter, sys.version),
            (Operator_PythonExecutable, sys.executable),
            (Operator_MasterMachine, getNodeName()),
            (Operator_NumProcessors, context.MPI_SIZE),
            (Operator_Date, context.START_TIME),
        ]

        runLog.header("=========== Case Information ===========")
        runLog.info(tabulate.tabulate(caseInfo, tableFmt="armi"))

    def _listInputFiles(cs):
        """
        Gathers information about the input files of this case.

        Returns
        -------
        inputInfo : list
            (label, fileName, shaHash) tuples
        """
        from armi.physics.neutronics.settings import CONF_LOADING_FILE

        pathToLoading = pathlib.Path(cs.inputDirectory) / cs[CONF_LOADING_FILE]

        if pathToLoading.is_file():
            if pathToLoading.suffix.lower() in (".h5", ".hdf5"):
                # The blueprints are in a database, there aren't multiple included files
                includedBlueprints = [pathToLoading]
            else:
                includedBlueprints = [inclusion[0] for inclusion in textProcessors.findYamlInclusions(pathToLoading)]
        else:
            includedBlueprints = []

        inputInfo = []
        inputFiles = [
            (
                "Case Settings",
                os.path.basename(cs.path) if cs.path else cs.caseTitle + ".yaml",
            ),  # This could be a YAML or an h5.
            ("Blueprints", cs[CONF_LOADING_FILE]),
        ] + [("Included blueprints", inclBp) for inclBp in includedBlueprints]

        activeInterfaces = interfaces.getActiveInterfaceInfo(cs)
        for klass, kwargs in activeInterfaces:
            if not kwargs.get("enabled", True):
                # Don't consider disabled interfaces
                continue
            interfaceFileNames = klass.specifyInputs(cs)
            for label, fileNames in interfaceFileNames.items():
                for fName in fileNames:
                    inputFiles.append((label, fName))

        if cs["reloadDBName"] and cs["runType"] == RunTypes.SNAPSHOTS:
            inputFiles.append(("Database", cs["reloadDBName"]))
        for label, fName in inputFiles:
            shaHash = "MISSING" if (not fName or not os.path.exists(fName)) else getFileSHA1Hash(fName, digits=10)
            inputInfo.append((label, fName, shaHash))

        # bonus: grab the files stored in the crossSectionControl section
        for xsID, xsSetting in cs["crossSectionControl"].items():
            fNames = []
            # Users shouldn't ever have both of these defined, but this is not the place
            # for code to fail if they do. Allow for both to not be None.
            if xsSetting.xsFileLocation is not None:
                # possibly a list of files
                if isinstance(xsSetting.xsFileLocation, list):
                    fNames.extend(xsSetting.xsFileLocation)
                else:
                    fNames.append(xsSetting.xsFileLocation)
            if xsSetting.fluxFileLocation is not None:
                # single file
                fNames.append(xsSetting.fluxFileLocation)
            for fName in fNames:
                label = f"crossSectionControl-{xsID}"
                if fName and os.path.exists(fName):
                    shaHash = getFileSHA1Hash(os.path.abspath(fName), digits=10)
                    inputInfo.append((label, fName, shaHash))

        return inputInfo

    def _writeInputFileInformation(cs):
        """Create a table that contains basic input file information."""
        inputFileData = []
        for label, fileName, shaHash in _listInputFiles(cs):
            inputFileData.append((label, fileName, shaHash))

        runLog.header("=========== Input File Information ===========")
        runLog.info(
            tabulate.tabulate(
                inputFileData,
                headers=["Input Type", "Path", "SHA-1 Hash"],
                tableFmt="armi",
            )
        )

    def _writeMachineInformation():
        """Create a table that contains basic machine and rank information."""
        processorNames = context.MPI_NODENAMES
        uniqueNames = set(processorNames)
        nodeMappingData = []
        sysInfo = ""
        for uniqueName in uniqueNames:
            matchingProcs = [str(rank) for rank, procName in enumerate(processorNames) if procName == uniqueName]
            numProcessors = str(len(matchingProcs))
            nodeMappingData.append((uniqueName, numProcessors, ", ".join(matchingProcs)))

            sysInfo += getSystemInfo()

        runLog.header("=========== Machine Information ===========")
        runLog.info(
            tabulate.tabulate(
                nodeMappingData,
                headers=["Machine", "Number of Processors", "Ranks"],
                tableFmt="armi",
            )
        )

        if sysInfo:
            runLog.header("=========== System Information ===========")
            runLog.info(sysInfo)

    def _writeReactorCycleInformation(o, cs):
        """Verify that all the operating parameters are defined for the same number of cycles."""
        operatingData = [
            ("Reactor Thermal Power (MW):", cs["power"] / units.WATTS_PER_MW),
            ("Number of Cycles:", cs["nCycles"]),
        ]
        operatingParams = {
            "Cycle Lengths:": o.cycleLengths,
            "Availability Factors:": o.availabilityFactors,
            "Power Fractions:": o.powerFractions,
            "Step Lengths (days):": o.stepLengths,
        }

        for name, param in operatingParams.items():
            paramStr = [str(p) for p in param]
            operatingData.append((name, textwrap.fill(", ".join(paramStr))))
        runLog.header("=========== Reactor Cycle Information ===========")
        runLog.info(tabulate.tabulate(operatingData, tableFmt="armi"))

    if context.MPI_RANK > 0:
        return  # prevent the worker nodes from printing the same thing

    _writeCaseInformation(o, cs)
    _writeInputFileInformation(cs)
    _writeMachineInformation()
    _writeReactorCycleInformation(o, cs)


def getNodeName():
    """Get the name of this compute node.

    First, look in context.py. Then try various Linux tools. Then try Windows commands.

    Returns
    -------
    str
        Compute node name.
    """
    hostNames = [
        context.MPI_NODENAME,
        context.MPI_NODENAMES[0],
        subprocess.run("hostname", capture_output=True, text=True, shell=True).stdout,
        subprocess.run("uname -n", capture_output=True, text=True, shell=True).stdout,
        os.environ.get("COMPUTERNAME", context.LOCAL),
    ]
    for nodeName in hostNames:
        if nodeName and nodeName != context.LOCAL:
            return nodeName

    return context.LOCAL


def _getSystemInfoWindows():
    """Get system information, assuming the system is Windows.

    Returns
    -------
    str
        Basic system information: OS name, OS version, basic processor information

    Examples
    --------
    Example results:

        OS Name:         Microsoft Windows 10 Enterprise
        OS Version:      10.0.19041 N/A Build 19041
        Processor(s):    1 Processor(s) Installed.
                         [01]: Intel64 Family 6 Model 142 Stepping 12 GenuineIntel ~801 Mhz
    """
    cmd = (
        'systeminfo | findstr /B /C:"OS Name" /B /C:"OS Version" /B /C:"Processor" && systeminfo | findstr /E /C:"Mhz"'
    )
    return subprocess.run(cmd, capture_output=True, text=True, shell=True).stdout


def _getSystemInfoMac():
    """Get system information, assuming the system is MacOS.

    Returns
    -------
    str
        Basic system information: OS name, OS version, basic processor information

    Examples
    --------
    Example results:

        System Software Overview:

        System Version: macOS 12.1 (21C52)
        Kernel Version: Darwin 21.2.0
        ...
        Hardware Overview:
        Model Name: MacBook Pro
        ...
    """
    cmd = "system_profiler SPSoftwareDataType SPHardwareDataType"
    return subprocess.check_output(cmd, shell=True).decode("utf-8")


def _getSystemInfoLinux():
    """Get system information, assuming the system is Linux.

    This method uses multiple, redundant variations on common Linux command utilities to get the
    information necessary. While it is not possible to guarantee what programs or files will be
    available on "all Linux operating system", this collection of tools is widely supported and
    should provide a reasonably broad-distribution coverage.

    Returns
    -------
    str
        Basic system information: OS name, OS version, basic processor information

    Examples
    --------
    Example results:

        OS Info:  Ubuntu 22.04.3 LTS
        Processor(s):
            processor   : 0
            vendor_id   : GenuineIntel
            cpu family  : 6
            model       : 126
            model name  : Intel(R) Core(TM) i5-1035G1 CPU @ 1.00GHz
            ...
    """
    # get OS name / version
    linuxOsCommands = [
        'cat /etc/os-release | grep "^PRETTY_NAME=" | cut -d = -f 2',
        "uname -a",
        "lsb_release -d | cut -d : -f 2",
        'hostnamectl | grep "Operating System" | cut -d : -f 2',
    ]
    osInfo = ""
    for cmd in linuxOsCommands:
        osInfo = subprocess.run(cmd, capture_output=True, text=True, shell=True).stdout.strip()
        if osInfo:
            break

    if not osInfo:
        runLog.warning("Linux OS information not found.")
        return ""

    # get processor information
    linuxProcCommands = ["lscpu", "cat /proc/cpuinfo", "lshw -class CPU"]
    procInfo = ""
    for cmd in linuxProcCommands:
        procInfo = subprocess.run(cmd, capture_output=True, text=True, shell=True).stdout
        if procInfo:
            break

    if not procInfo:
        runLog.warning("Linux processor information not found.")
        return ""

    # build output string
    out = "OS Info:  "
    out += osInfo.strip()
    out += "\nProcessor(s):\n    "
    out += procInfo.strip().replace("\n", "\n    ")
    out += "\n"

    return out


def getSystemInfo():
    """Get system information, assuming the system is Linux, MacOS, and Windows.

    Notes
    -----
    The format of the system information will be different on Linux, MacOS, and Windows.

    Returns
    -------
    str
        Basic system information: OS name, OS version, basic processor information
    """
    # Get basic system information (on Linux, MacOS, and Windows)
    if "darwin" in sys.platform:
        return _getSystemInfoMac()
    elif "win" in sys.platform:
        return _getSystemInfoWindows()
    elif "linux" in sys.platform:
        return _getSystemInfoLinux()
    else:
        runLog.warning(
            f"Cannot get system information for {sys.platform} because ARMI only "
            + "supports Linux, MacOS, and Windows."
        )
        return ""


def getInterfaceStackSummary(o):
    data = []
    for ii, i in enumerate(o.interfaces, start=1):
        data.append(
            (
                "{:02d}".format(ii),
                i.__class__.__name__.replace("Interface", ""),
                i.name,
                i.purpose,
                "Yes" if i.enabled() else "No",
                "Reversed" if i.reverseAtEOL else "Normal",
                "Yes" if i.bolForce() else "No",
            )
        )
    text = tabulate.tabulate(
        data,
        headers=(
            "Index",
            "Type",
            "Name",
            "Purpose",
            "Enabled",
            "EOL order",
            "BOL forced",
        ),
        tableFmt="armi",
    )
    text = text
    return text


def writeTightCouplingConvergenceSummary(convergenceSummary):
    runLog.info("Tight Coupling Convergence Summary")
    runLog.info(tabulate.tabulate(convergenceSummary, headers="keys", showIndex=True, tableFmt="armi"))


def writeAssemblyMassSummary(r):
    """Print out things like Assembly weights to the runLog.

    Parameters
    ----------
    r : armi.reactor.reactors.Reactor
    """
    massSum = []

    for a in r.blueprints.assemblies.values():
        mass = 0.0
        hmMass = 0.0
        fissileMass = 0.0
        coolantMass = 0.0  # to calculate wet vs. dry weight.
        types = []

        for b in a:
            # get masses in kg
            # skip stationary blocks (grid plate doesn't count)
            if b.hasFlags(Flags.GRID_PLATE):
                continue
            mass += b.getMass() / 1000.0
            hmMass += b.getHMMass() / 1000.0
            fissileMass += b.getFissileMass() / 1000.0
            coolants = b.getComponents(Flags.COOLANT, exact=True) + b.getComponents(Flags.INTERCOOLANT, exact=True)
            coolantMass += sum(coolant.getMass() for coolant in coolants) / 1000.0

            blockType = b.getType()
            if blockType not in types:
                types.append(blockType)
        # If the BOL fuel assem is in the center of the core, its area is 1/3 of the full area b/c
        # its a sliced assem.

        # count assemblies
        core = r.core
        thisTypeList = core.getChildrenOfType(a.getType())
        count = 0
        for t in thisTypeList:
            ring, _pos = t.spatialLocator.getRingPos()
            if ring == 1:
                # only count center location once.
                count += 1
            else:
                # add 3 if it's 1/3 core, etc.
                count += core.powerMultiplier

        # Get the dominant materials
        pinMaterialKey = "pinMaterial"
        pinMaterialObj = a.getDominantMaterial([Flags.FUEL, Flags.CONTROL])
        if pinMaterialObj is None:
            pinMaterialObj = a.getDominantMaterial()
            pinMaterialKey = "dominantMaterial"
            pinMaterial = pinMaterialObj.name
        else:
            pinMaterial = pinMaterialObj.name

        struct = a.getDominantMaterial([Flags.CLAD, Flags.DUCT, Flags.SHIELD])
        if struct:
            structuralMaterial = struct.name
        else:
            structuralMaterial = "[None]"
        cool = a.getDominantMaterial([Flags.COOLANT])
        if cool:
            coolantMaterial = cool.name
        else:
            coolantMaterial = "[None]"

        # Get pins per assembly
        pinsPerAssembly = 0
        for candidate in (Flags.FUEL, Flags.CONTROL, Flags.SHIELD):
            b = a.getFirstBlock(candidate)
            if b:
                pinsPerAssembly = b.getNumPins()
            if pinsPerAssembly:
                break

        massSum.append(
            {
                "type": a.getType(),
                "wetMass": mass,
                "hmMass": hmMass,
                "fissileMass": fissileMass,
                "dryMass": mass - coolantMass,
                "count": count,
                "components": types,
                pinMaterialKey: pinMaterial,
                "structuralMaterial": structuralMaterial,
                "coolantMaterial": coolantMaterial,
                "pinsPerAssembly": pinsPerAssembly,
            }
        )

    runLog.important(_makeBOLAssemblyMassSummary(massSum))
    runLog.important(_makeTotalAssemblyMassSummary(massSum))


def _makeBOLAssemblyMassSummary(massSum):
    str_ = ["--- BOL Assembly Mass Summary (kg) ---"]
    dataLabels = ["wetMass", "dryMass", "fissileMass", "hmMass", "count"]
    # print header for the printout of each assembly type
    str_.append(" " * 12 + "".join(["{0:25s}".format(s["type"]) for s in massSum]))
    for val in dataLabels:
        line = ""
        for s in massSum:
            line += "{0:<25.3f}".format(s[val])
        str_.append("{0:12s}{1}".format(val, line))

    # print blocks in this assembly up to 10
    for i in range(10):
        line = " " * 12
        for s in massSum:
            try:
                line += "{0:25s}".format(s["components"][i])
            except IndexError:
                line += " " * 25
        if re.search(r"\S", line):  # \S matches any non-whitespace character.
            str_.append(line)

    return "\n".join(str_)


def _makeTotalAssemblyMassSummary(massSum):
    massLabels = ["wetMass", "dryMass", "fissileMass", "hmMass"]
    totals = {}
    count = 0

    str_ = ["--Totals--"]
    for label in massLabels:
        totals[label] = 0.0
        for assemSum in massSum:
            totals[label] += assemSum[label] * assemSum["count"]
            count += assemSum["count"]
        str_.append("{0:12s} {1:.2f} MT".format(label, totals[label] / 1000.0))
    str_.append("Total assembly count: {0}".format(count // len(massLabels)))
    return "\n".join(str_)


def writeCycleSummary(core):
    """Prints a cycle summary to the runLog.

    Parameters
    ----------
    core: armi.reactor.reactors.Core
    cs: armi.settings.caseSettings.Settings
    """
    # Would io be worth considering for this?
    cycle = core.r.p.cycle
    str_ = []
    runLog.important("Cycle {0} Summary:".format(cycle))
    avgBu = core.calcAvgParam("percentBu", typeSpec=Flags.FUEL, generationNum=2)
    str_.append("Core Average Burnup: {0}".format(avgBu))
    str_.append("End of Cycle {0:02d}. Timestamp: {1} ".format(cycle, time.ctime()))

    runLog.info("\n".join(str_))


def setNeutronBalancesReport(core):
    """Determines the various neutron balances over the full core.

    Parameters
    ----------
    core : armi.reactor.reactors.Core
    """
    if not core.getFirstBlock().p.rateCap:
        runLog.warning(
            "No rate information (rateCap, rateAbs, etc.) available on the blocks. Skipping balance summary."
        )
        return

    cap = core.calcAvgParam("rateCap", volumeAveraged=False, generationNum=2)
    absorb = core.calcAvgParam("rateAbs", volumeAveraged=False, generationNum=2)
    fis = core.calcAvgParam("rateFis", volumeAveraged=False, generationNum=2)
    n2nProd = core.calcAvgParam("rateProdN2n", volumeAveraged=False, generationNum=2)
    fisProd = core.calcAvgParam("rateProdFis", volumeAveraged=False, generationNum=2)

    leak = n2nProd + fisProd - absorb

    report.setData(
        "Fission",
        "{0:.5e} ({1:.2%})".format(fisProd, fisProd / (fisProd + n2nProd)),
        report.NEUT_PROD,
    )
    report.setData(
        "n, 2n",
        "{0:.5e} ({1:.2%})".format(n2nProd, n2nProd / (fisProd + n2nProd)),
        report.NEUT_PROD,
    )
    report.setData(
        "Capture",
        "{0:.5e} ({1:.2%})".format(cap, cap / (absorb + leak)),
        report.NEUT_LOSS,
    )
    report.setData(
        "Fission",
        "{0:.5e} ({1:.2%})".format(fis, fis / (absorb + leak)),
        report.NEUT_LOSS,
    )
    report.setData(
        "Absorption",
        "{0:.5e} ({1:.2%})".format(absorb, absorb / (absorb + leak)),
        report.NEUT_LOSS,
    )
    report.setData(
        "Leakage",
        "{0:.5e} ({1:.2%})".format(leak, leak / (absorb + leak)),
        report.NEUT_LOSS,
    )

    runLog.info(report.ALL[report.NEUT_PROD])
    runLog.info(report.ALL[report.NEUT_LOSS])


def summarizePinDesign(core):
    """Prints out some information about the pin assembly/duct design.

    Handles multiple types of dimensions simplistically by taking the average.

    Parameters
    ----------
    core : armi.reactor.reactors.Core
    """
    designInfo = collections.defaultdict(list)

    try:
        for b in core.iterBlocks(Flags.FUEL):
            fuel = b.getComponent(Flags.FUEL)
            duct = b.getComponent(Flags.DUCT)
            clad = b.getComponent(Flags.CLAD)
            wire = b.getComponent(Flags.WIRE)
            designInfo["hot sd"].append(b.getSmearDensity(cold=False))
            designInfo["sd"].append(b.getSmearDensity())
            designInfo["ductThick"].append(
                (duct.getDimension("op") - duct.getDimension("ip")) * 5.0
            )  # convert to mm and divide by 2
            designInfo["cladThick"].append((clad.getDimension("od") - clad.getDimension("id")) * 5.0)
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
            report.setData(dim, val, report.PIN_ASSEM_DESIGN)

        a = core.refAssem
        report.setData(
            "Fuel Height (cm):",
            "{0:.2f}".format(a.getHeight(Flags.FUEL)),
            report.PIN_ASSEM_DESIGN,
        )
        report.setData(
            "Plenum Height (cm):",
            "{0:.2f}".format(a.getHeight(Flags.PLENUM)),
            report.PIN_ASSEM_DESIGN,
        )
        runLog.info(report.ALL[report.PIN_ASSEM_DESIGN])

        first_fuel_block = core.getFirstBlock(Flags.FUEL)
        runLog.info("Design & component information for first fuel block {}".format(first_fuel_block))

        runLog.info(first_fuel_block.setAreaFractionsReport())

        for component_ in sorted(first_fuel_block):
            runLog.info(component_.setDimensionReport())

    except Exception as error:
        runLog.warning("Pin summarization failed to work")
        runLog.warning(error)


def summarizePowerPeaking(core):
    """Prints reactor Fz, Fxy, Fq.

    Parameters
    ----------
    core : armi.reactor.reactors.Core
    """
    # Fz is the axial peaking of the highest power assembly
    _maxPow, maxPowBlock = core.getMaxParam("power", returnObj=True, generationNum=2)
    maxPowAssem = maxPowBlock.parent
    avgPDens = maxPowAssem.calcAvgParam("pdens")
    peakPDens = maxPowAssem.getMaxParam("pdens")
    if not avgPDens:
        # protect against divide-by-zero. Peaking doesn't make sense if there is no power
        return
    axPeakF = peakPDens / avgPDens

    # Fxy is the radial peaking factor, looking at ALL assemblies with axially integrated powers.
    power = 0.0
    n = 0
    for n, a in enumerate(core):
        power += a.calcTotalParam("power", typeSpec=Flags.FUEL)
    avgPow = power / (n + 1)
    radPeakF = maxPowAssem.calcTotalParam("power", typeSpec=Flags.FUEL) / avgPow

    runLog.important(
        "Power Peaking: Fz= {0:.3f} Fxy= {1:.3f} Fq= {2:.3f}".format(axPeakF, radPeakF, axPeakF * radPeakF)
    )


def summarizePower(core):
    """Provide an edit showing where the power is based on assembly types.

    Parameters
    ----------
    core : armi.reactor.reactors.Core
    """
    sums = collections.defaultdict(lambda: 0.0)
    pmult = core.powerMultiplier
    for a in core:
        sums[a.getType()] += a.calcTotalParam("power") * pmult

    # calculate total power
    tot = sum(sums.values()) or float("inf")
    # NOTE: if tot is 0.0, set to infinity to prevent ZeroDivisionError

    runLog.important("Power summary")
    for atype, val in sums.items():
        runLog.important(" Power in {0:35s}: {1:0.3E} Watts, {2:0.5f}%".format(atype, val, val / tot * 100))


def makeCoreDesignReport(core, cs):
    """Builds report to summarize core design inputs.

    Parameters
    ----------
    core: armi.reactor.reactors.Core
    cs: armi.settings.caseSettings.Settings
    """
    coreDesignTable = report.data.Table("SUMMARY OF CORE: {}".format(cs.caseTitle.upper()))
    coreDesignTable.header = ["", "Input Parameter"]

    # Change the ordering of the core design table in the report relative to the other data
    report.data.Report.groupsOrderFirst.insert(0, coreDesignTable)
    report.data.Report.componentWellGroups.insert(0, coreDesignTable)

    _setGeneralCoreDesignData(cs, coreDesignTable)
    _setGeneralCoreParametersData(core, cs, coreDesignTable)
    _setGeneralSimulationData(core, cs, coreDesignTable)


def _setGeneralCoreDesignData(cs, coreDesignTable):
    from armi.physics.fuelCycle.settings import CONF_SHUFFLE_LOGIC
    from armi.physics.neutronics.settings import CONF_LOADING_FILE

    report.setData("Case Title", "{}".format(cs.caseTitle), coreDesignTable, report.DESIGN)
    report.setData("Run Type", "{}".format(cs["runType"]), coreDesignTable, report.DESIGN)
    report.setData(
        "Loading File",
        "{}".format(cs[CONF_LOADING_FILE]),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Fuel Shuffling Logic File",
        "{}".format(cs[CONF_SHUFFLE_LOGIC]),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Reactor State Loading",
        "{}".format(cs["loadStyle"]),
        coreDesignTable,
        report.DESIGN,
    )
    if cs["loadStyle"] == "fromDB":
        report.setData(
            "Database File",
            "{}".format(cs["reloadDBName"]),
            coreDesignTable,
            report.DESIGN,
        )
        report.setData(
            "Starting Cycle",
            "{}".format(cs["startCycle"]),
            coreDesignTable,
            report.DESIGN,
        )
        report.setData(
            "Starting Node",
            "{}".format(cs["startNode"]),
            coreDesignTable,
            report.DESIGN,
        )


def _setGeneralCoreParametersData(core, cs, coreDesignTable):
    blocks = core.getBlocks()
    totalMass = sum(b.getMass() for b in blocks)
    fissileMass = sum(b.getFissileMass() for b in blocks)
    heavyMetalMass = sum(b.getHMMass() for b in blocks)
    totalVolume = sum(b.getVolume() for b in blocks)
    report.setData(" ", "", coreDesignTable, report.DESIGN)
    report.setData(
        "Core Power",
        "{:.2f} MWth".format(cs["power"] / units.WATTS_PER_MW),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Base Capacity Factor",
        "{}".format(cs["availabilityFactor"]),
        coreDesignTable,
        report.DESIGN,
    )  # note this doesn't consider availabilityFactors
    report.setData(
        "Cycle Length",
        "{} days".format(cs["cycleLength"]),
        coreDesignTable,
        report.DESIGN,
    )  # note this doesn't consider cycleLengths
    report.setData("Burnup Cycles", "{}".format(cs["nCycles"]), coreDesignTable, report.DESIGN)
    report.setData(
        "Burnup Steps per Cycle",
        "{}".format(cs["burnSteps"]),
        coreDesignTable,
        report.DESIGN,
    )  # note this doesn't consider the detailed cycle input option
    corePowerMult = int(core.powerMultiplier)
    report.setData(
        "Core Total Volume",
        "{:.2f} cc".format(totalVolume * corePowerMult),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Core Fissile Mass",
        "{:.2f} kg".format(fissileMass / units.G_PER_KG * corePowerMult),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Core Heavy Metal Mass",
        "{:.2f} kg".format(heavyMetalMass / units.G_PER_KG * corePowerMult),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Core Total Mass",
        "{:.2f} kg".format(totalMass / units.G_PER_KG * corePowerMult),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Number of Assembly Rings",
        "{}".format(core.getNumRings()),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Number of Assemblies",
        "{}".format(len(core.getAssemblies() * corePowerMult)),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Number of Fuel Assemblies",
        "{}".format(len(core.getAssemblies(Flags.FUEL) * corePowerMult)),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Number of Control Assemblies",
        "{}".format(len(core.getAssemblies(Flags.CONTROL) * corePowerMult)),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Number of Reflector Assemblies",
        "{}".format(len(core.getAssemblies(Flags.REFLECTOR) * corePowerMult)),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Number of Shield Assemblies",
        "{}".format(len(core.getAssemblies(Flags.SHIELD) * corePowerMult)),
        coreDesignTable,
        report.DESIGN,
    )


def _setGeneralSimulationData(core, cs, coreDesignTable):
    from armi.physics.neutronics.settings import CONF_GEN_XS, CONF_GLOBAL_FLUX_ACTIVE

    report.setData("  ", "", coreDesignTable, report.DESIGN)
    report.setData("Full Core Model", "{}".format(core.isFullCore), coreDesignTable, report.DESIGN)
    report.setData(
        "Tight Physics Coupling Enabled",
        "{}".format(bool(cs["tightCoupling"])),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Lattice Physics Enabled for",
        "{}".format(cs[CONF_GEN_XS]),
        coreDesignTable,
        report.DESIGN,
    )
    report.setData(
        "Neutronics Enabled for",
        "{}".format(cs[CONF_GLOBAL_FLUX_ACTIVE]),
        coreDesignTable,
        report.DESIGN,
    )


def makeBlockDesignReport(r):
    """Summarize the block designs from the loading file.

    Parameters
    ----------
    r : armi.reactor.reactors.Reactor
    """
    for bDesign in r.blueprints.blockDesigns:
        loadingFileTable = report.data.Table("SUMMARY OF BLOCK: {}".format(bDesign.name))
        loadingFileTable.header = ["", "Input Parameter"]

        # Change the ordering of the loading file table in the report relative to the other data
        report.data.Report.groupsOrderFirst.append(loadingFileTable)
        report.data.Report.componentWellGroups.append(loadingFileTable)
        report.setData("Number of Components", [len(bDesign)], loadingFileTable, report.DESIGN)
        for i, cDesign in enumerate(bDesign):
            cType = cDesign.name
            componentSplitter = (i + 1) * " " + "\n"
            report.setData(componentSplitter, [""], loadingFileTable, report.DESIGN)
            dimensions = _getComponentInputDimensions(cDesign)
            for label, values in dimensions.items():
                value, unit = values
                report.setData(
                    "{} {}".format(cType, label),
                    "{} {}".format(value, unit),
                    loadingFileTable,
                    report.DESIGN,
                )


def _getComponentInputDimensions(cDesign):
    """Get the input dimensions of a component and place them in a dictionary with labels and units."""
    dims = collections.OrderedDict()
    dims["Shape"] = (cDesign.shape, "")
    dims["Material"] = (cDesign.material, "")
    dims["Cold Temperature"] = (cDesign.Tinput, "C")
    dims["Hot Temperature"] = (cDesign.Thot, "C")

    if cDesign.isotopics is not None:
        dims["Custom Isotopics"] = (cDesign.isotopics, "")

    for dimName in ComponentType.TYPES[cDesign.shape.lower()].DIMENSION_NAMES:
        value = getattr(cDesign, dimName)

        if value is not None:
            # if not default, add it to the report
            dims[dimName] = (getattr(cDesign, dimName).value, "cm")

    return dims


def makeCoreAndAssemblyMaps(r, cs, generateFullCoreMap=False, showBlockAxMesh=True):
    """Create core and assembly design plots.

    Parameters
    ----------
    r : armi.reactor.reactors.Reactor
    cs: armi.settings.caseSettings.Settings
    generateFullCoreMap : bool, default False
    showBlockAxMesh : bool, default True
    """
    assems = []
    blueprints = r.blueprints
    for aKey in blueprints.assemDesigns.keys():
        a = blueprints.constructAssem(cs, name=aKey)
        # since we will be plotting cold input heights, we need to make sure that
        # that these new assemblies have access to a blueprints somewhere up the
        # composite chain. normally this would happen through an assembly's parent
        # reactor, but because these newly created assemblies are in the load queue,
        # they will not have a parent reactor. to get around this, we just attach
        # the blueprints to the assembly directly.
        a.blueprints = blueprints
        assems.append(a)

    core = r.core
    for plotNum, assemBatch in enumerate(iterables.chunk(assems, MAX_ASSEMS_PER_ASSEM_PLOT), start=1):
        assemPlotImage = copy(report.ASSEM_TYPES)
        assemPlotImage.title = assemPlotImage.title + " ({})".format(plotNum)
        report.data.Report.groupsOrderFirst.insert(-1, assemPlotImage)
        report.data.Report.componentWellGroups.insert(-1, assemPlotImage)
        assemPlotName = os.path.abspath(f"{core.name}AssemblyTypes{plotNum}.png")
        plotting.plotAssemblyTypes(
            assemBatch,
            assemPlotName,
            maxAssems=MAX_ASSEMS_PER_ASSEM_PLOT,
            showBlockAxMesh=showBlockAxMesh,
            hot=False,
        )

    # Create radial core map
    if generateFullCoreMap:
        core.growToFullCore(cs)

    counts = {
        assemDesign.name: len(core.getChildrenOfType(assemDesign.name)) for assemDesign in r.blueprints.assemDesigns
    }
    # assemDesigns.keys is ordered based on input, assemOrder only contains types that are in the core
    assemOrder = [aType for aType in r.blueprints.assemDesigns.keys() if counts[aType] > 0]
    data = [assemOrder.index(a.p.type) for a in core]
    labels = [r.blueprints.assemDesigns[a.p.type].specifier for a in core]
    legendMap = [
        (
            ai,
            assemDesign.specifier,
            "{} ({})".format(assemDesign.name, counts[assemDesign.name]),
        )
        for ai, assemDesign in enumerate(r.blueprints.assemDesigns)
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

    report.setData("Radial Core Map", os.path.abspath(fName), report.FACE_MAP, report.DESIGN)


COMPONENT_INFO = "Component Information"
