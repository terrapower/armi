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

"""
Tests for Uranium Oxide.

Note that more tests for UO2 are in tests/test_materials.py
"""

import unittest

from armi.materials.uraniumOxide import UO2
from armi.materials.tests.test_materials import _Material_Test


class UraniumOxide_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = UO2

    def setUp(self):
        _Material_Test.setUp(self)

    def test_applyInputParams(self):
        UO2_TD = UO2()
        original = UO2_TD.density3(500)
        UO2_TD.applyInputParams(TD_frac=0.1)
        new = UO2_TD.density3(500)
        ratio = new / original
        self.assertAlmostEqual(ratio, 0.1)

        UO2_TD = UO2()
        original = UO2_TD.density(500)
        UO2_TD.applyInputParams(TD_frac=0.1)
        new = UO2_TD.density(500)
        ratio = new / original
        self.assertAlmostEqual(ratio, 0.1)


if __name__ == "__main__":
    unittest.main()
