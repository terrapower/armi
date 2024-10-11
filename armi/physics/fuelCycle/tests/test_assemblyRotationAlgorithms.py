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
import copy
from unittest import mock

import numpy as np

from armi.reactor.assemblies import HexAssembly
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

    @staticmethod
    def prepShuffledAssembly(a: HexAssembly, percentBuMaxPinLocation: int):
        """Prepare the assembly that will be shuffled and rotated."""
        for b in a.getChildrenWithFlags(Flags.FUEL):
            # Fake some maximum burnup
            b.p.percentBuMax = 5
            # Fake enough information to build a spatial grid
            b.getPinPitch = mock.Mock(return_value=1.1)
            b.autoCreateSpatialGrids()
            b.p.percentBuMaxPinLocation = percentBuMaxPinLocation

    @staticmethod
    def prepPreviousAssembly(a: HexAssembly, pinPowers: list[float]):
        """Prep the assembly that existed at the site a shuffled assembly will occupy."""
        for b in a.getChildrenWithFlags(Flags.FUEL):
            # Fake enough information to build a spatial grid
            b.getPinPitch = mock.Mock(return_value=1.1)
            b.autoCreateSpatialGrids()
            b.p.linPowByPin = pinPowers

    def test_flatPowerNoRotation(self):
        """If all pin powers are identical, no rotation is suggested."""
        powers = np.ones(self.N_PINS)
        # Identical powers but _some_ non-central "max" burnup pin
        self.prepShuffledAssembly(self.assembly, percentBuMaxPinLocation=8)
        self.prepPreviousAssembly(self.assembly, powers)
        rot = getOptimalAssemblyOrientation(self.assembly, self.assembly)
        self.assertEqual(rot, 0)

    def test_maxBurnupAtCenterNoRotation(self):
        """If max burnup pin is at the center, no rotation is suggested."""
        # Fake a higher power towards the center
        powers = np.arange(self.N_PINS)[::-1]
        self.prepShuffledAssembly(self.assembly, percentBuMaxPinLocation=1)
        self.prepPreviousAssembly(self.assembly, powers)
        rot = getOptimalAssemblyOrientation(self.assembly, self.assembly)
        self.assertEqual(rot, 0)

    def test_oppositeRotation(self):
        """Test a 180 degree rotation is suggested when the max burnup pin is opposite the lowest power pin.

        Use the second ring of the hexagon because it's easier to write out pin locations
        and check work.

        .. test:: Test the burnup equalizing rotation algorithm.
            :id: T_ARMI_ROTATE_HEX_BURNUP
            :tests: R_ARMI_ROTATE_HEX_BURNUP
            :acceptance_criteria: After rotating a hexagonal assembly, confirm the pin with the highest burnup is
                in the same sector as pin with the lowest power in the high burnup pin's ring.
        """
        shuffledAssembly = self.assembly
        previousAssembly = copy.deepcopy(shuffledAssembly)
        for startPin, oppositePin in ((2, 5), (3, 6), (4, 7), (5, 2), (6, 3), (7, 4)):
            powers = np.ones(self.N_PINS)
            powers[startPin - 1] *= 2
            powers[oppositePin - 1] = 0
            self.prepShuffledAssembly(shuffledAssembly, startPin)
            self.prepPreviousAssembly(previousAssembly, powers)
            rot = getOptimalAssemblyOrientation(shuffledAssembly, previousAssembly)
            # 180 degrees is three 60 degree rotations
            self.assertEqual(rot, 3, msg=f"{startPin=} :: {oppositePin=}")

    def test_noGridOnShuffledBlock(self):
        """Require a spatial grid on the shuffled block."""
        with self.assertRaisesRegex(ValueError, "spatial grid"):
            getOptimalAssemblyOrientation(self.assembly, self.assembly)

    def test_mismatchPinPowersAndLocations(self):
        """Require pin powers and locations to be have the same length."""
        powers = np.arange(self.N_PINS + 1)
        self.prepShuffledAssembly(self.assembly, percentBuMaxPinLocation=4)
        self.prepPreviousAssembly(self.assembly, powers)
        with self.assertRaisesRegex(
            ValueError, "Inconsistent pin powers and number of pins"
        ):
            getOptimalAssemblyOrientation(self.assembly, self.assembly)


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
        # Show that we call the optimal assembly orientation function.
        # This function is tested seperately and more extensively elsewhere.
        with mock.patch(
            "armi.physics.fuelCycle.assemblyRotationAlgorithms.getOptimalAssemblyOrientation",
            return_value=0,
        ) as p:
            rotAlgos.buReducingAssemblyRotation(fh)
        p.assert_called_once_with(assem, assem)

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
