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
import os
import unittest

from armi import configure, isConfigured

if not isConfigured():
    configure()

from armi.reactor.blueprints import Blueprints
from armi.reactor.blueprints.gridBlueprint import Grids, Pitch, saveToStream
from armi.utils.customExceptions import InputError
from armi.utils.directoryChangers import TemporaryDirectoryChanger

LATTICE_BLUEPRINT = """
control:
    geom: hex_corners_up
    symmetry: full
    lattice pitch: 
      hex: 1.2
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
pins:
  geom: hex
  symmetry: full
  lattice pitch: 
    hex: 1.3
  lattice map: |
    -   -   FP
      -   FP  FP
    -   CL  CL  CL
      FP  FP  FP  FP
    FP  FP  FP  FP  FP
      CL  CL  CL  CL
    FP  FP  FP  FP  FP
      FP  FP  FP  FP
    CL  CL  CL  CL  CL
      FP  FP  FP  FP
    FP  FP  FP  FP  FP
      CL  CL  CL  CL
    FP  FP  FP  FP  FP
      FP  FP  FP  FP
        CL  CL  CL
          FP  FP
            FP

sfp:
    geom: cartesian
    symmetry: full
    lattice map: |
        2 2 2 2 2
        2 1 1 1 2
        2 1 3 1 2
        2 3 1 1 2
        2 2 2 2 2

sfp quarter:
    geom: cartesian
    symmetry: quarter through center assembly
    lattice map: |
        2 2 2 2 2
        2 1 1 1 2
        2 1 3 1 2
        2 3 1 1 2
        2 2 2 2 2

sfp quarter even:
    geom: cartesian
    symmetry: quarter core
    lattice map: |
        2 2 2 2 2
        2 1 1 1 2
        2 1 3 1 2
        2 3 1 1 2
        2 2 2 2 2

sfp even:
    geom: cartesian
    symmetry: full
    lattice map: |
        1 2 2 2 2 2
        1 2 1 1 1 2
        1 2 1 4 1 2
        1 2 2 1 1 2
        1 2 2 2 2 2
        1 1 1 1 1 1
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

SMALL_HEX = """core:
  geom: hex
  symmetry: third periodic
  lattice map: |
    F
     F
    F F
     F
    F F
pins:
  geom: hex
  symmetry: full
  lattice map: |
    -   -   FP
      -   FP  FP
    -   CL  CL  CL
      FP  FP  FP  FP
    FP  FP  FP  FP  FP
      CL  CL  CL  CL
    FP  FP  FP  FP  FP
      FP  FP  FP  FP
    CL  CL  CL  CL  CL
      FP  FP  FP  FP
    FP  FP  FP  FP  FP
      CL  CL  CL  CL
    FP  FP  FP  FP  FP
      FP  FP  FP  FP
        CL  CL  CL
          FP  FP
            FP
"""

TINY_GRID = """core:
    geom: hex
    lattice map:
    grid bounds:
    symmetry: full
    grid contents:
       ? - 0
         - 0
       : IF
