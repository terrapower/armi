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

"""Test YAML parsers for all files in the matProps data directory to ensure that there are no parsing errors."""

import os
import tempfile
import unittest
from os import path

import armi.matProps


class TestParsing(unittest.TestCase):
    """Class which tests the parsing and material library loading functions of matProps."""

    @property
    def dirname(self):
        """Provide the directory where this file is located."""
        return path.dirname(path.realpath(__file__))

    @classmethod
    def setUpClass(cls):
        cls.dummyDataPath = path.join(path.dirname(path.realpath(__file__)), "testMaterialsData")
        cls.dummyMatFiles = {}
        for root, _, files in os.walk(cls.dummyDataPath):
            for fileName in files:
                if fileName.lower().endswith((".yaml", ".yml")):
                    cls.dummyMatFiles[fileName] = os.path.join(root, fileName)

        armi.matProps.clear()

    def tearDown(self):
        armi.matProps.clear()

    def test_datafilesMatOwner(self):
        for matFile, matPath in self.dummyMatFiles.items():
            matNam = path.splitext(matFile)[0]
            # the default behavior is loadMaterial(matPath, false)
            m = armi.matProps.loadMaterial(matPath)
            self.assertIsNotNone(m)
            with self.assertRaisesRegex(KeyError, f"No material named `{matNam}` was loaded within loaded data."):
                armi.matProps.getMaterial(matNam)
            m = armi.matProps.loadMaterial(self.dummyMatFiles[matFile], False)
            self.assertIsNotNone(m)
            with self.assertRaisesRegex(KeyError, f"No material named `{matNam}` was loaded within loaded data."):
                armi.matProps.getMaterial(matNam)
            m = armi.matProps.loadMaterial(self.dummyMatFiles[matFile], True)
            self.assertIsNotNone(m)
            m = armi.matProps.getMaterial(matNam)
            self.assertIsNotNone(m)

    def test_multiDataLoadingLoadingAll(self):
        armi.matProps.loadAll(self.dummyDataPath)
        self.assertEqual(len(self.dummyMatFiles), len(armi.matProps.loadedMaterials()))

        armi.matProps.clear()
        self.assertEqual(0, len(armi.matProps.loadedMaterials()))

    def test_loadSafe(self):
        armi.matProps.clear()
        self.assertEqual(0, len(armi.matProps.loadedMaterials()))

        # verify that it is safe to call loadSafe() multiple times in a row
        for _ in range(3):
            armi.matProps.loadSafe(self.dummyDataPath)
            self.assertEqual(len(self.dummyMatFiles), len(armi.matProps.loadedMaterials()))

        # verify the correct behavior if a bad directory is provided
        badDir = "does_not_exist_2924"
        with self.assertRaisesRegex(FileNotFoundError, f"Directory {badDir} not found"):
            armi.matProps.loadSafe(badDir)

    def test_dataLoadingPrioSameDir(self):
        armi.matProps.loadAll(self.dummyDataPath)
        with self.assertRaises(KeyError):
            armi.matProps.loadAll(self.dummyDataPath)

    def test_datafilesBadPath(self):
        badDir = "nopity-nopers-missing"
        with self.assertRaisesRegex(FileNotFoundError, f"Directory {badDir} not found"):
            armi.matProps.loadAll(badDir)

        with self.assertRaisesRegex(NotADirectoryError, "Input path"):
            armi.matProps.loadAll(path.abspath(__file__))

        with tempfile.TemporaryDirectory() as tmpDirName:
            armi.matProps.loadAll(tmpDirName)

    def test_multiDataLoadingMultidir(self):
        """Tests loading multiple data directories.

        Load all files present in the following subdirectories of the matProps repository: tests/testDir1
        and tests/testDir2.
        """
        dir1 = path.join(self.dirname, "testDir1")
        dir2 = path.join(self.dirname, "testDir2")

        # Load the two directories
        armi.matProps.loadAll(dir1)
        armi.matProps.loadAll(dir2)

        # Check that the two directories are in loaded materials
        loadList = armi.matProps.getLoadedRootDirs()
        self.assertTrue(dir1 in loadList)
        self.assertTrue(dir2 in loadList)
        self.assertTrue(len(loadList) == 2)

        # Create list of file names in two directories. They are unique
        fileSet = set()
        for fileName in os.listdir(dir1):
            fileSet.add(path.splitext(fileName)[0])
        for fileName in os.listdir(dir2):
            fileSet.add(path.splitext(fileName)[0])

        materialSet = set()
        for material in armi.matProps.loadedMaterials():
            materialSet.add(material.name)

        self.assertTrue(fileSet == materialSet)

    def test_dataLoadingPrioDiffDir(self):
        """
        Tests that an error is raised for loading a material twice different directories.

        Attempts to load all files present in the following subdirectories of the matProps repository: tests/testDir1
        and tests/testDir3. Though that includes some duplicates that should raise an error.
        """
        dir1 = path.join(self.dirname, "testDir1")
        dir3 = path.join(self.dirname, "testDir3")

        armi.matProps.loadAll(dir1)
        with self.assertRaisesRegex(KeyError, "already exists"):
            armi.matProps.loadAll(dir3)

        matA = armi.matProps.getMaterial("a")
        density = matA.rho
        # Will evaluate to 1.0 if we have the data loaded from testDir1/a.yaml.
        # If we load from testDir3/a.yaml it will have a different value
        self.assertAlmostEqual(density.calc({"T": 150.0}), 1.0)
        self.assertAlmostEqual(density.calc(T=150.0), 1.0)

    def test_datafilesGetMat(self):
        """
        Test a material retrieved by getMaterial(name) is the same as another material with the same name.

        Also tests trying to access an unknown material.
        """
        armi.matProps.loadAll(self.dummyDataPath)
        for mat in armi.matProps.loadedMaterials():
            self.assertEqual(mat, armi.matProps.getMaterial(mat.name))

        with self.assertRaisesRegex(KeyError, "No material named `Fahrvergnugen` was loaded"):
            armi.matProps.getMaterial("Fahrvergnugen")
