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

"""Test the Lattice Interface"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import unittest

from armi.physics.neutronics.latticePhysics.latticePhysicsInterface import (
    LatticePhysicsInterface,
)
from armi import settings
from armi.settings.fwSettings.globalSettings import CONF_RUN_TYPE
from armi.operators.operator import Operator
from armi.reactor.reactors import Reactor, Core
from armi.physics.neutronics.crossSectionGroupManager import CrossSectionGroupManager

# As an interface, LatticePhysicsInterface must be subclassed to be used
class LatticeInterfaceTester(LatticePhysicsInterface):
    def __init__(self, r, cs):
        self.name = "LatticeInterfaceTester"
        super().__init__(r, cs)

    def _getExecutablePath(self):
        return "/tmp/fake_path"

    def readExistingXSLibraries(self, cycle):
        pass

    def _newLibraryShouldBeCreated(self, cycle, representativeBlockList, xsIDs):
        return False


class TestLatticePhysicsInterface(unittest.TestCase):
    """Test Lattice Physics Interface."""

    @classmethod
    def setUpClass(cls):
        cls.o = Operator(settings.Settings())
        cls.o.r = Reactor("empty", None)
        cls.o.r.core = Core("empty")
        xsGroupInterface = CrossSectionGroupManager(cls.o.r, cls.o.cs)
        cls.latticeInterface = LatticeInterfaceTester(cls.o.r, cls.o.cs)
        cls.o.addInterface(xsGroupInterface)
        cls.o.addInterface(cls.latticeInterface)

    def setUp(self):
        self.o.r.core.lib = "Nonsense"

    def test_LatticePhysicsInterface(self):
        """Super basic test of the LatticePhysicsInterface"""
        self.assertEqual(self.latticeInterface._HEX_MODEL.strip(), "hex")
        self.assertEqual(self.latticeInterface.executablePath, "/tmp/fake_path")
        self.assertEqual(self.latticeInterface.executableRoot, "/tmp")

        self.latticeInterface.updateXSLibrary(0)
        self.assertEqual(len(self.latticeInterface._oldXsIdsAndBurnup), 0)

    def test_interactCoupled_Snapshots(self):
        """should change self.o.r.core.lib from Nonesense to None"""
        self.o.cs[CONF_RUN_TYPE] = "Snapshots"
        self.latticeInterface.interactCoupled(iteration=0)
        self.assertIsNone(self.o.r.core.lib)
        # reset runtype
        self.o.cs[CONF_RUN_TYPE] = "Standard"

    def test_interactCoupled_TimeNode0(self):
        """make sure updateXSLibrary is run"""
        self.latticeInterface.interactCoupled(iteration=0)
        self.assertIsNone(self.o.r.core.lib)

    def test_interactCoupled_TimeNode1(self):
        """make sure updateXSLibrary is NOT run"""
        self.o.r.p.timeNode = 1
        self.latticeInterface.interactCoupled(iteration=0)
        self.assertEqual(self.o.r.core.lib, "Nonsense")


if __name__ == "__main__":
    unittest.main()
