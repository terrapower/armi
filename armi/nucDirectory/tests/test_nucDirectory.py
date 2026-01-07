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

"""Tests nuclide directory."""

import unittest

from armi.nucDirectory import nucDir
from armi.nucDirectory.nuclideBases import NuclideBases


class TestNucDirectory(unittest.TestCase):
    def test_nucDir_getNameForOldDashedNames(self):
        oldNames = [
            "U-232",
            "U-233",
            "U-234",
            "U-235",
            "U-236",
            "U-238",
            "B-10",
            "B-11",
            "BE-9",
            "F-19",
            "LI-6",
            "LI-7",
            "W-182",
            "W-183",
            "W-184",
            "W-186",
            "S-32",
            "O-16",
        ]
        for oldName in oldNames:
            self.assertIsNotNone(nucDir.getNuclideFromName(oldName))

    def test_nucDir_getNucFromNucNameReturnsNuc(self):
        nb = NuclideBases()
        for nuc in nb.instances:
            self.assertEqual(nuc, nucDir.getNuclideFromName(nuc.name))

    def test_nucDir_getNuclidesFromForBadName(self):
        with self.assertRaises(Exception):
            nucDir.getNuclideFromName("Charlie")

    def test_getDisplacementEnergy(self):
        """Test getting the displacement energy for a given nuclide."""
        ed = nucDir.getThresholdDisplacementEnergy("H1")
        self.assertEqual(ed, 10.0)

        with self.assertRaises(KeyError):
            nucDir.getThresholdDisplacementEnergy("fail")
