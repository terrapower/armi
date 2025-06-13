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

"""Tests for operators."""

import collections
import io
import os
import sys
import unittest
from unittest.mock import patch

from armi import settings
from armi.bookkeeping.db.databaseInterface import DatabaseInterface
from armi.interfaces import Interface, TightCoupler
from armi.operators.operator import Operator
from armi.physics.neutronics.globalFlux.globalFluxInterface import (
    GlobalFluxInterfaceUsingExecuters,
)
from armi.reactor.reactors import Core, Reactor
from armi.reactor.tests import test_reactors
from armi.settings.caseSettings import Settings
from armi.settings.fwSettings.globalSettings import (
    CONF_CYCLES_SKIP_TIGHT_COUPLING_INTERACTION,
    CONF_DEFERRED_INTERFACE_NAMES,
    CONF_DEFERRED_INTERFACES_CYCLE,
    CONF_RUN_TYPE,
    CONF_TIGHT_COUPLING,
    CONF_TIGHT_COUPLING_SETTINGS,
)
from armi.tests import mockRunLogs
from armi.utils import directoryChangers
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class InterfaceA(Interface):
    function = "A"
    name = "First"


class InterfaceB(InterfaceA):
    """Dummy Interface that extends A."""

    function = "A"
    name = "Second"


