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

"""Assembly Parameter Definitions."""

from armi import runLog
from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation
from armi.reactor.parameters.parameterDefinitions import isNumpyArray
from armi.utils import units


def getAssemblyParameterDefinitions():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(location=ParamLocation.CENTROID) as pb:
        pb.defParam(
            "orientation",
            units=units.DEGREES,
            description=(
                "Triple representing rotations counterclockwise around each spatial axis. "
                "For example, a hex assembly rotated by 1/6th has orientation (0, 0, 60.0)"
            ),
            default=None,
        )

        pb.defParam(
            "guideTubeTopElevation",
            units=units.CM,
            description=("Elevation of the top of the guide tube relative to the bottom of the duct."),
            categories=[parameters.Category.assignInBlueprints],
            saveToDB=True,
            default=None,
        )

    with pDefs.createBuilder(location=ParamLocation.AVERAGE, default=0.0) as pb:
        pb.defParam(
            "arealPd",
            units=f"{units.MW}/{units.METERS}^2",
            description="Power in assembly divided by its XY cross-sectional area. Related to PCT.",
        )

        pb.defParam(
            "buLimit",
            units=units.UNITLESS,
            description="buLimit",
            default=parameters.NoDefault,
        )

        pb.defParam(
            "chargeBu",
            units=units.PERCENT_FIMA,
            description="Max block-average burnup in this assembly when it most recently entered "
            "the core. If the assembly was discharged and then re-charged, this value will only "
            "reflect the most recent charge.",
        )

        pb.defParam(
            "chargeCycle",
            units=units.UNITLESS,
            description="Cycle number that this assembly most recently entered the core. If the "
            "assembly was discharged and then re-charged, this value will only reflect the most "
            "recent charge.",
        )

        pb.defParam(
            "chargeFis",
            units=units.KG,
            description="Fissile mass in assembly when it most recently entered the core. If the "
            "assembly was discharged and then re-charged, this value will only reflect the most "
            "recent charge.",
        )

        pb.defParam(
            "chargeTime",
            units=units.YEARS,
            description="Time at which this assembly most recently entered the core. If the "
            "assembly was discharged and then re-charged, this value will only reflect the most "
            "recent charge.",
            default=parameters.NoDefault,
        )

        pb.defParam(
            "multiplicity",
            units=units.UNITLESS,
            description="The number of physical assemblies that the associated object represents. "
            "This is typically 1, but may need to change when the assembly is moved between "
            "containers with different types of symmetry. For instance, if an assembly moves from "
            "a Core with 1/3rd symmetry into a spent-fuel pool with full symmetry, rather than "
            "splitting the assembly into 3, the multiplicity can be set to 3. For now, this is a "
            "bit of a hack to make fuel handling work; multiplicity in the 1/3 core should be 3 to "
            "begin with, in which case this parameter could be used as the primary means of "
            "handling symmetry and fractional domains throughout ARMI. We will probably roll that "
            "out once the dust settles on some of this SFP work. For now, the Core stores "
            "multiplicity as 1 always, since the powerMultiplier to adjust to full-core "
            "quantities.",
            default=1,
        )

        pb.defParam("daysSinceLastMove", units=units.UNITLESS, description="daysSinceLastMove")

        pb.defParam("kInf", units=units.UNITLESS, description="kInf")

        pb.defParam("maxDpaPeak", units=units.DPA, description="maxDpaPeak")

        pb.defParam("maxPercentBu", units=units.PERCENT, description="maxPercentBu")

        pb.defParam("numMoves", units=units.UNITLESS, description="numMoves")

        pb.defParam("timeToLimit", units=units.DAYS, description="timeToLimit", default=1e6)

    with pDefs.createBuilder(location=ParamLocation.AVERAGE) as pb:
        pb.defParam(
            "detailedNDens",
            setter=isNumpyArray("detailedNDens"),
            units=f"atoms/(bn*{units.CM})",
            description=(
                "High-fidelity number density vector with up to thousands of nuclides. "
                "Used in high-fi depletion runs where low-fi depletion may also be occurring. "
                "This param keeps the hi-fi and low-fi depletion values from interfering."
            ),
            saveToDB=True,
            default=None,
        )

        def _enforceNotesRestrictions(self, value):
            """Enforces that notes can only be of type str with max length of 1000."""
            if type(value) is not str:
                runLog.error("Values stored in the `notes` parameter must be strings of less than 1000 characters!")
                raise ValueError
            elif len(value) > 1000:
                runLog.warning(
                    "Strings stored in the `notes` parameter must be less than 1000 characters. "
                    f"Truncating the note starting with {value[0:15]}... at 1000 characters!"
                )
                self._p_notes = value[0:1000]
            else:
                self._p_notes = value

        pb.defParam(
            "notes",
            units=units.UNITLESS,
            description="A string with notes about the assembly, limited to 1000 characters. This "
            "parameter is not meant to store data. Needlessly storing large strings on this "
            "parameter for every assembly is potentially unwise from a memory perspective.",
            saveToDB=True,
            default="",
            setter=_enforceNotesRestrictions,
        )

    with pDefs.createBuilder(location="N/A", default=0.0, categories=["control rods"]) as pb:
        pb.defParam(
            "crCriticalFraction",
            units=units.UNITLESS,
            description=(
                "The insertion fraction when the control rod assembly is in its critical "
                "configuration. Note that the default of -1.0 is a trigger for this value not "
                "being set yet."
            ),
            saveToDB=True,
            default=-1.0,
        )

        pb.defParam(
            "crCurrentElevation",
            units=units.CM,
            description="The current elevation of the bottom of the moveable section of a control rod assembly.",
            categories=[parameters.Category.assignInBlueprints],
            saveToDB=True,
        )

        pb.defParam(
            "crInsertedElevation",
            units=units.CM,
            description=(
                "The elevation of the furthest-most insertion point of a control rod assembly. For "
                "a control rod assembly inserted from the top, this will be the lower tip of the "
                "bottom-most moveable section in the assembly when fully inserted."
            ),
            categories=[parameters.Category.assignInBlueprints],
            saveToDB=True,
        )

        pb.defParam(
            "crRodLength",
            units=units.CM,
            description="length of the control material within the control rod",
            saveToDB=True,
        )

        pb.defParam(
            "crWithdrawnElevation",
            units=units.CM,
            description=(
                "The elevation of the tip of a control rod assembly when it is fully withdrawn. "
                "For a control rod assembly inserted from the top, this will be the lower tip of "
                "the bottom-most moveable section in the assembly when fully withdrawn."
            ),
            categories=[parameters.Category.assignInBlueprints],
            saveToDB=True,
        )

    with pDefs.createBuilder(location=ParamLocation.AVERAGE, default=0.0, categories=["thermal hydraulics"]) as pb:
        pb.defParam(
            "THdeltaPNoGrav",
            units=units.PASCALS,
            description="Total pressure difference minus gravity; it can be thought of as being 'total pressure loss'",
        )

        pb.defParam(
            "THdeltaPPump",
            units=units.PASCALS,
            description="Pumping pressure rise required to pump the given mass flow rate through the rod bundle",
            categories=["broadcast"],
        )

        pb.defParam(
            "THdeltaPTotal",
            units=units.PASCALS,
            description="Total pressure difference across the assembly",
            categories=["broadcast"],
        )

        pb.defParam(
            "THcoolantOutletT",
            units=units.DEGC,
            description="The nominal average bulk coolant outlet temperature out of the block.",
            categories=["broadcast"],
        )

        pb.defParam(
            "THmassFlowRate",
            units=f"{units.KG}/{units.SECONDS}",
            description="The nominal assembly flow rate",
            categories=["broadcast"],
        )

        pb.defParam(
            "THlocalDTout",
            units=units.DEGC,
            description="Maximum delta-Ts for outlet temperatures of all assemblies",
            categories=["broadcast"],
        )

        pb.defParam(
            "THlocalDToutFuel",
            units=units.DEGC,
            description="Maximum delta-Ts for outlet temperatures of fuel assemblies",
            categories=["broadcast"],
        )

        pb.defParam(
            "THorificeZone",
            units=units.UNITLESS,
            description="orifice zone for assembly; should be location specific",
            default=0,  # integer default
        )

    with pDefs.createBuilder() as pb:
        pb.defParam(
            "type",
            units=units.UNITLESS,
            description="The name of the assembly input on the blueprints input",
            default="defaultAssemType",
            saveToDB=True,
        )

        pb.defParam(
            "nozzleType",
            units=units.UNITLESS,
            description="nozzle type for assembly",
            default="Default",
            saveToDB=True,
            categories=[parameters.Category.assignInBlueprints],
        )

    with pDefs.createBuilder(default=0.0) as pb:
        pb.defParam(
            "THcoolantInletT",
            units=units.DEGC,
            description="Assembly inlet temperature in C (cold temperature)",
        )

        pb.defParam("assemNum", units=units.UNITLESS, description="Assembly number")

        pb.defParam(
            "dischargeTime",
            units=units.YEARS,
            description="Time the Assembly was removed from the Reactor.",
        )

        pb.defParam(
            "hotChannelFactors",
            units=units.UNITLESS,
            description="Definition of set of HCFs to be applied to assembly.",
            default="Default",
            saveToDB=True,
            categories=[parameters.Category.assignInBlueprints],
        )

    with pDefs.createBuilder(categories=["radialGeometry"]) as pb:
        pb.defParam(
            "AziMesh",
            units=units.UNITLESS,
            description="Number of points in the Azimuthal mesh.",
            saveToDB=False,
            default=1,
        )

        pb.defParam(
            "RadMesh",
            units=units.UNITLESS,
            description="Number of points in the Radial mesh.",
            saveToDB=False,
            default=1,
        )

        return pDefs
