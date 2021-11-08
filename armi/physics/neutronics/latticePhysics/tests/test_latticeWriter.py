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

"""Test the Lattice Physics Writer"""

import os
import unittest

from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.physics.neutronics.latticePhysics.latticePhysicsWriter import (
    LatticePhysicsWriter,
)
from armi.reactor.tests.test_reactors import loadTestReactor
from armi.tests import TEST_ROOT


class FakeLatticePhysicsWriter(LatticePhysicsWriter):
    """LatticePhysicsWriter is abstract, so it must be subclassed to be tested"""

    def __init__(self, block, r, eci):
        self.testOut = ""
        super(FakeLatticePhysicsWriter, self).__init__(block, r, eci, "", False)

    def write(self):
        pass

    def _writeNuclide(
        self, fileObj, nuclide, density, nucTemperatureInC, category, xsIdSpecified=None
    ):
        pass

    def _writeComment(self, fileObj, msg):
        self.testOut += "\n" + str(msg)

    def _writeGroupStructure(self, fileObj):
        pass


class TestLatticePhysicsWriter(unittest.TestCase):
    """Test Lattice Physics Writer."""

    def test_LatticePhysicsWriter(self):
        """Super basic test of the LatticePhysicsWriter"""
        o, r = loadTestReactor(TEST_ROOT)
        cs = o.cs
        o.cs[CONF_CROSS_SECTION].setDefaults(
            cs["xsBlockRepresentation"], cs["disableBlockTypeExclusionInXsGeneration"]
        )
        block = r.core.getFirstBlock()
        w = FakeLatticePhysicsWriter(block, r, o)

        self.assertEqual(w.xsId, "AA")
        self.assertFalse(w.modelFissionProducts)
        self.assertEqual(w.driverXsID, "")
        self.assertAlmostEqual(w.minimumNuclideDensity, 1e-15, delta=1e-16)

        self.assertEqual(w.testOut, "")
        self.assertEqual(str(w), "<FakeLatticePhysicsWriter - XS ID AA (Neutron XS)>")

        w._writeTitle(None)
        self.assertIn("ARMI generated case for caseTitle armiRun", w.testOut)

        nucs = w._getAllNuclidesByTemperatureInC(None)
        self.assertEqual(len(nucs.keys()), 1)
        self.assertAlmostEqual(list(nucs.keys())[0], 450.0, delta=0.1)


if __name__ == "__main__":
    unittest.main()
