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

# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-method-argument,import-outside-toplevel
import unittest

from armi import settings
from armi.interfaces import Interface
from armi.operators.operator import Operator
from armi.reactor.tests import test_reactors
from armi.settings.caseSettings import Settings
from armi.utils.directoryChangers import TemporaryDirectoryChanger


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
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor()

    def test_addInterfaceSubclassCollision(self):
        cs = settings.Settings()

        interfaceA = InterfaceA(self.r, cs)

        interfaceB = InterfaceB(self.r, cs)
        self.o.addInterface(interfaceA)

        # 1) Adds B and gets rid of A
        self.o.addInterface(interfaceB)
        self.assertEqual(self.o.getInterface("Second"), interfaceB)
        self.assertEqual(self.o.getInterface("First"), None)

        # 2) Now we have B which is a subclass of A,
        #    we want to not add A (but also not have an error)
        self.o.addInterface(interfaceA)
        self.assertEqual(self.o.getInterface("Second"), interfaceB)
        self.assertEqual(self.o.getInterface("First"), None)

        # 3) Also if another class not a subclass has the same function,
        #    raise an error
        interfaceC = InterfaceC(self.r, cs)
        self.assertRaises(RuntimeError, self.o.addInterface, interfaceC)

        # 4) Check adding a different function Interface
        interfaceC.function = "C"
        self.o.addInterface(interfaceC)
        self.assertEqual(self.o.getInterface("Second"), interfaceB)
        self.assertEqual(self.o.getInterface("Third"), interfaceC)

    def test_checkCsConsistency(self):
        self.o._checkCsConsistency()  # passes without error

        self.o.cs = self.o.cs.modified(newSettings={"nCycles": 66})
        with self.assertRaises(RuntimeError):
            self.o._checkCsConsistency()

    def test_interfaceIsActive(self):
        self.o, _r = test_reactors.loadTestReactor()
        self.assertTrue(self.o.interfaceIsActive("main"))
        self.assertFalse(self.o.interfaceIsActive("Fake-o"))

    def test_loadStateError(self):
        """The loadTestReactor() test tool does not have any history in the DB to load from"""

        # a first, simple test that this method fails correctly
        with self.assertRaises(RuntimeError):
            self.o.loadState(0, 1)

    def test_couplingIsActive(self):
        self.assertFalse(self.o.couplingIsActive())

    def test_setStateToDefault(self):

        # reset the runType for testing
        self.assertEqual(self.o.cs["runType"], "Standard")
        self.o.cs = self.o.cs.modified(newSettings={"runType": "fake"})
        self.assertEqual(self.o.cs["runType"], "fake")

        # validate the method works
        cs = self.o.setStateToDefault(self.o.cs)
        self.assertEqual(cs["runType"], "Standard")

    def test_snapshotRequest(self):
        with TemporaryDirectoryChanger():
            self.o.snapshotRequest(0, 1)


class CyclesSettingsTests(unittest.TestCase):
    """
    Check that we can correctly access the various cycle settings from the operator.
    """

    detailedCyclesSettings = """
metadata:
  version: uncontrolled
settings:
  power: 1000000000.0
  nCycles: 3
  cycles:
    - name: startup sequence
      cumulative days: [1, 2, 3]
      power fractions: [0.1, 0.2, 0.3]
      availability factor: 0.1
    - cycle length: 10
      burn steps: 5
      power fractions: [0.2, 0.2, 0.2, 0.2, 0]
      availability factor: 0.5
    - name: prepare for shutdown
      step days: [3, R4]
      power fractions: [0.3, R4]
  runType: Standard
"""

    powerFractionsSolution = [
        [0.1, 0.2, 0.3],
        [0.2, 0.2, 0.2, 0.2, 0],
        [0.3, 0.3, 0.3, 0.3, 0.3],
    ]
    cycleNamesSolution = ["startup sequence", None, "prepare for shutdown"]
    availabilityFactorsSolution = [0.1, 0.5, 1]
    stepLengthsSolution = [
        [1, 1, 1],
        [10 / 5 * 0.5, 10 / 5 * 0.5, 10 / 5 * 0.5, 10 / 5 * 0.5, 10 / 5 * 0.5],
        [3, 3, 3, 3, 3],
    ]
    cycleLengthsSolution = [30, 10, 15]
    burnStepsSolution = [3, 5, 5]
    maxBurnStepsSolution = 5

    def setUp(self):
        self.standaloneDetailedCS = Settings()
        self.standaloneDetailedCS.loadFromString(self.detailedCyclesSettings)
        self.detailedOperator = Operator(self.standaloneDetailedCS)

    def test_getPowerFractions(self):
        self.assertEqual(
            self.detailedOperator.powerFractions, self.powerFractionsSolution
        )

        self.detailedOperator._powerFractions = None
        self.assertEqual(
            self.detailedOperator.powerFractions, self.powerFractionsSolution
        )

    def test_getCycleNames(self):
        self.assertEqual(self.detailedOperator.cycleNames, self.cycleNamesSolution)

        self.detailedOperator._cycleNames = None
        self.assertEqual(self.detailedOperator.cycleNames, self.cycleNamesSolution)

    def test_getAvailabilityFactors(self):
        self.assertEqual(
            self.detailedOperator.availabilityFactors,
            self.availabilityFactorsSolution,
        )

        self.detailedOperator._availabilityFactors = None
        self.assertEqual(
            self.detailedOperator.availabilityFactors,
            self.availabilityFactorsSolution,
        )

    def test_getStepLengths(self):
        self.assertEqual(self.detailedOperator.stepLengths, self.stepLengthsSolution)

        self.detailedOperator._stepLength = None
        self.assertEqual(self.detailedOperator.stepLengths, self.stepLengthsSolution)

    def test_getCycleLengths(self):
        self.assertEqual(self.detailedOperator.cycleLengths, self.cycleLengthsSolution)

        self.detailedOperator._cycleLengths = None
        self.assertEqual(self.detailedOperator.cycleLengths, self.cycleLengthsSolution)

    def test_getBurnSteps(self):
        self.assertEqual(self.detailedOperator.burnSteps, self.burnStepsSolution)

        self.detailedOperator._burnSteps = None
        self.assertEqual(self.detailedOperator.burnSteps, self.burnStepsSolution)

    def test_getMaxBurnSteps(self):
        self.assertEqual(self.detailedOperator.maxBurnSteps, self.maxBurnStepsSolution)

        self.detailedOperator._maxBurnSteps = None
        self.assertEqual(self.detailedOperator.maxBurnSteps, self.maxBurnStepsSolution)


if __name__ == "__main__":
    unittest.main()