"""

BIG_FULL_HEX_CORE = """core:
  geom: hex
  symmetry: full
  lattice map: |
    -   -   -   -   -   -   SS  SS
      -   -   -   -   SS  SS  SS  SS  SS
    -   -   -   -   SS  DD  DD  DD  DD  SS
      -   -   -   SS  DD  DD  DD  DD  DD  SS
    -   -   -   SS  DD  DD  DD  DD  DD  DD  SS
      -   -   SS  DD  DD  DD  DD  DD  DD  DD  SS
    -   -   SS  DD  DD  DD  DD  DD  DD  DD  DD  SS
      -   -   SS  DD  DD  DD  RB  DD  DD  DD  SS
    -   -   SS  DD  DD  RB  RB  RB  RB  DD  DD  SS
      -   SS  DD  DD  RB  RB  FF  RB  RB  DD  DD  SS
    -   SS  SS  DD  RB  FF  FF  FF  FF  RB  DD  DD  SS
      -   SS  DD  RB  FF  FF  FF  FF  FF  RB  DD  RR
    -   SS  DD  DD  FF  FF  PC  PC  PC  FF  DD  DD  SS
      SS  SS  DD  RB  FF  II  PC  FF  FF  RB  DD  DD  SS
    -   SS  DD  RB  FF  SS  II  II  PC  FF  RB  DD  RR
      SS  DD  DD  FF  II  II  II  II  II  FF  DD  DD  SS
    -   SS  DD  RB  II  II  II  II  II  II  RB  DD  SS
      SS  DD  RB  FF  RC  II  SS  II  II  FF  RB  DD  SS
    SS  DD  DD  FF  II  II  II  RC  PC  II  FF  DD  DD  SS
      SS  DD  RB  II  PC  II  II  II  PC  II  RB  DD  SS
    SS  DD  RB  FF  II  II  II  II  II  II  FF  RB  DD  SS
      SS  DD  FF  II  II  WW  II  II  II  II  FF  DD  SS
    SS  DD  RB  FF  II  II  WW  XX  PC  II  FF  RB  DD  SS
      SS  DD  FF  PC  II  BB  AA  YY  SS  DC  FF  DD  SS
    SS  DD  RB  FF  II  RC  CC  ZZ  II  II  FF  RB  DD  SS
      SS  DD  FF  II  II  II  II  II  II  II  FF  DD  SS
    SS  DD  RB  FF  II  II  II  II  II  II  FF  RB  DD  SS
      SS  DD  RB  II  II  II  II  RC  II  II  RB  DD  SS
    SS  DD  DD  FF  PC  II  SS  II  II  PC  FF  DD  DD  SS
      SS  DD  RB  II  II  II  II  II  II  II  RB  DD  SS
    -   SS  DD  FF  II  PC  II  II  II  II  FF  DD  SS
      SS  DD  RB  FF  II  II  PC  II  II  FF  RB  DD  SS
    -   SS  DD  RB  FF  SS  II  II  PC  FF  RB  DD  SS
      SS  SS  DD  RB  FF  II  II  II  FF  RB  DD  SS  SS
    -   SS  DD  DD  FF  FF  II  II  FF  FF  DD  DD  SS
      -   SS  DD  RB  FF  FF  FF  FF  FF  RB  DD  SS
    -   SS  SS  DD  RB  FF  FF  FF  FF  RB  DD  SS  SS
      -   SS  DD  DD  RB  RB  RB  RB  RB  DD  DD  SS
        -   SS  DD  DD  RB  RB  RB  RB  DD  DD  SS
          -   SS  DD  DD  DD  DD  DD  DD  DD  SS
            SS  DD  DD  DD  DD  DD  DD  DD  DD  SS
              SS  DD  DD  DD  DD  DD  DD  DD  SS
                SS  DD  DD  DD  DD  DD  DD  SS
                  SS  DD  DD  DD  DD  DD  SS
                    SS  DD  DD  DD  DD  SS
                      SS  SS  SS  SS  SS
                        -   SS  SS  -