class InterfaceC(Interface):
    function = "A"
    name = "Third"


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        self.activeInterfaces = [ii for ii in self.o.interfaces if ii.enabled()]

    def test_operatorData(self):
        """Test that the operator has input data, a reactor model.

        .. test:: The Operator includes input data and the reactor data model.
            :id: T_ARMI_OPERATOR_COMM
            :tests: R_ARMI_OPERATOR_COMM
        """
        self.assertEqual(self.o.r, self.r)
        self.assertEqual(type(self.o.cs), settings.Settings)

    @patch("armi.operators.Operator._interactAll")
    def test_orderedInterfaces(self, interactAll):
        """Test the default interfaces are in an ordered list, looped over at each time step.

        .. test:: An ordered list of interfaces are run at each time step.
            :id: T_ARMI_OPERATOR_INTERFACES
            :tests: R_ARMI_OPERATOR_INTERFACES

        .. test:: Interfaces are run at BOC, EOC, and at time points between.
            :id: T_ARMI_INTERFACE
            :tests: R_ARMI_INTERFACE

        .. test:: When users set the time discretization, it is enforced.
            :id: T_ARMI_FW_HISTORY2
            :tests: R_ARMI_FW_HISTORY
        """
        # an ordered list of interfaces
        self.assertGreater(len(self.o.interfaces), 0)
        for i in self.o.interfaces:
            self.assertTrue(isinstance(i, Interface))

        # make sure we only iterate one time step
        self.o.cs = self.o.cs.modified(newSettings={"nCycles": 2})
        self.r.p.cycle = 1

        # mock some stdout logging of what's happening when
        def sideEffect(node, activeInts, *args, **kwargs):
            print(node)
            print(activeInts)

        interactAll.side_effect = sideEffect

        # run the operator through one cycle
        origout = sys.stdout
        try:
            out = io.StringIO()
            sys.stdout = out
            self.o.operate()
        finally:
            sys.stdout = origout

        # grab the log data
        log = out.getvalue()

        # verify we have some common interfaces listed
        self.assertIn("main", log)
        self.assertIn("fuelHandler", log)
        self.assertIn("fissionProducts", log)
        self.assertIn("history", log)
        self.assertIn("snapshot", log)

        # At the first time step, we get one ordered list of interfaces
        interfaces = log.split("BOL")[1].split("EOL")[0].split(",")
        self.assertGreater(len(interfaces), 0)
        for i in interfaces:
            self.assertIn("Interface", i)

        # verify the various time nodes are hit in order
        timeNodes = ["BOL", "BOC"] + ["EveryNode"] * 3 + ["EOC", "EOL"]
        for node in timeNodes:
            self.assertIn(node, log)
            log = node.join(log.split(node)[1:])

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

    def test_interfaceIsActive(self):
        self.o, _r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        self.assertTrue(self.o.interfaceIsActive("main"))
        self.assertFalse(self.o.interfaceIsActive("Fake-o"))

    def test_getActiveInterfaces(self):
        """Ensure that the right interfaces are returned for a given interaction state."""
        self.o.cs[CONF_DEFERRED_INTERFACES_CYCLE] = 1
        self.o.cs[CONF_DEFERRED_INTERFACE_NAMES] = ["history"]

        # Test invalid inputs.
        with self.assertRaises(ValueError):
            self.o.getActiveInterfaces("notAnInterface")

        # Test BOL
        interfaces = self.o.getActiveInterfaces("BOL", excludedInterfaceNames=("xsGroups"))
        interfaceNames = [interface.name for interface in interfaces]
        self.assertNotIn("xsGroups", interfaceNames)
        self.assertNotIn("history", interfaceNames)

        # Test BOC
        interfaces = self.o.getActiveInterfaces("BOC", cycle=0)
        interfaceNames = [interface.name for interface in interfaces]
        self.assertNotIn("history", interfaceNames)

        # Test EveryNode and EOC
        interfaces = self.o.getActiveInterfaces("EveryNode", excludedInterfaceNames=("xsGroups"))
        interfaceNames = [interface.name for interface in interfaces]
        self.assertIn("history", interfaceNames)
        self.assertNotIn("xsGroups", interfaceNames)

        # Test Coupled
        interfaces = self.o.getActiveInterfaces("Coupled")
        for test, ref in zip(interfaces, self.activeInterfaces):
            self.assertEqual(test.name, ref.name)

        # Test EOL
        interfaces = self.o.getActiveInterfaces("EOL")
        self.assertEqual(interfaces[-1].name, "main")

        # Test excludedInterfaceNames
        excludedInterfaceNames = ["fissionProducts", "fuelHandler", "xsGroups"]
        interfaces = self.o.getActiveInterfaces("EOL", excludedInterfaceNames=excludedInterfaceNames)
        interfaceNames = [ii.name for ii in interfaces]
        self.assertIn("history", interfaceNames)
        self.assertIn("main", interfaceNames)
        self.assertIn("snapshot", interfaceNames)
        self.assertNotIn("fissionProducts", interfaceNames)
        self.assertNotIn("fuelHandler", interfaceNames)
        self.assertNotIn("xsGroups", interfaceNames)

    def test_loadStateError(self):
        """The ``loadTestReactor()`` test tool does not have any history in the DB to load from."""
        # a first, simple test that this method fails correctly
        with self.assertRaises(RuntimeError):
            self.o.loadState(0, 1)

    def test_setStateToDefault(self):
        # reset the runType for testing
        self.assertEqual(self.o.cs[CONF_RUN_TYPE], "Standard")
        self.o.cs = self.o.cs.modified(newSettings={"runType": "fake"})
        self.assertEqual(self.o.cs[CONF_RUN_TYPE], "fake")

        # validate the method works
        cs = self.o.setStateToDefault(self.o.cs)
        self.assertEqual(cs[CONF_RUN_TYPE], "Standard")

    @patch("shutil.copy")
    @patch("os.listdir")
    def test_snapshotRequest(self, fakeDirList, fakeCopy):
        fakeDirList.return_value = ["mccAA.inp"]
        with TemporaryDirectoryChanger():
            with mockRunLogs.BufferLog() as mock:
                self.o.snapshotRequest(0, 1)
                self.assertIn("ISOTXS-c0", mock.getStdout())
                self.assertIn("DIF3D input for snapshot", mock.getStdout())
                self.assertIn("Shuffle logic for snapshot", mock.getStdout())
                self.assertIn("Loading definition for snapshot", mock.getStdout())
            self.assertTrue(os.path.exists("snapShot0_1"))

        with TemporaryDirectoryChanger():
            with mockRunLogs.BufferLog() as mock:
                self.o.snapshotRequest(0, 2, iteration=1)
                self.assertIn("ISOTXS-c0", mock.getStdout())
                self.assertIn("DIF3D input for snapshot", mock.getStdout())
                self.assertIn("Shuffle logic for snapshot", mock.getStdout())
                self.assertIn("Loading definition for snapshot", mock.getStdout())
            self.assertTrue(os.path.exists("snapShot0_2"))


