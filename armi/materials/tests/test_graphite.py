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
Tests for graphite material
"""
import unittest

from armi.materials.graphite import Graphite


class Graphite_TestCase(unittest.TestCase):
    MAT_CLASS = Graphite

    def setUp(self):
        self.mat = self.MAT_CLASS()

    def test_linearExpansionPercent(self):
        accuracy = 2

        cur = self.mat.linearExpansionPercent(330)
        ref = 0.013186
        self.assertAlmostEqual(cur, ref, accuracy)

        cur = self.mat.linearExpansionPercent(1500)
        ref = 0.748161
        self.assertAlmostEqual(cur, ref, accuracy)

        cur = self.mat.linearExpansionPercent(3000)
        ref = 2.149009
        self.assertAlmostEqual(cur, ref, accuracy)

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)


if __name__ == "__main__":
    unittest.main()
