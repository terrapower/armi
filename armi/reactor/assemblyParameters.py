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

"""
Assembly Parameter Definitions
"""
import numpy

from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation
from armi.utils import units
from armi.reactor.flags import Flags  # non-standard import to avoid name conflict below


def getAssemblyParameterDefinitions():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder() as pb:

        def powerDecay(self, value):
            if value is None or isinstance(value, numpy.ndarray):
                self._p_powerDecay = value
            else:
                self._p_powerDecay = numpy.array(value)

        pb.defParam(
            "powerDecay",
            setter=powerDecay,
            units="W",
            description="List of decay heats at each time step specified in "
            "decayHeatCalcTimesInSeconds setting.",
            saveToDB=True,
            location=ParamLocation.AVERAGE,  # really total
            default=None,
        )

    with pDefs.createBuilder(location=ParamLocation.CENTROID) as pb:

        pb.defParam(
            "orientation",
            units="degrees",
            description=(
                "Triple representing rotations counterclockwise around each spatial axis. "
                "For example, a hex assembly rotated by 1/6th has orientation (0,0,60.0)"
            ),
            default=None,
        )

    with pDefs.createBuilder(location=ParamLocation.AVERAGE, default=0.0) as pb:

        pb.defParam(
            "arealPd",
            units="MW/m^2",
            description="Power in assembly divided by its XY cross-sectional area. Related to PCT.",
        )

        pb.defParam(
            "buLimit", units="", description="buLimit", default=parameters.NoDefault
        )

        pb.defParam(
            "chargeBu",
            units="%FIMA",
            description="Max block-average burnup in this assembly when it entered the core.",
        )

        pb.defParam(
            "chargeCycle",
            units="",
            description="Cycle number that this assembly entered the core.",
        )

        pb.defParam(
            "chargeFis",
            units="kg",
            description="Fissile mass in assembly when it entered the core.",
        )

        pb.defParam(
            "chargeTime",
            units="years",
            description="Time at which this assembly entered the core.",
            default=parameters.NoDefault,
        )

        pb.defParam("daysSinceLastMove", units="", description="daysSinceLastMove")

        pb.defParam("kInf", units="", description="kInf")

        pb.defParam("maxDpaPeak", units="", description="maxDpaPeak")

        pb.defParam("maxPercentBu", units="", description="maxPercentBu")

        pb.defParam("numMoves", units="", description="numMoves")

        pb.defParam("timeToLimit", units="", description="timeToLimit", default=1e6)

    with pDefs.createBuilder(location=ParamLocation.AVERAGE) as pb:

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
                # Could be moved to external physics plugin
            ),
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "assyAxialSwellingSF",
            units="mm",
            description="Assembly axial swelling due to stress-free swelling",
            default=0.0,
        )

        pb.defParam(
            "fuelVent",
            units=None,
            description="Boolean option to turn on/off vented fuel pins in TWR design",
            saveToDB=False,
            default=False,
            categories=[parameters.Category.assignInBlueprints],
        )

    with pDefs.createBuilder(
        location=ParamLocation.AVERAGE, default=0.0, categories=["thermal hydraulics"]
    ) as pb:

        pb.defParam("THdeltaPNoGrav", units="Pa", description="?")

        pb.defParam(
            "THdeltaPPump",
            units="Pa",
            description="Pumping pressure rise required to pump the given mass flow rate through the rod bundle",
            categories=["broadcast"],
        )

        pb.defParam(
            "THdeltaPTotal",
            units="Pa",
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
            units="kg/s",
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
            "THorificeSetting",
            units="Pa/$(kg/s)^2$",
            description="The ratio of pressure drop over mass flow rate squared, through an orifice",
            default=None,
        )

        pb.defParam(
            "THorificeZone",
            units=None,
            description="orifice zone for assembly; should be location specific",
            default=0,  # integer default
        )

    with pDefs.createBuilder(
        location="N/A", default=0.0, categories=["control rods"]
    ) as pb:

        pb.defParam(
            "crCurrentHeight",
            units="cm",
            description="The current height of the bottom of the control material from the 0 point in the reactor model",
        )

        pb.defParam(
            "crEndingHeight",
            units="cm",
            description="The final position of the bottom of the control material when "
            "starting control operations as measured from the 0 point in the reactor model",
        )

        pb.defParam(
            "crRodLength",
            units="cm",
            description="length of the control material within the control rod",
            saveToDB=False,
        )

        pb.defParam(
            "crStartingHeight",
            units="cm",
            description="The initial starting position of the bottom of the control "
            "material when starting control operations as measured from the 0 point in the "
            "reactor model",
        )

    with pDefs.createBuilder() as pb:

        pb.defParam(
            "type",
            units="?",
            description="The name of the assembly input on the blueprints input",
            location="?",
            default="defaultAssemType",
            saveToDB=True,
        )

    with pDefs.createBuilder(default=0.0) as pb:

        pb.defParam("Pos", units="?", description="?", location="?")

        pb.defParam("Ring", units="?", description="?", location="?")

        pb.defParam("THcoolantInletT", units="?", description="?", location="?")

        pb.defParam("assemNum", units="?", description="?", location="?")

        pb.defParam(
            "axExpWorthPT",
            units="pcm/%/cm^3",
            description="Axial swelling reactivity",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "coolFlowingWorthPT",
            units="pcm/%/cm^3",
            description="Flowing coolant reactivity",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "coolWorthPT",
            units="pcm/%/cm^3",
            description="Coolant reactivity",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam("dischargeTime", units="?", description="?", location="?")

        pb.defParam(
            "fuelWorthPT",
            units="pcm/%/cm^3",
            description="Fuel reactivity",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "hotChannelFactors",
            units="None",
            description="Definition of set of HCFs to be applied to assembly.",
            location="?",
            default="Default",
            saveToDB=False,
            categories=[parameters.Category.assignInBlueprints],
        )

        pb.defParam(
            "radExpWorthPT",
            units="pcm/%/cm^3",
            description="Radial swelling reactivity",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "structWorthPT",
            units="pcm/%/cm^3",
            description="Structure reactivity",
            location=ParamLocation.AVERAGE,
        )

    with pDefs.createBuilder(categories=["radialGeometry"]) as pb:

        pb.defParam(
            "AziMesh",
            units="?",
            description="?",
            location="?",
            saveToDB=False,
            default=1,
        )

        pb.defParam(
            "RadMesh",
            units="?",
            description="?",
            location="?",
            saveToDB=False,
            default=1,
        )

        return pDefs
