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
        # pylint: disable = protected-access
        self.assertEqual(len(self.fpModel._globalLFPs), 3)
        lfps = self.fpModel.getGlobalLumpedFissionProducts()
        self.assertIn("LFP39", lfps)

    def test_getAllFissionProductNames(self):
        # pylint: disable = protected-access
        fissionProductNames = self.fpModel.getAllFissionProductNames()
        self.assertGreater(len(fissionProductNames), 5)
        self.assertIn("XE135", fissionProductNames)
        
    def test_removeGaseousFissionProductsLFP(self):
        gasRemovalFractions = {}
        for b in self.r.core.getBlocks():
            
        
        self.fpModel.removeFissionGasesFromBlocks()


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
