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

"""This module contains rules supporting custom actions taken on the reading of setting inputs"""
import re

from armi import runLog
from armi.physics.neutronics import NEUTRON
from armi.physics.neutronics import NEUTRONGAMMA
from armi.physics.neutronics import ALL

OLD_TAGS = {
    "int": "int",
    "float": "float",
    "tuple": "tuple",
    "boolean": "bool",
    "string": "str",
    "list": "list",
}

# old : new
RENAMES = {
    "hexSideSubdivisions": "numberMeshPerEdge",
    "generateFluxReconImagePlots": "plotReconAxialPower",
    "snapShotDB": "reloadDBName",
    "summarizer": "genReports",
    "asymtoticExtrapolationPowerIters": "asymptoticExtrapolationPowerIters",
    "old1PhaseHTC": "SinglePhaseHTC",
    "1PhaseHTC": "SinglePhaseHTC",
    "movesFile": "explicitRepeatShuffles",
    "shuffleFileName": "explicitRepeatShuffles",
    "intrinsicsourceDecayTime": "intrinsicSourceDecayTime",
    "handlingSocketLength": "HandlingSocketLength",
    "VoidWorth": "voidWorth",
    # start of SASSYS settings rename
    "useFileforGenericUncertainty": "useFileForGenericUncertainty",
    "VoideddopplerCoeff": "voidedDopplerCoeff",
    "structDensityCoeff": "structureDensityCoeff",
    "cladaxialparams": "cladAxialParams",
    "cladaxialParams": "cladAxialParams",
    "cladaxialdistrib": "cladAxialDistrib",
    "cladaxialDistrib": "cladAxialDistrib",
    "structureaxialParams": "structureAxialParams",
    "structureaxialDistrib": "structureAxialDistrib",
    "fuelaxialparams": "fuelAxialParams",
    "fuelaxialParams": "fuelAxialParams",
    "fuelaxialdistrib": "fuelAxialDistrib",
    "fuelaxialDistrib": "fuelAxialDistrib",
    "cladaxialdistrib": "cladaxialDistrib",
    "coolantparams": "coolantParams",
    "coolantdistrib": "coolantDistrib",
    "crdlparams": "crdlParams",
    "crdldistrib": "crdlDistrib",
    "dopplerparams": "dopplerParams",
    "dopplerdistrib": "dopplerDistrib",
    "fuelaxialparams": "fuelaxialParams",
    "fuelaxialdistrib": "fuelaxialDistrib",
    "radialparams": "radialParams",
    "radialdistrib": "radialDistrib",
    "ACRDEX": "acrDex",
    "BCRDEX": "bcrDex",
    "CPfe": "cpFe",
    "CRWorthFile": "crWorthFile",
    "numberofCases": "numberOfCases",
    "numCaseforSassysSensitivity": "numCaseForSassysSensitivity",
    "PowerFlowUncerCases": "powerFlowUncerCases",
    "PowertoFlowRatioList": "powerToFlowRatioList",
    "reCRDL": "reCrdl",
    "sascases": "sasCases",
    "TinFactor": "tinFactor",
    "UTOPreactivity": "utopReactivity",
    "Param10blockstartlocation": "param10BlockStartLocation",
    "Param10Distrib": "param10Distrib",
    "Param10name": "param10Name",
    "Param10nominalvalue": "param10NominalValue",
    "Param10Params": "param10Params",
    "Param1blockstartlocation": "param1BlockStartLocation",
    "Param1Distrib": "param1Distrib",
    "Param1name": "param1Name",
    "Param1nominalvalue": "param1NominalValue",
    "Param1Params": "param1Params",
    "Param2blockstartlocation": "param2BlockStartLocation",
    "Param2Distrib": "param2Distrib",
    "Param2name": "param2Name",
    "Param2nominalvalue": "param2NominalValue",
    "Param2Params": "param2Params",
    "Param3blockstartlocation": "param3BlockStartLocation",
    "Param3Distrib": "param3Distrib",
    "Param3name": "param3Name",
    "Param3nominalvalue": "param3NominalValue",
    "Param3Params": "param3Params",
    "Param4blockstartlocation": "param4BlockStartLocation",
    "Param4Distrib": "param4Distrib",
    "Param4name": "param4Name",
    "Param4nominalvalue": "param4NominalValue",
    "Param4Params": "param4Params",
    "Param5blockstartlocation": "param5BlockStartLocation",
    "Param5Distrib": "param5Distrib",
    "Param5name": "param5Name",
    "Param5nominalvalue": "param5NominalValue",
    "Param5Params": "param5Params",
    "Param6blockstartlocation": "param6BlockStartLocation",
    "Param6Distrib": "param6Distrib",
    "Param6name": "param6Name",
    "Param6nominalvalue": "param6NominalValue",
    "Param6Params": "param6Params",
    "Param7blockstartlocation": "param7BlockStartLocation",
    "Param7Distrib": "param7Distrib",
    "Param7name": "param7Name",
    "Param7nominalvalue": "param7NominalValue",
    "Param7Params": "param7Params",
    "Param8Distrib": "param8Distrib",
    "Param8name": "param8Name",
    "Param8nominalvalue": "param8NominalValue",
    "Param8Params": "param8Params",
    "Param9blockstartlocation": "param9BlockStartLocation",
    "Param9Distrib": "param9Distrib",
    "Param9name": "param9Name",
    "Param9nominalvalue": "param9NominalValue",
    "Param9Params": "param9Params",
    "steadystate.txt": "steadyState.txt",
    "lockrotor.txt": "lockRotor.txt",
    "powerdefect.txt": "powerDefect.txt",
    "control0name": "control0Name",
    "control0location": "control0Location",
    "control0value": "control0Value",
    "control1name": "control1Name",
    "control1location": "control1Location",
    "control1value": "control1Value",
    "control2name": "control2Name",
    "control2location": "control2Location",
    "control2value": "control2Value",
    "SASdensityCoeff": "calcSpatialRxCoeffs",
    # end of sassys setting rename
    "turnOnProfiler": "profile",
    "mc2.path": "mc2v3.path",
    "mc2.minimumFissileFraction": "minimumFissileFraction",
    "DLAYXSFilePath": "mc2DLAYXSFilePath",
    "mc2BucklingConvergence": "bucklingConvergence",
    "inactiveCycles": "mcnpInactiveCycles",
    "mcnpBurnsPerAssem": "mcnpBurnRegionsPerBlock",
    "particlesPerCycle": "mcnpParticlesPerCycle",
    "mcnpCycles": "mcnpTotalCycles",
    "burnTime": "cycleLength",
    "capacityFactor": "availabilityFactor",
    "covarianceFileName": "covariancePath",
    "cinderdat": "mcnpBurnxDepLib",
    "loadCycle": "startCycle",
    "loadNode": "startNode",
}

