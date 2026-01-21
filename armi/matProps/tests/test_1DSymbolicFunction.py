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

"""
Historical tests that verify constant, polynomial, hyperbolic, and power law functional forms.

These tests were written when each functional form was it's own class. They have since been unified with the symbolic
function class. These tests have been converted to use the symbolic function class. They are retained because they are
fast and add more tests.
"""

import os

import numpy as np

from armi.matProps.tests import FunctionTestClassBase


class Test1DSymbolicFunction(FunctionTestClassBase):
    """Test 1D symbolic functions."""

    @classmethod
    def setUpClass(cls):
        """Initialization method for function data."""
        super().setUpClass()

        cls.basePolynomialMap = {0: 5, 1: 2, 2: -3, 3: 4, 4: -5, 5: 6, 6: -7, 7: 8}
        cls.basePolynomialData = {
            "type": "symbolic",
            "equation": cls.createEqnPoly(cls.basePolynomialMap),
        }

        cls.basePowerLawTerms = {
            "exponent": 2.0,
            "inner adder": 125.0,
            "outer multiplier": 3.4,
            "intercept": -2.5,
        }

        cls.basePowerLawData = {
            "type": "symbolic",
            "equation": cls.createEqnPower(cls.basePowerLawTerms),
        }

        cls.baseHyperbolicTerms = {
            "hyperbolic function": "tanh",
            "intercept": 5,
            "outer multiplier": 2,
            "inner denominator": 4,
            "inner adder": 1,
        }

        cls.baseHyperbolicData = {
            "type": "symbolic",
            "equation": cls.createEqnHyper(cls.baseHyperbolicTerms),
        }

        cls.baseConstantData = {"type": "symbolic", "equation": "9123.5"}

    def test_polynomial_eqn_int_int(self):
        """
        Evaluates a PolynomialFunction that has 8 power values that are all integers.

        This test is primarily performed to ensure that the override methods PolynomialFunction._parse_specific() and
        PolynomialFunction._calc_specific() are functioning appropriately. A minimal YAML file with a defined polynomial
        function is provided in this test. The polynomial is comprised of all integer coefficients and powers to ensure
        that matProps can properly handle integer inputs. The function is evaluated at several values in the valid
        range and compared to a lambda expression inside the test method to make sure their results are equivalent.
        """
        # these polynomials have up to 8 powers/terms (including 0)
        mat = self._create_function(self.basePolynomialData)
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        self.assertAlmostEqual(mat.rho.calc({"T": 0}), self.polynomialEvaluation(self.basePolynomialMap, 0))
        self.assertAlmostEqual(mat.rho.calc({"T": 50}), self.polynomialEvaluation(self.basePolynomialMap, 50))
        self.assertAlmostEqual(mat.rho.calc({"T": 100}), self.polynomialEvaluation(self.basePolynomialMap, 100))

    def test_polynomial_eqn_float_int(self):
        """
        Evaluates a PolynomialFunction with floating coefficients and integer power terms.

        A minimal YAML file with a polynomial function that has floating point values for the coefficients is provided.
        The function is evaluated at several values in the valid range and compared to a lambda expression inside the
        test method to make sure their results are equivalent. This test was provided to ensure that
        PolynomialFunction._calc_specific() evaluates appropriately for a polynomial function with floating point
        coefficients.
        """
        coefficientsMap = {0: -2.523536, 1: 5.374489, 2: 4.897134}
        data = {"type": "symbolic", "equation": self.createEqnPoly(coefficientsMap)}

        mat = self._create_function(data)
        func = mat.rho

        self.assertAlmostEqual(func.calc({"T": -100.0}), self.polynomialEvaluation(coefficientsMap, -100.0))
        self.assertAlmostEqual(func.calc({"T": 0.0}), self.polynomialEvaluation(coefficientsMap, 0.0))
        self.assertAlmostEqual(func.calc({"T": 100.0}), self.polynomialEvaluation(coefficientsMap, 100.0))
        self.assertAlmostEqual(func.calc({"T": 500.0}), self.polynomialEvaluation(coefficientsMap, 500.0))

    def test_polynomial_eqn_float_float(self):
        """
        Test the handling of float powers and float coefficients.

        A test file for a polynomial function containing floating point numbers for every coefficient and power is
        parsed. The parsed function is evaluated at several values to make sure it returns expected results. This test
        was created to make sure the matProps.PolynomialFunction class can handle non-integer values for both powers
        and coefficients.
        """
        coefficientsMap = {0.5: -2.5, 2.5: 5.389, 1.5: 4.375}
        data = {"type": "symbolic", "equation": self.createEqnPoly(coefficientsMap)}

        mat = self._create_function(data, minT=0.0)
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        func = mat.rho

        self.assertAlmostEqual(func.calc({"T": 0.0}), self.polynomialEvaluation(coefficientsMap, 0.0))
        self.assertAlmostEqual(func.calc({"T": 100.0}), self.polynomialEvaluation(coefficientsMap, 100.0))
        self.assertAlmostEqual(func.calc({"T": 500.0}), self.polynomialEvaluation(coefficientsMap, 500.0))

    def test_polynomial_diff_float_types(self):
        """Tests that matProps can accept numpy floats as input for calc method."""
        coefficientsMap = {0.5: -2.5, 2.5: 5.389, 1.5: 4.375}
        data = {"type": "symbolic", "equation": self.createEqnPoly(coefficientsMap)}

        mat = self._create_function(data, minT=0.0)
        func = mat.rho

        self.assertAlmostEqual(func.calc({"T": np.float64(0.0)}), 0.0)
        self.assertAlmostEqual(func.calc({"T": np.float64(100.0)}), 543250.0)
        self.assertAlmostEqual(func.calc({"T": np.float64(500.0)}), 30174283.91217429)

    def test_symbolic_eqn_error(self):
        """
        Test exception handling of the symbolic equation.

        This test was designed to show that matProps can properly handle invalid inputs that are specific to symbolic
        functions. Two YAML files are used: one for a symbolic function that is missing a “equation” node and another
        that has an improper value for the "equation" node. This test attempts to parse both sample YAML files and
        ensures that the appropriate Exceptions (KeyError and ValueError) are raised.
        """
        file1 = os.path.join(self.dirname, f"{self.filePrefix}_no_equation.yaml")
        # Leave out equation node
        dataNoCoeff = {"type": "symbolic"}
        with self.assertRaises(KeyError):
            self._create_function(dataNoCoeff, outFileName=file1)

        file2 = os.path.join(self.dirname, f"{self.filePrefix}_bad_equation.yaml")
        # Provide invalid equation node.
        dataBadCoeff = {"type": "symbolic", "equation": "NOT AN EQUATION"}
        with self.assertRaises(ValueError):
            self._create_function(dataBadCoeff, outFileName=file2)

    def test_power_eqn(self):
        """
        Tests the evaluation with floating terms and a mix of float and integer values.

        This test is used to make sure that the parameters are parsed appropriately in PowerLaw._parse_specific() and
        evaluated appropriately in PowerLaw._calc_specific(). This tests the logic branch where both optional nodes
        “intercept” and “outer multiplier” are provided. A sample YAML file is provided that contains the required power
        law nodes and all of the optional power law nodes. Floating point values are used for all the power law
        “coefficients” child nodes. The power law function is then evaluated at several points to ensure that the values
        were parsed appropriately.
        """
        mat = self._create_function(self.basePowerLawData)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 0}), self.powerLawEvaluation(self.basePowerLawTerms, 0))
        self.assertAlmostEqual(
            func.calc({"T": 12.5}),
            self.powerLawEvaluation(self.basePowerLawTerms, 12.5),
        )
        self.assertAlmostEqual(func.calc({"T": 25}), self.powerLawEvaluation(self.basePowerLawTerms, 25))
        self.assertAlmostEqual(func.calc({"T": 50}), self.powerLawEvaluation(self.basePowerLawTerms, 50))
        self.assertAlmostEqual(func.calc({"T": 75}), self.powerLawEvaluation(self.basePowerLawTerms, 75))
        self.assertAlmostEqual(func.calc({"T": 100}), self.powerLawEvaluation(self.basePowerLawTerms, 100))

    def test_power_eqn_all_int(self):
        """
        Tests the evaluation of a power law function with all integer terms and values.

        This test is designed to make sure that providing integer values for the power law coefficients does not yield
        unexpected results. A sample YAML file is generated containing all integer values for the “coefficient” nodes
        for the power law function. The YAML file is parsed, and the resulting function object that is generated is
        evaluated at several values to ensure that it returns expected results.
        """
        coefficients = {
            "exponent": 2,
            "inner adder": 125,
            "outer multiplier": 3,
            "intercept": -2,
        }
        powerLawDataInt = {
            "type": "symbolic",
            "equation": self.createEqnPower(coefficients),
        }

        mat = self._create_function(powerLawDataInt)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 0}), self.powerLawEvaluation(coefficients, 0))
        self.assertAlmostEqual(func.calc({"T": 25}), self.powerLawEvaluation(coefficients, 25))
        self.assertAlmostEqual(func.calc({"T": 50}), self.powerLawEvaluation(coefficients, 50))
        self.assertAlmostEqual(func.calc({"T": 75}), self.powerLawEvaluation(coefficients, 75))
        self.assertAlmostEqual(func.calc({"T": 100}), self.powerLawEvaluation(coefficients, 100))

    def test_power_eqn_float_int(self):
        """
        Tests the evaluation of a power law function with a mixture of float and integer terms.

        This test is designed to make sure that providing a mixture of floats and integers for the coefficients does not
        have an effect on expected results. A sample YAML file is generated containing a mixture of integer and float
        values for the “coefficient” nodes for the power law function. This YAML file is parsed and the resulting
        function object that is generated is evaluated at several values to ensure that it returns expected results.
        """
        coefficients = {
            "exponent": 2.5,
            "inner adder": 125,
            "outer multiplier": 3.14159,
            "intercept": -2,
        }
        powerLawDataInt = {
            "type": "symbolic",
            "equation": self.createEqnPower(coefficients),
        }

        mat = self._create_function(powerLawDataInt)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 0}), self.powerLawEvaluation(coefficients, 0))
        self.assertAlmostEqual(func.calc({"T": 25}), self.powerLawEvaluation(coefficients, 25))
        self.assertAlmostEqual(func.calc({"T": 50}), self.powerLawEvaluation(coefficients, 50))
        self.assertAlmostEqual(func.calc({"T": 75}), self.powerLawEvaluation(coefficients, 75))
        self.assertAlmostEqual(func.calc({"T": 100}), self.powerLawEvaluation(coefficients, 100))

    def test_power_eqn_no_inter(self):
        """
        Tests that a power law function parses and evaluates appropriately without an intercept term.

        This tests the logic branch in PowerLaw._parse_specific() where the optional “outer multiplier” node is
        provided, but the optional “intercept” node is omitted. A default value should be assigned in place of the
        “intercept” node and that default value should be utilized in the evaluation. A sample YAML file is provided
        that contains the required power law nodes and the optional “outer multiplier” node. The optional “intercept”
        node is omitted. The power law function is then evaluated at several points to ensure that the values were
        parsed appropriately.
        """
        coefficients = {"exponent": 2.0, "inner adder": 125.0, "outer multiplier": 3.4}
        data = {"type": "symbolic", "equation": self.createEqnPower(coefficients)}
        mat = self._create_function(data)

        # Intercept in self.powerLawEvaluation is 0.0 to reflect default value in matProps
        self.assertAlmostEqual(mat.rho.calc({"T": 0}), self.powerLawEvaluation(coefficients, 0))
        self.assertAlmostEqual(mat.rho.calc({"T": 25}), self.powerLawEvaluation(coefficients, 25))
        self.assertAlmostEqual(mat.rho.calc({"T": 50}), self.powerLawEvaluation(coefficients, 50))
        self.assertAlmostEqual(mat.rho.calc({"T": 75}), self.powerLawEvaluation(coefficients, 75))
        self.assertAlmostEqual(mat.rho.calc({"T": 100}), self.powerLawEvaluation(coefficients, 100))

    def test_power_eqn_no_outer(self):
        """
        Tests that a power law function parses and evaluates appropriately without an outer multiplier term.

        This tests the logic branch in PowerLaw._parse_specific() where the optional “intercept” node is provided, but
        the optional “outer multiplier” node is omitted. A default value should be assigned in place of the “outer
        multiplier” node and that default value should be utilized in the evaluation. A sample YAML file is provided
        that contains the required power law nodes and the optional “intercept” node. The optional “outer multiplier”
        node is omitted. The power law function is then evaluated at several points to ensure that the values were
        parsed appropriately.
        """
        coefficients = {"exponent": 2.0, "inner adder": 125.0, "intercept": -2.5}
        data = {"type": "symbolic", "equation": self.createEqnPower(coefficients)}

        mat = self._create_function(data)
        func = mat.rho
        # Outer multiplier in self.powerLawEvaluation is 1.0 to reflect default value in matProps
        self.assertAlmostEqual(func.calc({"T": 0}), self.powerLawEvaluation(coefficients, 0))
        self.assertAlmostEqual(func.calc({"T": 25}), self.powerLawEvaluation(coefficients, 25))
        self.assertAlmostEqual(func.calc({"T": 50}), self.powerLawEvaluation(coefficients, 50))
        self.assertAlmostEqual(func.calc({"T": 75}), self.powerLawEvaluation(coefficients, 75))
        self.assertAlmostEqual(func.calc({"T": 100}), self.powerLawEvaluation(coefficients, 100))

    def test_power_eqn_no_outer_inter(self):
        """
        Tests that a power law function without intercept and outer multiplier terms.

        This test checks the logic branch in PowerLaw._parse_specific() where both the optional “intercept” and “outer
        multiplier” nodes are omitted. Default values should be assigned in place of the “outer multiplier” and
        “intercept” nodes, and those default values should be utilized in the evaluation. A sample YAML file is provided
        that contains the required power law nodes and none of the optional power law nodes. The power law function is
        then evaluated at several points to ensure that the values were parsed appropriately.
        """
        coefficients = {"exponent": 2.0, "inner adder": 125.0}
        data = {"type": "symbolic", "equation": self.createEqnPower(coefficients)}

        mat = self._create_function(data)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 0}), self.powerLawEvaluation(coefficients, 0))
        self.assertAlmostEqual(func.calc({"T": 25}), self.powerLawEvaluation(coefficients, 25))
        self.assertAlmostEqual(func.calc({"T": 50}), self.powerLawEvaluation(coefficients, 50))
        self.assertAlmostEqual(func.calc({"T": 75}), self.powerLawEvaluation(coefficients, 75))
        self.assertAlmostEqual(func.calc({"T": 100}), self.powerLawEvaluation(coefficients, 100))

    def test_constants_eval(self):
        """
        Tests that a ConstantFunction evaluates appropriately for integer and float values.

        This test ensures that the override methods ConstantFunction._parse_specific() and
        ConstantFunction._calc_specific() are functioning appropriately. A minimal YAML file with a defined constant
        function is provided in this test. The function is evaluated at several values in the valid range and compared
        to a constant value inside the test method to make sure their results are equivalent.
        """
        mat = self._create_function(self.baseConstantData)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 0}), 9123.5)
        self.assertAlmostEqual(func.calc({"T": 12.5}), 9123.5)
        self.assertAlmostEqual(func.calc({"T": 50}), 9123.5)
        self.assertAlmostEqual(func.calc({"T": 100}), 9123.5)

    def test_hyperbolic_eqn_eval(self):
        """
        Tests that a HyperbolicFunction parses and evaluates appropriately.

        This test checks that the override methods HyperbolicFunction._parse_specific() and
        HyperbolicFunction._calc_specific() are functioning appropriately. A minimal YAML file with a defined hyperbolic
        function is provided in this test with integer coefficients. The function is evaluated at several values in the
        valid range and compared to a lambda expression inside the test method to make sure their results are
        equivalent.
        """
        mat = self._create_function(self.baseHyperbolicData)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 0}), self.hyperbolicEvaluation(self.baseHyperbolicTerms, 0))
        self.assertAlmostEqual(
            func.calc({"T": 12.5}),
            self.hyperbolicEvaluation(self.baseHyperbolicTerms, 12.5),
        )
        self.assertAlmostEqual(
            func.calc({"T": 50}),
            self.hyperbolicEvaluation(self.baseHyperbolicTerms, 50),
        )
        self.assertAlmostEqual(
            func.calc({"T": 100}),
            self.hyperbolicEvaluation(self.baseHyperbolicTerms, 100),
        )

    def test_hyperbolic_eqn_eval2(self):
        """
        Test a hyperbolic function with different values.

        This test shows that parsing and evaluating a hyperbolic function is successful when the coefficients are float
        values. A sample file with a hyperbolic function file is created. Each subnode of the
        matProps.HyperbolicFunction class “coefficients” node is a float value. There is an assertion is against the
        expected value.
        """
        coefficients = {
            "hyperbolic function": "tanh",
            "intercept": 3.829e8,
            "outer multiplier": -4.672e8,
            "inner denominator": 216.66,
            "inner adder": -613.52,
        }
        data = {"type": "symbolic", "equation": self.createEqnHyper(coefficients)}
        mat = self._create_function(data)
        func = mat.rho
        expectedValue = self.hyperbolicEvaluation(coefficients, 500)
        self.assertAlmostEqual(func.calc({"T": 500}), expectedValue, delta=expectedValue * 1e-5)
