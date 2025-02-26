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
"""Test ASCII maps."""

import io
import unittest

from armi.utils import asciimaps

CARTESIAN_MAP = """2 2 2 2 2
2 2 2 2 2
2 1 1 1 2
2 1 3 1 2
2 3 1 1 2
2 2 2 2 2
"""

HEX_THIRD_MAP = """- - 3 3
 - 3 3 3
  3 2 2 3
 3 2 2 2 3
  2 1 1 2 3
   1 1 1 2 3
  1 1 1 1 2 3
   1 1 1 1 2 3
    1 1 1 1 2
   1 1 1 1 1 3
    1 1 1 1 2 3
     1 1 1 1 2
    1 1 1 1 1 3
     1 1 1 1 2
      1 1 1 1 3
     1 1 1 1 2
      1 1 1 1 3
     1 1 1 1 2
"""

# This core map is from refTestBase, and exhibited some issues when trying to read with
# an older implementation of the 1/3 hex lattice reader.
HEX_THIRD_MAP_2 = """-   -   SH  SH
  -   SH  SH  SH
    SH  OC  OC  SH
  SH  OC  OC  OC  SH
    OC  EX  EX  OC  SH
      EX  EX  EX  OC  SH
    EX  MC  MC  EX  OC  SH
      MC  HX  MC  EX  OC  SH
        MC  MC  PC  EX  OC
      MC  IC  MC  MC  EX  SH
        IC  IC  MC  MC  OC  SH
          PC  IC  MC  EX  OC
        FA  FA  IC  TG  EX  SH
          IC  FA  IC  MC  OC
            IC  US  MC  EX  SH
          EX  IC  IC  MC  OC
            EX  FA  MC  EX  SH
          EX  IC  IC  PC  OC
"""

HEX_THIRD_MAP_WITH_HOLES = """-   -   SH  SH
  -   SH  SH  SH
    SH  OC  OC  SH
  SH  OC  OC  OC  SH
    OC  EX  EX  OC  SH
      EX  EX  EX  OC  SH
    EX  MC  MC  EX  OC  SH
      MC  HX  MC  EX  OC  SH
        MC  -   PC  EX  OC
      MC  IC  MC  MC  EX  SH
        IC  IC  MC  MC  OC  SH
          PC  IC  MC  EX  OC
        FA  FA  IC  TG  EX  SH
          IC  FA  IC  -   OC
            -   US  MC  EX  SH
          EX  IC  IC  MC  OC
            EX  FA  MC  EX  SH
          EX  IC  IC  PC  OC
"""

HEX_THIRD_MAP_WITH_EMPTY_ROW = """-   -   SH  SH
  -   SH  SH  SH
    SH  OC  OC  SH
  SH  OC  OC  OC  SH
    OC  EX  EX  OC  SH
      EX  EX  EX  OC  SH
    EX  MC  MC  EX  OC  SH
      MC  HX  MC  EX  OC  SH
        MC  -   PC  EX  OC
      MC  IC  MC  MC  EX  SH
        IC  IC  MC  MC  OC  SH
          -   -   -   -   - 
        FA  FA  IC  TG  EX  SH
          IC  FA  IC  -   OC
            -   US  MC  EX  SH
          EX  IC  IC  MC  OC
            EX  FA  MC  EX  SH
          EX  IC  IC  PC  OC
"""

# This is a "corners-up" hexagonal map.
HEX_FULL_MAP = """- - - - - - - - - 1 1 1 1 1 1 1 1 1 4
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
"""

