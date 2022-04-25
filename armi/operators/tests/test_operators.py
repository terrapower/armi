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

"""Tests for operators"""

# pylint: disable=abstract-method,no-self-use,unused-argument
import unittest

from armi import settings
from armi.interfaces import Interface
from armi.operators.operator import (
    getPowerFractions,
    getCycleNames,
    getAvailabilityFactors,
    getStepLengths,
    getCycleLengths,
    getBurnSteps,
    Operator,
)
from armi.reactor.tests import test_reactors
from armi.settings.caseSettings import Settings


class InterfaceA(Interface):
    function = "A"
    name = "First"


class InterfaceB(InterfaceA):
    """Dummy Interface that extends A"""

    function = "A"
    name = "Second"


class InterfaceC(Interface):
    function = "A"
    name = "Third"


# TODO: Add a test that shows time evolution of Reactor (REQ_EVOLVING_STATE)
class OperatorTests(unittest.TestCase):
    def test_addInterfaceSubclassCollision(self):
        self.cs = settings.Settings()
        o, r = test_reactors.loadTestReactor()

        interfaceA = InterfaceA(r, self.cs)

        interfaceB = InterfaceB(r, self.cs)
        o.addInterface(interfaceA)

        # 1) Adds B and gets rid of A
        o.addInterface(interfaceB)
        self.assertEqual(o.getInterface("Second"), interfaceB)
        self.assertEqual(o.getInterface("First"), None)

        # 2) Now we have B which is a subclass of A,
        #    we want to not add A (but also not have an error)
        o.addInterface(interfaceA)
        self.assertEqual(o.getInterface("Second"), interfaceB)
        self.assertEqual(o.getInterface("First"), None)

        # 3) Also if another class not a subclass has the same function,
        #    raise an error
        interfaceC = InterfaceC(r, self.cs)

        self.assertRaises(RuntimeError, o.addInterface, interfaceC)

        # 4) Check adding a different function Interface

        interfaceC.function = "C"

        o.addInterface(interfaceC)
        self.assertEqual(o.getInterface("Second"), interfaceB)
        self.assertEqual(o.getInterface("Third"), interfaceC)


