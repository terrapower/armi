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


class FullImplFuelHandler(fuelHandlers.FuelHandler):
    """Implements the entire interface but with empty methods."""

    def chooseSwaps(self, *args, **kwargs):
        pass


class TestOptimalAssemblyRotation(FuelHandlerTestHelper):
    N_PINS = 271

    @staticmethod
    def prepShuffledAssembly(a: HexAssembly, percentBuMaxPinLocation: int):
        """Prepare the assembly that will be shuffled and rotated."""
        for b in a.getChildrenWithFlags(Flags.FUEL):
            # Fake enough information to build a spatial grid
            b.getPinPitch = mock.Mock(return_value=1.1)
            b.autoCreateSpatialGrids()
            for c in b.getChildrenWithFlags(Flags.FUEL):
                mult = c.getDimension("mult")
                if mult <= percentBuMaxPinLocation:
                    continue
                burnups = np.ones(mult, dtype=float)
                burnups[percentBuMaxPinLocation] *= 2
                c.p.pinPercentBu = burnups

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
        self.prepShuffledAssembly(self.assembly, percentBuMaxPinLocation=0)
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

        Notes
        -----
        Note: use zero-indexed pin location not pin ID to assign burnups and powers. Since
        we have a single component, ``Block.p.linPowByPin[i] <-> Component.p.pinPercentBu[i]``
        """
        shuffledAssembly = self.assembly
        previousAssembly = copy.deepcopy(shuffledAssembly)
        for startPin, oppositePin in ((1, 4), (2, 5), (3, 6), (4, 1), (5, 2), (6, 3)):
            powers = np.ones(self.N_PINS)
            powers[oppositePin] = 0
            self.prepShuffledAssembly(shuffledAssembly, startPin)
            self.prepPreviousAssembly(previousAssembly, powers)
            rot = getOptimalAssemblyOrientation(shuffledAssembly, previousAssembly)
            # 180 degrees is three 60 degree rotations
            self.assertEqual(rot, 3, msg=f"{startPin=} :: {oppositePin=}")

    def test_noBlocksWithBurnup(self):
        """Require at least one block to have burnup."""
        with self.assertRaisesRegex(ValueError, "No blocks with burnup found"):
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
    @staticmethod
    def prepareAssemForBurnupRotation(assem: HexAssembly):
        """Set necessary data in order for the burnup rotation to be performed."""
        for b in assem.getBlocks(Flags.FUEL):
            b.initializePinLocations()
            fuel = b.getChildrenWithFlags(Flags.FUEL)[0]
            mult = fuel.getDimension("mult")
            fuel.p.pinPercentBu = np.arange(mult, dtype=float)[::-1]
            b.p.linPowByPin = reversed(range(b.getNumPins()))

    def test_buReducingAssemblyRotation(self):
        """Test that the fuel handler supports the burnup reducing assembly rotation."""
        newSettings = {
            CONF_ASSEM_ROTATION_STATIONARY: False,
            "fluxRecon": True,
            "assemblyRotationAlgorithm": "buReducingAssemblyRotation",
        }
        self.o.cs = self.o.cs.modified(newSettings=newSettings)

        # Grab two assemblies and make them look like they were part of a shuffling operation
        rotatedAssem, shuffledAway = self.o.r.core.getChildrenWithFlags(Flags.FUEL)[:2]
        self.prepareAssemForBurnupRotation(rotatedAssem)
        self.prepareAssemForBurnupRotation(shuffledAway)

        # Mimic a shuffling where shuffledAway used to be where rotatedAssem is now
        shuffledAway.lastLocationLabel = rotatedAssem.getLocation()

        # Show that we call the optimal assembly orientation function.
        # This function is tested seperately and more extensively elsewhere.
        fh = FullImplFuelHandler(self.o)
        # Mocked swap function updates the moved assemblies collection
        fh.chooseSwaps = mock.Mock(side_effect=lambda _: fh.moved.append(shuffledAway))
        with mock.patch(
            "armi.physics.fuelCycle.assemblyRotationAlgorithms.getOptimalAssemblyOrientation",
            return_value=4,
        ) as p:
            fh.outage(1)
        # fh.outage clears fh.moved at the end. But if it was called, we know our mock function added
        # our shuffled assembly to the moved assemblies.
        fh.chooseSwaps.assert_called_once()
        p.assert_called_once_with(rotatedAssem, shuffledAway)
        for b in rotatedAssem.getBlocks(Flags.FUEL):
            # Four rotations is 240 degrees
            self.assertEqual(b.p.orientation[2], 240)

    def test_buRotationWithFreshFeed(self):
        """Test that rotation works if a new assembly is swapped with fresh fuel.

        Fresh feed assemblies will not exist in the reactor, and various checks that
        try to the "previous" assembly's location can fail.
        """
        newSettings = {
            "fluxRecon": True,
            "assemblyRotationAlgorithm": "buReducingAssemblyRotation",
        }
        self.o.cs = self.o.cs.modified(newSettings=newSettings)

        fresh = self.r.core.createFreshFeed(self.o.cs)
        self.assertEqual(fresh.lastLocationLabel, HexAssembly.LOAD_QUEUE)
        fh = FullImplFuelHandler(self.o)
        fh.chooseSwaps = mock.Mock(side_effect=lambda _: fh.moved.append(fresh))

        with mock.patch(
            "armi.physics.fuelCycle.assemblyRotationAlgorithms.getOptimalAssemblyOrientation",
        ) as p:
            fh.outage()
        # The only moved assembly was most recently outside the core so we have no need to rotate
        # Make sure our fake chooseSwaps added the fresh assembly to the moved assemblies
        fh.chooseSwaps.assert_called_once()
        p.assert_not_called()

    def test_buRotationWithStationaryRotation(self):
        """Test that the burnup equalizing rotation algorithm works on non-shuffled assemblies."""
        newSettings = {
            CONF_ASSEM_ROTATION_STATIONARY: True,
            "fluxRecon": True,
            "assemblyRotationAlgorithm": "buReducingAssemblyRotation",
        }
        self.o.cs = self.o.cs.modified(newSettings=newSettings)

        # Grab two assemblies that were not moved. One of which will have the detailed information
        # needed for rotation
        detailedAssem, coarseAssem = self.o.r.core.getChildrenWithFlags(Flags.FUEL)[:2]
        self.prepareAssemForBurnupRotation(detailedAssem)
        detailedAssem.rotate = mock.Mock()
        coarseAssem.rotate = mock.Mock()

        fh = FullImplFuelHandler(self.o)

        with mock.patch(
            "armi.physics.fuelCycle.assemblyRotationAlgorithms.getOptimalAssemblyOrientation",
            return_value=5,
        ) as p:
            fh.outage()
        p.assert_called_once_with(detailedAssem, detailedAssem)
        detailedAssem.rotate.assert_called_once()
        coarseAssem.rotate.assert_not_called()

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
