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
    for lfp in b.getLumpedFissionProductCollection():
        nDens[lfp] = b.getNumberDensity(lfp.name)
    return nDens

class TestFissionProductModel(unittest.TestCase):
    """
    Test for the fission product model, ensures LFP model contains appropriate FPs.
    """

    def setUp(self):
        o = buildOperatorOfEmptyHexBlocks()
        self.fpModel = fissionProductModel.FissionProductModel(o.r, o.cs)
        o.removeAllInterfaces()
        o.addInterface(self.fpModel)
        dummyLFPs = test_lumpedFissionProduct.getDummyLFPFile()
        self.fpModel.setGlobalLumpedFissionProducts(dummyLFPs.createLFPsFromFile())
        self.fpModel.setAllBlockLFPs()

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
        
    def test_removeGaseousFissionProductsLFP(self):
        """Tests removal of gaseous fission products globally in the core."""
        gasRemovalFractions = {}
        previousBlockFissionProductNumberDensities = {}
        updatedBlockFissionProductNumberDensities = {}
        for b in self.r.core.getBlocks():
            lfpCollection = b.getLumpedFissionProductCollection()
            if lfpCollection is None:
                continue
            
            previousBlockFissionProductNumberDensities[b] = _getLumpedFissionProductNumberDensities(b)
            gasRemovalFractions = {b: 0.1}
        
        self.fpModel.removeFissionGasesFromBlocks(gasRemovalFractions)
        for b in self.r.core.getBlocks():
            lfpCollection = b.getLumpedFissionProductCollection()
            if lfpCollection is None:
                continue
            
            updatedBlockFissionProductNumberDensities[b] = _getLumpedFissionProductNumberDensities(b)
            for lfp in lfpCollection:
                old = previousBlockFissionProductNumberDensities[b][lfp]
                new = updatedBlockFissionProductNumberDensities[b][lfp]
                self.assertAlmostEqual(new, old * (1.0 - gasRemovalFractions[b]))
            
        
        
    def test_removeGaseousFissionProductsLFPFailure(self):
        """Tests failure when the gaseous removal fractions are out of range."""
        


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
