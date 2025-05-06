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
from armi import runLog
from armi.physics.neutronics import crossSectionGroupManager
from armi.reactor import parameters
from armi.reactor.parameters import NoDefault, Parameter, ParamLocation
from armi.reactor.parameters.parameterDefinitions import isNumpyArray
from armi.utils import units
from armi.utils.units import ASCII_LETTER_A, ASCII_LETTER_Z, ASCII_LETTER_a


def getBlockParameterDefinitions():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(location=ParamLocation.CENTROID) as pb:

        pb.defParam(
            "orientation",
            units=units.DEGREES,
            description=(
                "Triple representing rotations counterclockwise around each spatial axis. For "
                "example, a hex assembly rotated by 1/6th has orientation (0,0,60.0)"
            ),
            default=None,
        )

        pb.defParam(
            "pinLocation",
            description="Location of fuel pins",
            units=units.UNITLESS,
            saveToDB=False,
            default=None,
            location=ParamLocation.CHILDREN,
        )

        pb.defParam(
            "detailedNDens",
            setter=isNumpyArray("detailedNDens"),
            units=f"atoms/(bn*{units.CM})",
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
            units=f"{units.MWD}/{units.KG}",
            description="Burnup in MWd/kg of initial heavy metal",
            categories=["cumulative"],
        )

        pb.defParam(
            "newDPA",
            units=units.DPA,
            description="Dose in DPA accrued during the current time step",
        )

        pb.defParam(
            "percentBu",
            units=units.PERCENT_FIMA,
            description="Percentage of the initial heavy metal atoms that have been fissioned",
            categories=["cumulative"],
        )

        pb.defParam(
            "percentBuByPin",
            units=units.PERCENT_FIMA,
            description="Percent burnup of the initial heavy metal atoms that have been fissioned for each pin",
            default=None,
            saveToDB=False,
            location=ParamLocation.CHILDREN,
        )

        pb.defParam(
            "percentBuMax",
            units=units.PERCENT_FIMA,
            description="Maximum percentage in a single pin of the initial heavy metal "
            "atoms that have been fissioned",
            location=ParamLocation.MAX,
        )

        pb.defParam(
            "residence",
            units=units.DAYS,
            description=(
                "Duration that a block has been in the core multiplied by the fraction "
                "of full power generated in that time."
            ),
            categories=["cumulative"],
        )

    with pDefs.createBuilder(
        default=0.0, location=ParamLocation.VOLUME_INTEGRATED, categories=["depletion"]
    ) as pb:

        pb.defParam(
            "molesHmNow",
            units=f"{units.MOLES}",
            description="Total number of atoms of heavy metal",
        )

        pb.defParam(
            "molesHmBOL",
            units=f"{units.MOLES}",
            description="Total number of atoms of heavy metal at BOL.",
        )

        pb.defParam(
            "massHmBOL",
            units=units.GRAMS,
            description="Mass of heavy metal at BOL",
        )

        pb.defParam(
            "initialB10ComponentVol",
            units=f"{units.CM}^3",
            description=(
                "cc's of un-irradiated, cold B10 containing component "
                "(includes full volume of any components with B10)"
            ),
        )

    pDefs.add(
        Parameter(
            name="depletionMatrix",
            units=units.UNITLESS,
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
            units=units.UNITLESS,
            description="Integrated burn matrix mapping this block from its BOC to EOC number densities.",
            location=ParamLocation.AVERAGE,
            saveToDB=False,
            default=None,
            setter=NoDefault,
            categories=set(),
        )
    )

    with pDefs.createBuilder(default=0.0, location=ParamLocation.AVERAGE) as pb:

        def envGroup(self, envGroupChar):
            if isinstance(envGroupChar, (int, float)):
                intValue = int(envGroupChar)
                runLog.warning(
                    f"Attempting to set `b.p.envGroup` to int value ({envGroupChar})."
                    "Possibly loading from old database",
                    single=True,
                    label="env group as int " + str(intValue),
                )
                self.envGroupNum = intValue
                return
            elif not isinstance(envGroupChar, str):
                raise Exception(
                    f"Wrong type for envGroupChar {envGroupChar}: {type(envGroupChar)}"
                )

            if envGroupChar.islower():
                # if lower case find the distance from lowercase a and add the span of A to Z
                lowerCaseOffset = ASCII_LETTER_Z - ASCII_LETTER_A + 1  # 26
                envGroupNum = ord(envGroupChar) - ASCII_LETTER_a + lowerCaseOffset
            else:
                envGroupNum = ord(envGroupChar) - ASCII_LETTER_A
            self._p_envGroup = envGroupChar
            self._p_envGroupNum = envGroupNum
            envGroupNumDef = parameters.ALL_DEFINITIONS["envGroupNum"]
            envGroupNumDef.assigned = parameters.SINCE_ANYTHING

        pb.defParam(
            "envGroup",
            units=units.UNITLESS,
            description="The environment group letter of this block",
            default="A",
            setter=envGroup,
        )

        def envGroupNum(self, envGroupNum):
            # support capital and lowercase alpha chars (52= 26*2)
            if envGroupNum > 52:
                raise RuntimeError(
                    "Invalid env group number ({}): too many groups. 52 is the max.".format(
                        envGroupNum
                    )
                )
            self._p_envGroupNum = envGroupNum
            lowerCaseOffset = ASCII_LETTER_Z - ASCII_LETTER_A
            if envGroupNum > lowerCaseOffset:
                envGroupNum = envGroupNum - (lowerCaseOffset + 1)
                self._p_envGroup = chr(envGroupNum + ASCII_LETTER_a)
            else:
                self._p_envGroup = chr(envGroupNum + ASCII_LETTER_A)
            envGroupDef = parameters.ALL_DEFINITIONS["envGroup"]
            envGroupDef.assigned = parameters.SINCE_ANYTHING

        pb.defParam(
            "envGroupNum",
            units=units.UNITLESS,
            description="An integer representation of the environment group "
            "(burnup/temperature/etc.). linked to envGroup.",
            default=0,
            setter=envGroupNum,
        )

        pb.defParam(
            "buRate",
            units=f"{units.PERCENT_FIMA}/{units.DAYS}",
            # This is very related to power, but normalized to %FIMA.
            description=(
                "Current rate of burnup accumulation. Useful for estimating times when "
                "burnup limits may be exceeded."
            ),
        )

        pb.defParam(
            "buRatePeak",
            units=f"{units.PERCENT_FIMA}/{units.DAYS}",
            description="Current rate of burnup accumulation at peak location",
            location=ParamLocation.MAX,
        )

        pb.defParam(
            "detailedDpa",
            units=units.DPA,
            description="displacements per atom",
            categories=["cumulative", "detailedAxialExpansion", "depletion"],
        )

        pb.defParam(
            "detailedDpaPeak",
            units=units.DPA,
            description="displacements per atom with peaking factor",
            categories=["cumulative", "detailedAxialExpansion", "depletion"],
            location=ParamLocation.MAX,
        )

        pb.defParam(
            "detailedDpaRate",
            units=f"{units.DPA}/{units.SECONDS}",
            description="Current time derivative of average detailed DPA",
            categories=["detailedAxialExpansion", "depletion"],
        )

        pb.defParam(
            "displacementX",
            units=units.METERS,
            description="Assembly displacement in the x direction",
        )

        pb.defParam(
            "displacementY",
            units=units.METERS,
            description="Assembly displacement in the y direction",
        )

        pb.defParam(
            "heliumInB4C",
            units=f"He/{units.SECONDS}/{units.CM}^3",
            description="Alpha particle production rate in B4C control and shield material.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "powerRx",
            units=f"{units.WATTS}/{units.CM}^3",
            description="Power density of the reactor",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "timeToLimit",
            units=units.DAYS,
            description="Time unit block violates its burnup limit.",
        )

        pb.defParam(
            "zbottom",
            units=units.CM,
            description="Axial position of the bottom of this block",
            categories=[parameters.Category.retainOnReplacement],
        )

        pb.defParam(
            "ztop",
            units=units.CM,
            description="Axial position of the top of this block",
            categories=[parameters.Category.retainOnReplacement],
        )

        pb.defParam(
            "nHMAtBOL",
            units=f"atoms/(bn*{units.CM})",
            description="Ndens of heavy metal at BOL",
            saveToDB=False,
        )

        pb.defParam(
            "z",
            units=units.CM,
            description="Center axial dimension of this block",
            categories=[parameters.Category.retainOnReplacement],
        )

    with pDefs.createBuilder() as pb:
        pb.defParam(
            "axialExpTargetComponent",
            units=units.UNITLESS,
            description=(
                "The name of the target component used for axial expansion and "
                "contraction of solid components."
            ),
            default="",
            saveToDB=True,
        )

        pb.defParam(
            "topIndex",
            units=units.UNITLESS,
            description=(
                "the axial block index within its parent assembly (0 is bottom block). This index with"
                "regard to the mesh of the reference assembly so it does not increase by 1 for each block."
                "It is used to keep the mesh of the assemblies uniform with axial expansion."
                "See setBlockMesh, makeAxialSnapList",
            ),
            default=0,
            saveToDB=True,
            categories=[parameters.Category.retainOnReplacement],
        )

        pb.defParam(
            "eqRegion",
            units=units.UNITLESS,
            description="Equilibrium shuffling region. Corresponds to how many full cycles fuel here has gone through.",
            default=-1,
        )

        pb.defParam(
            "eqCascade",
            units=units.UNITLESS,
            description="Cascade number in repetitive equilibrium shuffling fuel management.",
            default=-1,
        )

        pb.defParam(
            "id",
            units=units.UNITLESS,
            description="Inner diameter of the Block.",
            default=None,
        )

        pb.defParam(
            "height",
            units=units.CM,
            description="the block height",
            default=None,
            categories=[parameters.Category.retainOnReplacement],
        )

        def xsType(self, value):
            self._p_xsType = value
            self._p_xsTypeNum = crossSectionGroupManager.getXSTypeNumberFromLabel(value)
            xsTypeNumDef = parameters.ALL_DEFINITIONS["xsTypeNum"]
            xsTypeNumDef.assigned = parameters.SINCE_ANYTHING

        pb.defParam(
            "xsType",
            units=units.UNITLESS,
            description="The xs group letter of this block",
            default="A",
            setter=xsType,
        )

        def xsTypeNum(self, value):
            self._p_xsTypeNum = value
            self._p_xsType = crossSectionGroupManager.getXSTypeLabelFromNumber(value)
            xsTypeDef = parameters.ALL_DEFINITIONS["xsType"]
            xsTypeDef.assigned = parameters.SINCE_ANYTHING

        pb.defParam(
            "xsTypeNum",
            units=units.UNITLESS,
            description="An integer representation of the cross section type, linked to xsType.",
            default=65,  # NOTE: buGroupNum actually starts at 0
            setter=xsTypeNum,
        )

        pb.defParam(
            "type",
            units=units.UNITLESS,
            description="string name of the input block",
            default="defaultType",
            saveToDB=True,
        )

    with pDefs.createBuilder(default=0.0) as pb:

        pb.defParam(
            "assemNum",
            units=units.UNITLESS,
            description="Index that refers, nominally, to the assemNum parameter of the containing "
            "Assembly object. This is stored on the Block to aid in visualizing shuffle patterns "
            "and the like, and should not be used within the code. These are not guaranteed to be "
            "consistent with the containing Assembly, so they should not be used as a reliable "
            "means to reconstruct the model.",
            categories=[parameters.Category.retainOnReplacement],
        )

        pb.defParam(
            "breedRatio",
            units=units.UNITLESS,
            description="Breeding ratio",
            categories=["detailedAxialExpansion"],
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "fissileDestroyed",
            units=f"atoms/(bn*{units.CM})",
            description="Fissile atoms destroyed in last depletion step (not net!)",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "fissileBefore",
            units=f"atoms/(bn*{units.CM})",
            description="Fissile atoms at beginning of last depletion step (could be substep!)",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "fissileAfter",
            units=f"atoms/(bn*{units.CM})",
            description="Fissile atoms at end of last depletion step (could be substep!)",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam("buLimit", units=units.PERCENT_FIMA, description="Burnup limit")

        pb.defParam(
            "convRatio",
            units=units.UNITLESS,
            description="Conversion ratio",
            categories=["detailedAxialExpansion"],
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "cyclicNErr",
            units=units.UNITLESS,
            description="Relative error of the block number density",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "heightBOL",
            units=units.CM,
            description="As-fabricated height of this block (as input). Used in fuel performance. Should be constant.",
            location=ParamLocation.AVERAGE,
            categories=[parameters.Category.retainOnReplacement],
        )

        pb.defParam(
            "intrinsicSource",
            units=units.UNITLESS,
            description="Intrinsic neutron source from spontaneous fissions before a decay period",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "kgFis",
            units=units.KG,
            description="Mass of fissile material in block",
            location=ParamLocation.VOLUME_INTEGRATED,
        )

        pb.defParam(
            "kgHM",
            units=units.KG,
            description="Mass of heavy metal in block",
            location=ParamLocation.VOLUME_INTEGRATED,
        )

        pb.defParam("nPins", units=units.UNITLESS, description="Number of pins")

        pb.defParam(
            "newDPAPeak",
            units=units.DPA,
            description="The peak DPA accumulated in the last burn step",
            location=ParamLocation.MAX,
        )

        pb.defParam(
            "percentBuPeak",
            units=units.PERCENT_FIMA,
            description="Peak percentage of the initial heavy metal atoms that have been fissioned",
            location=ParamLocation.MAX,
            categories=["cumulative", "eq cumulative shift"],
        )

        pb.defParam(
            "puFrac",
            units=units.UNITLESS,
            description="Current Pu number density relative to HM at BOL",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "smearDensity",
            units=units.UNITLESS,
            description=(
                "Smear density of fuel pins in this block. Defined as the ratio of fuel "
                "area to total space inside cladding."
            ),
            location=ParamLocation.AVERAGE,
        )

    return pDefs
