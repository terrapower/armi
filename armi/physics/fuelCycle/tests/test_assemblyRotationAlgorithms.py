# Copyright 2022 TerraPower, LLC
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
Tests for tools used to rotate hex assemblies.

Notes
-----
These algorithms are defined in assemblyRotationAlgorithms.py, but they are used in:
``FuelHandler.outage()``.
"""
from unittest import mock
import numpy as np

from armi.physics.fuelCycle import assemblyRotationAlgorithms as rotAlgos
from armi.physics.fuelCycle.hexAssemblyFuelMgmtUtils import (
    getOptimalAssemblyOrientation,
)
from armi.physics.fuelCycle import fuelHandlers
from armi.physics.fuelCycle.settings import CONF_ASSEM_ROTATION_STATIONARY
from armi.physics.fuelCycle.tests.test_fuelHandlers import addSomeDetailAssemblies
from armi.physics.fuelCycle.tests.test_fuelHandlers import FuelHandlerTestHelper
from armi.reactor.flags import Flags


class TestOptimalAssemblyRotation(FuelHandlerTestHelper):
    N_PINS = 271

    def prepBlocks(self, percentBuMaxPinLocation: int, pinPowers: list[float]):
        """Assign basic information to the blocks so we can rotate them.

        Parameters
        ----------
        percentBuMaxPinLocation : int
            ARMI pin number, 1-indexed, for the pin with the highest burnup
        pinPowers : list[float]
            Powers in each pin
        """
        for b in self.assembly.getBlocks(Flags.FUEL):
            b.p.percentBuMax = 5
            # Fake enough behavior so we can make a spatial grid
            b.getPinPitch = mock.Mock(return_value=1.1)
            b.autoCreateSpatialGrids()
            b.p.percentBuMaxPinLocation = percentBuMaxPinLocation
            b.p.linPowByPin = pinPowers


    def test_flatPowerNoRotation(self):
        """If all pin powers are identical, no rotation is suggested."""
        powers = np.ones(self.N_PINS)
        # Identical powers but _some_ non-central "max" burnup pin
        self.prepBlocks(percentBuMaxPinLocation=8, pinPowers=powers)
        rot = getOptimalAssemblyOrientation(self.assembly, self.assembly)
        self.assertEqual(rot, 0)

    def test_maxBurnupAtCenterNoRotation(self):
        """If max burnup pin is at the center, no rotation is suggested."""
        # Fake a higher power towards the center
        powers = np.arange(self.N_PINS)[::-1]
        self.prepBlocks(percentBuMaxPinLocation=1, pinPowers=powers)
        rot = getOptimalAssemblyOrientation(self.assembly, self.assembly)
        self.assertEqual(rot, 0)

    def test_oppositeRotation(self):
        """Test a 180 degree rotation is suggested when the max burnup pin is opposite the lowest power pin.

        Use the second ring of the hexagon because it's easier to write out pin locations
        and check work.
        """
        for startPin, oppositePin in ((2, 5), (3, 6), (4, 7), (5, 2), (6, 3), (7, 4)):
            powers = np.ones(self.N_PINS)
            powers[startPin - 1] *= 2
            powers[oppositePin - 1] = 0
            self.prepBlocks(percentBuMaxPinLocation=startPin, pinPowers=powers)
            rot = getOptimalAssemblyOrientation(self.assembly, self.assembly)
            # 180 degrees is three 60 degree rotations
            self.assertEqual(rot, 3, msg=f"{startPin=} :: {oppositePin=}")


class TestFuelHandlerMgmtTools(FuelHandlerTestHelper):
    def test_buReducingAssemblyRotation(self):
        fh = fuelHandlers.FuelHandler(self.o)
        hist = self.o.getInterface("history")
        newSettings = {CONF_ASSEM_ROTATION_STATIONARY: True}
        self.o.cs = self.o.cs.modified(newSettings=newSettings)
        assem = self.o.r.core.getFirstAssembly(Flags.FUEL)

        # apply dummy pin-level data to allow intelligent rotation
        for b in assem.getBlocks(Flags.FUEL):
            b.initializePinLocations()
            b.p.percentBuMaxPinLocation = 10
            b.p.percentBuMax = 5
            b.p.linPowByPin = list(reversed(range(b.getNumPins())))

        addSomeDetailAssemblies(hist, [assem])
        rotNum = b.getRotationNum()
        rotAlgos.buReducingAssemblyRotation(fh)
        self.assertNotEqual(b.getRotationNum(), rotNum)

    def test_simpleAssemblyRotation(self):
        """Test rotating assemblies 120 degrees."""
        fh = fuelHandlers.FuelHandler(self.o)
        newSettings = {CONF_ASSEM_ROTATION_STATIONARY: True}
        self.o.cs = self.o.cs.modified(newSettings=newSettings)
        hist = self.o.getInterface("history")
        assems = hist.o.r.core.getAssemblies(Flags.FUEL)[:5]
        addSomeDetailAssemblies(hist, assems)
        b = self.o.r.core.getFirstBlock(Flags.FUEL)
        rotNum = b.getRotationNum()
        rotAlgos.simpleAssemblyRotation(fh)
        rotAlgos.simpleAssemblyRotation(fh)
        self.assertEqual(b.getRotationNum(), rotNum + 2)
