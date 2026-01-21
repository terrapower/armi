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

import hashlib
import os
import tempfile
import unittest
from os import path

from armi import matProps


def getFileHash(path):
    """Compute sha1 checksum for file."""
    sha1 = hashlib.sha1()
    with open(path, "rb") as f:
        sha1.update(f.read())
    return sha1.hexdigest()


class TestParsing(unittest.TestCase):
    """Class which tests the parsing and material library loading functions of matProps."""

    @property
    def dirname(self):
        """Provide the directory where this file is located."""
        return path.dirname(path.realpath(__file__))

    @classmethod
    def setUpClass(cls):
        """Sets up the class members. Is performed prior to the tests being run."""
        cls.dummyDataPath = path.join(path.dirname(path.realpath(__file__)), "testMaterialsData")
        cls.dummyMatFiles = {}
        for root, _, files in os.walk(cls.dummyDataPath):
            for fileName in files:
                if fileName.lower().endswith((".yaml", ".yml")):
                    cls.dummyMatFiles[fileName] = os.path.join(root, fileName)

    def setUp(self):
        """Method called to clear matProps before each test is run."""
        matProps.clear()

    def tearDown(self):
        """Method called to clear matProps after each test is run."""
        matProps.clear()

    def test_datafiles_matowner(self):
        for matFile, matPath in self.dummyMatFiles.items():
            matNam = path.splitext(matFile)[0]
            # the default behavior is load_material(matPath, false)
            m = matProps.load_material(matPath)
            self.assertIsNotNone(m)
            with self.assertRaisesRegex(KeyError, f"No material named `{matNam}` was loaded within loaded data."):
                matProps.get_material(matNam)
            m = matProps.load_material(self.dummyMatFiles[matFile], False)
            self.assertIsNotNone(m)
            with self.assertRaisesRegex(KeyError, f"No material named `{matNam}` was loaded within loaded data."):
                matProps.get_material(matNam)
            m = matProps.load_material(self.dummyMatFiles[matFile], True)
            self.assertIsNotNone(m)
            m = matProps.get_material(matNam)
            self.assertIsNotNone(m)

    def test_multi_data_loading_loading_all(self):
        matProps.load_all(self.dummyDataPath)
        self.assertEqual(len(self.dummyMatFiles), len(matProps.loaded_materials()))

        matProps.clear()
        self.assertEqual(0, len(matProps.loaded_materials()))

    def test_load_safe(self):
        matProps.clear()
        self.assertEqual(0, len(matProps.loaded_materials()))

        # verify that it is safe to call load_safe() multiple times in a row
        for _ in range(3):
            matProps.load_safe(self.dummyDataPath)
            self.assertEqual(len(self.dummyMatFiles), len(matProps.loaded_materials()))

        # verify the correct behavior if a bad directory is provided
        badDir = "does_not_exist_2924"
        with self.assertRaisesRegex(FileNotFoundError, f"Directory {badDir} not found"):
            matProps.load_safe(badDir)

    def test_data_loading_prio_same_dir(self):
        matProps.load_all(self.dummyDataPath)
        with self.assertRaises(KeyError):
            matProps.load_all(self.dummyDataPath)

    def test_datafiles_badpath(self):
        badDir = "nopity-nopers-missing"
        with self.assertRaisesRegex(FileNotFoundError, f"Directory {badDir} not found"):
            matProps.load_all(badDir)

        with self.assertRaisesRegex(NotADirectoryError, "Input path"):
            matProps.load_all(path.abspath(__file__))

        with tempfile.TemporaryDirectory() as tmpDirName:
            matProps.load_all(tmpDirName)

    def test_multi_data_loading_multidir(self):
        """Tests loading multiple data directories.

        This test loads all files present in the following subdirectories of the matProps repository: tests/testDir1
        and tests/testDir2.

        This test ensures that matProps can properly handle loading multiple directories. It tests the directory load
        workflow for an idealized case where all file names are unique. This test loads two directories sequentially
        into matProps and checks to ensure that both directories and their contents are appropriately accounted for in
        matProps.
        """
        dir1 = path.join(self.dirname, "testDir1")
        dir2 = path.join(self.dirname, "testDir2")

        # Load the two directories
        matProps.load_all(dir1)
        matProps.load_all(dir2)

        # Check that the two directories are in loaded materials
        loadList = matProps.get_loaded_root_dirs()
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
        for material in matProps.loaded_materials():
            materialSet.add(material.name)

        self.assertTrue(fileSet == materialSet)

    def test_data_loading_prio_diff_dir(self):
        """
        Tests that an error is raised for loading a material twice different directories.

        This test attempts to load all files present in the following subdirectories of the matProps repository:
        tests/testDir1 and tests/testDir3.

        This test loads material files from two separate directories. The two directories have a material file with a
        common material name (“a”), but with differing density property values inside the material itself. Both
        materials use a constant function with different values. This test will load the first directory and will
        attempt to load the second directory, verifying that a ValueError is thrown. After the second directory load is
        attempted, the property value will be queried to make sure it was not overwritten by the second load attempt.
        """
        dir1 = path.join(self.dirname, "testDir1")
        dir3 = path.join(self.dirname, "testDir3")

        matProps.load_all(dir1)
        with self.assertRaisesRegex(KeyError, "already exists"):
            matProps.load_all(dir3)

        matA = matProps.get_material("a")
        density = matA.rho
        # Will evaluate to 1.0 if we have the data loaded from testDir1/a.yaml.
        # If we load from testDir3/a.yaml it will have a different value
        self.assertAlmostEqual(density.calc({"T": 150.0}), 1.0)

    def test_datafiles_getmat(self):
        """
        Test a material retrieved by get_material(name) is the same as another material with the same name.

        The data files in the tests/testMaterialsData subdirectory of the matProps repository are referenced for this
        test.

        This test is provided to check the logic branches of matProps.get_material(std.string). The test first loads the
        Materials library into matProps via call to matProps.load_all(std.string). Next, the materials in
        matProps.loaded_materials() are looped over and stored in a variable. matProps.get_material(std.string) gets
        called with each material name in the loop. An assertion is made to make sure the return value and variable are
        the same object. This demonstrates that matProps.get_material(std.string) is grabbing a material in
        matProps.loaded_materials(). Finally, a call to matProps.get_material(std.string) with a non-existent material
        name is made to ensure that matProps will throw a KeyError.
        """
        matProps.load_all(self.dummyDataPath)
        for mat in matProps.loaded_materials():
            self.assertEqual(mat, matProps.get_material(mat.name))

        with self.assertRaisesRegex(KeyError, "No material named `Fahrvergnugen` was loaded"):
            matProps.get_material("Fahrvergnugen")