TARGETED_CONVERSIONS = {}
GENERAL_CONVERSIONS = []


def include_as_rule(*args):
    def decorated_conversion(func):
        def signature_enforcement(cs, name, value):
            updateSettings = func(cs, name, value)
            return updateSettings

        if isinstance(args[0], str):
            for trigger in args:  # should be a setting name
                if trigger in TARGETED_CONVERSIONS:
                    raise Exception(
                        "Only one targeted conversion should be alloted per trigger. "
                        "{} is given at least twice.".format(trigger)
                    )
                TARGETED_CONVERSIONS[trigger] = signature_enforcement
        else:
            GENERAL_CONVERSIONS.append(signature_enforcement)

        return signature_enforcement

    if len(args) == 1 and callable(args[0]):  # general conversion
        return decorated_conversion(args[0])
    elif isinstance(args[0], str):  # setting string names provided
        return decorated_conversion
    else:
        raise ValueError(
            "The setting conversion decorator has been misused. "
            "Input args were {}".format(args)
        )


@include_as_rule
def rename(_cs, name, value):
    if name in RENAMES:
        runLog.warning(
            "Invalid setting {} found. Renaming to {}.".format(name, RENAMES[name])
        )
        name = RENAMES[name]

    return {name: value}


@include_as_rule("verbosity", "branchVerbosity")
def applyVerbosity(cs, name, value):
    # rather than erroring on poor inputs because these used to be integers, just go to the default
    # this isn't a high risk setting that terribly needs protection. 'value' should only be fed in after
    # a valid definition has been supplied so we can look at the existing options.
    if name in cs.settings and value not in cs.settings["verbosity"].options:
        value = cs["verbosity"]

    return {name: value}


@include_as_rule("fpModel")
def oldFourPass(_cs, name, value):
    if value == "oldFourPass":
        runLog.warning(
            'The fpModel setting value of "oldFourPass" is no longer valid, '
            'changing to "infinitelyDilute"'
        )
        value = "infinitelyDilute"

    return {name: value}


@include_as_rule("fuelPerformanceEngine")
def squashNoneFP(_cs, name, value):
    if value == "None":
        value = ""
    return {name: value}


@include_as_rule("assemblyRotationAlgorithm")
def assemblyRotationAlgorithmStringNone(_cs, name, value):
    """Some users experienced a string None being introduced into this setting
    and we want to provide a smooth fix

    See T1345

    """
    if value == "None":
        value = ""

    return {name: value}


