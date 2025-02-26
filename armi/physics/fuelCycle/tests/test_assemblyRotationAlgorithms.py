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
import enum
import math
import typing
from unittest import TestCase, mock

import numpy as np

from armi.physics.fuelCycle import assemblyRotationAlgorithms as rotAlgos
from armi.physics.fuelCycle import fuelHandlers
from armi.physics.fuelCycle.hexAssemblyFuelMgmtUtils import (
    getOptimalAssemblyOrientation,
)
from armi.physics.fuelCycle.settings import CONF_ASSEM_ROTATION_STATIONARY
from armi.physics.fuelCycle.tests.test_fuelHandlers import addSomeDetailAssemblies
from armi.reactor.assemblies import HexAssembly
from armi.reactor.blocks import HexBlock
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors


class MockFuelHandler(fuelHandlers.FuelHandler):
    """Implements the entire interface but with empty methods."""

    def chooseSwaps(self, *args, **kwargs):
        pass


class _PinLocations(enum.IntEnum):
    """Zero-indexed locations for specific points of interest.

    If a data vector has an entry to all ``self.N_PINS=169`` pins in the test model,
    then ``data[PIN_LOCATIONS.UPPER_RIGHT_VERTEX]`` will access the data for the pin
    along the upper right 60 symmetry line. Since we're dealing with rotations here, it
    does not need to literally be the pin at the vertex. Just along the symmetry line
    to help explain tests.

    The use case here is setting the pin or burnup array to be a constant value, but
    using a single max or minimum value to determine rotation.
    """

    CENTER = 0
    UPPER_RIGHT_VERTEX = 1
    UPPER_LEFT_VERTEX = 2
    DUE_LEFT_VERTEX = 3
    LOWER_LEFT_VERTEX = 4
    LOWER_RIGHT_VERTEX = 5
    DUE_RIGHT_VERTEX = 6


class ShuffleAndRotateTestHelper(TestCase):
    """Fixture class to assist in testing rotation of assemblies via the fuel handler."""

    N_PINS = 169

    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor()
        self.r.core.locateAllAssemblies()

    @staticmethod
    def ensureBlockHasSpatialGrid(b: HexBlock):
        """If ``b`` does not have a spatial grid, auto create one."""
        if b.spatialGrid is None:
            b.getPinPitch = mock.Mock(return_value=1.1)
            b.autoCreateSpatialGrids()

    def setAssemblyPinBurnups(self, a: HexAssembly, burnups: np.ndarray):
        """Prepare the assembly that will be shuffled and rotated."""
        peakBu = burnups.max()
        for b in a.getChildrenWithFlags(Flags.FUEL):
            self.ensureBlockHasSpatialGrid(b)
            b.p.percentBuPeak = peakBu
            for c in b.getChildrenWithFlags(Flags.FUEL):
                c.p.pinPercentBu = burnups

    def setAssemblyPinPowers(self, a: HexAssembly, pinPowers: np.ndarray):
        """Prep the assembly that existed at the site a shuffled assembly will occupy."""
        for b in a.getChildrenWithFlags(Flags.FUEL):
            self.ensureBlockHasSpatialGrid(b)
            b.p.linPowByPin = pinPowers

    def powerWithMinValue(self, minIndex: int) -> np.ndarray:
        """Create a vector of pin powers with a minimum value at a given index."""
        data = np.ones(self.N_PINS)
        data[minIndex] = 0
        return data

    def burnupWithMaxValue(self, maxIndex: int) -> np.ndarray:
        """Create a vector of pin burnups with a maximum value at a given index."""
        data = np.zeros(self.N_PINS)
        data[maxIndex] = 50
        return data

    def compareMockedToExpectedRotation(self, nRotations: int, mRotate: mock.Mock, msg: typing.Optional[str] = None):
        """Helper function to check the mocked rotate and compare against expected rotation."""
        expectedRadians = nRotations * math.pi / 3
        (actualRadians,) = mRotate.call_args.args
        self.assertAlmostEqual(actualRadians, expectedRadians, msg=msg)


