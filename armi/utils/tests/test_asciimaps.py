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
import unittest
import io
import sys

from armi.utils import asciimaps

CARTESIAN_MAP = """2 2 2 2 2
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

HEX_FULL_MAP = """
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
"""


class TestAsciiMaps(unittest.TestCase):
    """Test ascii maps."""

    def test_cartesian(self):
        """Make sure we can read Cartesian maps."""
        reader = asciimaps.AsciiMapCartesian()
        lattice = reader.readMap(CARTESIAN_MAP)
        self.assertEqual(lattice[0, 0], "2")
        self.assertEqual(lattice[1, 1], "3")
        self.assertEqual(lattice[2, 2], "3")
        self.assertEqual(lattice[3, 3], "1")
        with self.assertRaises(KeyError):
            lattice[5, 2]  # pylint: disable=pointless-statement

        with io.StringIO() as stream:
            reader.writeMap(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, CARTESIAN_MAP)

    def test_hexThird(self):
        """Check some third-symmetry maps against known answers."""
        reader = asciimaps.AsciiMapHexThird()
        lattice = reader.readMap(HEX_THIRD_MAP)
        self.assertEqual(lattice[7, 0], "2")
        self.assertEqual(lattice[8, 0], "3")
        self.assertEqual(lattice[8, -4], "2")
        self.assertEqual(lattice[0, 8], "3")
        self.assertEqual(lattice[0, 0], "1")
        with self.assertRaises(KeyError):
            lattice[10, 0]  # pylint: disable=pointless-statement

        with io.StringIO() as stream:
            reader.writeMap(stream)
            stream.seek(0)
            output = stream.read()
            self.assertEqual(output, HEX_THIRD_MAP)

    def test_troublesomeHexThird(self):
        reader = asciimaps.AsciiMapHexThird()
        lattice = reader.readMap(HEX_THIRD_MAP_2)
        writer = asciimaps.AsciiMapHexThird(lattice)
        with io.StringIO() as stream:
            writer.writeMap(stream)
            asStr = stream.getvalue()
            self.assertEqual(asStr, HEX_THIRD_MAP_2)

    def test_hexFull(self):
        """Test sample full hex map against known answers."""
        # hex map is 19 rows tall, so it should go from -9 to 9
        reader = asciimaps.AsciiMapHexFullTipsUp()
        lattice = reader.readMap(HEX_FULL_MAP)
        self.assertEqual(lattice[0, 0], "0")
        self.assertEqual(lattice[0, -1], "2")
        self.assertEqual(lattice[0, -8], "6")
        self.assertEqual(lattice[0, 9], "4")
        self.assertEqual(lattice[-9, 0], "7")
        self.assertEqual(lattice[-8, 7], "8")
        self.assertEqual(lattice[6, -6], "3")


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
