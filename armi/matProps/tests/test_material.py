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

"""Program that runs all of the tests in the TestMapPropsMaterial class."""

import os
import unittest

import armi.matProps
from armi.matProps.material import Material
from armi.matProps.materialType import MaterialType

THIS_DIR = os.path.dirname(__file__)


class TestMapPropsMaterial(unittest.TestCase):
    """Class which tests the functionality of the matProps Material class."""

    @staticmethod
    def _createFunction(materialType):
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

        mat = Material()
        mat.loadNode(testNode)

        return mat

    def test_getValidFileFormatVersions(self):
        versions = armi.matProps.Material.getValidFileFormatVersions()
        self.assertGreater(len(versions), 1)
        for version in versions:
            if type(version) is not float:
                self.assertEqual(version, "TESTS")

    def test_loadFile(self):
        mat = armi.matProps.Material()
        self.assertEqual(str(mat), "<Material None None>")
        fPath = os.path.join(THIS_DIR, "testMaterialsData", "materialA.yaml")
        self.assertEqual(len(sorted(armi.matProps.materials.keys())), 0)
        mat.loadFile(fPath)
        self.assertEqual(len(sorted(armi.matProps.materials.keys())), 0)

    def test_datafilesType(self):
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
            parseType = self._createFunction(matTypeName).materialType
            typeIdx = MaterialType.types[matTypeName]
            expectedType = MaterialType(typeIdx)
            self.assertEqual(parseType, expectedType)

    def test_datafilesInvType(self):
        with self.assertRaisesRegex(KeyError, "Invalid material type"):
            self._createFunction("Solid")

    def test_saveLogic(self):
        mat = self._createFunction("Metal")
        self.assertFalse(mat.saved())
        mat.save()
        self.assertTrue(mat.saved())
