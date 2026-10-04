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

"""Tests the __init__.py file since it has rather unique behavior."""

import os
import shutil
import unittest

from pytest import MonkeyPatch

from armi import getPluginManagerOrFail, materials, plugins
from armi.bookkeeping.db.database import Database
from armi.bookkeeping.db.databaseInterface import DatabaseInterface
from armi.materials import uZr
from armi.materials.material import FuelMaterial, Material
from armi.materials.mostlyYaml import _RESOURCES_DIR, HT9
from armi.reactor.blueprints import loadFromCs
from armi.reactor.flags import Flags
from armi.reactor.reactors import Reactor
from armi.settings import caseSettings
from armi.settings.fwSettings.globalSettings import CONF_MATERIAL_NAMESPACE_ORDER
from armi.testing import loadTestReactor, TESTING_ROOT
from armi.utils import directoryChangers


def betterSubClassCheck(item, superClass):
    try:
        return issubclass(item, superClass)
    except TypeError:
        return False


class TestMaterialsInit(unittest.TestCase):
    def test_canAccessClassesFromPackage(self):
        klasses = [kk for _, kk in vars(materials).items() if betterSubClassCheck(kk, materials.material.Material)]
        self.assertGreater(len(klasses), 10)

    def test_packageClassesEqualModuleClasses(self):
        self.assertEqual(materials.Water, materials.water.Water)


class FakeMaterial(Material):
    pass


class PluginMaterialA(plugins.ArmiPlugin):
    @staticmethod
    @plugins.HOOKIMPL
    def setMaterialBaseClass(materialType):
        """Set material base class."""
        return FakeMaterial


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
        self.assertIsInstance(mat, FakeMaterial)


class TestYamlMaterial(unittest.TestCase):
    """Test a custom YAML material.

    .. test:: Test a custom YAML material is able to be created, loaded with a reactor, and loaded from a database.
        :id: T_ARMI_MAT_CUSTOM1
        :tests: R_ARMI_MAT_CUSTOM
    """

    def setUp(self):
        self._monkeypatch = MonkeyPatch()
        origNamespace = materials._MATERIAL_NAMESPACE_ORDER
        self._monkeypatch.setattr(materials, "_MATERIAL_NAMESPACE_ORDER", origNamespace)

        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()

        shutil.copy(f"{os.path.join(_RESOURCES_DIR, 'HT9.yaml')}", self.td.destination)
        self.namespaceOrder = [f"dir:{self.td.destination}", "armi.materials"]
        materials.setMaterialNamespaceOrder(self.namespaceOrder)

    def tearDown(self):
        self.td.__exit__(None, None, None)
        self._monkeypatch.undo()

    def test_materialClass(self):
        """Verify the directory HT9 is being used not the HT9 class in ARMI."""
        mat = materials.createMaterialByName("HT9")
        self.assertIsInstance(mat, Material)
        self.assertNotIsInstance(mat, HT9)
        self.assertEqual(mat.YAML_PATH, os.path.join(self.td.destination, "HT9.yaml"))

    def test_loadReactor(self):
        """Verifies that a reactor can be loaded from case settings with custom YAML materials."""
        _, r = loadTestReactor(
            useCache=False,
            customSettings={CONF_MATERIAL_NAMESPACE_ORDER: self.namespaceOrder},
        )
        self.assertIsInstance(r, Reactor)
        fuelBlock = r.core.getFirstBlock(Flags.FUEL)
        cladComp = fuelBlock.getFirstComponent(Flags.CLAD)
        mat = materials.createMaterialByName("HT9")
        self.assertEqual(cladComp.material.YAML_PATH, mat.YAML_PATH)

    def test_loadDB(self):
        """Verifies that a reactor can be loaded from database with custom YAML materials."""
        o, r = loadTestReactor(
            useCache=False,
            customSettings={CONF_MATERIAL_NAMESPACE_ORDER: self.namespaceOrder},
        )
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


class TestPythonMaterial(unittest.TestCase):
    """Test a custom Python material.

    .. test:: Test a custom Python material is able to be created, loaded with a reactor, and loaded from a database.
        :id: T_ARMI_MAT_CUSTOM0
        :tests: R_ARMI_MAT_CUSTOM
    """

    def setUp(self):
        self._monkeypatch = MonkeyPatch()
        origNamespace = materials._MATERIAL_NAMESPACE_ORDER
        self._monkeypatch.setattr(materials, "_MATERIAL_NAMESPACE_ORDER", origNamespace)

        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()

        # Create the custom Python material
        self._monkeypatch.syspath_prepend(str(self.td.destination))
        customStr = """from armi.materials import uZr

class UZr(uZr.UZr):
    DATA_SOURCE = "Custom"
"""
        with open(os.path.join(self.td.destination, "customFuel.py"), "w") as file:
            file.write(customStr)
        self.namespaceOrder = ["customFuel", "armi.materials"]
        materials.setMaterialNamespaceOrder(self.namespaceOrder)

        # Write BP file with customFuel edits
        testRxtrSettings = caseSettings.Settings(
            os.path.join(TESTING_ROOT, "reactors/smallestTestReactor/armiRunSmallest.yaml")
        )
        bp = loadFromCs(testRxtrSettings)
        for block in bp.blockDesigns:
            for component in block:
                if component.material == "UZr":
                    component.material = "customFuel:UZr"
        with open("newBlueprints.yaml", "w") as f:
            bp.dump(bp, f)

    def tearDown(self):
        self.td.__exit__(None, None, None)
        self._monkeypatch.undo()

    def test_materialClass(self):
        """Verify the custom UZr material can load and is what we expect."""
        mat = materials.createMaterialByName("customFuel:UZr")
        self.assertTrue(issubclass(type(mat), FuelMaterial))
        self.assertTrue(issubclass(type(mat), uZr.UZr))
        # __repr__ is same class is not
        self.assertTrue(mat.__repr__() == uZr.UZr().__repr__())
        self.assertFalse(mat == uZr.UZr())
        # and of course the data source is what we expect
        self.assertEqual(mat.DATA_SOURCE, "Custom")

    def test_loadReactor(self):
        """Verifies that a reactor can be loaded from case settings with custom Python materials."""
        _, r = loadTestReactor(
            useCache=False,
            customSettings={
                CONF_MATERIAL_NAMESPACE_ORDER: self.namespaceOrder,
                "loadingFile": os.path.join(self.td.destination, "newBlueprints.yaml"),
            },
        )
        self.assertIsInstance(r, Reactor)
        fuelBlock = r.core.getFirstBlock(Flags.FUEL)
        fuelComp = fuelBlock.getFirstComponent(Flags.FUEL)
        self.assertEqual(fuelComp.material.DATA_SOURCE, "Custom")

    def test_loadDB(self):
        """Verifies that a reactor can be loaded from database with custom Python materials."""
        o, r = loadTestReactor(
            useCache=False,
            customSettings={
                CONF_MATERIAL_NAMESPACE_ORDER: self.namespaceOrder,
                "loadingFile": os.path.join(self.td.destination, "newBlueprints.yaml"),
            },
        )
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
                # Verify the ARMI UZr is not being used
                if c.getProperties().name == "UZr":
                    # __repr__ is same class is not
                    self.assertTrue(c.material.__repr__() == uZr.UZr().__repr__())
                    self.assertFalse(c.material == uZr.UZr())
                    # and of course the data source is what we expect
                    self.assertEqual(c.material.DATA_SOURCE, "Custom")
