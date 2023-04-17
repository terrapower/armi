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

"""Tests for simplified UZr material."""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import unittest

from armi.materials.uZr import UZr
from armi.materials.tests import test_materials


class UZR_TestCase(test_materials._Material_Test, unittest.TestCase):
    MAT_CLASS = UZr

    def test_density(self):
        cur = self.mat.density(400)
        ref = 15.94
        delta = ref * 0.01
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)


if __name__ == "__main__":
    unittest.main()