"""


class TestGridBPRoundTrip(unittest.TestCase):
    def setUp(self):
        self.grids = Grids.load(SMALL_HEX)

    def test_contents(self):
        self.assertIn("core", self.grids)

    def test_roundTrip(self):
        """
        Test saving blueprint data to a stream.

        .. test:: Grid blueprints can be written to disk.
            :id: T_ARMI_BP_TO_DB0
            :tests: R_ARMI_BP_TO_DB
        """
        stream = io.StringIO()
        saveToStream(stream, self.grids, False, True)
        stream.seek(0)
        gridBp = Grids.load(stream)
        self.assertIn("third", gridBp["core"].symmetry)

    def test_tinyMap(self):
        """
        Test that a lattice map can be defined, written, and read in from blueprint file.

        .. test:: Define a lattice map in reactor core.
            :id: T_ARMI_BP_GRID1
            :tests: R_ARMI_BP_GRID
        """
        grid = Grids.load(TINY_GRID)
        stream = io.StringIO()
        saveToStream(stream, grid, full=True, tryMap=True)
        stream.seek(0)
        text = stream.read()
        self.assertIn("IF", text)
        stream.seek(0)
        gridBp = Grids.load(stream)
        self.assertIn("full", gridBp["core"].symmetry)
        self.assertIn("IF", gridBp["core"].latticeMap)


class TestGridBPRoundTripFull(unittest.TestCase):
    def test_fullMap(self):
        """
        Test that a lattice map can be defined, written, and read in from blueprint file.

        .. test:: Define a lattice map in reactor core.
            :id: T_ARMI_BP_GRID2
            :tests: R_ARMI_BP_GRID
        """
        grid = Grids.load(BIG_FULL_HEX_CORE)
        gridDesign = grid["core"]
        _ = gridDesign.construct()

        # test before the round-trip
        self.assertEqual(gridDesign.gridContents[0, 0], "AA")
        self.assertEqual(gridDesign.gridContents[-2, 1], "BB")
        self.assertEqual(gridDesign.gridContents[-1, 0], "CC")
        self.assertEqual(gridDesign.gridContents[-1, 1], "WW")
        self.assertEqual(gridDesign.gridContents[1, 0], "XX")
        self.assertEqual(gridDesign.gridContents[2, -1], "YY")
        self.assertEqual(gridDesign.gridContents[1, -1], "ZZ")
        self.assertEqual(gridDesign.gridContents[-3, 1], "RC")
        self.assertEqual(gridDesign.gridContents[3, -1], "PC")

        # perform a roundtrip
        stream = io.StringIO()
        saveToStream(stream, grid, full=True, tryMap=True)
        stream.seek(0)
        gridBp = Grids.load(stream)
        gridDesign = gridBp["core"]
        _ = gridDesign.construct()

        # test again after the round-trip
        self.assertEqual(gridDesign.gridContents[0, 0], "AA")
        self.assertEqual(gridDesign.gridContents[-2, 1], "BB")
        self.assertEqual(gridDesign.gridContents[-1, 0], "CC")
        self.assertEqual(gridDesign.gridContents[-1, 1], "WW")
        self.assertEqual(gridDesign.gridContents[1, 0], "XX")
        self.assertEqual(gridDesign.gridContents[2, -1], "YY")
        self.assertEqual(gridDesign.gridContents[1, -1], "ZZ")
        self.assertEqual(gridDesign.gridContents[-3, 1], "RC")
        self.assertEqual(gridDesign.gridContents[3, -1], "PC")


class TestGridBlueprintsSection(unittest.TestCase):
    """Tests for lattice blueprint section."""

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()
        self.grids = Grids.load(LATTICE_BLUEPRINT.format(self._testMethodName))

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_simpleRead(self):
        gridDesign = self.grids["control"]
        grid = gridDesign.construct()
        self.assertAlmostEqual(grid.pitch, 1.2)
        self.assertEqual(gridDesign.gridContents[-8, 0], "6")

        gridDesign = self.grids["pins"]
        grid = gridDesign.construct()
        self.assertAlmostEqual(grid.pitch, 1.3)
        self.assertEqual(gridDesign.gridContents[-4, 0], "FP")
        self.assertEqual(gridDesign.gridContents[-3, 3], "CL")

        # Cartesian full, odd
        gridDesign2 = self.grids["sfp"]
        _ = gridDesign2.construct()
        self.assertEqual(gridDesign2.gridContents[1, 1], "1")
        self.assertEqual(gridDesign2.gridContents[0, 0], "3")
        self.assertEqual(gridDesign2.gridContents[-1, -1], "3")

        # Cartesian quarter, odd
        gridDesign3 = self.grids["sfp quarter"]
        grid = gridDesign3.construct()
        self.assertEqual(gridDesign3.gridContents[0, 0], "2")
        self.assertEqual(gridDesign3.gridContents[1, 1], "3")
        self.assertEqual(gridDesign3.gridContents[2, 2], "3")
        self.assertEqual(gridDesign3.gridContents[3, 3], "1")
        self.assertTrue(grid.symmetry.isThroughCenterAssembly)

        # cartesian quarter, even not through center
        gridDesign3 = self.grids["sfp quarter even"]
        grid = gridDesign3.construct()
        self.assertFalse(grid.symmetry.isThroughCenterAssembly)

        # Cartesian full, even/odd hybrid
        gridDesign4 = self.grids["sfp even"]
        grid = gridDesign4.construct()
        self.assertEqual(gridDesign4.gridContents[0, 0], "4")
        self.assertEqual(gridDesign4.gridContents[-1, -1], "2")
        self.assertEqual(gridDesign4.gridContents[2, 2], "2")
        self.assertEqual(gridDesign4.gridContents[-3, -3], "1")
        with self.assertRaises(KeyError):
            self.assertEqual(gridDesign4.gridContents[-4, -3], "1")

    def test_pitchEdgeCases(self):
        with self.assertRaises(TypeError):
            Pitch(0, 0, 0, 0)

        with self.assertRaises(InputError):
            Pitch([1], 2, 3, 4)

        with self.assertRaises(InputError):
            Pitch([0], 0, 0, 0)

    def test_simpleReadLatticeMap(self):
        """Read lattice map and create a grid.

        .. test:: Define a lattice map in reactor core.
            :id: T_ARMI_BP_GRID0
            :tests: R_ARMI_BP_GRID
        """
        from armi.reactor.blueprints.tests.test_blockBlueprints import FULL_BP

        # Cartesian full, even/odd hybrid
        gridDesign4 = self.grids["sfp even"]
        _grid = gridDesign4.construct()

        # test that we can correctly save this to a YAML
        bp = Blueprints.load(FULL_BP)
        filePath = "TestGridBlueprintsSection__test_simpleReadLatticeMap.log"
        with open(filePath, "w") as stream:
            saveToStream(stream, bp, True)

        # test that the output looks valid, and includes a lattice map
        with open(filePath, "r") as f:
            outText = f.read()
            self.assertIn("blocks:", outText)
            self.assertIn("shape: Circle", outText)
            self.assertIn("assemblies:", outText)
            self.assertIn("flags: fuel test", outText)
            self.assertIn("grid contents:", outText)
            self.assertIn("lattice map:", outText)
            before, after = outText.split("lattice map:")
            self.assertGreater(len(before), 100)
            self.assertGreater(len(after), 20)
            self.assertIn("1 2 1 2 1 2 1", after, msg="lattice map not showing up")
            self.assertNotIn("- -3", after, msg="grid contents are showing up when they shouldn't")
            self.assertNotIn("readFromLatticeMap", outText)

        self.assertTrue(os.path.exists(filePath))

    def test_simpleReadNoLatticeMap(self):
        from armi.reactor.blueprints.tests.test_blockBlueprints import FULL_BP_GRID

        # Cartesian full, even/odd hybrid
        gridDesign4 = self.grids["sfp even"]
        _grid = gridDesign4.construct()

        # test that we can correctly save this to a YAML
        bp = Blueprints.load(FULL_BP_GRID)
        filePath = "TestGridBlueprintsSection__test_simpleReadNoLatticeMap.log"
        with open(filePath, "w") as stream:
            saveToStream(stream, bp, True)

        # test that the output looks valid, and includes a lattice map
        with open(filePath, "r") as f:
            outText = f.read()
            self.assertIn("blocks:", outText)
            self.assertIn("shape: Circle", outText)
            self.assertIn("assemblies:", outText)
            self.assertIn("flags: fuel test", outText)
            self.assertIn("grid contents:", outText)
            self.assertIn("lattice map:", outText)
            before, after = outText.split("grid contents:")
            self.assertGreater(len(before), 100)
            self.assertGreater(len(after), 20)
            self.assertIn("- -3", after, msg="grid contents not showing up")
            self.assertNotIn("1 3 1 2 1 3 1", after, msg="lattice map showing up when it shouldn't")
            self.assertNotIn("readFromLatticeMap", outText)

        self.assertTrue(os.path.exists(filePath))


class TestRZTGridBlueprint(unittest.TestCase):
    """Tests for R-Z-Theta grid inputs."""

    def setUp(self):
        self.grids = Grids.load(RZT_BLUEPRINT)

    def test_construct(self):
        gridDesign = self.grids["rzt_core"]
        grid = gridDesign.construct()
        self.assertEqual(gridDesign.gridContents[2, 2], "assembly3_3 fuel")
        self.assertEqual(
            grid.indicesOfBounds(57.1428571429, 71.4285714286, 0.5542707944631219, 0.6698344789311578),
            (5, 4, 0),
        )
