# Copyright 2020 TerraPower, LLC
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
"""Parameter definitions for thermal hydraulic plugins."""
from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation
from armi.reactor.blocks import Block
from armi.utils import units


def getParameterDefinitions():
    """Return ParameterDefinitionCollections for each appropriate ArmiObject."""
    return {Block: _getBlockParams()}


def _getBlockParams():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        saveToDB=False,
        categories=["thermal hydraulics"],
    ) as pb:

        pb.defParam(
            "pressureLossCoeffs",
            units=units.UNITLESS,
            description="Pressure loss coefficients from form losses outside of bundle region of "
            "assembly, e.g. losses through pin attachment hardware, expansion in inlet "
            "nozzle.",
            default=None,
            categories=[parameters.Category.assignInBlueprints],
        )

    with pDefs.createBuilder(
        default=0.0, location=ParamLocation.AVERAGE, categories=["thermal hydraulics"]
    ) as pb:

        pb.defParam(
            "THhotChannelCladMidwallT",
            units=units.DEGC,
            saveToDB=False,
            description="Midwall (average) clad temperature for the hot channel or hot pin.",
        )

        pb.defParam(
            "THhotChannelHeatTransferCoeff",
            units="W/m^2/K",
            saveToDB=True,
            description="Film heat transfer coefficient for hot channel in the assembly.",
        )

    with pDefs.createBuilder(
        default=None, saveToDB=True, categories=["thermal hydraulics"]
    ) as pb:

        pb.defParam(
            "THhotChannelCladODT",
            units=units.DEGC,
            description="Nominal clad outer diameter temperature of the hot pin",
            categories=["thInterface"],
        )

        pb.defParam(
            "THhotChannelCladIDT",
            units=units.DEGC,
            description="Nominal clad inner diameter temperature of the hot pin",
            categories=["thInterface"],
        )

        pb.defParam(
            "THhotChannelFuelODT",
            units=units.DEGC,
            description="Temperature of the fuel outer diameter",
            categories=["thInterface"],
        )

        pb.defParam(
            "THhotChannelFuelCenterlineT",
            units=units.DEGC,
            description="Nominal hot channel fuel centerline temperature",
            categories=["thInterface"],
        )

        pb.defParam(
            "TH0SigmaCladODT",
            units=units.DEGC,
            description="0-sigma clad outer diameter temperature of the hot pin",
            categories=["thInterface"],
        )

        pb.defParam(
            "TH2SigmaCladODT",
            units=units.DEGC,
            description="2-sigma clad outer diameter temperature of the hot pin",
            categories=["thInterface"],
        )

        pb.defParam(
            "TH3SigmaCladODT",
            units=units.DEGC,
            description="3-sigma clad outer diameter temperature of the hot pin",
            categories=["thInterface"],
        )

        pb.defParam(
            "TH0SigmaCladIDT",
            units=units.DEGC,
            description="0-sigma clad inner diameter temperature of the hot pin",
            categories=["thInterface"],
        )

        pb.defParam(
            "TH2SigmaCladIDT",
            units=units.DEGC,
            description="2-sigma clad inner diameter temperature of the hot pin",
            categories=["thInterface"],
        )

        pb.defParam(
            "TH3SigmaCladIDT",
            units=units.DEGC,
            description="3-sigma clad inner diameter temperature of the hot pin",
            categories=["thInterface"],
        )

        pb.defParam(
            "THdilationPressure",
            units=units.PASCALS,
            description="Dilation pressure",
            categories=["thInterface"],
            default=0.0,
            location=ParamLocation.AVERAGE,
        )

    with pDefs.createBuilder(
        default=0.0, categories=["thInterface"], saveToDB=True
    ) as pb:

        pb.defParam(
            "THTfuelCL",
            units=units.DEGC,
            description="Average temperature of the fuel centerline used for neutronic coupling",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THTfuelOD",
            units=units.DEGC,
            description="Average temperature of the fuel outer diameter used for neutronic coupling",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THaverageCladODT",
            units=units.DEGC,
            description="Block average of the outer clad temperature.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THaverageCladIDT",
            units=units.DEGC,
            description="Block average of the inner clad temperature",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THaverageCladTemp",
            units=units.DEGC,
            description="The nominal average clad temperature in the block, which should be used for neutronic and TH feedback.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THaverageGapTemp",
            units=units.DEGC,
            description="The nominal average gap temperature in the block, which should be used for neutronic and TH feedback.",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
        )

        pb.defParam(
            "THaverageDuctTemp",
            units=units.DEGC,
            description="The nominal average duct temperature in the block, which should be used for neutronic and TH feedback.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THcoolantAverageT",
            units=units.DEGC,
            description="Flow-based average of the inlet and outlet coolant temperatures.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THcoolantInletT",
            units=units.DEGC,
            description="The nominal average bulk coolant inlet temperature into the block.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THcoolantOutletT",
            units=units.DEGC,
            description="Coolant temperature at the outlet of this block",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THcoolantStaticT",
            units=units.DEGC,
            description="Volume-based average coolant temperature, recommended for neutronics",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THdeltaPTotal",
            units=units.PASCALS,
            description="Total pressure difference in a block",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THhotChannelOutletT",
            units=units.DEGC,
            description="Nominal hot channel outlet temperature",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THlocalDTout",
            units=units.DEGC,
            description="Maximum delta-Ts for outlet temperatures of all assemblies",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THlocalDToutFuel",
            units=units.DEGC,
            description="Maximum delta-Ts for outlet temperatures of fuel assemblies",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THmassFlowRate",
            units="kg/s",
            description="Mass flow rate",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "THorificeZone",
            units=units.UNITLESS,
            description="A list of orificing zones corresponding to the assembly list",
            location=ParamLocation.AVERAGE,
        )

    with pDefs.createBuilder(
        default=0.0, categories=["thermal hydraulics", "mongoose"], saveToDB=True
    ) as pb:

        pb.defParam(
            "THcornTemp",
            units=units.DEGC,
            description="Best estimate duct temperature [degC] for assembly corners",
            location=ParamLocation.TOP | ParamLocation.CORNERS,
        )

        pb.defParam(
            "THedgeTemp",
            units=units.DEGC,
            description="Best estimate duct temperature for assembly edges",
            location=ParamLocation.TOP | ParamLocation.EDGES,
        )

        pb.defParam(
            "THhotChannel",
            units=units.UNITLESS,
            description="Hot channel (highest coolant dT) identifier",
            location=ParamLocation.AVERAGE,
        )

    return pDefs