class TestCreateOperator(unittest.TestCase):
    def test_createOperator(self):
        """Test that an operator can be created from settings.

        .. test:: Create an operator from settings.
            :id: T_ARMI_OPERATOR_SETTINGS
            :tests: R_ARMI_OPERATOR_SETTINGS
        """
        cs = settings.Settings()
        o = Operator(cs)
        # high-level items
        self.assertTrue(isinstance(o, Operator))
        self.assertTrue(isinstance(o.cs, settings.Settings))

        # validate some more nitty-gritty operator details come from settings
        burnStepsSetting = cs["burnSteps"]
        if type(burnStepsSetting) is not list:
            burnStepsSetting = [burnStepsSetting]
        self.assertEqual(o.burnSteps, burnStepsSetting)
        self.assertEqual(o.maxBurnSteps, max(burnStepsSetting))

        powerFracsSetting = cs["powerFractions"]
        if powerFracsSetting:
            self.assertEqual(o.powerFractions, powerFracsSetting)
        else:
            self.assertEqual(o.powerFractions, [[1] * cs["burnSteps"]])


class TestTightCoupling(unittest.TestCase):
    def setUp(self):
        self.cs = settings.Settings()
        self.cs[CONF_TIGHT_COUPLING] = True
        self.o = Operator(self.cs)
        self.o.r = Reactor("empty", None)
        self.o.r.core = Core("empty")

    def test_getStepLengths(self):
        """Test the step lengths are correctly calculated, based on settings.

        .. test:: Users can control time discretization of the simulation through settings.
            :id: T_ARMI_FW_HISTORY0
            :tests: R_ARMI_FW_HISTORY
        """
        self.assertEqual(self.cs["nCycles"], 1)
        self.assertAlmostEqual(self.cs["cycleLength"], 365.242199)
        self.assertEqual(self.cs["burnSteps"], 4)

        self.assertEqual(len(self.o.stepLengths), 1)
        self.assertEqual(len(self.o.stepLengths[0]), 4)

    def test_couplingIsActive(self):
        """Ensure that ``cs[CONF_TIGHT_COUPLING]`` controls ``couplingIsActive``."""
        self.assertTrue(self.o.couplingIsActive())
        self.o.cs[CONF_TIGHT_COUPLING] = False
        self.assertFalse(self.o.couplingIsActive())

    def test_performTightCoupling_Inactive(self):
        """Ensures no action by ``_performTightCoupling`` if ``cs[CONF_TIGHT_COUPLING] = false``."""
        self.o.cs[CONF_TIGHT_COUPLING] = False
        self.o._performTightCoupling(0, 0, writeDB=False)
        self.assertEqual(self.o.r.core.p.coupledIteration, 0)

    def test_performTightCoupling_skip(self):
        """Ensure that cycles within ``cs[CONF_CYCLES_SKIP_TIGHT_COUPLING_INTERACTION]`` are skipped."""
        self.o.cs[CONF_CYCLES_SKIP_TIGHT_COUPLING_INTERACTION] = [1]
        with mockRunLogs.BufferLog() as mock:
            self.o._performTightCoupling(1, 0, writeDB=False)
            self.assertIn("interactAllCoupled disabled this cycle", mock.getStdout())
            self.assertEqual(self.o.r.core.p.coupledIteration, 0)

    def test_performTightCoupling_notConverged(self):
        """Ensure that the appropriate ``runLog.warning`` is addressed in tight coupling reaches max num of iters.

        .. test:: The tight coupling logic can fail if there is no convergence.
            :id: T_ARMI_OPERATOR_PHYSICS0
            :tests: R_ARMI_OPERATOR_PHYSICS
        """

        class NoConverge(TightCoupler):
            def isConverged(self, _val: TightCoupler._SUPPORTED_TYPES) -> bool:
                return False

        class InterfaceNoConverge(Interface):
            name = "NoConverge"

            def __init__(self, r, cs):
                super().__init__(r, cs)
                self.coupler = NoConverge(param="dummy", tolerance=None, maxIters=1)

            def getTightCouplingValue(self):
                return 0.0

        self.o.addInterface(InterfaceNoConverge(None, self.o.cs))
        with mockRunLogs.BufferLog() as mock:
            self.o._performTightCoupling(0, 0, writeDB=False)
            self.assertIn("have not converged! The maximum number of iterations", mock.getStdout())

    def test_performTightCoupling_WriteDB(self):
        """Ensure a tight coupling iteration accours and that a DB WILL be written if requested."""
        hasCouplingInteraction = 1
        with directoryChangers.TemporaryDirectoryChanger():
            with mockRunLogs.BufferLog() as mock:
                self.dbWriteForCoupling(writeDB=True)
                self.assertIn("Writing to database for statepoint:", mock.getStdout())
                self.assertEqual(self.o.r.core.p.coupledIteration, hasCouplingInteraction)

    def test_performTightCoupling_NoWriteDB(self):
        """Ensure a tight coupling iteration accours and that a DB WILL NOT be written if requested."""
        hasCouplingInteraction = 1
        with directoryChangers.TemporaryDirectoryChanger():
            with mockRunLogs.BufferLog() as mock:
                self.dbWriteForCoupling(writeDB=False)
                self.assertNotIn("Writing to database for statepoint:", mock.getStdout())
                self.assertEqual(self.o.r.core.p.coupledIteration, hasCouplingInteraction)

    def dbWriteForCoupling(self, writeDB: bool):
        self.o.removeAllInterfaces()
        dbi = DatabaseInterface(self.o.r, self.o.cs)
        dbi.initDB(fName=self._testMethodName + ".h5")
        self.o.addInterface(dbi)
        self.o._performTightCoupling(0, 0, writeDB=writeDB)
        h5Contents = list(dbi.database.getH5Group(dbi.r).items())
        if writeDB:
            self.assertTrue(h5Contents)
        else:
            self.assertFalse(h5Contents)
        dbi.database.close()

    def test_computeTightCouplingConvergence(self):
        """Ensure that tight coupling convergence can be computed and checked.

        Notes
        -----
        - Assertion #1: ensure that the convergence of Keff, eps, is greater than 1e-5 (the
          prescribed convergence criteria)
        - Assertion #2: ensure that eps is (prevIterKeff - currIterKeff)
        """
        prevIterKeff = 0.9
        currIterKeff = 1.0
        self.o.cs[CONF_TIGHT_COUPLING_SETTINGS] = {"globalFlux": {"parameter": "keff", "convergence": 1e-05}}
        globalFlux = GlobalFluxInterfaceUsingExecuters(self.o.r, self.o.cs)
        globalFlux.coupler.storePreviousIterationValue(prevIterKeff)
        self.o.addInterface(globalFlux)
        # set keff to some new value and compute tight coupling convergence
        self.o.r.core.p.keff = currIterKeff
        self.o._convergenceSummary = collections.defaultdict(list)
        self.assertFalse(self.o._checkTightCouplingConvergence([globalFlux]))
        self.assertAlmostEqual(
            globalFlux.coupler.eps,
            currIterKeff - prevIterKeff,
        )


