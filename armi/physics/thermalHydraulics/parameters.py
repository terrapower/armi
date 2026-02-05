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
from armi.reactor.assemblies import Assembly
from armi.reactor.blocks import Block
from armi.reactor.parameters import ParamLocation
from armi.utils import units


def getParameterDefinitions():
    """Return ParameterDefinitionCollections for each appropriate ArmiObject."""
    return {Assembly: _getAssemblyParams(), Block: _getBlockParams()}


def _getAssemblyParams():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(default=0.0, categories=["thermal hydraulics"]) as pb:
        pb.defParam(
            "THmassFlowRate",
            units=f"{units.KG}/{units.SECONDS}",
            description="The nominal assembly flow rate",
            categories=["broadcast"],
            location=ParamLocation.VOLUME_INTEGRATED,
        )

        pb.defParam(
            "THcoolantInletT",
            units=units.DEGC,
            description="Assembly inlet temperature in C (cold temperature)",
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        saveToDB=True,
        categories=["thermal hydraulics"],
    ) as pb:
        pb.defParam(
            "THdeltaPTotal",
            units=units.PASCALS,
            description="Total pressure difference across the assembly",
            categories=["broadcast"],
        )

    return pDefs


def _getBlockParams():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(default=0.0, categories=["thInterface"], saveToDB=True) as pb:
        pb.defParam(
            "THcoolantOutletT",
            units=units.DEGC,
            description="Coolant temperature at the outlet of this block",
            location=ParamLocation.TOP,
        )

        pb.defParam(
            "THmassFlowRate",
            units=f"{units.KG}/{units.SECONDS}",
            description="Mass flow rate",
            location=ParamLocation.VOLUME_INTEGRATED,
        )

        pb.defParam(
            "THcoolantInletT",
            units=units.DEGC,
            description="The nominal average bulk coolant inlet temperature into the block.",
            location=ParamLocation.BOTTOM,
        )

        pb.defParam(
            "THdeltaPTotal",
            units=units.PASCALS,
            description="Total pressure difference in a block",
            location=ParamLocation.AVERAGE,
        )

    with pDefs.createBuilder(default=None, categories=["thermal hydraulics", "mongoose"], saveToDB=True) as pb:
        pb.defParam(
            "THcornTemp",
            units=units.DEGC,
            description="Mid-wall duct temperature for assembly corners",
            location=ParamLocation.BOTTOM | ParamLocation.CORNERS,
        )

        pb.defParam(
            "THedgeTemp",
            units=units.DEGC,
            description="Mid-wall duct temperature for assembly edges",
            location=ParamLocation.BOTTOM | ParamLocation.EDGES,
        )

    return pDefs
