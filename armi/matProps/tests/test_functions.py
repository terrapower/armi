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

"""Unit tests for the Function class."""

from armi.matProps.material import Material
from armi.matProps.tests import MatPropsFunTestBase


class TestFunctions(MatPropsFunTestBase):
    """Class which encapsulates the unit tests data and methods to test the matProps Function class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.baseConstantData = {"type": "symbolic", "equation": "9123.5"}

    def test_getReferences(self):
        mat = self._createFunction(self.baseConstantData)
        mat.rho._references = ["1", "2"]
        self.assertEqual(mat.rho.references[0], "1")
        self.assertEqual(mat.rho.references[1], "2")

    def test_datafilesVarVals(self):
        """
        Test to make sure that parsing variable values return the expected values when parsing "max" and "min" nodes for
        the T variable.
        """
        mat = self._createFunction(self.baseConstantData)
        mat.name = self.testName
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        density = mat.rho
        self.assertEqual(density.getMinBound("T"), -100.0)
        self.assertEqual(density.getMaxBound("T"), 500.0)

    def test_datafilesMaxVar(self):
        """Test that makes sure a ValueError is thrown if the max of a variable is less than the min."""
        with self.assertRaises(ValueError):
            self._createFunction(self.baseConstantData, maxT=-101.0)

    def test_datafilesInvType(self):
        """Test that makes sure a KeyError is thrown if an unsupported function type is provided."""
        data = {"type": "fake function"}
        with self.assertRaisesRegex(KeyError, "fake function"):
            self._createFunction(data)

    def test_refTempEval(self):
        """Test that a function with a reference temperature correctly parses and returns the expected value."""
        testData = self.baseConstantData.copy()
        testData.update({"reference temperature": 200.0})
        mat = self._createFunction(testData)
        func = mat.rho
        self.assertAlmostEqual(func.getReferenceTemperature(), 200.0)

    def test_refTempMissing(self):
        """Test that a ValueError is thrown when accessing a reference temperature value that is not provided."""
        mat = self._createFunction(self.baseConstantData)
        func = mat.rho
        with self.assertRaisesRegex(ValueError, "Reference temperature is undefined"):
            func.getReferenceTemperature()

    def test_refTempInvalid(self):
        """Test to make sure that a ValueError is thrown if the provided reference temperature value is invalid."""
        testData = self.baseConstantData.copy()
        testData.update({"reference temperature": -273.25})
        mat = self._createFunction(testData)
        func = mat.rho
        with self.assertRaisesRegex(ValueError, "Reference temperature is undefined"):
            func.getReferenceTemperature()

    def test_independentVars(self):
        mat = self._createFunction(self.baseConstantData)
        fun = mat.rho

        self.assertEqual(len(fun.independentVars), 1)
        self.assertEqual(fun.getIndependentVariables(), ["T"])
        self.assertEqual(fun.getMinBound("T"), -100)
        self.assertEqual(fun.getMaxBound("T"), 500)

        with self.assertRaises(KeyError):
            fun.getMinBound("X")

        with self.assertRaises(KeyError):
            fun.getMaxBound("Y")

    def test_calcEdgeCases(self):
        mat = self._createFunction(self.baseConstantData)
        fun = mat.rho

        with self.assertRaises(ValueError):
            fun.calc({"T": 200}, T=300)

        with self.assertRaises(ValueError):
            fun.calc()

        with self.assertRaises(KeyError):
            fun.calc({"Z": 200})

        # whoops, I forgot to declare a "max" value
        materialData = {
            "file format": "TESTS",
            "composition": {"Fe": "balance"},
            "material type": "Metal",
            "density": {"function": {"T": {"min": 1.0}, "type": "symbolic", "equation": 1.0}},
        }

        mat = Material()
        with self.assertRaises(KeyError):
            mat.loadNode(materialData)

    def test_references(self):
        materialData = {
            "file format": "TESTS",
            "composition": {"Fe": "balance"},
            "material type": "Metal",
            "density": {
                "function": {
                    "T": {"min": 1.0, "max": 10.0},
                    "type": "symbolic",
                    "equation": 1.0,
                },
                "references": [{"ref": "things", "type": "open literature"}],
            },
        }

        mat = Material()
        mat.loadNode(materialData)
        self.assertEqual(len(mat.rho.references), 1)
        self.assertEqual(mat.rho.references[0].getRef(), "things")

    def test_tabulatedData(self):
        tableData = [
            [300, 25],
            [400, 26.28],
            [500, 26.26],
            [600, 25.89],
            [700, 25.19],
            [800, 25.10],
            [900, 26.32],
        ]

        materialData = {
            "file format": "TESTS",
            "composition": {"Fe": "balance"},
            "material type": "Metal",
            "density": {
                "function": {
                    "T": {"min": 1.0, "max": 10.0},
                    "type": "symbolic",
                    "equation": 1.0,
                },
                "tabulated data": tableData,
            },
        }

        mat = Material()
        mat.loadNode(materialData)
        self.assertEqual(len(mat.rho.references), 0)
        self.assertEqual(len(mat.rho.tableData._values), 7)
