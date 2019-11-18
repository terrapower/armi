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
"""Tests for block blueprints."""
import unittest
import io

from armi.reactor import blueprints
from armi import settings
from armi.physics.neutronics import isotopicDepletion
from armi.reactor.flags import Flags

FULL_BP = """
blocks:
    fuel: &block_fuel
        grid name: fuelgrid
        fuel:
            shape: Circle
            material: UZr
            Tinput: 25.0
            Thot: 600.0
            id: 0.0
            od: 0.86602
            latticeIDs: [1]
        clad:
            shape: Circle
            material: HT9
            Tinput: 25.0
            Thot: 470.0
            id: 1.0
            od: 1.09
            latticeIDs: [1,2]
        coolant:
            shape: DerivedShape
            material: Sodium
            Tinput: 450.0
            Thot: 450.0
        duct:
            shape: Hexagon
            material: HT9
            Tinput: 25.0
            Thot: 450.0
            ip: 16.0
            mult: 1.0
            op: 16.6
        intercoolant:
            shape: Hexagon
            material: Sodium
            Tinput: 450.0
            Thot: 450.0
            ip: duct.op
            mult: 1.0
            op: 16.75
assemblies:
    fuel:
        specifier: IC
        blocks:  [*block_fuel, *block_fuel]
        height: [25.0, 25.0]
        axial mesh points:  [1, 1]
        material modifications:
            U235_wt_frac: [0.11, 0.11]
            ZR_wt_frac:  [0.06, 0.06]
        xs types: [A, A]
grids:
    fuelgrid:
       geom: hex
       symmetry: full
       lattice map: |
         - - -  1 1 1 1
           - - 1 1 2 1 1
            - 1 1 1 1 1 1
             1 3 1 2 1 3 1
              1 1 1 1 1 1
               1 1 2 1 1
                1 1 1 1

"""


class TestGriddedBlock(unittest.TestCase):
    """Tests for a block that has components in a lattice."""

    def setUp(self):
        self.cs = settings.Settings()
        isotopicDepletion.applyDefaultBurnChain()

        with io.StringIO(FULL_BP) as stream:
            self.blueprints = blueprints.Blueprints.load(stream)
            self.blueprints._prepConstruction(self.cs)

    def test_constructSpatialGrid(self):
        """Test intermediate grid construction function"""
        bDesign = self.blueprints.blockDesigns["fuel"]
        gridDesign = bDesign._getGridDesign(self.blueprints)
        self.assertEqual(gridDesign.gridContents[0, 0], "2")

    def test_getLocatorsAtLatticePositions(self):
        """Ensure extraction of specifiers results in locators"""
        bDesign = self.blueprints.blockDesigns["fuel"]
        gridDesign = bDesign._getGridDesign(self.blueprints)
        grid = gridDesign.construct()
        locators = gridDesign.getLocators(grid, ["2"])
        self.assertEqual(len(locators), 3)
        self.assertIs(grid[locators[0].getCompleteIndices()], locators[0])

    def test_blockLattice(self):
        """Make sure constructing a block with grid specifiers works as a whole."""
        aDesign = self.blueprints.assemDesigns.bySpecifier["IC"]
        a = aDesign.construct(self.cs, self.blueprints)
        fuelBlock = a.getFirstBlock(Flags.FUEL)
        fuel = fuelBlock.getComponent(Flags.FUEL)
        self.assertTrue(fuel.spatialLocator)
        seen = False
        for locator in fuel.spatialLocator:
            if locator == (1, 0, 0):
                seen = True
        self.assertTrue(seen)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
