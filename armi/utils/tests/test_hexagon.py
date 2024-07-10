# Copyright 2023 TerraPower, LLC
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
"""Test hexagon tools."""
import math
import unittest

from armi.utils import hexagon


class TestHexagon(unittest.TestCase):
    def test_hexagon_area(self):
        """
        Area of a hexagon.

        .. test:: Hexagonal area is retrievable.
            :id: T_ARMI_UTIL_HEXAGON0
            :tests: R_ARMI_UTIL_HEXAGON
        """
        # Calculate area given a pitch
        self.assertEqual(hexagon.area(1), math.sqrt(3.0) / 2)
        self.assertEqual(hexagon.area(2), 4 * math.sqrt(3.0) / 2)

    def test_numPositionsInRing(self):
        """
        Calculate number of positions in a ring of hexagons.

        .. test:: Compute number of positions in ring.
            :id: T_ARMI_UTIL_HEXAGON1
            :tests: R_ARMI_UTIL_HEXAGON
        """
        self.assertEqual(hexagon.numPositionsInRing(1), 1)
        self.assertEqual(hexagon.numPositionsInRing(2), 6)
        self.assertEqual(hexagon.numPositionsInRing(3), 12)
        self.assertEqual(hexagon.numPositionsInRing(4), 18)
