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
import io
import unittest

import armi

if not armi.isConfigured():
    armi.configure()
from armi.reactor.blueprints import gridBlueprint
from armi.reactor import geometry

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

RZT_BLUEPRINT = """
rzt_core:
    geom: thetarz
    symmetry: eighth core periodic
    grid bounds:
        r:
            - 0.0
            - 14.2857142857
            - 28.5714285714
            - 42.8571428571
            - 57.1428571429
            - 71.4285714286
            - 85.7142857143
            - 100.001
            - 115.001
            - 130.001
        theta:
            - 0.0
            - 0.11556368446681414
            - 0.2311273689343264
            - 0.34669105340061696
            - 0.43870710999683127
            - 0.5542707944631219
            - 0.6698344789311578
            - 0.7853981633974483
    grid contents:
        [0,0]: assembly1_1 fuel
        [0,1]: assembly1_2 fuel
        [0,2]: assembly1_3 fuel
        [0,3]: assembly1_4 fuel
        [0,4]: assembly1_5 fuel
        [0,5]: assembly1_6 fuel
        [0,6]: assembly1_7 fuel

        [1,0]: assembly2_1 fuel
        [1,1]: assembly2_2 fuel
        [1,2]: assembly2_3 fuel
        [1,3]: assembly2_4 fuel
        [1,4]: assembly2_5 fuel
        [1,5]: assembly2_6 fuel
        [1,6]: assembly2_7 fuel

        [2,0]: assembly3_1 fuel
        [2,1]: assembly3_2 fuel
        [2,2]: assembly3_3 fuel
        [2,3]: assembly3_4 fuel
        [2,4]: assembly3_5 fuel
        [2,5]: assembly3_6 fuel
        [2,6]: assembly3_7 fuel

        [3,0]: assembly4_1 fuel
        [3,1]: assembly4_2 fuel
        [3,2]: assembly4_3 fuel
        [3,3]: assembly4_4 fuel
        [3,4]: assembly4_5 fuel
        [3,5]: assembly4_6 fuel
        [3,6]: assembly4_7 fuel

        [4,0]: assembly5_1 fuel
        [4,1]: assembly5_2 fuel
        [4,2]: assembly5_3 fuel
        [4,3]: assembly5_4 fuel
        [4,4]: assembly5_5 fuel
        [4,5]: assembly5_6 fuel
        [4,6]: assembly5_7 fuel

        [5,0]: assembly6_1 fuel
        [5,1]: assembly6_2 fuel
        [5,2]: assembly6_3 fuel
        [5,3]: assembly6_4 fuel
        [5,4]: assembly6_5 fuel
        [5,5]: assembly6_6 fuel
        [5,6]: assembly6_7 fuel

        [6,0]: assembly7_1 fuel
        [6,1]: assembly7_2 fuel
        [6,2]: assembly7_3 fuel
        [6,3]: assembly7_4 fuel
        [6,4]: assembly7_5 fuel
        [6,5]: assembly7_6 fuel
        [6,6]: assembly7_7 fuel

        [7,0]: assembly8_1 fuel
        [7,1]: assembly8_2 fuel
        [7,2]: assembly8_3 fuel
        [7,3]: assembly8_4 fuel
        [7,4]: assembly8_5 fuel
        [7,5]: assembly8_6 fuel
        [7,6]: assembly8_7 fuel

        [8,0]: assembly9_1 fuel
        [8,1]: assembly9_2 fuel
        [8,2]: assembly9_3 fuel
        [8,3]: assembly9_4 fuel
        [8,4]: assembly9_5 fuel
        [8,5]: assembly9_6 fuel
        [8,6]: assembly9_7 fuel
"""