class TestOptimalAssemblyRotation(ShuffleAndRotateTestHelper):
    """Test the burnup dependent assembly rotation methods."""

    def setUp(self):
        super().setUp()
        self.assembly: HexAssembly = self.r.core.getFirstAssembly(Flags.FUEL)

    def test_flatPowerNoRotation(self):
        """If all pin powers are identical, no rotation is suggested."""
        burnups = self.burnupWithMaxValue(_PinLocations.UPPER_LEFT_VERTEX)
        powers = np.ones_like(burnups)
        self.setAssemblyPinBurnups(self.assembly, burnups)
        self.setAssemblyPinPowers(self.assembly, powers)
        rot = getOptimalAssemblyOrientation(self.assembly, self.assembly)
        self.assertEqual(rot, 0)

    def test_maxBurnupAtCenterNoRotation(self):
        """If max burnup pin is at the center, no rotation is suggested."""
        burnups = self.burnupWithMaxValue(_PinLocations.CENTER)
        powers = np.zeros_like(burnups)
        self.setAssemblyPinBurnups(self.assembly, burnups)
        self.setAssemblyPinPowers(self.assembly, powers)
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
        Use zero-indexed pin location not pin ID to assign burnups and powers. Since
        we have a single component, ``Block.p.linPowByPin[i] <-> Component.p.pinPercentBu[i]``
        """
        shuffledAssembly = self.assembly
        previousAssembly = copy.deepcopy(shuffledAssembly)
        pairs = (
            (_PinLocations.DUE_RIGHT_VERTEX, _PinLocations.DUE_LEFT_VERTEX),
            (_PinLocations.UPPER_LEFT_VERTEX, _PinLocations.LOWER_RIGHT_VERTEX),
            (_PinLocations.UPPER_RIGHT_VERTEX, _PinLocations.LOWER_LEFT_VERTEX),
            (_PinLocations.DUE_LEFT_VERTEX, _PinLocations.DUE_RIGHT_VERTEX),
            (_PinLocations.LOWER_RIGHT_VERTEX, _PinLocations.UPPER_LEFT_VERTEX),
            (_PinLocations.LOWER_LEFT_VERTEX, _PinLocations.UPPER_RIGHT_VERTEX),
        )
        for startPin, oppositePin in pairs:
            powers = self.powerWithMinValue(oppositePin)
            burnups = self.burnupWithMaxValue(startPin)
            self.setAssemblyPinBurnups(shuffledAssembly, burnups)
            self.setAssemblyPinPowers(previousAssembly, powers)
            rot = getOptimalAssemblyOrientation(shuffledAssembly, previousAssembly)
            # 180 degrees is three 60 degree rotations
            self.assertEqual(rot, 3, msg=f"{startPin=} :: {oppositePin=}")

    def test_noBlocksWithBurnup(self):
        """Require at least one block to have burnup."""
        with self.assertRaisesRegex(ValueError, "Error finding max burnup"):
            getOptimalAssemblyOrientation(self.assembly, self.assembly)

    def test_mismatchPinPowersAndLocations(self):
        """Require pin powers and locations to be have the same length."""
        powers = np.arange(self.N_PINS + 1)
        burnups = np.arange(self.N_PINS)
        self.setAssemblyPinBurnups(self.assembly, burnups)
        self.setAssemblyPinPowers(self.assembly, powers)
        with self.assertRaisesRegex(ValueError, "Inconsistent pin powers and number of pins"):
            getOptimalAssemblyOrientation(self.assembly, self.assembly)


class TestFuelHandlerMgmtTools(ShuffleAndRotateTestHelper):
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
        fh = MockFuelHandler(self.o)
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
        self.setAssemblyPinBurnups(detailedAssem, burnups=np.arange(self.N_PINS))
        self.setAssemblyPinPowers(detailedAssem, pinPowers=np.arange(self.N_PINS))
        detailedAssem.rotate = mock.Mock()
        coarseAssem.rotate = mock.Mock()

        fh = MockFuelHandler(self.o)

        with mock.patch(
            "armi.physics.fuelCycle.assemblyRotationAlgorithms.getOptimalAssemblyOrientation",
            return_value=5,
        ) as p:
            fh.outage()
        p.assert_called_once_with(detailedAssem, detailedAssem)
        # Assembly with detailed pin powers and pin burnups will be rotated
        detailedAssem.rotate.assert_called_once()
        self.compareMockedToExpectedRotation(5, detailedAssem.rotate)
        # Assembly without pin level data will not be rotated
        coarseAssem.rotate.assert_not_called()

    def test_rotateInShuffleQueue(self):
        """Test for expected behavior when multiple assemblies are shuffled and rotated in one outage.

        Examine the behavior of three assemblies: ``first -> second -> third``

        1. ``first`` is moved to the location of ``second`` and rotated by comparing
           ``first`` burnup against ``second`` pin powers.
        2. ``second`` is moved to the location of ``third`` and rotated by comparing
           ``second`` burnup against ``third`` pin powers.

        where:

        * ``first`` burnup is maximized in the upper left direction.
        * ``second`` pin power is minimized along the lower left direction.
        * ``second`` burnup is maximized in the upper right direction.
        * ``third`` pin power is minimized in the direct right direction.

        We should expect:

        1. ``first`` is rotated from upper left to lower left => two 60 degree CCW rotations.
        2. ``second`` is rotated from upper right to direct right => five 60 degree CCW rotations.
        """
        newSettings = {
            CONF_ASSEM_ROTATION_STATIONARY: False,
            "fluxRecon": True,
            "assemblyRotationAlgorithm": "buReducingAssemblyRotation",
        }
        self.o.cs = self.o.cs.modified(newSettings=newSettings)

        first, second, third = self.r.core.getChildrenWithFlags(Flags.FUEL)[:3]

        firstBurnups = self.burnupWithMaxValue(_PinLocations.UPPER_LEFT_VERTEX)
        self.setAssemblyPinBurnups(first, firstBurnups)

        secondPowers = self.powerWithMinValue(_PinLocations.LOWER_LEFT_VERTEX)
        self.setAssemblyPinPowers(second, pinPowers=secondPowers)

        secondBurnups = self.burnupWithMaxValue(_PinLocations.UPPER_RIGHT_VERTEX)
        self.setAssemblyPinBurnups(second, burnups=secondBurnups)

        thirdPowers = self.powerWithMinValue(_PinLocations.DUE_RIGHT_VERTEX)
        self.setAssemblyPinPowers(third, thirdPowers)

        # Set the shuffling sequence
        # first -> second
        # second -> third
        second.lastLocationLabel = first.getLocation()
        third.lastLocationLabel = second.getLocation()

        first.rotate = mock.Mock()
        second.rotate = mock.Mock()
        third.rotate = mock.Mock()

        fh = MockFuelHandler(self.o)
        fh.chooseSwaps = mock.Mock(side_effect=lambda _: fh.moved.extend([second, third]))
        fh.outage()

        first.rotate.assert_called_once()
        self.compareMockedToExpectedRotation(2, first.rotate, "First")
        second.rotate.assert_called_once()
        self.compareMockedToExpectedRotation(5, second.rotate, "Second")
        third.rotate.assert_not_called()


class SimpleRotationTests(ShuffleAndRotateTestHelper):
    """Test the simple rotation where assemblies are rotated a fixed amount."""

    def test_simpleAssemblyRotation(self):
        """Test rotating assemblies 120 degrees with two rotation events."""
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
