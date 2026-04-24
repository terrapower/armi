# Copyright 2026 TerraPower, LLC
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
ARMI provides several different Block types for downstream users.

The generic Block is meant to be a base class. And then ARMI provides different geometries that might be interesting or
useful, such as hexagonal or cartesian blocks.

ARMI encourages you to build your own subclass of an ARMI Block type, to simplify your reactor blueprints.
"""

# ruff: noqa: F401
from armi.reactor.blocks.block import PIN_COMPONENTS, Block
from armi.reactor.blocks.cartesianBlock import CartesianBlock
from armi.reactor.blocks.hexBlock import HexBlock
from armi.reactor.blocks.thRZBlock import ThRZBlock
