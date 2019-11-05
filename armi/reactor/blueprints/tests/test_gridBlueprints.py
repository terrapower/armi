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
"""Tests for grid blueprints."""
import unittest

from armi.reactor.blueprints import gridBlueprint

LATTICE_BLUEPRINT = """
control:
    geom: hex
    symmetry: full
    lattice map: |
       - - - - - - - - - 1 1 1 1 1 1 1 1 1 4
        - - - - - - - - 1 1 1 1 1 1 1 1 1 1 1
         - - - - - - - 1 8 1 1 1 1 1 1 1 1 1 1
          - - - - - - 1 1 1 1 1 1 1 1 1 1 1 1 1
           - - - - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1
            - - - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
             - - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
              - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
               - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                7 1 1 1 1 1 1 1 1 0 1 1 1 1 1 1 1 1 1
                 1 1 1 1 1 1 1 1 2 1 1 1 1 1 1 1 1 1
                  1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                   1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                    1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                     1 1 1 1 1 1 1 1 1 1 1 1 1 1
                      1 1 1 1 1 1 1 1 1 3 1 1 1
                       1 1 1 1 1 1 1 1 1 1 1 1
                        1 6 1 1 1 1 1 1 1 1 1
                         1 1 1 1 1 1 1 1 1 1

sfp:
    geom: cartesian
    symmetry: full
    lattice map: |
        2 2 2 2 2
        2 1 1 1 2
        2 1 3 1 2
        2 3 1 1 2
        2 2 2 2 2
"""


class TestGridBlueprintsSection(unittest.TestCase):
    """Tests for lattice blueprint section."""

    def setUp(self):
        self.grids = gridBlueprint.Grids.load(
            LATTICE_BLUEPRINT.format(self._testMethodName)
        )

    def test_simple_read(self):
        gridDesign = self.grids["control"]
        _grid = gridDesign.construct()
        self.assertEqual(gridDesign.gridContents[0, -8], "6")

        gridDesign2 = self.grids["sfp"]
        _grid = gridDesign2.construct()
        self.assertEqual(gridDesign2.gridContents[1, 1], "3")


if __name__ == "__main__":
    unittest.main()
