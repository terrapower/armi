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
Test loading Theta-RZ reactor models.
"""
import unittest
import os
import math

from armi import settings
from armi.tests import TEST_ROOT
from armi.reactor import reactors


class Test_RZT_Reactor(unittest.TestCase):
    """Tests for RZT reactors."""

    @classmethod
    def setUpClass(cls):
        cs = settings.Settings(fName=os.path.join(TEST_ROOT, "ThRZSettings.yaml"))
        cls.r = reactors.loadFromCs(cs)

    def test_loadRZT(self):
        self.assertEqual(len(self.r.core), 14)
        radMeshes = [a.p.RadMesh for a in self.r.core]
        self.assertTrue(all(radMesh == 4 for radMesh in radMeshes))

    def test_findAllMeshPoints(self):
        i, j, k = self.r.core.findAllMeshPoints()
        self.assertLess(i[-1], 2 * math.pi)


if __name__ == "__main__":
    unittest.main()
