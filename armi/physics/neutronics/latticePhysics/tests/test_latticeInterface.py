# Copyright 2021 TerraPower, LLC
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

"""Test the Lattice Interface."""

import unittest
from collections import OrderedDict

from armi import settings
from armi.nuclearDataIO.cccc import isotxs
from armi.operators.operator import Operator
from armi.physics.neutronics import LatticePhysicsFrequency
from armi.physics.neutronics.crossSectionGroupManager import CrossSectionGroupManager
from armi.physics.neutronics.latticePhysics.latticePhysicsInterface import (
    LatticePhysicsInterface,
)
from armi.physics.neutronics.settings import CONF_GEN_XS, CONF_GLOBAL_FLUX_ACTIVE
from armi.reactor.assemblies import (
    HexAssembly,
    grids,
)
from armi.reactor.reactors import Core, Reactor
from armi.reactor.tests.test_blocks import buildSimpleFuelBlock
from armi.tests import ISOAA_PATH, mockRunLogs


# As an interface, LatticePhysicsInterface must be subclassed to be used
class LatticeInterfaceTester(LatticePhysicsInterface):
    def __init__(self, r, cs):
        self.name = "LatticeInterfaceTester"
        super().__init__(r, cs)

    def _getExecutablePath(self):
        return "/tmp/fake_path"

    def readExistingXSLibraries(self, cycle, node):
        pass


class LatticeInterfaceTesterLibFalse(LatticeInterfaceTester):
    """Subclass setting _newLibraryShouldBeCreated = False."""

    def _newLibraryShouldBeCreated(self, cycle, representativeBlockList, xsIDs):
        self.testVerification = True
        return False


class TestLatticePhysicsInterfaceBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # create empty reactor core
        cls.o = Operator(settings.Settings())
        cls.o.r = Reactor("testReactor", None)
        cls.o.r.core = Core("testCore")
        # add an assembly with a single block
        cls.assembly = HexAssembly("testAssembly")
        cls.assembly.spatialGrid = grids.AxialGrid.fromNCells(1)
        cls.assembly.spatialGrid.armiObject = cls.assembly
        cls.assembly.add(buildSimpleFuelBlock())
        # cls.o.r.core.add(assembly)
        # init and add interfaces
        cls.xsGroupInterface = CrossSectionGroupManager(cls.o.r, cls.o.cs)
        cls.o.addInterface(cls.xsGroupInterface)


