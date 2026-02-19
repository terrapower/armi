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

"""Tests 1D and 2D table Functions."""

import numpy as np

from armi.matProps.tableFunction2D import TableFunction2D
from armi.matProps.tests import MatPropsFunTestBase


class TestTableFunctions(MatPropsFunTestBase):
    """Tests 1D and 2D table Functions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.baseOneDimTableData = {"type": "table", "T": 0}
        cls.baseOneDimTable = [[0.0, 5.0], [100.0, 105.0]]

        cls.baseTwoDimTableData = {
            "type": "two dimensional table",
            "T": 0,
            "t": 1,
        }
        cls.baseTwoDimTable = [
            [None, [2.0, 200.0, 632.4555]],
            [1.0, [10.0, 208.0, 640.4555]],
            [100.0, [110.0, 308.0, 740.4555]],
            [316.2278, [135, 333, 765.4555]],
        ]

    def test_interpolation1Dtable(self):
        """Test interpolation for a two-point one-dimensional table."""
        mat = self._createFunction(self.baseOneDimTableData, self.baseOneDimTable)
        mat.name = self.testName
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        func = mat.rho
        self.assertIn("TableFunction1D", str(func))
        for index in range(9):
            val = float(index) * 12.5
            self.assertAlmostEqual(func.calc({"T": np.float64(val)}), 5.0 + val)
            self.assertAlmostEqual(func.calc({"T": val}), 5.0 + val)

        # directly check error is correctly raised if the variable is unknown
        with self.assertRaises(ValueError):
            func._calcSpecific({"X": 1})

    def test_points(self):
        mat = self._createFunction(self.baseOneDimTableData, self.baseOneDimTable)
        func = mat.rho
        points = func.points()
        self.assertAlmostEqual(points[0].variable1, 0.0)
        self.assertAlmostEqual(points[0].value, 5.0)
        self.assertAlmostEqual(points[1].variable1, 100.0)
        self.assertAlmostEqual(points[1].value, 105.0)

    def test_interpolation1DtableMissnode(self):
        """Test to make sure a KeyError is thrown if 'tabulated data' node is absent."""
        with self.assertRaisesRegex(KeyError, "tabulated data"):
            self._createFunctionWithoutTable(self.baseOneDimTableData)

    def test_interpolation1Dtable2(self):
        """Test interpolation for a many-point one-dimensional table."""
        data = {"type": "table", "T": {"min": 900, "max": 250}}
        tableData = [
            [250, 25.68],
            [300, 25.97],
            [400, 26.28],
            [500, 26.26],
            [600, 25.89],
            [700, 25.19],
            [759.7, 24.61],
            [800, 25.10],
            [900, 26.32],
        ]

        mat = self._createFunction(data, tableData)
        mat.name = self.testName
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        self.assertAlmostEqual(mat.rho.calc(T=250), 25.68)
        self.assertAlmostEqual(mat.rho.calc(T=275), 25.825)
        self.assertAlmostEqual(mat.rho.calc(T=500), 26.26)
        self.assertAlmostEqual(mat.rho.calc(T=512.5), 26.21375)
        self.assertAlmostEqual(mat.rho.calc(T=729.7), 24.9014572864322)
        self.assertAlmostEqual(mat.rho.calc(T=759.7), 24.61)

        with self.assertRaises(ValueError):
            mat.rho.calc(T=999)

        # bonus test of method to clear table data
        self.assertIsNotNone(mat.rho.tableData)
        self.assertGreater(len(mat.rho.points()), 0)
        mat.rho.clear()
        self.assertIsNone(mat.rho.tableData)

    def test_interpolation1DtableInt(self):
        """Test interpolation for one-dimensional tables with all integer values."""
        tableData = [
            [250, 5],
            [300, 6],
            [400, 7],
            [500, 8],
            [600, 9],
            [700, 10],
            [800, 11],
            [900, 12],
        ]

        mat = self._createFunction(self.baseOneDimTableData, tableData, minT=250, maxT=900)
        mat.name = self.testName
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        self.assertAlmostEqual(mat.rho.calc(T=275), 5.5)
        self.assertAlmostEqual(mat.rho.calc(T=312.5), 6.125)

    def test_interpolationTable2D(self):
        """Test that evaluates TableFunction2D for different combinations of integer and floating values."""
        mat = self._createFunction(self.baseTwoDimTableData, self.baseTwoDimTable)
        mat.name = self.testName
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        func = mat.rho
        self.assertIn("TableFunction2D", str(func))
        self.assertAlmostEqual(func.calc({"T": 2, "t": 1}), 10)
        self.assertAlmostEqual(func.calc({"T": 2, "t": 100.0}), 110)
        self.assertAlmostEqual(func.calc({"T": 200, "t": 1}), 208)
        self.assertAlmostEqual(func.calc({"T": 200, "t": 100}), 308)
        self.assertAlmostEqual(func.calc({"T": 100, "t": 1}), 108)
        self.assertAlmostEqual(func.calc({"T": 100, "t": 100}), 208)
        self.assertAlmostEqual(func.calc({"T": 2, "t": 10}), 60)
        self.assertAlmostEqual(func.calc({"T": 100, "t": 10}), 158)
        self.assertAlmostEqual(func.calc({"T": 2, "t": 316.2278}), 135)
        self.assertAlmostEqual(func.calc({"T": 632.4555, "t": 1}), 640.4555)
        self.assertAlmostEqual(func.calc({"T": 200, "t": 316.2278}), 333)
        self.assertAlmostEqual(func.calc({"T": 632.4555, "t": 100}), 740.4555)
        self.assertAlmostEqual(func.calc({"T": 632.4555, "t": 316.2278}), 765.4555)
        self.assertAlmostEqual(func.calc({"T": 200, "t": 177.828}), 320.500006)
        self.assertAlmostEqual(func.calc({"T": 355.6559, "t": 100}), 463.6559)
        self.assertAlmostEqual(func.calc({"T": 355.6559, "t": 177.828}), 476.155906)

    def test_interpolationTable2DMissNode(self):
        """Test to make sure TableFunction2D throws a KeyError if 'tabulated data' node is absent."""
        with self.assertRaisesRegex(KeyError, "tabulated data"):
            self._createFunctionWithoutTable(self.baseTwoDimTableData)

    def test_inputCheckTable2Doutbounds(self):
        """Ensure a ValueError is thrown when evaluating out of the valid bounds."""
        mat = self._createFunction(self.baseTwoDimTableData, self.baseTwoDimTable)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": 1.99, "t": 1.0})

        with self.assertRaises(ValueError):
            func.calc({"T": 632.4655, "t": 1.0})

        with self.assertRaises(ValueError):
            func.calc({"T": 2.0, "t": 0.99})

        with self.assertRaises(ValueError):
            func.calc({"T": 2.0, "t": 316.2378})

    def test_inputCheckTableMinVar(self):
        """Test to make sure an error is raised when attempting to evaluate below the valid range."""
        self.belowMinimumCheck(self.baseOneDimTableData, self.baseOneDimTable)

    def test_inputCheckTableMaxVar(self):
        """Test to make sure an error is raised when attempting to evaluate above the valid range."""
        self.aboveMaximumCheck(self.baseOneDimTableData, self.baseOneDimTable)

    def test_inputCheckTable2DMinVar1(self):
        """Test to make sure an error is raised when attempting to evaluate below the valid range."""
        mat = self._createFunction(self.baseTwoDimTableData, self.baseTwoDimTable)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": 1, "t": 50})

    def test_inputCheckTable2DMaxVar1(self):
        """Test to make sure an error is raised when attempting to evaluate above the valid range."""
        mat = self._createFunction(self.baseTwoDimTableData, self.baseTwoDimTable)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": 650, "t": 50})

    def test_inputCheckTable2DMinVar2(self):
        """Ensure an ValueError is raised when evaluating below the valid range."""
        mat = self._createFunction(self.baseTwoDimTableData, self.baseTwoDimTable)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": 1, "t": 0})

    def test_table2DsetBounds(self):
        mat = self._createFunction(self.baseTwoDimTableData, self.baseTwoDimTable)
        fun = mat.rho

        # staring values
        self.assertEqual(fun.independentVars["T"], (2.0, 632.4555))
        self.assertEqual(fun.independentVars["t"], (1.0, 316.2278))

        # calling _setBounds will wipe out the "t" variable, but not update "T"
        fun._columnValues = [123, 987]
        fun._setBounds(0, "T")
        self.assertEqual(fun.independentVars["T"], (2.0, 632.4555))
        with self.assertRaises(KeyError):
            fun.independentVars["t"]

        # Here we update "T" with new column values
        fun._columnValues = [123, 987]
        fun._setBounds(0, "X")
        self.assertEqual(fun.independentVars["X"], (123.0, 987.0))

        # Here we update the new variable "X" with new row values
        fun._rowValues = [11, 99]
        fun._setBounds(1, "X")
        self.assertEqual(fun.independentVars["T"], (2.0, 632.4555))
        self.assertEqual(fun.independentVars["X"], (11.0, 99.0))
        with self.assertRaises(KeyError):
            fun.independentVars["t"]

        # Bad inputs
        with self.assertRaises(ValueError):
            fun._setBounds(2, "X")

    def test_inputCheckTable2DMaxVar2(self):
        """Ensure an ValueError is raised when evaluating above the valid range."""
        mat = self._createFunction(self.baseTwoDimTableData, self.baseTwoDimTable)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": 1, "t": 1000})

    def test_calcSpec2dEdgeCase(self):
        f = TableFunction2D("mat", "prop")
        f.independentVars = {"T": (250.0, 800.0), "t": (1, 3)}

        # This should fail correctly when given a bad input param
        with self.assertRaises(ValueError):
            f._calcSpecific({"Pa": 1.0})
