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
from armi.reactor.blocks import Block
from armi.reactor.parameters import ParamLocation
from armi.utils import units


def getFuelPerformanceParameterDefinitions():
    """Return ParameterDefinitionCollections for each appropriate ArmiObject."""
    return {Block: _getFuelPerformanceBlockParams()}


def _getFuelPerformanceBlockParams():
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(default=0.0, location=ParamLocation.AVERAGE) as pb:
        pb.defParam(
            "fuelCladLocked",
            units=units.UNITLESS,
            default=False,
            description="Boolean to indicate if the fuel is locked with the clad."
            " This is used to determine the expansion constraints for the fuel during"
            " thermal and/or burn-up expansion of the fuel and cladding materials.",
        )

        def gasReleaseFraction(self, value):
            if value < 0.0 or value > 1.0:
                raise ValueError(f"Cannot set a gas release fraction of {value} outside of the bounds of [0.0, 1.0]")
            self._p_gasReleaseFraction = value

        pb.defParam(
            "gasReleaseFraction",
            setter=gasReleaseFraction,
            units=units.UNITLESS,
            description="Fraction of generated fission gas that no longer exists in the block.",
            categories=["eq cumulative shift"],
        )

        def bondRemoved(self, value):
            if value < 0.0 or value > 1.0:
                raise ValueError(f"Cannot set a bond removed of {value} outside of the bounds of [0.0, 1.0]")
            self._p_bondRemoved = value

        pb.defParam(
            "bondRemoved",
            setter=bondRemoved,
            units=units.UNITLESS,
            description="Fraction of thermal bond between fuel and clad that has been pushed out.",
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
            units=units.PERCENT,
            description="Total diametral clad strain.",
            categories=["eq cumulative shift"],
        )

        pb.defParam(
            "axialGrowthPct",
            units=units.PERCENT,
            description="Axial growth percentage",
            categories=["eq cumulative shift"],
        )

        pb.defParam(
            "fpPeakFuelTemp",
            units=units.DEGC,
            description="Fuel performance calculated peak fuel temperature.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "fpAveFuelTemp",
            units=units.DEGC,
            description="Fuel performance calculated average fuel temperature.",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "gasPorosity",
            units=units.UNITLESS,
            description="Fraction of fuel volume that is occupied by gas pores",
            default=0.0,
            categories=["eq cumulative shift"],
        )

        pb.defParam(
            "liquidPorosity",
            units=units.UNITLESS,
            description="Fraction of fuel volume that is occupied by liquid filled pores",
            default=0.0,
        )

    return pDefs