class TestLatticePhysicsInterface(TestLatticePhysicsInterfaceBase):
    """Test Lattice Physics Interface."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.latticeInterface = LatticeInterfaceTesterLibFalse(cls.o.r, cls.o.cs)
        cls.o.addInterface(cls.latticeInterface)

    def setUp(self):
        self.o.r.core.lib = "Nonsense"
        self.latticeInterface.testVerification = False

    def test_includeGammaXS(self):
        """Test that we can correctly flip the switch to calculate gamma XS."""
        # The default operator here turns off Gamma XS generation
        self.assertFalse(self.latticeInterface.includeGammaXS)
        self.assertEqual(self.o.cs[CONF_GLOBAL_FLUX_ACTIVE], "Neutron")

        # but we can create an operator that turns on Gamma XS generation
        cs = settings.Settings().modified(newSettings={CONF_GLOBAL_FLUX_ACTIVE: "Neutron and Gamma"})
        newOperator = Operator(cs)
        newLatticeInterface = LatticeInterfaceTesterLibFalse(newOperator.r, cs)
        self.assertTrue(newLatticeInterface.includeGammaXS)
        self.assertEqual(cs[CONF_GLOBAL_FLUX_ACTIVE], "Neutron and Gamma")

    def test_latticePhysicsInterface(self):
        """Super basic test of the LatticePhysicsInterface."""
        self.assertEqual(self.latticeInterface._updateBlockNeutronVelocities, True)
        self.assertEqual(self.latticeInterface.executablePath, "/tmp/fake_path")
        self.assertEqual(self.latticeInterface.executableRoot, "/tmp")
        self.latticeInterface.updateXSLibrary(0)
        self.assertEqual(len(self.latticeInterface._oldXsIdsAndBurnup), 0)

    def test_interactBOL(self):
        """
        Test interactBOL() with different update frequencies.

        Notes
        -----
        Unlike other interactions, self.o.r.core.lib is not set to None at BOC, so this test uses
        self.testVerification instead.
        """
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.never
        self.latticeInterface.interactBOL()
        self.assertFalse(self.latticeInterface.testVerification)
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.everyNode
        self.latticeInterface.interactBOL()
        self.assertFalse(self.latticeInterface.testVerification)
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.BOL
        self.latticeInterface.interactBOL()
        self.assertTrue(self.latticeInterface.testVerification)

    def test_interactBOC(self):
        """
        Test interactBOC() with different update frequencies.

        Notes
        -----
        Unlike other interactions, self.o.r.core.lib is not set to None at BOC, so this test uses
        self.testVerification instead.
        """
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.BOL
        self.latticeInterface.interactBOC()
        self.assertFalse(self.latticeInterface.testVerification)
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.everyNode
        self.latticeInterface.interactBOC()
        self.assertFalse(self.latticeInterface.testVerification)
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.BOC
        self.latticeInterface.interactBOC()
        self.assertTrue(self.latticeInterface.testVerification)

    def test_interactEveryNode(self):
        """Test interactEveryNode() with different update frequencies."""
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.BOC
        self.latticeInterface.interactEveryNode()
        self.assertEqual(self.o.r.core.lib, "Nonsense")
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.everyNode
        self.latticeInterface.interactEveryNode()
        self.assertIsNone(self.o.r.core.lib)

    def test_interactEveryNodeWhenCoupled(self):
        """
        Test that the XS lib is not cleared when coupled iterations are turned on
        and XS will be generated during the coupled iterations.
        """
        self.o.couplingIsActive = lambda: True
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.firstCoupledIteration
        self.latticeInterface.interactEveryNode()
        self.assertEqual(self.o.r.core.lib, "Nonsense")

        self.o.couplingIsActive = lambda: False
        self.latticeInterface.interactEveryNode()
        self.assertIsNone(self.o.r.core.lib)

    def test_interactEveryNodeWhenCoupledButNot(self):
        """
        Test that the XS lib is cleared when coupled iterations are turned on
        but the lattice physics frequency is not high enough.
        """
        self.o.couplingIsActive = lambda: True
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.firstCoupledIteration
        self.latticeInterface.interactEveryNode()
        self.assertEqual(self.o.r.core.lib, "Nonsense")

        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.everyNode
        self.latticeInterface.interactEveryNode()
        self.assertIsNone(self.o.r.core.lib)

    def test_interactEveryNodeFirstCoupled(self):
        """Test interactEveryNode() with LatticePhysicsFrequency.firstCoupledIteration."""
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.firstCoupledIteration
        self.latticeInterface.interactEveryNode()
        self.assertIsNone(self.o.r.core.lib)

    def test_interactEveryNodeAll(self):
        """Test interactEveryNode() with LatticePhysicsFrequency.all."""
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.all
        self.latticeInterface.interactEveryNode()
        self.assertIsNone(self.o.r.core.lib)

    def test_interactFirstCoupledIteration(self):
        """Test interactCoupled() with different update frequencies on first iteration."""
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.everyNode
        self.latticeInterface.interactCoupled(iteration=0)
        self.assertEqual(self.o.r.core.lib, "Nonsense")
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.firstCoupledIteration
        self.latticeInterface.interactCoupled(iteration=0)
        self.assertIsNone(self.o.r.core.lib)

    def test_interactAll(self):
        """Test interactCoupled() with different update frequencies on non-first iteration."""
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.firstCoupledIteration
        self.latticeInterface.interactCoupled(iteration=1)
        self.assertEqual(self.o.r.core.lib, "Nonsense")
        self.latticeInterface._latticePhysicsFrequency = LatticePhysicsFrequency.all
        self.latticeInterface.interactCoupled(iteration=1)
        self.assertIsNone(self.o.r.core.lib)

    def test_getSuffix(self):
        self.assertEqual(self.latticeInterface._getSuffix(7), "")


class TestLatticePhysicsLibraryCreation(TestLatticePhysicsInterfaceBase):
    """Test variations of _newLibraryShouldBeCreated."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.latticeInterface = LatticeInterfaceTester(cls.o.r, cls.o.cs)
        cls.o.addInterface(cls.latticeInterface)
        cls.xsGroupInterface.representativeBlocks = OrderedDict({"AA": cls.assembly[0]})
        cls.b, cls.xsIDs = cls.latticeInterface._getBlocksAndXsIds()

    def setUp(self):
        """Reset representativeBlocks and CONF_GEN_XS."""
        self.xsGroupInterface.representativeBlocks = OrderedDict({"AA": self.assembly[0]})
        self.assembly[0].p.xsType = "A"
        self.o.cs[CONF_GEN_XS] = ""
        self.o.r.core.lib = isotxs.readBinary(ISOAA_PATH)

    def test_libCreation_NoGenXS(self):
        """No ISOTXS and xs gen not requested."""
        self.o.r.core.lib = None
        with mockRunLogs.BufferLog() as mock:
            xsGen = self.latticeInterface._newLibraryShouldBeCreated(1, self.b, self.xsIDs)
            self.assertIn("Cross sections will not be generated on cycle 1.", mock.getStdout())
            self.assertFalse(xsGen)

    def test_libCreation_GenXS(self):
        """No ISOTXS and xs gen requested."""
        self.o.cs[CONF_GEN_XS] = "Neutron"
        self.o.r.core.lib = None
        with mockRunLogs.BufferLog() as mock:
            xsGen = self.latticeInterface._newLibraryShouldBeCreated(1, self.b, self.xsIDs)
            self.assertIn(
                "Cross sections will be generated on cycle 1 for the following XS IDs: ['AA']",
                mock.getStdout(),
            )
            self.assertTrue(xsGen)

    def test_libCreation_NoGenXS_2(self):
        """ISOTXS present and has all of the necessary information."""
        with mockRunLogs.BufferLog() as mock:
            xsGen = self.latticeInterface._newLibraryShouldBeCreated(1, self.b, self.xsIDs)
            self.assertIn(
                "The generation of XS will be skipped.",
                mock.getStdout(),
            )
            self.assertFalse(xsGen)

    def test_libCreation_GenXS_2(self):
        """ISOTXS present and does not have all of the necessary information."""
        self.xsGroupInterface.representativeBlocks = OrderedDict({"BB": self.assembly[0]})
        b, xsIDs = self._modifyXSType()
        with mockRunLogs.BufferLog() as mock:
            xsGen = self.latticeInterface._newLibraryShouldBeCreated(1, b, xsIDs)
            self.assertIn(
                "is not enabled, but will be run to generate these missing cross sections.",
                mock.getStdout(),
            )
            self.assertTrue(xsGen)

    def test_libCreation_GenXS_3(self):
        """ISOTXS present and does not have all of the necessary information."""
        self.o.cs[CONF_GEN_XS] = "Neutron"
        b, xsIDs = self._modifyXSType()
        with mockRunLogs.BufferLog() as mock:
            xsGen = self.latticeInterface._newLibraryShouldBeCreated(1, b, xsIDs)
            self.assertIn("These will be generated on cycle ", mock.getStdout())
            self.assertTrue(xsGen)

    def _modifyXSType(self):
        self.xsGroupInterface.representativeBlocks = OrderedDict({"BB": self.assembly[0]})
        self.assembly[0].p.xsType = "B"
        return self.latticeInterface._getBlocksAndXsIds()