class CyclesSettingsTests(unittest.TestCase):
    """
    Check the various cycle history settings for both the detailed and simple input
    options.

    For each setting, check the information as it is pulled directly from a cs
    object as well as pulling it from the operator itself.
    """

    detailedCyclesSettings = """
metadata:
  version: uncontrolled
settings:
  power: 1000000000.0
  nCycles: 3
  cycles:
    - name: dog
      cumulative days: [1, 2, 3]
      power fractions: [0.1, 0.2, 0.3]
      availability factor: 0.1
    - cumulative days: [2, 4, 6, 8, 10]
      power fractions: [0.2, 0.2, 0.2, 0.2, 0]
    - name: ferret
      step days: [3, R4]
      power fractions: [0.3, R4]
  runType: Standard
"""
    simpleCyclesSettings = """
metadata:
  version: uncontrolled
settings:
  power: 1000000000.0
  nCycles: 3
  availabilityFactors: [0.1, R2]
  cycleLengths: [1, 2, 3]
  powerFractions: [0.1, 0.2, R1]
  burnSteps: 3
  runType: Standard
  """

    powerFractionsDetailedSolution = [
        [0.1, 0.2, 0.3],
        [0.2, 0.2, 0.2, 0.2, 0],
        [0.3, 0.3, 0.3, 0.3, 0.3],
    ]
    powerFractionsSimpleSolution = [[0.1, 0.1, 0.1], [0.2, 0.2, 0.2], [0.2, 0.2, 0.2]]
    cycleNamesDetailedSolution = ["dog", None, "ferret"]
    cycleNamesSimpleSolution = [None, None, None]
    availabilityFactorsDetailedSolution = [0.1, 1, 1]
    availabilityFactorsSimpleSolution = [0.1, 0.1, 0.1]
    stepLengthsDetailedSolution = [[1, 1, 1], [2, 2, 2, 2, 2], [3, 3, 3, 3, 3]]
    stepLengthsSimpleSolution = [
        [1 / 3, 1 / 3, 1 / 3],
        [2 / 3, 2 / 3, 2 / 3],
        [1, 1, 1],
    ]
    cycleLengthsDetailedSolution = [3, 10, 15]
    cycleLengthsSimpleSolution = [1, 2, 3]
    burnStepsDetailedSolution = [3, 5, 5]
    burnStepsSimpleSolution = [3, 3, 3]

    def setUp(self):
        self.standaloneDetailedCS = Settings()
        self.standaloneDetailedCS.loadFromString(self.detailedCyclesSettings)
        self.detailedOperator = Operator(self.standaloneDetailedCS)

        self.standaloneSimpleCS = Settings()
        self.standaloneSimpleCS.loadFromString(self.simpleCyclesSettings)
        self.simpleOperator = Operator(self.standaloneSimpleCS)

    def test_getPowerFractions(self):
        self.assertEqual(
            getPowerFractions(self.standaloneDetailedCS),
            self.powerFractionsDetailedSolution,
        )
        self.assertEqual(
            self.detailedOperator.powerFractions, self.powerFractionsDetailedSolution
        )

        self.assertEqual(
            getPowerFractions(self.standaloneSimpleCS),
            self.powerFractionsSimpleSolution,
        )
        self.assertEqual(
            self.simpleOperator.powerFractions, self.powerFractionsSimpleSolution
        )

    def test_getCycleNames(self):
        self.assertEqual(
            getCycleNames(self.standaloneDetailedCS), self.cycleNamesDetailedSolution
        )
        self.assertEqual(
            self.detailedOperator.cycleNames, self.cycleNamesDetailedSolution
        )

        self.assertEqual(
            getCycleNames(self.standaloneSimpleCS), self.cycleNamesSimpleSolution
        )
        self.assertEqual(self.simpleOperator.cycleNames, self.cycleNamesSimpleSolution)

    def test_getAvailabilityFactors(self):
        self.assertEqual(
            getAvailabilityFactors(self.standaloneDetailedCS),
            self.availabilityFactorsDetailedSolution,
        )
        self.assertEqual(
            self.detailedOperator.availabilityFactors,
            self.availabilityFactorsDetailedSolution,
        )

        self.assertEqual(
            getAvailabilityFactors(self.standaloneSimpleCS),
            self.availabilityFactorsSimpleSolution,
        )
        self.assertEqual(
            self.simpleOperator.availabilityFactors,
            self.availabilityFactorsSimpleSolution,
        )

    def test_getStepLengths(self):
        self.assertEqual(
            getStepLengths(self.standaloneDetailedCS),
            self.stepLengthsDetailedSolution,
        )
        self.assertEqual(
            self.detailedOperator.stepLengths, self.stepLengthsDetailedSolution
        )

        self.assertEqual(
            getStepLengths(self.standaloneSimpleCS),
            self.stepLengthsSimpleSolution,
        )
        self.assertEqual(
            self.simpleOperator.stepLengths, self.stepLengthsSimpleSolution
        )

    def test_getCycleLengths(self):
        self.assertEqual(
            getCycleLengths(self.standaloneDetailedCS),
            self.cycleLengthsDetailedSolution,
        )
        self.assertEqual(
            self.detailedOperator.cycleLengths, self.cycleLengthsDetailedSolution
        )

        self.assertEqual(
            getCycleLengths(self.standaloneSimpleCS), self.cycleLengthsSimpleSolution
        )
        self.assertEqual(
            self.simpleOperator.cycleLengths, self.cycleLengthsSimpleSolution
        )

    def test_getBurnSteps(self):
        self.assertEqual(
            getBurnSteps(self.standaloneDetailedCS), self.burnStepsDetailedSolution
        )
        self.assertEqual(
            self.detailedOperator.burnSteps, self.burnStepsDetailedSolution
        )

        self.assertEqual(
            getBurnSteps(self.standaloneSimpleCS), self.burnStepsSimpleSolution
        )
        self.assertEqual(self.simpleOperator.burnSteps, self.burnStepsSimpleSolution)


if __name__ == "__main__":
    unittest.main()
