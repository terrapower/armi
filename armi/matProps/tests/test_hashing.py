# Copyright 2026 TerraPower, LLC
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

"""Program that runs tests for the TestHashValues class."""

import os
import unittest

import armi.matProps


class TestHashValues(unittest.TestCase):
    """Testing the material hashing logic."""

    @classmethod
    def setUpClass(cls):
        cls.testDir = os.path.dirname(__file__)

    def test_hash(self):
        testFileA = os.path.join(self.testDir, "testDir1", "a.yaml")
        testFileB = os.path.join(self.testDir, "testMaterialsData", "materialB.yaml")

        matA = armi.matProps.loadMaterial(testFileA, False)
        matB = armi.matProps.loadMaterial(testFileB, False)

        self.assertEqual(matA.hash(), "409f0d651197e4563af9eb0db8b8be1b2f77f425")
        self.assertEqual(matB.hash(), "ec7a4048a24255976e04e5765fd7b2acf0a8ea45")