@include_as_rule("sensitivityCoefficientsToCompute")
def sensitivityCoefficientsCommonCapitalizationMistake(_cs, name, value):
    newval = []
    # only convert when already converted to list. (Default starts as string!)
    if isinstance(value, list):
        for val in value:
            original = val
            val = re.sub("voidworth", "rxCoreWideCoolantVoidWorth", val)
            val = re.sub("naDensity3", "totalCoolantDensity", val)
            val = re.sub("totalCoolantDensity", "rxCoolantDensityCoeffPerTemp", val)
            if val != original:
                runLog.warning(
                    "invalid sensitivityCoefficientsToCompute setting value `{}` changed to `{}`.".format(
                        original, val
                    )
                )
            newval.append(val)
    else:
        newval = value

    return {name: newval}


@include_as_rule("twrcOption")
def twrcOptionConversion(_cs, name, value):
    """
    Deprecated `twrcOption` is warned about here.
    """
    raise ValueError(
        "The `twrcOption` setting has been removed and cannot be migrated automatically. Please "
        "`sasPlantModelInputFile` settings as appropriate."
    )


@include_as_rule("PumpInertiaPercentChange")
def PumpInertiaPercentChange(_cs, name, value):
    percentChange = float(value) / 100.0
    if abs(percentChange) < 0.001:
        # small values used to be used to trigger the default pump inertia. Now we just set it exactly
        percentChange = 0.0
    newVal = _cs["pumpInertia"] * (1.0 + percentChange)
    runLog.warning(
        "Setting new `pumpInertia` setting to {} based on deprecated `PumpInertiaPercentChange` value"
        " of {}".format(newVal, value)
    )
    return {"pumpInertia": newVal}


@include_as_rule("nodal")
def newDif3dRebusOptions(cs, _name, value):
    """
    Update the `neutronicsKernel` setting to either `YYYY-Nodal` or `YYYY-FD` based on deprecated nodal setting, where
    YYYY refers to either DIF3D or REBUS solver.
    """
    if cs["neutronicsKernel"] not in cs.settings["neutronicsKernel"].options:
        if value == "False":
            nk = cs["neutronicsKernel"] + "-FD"
        else:
            nk = cs["neutronicsKernel"] + "-Nodal"
        runLog.warning(
            "The `neutronicsKernel` option has been set to {} based on the deprecated `nodal` setting."
            "".format(nk)
        )
        return {"neutronicsKernel": nk}
    else:
        return {}


@include_as_rule("saveNeutronicsOutputs")
def resetNeutronicsOutputsToSaveAfterRename(_cs, _name, value):
    """
    Reset the values of 'saveNeutronicsOutputs' setting after it was migrated to 'neutronicsOutputsToSave'.

    Arguments
    ---------
    cs : setting object
        ARMi object containing the default and user-specified settings.

    name : str
        Setting name to be modified by this rule.

    value : str
        Value of the setting identified by name.

    Returns
    -------
    dict : dict
        Updated setting name and or value.
    """
    newName = "neutronicsOutputsToSave"
    if value == "True":
        newValue = ALL
    elif value == "False":
        newValue = ""

    runLog.info(
        "The `neutronicsOutputsToSave` setting has been set to {} based on deprecated "
        "`saveNeutronicsOutputs`.".format(newValue)
    )
    return {newName: newValue}


@include_as_rule("gammaTransportActive")
def removeGammaTransportActive(cs, _name, value):
    """
    Remove 'gammaTransportActive' and set values of 'globalFluxActive' for the same functionality.

    Arguments
    ---------
    cs : setting object
        ARMi object containing the default and user-specified settings.

    name : str
        Setting name to be modified by this rule.

    value : str
        Value of the setting identified by name.
    """
    if value == "True":
        newValue = NEUTRONGAMMA
    elif value == "False":
        newValue = NEUTRON

    cs["globalFluxActive"] = newValue
    runLog.info(
        "The `globalFluxActive` setting has been set to {} based on deprecated "
        "`gammaTransportActive`.".format(newValue)
    )


@include_as_rule("globalFluxActive")
def newGlobalFluxOptions(_cs, name, value):
    """
    Set new values of 'globalFluxActive' setting based on previous setting values.

    Arguments
    ---------
    cs : setting object
        ARMi object containing the default and user-specified settings.

    name : str
        Setting name to be modified by this rule.

    value : str
        Value of the setting identified by name.

    Returns
    -------
    dict : dict
        Updated setting name and or value.
    """
    if value == "True":
        newValue = NEUTRON
    elif value == "False":
        newValue = ""
    else:
        newValue = value

    if value != newValue:
        runLog.info(
            "The `globalFluxActive` setting has been set to {}.".format(newValue)
        )
    return {name: newValue}


