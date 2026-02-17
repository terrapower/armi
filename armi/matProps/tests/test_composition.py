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
import unittest

from ruamel.yaml.constructor import DuplicateKeyError

import armi.matProps
from armi.matProps.material import Material


class TestComposition(unittest.TestCase):
    """Class which encapsulates the unit tests data and methods to test the matProps Composition class."""

    def setUp(self):
        self.testName = self.id().split(".")[-1]
        searchStr = "test_"
        if self.testName.startswith(searchStr):
            self.testName = self.testName[len(searchStr) :]

    def _createFunction(self, compMap=None):
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

        mat = Material()
        mat.loadNode(materialMap)

        return mat

    def test_compositionMissing(self):
        materialMap = {
            "file format": "TESTS",
            "material type": "Metal",
            "density": "whatever",
        }

        mat = Material()

        with self.assertRaisesRegex(KeyError, "Missing YAML node `composition`"):
            mat.loadNode(materialMap)

    def test_compositionInvTuple(self):
        # Invalid doesn't have two elements
        badCompMap = {"Fe": [1.0]}
        with self.assertRaisesRegex(
            TypeError,
            "Composition values must be either a tuple of min/max values, or `balance`",
        ):
            self._createFunction(badCompMap)

    def test_compositionInvStr(self):
        badCompMap = {"a": [0.5, 0.5], "b": "remainder"}
        with self.assertRaisesRegex(
            TypeError,
            "Composition values must be either a tuple of min/max values, or `balance`",
        ):
            self._createFunction(badCompMap)

    def test_compositionMissBalance(self):
        compMap = {"a": [0.25, 0.26], "b": [0.3, 0.31], "c": [0.45, 0.46]}
        with self.assertRaisesRegex(ValueError, "exactly one balance element"):
            self._createFunction(compMap)

    def test_compositionBalanceNum(self):
        compMap = {"a": [15.0, 15.1], "b": "balance", "c": "balance"}
        with self.assertRaisesRegex(ValueError, "exactly one balance element"):
            self._createFunction(compMap)

    def test_compositionBalance(self):
        compMap = {"a": [15.0, 20.0], "b": [30.0, 35.0], "c": "balance"}
        mat = self._createFunction(compMap)
        mat.name = self.testName
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        c_minValue, c_maxValue = None, None
        sumMin, sumMax = 0.0, 0.0
        for compElement in mat.composition:
            if compElement.name != "c":
                self.assertFalse(compElement.isBalance)
                compValue = compMap.get(compElement.name)
                self.assertIsNotNone(compValue)
                self.assertAlmostEqual(compElement.minValue, compValue[0])
                self.assertAlmostEqual(compElement.maxValue, compValue[1])
                sumMin += compElement.minValue
                sumMax += compElement.maxValue
            else:
                self.assertTrue(compElement.isBalance)
                c_minValue = compElement.minValue
                c_maxValue = compElement.maxValue

        self.assertAlmostEqual(c_minValue, 100.0 - sumMax)
        self.assertAlmostEqual(c_maxValue, 100.0 - sumMin)

    def test_compositionBalance2(self):
        compMap = {
            "a": [10.0, 15.0],
            "b": [20.1, 35.1],
            "c": [30.2, 50.2],
            "d": "balance",
        }

        mat = self._createFunction(compMap)
        mat.name = self.testName
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        sumMin = 0.0
        d_minValue, d_maxValue = None, None
        for compElement in mat.composition:
            if compElement.name != "d":
                self.assertFalse(compElement.isBalance)
                compValue = compMap.get(compElement.name)
                self.assertIsNotNone(compValue)
                self.assertAlmostEqual(compElement.minValue, compValue[0])
                self.assertAlmostEqual(compElement.maxValue, compValue[1])
                sumMin += compElement.minValue
            else:
                self.assertTrue(compElement.isBalance)
                d_minValue = compElement.minValue
                d_maxValue = compElement.maxValue

        self.assertAlmostEqual(d_minValue, 0.0)
        self.assertAlmostEqual(d_maxValue, 100.0 - sumMin)

    def test_compositionMinValue(self):
        compMap = {"a": [-1.0, 20.0], "b": "balance"}
        with self.assertRaisesRegex(ValueError, "negative minimum"):
            self._createFunction(compMap)

    def test_compositionMaxValue(self):
        compMap = {"a": [15.0, 14.9], "b": "balance"}
        with self.assertRaisesRegex(ValueError, "max < min"):
            self._createFunction(compMap)

    def test_compositionMaxValue2(self):
        compMap = {"a": [15.0, 100.1], "b": "balance"}
        with self.assertRaisesRegex(ValueError, "max > 100.0"):
            self._createFunction(compMap)

    def test_compositionMinSum(self):
        compMap = {
            "a": [30.0, 30.1],
            "b": [40.1, 40.2],
            "c": [50.2, 50.3],
            "d": "balance",
        }
        with self.assertRaisesRegex(ValueError, "minimum composition summation greater than 100.0"):
            self._createFunction(compMap)

    def test_compositionDuplicate(self):
        duplicateTestFile = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "invalidTestFiles",
            "duplicateComposition.yaml",
        )
        with self.assertRaises(DuplicateKeyError):
            armi.matProps.loadMaterial(duplicateTestFile)
