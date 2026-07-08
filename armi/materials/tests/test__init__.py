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

from armi import getPluginManagerOrFail, materials, plugins
from armi.materials.material import Material
from armi.materials.pureYaml import _RESOURCES_DIR


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
        self.assertEqual(materials.Water, materials.water.Water)


class TestMaterial(Material):
    pass


class PluginMaterialA(plugins.ArmiPlugin):
    @staticmethod
    @plugins.HOOKIMPL
    def setMaterialBaseClass(materialType):
        """Set material base class."""
        return TestMaterial


class TestMaterialBaseClassHook(unittest.TestCase):
    def setUp(self):
        """
        Manipulate the standard App. We can't just configure our own, since the
        pytest environment bleeds between tests.
        """
        pm = getPluginManagerOrFail()
        pm.register(PluginMaterialA)
        self.namespaceOrder = materials.getMaterialNamespaceOrder()

    def tearDown(self):
        """Restore the App to its original state."""
        pm = getPluginManagerOrFail()
        pm.unregister(PluginMaterialA)
        materials.setMaterialNamespaceOrder(self.namespaceOrder)

    def test_materialBaseClassHook(self):
        """Verify materials are created with the right base class."""
        materials.setMaterialNamespaceOrder(["dir:" + _RESOURCES_DIR])
        mat = materials.createMaterialByName("Air")
        self.assertIsInstance(mat, TestMaterial)
