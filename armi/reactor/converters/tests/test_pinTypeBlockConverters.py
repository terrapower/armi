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
"""Unit tests for pin type block converters."""
import copy
import unittest

from armi.reactor.converters.pinTypeBlockConverters import (
    adjustCladThicknessByID,
    adjustCladThicknessByOD,
    adjustSmearDensity,
)
from armi.reactor.flags import Flags
from armi.reactor.tests.test_blocks import buildSimpleFuelBlock, loadTestBlock


class TestPinTypeConverters(unittest.TestCase):
    def setUp(self):
        self.block = loadTestBlock()

    def test_adjustCladThicknessByOD(self):
        thickness = 0.05
        clad = self.block.getComponent(Flags.CLAD)
        ref = clad.getDimension("id", cold=True) + 2.0 * thickness
        adjustCladThicknessByOD(self.block, thickness)
        cur = clad.getDimension("od", cold=True)
        curThickness = (
            clad.getDimension("od", cold=True) - clad.getDimension("id", cold=True)
        ) / 2.0
        self.assertAlmostEqual(cur, ref)
        self.assertAlmostEqual(curThickness, thickness)

    def test_adjustCladThicknessByID(self):
        thickness = 0.05
        clad = self.block.getComponent(Flags.CLAD)
        ref = clad.getDimension("od", cold=True) - 2.0 * thickness
        adjustCladThicknessByID(self.block, thickness)
        cur = clad.getDimension("id", cold=True)
        curThickness = (
            clad.getDimension("od", cold=True) - clad.getDimension("id", cold=True)
        ) / 2.0
        self.assertAlmostEqual(cur, ref)
        self.assertAlmostEqual(curThickness, thickness)


class MassConservationTests(unittest.TestCase):
    r"""Tests designed to verify mass conservation during thermal expansion."""

    def setUp(self):
        self.b = buildSimpleFuelBlock()

    def test_adjustSmearDensity(self):
        r"""Tests the getting, setting, and getting of smear density functions."""
        bolBlock = copy.deepcopy(self.b)

        s = self.b.getSmearDensity(cold=False)

        fuel = self.b.getComponent(Flags.FUEL)
        clad = self.b.getComponent(Flags.CLAD)

        self.assertAlmostEqual(
            s, (fuel.getDimension("od") ** 2) / clad.getDimension("id") ** 2, 8
        )

        adjustSmearDensity(self.b, self.b.getSmearDensity(), bolBlock=bolBlock)

        s2 = self.b.getSmearDensity(cold=False)

        self.assertAlmostEqual(s, s2, 8)

        adjustSmearDensity(self.b, 0.733, bolBlock=bolBlock)
        self.assertAlmostEqual(0.733, self.b.getSmearDensity(), 8)

        # try annular fuel
        clad = self.b.getComponent(Flags.CLAD)
        fuel = self.b.getComponent(Flags.FUEL)

        fuel.setDimension("od", clad.getDimension("id", cold=True))
        fuel.setDimension("id", 0.0001)

        adjustSmearDensity(self.b, 0.733, bolBlock=bolBlock)
        self.assertAlmostEqual(0.733, self.b.getSmearDensity(), 8)