RTH_GEOM = """
<reactor geom="ThetaRZ" symmetry="eighth core periodic">
    <assembly azimuthalMesh="4" name="assembly1_1 fuel" rad1="0.0" rad2="14.2857142857" radialMesh="4" theta1="0.0" theta2="0.11556368446681414" />
    <assembly azimuthalMesh="4" name="assembly1_2 fuel" rad1="0.0" rad2="14.2857142857" radialMesh="4" theta1="0.11556368446681414" theta2="0.2311273689343264" />
    <assembly azimuthalMesh="4" name="assembly1_3 fuel" rad1="0.0" rad2="14.2857142857" radialMesh="4" theta1="0.2311273689343264" theta2="0.34669105340061696" />
    <assembly azimuthalMesh="4" name="assembly1_4 fuel" rad1="0.0" rad2="14.2857142857" radialMesh="4" theta1="0.34669105340061696" theta2="0.43870710999683127" />
    <assembly azimuthalMesh="4" name="assembly1_5 fuel" rad1="0.0" rad2="14.2857142857" radialMesh="4" theta1="0.43870710999683127" theta2="0.5542707944631219" />
    <assembly azimuthalMesh="4" name="assembly1_6 fuel" rad1="0.0" rad2="14.2857142857" radialMesh="4" theta1="0.5542707944631219" theta2="0.6698344789311578" />
    <assembly azimuthalMesh="4" name="assembly1_7 fuel" rad1="0.0" rad2="14.2857142857" radialMesh="4" theta1="0.6698344789311578" theta2="0.7853981633974483" />
    <assembly azimuthalMesh="4" name="assembly2_1 fuel" rad1="14.2857142857" rad2="28.5714285714" radialMesh="4" theta1="0.0" theta2="0.11556368446681414" />
    <assembly azimuthalMesh="4" name="assembly2_2 fuel" rad1="14.2857142857" rad2="28.5714285714" radialMesh="4" theta1="0.11556368446681414" theta2="0.2311273689343264" />
    <assembly azimuthalMesh="4" name="assembly2_3 fuel" rad1="14.2857142857" rad2="28.5714285714" radialMesh="4" theta1="0.2311273689343264" theta2="0.34669105340061696" />
    <assembly azimuthalMesh="4" name="assembly2_4 fuel" rad1="14.2857142857" rad2="28.5714285714" radialMesh="4" theta1="0.34669105340061696" theta2="0.43870710999683127" />
    <assembly azimuthalMesh="4" name="assembly2_5 fuel" rad1="14.2857142857" rad2="28.5714285714" radialMesh="4" theta1="0.43870710999683127" theta2="0.5542707944631219" />
    <assembly azimuthalMesh="4" name="assembly2_6 fuel" rad1="14.2857142857" rad2="28.5714285714" radialMesh="4" theta1="0.5542707944631219" theta2="0.6698344789311578" />
    <assembly azimuthalMesh="4" name="assembly2_7 fuel" rad1="14.2857142857" rad2="28.5714285714" radialMesh="4" theta1="0.6698344789311578" theta2="0.7853981633974483" />
    <assembly azimuthalMesh="4" name="assembly3_1 fuel" rad1="28.5714285714" rad2="42.8571428571" radialMesh="4" theta1="0.0" theta2="0.11556368446681414" />
    <assembly azimuthalMesh="4" name="assembly3_2 fuel" rad1="28.5714285714" rad2="42.8571428571" radialMesh="4" theta1="0.11556368446681414" theta2="0.2311273689343264" />
    <assembly azimuthalMesh="4" name="assembly3_3 fuel" rad1="28.5714285714" rad2="42.8571428571" radialMesh="4" theta1="0.2311273689343264" theta2="0.34669105340061696" />
    <assembly azimuthalMesh="4" name="assembly3_4 fuel" rad1="28.5714285714" rad2="42.8571428571" radialMesh="4" theta1="0.34669105340061696" theta2="0.43870710999683127" />
    <assembly azimuthalMesh="4" name="assembly3_5 fuel" rad1="28.5714285714" rad2="42.8571428571" radialMesh="4" theta1="0.43870710999683127" theta2="0.5542707944631219" />
    <assembly azimuthalMesh="4" name="assembly3_6 fuel" rad1="28.5714285714" rad2="42.8571428571" radialMesh="4" theta1="0.5542707944631219" theta2="0.6698344789311578" />
    <assembly azimuthalMesh="4" name="assembly3_7 fuel" rad1="28.5714285714" rad2="42.8571428571" radialMesh="4" theta1="0.6698344789311578" theta2="0.7853981633974483" />
    <assembly azimuthalMesh="4" name="assembly4_1 fuel" rad1="42.8571428571" rad2="57.1428571429" radialMesh="4" theta1="0.0" theta2="0.11556368446681414" />
    <assembly azimuthalMesh="4" name="assembly4_2 fuel" rad1="42.8571428571" rad2="57.1428571429" radialMesh="4" theta1="0.11556368446681414" theta2="0.2311273689343264" />
    <assembly azimuthalMesh="4" name="assembly4_3 fuel" rad1="42.8571428571" rad2="57.1428571429" radialMesh="4" theta1="0.2311273689343264" theta2="0.34669105340061696" />
    <assembly azimuthalMesh="4" name="assembly4_4 fuel" rad1="42.8571428571" rad2="57.1428571429" radialMesh="4" theta1="0.34669105340061696" theta2="0.43870710999683127" />
    <assembly azimuthalMesh="4" name="assembly4_5 fuel" rad1="42.8571428571" rad2="57.1428571429" radialMesh="4" theta1="0.43870710999683127" theta2="0.5542707944631219" />
    <assembly azimuthalMesh="4" name="assembly4_6 fuel" rad1="42.8571428571" rad2="57.1428571429" radialMesh="4" theta1="0.5542707944631219" theta2="0.6698344789311578" />
    <assembly azimuthalMesh="4" name="assembly4_7 fuel" rad1="42.8571428571" rad2="57.1428571429" radialMesh="4" theta1="0.6698344789311578" theta2="0.7853981633974483" />
    <assembly azimuthalMesh="4" name="assembly5_1 fuel" rad1="57.1428571429" rad2="71.4285714286" radialMesh="4" theta1="0.0" theta2="0.11556368446681414" />
    <assembly azimuthalMesh="4" name="assembly5_2 fuel" rad1="57.1428571429" rad2="71.4285714286" radialMesh="4" theta1="0.11556368446681414" theta2="0.2311273689343264" />
    <assembly azimuthalMesh="4" name="assembly5_3 fuel" rad1="57.1428571429" rad2="71.4285714286" radialMesh="4" theta1="0.2311273689343264" theta2="0.34669105340061696" />
    <assembly azimuthalMesh="4" name="assembly5_4 fuel" rad1="57.1428571429" rad2="71.4285714286" radialMesh="4" theta1="0.34669105340061696" theta2="0.43870710999683127" />
    <assembly azimuthalMesh="4" name="assembly5_5 fuel" rad1="57.1428571429" rad2="71.4285714286" radialMesh="4" theta1="0.43870710999683127" theta2="0.5542707944631219" />
    <assembly azimuthalMesh="4" name="assembly5_6 fuel" rad1="57.1428571429" rad2="71.4285714286" radialMesh="4" theta1="0.5542707944631219" theta2="0.6698344789311578" />
    <assembly azimuthalMesh="4" name="assembly5_7 fuel" rad1="57.1428571429" rad2="71.4285714286" radialMesh="4" theta1="0.6698344789311578" theta2="0.7853981633974483" />
    <assembly azimuthalMesh="4" name="assembly6_1 fuel" rad1="71.4285714286" rad2="85.7142857143" radialMesh="4" theta1="0.0" theta2="0.11556368446681414" />
    <assembly azimuthalMesh="4" name="assembly6_2 fuel" rad1="71.4285714286" rad2="85.7142857143" radialMesh="4" theta1="0.11556368446681414" theta2="0.2311273689343264" />
    <assembly azimuthalMesh="4" name="assembly6_3 fuel" rad1="71.4285714286" rad2="85.7142857143" radialMesh="4" theta1="0.2311273689343264" theta2="0.34669105340061696" />
    <assembly azimuthalMesh="4" name="assembly6_4 fuel" rad1="71.4285714286" rad2="85.7142857143" radialMesh="4" theta1="0.34669105340061696" theta2="0.43870710999683127" />
    <assembly azimuthalMesh="4" name="assembly6_5 fuel" rad1="71.4285714286" rad2="85.7142857143" radialMesh="4" theta1="0.43870710999683127" theta2="0.5542707944631219" />
    <assembly azimuthalMesh="4" name="assembly6_6 fuel" rad1="71.4285714286" rad2="85.7142857143" radialMesh="4" theta1="0.5542707944631219" theta2="0.6698344789311578" />
    <assembly azimuthalMesh="4" name="assembly6_7 fuel" rad1="71.4285714286" rad2="85.7142857143" radialMesh="4" theta1="0.6698344789311578" theta2="0.7853981633974483" />
    <assembly azimuthalMesh="4" name="assembly7_1 fuel" rad1="85.7142857143" rad2="100.001" radialMesh="4" theta1="0.0" theta2="0.11556368446681414" />
    <assembly azimuthalMesh="4" name="assembly7_2 fuel" rad1="85.7142857143" rad2="100.001" radialMesh="4" theta1="0.11556368446681414" theta2="0.2311273689343264" />
    <assembly azimuthalMesh="4" name="assembly7_3 fuel" rad1="85.7142857143" rad2="100.001" radialMesh="4" theta1="0.2311273689343264" theta2="0.34669105340061696" />
    <assembly azimuthalMesh="4" name="assembly7_4 fuel" rad1="85.7142857143" rad2="100.001" radialMesh="4" theta1="0.34669105340061696" theta2="0.43870710999683127" />
    <assembly azimuthalMesh="4" name="assembly7_5 fuel" rad1="85.7142857143" rad2="100.001" radialMesh="4" theta1="0.43870710999683127" theta2="0.5542707944631219" />
    <assembly azimuthalMesh="4" name="assembly7_6 fuel" rad1="85.7142857143" rad2="100.001" radialMesh="4" theta1="0.5542707944631219" theta2="0.6698344789311578" />
    <assembly azimuthalMesh="4" name="assembly7_7 fuel" rad1="85.7142857143" rad2="100.001" radialMesh="4" theta1="0.6698344789311578" theta2="0.7853981633974483" />
    <assembly azimuthalMesh="4" name="assembly8_1 fuel" rad1="100.001" rad2="115.001" radialMesh="4" theta1="0.0" theta2="0.11556368446681414" />
    <assembly azimuthalMesh="4" name="assembly8_2 fuel" rad1="100.001" rad2="115.001" radialMesh="4" theta1="0.11556368446681414" theta2="0.2311273689343264" />
    <assembly azimuthalMesh="4" name="assembly8_3 fuel" rad1="100.001" rad2="115.001" radialMesh="4" theta1="0.2311273689343264" theta2="0.34669105340061696" />
    <assembly azimuthalMesh="4" name="assembly8_4 fuel" rad1="100.001" rad2="115.001" radialMesh="4" theta1="0.34669105340061696" theta2="0.43870710999683127" />
    <assembly azimuthalMesh="4" name="assembly8_5 fuel" rad1="100.001" rad2="115.001" radialMesh="4" theta1="0.43870710999683127" theta2="0.5542707944631219" />
    <assembly azimuthalMesh="4" name="assembly8_6 fuel" rad1="100.001" rad2="115.001" radialMesh="4" theta1="0.5542707944631219" theta2="0.6698344789311578" />
    <assembly azimuthalMesh="4" name="assembly8_7 fuel" rad1="100.001" rad2="115.001" radialMesh="4" theta1="0.6698344789311578" theta2="0.7853981633974483" />
    <assembly azimuthalMesh="4" name="assembly9_1 fuel" rad1="115.001" rad2="130.001" radialMesh="4" theta1="0.0" theta2="0.11556368446681414" />
    <assembly azimuthalMesh="4" name="assembly9_2 fuel" rad1="115.001" rad2="130.001" radialMesh="4" theta1="0.11556368446681414" theta2="0.2311273689343264" />
    <assembly azimuthalMesh="4" name="assembly9_3 fuel" rad1="115.001" rad2="130.001" radialMesh="4" theta1="0.2311273689343264" theta2="0.34669105340061696" />
    <assembly azimuthalMesh="4" name="assembly9_4 fuel" rad1="115.001" rad2="130.001" radialMesh="4" theta1="0.34669105340061696" theta2="0.43870710999683127" />
    <assembly azimuthalMesh="4" name="assembly9_5 fuel" rad1="115.001" rad2="130.001" radialMesh="4" theta1="0.43870710999683127" theta2="0.5542707944631219" />
    <assembly azimuthalMesh="4" name="assembly9_6 fuel" rad1="115.001" rad2="130.001" radialMesh="4" theta1="0.5542707944631219" theta2="0.6698344789311578" />
    <assembly azimuthalMesh="4" name="assembly9_7 fuel" rad1="115.001" rad2="130.001" radialMesh="4" theta1="0.6698344789311578" theta2="0.7853981633974483" />
</reactor>
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


class TestRZTGridBlueprint(unittest.TestCase):
    """
    Tests for R-Z-Theta grid inputs.
    """

    def setUp(self):
        self.grids = gridBlueprint.Grids.load(RZT_BLUEPRINT)

    def test_construct(self):
        gridDesign = self.grids["rzt_core"]
        grid = gridDesign.construct()
        self.assertEqual(gridDesign.gridContents[2, 2], "assembly3_3 fuel")
        self.assertEqual(
            grid.indicesOfBounds(
                57.1428571429, 71.4285714286, 0.5542707944631219, 0.6698344789311578
            ),
            (5, 4, 0),
        )

    def test_geomFile(self):
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromStream(io.StringIO(RTH_GEOM))
        gridDesign = geom.toGridBlueprint("test_grid")


if __name__ == "__main__":
    unittest.main()