# This is a "flats-up" hexagonal map.
HEX_FULL_MAP_FLAT = """-       -       -       -       ORS     ORS     ORS 
    -       -       -       ORS     ORS     ORS     ORS 
-       -       -       ORS     IRS     IRS     IRS     ORS 
    -       -       ORS     IRS     IRS     IRS     IRS     ORS 
-       -       ORS     IRS     RR89    RR89    RR89    IRS     ORS 
    -       ORS     IRS     RR89    RR89    RR89    RR89    IRS     ORS 
-       ORS     IRS     RR89    RR89    RR7     RR89    RR89    IRS     ORS 
    -       IRS     RR89    RR89    RR7     RR7     RR89    RR89    IRS 
-       ORS     RR89    RR89    RR7     OC      RR7     RR89    RR89    ORS 
    ORS     IRS     RR89    RR7     OC      OC      RR7     RR89    IRS     ORS 
-       IRS     RR89    RR7     OC      OC      FS      RR7     RR89    IRS 
    ORS     RR89    RR7     OC      OC      OC      OC      RR7     RR89    ORS 
ORS     IRS     RR7     OC      OC      IC      OC      OC      RR7     IRS     ORS 
    IRS     RR89    OC      SC      ICS     IC      SC      OC      RR89    IRS 
ORS     RR89    RR7     OC      IC      IC      IC      OC      RR7     RR89    ORS 
    IRS     RR89    OC      IC      IC      IC      IC      OC      RR89    IRS 
ORS     RR89    RR7     SC      PC      ICS     PC      SC      RR7     RR89    ORS 
    IRS     RR89    OC      IC      IC      IC      IC      OC      RR89    IRS 
ORS     RR89    RR7     OC      IC      IC      IC      OC      RR7     RR89    ORS 
    IRS     RR89    VOTA    ICS     IC      IRT     ICS     OC      RR89    IRS 
ORS     RR89    RR7     OC      IC      IC      IC      OC      RR7     RR89    ORS 
    IRS     RR89    OC      IC      IC      IC      IC      OC      RR89    IRS 
ORS     RR89    FS      OC      ICS     PC      ICS     OC      RR7     RR89    ORS 
    IRS     RR89    OC      OC      IC      IC      OC      OC      RR89    IRS 
ORS     IRS     RR7     OC      OC      IC      OC      OC      RR7     IRS     ORS 
    ORS     RR89    RR7     OC      SC      SC      OC      FS      RR89    ORS 
-       IRS     RR89    RR7     OC      OC      OC      RR7     RR89    IRS 
    ORS     IRS     RR89    RR7     OC      OC      RR7     RR89    IRS     ORS 
-       ORS     RR89    RR89    RR7     OC      RR7     RR89    RR89    ORS 
    -       IRS     RR89    RR89    RR7     RR7     RR89    RR89    IRS 
        ORS     IRS     RR89    RR89    RR7     RR89    RR89    IRS     ORS 
            ORS     IRS     RR89    RR89    RR89    RR89    IRS     ORS 
                ORS     IRS     RR89    RR89    RR89    IRS     ORS 
                    ORS     IRS     IRS     IRS     IRS     ORS 
                        ORS     IRS     IRS     IRS     ORS 
                            ORS     ORS     ORS     ORS 
                                ORS     ORS     ORS 
"""

HEX_FULL_MAP_SMALL = """F
 F F
F
F F
 F
"""


