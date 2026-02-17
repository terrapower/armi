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

"""Simple examples to verify constant, polynomial, hyperbolic, and power law functional forms."""

import numpy as np

from matProps.tests import MatPropsFunTestBase


class Test1DSymbolicFunction(MatPropsFunTestBase):
    """Test 1D symbolic functions."""

    @classmethod
    def setUpClass(cls):
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

    def test_polynomialEqnIntInt(self):
        """
        Evaluates a PolynomialFunction that has 8 power values that are all integers.

        Ensure that the override methods PolynomialFunction._parseSpecific() and PolynomialFunction._calcSpecific() are
        functioning appropriately. A minimal input with a defined polynomial function is provided. The polynomial is
        comprised of all integer coefficients and powers to ensure that matProps can properly handle integer inputs. The
        function is evaluated at several values in the valid range and compared to a lambda expression inside the test
        method to make sure their results are equivalent.
        """
        # these polynomials have up to 8 powers/terms (including 0)
        mat = self._createFunction(self.basePolynomialData)
        mat.name = self.testName
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")

        # test using input dict for calc
        self.assertAlmostEqual(mat.rho.calc({"T": 0}), self.polynomialEvaluation(self.basePolynomialMap, 0))
        self.assertAlmostEqual(mat.rho.calc({"T": 50}), self.polynomialEvaluation(self.basePolynomialMap, 50))
        self.assertAlmostEqual(mat.rho.calc({"T": 100}), self.polynomialEvaluation(self.basePolynomialMap, 100))

        # test using kwargs for calc
        self.assertAlmostEqual(mat.rho.calc(T=0), self.polynomialEvaluation(self.basePolynomialMap, 0))
        self.assertAlmostEqual(mat.rho.calc(T=50), self.polynomialEvaluation(self.basePolynomialMap, 50))
        self.assertAlmostEqual(mat.rho.calc(T=100), self.polynomialEvaluation(self.basePolynomialMap, 100))

    def test_polynomialEqnFloatInt(self):
        """Evaluates a PolynomialFunction with floating point coefficients and integer point power terms."""
        coefficientsMap = {0: -2.523536, 1: 5.374489, 2: 4.897134}
        data = {"type": "symbolic", "equation": self.createEqnPoly(coefficientsMap)}

        mat = self._createFunction(data)
        func = mat.rho

        # test using input dict for calc
        self.assertAlmostEqual(func.calc({"T": -100.0}), self.polynomialEvaluation(coefficientsMap, -100.0))
        self.assertAlmostEqual(func.calc({"T": 0.0}), self.polynomialEvaluation(coefficientsMap, 0.0))
        self.assertAlmostEqual(func.calc({"T": 100.0}), self.polynomialEvaluation(coefficientsMap, 100.0))
        self.assertAlmostEqual(func.calc({"T": 500.0}), self.polynomialEvaluation(coefficientsMap, 500.0))

        # test using kwargs for calc
        self.assertAlmostEqual(func.calc(T=-100.0), self.polynomialEvaluation(coefficientsMap, -100.0))
        self.assertAlmostEqual(func.calc(T=0.0), self.polynomialEvaluation(coefficientsMap, 0.0))
        self.assertAlmostEqual(func.calc(T=100.0), self.polynomialEvaluation(coefficientsMap, 100.0))
        self.assertAlmostEqual(func.calc(T=500.0), self.polynomialEvaluation(coefficientsMap, 500.0))

    def test_polynomialEqnFloatFloat(self):
        """Evaluates a PolynomialFunction with floating point coefficients and floating point power terms."""
        coefficientsMap = {0.5: -2.5, 2.5: 5.389, 1.5: 4.375}
        data = {"type": "symbolic", "equation": self.createEqnPoly(coefficientsMap)}

        mat = self._createFunction(data, minT=0.0)
        mat.name = self.testName
        self.assertEqual(str(mat), f"<Material {self.testName} <MaterialType Metal>>")
        func = mat.rho

        self.assertAlmostEqual(func.calc({"T": 0.0}), self.polynomialEvaluation(coefficientsMap, 0.0))
        self.assertAlmostEqual(func.calc({"T": 100.0}), self.polynomialEvaluation(coefficientsMap, 100.0))
        self.assertAlmostEqual(func.calc({"T": 500.0}), self.polynomialEvaluation(coefficientsMap, 500.0))

    def test_polynomialDiffFloatTypes(self):
        """Evaluates a PolynomialFunction with floating point coefficients power terms, checking exact values."""
        coefficientsMap = {0.5: -2.5, 2.5: 5.389, 1.5: 4.375}
        data = {"type": "symbolic", "equation": self.createEqnPoly(coefficientsMap)}

        mat = self._createFunction(data, minT=0.0)
        self.assertAlmostEqual(mat.rho.calc({"T": np.float64(0.0)}), 0.0)
        self.assertAlmostEqual(mat.rho.calc({"T": np.float64(100.0)}), 543250.0)
        self.assertAlmostEqual(mat.rho.calc({"T": np.float64(500.0)}), 30174283.91217429)

    def test_symbolicEqnError(self):
        """Ensure symbolic equations fail correctly when given empty or nonsense inputs."""
        # Leave out equation node
        dataNoCoeff = {"type": "symbolic"}
        with self.assertRaises(KeyError):
            self._createFunction(dataNoCoeff)

        # Provide invalid equation node.
        dataBadCoeff = {"type": "symbolic", "equation": "NOT AN EQUATION"}
        with self.assertRaises(ValueError):
            self._createFunction(dataBadCoeff)

    def test_powerEqn(self):
        """Evaluates a PowerLaw with floating point coefficients and exponents."""
        mat = self._createFunction(self.basePowerLawData)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 0}), self.powerLawEvaluation(self.basePowerLawTerms, 0))
        self.assertAlmostEqual(func.calc({"T": 12.5}), self.powerLawEvaluation(self.basePowerLawTerms, 12.5))
        self.assertAlmostEqual(func.calc({"T": 25}), self.powerLawEvaluation(self.basePowerLawTerms, 25))
        self.assertAlmostEqual(func.calc({"T": 50}), self.powerLawEvaluation(self.basePowerLawTerms, 50))
        self.assertAlmostEqual(func.calc({"T": 75}), self.powerLawEvaluation(self.basePowerLawTerms, 75))
        self.assertAlmostEqual(func.calc({"T": 100}), self.powerLawEvaluation(self.basePowerLawTerms, 100))

    def test_powerEqnAllInt(self):
        """Evaluates a PowerLaw with integer coefficients and exponents."""
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

        mat = self._createFunction(powerLawDataInt)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 0}), self.powerLawEvaluation(coefficients, 0))
        self.assertAlmostEqual(func.calc({"T": 25}), self.powerLawEvaluation(coefficients, 25))
        self.assertAlmostEqual(func.calc({"T": 50}), self.powerLawEvaluation(coefficients, 50))
        self.assertAlmostEqual(func.calc({"T": 75}), self.powerLawEvaluation(coefficients, 75))
        self.assertAlmostEqual(func.calc({"T": 100}), self.powerLawEvaluation(coefficients, 100))

    def test_powerEqnFloatInt(self):
        """Evaluates a PowerLaw with a mixture of integer and floating point coefficients and exponents."""
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

        mat = self._createFunction(powerLawDataInt)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 0}), self.powerLawEvaluation(coefficients, 0))
        self.assertAlmostEqual(func.calc({"T": 25}), self.powerLawEvaluation(coefficients, 25))
        self.assertAlmostEqual(func.calc({"T": 50}), self.powerLawEvaluation(coefficients, 50))
        self.assertAlmostEqual(func.calc({"T": 75}), self.powerLawEvaluation(coefficients, 75))
        self.assertAlmostEqual(func.calc({"T": 100}), self.powerLawEvaluation(coefficients, 100))

    def test_powerEqnNoInter(self):
        """Evaluates a PowerLaw with no intercept term."""
        coefficients = {"exponent": 2.0, "inner adder": 125.0, "outer multiplier": 3.4}
        data = {"type": "symbolic", "equation": self.createEqnPower(coefficients)}
        mat = self._createFunction(data)

        # Intercept in self.powerLawEvaluation is 0.0 to reflect default value in matProps
        self.assertAlmostEqual(mat.rho.calc({"T": 0}), self.powerLawEvaluation(coefficients, 0))
        self.assertAlmostEqual(mat.rho.calc({"T": 25}), self.powerLawEvaluation(coefficients, 25))
        self.assertAlmostEqual(mat.rho.calc({"T": 50}), self.powerLawEvaluation(coefficients, 50))
        self.assertAlmostEqual(mat.rho.calc({"T": 75}), self.powerLawEvaluation(coefficients, 75))
        self.assertAlmostEqual(mat.rho.calc({"T": 100}), self.powerLawEvaluation(coefficients, 100))

    def test_powerEqnNoOuter(self):
        """Evaluates a PowerLaw with no outer multiplier term."""
        coefficients = {"exponent": 2.0, "inner adder": 125.0, "intercept": -2.5}
        data = {"type": "symbolic", "equation": self.createEqnPower(coefficients)}

        mat = self._createFunction(data)
        func = mat.rho
        # Outer multiplier in self.powerLawEvaluation is 1.0 to reflect default value in matProps
        self.assertAlmostEqual(func.calc({"T": 0}), self.powerLawEvaluation(coefficients, 0))
        self.assertAlmostEqual(func.calc({"T": 25}), self.powerLawEvaluation(coefficients, 25))
        self.assertAlmostEqual(func.calc({"T": 50}), self.powerLawEvaluation(coefficients, 50))
        self.assertAlmostEqual(func.calc({"T": 75}), self.powerLawEvaluation(coefficients, 75))
        self.assertAlmostEqual(func.calc({"T": 100}), self.powerLawEvaluation(coefficients, 100))

    def test_powerEqnNoOuterInter(self):
        """Evaluates a PowerLaw with no outer multiplier or intercept term."""
        coefficients = {"exponent": 2.0, "inner adder": 125.0}
        data = {"type": "symbolic", "equation": self.createEqnPower(coefficients)}

        mat = self._createFunction(data)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 0}), self.powerLawEvaluation(coefficients, 0))
        self.assertAlmostEqual(func.calc({"T": 25}), self.powerLawEvaluation(coefficients, 25))
        self.assertAlmostEqual(func.calc({"T": 50}), self.powerLawEvaluation(coefficients, 50))
        self.assertAlmostEqual(func.calc({"T": 75}), self.powerLawEvaluation(coefficients, 75))
        self.assertAlmostEqual(func.calc({"T": 100}), self.powerLawEvaluation(coefficients, 100))

    def test_constantsEval(self):
        """Evaluates a PowerLaw for integer and floating point values."""
        mat = self._createFunction(self.baseConstantData)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": 0}), 9123.5)
        self.assertAlmostEqual(func.calc({"T": 12.5}), 9123.5)
        self.assertAlmostEqual(func.calc({"T": 50}), 9123.5)
        self.assertAlmostEqual(func.calc({"T": 100}), 9123.5)

    def test_hyperbolicEqnEval(self):
        """Evaluates a HyperbolicFunction for integer and floating point values."""
        mat = self._createFunction(self.baseHyperbolicData)

        # test using input dict for calc
        self.assertAlmostEqual(mat.rho.calc({"T": 0}), self.hyperbolicEvaluation(self.baseHyperbolicTerms, 0))
        self.assertAlmostEqual(mat.rho.calc({"T": 12.5}), self.hyperbolicEvaluation(self.baseHyperbolicTerms, 12.5))
        self.assertAlmostEqual(mat.rho.calc({"T": 50}), self.hyperbolicEvaluation(self.baseHyperbolicTerms, 50))
        self.assertAlmostEqual(mat.rho.calc({"T": 100}), self.hyperbolicEvaluation(self.baseHyperbolicTerms, 100))

        # test using kwargs for calc
        self.assertAlmostEqual(mat.rho.calc(T=0), self.hyperbolicEvaluation(self.baseHyperbolicTerms, 0))
        self.assertAlmostEqual(mat.rho.calc(T=12.5), self.hyperbolicEvaluation(self.baseHyperbolicTerms, 12.5))
        self.assertAlmostEqual(mat.rho.calc(T=50), self.hyperbolicEvaluation(self.baseHyperbolicTerms, 50))
        self.assertAlmostEqual(mat.rho.calc(T=100), self.hyperbolicEvaluation(self.baseHyperbolicTerms, 100))

    def test_hyperbolicEqnEval2(self):
        """Evaluates a HyperbolicFunction for a different set of floating point values."""
        coefficients = {
            "hyperbolic function": "tanh",
            "intercept": 3.829e8,
            "outer multiplier": -4.672e8,
            "inner denominator": 216.66,
            "inner adder": -613.52,
        }
        data = {"type": "symbolic", "equation": self.createEqnHyper(coefficients)}
        mat = self._createFunction(data)
        func = mat.rho
        expectedValue = self.hyperbolicEvaluation(coefficients, 500)
        self.assertAlmostEqual(func.calc({"T": 500}), expectedValue, delta=expectedValue * 1e-5)
