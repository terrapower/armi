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

"""Parameter definitions for Blocks."""

import numpy

import six

from armi import runLog
from armi.nucDirectory import nuclideBases
from armi.physics.neutronics import crossSectionGroupManager
from armi.reactor.flags import Flags  # non-standard import to avoid name conflict below
from armi.utils import units
from armi.utils.units import ASCII_LETTER_A

from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation, Parameter, NoDefault


def getBlockParameterDefinitions():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(location=ParamLocation.CENTROID) as pb:

        pb.defParam(
            "orientation",
            units="degrees",
            description=(
                "Triple representing rotations counterclockwise around each spatial axis. For example, "
                "a hex assembly rotated by 1/6th has orientation (0,0,60.0)"
            ),
            default=None,
        )

        pb.defParam(
            "pinLocation",
            description="Location of fuel pins",
            units=None,
            saveToDB=False,
            default=None,
        )

        def detailedNDens(self, value):
            """Ensures that data is stored in an numpy array to save memory/space."""
            if value is None or isinstance(value, numpy.ndarray):
                self._p_detailedNDens = value
            else:
                self._p_detailedNDens = numpy.array(value)

        pb.defParam(
            "detailedNDens",
            setter=detailedNDens,
            units="atoms/bn-cm",
            description=(
                "High-fidelity number density vector with up to thousands of nuclides. "
                "Used in high-fi depletion runs where low-fi depletion may also be occurring. "
                "This param keeps the hi-fi and low-fi depletion values from interfering. "
                "See core.p.detailedNucKeys for keys. "
                # could move to external physic plugin
            ),
            location=ParamLocation.AVERAGE,
            saveToDB=False,
            default=None,
        )

    with pDefs.createBuilder(
        default=0.0, location=ParamLocation.AVERAGE, categories=["depletion"]
    ) as pb:

        pb.defParam(
            "burnupMWdPerKg",
            units="MWd/kg",
            description="Burnup in MWd/kg of initial heavy metal",
            categories=["cumulative"],
        )

        pb.defParam(
            "fissileFraction",
            units=None,
            description="Ratio of fissile mass to heavy metal mass at block-level",
        )

        pb.defParam(
            "molesHmBOL",
            units="mole",
            description="Total number of atoms of heavy metal at BOL assuming a full assembly",
            default=None,
        )

        pb.defParam(
            "massHmBOL",
            units="grams",
            description="Mass of heavy metal at BOL",
            default=None,
        )

        pb.defParam(
            "molesHmBOLByPin",
            units="mole",
            description="Total number of atoms of heavy metal at BOL",
            default=None,
            saveToDB=False,
        )

        pb.defParam(
            "molesHmNow",
            units="mole",
            description="Total number of atoms of heavy metal",
        )

        pb.defParam(
            "newDPA",
            units="dpa",
            description="Dose in DPA accrued during the current time step",
        )

        pb.defParam(
            "percentBu",
            units="%FIMA",
            description="Percentage of the initial heavy metal atoms that have been fissioned",
            categories=["cumulative"],
        )

        pb.defParam(
            "percentBuByPin",
            units="%FIMA",
            description="Percent burnup of the initial heavy metal atoms that have been fissioned for each pin",
            default=None,
            saveToDB=False,
        )

        pb.defParam(
            "percentBuMax",
            units="%FIMA",
            description="Maximum percentage in a single pin of the initial heavy metal "
            "atoms that have been fissioned",
        )

        pb.defParam(
            "percentBuMaxPinLocation",
            units="int",
            description="Peak burnup pin location",
        )

        pb.defParam(
            "percentBuMin",
            units="%FIMA",
            description="Minimum percentage of the initial heavy metal atoms that have been fissioned",
        )

        pb.defParam(
            "residence",
            units="EFP days",
            description="Duration that a block has been in the core at full power.",
            categories=["cumulative"],
        )

    pDefs.add(
        Parameter(
            name="depletionMatrix",
            units="N/A",
            description="Full BurnMatrix objects containing transmutation and decay info about this block.",
            location=ParamLocation.AVERAGE,
            saveToDB=False,
            default=None,
            setter=NoDefault,
            categories=set(),
        )
    )

    pDefs.add(
        Parameter(
            name="cycleAverageBurnMatrix",
            units="N/A",
            description="Integrated burn matrix mapping this block from its BOC to EOC number densities.",
            location=ParamLocation.AVERAGE,
            saveToDB=False,
            default=None,
            setter=NoDefault,
            categories=set(),
        )
    )

    with pDefs.createBuilder(default=0.0, location=ParamLocation.AVERAGE) as pb:

        pb.defParam("bu", units="", description="?")

        def buGroup(self, buGroupChar):  # pylint: disable=method-hidden
            if isinstance(buGroupChar, (int, float)):
                intValue = int(buGroupChar)
                runLog.warning(
                    "Attempting to set `b.p.buGroup` to int value ({}). Possibly loading from old database".format(
                        buGroupChar
                    ),
                    single=True,
                    label="bu group as int " + str(intValue),
                )
                self.buGroupNum = intValue
                return
            elif not isinstance(buGroupChar, six.string_types):
                raise Exception(
                    "Wrong type for buGroupChar {}: {}".format(
                        buGroupChar, type(buGroupChar)
                    )
                )

            buGroupNum = ord(buGroupChar) - ASCII_LETTER_A
            self._p_buGroup = (
                buGroupChar  # pylint: disable=attribute-defined-outside-init
            )
            self._p_buGroupNum = (
                buGroupNum  # pylint: disable=attribute-defined-outside-init
            )
            buGroupNumDef = parameters.ALL_DEFINITIONS["buGroupNum"]
            buGroupNumDef.assigned = parameters.SINCE_ANYTHING

        pb.defParam(
            "buGroup",
            units=units.NOT_APPLICABLE,
            description="The burnup group letter of this block",
            default="A",
            setter=buGroup,
        )

        def buGroupNum(self, buGroupNum):  # pylint: disable=method-hidden
            if buGroupNum > 26:
                raise RuntimeError(
                    "Invalid bu group number ({}): too many groups. 26 is the max.".format(
                        buGroupNum
                    )
                )
            self._p_buGroupNum = (
                buGroupNum  # pylint: disable=attribute-defined-outside-init
            )
            self._p_buGroup = chr(
                buGroupNum + ASCII_LETTER_A
            )  # pylint: disable=attribute-defined-outside-init
            buGroupDef = parameters.ALL_DEFINITIONS["buGroup"]
            buGroupDef.assigned = parameters.SINCE_ANYTHING

        pb.defParam(
            "buGroupNum",
            units=units.NOT_APPLICABLE,
            description="An integer representation of the burnup group, linked to buGroup.",
            default=0,
            setter=buGroupNum,
        )

        pb.defParam(
            "buRate",
            units="%FIMA/day",
            # This is very related to power, but normalized to %FIMA.
            description=(
                "Current rate of burnup accumulation. Useful for estimating times when "
                "burnup limits may be exceeded."
            ),
        )

        pb.defParam(
            "detailedDpa",
            units="dpa",
            description="displacements per atom",
            categories=["cumulative", "detailedAxialExpansion", "depletion"],
        )

        pb.defParam(
            "detailedDpaPeak",
            units="dpa",
            description="displacements per atom with peaking factor",
            categories=["cumulative", "detailedAxialExpansion", "depletion"],
        )

        pb.defParam(
            "detailedDpaRate",
            units="dpa/s",
            description="Current time derivative of average detailed DPA",
            categories=["detailedAxialExpansion", "depletion"],
        )

        pb.defParam(
            "displacementX",
            units="m",
            description="Assembly displacement in the x direction",
        )

        pb.defParam(
            "displacementY",
            units="m",
            description="Assembly displacement in the y direction",
        )

        pb.defParam(
            "powerRx", units="W/cm$^3$", description="?", location=ParamLocation.AVERAGE
        )

        pb.defParam(
            "dpaRx", units="dpa/s", description="?", location=ParamLocation.AVERAGE
        )

        pb.defParam(
            "heliumInB4C",
            units="He/s/cm$^3$",
            description="?",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "timeToLimit",
            units="days",
            description="Time unit block violates its burnup limit.",
        )

        pb.defParam(
            "zbottom",
            units="cm",
            description="Axial position of the bottom of this block",
            categories=[parameters.Category.retainOnReplacement],
        )

        pb.defParam(
            "ztop",
            units="cm",
            description="Axial position of the top of this block",
            categories=[parameters.Category.retainOnReplacement],
        )

        pb.defParam("baseBu", units="?", description="?", saveToDB=False)

        pb.defParam("basePBu", units="?", description="?", saveToDB=False)

        pb.defParam("hydDiam", units="?", description="?", saveToDB=False)

        pb.defParam(
            "nHMAtBOL",
            units="atoms/bn-cm.",
            description="Ndens of heavy metal at BOL",
            saveToDB=False,
        )

        pb.defParam(
            "z",
            units="cm",
            description="Center axial dimension of this block",
            categories=[parameters.Category.retainOnReplacement],
        )

        pb.defParam(
            "pinPeakingStdDev",
            units="None",
            description="Standard deviation of the pin peaking factors for the block",
        )

    with pDefs.createBuilder() as pb:

        pb.defParam(
            "topIndex",
            units="",
            description="the axial block index within its parent assembly (0 is bottom block)",
            default=0,
            saveToDB=True,
            categories=[parameters.Category.retainOnReplacement],
        )

        pb.defParam(
            "eqRegion",
            units="",
            description="Equilibrium shuffling region. Corresponds to how many full cycles fuel here has gone through.",
            default=-1,
        )

        pb.defParam(
            "eqCascade",
            units="",
            description="Cascade number in repetitive equilibrium shuffling fuel management.",
            default=-1,
        )

        pb.defParam("id", units="?", description="?", default=None)

        pb.defParam(
            "height",
            units="cm",
            description="the block height",
            default=None,
            categories=[parameters.Category.retainOnReplacement],
        )

        def xsType(self, value):  # pylint: disable=method-hidden
            self._p_xsType = value  # pylint: disable=attribute-defined-outside-init
            self._p_xsTypeNum = crossSectionGroupManager.getXSTypeNumberFromLabel(
                value
            )  # pylint: disable=attribute-defined-outside-init
            xsTypeNumDef = parameters.ALL_DEFINITIONS["xsTypeNum"]
            xsTypeNumDef.assigned = parameters.SINCE_ANYTHING

        pb.defParam(
            "xsType",
            units=units.NOT_APPLICABLE,
            description="The xs group letter of this block",
            default="A",
            setter=xsType,
        )

        def xsTypeNum(self, value):  # pylint: disable=method-hidden
            self._p_xsTypeNum = value  # pylint: disable=attribute-defined-outside-init
            self._p_xsType = crossSectionGroupManager.getXSTypeLabelFromNumber(
                value
            )  # pylint: disable=attribute-defined-outside-init
            xsTypeDef = parameters.ALL_DEFINITIONS["xsType"]
            xsTypeDef.assigned = parameters.SINCE_ANYTHING

        pb.defParam(
            "xsTypeNum",
            units=units.NOT_APPLICABLE,
            description="An integer representation of the cross section type, linked to xsType.",
            default=65,  # NOTE: buGroupNum actually starts at 0
            setter=xsTypeNum,
        )

        pb.defParam(
            "type",
            units="N/A",
            description="string name of the input block",
            default="defaultType",
            saveToDB=True,
        )

        pb.defParam(
            "regName",
            units="?",
            description="Set by Assembly in writeNIP30 once the region has been placed",
            default=False,
            saveToDB=False,
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        categories=["reactivity coefficients"],
    ) as pb:

        pb.defParam(
            "VoideddopplerWorth",
            units="dk/kk' K**(n-1)",
            description="Distributed Voided Doppler constant.",
        )

        pb.defParam(
            "dopplerWorth",
            units="dk/kk' * K^(n-1)",
            description="Distributed Doppler constant.",
        )

        pb.defParam(
            "distortWorth",
            units="pcm/cm^3",
            description="Distortion reactivity distribution",
            default=None,
        )

        pb.defParam(
            "fuelWorth",
            units="dk/kk'-kg",
            description="Reactivity worth of fuel material per unit mass",
        )

        pb.defParam(
            "fuelWorthDollarsPerKg",
            units="$/kg",
            description="Reactivity worth of fuel material per unit mass",
        )

        pb.defParam("fuelWorthPT", units="pcm/%/cm^3", description="Fuel reactivity")

        pb.defParam(
            "structWorthPT", units="pcm/%/cm^3", description="Structure reactivity"
        )

        pb.defParam(
            "radExpWorthPT",
            units="pcm/%/cm^3",
            description="Radial swelling reactivity",
        )

        pb.defParam("coolWorthPT", units="pcm/%/cm^3", description="Coolant reactivity")

        pb.defParam(
            "coolFlowingWorthPT",
            units="pcm/%/cm^3",
            description="Flowing coolant reactivity",
        )

        pb.defParam(
            "axExpWorthPT", units="pcm/%/cm^3", description="Axial swelling reactivity"
        )

        pb.defParam(
            "coolantWorth",
            units="dk/kk'-kg",
            description="Reactivity worth of coolant material per unit mass",
        )

        pb.defParam(
            "coolantWorthDollarsPerKg",
            units="$/kg",
            description="Reactivity worth of coolant material per unit mass",
        )

        pb.defParam(
            "cladWorth",
            units="dk/kk'-kg",
            description="Reactivity worth of clad material per unit mass",
        )

        pb.defParam(
            "cladWorthDollarsPerKg",
            units="$/kg",
            description="Reactivity worth of clad material per unit mass",
        )

        pb.defParam(
            "structureWorth",
            units="dk/kk'-kg",
            description="Reactivity worth of structure material per unit mass",
        )

        pb.defParam(
            "structureWorthDollarsPerKg",
            units="$/kg",
            description="Reactivity worth of structure material (non-clad and non-wire wrap material) per unit mass",
        )

        pb.defParam(
            "rxAxialCentsPerK",
            units="cents/K",
            description="Axial temperature reactivity coefficient",
        )

        pb.defParam(
            "rxAxialCentsPerPow",
            units="cents/K",
            description="Axial power reactivity coefficient",
        )

        pb.defParam(
            "rxCoolantCentsPerK",
            units="cents/K",
            description="Coolant temperature reactivity coefficient",
        )

        pb.defParam(
            "rxCoolantCentsPerPow",
            units="cents/K",
            description="Coolant power reactivity coefficient",
        )

        pb.defParam(
            "rxDopplerCentsPerK",
            units="cents/K",
            description="Doppler temperature reactivity coefficient",
        )

        pb.defParam(
            "rxDopplerCentsPerPow",
            units="cents/K",
            description="Doppler power reactivity coefficient",
        )

        pb.defParam(
            "rxFuelCentsPerK",
            units="cents/K",
            description="Fuel temperature reactivity coefficient",
        )

        pb.defParam(
            "rxFuelCentsPerPow",
            units="cents/K",
            description="Fuel power reactivity coefficient",
        )

        pb.defParam(
            "rxNetCentsPerK",
            units="cents/K",
            description="Net temperature reactivity coefficient",
        )

        pb.defParam(
            "rxNetCentsPerPow",
            units="cents/K",
            description="Net power reactivity coefficient",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "rxNetPosNeg",
            units="cents/K",
            description="Net temperature reactivity coefficient: positive or negative",
        )

        pb.defParam(
            "rxNetPosNegPow",
            units="cents/K",
            description="Net power reactivity coefficient: positive or negative",
        )

        pb.defParam(
            "rxRadialCentsPerK",
            units="cents/K",
            description="Radial temperature reactivity coefficient",
        )

        pb.defParam(
            "rxRadialCentsPerPow",
            units="cents/K",
            description="Radial power reactivity coefficient",
        )

        pb.defParam(
            "rxStructCentsPerK",
            units="cents/K",
            description="Structure temperature reactivity coefficient",
        )

        pb.defParam(
            "rxStructCentsPerPow",
            units="cents/K",
            description="Structure power reactivity coefficient",
        )

        pb.defParam(
            "rxVoidedDopplerCentsPerK",
            units="cents/K",
            description="Voided Doppler temperature reactivity coefficient",
        )

        pb.defParam(
            "rxVoidedDopplerCentsPerPow",
            units="cents/K",
            description="Voided Doppler power reactivity coefficient",
        )

        pb.defParam(
            "virdentGr",
            units="pcm/%/cm^3",
            description="Radial surface leakage reactivity",
        )

        pb.defParam(
            "virdentGz",
            units="pcm/%/cm^3",
            description="Axial surface leakage reactivity",
        )

        pb.defParam(
            "virdentLr",
            units="pcm/%/cm^3",
            description="Radial volume leakage reactivity",
        )

        pb.defParam(
            "virdentLz",
            units="pcm/%/cm^3",
            description="Axial volume leakage reactivity",
        )

        pb.defParam(
            "assemPeakStd", units="pcm/%/cm^3", description="Spectral reactivity"
        )

        pb.defParam("virdentS", units="pcm/%/cm^3", description="Spectral reactivity")

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        categories=[
            "reactivity coefficients",
            "spatially dependent",
            "mass normalized",
        ],
    ) as pb:

        # FUEL COEFFICIENTS
        pb.defParam(
            "rxFuelDensityCoeffPerMass",
            units="dk/kk'-kg",
            description="Fuel Density Coefficient",
        )

        pb.defParam(
            "rxFuelDopplerConstant",
            units="dk/kk' K**(n-1)",
            description="Fuel Doppler Constant",
        )

        pb.defParam(
            "rxFuelVoidedDopplerConstant",
            units="dk/kk' K**(n-1)",
            description="Fuel Voided-Coolant Constant",
        )

        pb.defParam(
            "rxFuelTemperatureCoeffPerMass",
            units="dk/kk'-kg",
            description="Fuel Temperature Coefficient",
        )

        pb.defParam(
            "rxFuelVoidedTemperatureCoeffPerMass",
            units="dk/kk'-kg",
            description="Fuel Voided-Coolant Temperature Coefficient",
        )

        # CLAD COEFFICIENTS
        pb.defParam(
            "rxCladDensityCoeffPerMass",
            units="dk/kk'-kg",
            description="Clad Density Coefficient",
        )

        pb.defParam(
            "rxCladDopplerConstant",
            units="dk/kk' K**(n-1)",
            description="Clad Doppler Constant",
        )

        pb.defParam(
            "rxCladTemperatureCoeffPerMass",
            units="dk/kk'-kg",
            description="Clad Temperature Coefficient",
        )

        # STRUCTURE COEFFICIENTS
        pb.defParam(
            "rxStructureDensityCoeffPerMass",
            units="dk/kk'-kg",
            description="Structure Density Coefficient",
        )

        pb.defParam(
            "rxStructureDopplerConstant",
            units="dk/kk' K**(n-1)",
            description="Structure Doppler Constant",
        )

        pb.defParam(
            "rxStructureTemperatureCoeffPerMass",
            units="dk/kk'-kg",
            description="Structure Temperature Coefficient",
        )

        # COOLANT COEFFICIENTS
        pb.defParam(
            "rxCoolantDensityCoeffPerMass",
            units="dk/kk'-kg",
            description="Coolant Density Coefficient",
        )

        pb.defParam(
            "rxCoolantTemperatureCoeffPerMass",
            units="dk/kk'-kg",
            description="Coolant Temperature Coefficient",
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        categories=[
            "reactivity coefficients",
            "spatially dependent",
            "temperature normalized",
        ],
    ) as pb:

        # FUEL COEFFICIENTS
        pb.defParam(
            "rxFuelDensityCoeffPerTemp",
            units="dk/kk'-K",
            description="Fuel Density Coefficient",
        )

        pb.defParam(
            "rxFuelDopplerCoeffPerTemp",
            units="dk/kk'-K",
            description="Fuel Doppler Coefficient",
        )

        pb.defParam(
            "rxFuelVoidedDopplerCoeffPerTemp",
            units="dk/kk'-K",
            description="Fuel Voided-Coolant Doppler Coefficient",
        )

        pb.defParam(
            "rxFuelTemperatureCoeffPerTemp",
            units="dk/kk'-K",
            description="Fuel Temperature Coefficient",
        )

        pb.defParam(
            "rxFuelVoidedTemperatureCoeffPerTemp",
            units="dk/kk'-K",
            description="Fuel Voided-Coolant Temperature Coefficient",
        )

        # CLAD COEFFICIENTS
        pb.defParam(
            "rxCladDensityCoeffPerTemp",
            units="dk/kk'-K",
            description="Clad Density Coefficient",
        )

        pb.defParam(
            "rxCladDopplerCoeffPerTemp",
            units="dk/kk'-K",
            description="Clad Doppler Coefficient",
        )

        pb.defParam(
            "rxCladTemperatureCoeffPerTemp",
            units="dk/kk'-K",
            description="Clad Temperature Coefficient",
        )

        # STRUCTURE COEFFICIENTS
        pb.defParam(
            "rxStructureDensityCoeffPerTemp",
            units="dk/kk'-K",
            description="Structure Density Coefficient",
        )

        pb.defParam(
            "rxStructureDopplerCoeffPerTemp",
            units="dk/kk'-K",
            description="Structure Doppler Coefficient",
        )

        pb.defParam(
            "rxStructureTemperatureCoeffPerTemp",
            units="dk/kk'-K",
            description="Structure Temperature Coefficient",
        )

        # COOLANT COEFFICIENTS
        pb.defParam(
            "rxCoolantDensityCoeffPerTemp",
            units="dk/kk'-K",
            description="Coolant Density Coefficient",
        )

        pb.defParam(
            "rxCoolantTemperatureCoeffPerTemp",
            units="dk/kk'-K",
            description="Coolant Temperature Coefficient",
        )

    with pDefs.createBuilder(default=0.0) as pb:

        pb.defParam(
            "VirDenTerr",
            units="%",
            description="VirDenT error",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "assemNum",
            units="None",
            description="Index that refers, nominally, to the assemNum parameter of "
            "the containing Assembly object. This is stored on the Block to aid in "
            "visualizing shuffle patterns and the like, and should not be used within "
            "the code. These are not guaranteed to be consistent with the containing "
            "Assembly, so they should not be used as a reliable means to reconstruct "
            "the model.",
            categories=[parameters.Category.retainOnReplacement],
        )

        pb.defParam(
            "avgFuelTemp", units="?", description="?", location=ParamLocation.AVERAGE
        )

        pb.defParam(
            "avgTempRef", units="?", description="?", location=ParamLocation.AVERAGE
        )

        pb.defParam(
            "axExtenNodeHeight",
            units="meter",
            description="Axial extension node height",
            location=ParamLocation.AVERAGE,
            default=0.0,
        )

        pb.defParam(
            "blockBeta",
            units="unitless",
            description="Beta in each block",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "blockF",
            units="1/cm^5/s^2",
            description="Adjoint-weighted fission source in each block",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam("bondBOL", units="?", description="?", saveToDB=False)

        pb.defParam(
            "breedRatio",
            units="None",
            description="Breeding ratio",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "fissileDestroyed",
            units="atoms/bn-cm",
            description="Fissile atoms destroyed in last depletion step (not net!)",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "fissileBefore",
            units="atoms/bn-cm",
            description="Fissile atoms at beginning of last depletion step (could be substep!)",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "fissileAfter",
            units="atoms/bn-cm",
            description="Fissile atoms at end of last depletion step (could be substep!)",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam("buLimit", units="%FIMA", description="Burnup limit")

        pb.defParam(
            "cladACCI",
            units=units.MICRONS,
            description="The amount of cladding wastage due to absorber chemical clad interaction",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "convRatio",
            units="None",
            description="Conversion ratio",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "coolRemFrac",
            units="?",
            description="Fractional sodium density change for each block",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "crWastage",
            units=units.MICRONS,
            description="Combines ACCI and clad corrosion for control blocks",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "cyclicNErr",
            units="None",
            description="Relative error of the block number density",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "deltaTclad",
            units="1/cm^5/s^2",
            description="Change in fuel temperature due to 1% rise in power.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "deltaTduct",
            units="1/cm^5/s^2",
            description="Change in fuel temperature due to 1% rise in power.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "deltaTfuel",
            units="1/cm^5/s^2",
            description="Change in fuel temperature due to 1% rise in power.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "dilationElasticPM",
            units="mm",
            description="Combined elastic membrane and bending components of duct dilation",
            location=ParamLocation.AVERAGE,
            categories=["distortion"],
        )

        pb.defParam(
            "dilationElasticT",
            units="mm",
            description="Thermal expansion component of duct dilation",
            location=ParamLocation.AVERAGE,
            categories=["distortion"],
        )

        pb.defParam(
            "dilationElasticTRefueling",
            units="mm",
            description="Thermal expansion component of duct dilation at refueling temperature (180C)",
            location=ParamLocation.AVERAGE,
            categories=["distortion"],
        )

        pb.defParam(
            "dilationCreepIrrad",
            units="mm",
            description="Irradiation creep component of duct dilation",
            location=ParamLocation.AVERAGE,
            categories=["cumulative", "distortion"],
        )

        pb.defParam(
            "dilationSwellingSF",
            units="mm",
            description="Stress-free void swelling component of duct dilation",
            location=ParamLocation.AVERAGE,
            categories=["cumulative", "distortion"],
        )

        pb.defParam(
            "blockAxialSwellingSF",
            units="mm",
            description="Axial stress-free void swelling of block",
            location=ParamLocation.AVERAGE,
            categories=["cumulative", "distortion"],
        )

        pb.defParam(
            "dilationSwellingSE",
            units="mm",
            description="Stress-enhanced swelling component of duct dilation",
            location=ParamLocation.AVERAGE,
            categories=["cumulative", "distortion"],
        )

        pb.defParam(
            "dilationCreepTh1",
            units="mm",
            description="Primary thermal creep component of duct dilation",
            location=ParamLocation.AVERAGE,
            categories=["cumulative", "distortion"],
        )

        pb.defParam(
            "dilationCreepTh2",
            units="mm",
            description="Secondary thermal creep component of duct dilation",
            location=ParamLocation.AVERAGE,
            categories=["cumulative", "distortion"],
        )

        pb.defParam(
            "dilationTotal",
            units="mm",
            description="Total duct dilation",
            location=ParamLocation.AVERAGE,
            categories=["distortion"],
        )

        pb.defParam(
            "dilationRefueling",
            units="mm",
            description="Amount of duct dilation at refueling temperature (180C)",
            location=ParamLocation.AVERAGE,
            categories=["distortion"],
        )

        pb.defParam("displacementMAG", units="?", description="?")

        pb.defParam(
            "heightBOL",
            units="cm",
            description="As-fabricated height of this block (as input). Used in fuel performance. Should be constant.",
            location=ParamLocation.AVERAGE,
            categories=[parameters.Category.retainOnReplacement],
        )

        pb.defParam(
            "intrinsicSource",
            units="?",
            description="Intrinsic neutron source from spontaneous fissions before a decay period",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "intrinsicSourceDecayed",
            units="?",
            description="Intrinsic source from spontaneous fissions after a decay period",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "kgFis",
            units="kg",
            description="Mass of fissile material in block",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "kgHM",
            units="kg",
            description="Mass of heavy metal in block",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "mchan",
            units="None",
            description="SASSYS/DIF3D-K (external) channel index assignment",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "mreg",
            units="None",
            description="SASSYS/DIF3D-K radial region index assignment",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam("nPins", units=None, description="Number of pins")

        pb.defParam(
            "newDPAPeak",
            units="dpa",
            description="The peak DPA accumulated in the last burn step",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "percentBuPeak",
            units="%FIMA",
            description="Peak percentage of the initial heavy metal atoms that have been fissioned",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "powerShapeDelta",
            units="W",
            description="Change in power shape when core temperature rises.",
            location=ParamLocation.VOLUME_INTEGRATED,
        )

        pb.defParam(
            "powerShapePercent",
            units="%",
            description="Percent change in power shape when core temperature rises.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "puFrac",
            units="None",
            description="Current Pu number density relative to HM at BOL",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "smearDensity",
            units="?",
            description="Smear density of fuel pins in this block. Defined as the ratio of fuel area to total space inside cladding.",
            location=ParamLocation.AVERAGE,
        )

    with pDefs.createBuilder(location=ParamLocation.AVERAGE) as pb:

        pb.defParam("distortionReactivity", units="?", description="?")

        pb.defParam("harmonic", units="?", description="?")

        pb.defParam("harmonicAdj", units="?", description="?")

    return pDefs
