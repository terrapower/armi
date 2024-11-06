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

from unittest import TestCase

import numpy as np

from armi.reactor.blocks import Block
from armi.reactor.components import Circle
from armi.reactor.flags import Flags
from armi.reactor.grids import IndexLocation, MultiIndexLocation
from armi.physics.fuelCycle import utils


class FuelCycleUtilsTests(TestCase):
    """Tests for geometry indifferent fuel cycle routines."""

    N_PINS = 169

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

    def test_maxBurnupLocationFromComponents(self):
        """Test that the ``Component.p.pinPercentBu`` parameter can reveal max burnup location."""
        self.fuel.spatialLocator = MultiIndexLocation(None)
        locations = []
        for i in range(self.N_PINS):
            loc = IndexLocation(i, 0, 0, None)
            self.fuel.spatialLocator.append(loc)
            locations.append(loc)
        self.fuel.p.pinPercentBu = np.ones(self.N_PINS, dtype=float)

        # Pick an arbitrary index for the pin with the most burnup
        maxBuIndex = self.N_PINS // 3
        self.fuel.p.pinPercentBu[maxBuIndex] *= 2
        expectedLoc = locations[maxBuIndex]
        actual = utils.maxBurnupLocator(self.block)
        self.assertEqual(actual, expectedLoc)

    def test_singleLocatorWithBurnup(self):
        """Test that a single component with burnup can be used to find the highest burnup."""
        freeComp = Circle(
            "free fuel", material="UO2", Tinput=200, Thot=200, id=0, od=1, mult=1
        )
        freeComp.spatialLocator = IndexLocation(2, 4, 0, None)
        freeComp.p.pinPercentBu = [
            0.01,
        ]
        loc = utils.maxBurnupLocator([freeComp])
        self.assertIs(loc, freeComp.spatialLocator)

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

    def test_assemblyHasPinBurnups(self):
        """Test the ability to check if an assembly has fuel pin burnup."""
        fakeAssem = [self.block]
        # No fuel components => no assembly burnups
        self.assertFalse(self.block.getChildrenWithFlags(Flags.FUEL))
        self.assertFalse(utils.assemblyHasFuelPinBurnup(fakeAssem))
        # No fuel with burnup => no assembly burnups
        self.block.p.flags |= Flags.FUEL
        self.fuel.p.flags |= Flags.FUEL
        self.assertFalse(utils.assemblyHasFuelPinBurnup(fakeAssem))
        # Fuel pin has burnup => yes assembly burnup
        self.fuel.p.pinPercentBu = np.arange(self.N_PINS, dtype=float)
        self.assertTrue(utils.assemblyHasFuelPinBurnup(fakeAssem))
        # Fuel pin has empty burnup => no assembly burnup
        self.fuel.p.pinPercentBu = np.zeros(self.N_PINS)
        self.assertFalse(utils.assemblyHasFuelPinBurnup(fakeAssem))
        # Yes burnup but no fuel flags => no assembly burnup
        self.fuel.p.flags ^= Flags.FUEL
        self.assertFalse(self.fuel.hasFlags(Flags.FUEL))
        self.fuel.p.pinPercentBu = np.arange(self.N_PINS, dtype=float)
        self.assertFalse(utils.assemblyHasFuelPinBurnup(fakeAssem))