class CyclesSettingsTests(unittest.TestCase):
    """Check that we can correctly access the various cycle settings from the operator."""

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

    def setUp(self):
        self.standaloneDetailedCS = Settings()
        self.standaloneDetailedCS.loadFromString(self.detailedCyclesSettings)
        self.detailedOperator = Operator(self.standaloneDetailedCS)

    def test_getPowerFractions(self):
        """Test that the power fractions are calculated correctly.

        .. test:: Test the powerFractions are retrieved correctly for multiple cycles.
            :id: T_ARMI_SETTINGS_POWER1
            :tests: R_ARMI_SETTINGS_POWER
        """
        powerFractionsSolution = [
            [0.1, 0.2, 0.3],
            [0.2, 0.2, 0.2, 0.2, 0],
            [0.3, 0.3, 0.3, 0.3, 0.3],
        ]

        self.assertEqual(self.detailedOperator.powerFractions, powerFractionsSolution)
        self.detailedOperator._powerFractions = None
        self.assertEqual(self.detailedOperator.powerFractions, powerFractionsSolution)

    def test_getCycleNames(self):
        cycleNamesSolution = ["startup sequence", None, "prepare for shutdown"]
        self.assertEqual(self.detailedOperator.cycleNames, cycleNamesSolution)

        self.detailedOperator._cycleNames = None
        self.assertEqual(self.detailedOperator.cycleNames, cycleNamesSolution)

    def test_getAvailabilityFactors(self):
        """Check that the "availability factor" is correctly set from the "cycles" setting.

        .. test:: Users can manually control time discretization of the simulation.
            :id: R_ARMI_FW_HISTORY3
            :tests: R_ARMI_FW_HISTORY
        """
        availabilityFactorsSolution = [0.1, 0.5, 1]
        self.assertEqual(self.detailedOperator.availabilityFactors, availabilityFactorsSolution)

        self.detailedOperator._availabilityFactors = None
        self.assertEqual(self.detailedOperator.availabilityFactors, availabilityFactorsSolution)

    def test_getStepLengths(self):
        """Test that the manually-set, detailed time steps are retrievable.

        .. test:: Users can manually control time discretization of the simulation.
            :id: T_ARMI_FW_HISTORY1
            :tests: R_ARMI_FW_HISTORY
        """
        stepLengthsSolution = [
            [1, 1, 1],
            [10 / 5 * 0.5, 10 / 5 * 0.5, 10 / 5 * 0.5, 10 / 5 * 0.5, 10 / 5 * 0.5],
            [3, 3, 3, 3, 3],
        ]

        # detailed step lengths can be set manually
        self.assertEqual(self.detailedOperator.stepLengths, stepLengthsSolution)
        self.detailedOperator._stepLength = None
        self.assertEqual(self.detailedOperator.stepLengths, stepLengthsSolution)

        # when doing detailed step information, we don't get step information from settings
        cs = self.detailedOperator.cs
        self.assertEqual(cs["nCycles"], 3)
        with self.assertRaises(ValueError):
            cs["cycleLength"]
        with self.assertRaises(ValueError):
            cs["burnSteps"]

    def test_getCycleLengths(self):
        """Check that the "cycle length" is correctly set from the "cycles" setting.

        .. test:: Users can manually control time discretization of the simulation.
            :id: R_ARMI_FW_HISTORY4
            :tests: R_ARMI_FW_HISTORY
        """
        cycleLengthsSolution = [30, 10, 15]
        self.assertEqual(self.detailedOperator.cycleLengths, cycleLengthsSolution)

        self.detailedOperator._cycleLengths = None
        self.assertEqual(self.detailedOperator.cycleLengths, cycleLengthsSolution)

    def test_getBurnSteps(self):
        """Check that the "burn steps" is correctly set from the "cycles" setting.

        .. test:: Users can manually control time discretization of the simulation.
            :id: R_ARMI_FW_HISTORY5
            :tests: R_ARMI_FW_HISTORY
        """
        burnStepsSolution = [3, 5, 5]
        self.assertEqual(self.detailedOperator.burnSteps, burnStepsSolution)

        self.detailedOperator._burnSteps = None
        self.assertEqual(self.detailedOperator.burnSteps, burnStepsSolution)

    def test_getMaxBurnSteps(self):
        """Check that the max of the "burn steps" is correctly set from the "cycles" setting.

        .. test:: Users can manually control time discretization of the simulation.
            :id: R_ARMI_FW_HISTORY6
            :tests: R_ARMI_FW_HISTORY
        """
        maxBurnStepsSolution = 5
        self.assertEqual(self.detailedOperator.maxBurnSteps, maxBurnStepsSolution)

        self.detailedOperator._maxBurnSteps = None
        self.assertEqual(self.detailedOperator.maxBurnSteps, maxBurnStepsSolution)


class TestInterfaceAndEventHeaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.o, cls.r = test_reactors.loadTestReactor(
            inputFileName="smallestTestReactor/armiRunSmallest.yaml",
            customSettings={CONF_TIGHT_COUPLING: True},
        )
        cls.r.p.cycle = 0
        cls.r.p.timeNode = 1
        cls.r.p.time = 11.01
        cls.r.core.p.coupledIteration = 7

    def test_expandCycleAndTimeNodeArgs_Empty(self):
        """When cycleNodeInfo should be an empty string."""
        for task in ["Init", "BOL", "EOL"]:
            self.assertEqual(self.o._expandCycleAndTimeNodeArgs(interactionName=task), "")

    def test_expandCycleAndTimeNodeArgs_Cycle(self):
        """When cycleNodeInfo should return only the cycle."""
        for task in ["BOC", "EOC"]:
            self.assertEqual(
                self.o._expandCycleAndTimeNodeArgs(interactionName=task),
                f" - timestep: cycle {self.r.p.cycle}",
            )

    def test_expandCycleAndTimeNodeArgs_EveryNode(self):
        """When cycleNodeInfo should return the cycle and node."""
        self.assertEqual(
            self.o._expandCycleAndTimeNodeArgs(interactionName="EveryNode"),
            f" - timestep: cycle {self.r.p.cycle}, node {self.r.p.timeNode}, year {'{0:.2f}'.format(self.r.p.time)}",
        )

    def test_expandCycleAndTimeNodeArgs_Coupled(self):
        """When cycleNodeInfo should return the cycle, node, and iteration number."""
        self.assertEqual(
            self.o._expandCycleAndTimeNodeArgs(interactionName="Coupled"),
            (
                f" - timestep: cycle {self.r.p.cycle}, node {self.r.p.timeNode}, year "
                f"{'{0:.2f}'.format(self.r.p.time)} - iteration {self.r.core.p.coupledIteration}"
            ),
        )