@include_as_rule("genXS")
def newGenXSOptions(_cs, name, value):
    """
    Set new values of 'genXS' setting based on previous setting values.

    Arguments
    ---------
    cs : setting object
        ARMi object containing the default and user-specified settings.

    name : str
        Setting name to be modified by this rule.

    value : str
        Value of the setting identified by name.

    Returns
    -------
    dict : dict
        Updated setting name and or value.
    """
    if value == "True":
        newValue = NEUTRON
    elif value == "False":
        newValue = ""
    else:
        newValue = value

    if value != newValue:
        runLog.info("The `genXS` setting has been set to {}.".format(newValue))
    return {name: newValue}


@include_as_rule("existingFIXSRC")
def newFixedSourceOption(cs, _name, value):
    """
    Migrate the deprecated setting 'existingFIXSRC' to 'existingFixedSource'.

    Arguments
    ---------
    cs : setting object
        ARMi object containing the default and user-specified settings.

    name : str
        Setting name to be modified by this rule.

    value : str
        Value of the setting identified by name.

    Returns
    -------
    dict : dict
        Updated setting name and or value.
    """
    newName = "existingFixedSource"
    if value == "True":
        newValue = "FIXSRC"
    else:
        newValue = ""

    if value != newValue:
        runLog.info(
            "The `existingFixedSource` setting has been set to {} based on deprecated "
            "`existingFIXSRC`.".format(newValue)
        )

    return {newName: newValue}


@include_as_rule("boundaries")
def migrateNormalBCSetting(_cs, name, value):
    """
    Boundary setting is migrated from `Normal` to `Extrapolated`.
    """
    newValue = value
    if value == "Normal":
        newValue = "Extrapolated"

    return {name: newValue}


@include_as_rule("asymptoticExtrapolationPowerIters")
def deprecateAsymptoticExtrapolationPowerIters(_cs, _name, _value):
    """
    The setting `asymptoticExtrapolationPowerIters` has been deprecated and replaced by
    three settings to remove confusion and ensure proper use.

    The three new settings are:
        - numOuterIterPriorAsympExtrap
        - asympExtrapOfOverRelaxCalc
        - asympExtrapOfNodalCalc
    """
    runLog.error(
        "The setting `asymptoticExtrapolationPowerIters` has been deprecated and replaced "
        "with `numOuterIterPriorAsympExtrap`, `asympExtrapOfOverRelaxCalc`, "
        "`asympExtrapOfNodalCalc`. Please use these settings for intended behavior."
    )

    raise ValueError(
        "Setting `asymptoticExtrapolationPowerIters` has been deprecated. "
        "See stdout for more details."
    )


@include_as_rule("groupStructure")
def updateXSGroupStructure(cs, name, value):
    from armi.utils import units

    try:
        units.getGroupStructure(value)
        return {name: value}
    except KeyError:
        try:
            newValue = value.upper()
            units.getGroupStructure(newValue)
            runLog.info(
                "Updating the cross section group structure from {} to {}".format(
                    value, newValue
                )
            )
            return {name: newValue}
        except KeyError:
            runLog.info(
                "Unable to automatically convert the `groupStructure` setting of {}. Defaulting to {}".format(
                    value, cs.settings["groupStructure"].default
                )
            )
            return {name: cs.settings["groupStructure"].default}


def _migrateDpa(_cs, name, value):
    newValue = value
    if value == "dpaHT9_33":
        newValue = "dpaHT9_ANL33_TwrBol"
    elif value == "dpa_SS316":
        newValue = "dpaSS316_ANL33_TwrBol"

    return {name: newValue}


@include_as_rule("gridPlateDpaXsSet")
def migrateGridPlateDpa(_cs, name, value):
    """Got more rigorous in dpa XS names."""
    return _migrateDpa(_cs, name, value)


@include_as_rule("dpaXsSet")
def migrateDpaXs(_cs, name, value):
    return _migrateDpa(_cs, name, value)


@include_as_rule
def addToDumpSnapshots(cs, _name, _value):
    from armi import operators

    if cs["runType"] != operators.RunTypes.SNAPSHOTS:
        return {}
    if cs["startCycle"] or cs["startNode"]:
        cccnnn = "{:03d}{:03d}".format(cs["startCycle"], cs["startNode"])
        # Revert default since they are no longer valid settings for snapshots.
        cs.settings["startCycle"].revertToDefault()
        cs.settings["startNode"].revertToDefault()
        cs["dumpSnapshot"].append(cccnnn)
    if not cs["dumpSnapshot"]:
        # Nothing was specified in standard cycle/node or dumpSnapshots.
        # Give old default of 0, 0.
        cs["dumpSnapshot"] = ["000000"]
    return {}
