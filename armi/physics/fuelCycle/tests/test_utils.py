# Copyright 2024 TerraPower, LLC
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

from unittest import TestCase, mock

from armi.reactor.grids import IndexLocation
from armi.reactor.blocks import Block
from armi.physics.fuelCycle import utils

class FuelCycleUtilsTests(TestCase):
    """Tests for geometry indifferent fuel cycle routines."""

    def setUp(self):
        self.block = Block("test block")

    def test_maxBurnupPinLocationBlockParameter(self):
        """Test that the ``Block.p.percentBuMaxPinLocation`` parameter gets the location."""
        # Zero-indexed pin index, pin number is this plus one
        pinLocationIndex = 3
        self.block.p.percentBuMaxPinLocation = pinLocationIndex + 1
        locations = [IndexLocation(i, 0, 0, None) for i in range(pinLocationIndex + 5)]
        self.block.getPinLocations = mock.Mock(return_value=locations)
        expected = locations[pinLocationIndex]
        actual = utils.maxBurnupFuelPinLocation(self.block)
        self.assertIs(actual, expected)
