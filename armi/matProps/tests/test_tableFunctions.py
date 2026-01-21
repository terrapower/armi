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

"""Tests related to table functions (both 1D and 2D tables)."""

import numpy as np

from armi.matProps.tests import FunctionTestClassBase


class TestTableFunctions(FunctionTestClassBase):
    """Tests related to table functions (both 1D and 2D tables)."""

    @classmethod
    def setUpClass(cls):
        """Initialization method for function data."""
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
        """
        Test interpolation for two point one dimensional table.

        Input file: This test creates the file T_INTERPOLATION_1DTABLE.yaml.

        This test ensures that the override methods TableFunction1D._parse_specific() and
        TableFunction1D._calc_specific() are functioning appropriately. A minimal YAML file with a defined one
        dimensional table function is provided in this test. The function is evaluated at several values in the valid
        range and checked against some interpolated values to ensure that the linear interpolation performed for this
        table is valid. Each value is checked when provided as both a standard Python float as well as a Numpy float.
        """
        mat = self._create_function(self.baseOneDimTableData, self.baseOneDimTable)
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        func = mat.rho
        self.assertIn("TableFunction1D", str(func))
        for index in range(9):
            val = float(index) * 12.5
            self.assertAlmostEqual(func.calc({"T": np.float64(val)}), 5.0 + val)
            self.assertAlmostEqual(func.calc({"T": val}), 5.0 + val)

    def test_points(self):
        mat = self._create_function(self.baseOneDimTableData, self.baseOneDimTable)
        func = mat.rho
        points = func.points()
        self.assertAlmostEqual(points[0].variable1, 0.0)
        self.assertAlmostEqual(points[0].value, 5.0)
        self.assertAlmostEqual(points[1].variable1, 100.0)
        self.assertAlmostEqual(points[1].value, 105.0)

    def test_interpolation1DtableMissnode(self):
        """
        Test to make sure a KeyError is thrown if 'tabulated data' node is absent.

        Input file: This test creates the file T_INTERPOLATION_1DTABLE_MISSNODE.yaml.

        This test checks a logic branch inside the TableFunction1D._parse_specific() method which is responsible for
        parsing the data members specific to the mat_props.TableFunction1D class. A sample YAML file for a one
        dimensional table function that is missing a “tabulated data” node is provided. Attempting to parse this file
        should cause a KeyError to be thrown for one dimensional table functions.
        """
        with self.assertRaisesRegex(KeyError, "tabulated data"):
            self._create_function_without_table(self.baseOneDimTableData)

    # TODO: T_INTERPOLATION_1DTABLE2 and T_INTERPOLATION_1DTABLE
    def test_interpolation1Dtable2(self):
        """
        Test interpolation for many point one dimensional table.

        Input file: This test creates the file T_INTERPOLATION_1DTABLE2.yaml.

        A minimal YAML file with a defined one dimensional table function is provided in this test. The function is
        evaluated at several values in the valid range and checked against some interpolated values to ensure that the
        linear interpolation performed for this table is valid. This test verifies table interpolation on a different
        combination of table values and data types compared to ``T_INTERPOLATION_1DTABLE``.
        """
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

        mat = self._create_function(data, tableData)
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 250}), 25.68)
        self.assertAlmostEqual(func.calc({"T": 275}), 25.825)
        self.assertAlmostEqual(func.calc({"T": 500}), 26.26)
        self.assertAlmostEqual(func.calc({"T": 512.5}), 26.21375)
        self.assertAlmostEqual(func.calc({"T": 729.7}), 24.9014572864322)
        self.assertAlmostEqual(func.calc({"T": 759.7}), 24.61)

    def test_interpolation1DtableInt(self):
        """
        Test interpolation for one dimensional tables with all integer values.

        Input file: This test creates the file T_INTERPOLATION_1DTABLE_INT.yaml.

        This test makes sure that parsing integer inputs for tabular data does not cast output values as an integer. A
        sample YAML file with a one dimensional table function that has all integer values in its table entries is
        provided. The parsed table function is evaluated for both integer and floating-point inputs and compared to
        expected results.
        """
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

        mat = self._create_function(self.baseOneDimTableData, tableData, minT=250, maxT=900)
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 275}), 5.5)
        self.assertAlmostEqual(func.calc({"T": 312.5}), 6.125)

    def test_interpolationTable2D(self):
        """
        Test that evaluates TableFunction2D for different combinations of integer and floating values.

        Input file: This test creates the file T_INTERPOLATION_TABLE2D.yaml.

        A minimal YAML file with a defined two dimensional table function is provided in this test. The function is
        evaluated at several values in the valid variable ranges and checked against interpolated values to ensure that
        the calculations were performed correctly.
        """
        mat = self._create_function(self.baseTwoDimTableData, self.baseTwoDimTable)
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
        """
        Test to make sure TableFunction2D throws a KeyError if 'tabulated data' node is absent.

        Input file: This test creates the file T_INTERPOLATION_TABLE2D_MISSNODE.yaml.

        This test verifies that the TableFunction2D._parse_specific() method which is responsible for parsing the data
        members specific to the mat_props.TableFunction2D class can appropriately handle the case where a “tabulated
        data” node is not present. This test provides a sample YAML file for a two dimensional table function that is
        missing a “tabulated data” node. Not having this node should cause a KeyError to be thrown for two dimensional
        table functions.
        """
        with self.assertRaisesRegex(KeyError, "tabulated data"):
            self._create_function_without_table(self.baseTwoDimTableData)

    def test_inputCheckTable2Doutbounds(self):
        """
        Ensure a ValueError is thrown when evaluating out of the valid bounds.

        Input file: This test creates the file T_INPUT_CHECK_TABLE2D_OUTBOUNDS.yaml.

        A minimal YAML file with a defined two dimensional table function is provided in this test. Tests that a
        ValueError is raised when evaluating the table at values above and below the valid bounds for each independent
        variable.
        """
        mat = self._create_function(self.baseTwoDimTableData, self.baseTwoDimTable)
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
        """
        Test to make sure an error is raised when attempting to evaluate below the valid range.

        Input file: This test creates the file T_INPUT_CHECK_TABLE_MINVAR.yaml.

        A minimal YAML file with a defined 1D table function is provided in this test. Tests that an ValueError is
        raised when a value below the minimum valid range is used with a 1D table function.
        """
        self.belowMinimumCheck(self.baseOneDimTableData, self.baseOneDimTable)

    def test_inputCheckTableMaxVar(self):
        """
        Test to make sure an error is raised when attempting to evaluate above the valid range.

        Input file: This test creates the file T_INPUT_CHECK_TABLE_MAXVAR.yaml.

        A minimal YAML file with a defined 1D table function is provided in this test. Tests that an ValueError is
        raised when a value above the maximum valid range is used with a 1D table function.
        """
        self.aboveMaximumCheck(self.baseOneDimTableData, self.baseOneDimTable)

    def test_inputCheckTable2DMinVar1(self):
        """
        Test to make sure an error is raised when attempting to evaluate below the valid range.

        Input file: This test creates the file T_INPUT_CHECK_TABLE2D_MINVAR1.yaml.

        A minimal YAML file with a defined 2D table function is provided in this test. Tests that an ValueError is
        raised when a value for the first independent variable is below the minimum valid range is used with a 2D table
        function.
        """
        mat = self._create_function(self.baseTwoDimTableData, self.baseTwoDimTable)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": 1, "t": 50})

    def test_inputCheckTable2DMaxVar1(self):
        """
        Test to make sure an error is raised when attempting to evaluate above the valid range.

        Input file: This test creates the file T_INPUT_CHECK_TABLE2D_MAXVAR1.yaml.

        A minimal YAML file with a defined 2D table function is provided in this test. Tests that an ValueError is
        raised when a value for the first independent variable is above the maximum valid range is used with a 2D table
        function.
        """
        mat = self._create_function(self.baseTwoDimTableData, self.baseTwoDimTable)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": 650, "t": 50})

    def test_inputCheckTable2DMinVar2(self):
        """
        Test to make sure an error is raised when attempting to evaluate below the valid range.

        Input file: This test creates the file T_INPUT_CHECK_TABLE2D_MINVAR2.yaml.

        A minimal YAML file with a defined 2D table function is provided in this test. Tests that an ValueError is
        raised when a value for the second independent variable is below the minimum valid range is used with a 2D table
        function.
        """
        mat = self._create_function(self.baseTwoDimTableData, self.baseTwoDimTable)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": 1, "t": 0})

    def test_inputCheckTable2DMaxVar2(self):
        """
        Test to make sure an error is raised when attempting to evaluate above the valid range.

        Input file: This test creates the file T_INPUT_CHECK_TABLE2D_MAXVAR2.yaml.

        A minimal YAML file with a defined 2D table function is provided in this test. Tests that an ValueError is
        raised when a value for the second independent variable is above the maximum valid range is used with a 2D table
        function.
        """
        mat = self._create_function(self.baseTwoDimTableData, self.baseTwoDimTable)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": 1, "t": 1000})
