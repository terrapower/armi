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

"""Test the Lattice Physics Writer."""

import unittest
from collections import defaultdict

from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.physics.neutronics.fissionProductModel.fissionProductModelSettings import (
    CONF_FP_MODEL,
)
from armi.physics.neutronics.latticePhysics.latticePhysicsInterface import (
    setBlockNeutronVelocities,
)
from armi.physics.neutronics.latticePhysics.latticePhysicsWriter import (
    LatticePhysicsWriter,
)
from armi.physics.neutronics.settings import (
    CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION,
    CONF_XS_BLOCK_REPRESENTATION,
)
from armi.testing import loadTestReactor
from armi.tests import TEST_ROOT


class FakeLatticePhysicsWriter(LatticePhysicsWriter):
    """LatticePhysicsWriter is abstract, so it must be subclassed to be tested."""

    def __init__(self, block, r, eci):
        self.testOut = ""
        super(FakeLatticePhysicsWriter, self).__init__(block, r, eci, "", False)

    def write(self):
        pass

    def _writeNuclide(self, fileObj, nuclide, density, nucTemperatureInC, category, xsIdSpecified=None):
        pass

    def _writeComment(self, fileObj, msg):
        self.testOut += "\n" + str(msg)

    def _writeGroupStructure(self, fileObj):
        pass


class TestLatticePhysicsWriter(unittest.TestCase):
    """Test Lattice Physics Writer."""

    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT)
        self.cs = self.o.cs
        self.cs[CONF_CROSS_SECTION].setDefaults(
            self.cs[CONF_XS_BLOCK_REPRESENTATION],
            self.cs[CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION],
        )
        self.block = self.r.core.getFirstBlock()
        self.w = FakeLatticePhysicsWriter(self.block, self.r, self.o)

    def test_setBlockNeutronVelocities(self):
        d = defaultdict(float)
        d["AA"] = 10.0
        setBlockNeutronVelocities(self.r, d)
        tot = sum([b.p.mgNeutronVelocity for b in self.r.core.iterBlocks()])
        self.assertGreater(tot, 3000.0)

    def test_latticePhysicsWriter(self):
        """Super basic test of the LatticePhysicsWriter."""
        self.assertEqual(self.w.xsId, "AA")
        self.assertFalse(self.w.modelFissionProducts)
        self.assertEqual(self.w.driverXsID, "")
        self.assertAlmostEqual(self.w.minimumNuclideDensity, 1e-15, delta=1e-16)

        self.assertEqual(self.w.testOut, "")
        self.assertEqual(str(self.w), "<FakeLatticePhysicsWriter - XS ID AA (Neutron XS)>")

        self.w._writeTitle(None)
        self.assertIn("ARMI generated case for caseTitle armiRun", self.w.testOut)

        nucs = self.w._getAllNuclidesByTemperatureInC(None)
        self.assertEqual(len(nucs.keys()), 1)
        self.assertAlmostEqual(list(nucs.keys())[0], 450.0, delta=0.1)

    def test_writeTitle(self):
        self.w._writeTitle("test_writeTitle")
        self.assertIn("ARMI generated case for caseTitle", self.w.testOut)

    def test_isSourceDriven(self):
        self.assertFalse(self.w._isSourceDriven)
        self.w.driverXsID = True
        self.assertTrue(self.w._isSourceDriven)

    def test_isGammaXSGenerationEnabled(self):
        self.assertFalse(self.w._isGammaXSGenerationEnabled)

    def test_getAllNuclidesByTemperatureInCNone(self):
        nucsByTemp = self.w._getAllNuclidesByTemperatureInC(None)
        keys0 = list(nucsByTemp.keys())
        self.assertEqual(len(keys0), 1)
        self.assertEqual(keys0[0], 450.0)
        keys1 = nucsByTemp[keys0[0]]
        self.assertGreater(len(keys1), 1)
        names = [k.name for k in keys1]
        self.assertIn("AM241", names)
        self.assertIn("U238", names)

    def test_getAllNuclidesByTemperatureInC(self):
        self.w.explicitFissionProducts = False
        c = self.r.core[0][0]
        nucsByTemp = self.w._getAllNuclidesByTemperatureInC(c)
        keys0 = list(nucsByTemp.keys())
        self.assertEqual(len(keys0), 1)
        self.assertEqual(keys0[0], 450.0)
        keys1 = nucsByTemp[keys0[0]]
        self.assertGreater(len(keys1), 1)
        names = [k.name for k in keys1]
        self.assertIn("AM241", names)
        self.assertIn("U238", names)

    def test_getAllNuclidesByTempInCExplicitFisProd(self):
        self.w.explicitFissionProducts = True
        c = self.r.core[0][0]
        nucsByTemp = self.w._getAllNuclidesByTemperatureInC(c)
        keys0 = list(nucsByTemp.keys())
        self.assertEqual(len(keys0), 1)
        self.assertEqual(keys0[0], 450.0)
        keys1 = nucsByTemp[keys0[0]]
        self.assertGreater(len(keys1), 1)
        names = [k.name for k in keys1]
        self.assertIn("AM241", names)
        self.assertIn("U238", names)

    def test_getAvgNuclideTemperatureInC(self):
        temp = self.w._getAvgNuclideTemperatureInC("U238")
        self.assertAlmostEqual(temp, 450, delta=0.001)

        temp = self.w._getAvgNuclideTemperatureInC("U235")
        self.assertAlmostEqual(temp, 450, delta=0.001)

    def test_getFuelTemperature(self):
        temp = self.w._getFuelTemperature()
        self.assertAlmostEqual(temp, 450, delta=0.001)

    def test_getDetailedFissionProducts(self):
        dfpDen = defaultdict(int)
        dfpDen["U238"] = 1.2
        dfpDen["U235"] = 2.3
        dfpDen["AM241"] = 3.4
        prods = self.w._getDetailedFissionProducts(dfpDen)
        self.assertEqual(len(prods), 3)
        self.assertIn("U238", prods)
        self.assertIn("U235", prods)
        self.assertIn("AM241", prods)

    def test_getDetailedFissionProductsPass(self):
        self.cs[CONF_FP_MODEL] = "noFissionProducts"

        prods = self.w._getDetailedFissionProducts({})
        self.assertEqual(len(prods), 0)

    def test_getDetailedFPDensities(self):
        self.w.modelFissionProducts = False
        dens = self.w._getDetailedFPDensities()
        self.assertEqual(len(dens), 0)

        self.w.modelFissionProducts = True
        with self.assertRaises(AttributeError):
            dens = self.w._getDetailedFPDensities()

    def test_isCriticalBucklingSearchActive(self):
        isActive = self.w._isCriticalBucklingSearchActive
        self.assertTrue(isActive)

    def test_getDriverBlock(self):
        self.w.driverXsID = ""
        b = self.w._getDriverBlock()
        self.assertIsNone(b)
        self.w.driverXsID = "AA"
        with self.assertRaises(ValueError):
            b = self.w._getDriverBlock()
