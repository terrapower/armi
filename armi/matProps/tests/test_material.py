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

"""Program that runs all of the tests in the TestMaterial class."""

import os
import shutil
import unittest

from ruamel.yaml import YAML

from armi import matProps
from armi.matProps.materialType import MaterialType

THIS_DIR = os.path.dirname(__file__)


class TestMaterial(unittest.TestCase):
    """Class which tests the functionality of the armi.matProps Material class."""

    @classmethod
    def setUpClass(cls):
        """Set up class members prior to running tests."""
        cls.dirname = os.path.join(os.path.dirname(os.path.realpath(__file__)), "outputFiles", "materialTests")
        if os.path.isdir(cls.dirname):
            shutil.rmtree(cls.dirname)

        os.makedirs(cls.dirname)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(os.path.dirname(cls.dirname))

    @staticmethod
    def _create_function(fileName, materialType):
        """
        Helper function used to construct a minimum viable YAML file for tests.

        Parameters
        ----------
        fileName
            String containing name of yaml file being written
        materialType
            String containing the "material type" node value
        """
        testNode = {
            "file format": "TESTS",
            "composition": {"Fe": "balance"},
            "material type": materialType,
            "density": {
                "function": {
                    "T": {
                        "min": 100.0,
                        "max": 200.0,
                    },
                    "type": "symbolic",
                    "equation": 1.0,
                }
            },
        }

        with open(fileName, "w", encoding="utf-8") as f:
            yaml = YAML()
            yaml.dump(testNode, f)

        return matProps.load_material(fileName)

    def test_get_valid_file_format_versions(self):
        versions = matProps.Material.get_valid_file_format_versions()
        self.assertGreater(len(versions), 1)
        for version in versions:
            if type(version) is not float:
                self.assertEqual(version, "TESTS")

    def test_load_file(self):
        mat = matProps.Material()
        self.assertEqual(str(mat), "<Material None None>")
        fPath = os.path.join(THIS_DIR, "testMaterialsData", "materialA.yaml")
        self.assertEqual(len(sorted(matProps.materials.keys())), 0)
        mat.load_file(fPath)
        self.assertEqual(len(sorted(matProps.materials.keys())), 0)

    def test_datafiles_type(self):
        materialTypeNames = [
            "Fuel",
            "Metal",
            "Fluid",
            "Ceramic",
            "ASME2015",
            "ASME2017",
            "ASME2019",
        ]

        for matTypeName in materialTypeNames:
            fileName = f"T_DATAFILES_TYPE_{matTypeName}.yaml"
            outFile = os.path.join(self.dirname, fileName)
            parseType = self._create_function(outFile, matTypeName).material_type
            typeIdx = MaterialType.types[matTypeName]
            expectedType = MaterialType(typeIdx)
            self.assertEqual(parseType, expectedType)

    def test_datafiles_inv_type(self):
        outFile = os.path.join(self.dirname, "T_DATAFILES_INV_TYPE.yaml")
        with self.assertRaisesRegex(KeyError, "Invalid material type"):
            self._create_function(outFile, "Solid")
