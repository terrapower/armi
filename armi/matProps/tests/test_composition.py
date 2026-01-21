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

"""Program that runs all of the tests for the TestComposition class."""

import os
import shutil
import unittest

from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError

from armi import matProps


class TestComposition(unittest.TestCase):
    """Class which encapsulates the unit tests data and methods to test the matProps Composition class."""

    @classmethod
    def setUpClass(cls):
        """Method which sets up class attributes for TestComposition. Performed prior to all tests being run."""
        cls.dirname = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "outputFiles",
            "compositionTests",
        )
        if os.path.isdir(cls.dirname):
            shutil.rmtree(cls.dirname)

        os.makedirs(cls.dirname)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(os.path.dirname(cls.dirname))

    def setUp(self):
        self.testName = self.id().split(".")[-1]
        searchStr = "test_"
        if self.testName.startswith(searchStr):
            self.testName = self.testName[len(searchStr) :]
        self.testFileName = os.path.join(self.dirname, self.testName + ".yaml")

    def _create_function(self, compMap=None):
        compValue = {}
        if compMap is not None:
            compValue = compMap
        materialMap = {
            "file format": "TESTS",
            "composition": compValue,
            "material type": "Metal",
            "density": {
                "function": {
                    "T": {"min": 100.0, "max": 200.0},
                    "type": "symbolic",
                    "equation": 1.0,
                }
            },
        }

        with open(self.testFileName, "w", encoding="utf-8") as f:
            yaml = YAML()
            yaml.dump(materialMap, f)

        return matProps.load_material(self.testFileName)

    def test_composition_missing(self):
        outFile = os.path.join(self.dirname, "T_COMPOSITION_MISSING.yaml")
        with open(outFile, "w", encoding="utf-8") as f:
            yaml = YAML()
            yaml.dump(
                {
                    "file format": "TESTS",
                    "material type": "Metal",
                    "density": "whatever",
                },
                f,
            )

        with self.assertRaisesRegex(KeyError, "Missing YAML node `composition`"):
            matProps.load_material(outFile)

    def test_composition_inv_tuple(self):
        # Invalid doesn't have two elements
        badCompMap = {"Fe": [1.0]}
        with self.assertRaisesRegex(
            TypeError,
            "Composition values must be either a tuple of min/max values, or `balance`",
        ):
            self._create_function(badCompMap)

    def test_composition_inv_str(self):
        badCompMap = {"a": [0.5, 0.5], "b": "remainder"}
        with self.assertRaisesRegex(
            TypeError,
            "Composition values must be either a tuple of min/max values, or `balance`",
        ):
            self._create_function(badCompMap)

    def test_composition_miss_balance(self):
        compMap = {"a": [0.25, 0.26], "b": [0.3, 0.31], "c": [0.45, 0.46]}
        with self.assertRaisesRegex(ValueError, "exactly one balance element"):
            self._create_function(compMap)

    def test_composition_balance_num(self):
        compMap = {"a": [15.0, 15.1], "b": "balance", "c": "balance"}
        with self.assertRaisesRegex(ValueError, "exactly one balance element"):
            self._create_function(compMap)

    def test_composition_balance(self):
        compMap = {"a": [15.0, 20.0], "b": [30.0, 35.0], "c": "balance"}
        mat = self._create_function(compMap)
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        c_min_value, c_max_value = None, None
        sumMin, sumMax = 0.0, 0.0
        for compElement in mat.composition:
            if compElement.name != "c":
                self.assertFalse(compElement.is_balance)
                compValue = compMap.get(compElement.name)
                self.assertIsNotNone(compValue)
                self.assertAlmostEqual(compElement.min_value, compValue[0])
                self.assertAlmostEqual(compElement.max_value, compValue[1])
                sumMin += compElement.min_value
                sumMax += compElement.max_value
            else:
                self.assertTrue(compElement.is_balance)
                c_min_value = compElement.min_value
                c_max_value = compElement.max_value

        self.assertAlmostEqual(c_min_value, 100.0 - sumMax)
        self.assertAlmostEqual(c_max_value, 100.0 - sumMin)

    def test_composition_balance2(self):
        compMap = {
            "a": [10.0, 15.0],
            "b": [20.1, 35.1],
            "c": [30.2, 50.2],
            "d": "balance",
        }

        mat = self._create_function(compMap)
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        sumMin = 0.0
        d_min_value, d_max_value = None, None
        for compElement in mat.composition:
            if compElement.name != "d":
                self.assertFalse(compElement.is_balance)
                compValue = compMap.get(compElement.name)
                self.assertIsNotNone(compValue)
                self.assertAlmostEqual(compElement.min_value, compValue[0])
                self.assertAlmostEqual(compElement.max_value, compValue[1])
                sumMin += compElement.min_value
            else:
                self.assertTrue(compElement.is_balance)
                d_min_value = compElement.min_value
                d_max_value = compElement.max_value

        self.assertAlmostEqual(d_min_value, 0.0)
        self.assertAlmostEqual(d_max_value, 100.0 - sumMin)

    def test_composition_min_value(self):
        compMap = {"a": [-1.0, 20.0], "b": "balance"}
        with self.assertRaisesRegex(ValueError, "negative minimum"):
            self._create_function(compMap)

    def test_composition_max_value(self):
        compMap = {"a": [15.0, 14.9], "b": "balance"}
        with self.assertRaisesRegex(ValueError, "max < min"):
            self._create_function(compMap)

    def test_composition_max_value2(self):
        compMap = {"a": [15.0, 100.1], "b": "balance"}
        with self.assertRaisesRegex(ValueError, "max > 100.0"):
            self._create_function(compMap)

    def test_composition_min_sum(self):
        compMap = {
            "a": [30.0, 30.1],
            "b": [40.1, 40.2],
            "c": [50.2, 50.3],
            "d": "balance",
        }
        with self.assertRaisesRegex(ValueError, "minimum composition summation greater than 100.0"):
            self._create_function(compMap)

    def test_composition_duplicate(self):
        duplicateTestFile = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "invalidTestFiles",
            "duplicateComposition.yaml",
        )
        with self.assertRaises(DuplicateKeyError):
            matProps.load_material(duplicateTestFile)
