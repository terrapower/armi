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
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import unittest

from armi.physics.fuelCycle import assemblyRotationAlgorithms as rotAlgos
from armi.physics.fuelCycle import fuelHandlers
from armi.physics.fuelCycle.settings import CONF_ASSEM_ROTATION_STATIONARY
from armi.physics.fuelCycle.tests.test_fuelHandlers import addSomeDetailAssemblies
from armi.physics.fuelCycle.tests.test_fuelHandlers import FuelHandlerTestHelper
from armi.reactor.flags import Flags


class TestFuelHandlerMgmtTools(FuelHandlerTestHelper):
    def test_buReducingAssemblyRotation(self):
        fh = fuelHandlers.FuelHandler(self.o)
        hist = self.o.getInterface("history")
        newSettings = {CONF_ASSEM_ROTATION_STATIONARY: True}
        self.o.cs = self.o.cs.modified(newSettings=newSettings)
        assem = self.o.r.core.getFirstAssembly(Flags.FUEL)

        # apply dummy pin-level data to allow intelligent rotation
        for b in assem.getBlocks(Flags.FUEL):
            b.breakFuelComponentsIntoIndividuals()
            b.initializePinLocations()
            b.p.percentBuMaxPinLocation = 10
            b.p.percentBuMax = 5
            b.p.linPowByPin = list(reversed(range(b.getNumPins())))

        addSomeDetailAssemblies(hist, [assem])
        rotNum = b.getRotationNum()
        rotAlgos.buReducingAssemblyRotation(fh)
        self.assertNotEqual(b.getRotationNum(), rotNum)

    def test_simpleAssemblyRotation(self):
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
