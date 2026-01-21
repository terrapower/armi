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

"""Tests related to piecewise functions."""

from ruamel.yaml import YAML

from armi import matProps
from armi.matProps.tests import FunctionTestClassBase


class TestPiecewiseFunction(FunctionTestClassBase):
    """Tests related to piecewise functions."""

    @classmethod
    def setUpClass(cls):
        """Initialization method for function data."""
        super().setUpClass()

        cls.basePiecewiseData = {
            "type": "piecewise",
            "T": {
                "min": 0,
                "max": 100,
            },
            "functions": [
                {
                    "function": {
                        "T": {"min": 0, "max": 25.4},
                        "type": "symbolic",
                        "equation": "10",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 25.4, "max": 50},
                        "type": "symbolic",
                        "equation": "99",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 50, "max": 100},
                        "type": "symbolic",
                        "equation": "-99",
                    },
                    "tabulated data": None,
                },
            ],
        }

    def test_piecewise_eqn_eval(self):
        """
        Tests the parsing of a PiecewiseFunction and make sure it evaluates at the appropriate sub function.

        Input File: This test creates the file T_PIECEWISE_EQN_EVAL.yaml.

        This test ensures that the override methods PiecewiseFunction._parse_specific() and
        PiecewiseFunction._calc_specific() are functioning appropriately. A minimal YAML file with a piecewise function
        consisting of three temperature-dependent constant functions is provided in this test. The function is evaluated
        at values in all temperature regions of the piecewise function and checked against the expected outputs.
        """
        mat = self._create_function(self.basePiecewiseData)
        func = mat.rho
        self.assertIn("PiecewiseFunction", str(func))
        self.assertAlmostEqual(func.calc({"T": 0}), 10)
        self.assertAlmostEqual(func.calc({"T": 25.4}), 10)
        self.assertAlmostEqual(func.calc({"T": 25.41}), 99)
        self.assertAlmostEqual(func.calc({"T": 50}), 99)
        self.assertAlmostEqual(func.calc({"T": 50.1}), -99)
        self.assertAlmostEqual(func.calc({"T": 100}), -99)

    def test_piecewise_eqn_gap(self):
        """
        Test that PiecewiseFunction evaluates correctly with gaps.

        Input File: This test creates the file T_PIECEWISE_EQN_GAP.yaml.

        This test checks that matProps can properly handle evaluations of a piecewise function outside of its defined
        domain. This scenario tests outside the boundaries of the piecewise function as well as the special case where
        gaps occur between piecewise regions. Values outside the bounds of any of the piecewise components should throw
        an error.
        """
        data = {
            "type": "piecewise",
            "functions": [
                {
                    "function": {
                        "T": {"min": 0, "max": 20},
                        "type": "symbolic",
                        "equation": "10",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 30, "max": 50},
                        "type": "symbolic",
                        "equation": "99",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 50, "max": 100},
                        "type": "symbolic",
                        "equation": "-99",
                    },
                    "tabulated data": None,
                },
            ],
        }

        mat = self._create_function(data)
        func = mat.rho
        with self.assertRaisesRegex(ValueError, "PiecewiseFunction error, could not evaluate"):
            func.calc({"T": -1.0})

        with self.assertRaisesRegex(ValueError, "PiecewiseFunction error, could not evaluate"):
            func.calc({"T": 25.0})

        with self.assertRaisesRegex(ValueError, "PiecewiseFunction error, could not evaluate"):
            func.calc({"T": 101.0})

        self.assertAlmostEqual(func.calc({"T": 0}), 10)
        self.assertAlmostEqual(func.calc({"T": 10}), 10)
        self.assertAlmostEqual(func.calc({"T": 20}), 10)
        self.assertAlmostEqual(func.calc({"T": 30}), 99)
        self.assertAlmostEqual(func.calc({"T": 40}), 99)
        self.assertAlmostEqual(func.calc({"T": 50}), 99)
        self.assertAlmostEqual(func.calc({"T": 75}), -99)
        self.assertAlmostEqual(func.calc({"T": 100}), -99)

    def test_piecewise_eqn_poly(self):
        """
        Test that makes a PiecewiseFunction composed of multiple PolynomialFunctions.

        Input File: This test creates the file T_PIECEWISE_EQN_POLY.yaml.

        A minimal YAML file with defined temperature dependent polynomial piecewise functions is provided in this test.
        The function is evaluated at values in all temperature regions of the piecewise function and checked against the
        expected outputs.
        """
        poly1CoMap = {0: -2.5, 1: 5, 2: 4}
        poly2CoMap = {0: 3.5, 1: 3, 2: -2, 3: 1}
        poly3CoMap = {0: 4.5, 1: -2, 2: 3, 3: -2, 4: 1}
        data = {
            "type": "piecewise",
            "functions": [
                {
                    "function": {
                        "T": {"min": -100, "max": 100},
                        "type": "symbolic",
                        "equation": self.createEqnPoly(poly1CoMap),
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 100, "max": 300},
                        "type": "symbolic",
                        "equation": self.createEqnPoly(poly2CoMap),
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 300, "max": 500},
                        "type": "symbolic",
                        "equation": self.createEqnPoly(poly3CoMap),
                    },
                    "tabulated data": None,
                },
            ],
        }

        mat = self._create_function(data)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": -100.0}), self.polynomialEvaluation(poly1CoMap, -100.0))
        self.assertAlmostEqual(func.calc({"T": 0.0}), self.polynomialEvaluation(poly1CoMap, 0.0))
        self.assertAlmostEqual(func.calc({"T": 100.0}), self.polynomialEvaluation(poly1CoMap, 100.0))
        self.assertAlmostEqual(func.calc({"T": 200.0}), self.polynomialEvaluation(poly2CoMap, 200.0))
        self.assertAlmostEqual(func.calc({"T": 300.0}), self.polynomialEvaluation(poly2CoMap, 300.0))
        self.assertAlmostEqual(func.calc({"T": 400.0}), self.polynomialEvaluation(poly3CoMap, 400.0))
        self.assertAlmostEqual(func.calc({"T": 500.0}), self.polynomialEvaluation(poly3CoMap, 500.0))

    def test_piecewise_eqn_polytable(self):
        """
        Test that makes a PiecewiseFunction composed of a mixture of polynomial and table functions.

        Input file: This test creates the file T_PIECEWISE_EQN_POLYTABLE.yaml.

        A minimal YAML file with temperature dependent polynomial and tabular piecewise functions is provided in this
        test. The function is evaluated in all temperature regions of the piecewise function and checked against the
        expected outputs.
        """
        poly1CoMap = {0: 3.5, 1: 3, 2: -2, 3: 1}
        poly2CoMap = {0: 4.5, 1: -2, 2: 3, 3: -2, 4: 1}
        data = {
            "type": "piecewise",
            "functions": [
                {
                    "function": {
                        "T": 0,
                        "type": "table",
                    },
                    "tabulated data": [[-100.0, -50.0], [0.0, 0.0], [100.0, 50.0]],
                },
                {
                    "function": {
                        "T": {"min": 100, "max": 300},
                        "type": "symbolic",
                        "equation": self.createEqnPoly(poly1CoMap),
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 300, "max": 500},
                        "type": "symbolic",
                        "equation": self.createEqnPoly(poly2CoMap),
                    },
                    "tabulated data": None,
                },
            ],
        }

        mat = self._create_function(data)
        func = mat.rho

        self.assertAlmostEqual(func.calc({"T": -100.0}), -50.0)
        self.assertAlmostEqual(func.calc({"T": -50.0}), -25.0)
        self.assertAlmostEqual(func.calc({"T": 0.0}), 0.0)
        self.assertAlmostEqual(func.calc({"T": 50.0}), 25.0)
        self.assertAlmostEqual(func.calc({"T": 100.0}), 50.0)
        self.assertAlmostEqual(func.calc({"T": 200.0}), self.polynomialEvaluation(poly1CoMap, 200.0))
        self.assertAlmostEqual(func.calc({"T": 300.0}), self.polynomialEvaluation(poly1CoMap, 300.0))
        self.assertAlmostEqual(func.calc({"T": 400.0}), self.polynomialEvaluation(poly2CoMap, 400.0))
        self.assertAlmostEqual(func.calc({"T": 500.0}), self.polynomialEvaluation(poly2CoMap, 500.0))

    def test_input_check_piecewise_mintemp(self):
        """
        Test to make sure an error is thrown when attempting to evaluate below the minimum valid range.

        Input file: This test creates the file T_INPUT_CHECK_PIECEWISE_MINTEMP.yaml.

        A minimal YAML file with a defined piecewise function is provided in this test. Tests that an error is raised
        when a value below the minimum valid range is used with a piecewise function.
        """
        self.belowMinimumCheck(self.basePiecewiseData)

    def test_input_check_piecewise_maxtemp(self):
        """
        Test to make sure an error is thrown when attempting to evaluate above the maximum valid range.

        Input file: This test creates the file T_INPUT_CHECK_PIECEWISE_MAXTEMP.yaml.

        A minimal YAML file with a defined piecewise function is provided in this test. Tests that a ValueError is
        raised when a value above the maximum valid range is used with a piecewise function.
        """
        self.aboveMaximumCheck(self.basePiecewiseData)

    def _create_function2D(self, data=None, outFileName=None):
        """
        Helper function designed to create a basic viable yaml file for a two dimensional function.

        Parameters
        ----------
        data : dict
            A dictionary containing user specified function child nodes.
        outFileName : str
            String containing path of test file to create.
        """
        if outFileName is None:
            outFileName = self.testFileName
        with open(outFileName, "w", encoding="utf-8") as f:
            funcBody = {"T": {"min": -100, "max": 100}, "t": {"min": -100, "max": 100}}
            funcBody.update(data or {})
            materialData = {
                "file format": "TESTS",
                "composition": {"Fe": "balance"},
                "material type": "Metal",
                "density": {"function": funcBody, "tabulated data": {}},
            }
            yaml = YAML()
            yaml.dump(materialData, f)

        return matProps.load_material(outFileName)

    def test_piecewise_eqn_2d(self):
        """
        Test that PiecewiseFunction evaluates correctly with multiple dimensions.

        Input file: This test creates the file T_PIECEWISE_EQN_2D.yaml.

        This test checks that matProps can properly handle evaluations of a piecewise function inside and outside of its
        defined independent variable domain. This scenario tests inside the boundaries of a two dimensional piecewise
        function and outside the boundaries of the piecewise function as well as the special case where gaps occur
        between piecewise regions. Values outside the bounds of any of the piecewise components should throw an error.
        """
        data = {
            "type": "piecewise",
            "functions": [
                {
                    "function": {
                        "T": {"min": 0, "max": 20},
                        "t": {"min": 0, "max": 20},
                        "type": "symbolic",
                        "equation": "10",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 30, "max": 40},
                        "t": {"min": 0, "max": 20},
                        "type": "symbolic",
                        "equation": "99",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 0, "max": 20},
                        "t": {"min": 30, "max": 40},
                        "type": "symbolic",
                        "equation": "20",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 30, "max": 40},
                        "t": {"min": 30, "max": 40},
                        "type": "symbolic",
                        "equation": "199",
                    },
                    "tabulated data": None,
                },
            ],
        }

        mat = self._create_function2D(data)
        func = mat.rho
        # Below var 1
        with self.assertRaisesRegex(ValueError, "PiecewiseFunction error, could not evaluate"):
            func.calc({"T": -1.0, "t": 10})
        # Middle gap var 1
        with self.assertRaisesRegex(ValueError, "PiecewiseFunction error, could not evaluate"):
            func.calc({"T": 25.0, "t": 10})

        # Above var 1
        with self.assertRaisesRegex(ValueError, "PiecewiseFunction error, could not evaluate"):
            func.calc({"T": 45.0, "t": 10})

        # Below var 2
        with self.assertRaisesRegex(ValueError, "PiecewiseFunction error, could not evaluate"):
            func.calc({"T": 10, "t": -1})

        # Middle gap var 2
        with self.assertRaisesRegex(ValueError, "PiecewiseFunction error, could not evaluate"):
            func.calc({"T": 10, "t": 25})

        # Above var 2
        with self.assertRaisesRegex(ValueError, "PiecewiseFunction error, could not evaluate"):
            func.calc({"T": 10, "t": 45})

        self.assertAlmostEqual(func.calc({"T": 10, "t": 10}), 10)
        self.assertAlmostEqual(func.calc({"T": 10, "t": 35}), 20)
        self.assertAlmostEqual(func.calc({"T": 35, "t": 10}), 99)
        self.assertAlmostEqual(func.calc({"T": 35, "t": 35}), 199)

    def test_piecewise_eqn_overlap(self):
        """
        Test that PiecewiseFunction fails to load with overlapping regions.

        Input file: This test creates the file T_PIECEWISE_EQN_OVERLAP.yaml.

        This test checks that matProps can properly identify and throw an error when piecewise functions have
        overlapping regions. A piecewise function where two of the four regions are overlapping is provided and an error
        is checked for on loading.
        """
        data = {
            "type": "piecewise",
            "functions": [
                {
                    "function": {
                        "T": {"min": 0, "max": 20},
                        "t": {"min": 0, "max": 20},
                        "type": "symbolic",
                        "equation": "10",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 10, "max": 40},
                        "t": {"min": 0, "max": 20},
                        "type": "symbolic",
                        "equation": "99",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 0, "max": 20},
                        "t": {"min": 30, "max": 40},
                        "type": "symbolic",
                        "equation": "20",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 30, "max": 40},
                        "t": {"min": 30, "max": 40},
                        "type": "symbolic",
                        "equation": "199",
                    },
                    "tabulated data": None,
                },
            ],
        }

        with self.assertRaisesRegex(ValueError, "Piecewise child functions overlap"):
            self._create_function2D(data)

    def test_piecewise_eqn_diffvars(self):
        """
        Test that PiecewiseFunction fails to load when child functions use different variables.

        Input file:  This test creates the file T_PIECEWISE_EQN_DIFFVARS.yaml.

        This test checks that matProps can properly identify and throw an error when piecewise functions have child
        functions that have different variables used in the bounds. A piecewise function where two of regions are use
        divergent variables is provided and an error is checked for on loading.
        """
        data = {
            "type": "piecewise",
            "functions": [
                {
                    "function": {
                        "T": {"min": 0, "max": 20},
                        "t": {"min": 0, "max": 20},
                        "type": "symbolic",
                        "equation": "10",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 30, "max": 40},
                        "t": {"min": 0, "max": 20},
                        "type": "symbolic",
                        "equation": "99",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "R": {"min": 0, "max": 20},
                        "t": {"min": 30, "max": 40},
                        "type": "symbolic",
                        "equation": "20",
                    },
                    "tabulated data": None,
                },
                {
                    "function": {
                        "T": {"min": 30, "max": 40},
                        "t": {"min": 30, "max": 40},
                        "type": "symbolic",
                        "equation": "199",
                    },
                    "tabulated data": None,
                },
            ],
        }

        with self.assertRaisesRegex(KeyError, "Piecewise child function must have same variables"):
            self._create_function2D(data)
