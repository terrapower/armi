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
Hex block to RZ geometry conversion
===================================
Often, parts of a reactor model must be transformed to a different geometry in order to
perform a certain type of physics calculation. For example, in some fast reactor lattice
physics calculations, detailed descriptions of control assemblies must be mapped to
equivalent 1-D cylindrical models.

This example shows how a control assembly defined in full hex-pin detail can be
automatically converted to an equivalent 1-D RZ case, including an outer ring of fuel to
drive the case.

This conversion includes rings for control material, gap, cladding (on both sides of each
ring of control material), coolant, duct, and fuel. The color of the plot is proportional
to the mass density.

Given this transformation, a 1-D lattice physics solver can be executed to compute
accurate cross sections.

By automating these kinds of geometry conversions, ARMI allows core designers to maintain
the design in real geometry while still performing appropriate approximations for
efficient analysis.

.. warning::
    This uses :py:mod:`armi.reactor.converters.blockConverters`, which
    currently only works on a constrained set of hex-based geometries. For your systems,
    consider these an example and starting point and build your own converters as
    appropriate.
"""
from armi import configure
from armi.reactor.converters import blockConverters
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors

# configure ARMI
configure(permissive=True)

_o, r = test_reactors.loadTestReactor()

# fully heterogeneous
bFuel = r.core.getBlocks(Flags.FUEL)[0]
bControl = r.core.getBlocks(Flags.CONTROL)[0]
converter = blockConverters.HexComponentsToCylConverter(
    sourceBlock=bControl, driverFuelBlock=bFuel, numExternalRings=1
)
converter.convert()
converter.plotConvertedBlock()

# partially heterogeneous
converter = blockConverters.HexComponentsToCylConverter(
    sourceBlock=bFuel, ductHeterogeneous=True
)
converter.convert()
converter.plotConvertedBlock()
