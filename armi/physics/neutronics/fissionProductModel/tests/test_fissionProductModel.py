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
"""
Test the fission product module to ensure all FP are available.
"""
import unittest

from armi.physics.neutronics.fissionProductModel import fissionProductModel
from armi.reactor.tests.test_reactors import buildOperatorOfEmptyHexBlocks

from armi.physics.neutronics.fissionProductModel.tests import test_lumpedFissionProduct


def _getLumpedFissionProductNumberDensities(b):
    """Returns the number densities for each lumped fission product in a block."""
    nDens = {}
    for lfpName, lfp in b.getLumpedFissionProductCollection().items():
        nDens[lfp] = b.getNumberDensity(lfpName)
    return nDens


class TestFissionProductModelLumpedFissionProducts(unittest.TestCase):
    """
    Tests the fission product model interface behavior when lumped fission products are enabled.

    Notes
    -----
    This loads the global fission products from a file stream.
    """

    def setUp(self):
        o = buildOperatorOfEmptyHexBlocks()
        o.removeAllInterfaces()
        self.fpModel = fissionProductModel.FissionProductModel(o.r, o.cs)
        o.addInterface(self.fpModel)

        # Load the fission products from a file stream.
        dummyLFPs = test_lumpedFissionProduct.getDummyLFPFile()
        self.fpModel.setGlobalLumpedFissionProducts(dummyLFPs.createLFPsFromFile())

        # Set up the global LFPs and check that they are setup.
        self.fpModel.setAllBlockLFPs()
        self.assertTrue(self.fpModel._useGlobalLFPs)

    def test_loadGlobalLFPsFromFile(self):
        """Tests that loading lumped fission products from a file."""
        self.assertEqual(len(self.fpModel._globalLFPs), 3)
        lfps = self.fpModel.getGlobalLumpedFissionProducts()
        self.assertIn("LFP39", lfps)

    def test_getAllFissionProductNames(self):
        """Tests retrieval of the fission product names within all the lumped fission products of the core."""
        fissionProductNames = self.fpModel.getAllFissionProductNames()
        self.assertGreater(len(fissionProductNames), 5)
        self.assertIn("XE135", fissionProductNames)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
