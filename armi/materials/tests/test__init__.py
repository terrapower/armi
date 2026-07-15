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

import os
import shutil
import unittest

from pytest import MonkeyPatch

from armi import getPluginManagerOrFail, materials, plugins
from armi.bookkeeping.db.database import Database
from armi.bookkeeping.db.databaseInterface import DatabaseInterface
from armi.materials.material import Material
from armi.materials.mostlyYaml import _RESOURCES_DIR, HT9
from armi.reactor.reactors import Reactor
from armi.settings.fwSettings.globalSettings import CONF_MATERIAL_NAMESPACE_ORDER
from armi.testing import loadTestReactor
from armi.utils import directoryChangers


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


class YamlMaterialTests(unittest.TestCase):
    def setUp(self):
        self._monkeypatch = MonkeyPatch()
        origNamespace = materials._MATERIAL_NAMESPACE_ORDER
        self._monkeypatch.setattr(materials, "_MATERIAL_NAMESPACE_ORDER", origNamespace)

        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()

        shutil.copy(f"{os.path.join(_RESOURCES_DIR, 'HT9.yaml')}", os.getcwd())
        self.namespaceOrder = [f"dir:{os.getcwd()}", "armi.materials"]
        materials.setMaterialNamespaceOrder(self.namespaceOrder)

    def tearDown(self):
        self.td.__exit__(None, None, None)
        self._monkeypatch.undo()

    def test_materialClass(self):
        # Verify the directory HT9 is being used not the HT9 class in ARMI.
        mat = materials.createMaterialByName("HT9")
        self.assertIsInstance(mat, Material)
        self.assertNotIsInstance(mat, HT9)

    def test_loadReactor(self):
        # verifies that a reactor can be loaded from case settings with YAML materials
        _, r = loadTestReactor(
            useCache=False,
            customSettings={CONF_MATERIAL_NAMESPACE_ORDER: self.namespaceOrder},
        )
        self.assertIsInstance(r, Reactor)

    def test_loadDB(self):
        # verifies that a reactor can be loaded from database with YAML materials
        o, r = loadTestReactor(
            useCache=False,
            customSettings={CONF_MATERIAL_NAMESPACE_ORDER: self.namespaceOrder},
        )
        self.assertIsInstance(r, Reactor)

        # Write this reactor to a database file.
        dbi = DatabaseInterface(r, o.cs)
        dbi.initDB(fName="testDB1.h5")
        db = dbi.database
        db.writeToDB(r)
        db.close()

        with Database("testDB1.h5", "r") as db:
            cs2 = db.loadCS()
            r2 = db.load(0, 0, cs=cs2)

        # Verify the reactor loaded successfully
        self.assertIsInstance(r2, Reactor)
        for b in r2.core.getBlocks():
            for c in b:
                if c.getProperties().name == "HT9":
                    # Verify the directory HT9 is being used not the HT9 class in ARMI.
                    self.assertIsInstance(c.getProperties(), Material)
                    self.assertNotIsInstance(c.getProperties(), HT9)
