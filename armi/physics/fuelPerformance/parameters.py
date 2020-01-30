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
"""Parameter definitions for fuel performance plugins."""
from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation
from armi.reactor.blocks import Block
from armi.utils import units


def getFuelPerformanceParameterDefinitions():
    """Return ParameterDefinitionCollections for each appropriate ArmiObject."""
    return {Block: _getFuelPerformanceBlockParams()}


def _getFuelPerformanceBlockParams():
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(default=0.0, location=ParamLocation.AVERAGE) as pb:

        pb.defParam(
            "gasReleaseFraction",
            units="fraction",
            description="Fraction of generated fission gas that no longer exists in the block."
            " Should be between 0 and 1, inclusive.",
            categories=["eq cumulative shift"],
        )

        pb.defParam(
            "bondRemoved",
            units="fraction",
            description="Fraction of thermal bond between fuel and clad that has been pushed out. "
            "Should be between 0 and 1, inclusive.",
            categories=["eq cumulative shift"],
        )

        pb.defParam(
            "cladWastage",
            units=units.MICRONS,
            description="Total cladding wastage from inner and outer surfaces.",
            location=ParamLocation.AVERAGE,
            categories=["eq cumulative shift"],
        )

        pb.defParam(
            "totalCladStrain",
            units="%",
            description="Total diametral clad strain.",
            categories=["eq cumulative shift"],
        )

        pb.defParam(
            "axialGrowthPct",
            units="%",
            description="Axial growth percentage",
            categories=["eq cumulative shift"],
        )

        pb.defParam(
            "fpPeakFuelTemp",
            units="C",
            description="Fuel performance calculated peak fuel temperature.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "fpAveFuelTemp",
            units="C",
            description="Fuel performance calculated average fuel temperature.",
            location=ParamLocation.AVERAGE,
        )

    return pDefs
