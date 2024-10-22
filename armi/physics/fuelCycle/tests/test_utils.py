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

import numpy as np

from armi.reactor.blocks import Block
from armi.reactor.components import Circle
from armi.reactor.flags import Flags
from armi.reactor.grids import IndexLocation
from armi.physics.fuelCycle import utils


class FuelCycleUtilsTests(TestCase):
    """Tests for geometry indifferent fuel cycle routines."""

    N_PINS = 271

    def setUp(self):
        self.block = Block("test block")
        self.fuel = Circle(
            "test pin",
            material="UO2",
            Tinput=20,
            Thot=20,
            mult=self.N_PINS,
            id=0.0,
            od=1.0,
        )
        self.block.add(self.fuel)
        # Force no fuel flags
        self.fuel.p.flags = Flags.PIN

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

    def test_assemblyHasPinPower(self):
        """Test the ability to check if an assembly has fuel pin powers."""
        fakeAssem = [self.block]
        # No fuel blocks, no pin power on blocks => no pin powers
        self.assertFalse(utils.assemblyHasFuelPinBurnup(fakeAssem))

        # Yes fuel blocks, no pin power on blocks => no pin powers
        self.block.p.flags |= Flags.FUEL
        self.assertFalse(utils.assemblyHasFuelPinPowers(fakeAssem))

        # Yes fuel blocks, yes pin power on blocks => yes pin powers
        self.block.p.linPowByPin = np.arange(self.N_PINS, dtype=float)
        self.assertTrue(utils.assemblyHasFuelPinPowers(fakeAssem))

        # Yes fuel blocks, yes pin power assigned but all zeros => no pin powers
        self.block.p.linPowByPin = np.zeros(self.N_PINS, dtype=float)
        self.assertFalse(utils.assemblyHasFuelPinPowers(fakeAssem))
