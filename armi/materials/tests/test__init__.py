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

"""This module tests the __init__.py file since it has rather unique behavior."""

import unittest

from armi import materials


def betterSubClassCheck(item, superClass):
    try:
        return issubclass(item, superClass)
    except TypeError:
        return False


class Materials__init__Tests(unittest.TestCase):
    def test_canAccessClassesFromPackage(self):
        klasses = [kk for _, kk in vars(materials).items() if betterSubClassCheck(kk, materials.material.Material)]
        self.assertGreater(len(klasses), 10)

    def test_packageClassesEqualModuleClasses(self):
        self.assertEqual(materials.UraniumOxide, materials.uraniumOxide.UraniumOxide)
