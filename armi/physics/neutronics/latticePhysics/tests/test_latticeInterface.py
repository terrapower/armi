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

import unittest

from armi.physics.neutronics.latticePhysics.latticePhysicsInterface import (
    LatticePhysicsInterface,
)
from armi.reactor.tests.test_reactors import loadTestReactor
from armi.settings import Settings


# As an interface, LatticePhysicsInterface must be subclassed to be used
class LatticeInterfaceTester(LatticePhysicsInterface):
    def __init__(self, r, cs):
        self.name = "LatticeInterfaceTester"
        super(LatticeInterfaceTester, self).__init__(r, cs)

    def _getExecutablePath(self):
        return "/tmp/fake_path"

    def readExistingXSLibraries(self, cycle):
        pass


class TestLatticePhysicsInterface(unittest.TestCase):
    """Test Lattice Physics Interface."""

    def test_LatticePhysicsInterface(self):
        """Super basic test of the LatticePhysicsInterface"""
        cs = Settings()
        _o, r = loadTestReactor()
        i = LatticeInterfaceTester(r, cs)

        self.assertEqual(i._HEX_MODEL.strip(), "hex")
        self.assertEqual(i.executablePath, "/tmp/fake_path")
        self.assertEqual(i.executableRoot, "/tmp")

        i.updateXSLibrary(0)
        self.assertEqual(len(i._oldXsIdsAndBurnup), 0)


if __name__ == "__main__":
    unittest.main()