class TestAsciiMaps(unittest.TestCase):
    """Test ascii maps."""

    def test_cartesian(self):
        """Make sure we can read Cartesian maps."""
        asciimap = asciimaps.AsciiMapCartesian()
        with io.StringIO() as stream:
            stream.write(CARTESIAN_MAP)
            stream.seek(0)
            asciimap.readAscii(stream.read())

        self.assertEqual(asciimap[0, 0], "2")
        self.assertEqual(asciimap[1, 1], "3")
        self.assertEqual(asciimap[2, 2], "3")
        self.assertEqual(asciimap[3, 3], "1")
        with self.assertRaises(KeyError):
            asciimap[5, 2]

        outMap = asciimaps.AsciiMapCartesian()
        outMap.asciiLabelByIndices = asciimap.asciiLabelByIndices
        outMap.gridContentsToAscii()
        with io.StringIO() as stream:
            outMap.writeAscii(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, CARTESIAN_MAP)

    def test_hexThird(self):
        """Read 1/3 core flats-up maps."""
        asciimap = asciimaps.AsciiMapHexThirdFlatsUp()
        with io.StringIO() as stream:
            stream.write(HEX_THIRD_MAP)
            stream.seek(0)
            asciimap.readAscii(stream.read())

        with io.StringIO() as stream:
            asciimap.writeAscii(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, HEX_THIRD_MAP)

        self.assertEqual(asciimap[7, 0], "2")
        self.assertEqual(asciimap[8, 0], "3")
        self.assertEqual(asciimap[8, -4], "2")
        self.assertEqual(asciimap[0, 8], "3")
        self.assertEqual(asciimap[0, 0], "1")
        with self.assertRaises(KeyError):
            asciimap[10, 0]

    def test_hexWithHoles(self):
        """Read 1/3 core flats-up maps with holes."""
        asciimap = asciimaps.AsciiMapHexThirdFlatsUp()
        with io.StringIO() as stream:
            stream.write(HEX_THIRD_MAP_WITH_HOLES)
            stream.seek(0)
            asciimap.readAscii(stream.read())

        with io.StringIO() as stream:
            asciimap.writeAscii(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, HEX_THIRD_MAP_WITH_HOLES)

        self.assertEqual(asciimap[1, 1], asciimaps.PLACEHOLDER)
        self.assertEqual(asciimap[5, 0], "TG")
        with self.assertRaises(KeyError):
            asciimap[10, 0]

        # also test writing from pure data (vs. reading) gives the exact same map :o
        with io.StringIO() as stream:
            asciimap2 = asciimaps.AsciiMapHexThirdFlatsUp()
            asciimap2.asciiLabelByIndices = asciimap.asciiLabelByIndices
            asciimap2.gridContentsToAscii()
            asciimap2.writeAscii(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, HEX_THIRD_MAP_WITH_HOLES)

    def test_hexWithEmptyRow(self):
        """Read 1/3 core flats-up maps with one entirely empty row."""
        asciimap = asciimaps.AsciiMapHexThirdFlatsUp()
        with io.StringIO() as stream:
            stream.write(HEX_THIRD_MAP_WITH_EMPTY_ROW)
            stream.seek(0)
            asciimap.readAscii(stream.read())

        with io.StringIO() as stream:
            asciimap.writeAscii(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, HEX_THIRD_MAP_WITH_EMPTY_ROW)

        self.assertEqual(asciimap[1, 1], asciimaps.PLACEHOLDER)
        self.assertEqual(asciimap[6, 0], asciimaps.PLACEHOLDER)
        self.assertEqual(asciimap[5, 0], "TG")
        with self.assertRaises(KeyError):
            asciimap[10, 0]

    def test_troublesomeHexThird(self):
        asciimap = asciimaps.AsciiMapHexThirdFlatsUp()
        with io.StringIO() as stream:
            stream.write(HEX_THIRD_MAP_2)
            stream.seek(0)
            asciimap.readAscii(stream.read())

        with io.StringIO() as stream:
            asciimap.writeAscii(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, HEX_THIRD_MAP_2)

        self.assertEqual(asciimap[5, 0], "TG")

    def test_hexFullCornersUpSpotCheck(self):
        """Spot check some hex grid coordinates are what they should be."""
        # The corners and a central line of non-zero values.
        corners_map = """- - - - - - - - - 3 0 0 0 0 0 0 0 0 2
         - - - - - - - - 0 0 0 0 0 0 0 0 0 0 0
          - - - - - - - 0 0 0 0 0 0 0 0 0 0 0 0
           - - - - - - 0 0 0 0 0 0 0 0 0 0 0 0 0
            - - - - - 0 0 0 0 0 0 0 0 0 0 0 0 0 0
             - - - - 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
              - - - 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
               - - 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
                - 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
                 4 0 0 0 0 0 0 0 0 0 1 2 3 4 5 6 7 0 1
                  0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
                   0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
                    0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
                     0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
                      0 0 0 0 0 0 0 0 0 0 0 0 0 0
                       0 0 0 0 0 0 0 0 0 0 0 0 0
                        0 0 0 0 0 0 0 0 0 0 0 0
                         0 0 0 0 0 0 0 0 0 0 0
                          5 0 0 0 0 0 0 0 0 6
        """

        # hex map is 19 rows tall: from -9 to 9
        asciimap = asciimaps.AsciiMapHexFullTipsUp()
        asciimap.readAscii(corners_map)

        # verify the corners
        self.assertEqual(asciimap[9, -9], "1")
        self.assertEqual(asciimap[9, 0], "2")
        self.assertEqual(asciimap[0, 9], "3")
        self.assertEqual(asciimap[-9, 9], "4")
        self.assertEqual(asciimap[-9, 0], "5")
        self.assertEqual(asciimap[0, -9], "6")

        # verify a line of coordinates
        self.assertEqual(asciimap[0, 0], "0")
        self.assertEqual(asciimap[1, -1], "1")
        self.assertEqual(asciimap[2, -2], "2")
        self.assertEqual(asciimap[3, -3], "3")
        self.assertEqual(asciimap[4, -4], "4")
        self.assertEqual(asciimap[5, -5], "5")
        self.assertEqual(asciimap[6, -6], "6")
        self.assertEqual(asciimap[7, -7], "7")

    def test_hexFullCornersUp(self):
        """Test sample full hex map (with hex corners up) against known answers."""
        # hex map is 19 rows tall: from -9 to 9
        asciimap = asciimaps.AsciiMapHexFullTipsUp()
        asciimap.readAscii(HEX_FULL_MAP)

        # spot check some values in the map
        self.assertIn("7 1 1 1 1 1 1 1 1 0", str(asciimap))
        self.assertEqual(asciimap[-9, 9], "7")
        self.assertEqual(asciimap[-8, 0], "6")
        self.assertEqual(asciimap[-1, 0], "2")
        self.assertEqual(asciimap[-1, 8], "8")
        self.assertEqual(asciimap[0, -6], "3")
        self.assertEqual(asciimap[0, 0], "0")
        self.assertEqual(asciimap[9, 0], "4")

        # also test writing from pure data (vs. reading) gives the exact same map
        asciimap2 = asciimaps.AsciiMapHexFullTipsUp()
        for ij, spec in asciimap.items():
            asciimap2.asciiLabelByIndices[ij] = spec

        with io.StringIO() as stream:
            asciimap2.gridContentsToAscii()
            asciimap2.writeAscii(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, HEX_FULL_MAP)

        self.assertIn("7 1 1 1 1 1 1 1 1 0", str(asciimap))
        self.assertIn("7 1 1 1 1 1 1 1 1 0", str(asciimap2))

    def test_hexFullFlatsUp(self):
        """Test sample full hex map (with hex flats up) against known answers."""
        # hex map is 21 rows tall: from -10 to 10
        asciimap = asciimaps.AsciiMapHexFullFlatsUp()
        asciimap.readAscii(HEX_FULL_MAP_FLAT)

        # spot check some values in the map
        self.assertIn("VOTA    ICS     IC      IRT     ICS     OC", str(asciimap))
        self.assertEqual(asciimap[-3, 10], "ORS")
        self.assertEqual(asciimap[0, -9], "ORS")
        self.assertEqual(asciimap[0, 0], "IC")
        self.assertEqual(asciimap[0, 9], "ORS")
        self.assertEqual(asciimap[4, -6], "RR7")
        self.assertEqual(asciimap[6, 0], "RR7")
        self.assertEqual(asciimap[7, -1], "RR89")

        # also test writing from pure data (vs. reading) gives the exact same map
        asciimap2 = asciimaps.AsciiMapHexFullFlatsUp()
        for ij, spec in asciimap.items():
            asciimap2.asciiLabelByIndices[ij] = spec

        with io.StringIO() as stream:
            asciimap2.gridContentsToAscii()
            asciimap2.writeAscii(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, HEX_FULL_MAP_FLAT)

        self.assertIn("VOTA    ICS     IC      IRT     ICS     OC", str(asciimap))
        self.assertIn("VOTA    ICS     IC      IRT     ICS     OC", str(asciimap2))

    def test_hexFullFlat(self):
        """Test sample full hex map against known answers."""
        # hex map is 19 rows tall, so it should go from -9 to 9
        asciimap = asciimaps.AsciiMapHexFullFlatsUp()
        with io.StringIO() as stream:
            stream.write(HEX_FULL_MAP_FLAT)
            stream.seek(0)
            asciimap.readAscii(stream.read())

        with io.StringIO() as stream:
            asciimap.writeAscii(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, HEX_FULL_MAP_FLAT)

        self.assertEqual(asciimap[0, 0], "IC")
        self.assertEqual(asciimap[-5, 2], "VOTA")
        self.assertEqual(asciimap[2, 3], "FS")

        # also test writing from pure data (vs. reading) gives the exact same map
        with io.StringIO() as stream:
            asciimap2 = asciimaps.AsciiMapHexFullFlatsUp()
            asciimap2.asciiLabelByIndices = asciimap.asciiLabelByIndices
            asciimap2.gridContentsToAscii()
            asciimap2.writeAscii(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, HEX_FULL_MAP_FLAT)

    def test_hexSmallFlat(self):
        asciimap = asciimaps.AsciiMapHexFullFlatsUp()
        with io.StringIO() as stream:
            stream.write(HEX_FULL_MAP_SMALL)
            stream.seek(0)
            asciimap.readAscii(stream.read())

        with io.StringIO() as stream:
            asciimap.writeAscii(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, HEX_FULL_MAP_SMALL)

    def test_flatHexBases(self):
        """For the full core with 2 lines chopped, get the first 3 bases."""
        asciimap = asciimaps.AsciiMapHexFullFlatsUp()
        with io.StringIO() as stream:
            stream.write(HEX_FULL_MAP_FLAT)
            stream.seek(0)
            asciimap.readAscii(stream.read())
        bases = []
        for li in range(3):
            bases.append(asciimap._getIJBaseByAsciiLine(li))
        # self.assertEqual(bases, [(0, -10), (-1, -9), (-2, -8)]) # unchopped
        self.assertEqual(bases, [(-2, -8), (-3, -7), (-4, -6)])  # chopped
