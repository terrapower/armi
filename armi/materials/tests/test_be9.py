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
"""Unit test for Beryllium"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import unittest

from armi.materials.be9 import Be9
from armi.materials.tests import test_materials


class Test_Be9(test_materials._Material_Test, unittest.TestCase):
    """Be tests"""

    MAT_CLASS = Be9

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(Tc=25)
        ref = 1.85
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_propertyValidTemperature(self):
        self.assertGreater(len(self.mat.propertyValidTemperature), 0)


if __name__ == "__main__":
    unittest.main()
