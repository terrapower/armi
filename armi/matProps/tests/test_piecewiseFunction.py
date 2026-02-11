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

from armi.matProps.material import Material
from armi.matProps.tests import MatPropsFunTestBase


class TestPiecewiseFunction(MatPropsFunTestBase):
    """Tests related to piecewise functions."""

    @classmethod
    def setUpClass(cls):
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

    def test_piecewiseEqnEval(self):
        """Tests the parsing of a PiecewiseFunction and make sure it evaluates at the appropriate sub function."""
        mat = self._createFunction(self.basePiecewiseData)
        func = mat.rho
        self.assertIn("PiecewiseFunction", str(func))
        self.assertAlmostEqual(func.calc({"T": 0}), 10)
        self.assertAlmostEqual(func.calc({"T": 25.4}), 10)
        self.assertAlmostEqual(func.calc({"T": 25.41}), 99)
        self.assertAlmostEqual(func.calc({"T": 50}), 99)
        self.assertAlmostEqual(func.calc({"T": 50.1}), -99)
        self.assertAlmostEqual(func.calc({"T": 100}), -99)

    def test_piecewiseEqnGap(self):
        """Test that PiecewiseFunction evaluates correctly with gaps."""
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

        mat = self._createFunction(data)
        func = mat.rho
        with self.assertRaisesRegex(ValueError, "PiecewiseFunction error, could not evaluate"):
            func.calc({"T": -1.0})

        with self.assertRaisesRegex(ValueError, "PiecewiseFunction error, could not evaluate"):
            func.calc({"T": 25.0})

        with self.assertRaisesRegex(ValueError, "PiecewiseFunction error, could not evaluate"):
            func.calc({"T": 101.0})

        self.assertAlmostEqual(func.calc(T=0), 10)
        self.assertAlmostEqual(func.calc(T=10), 10)
        self.assertAlmostEqual(func.calc(T=20), 10)
        self.assertAlmostEqual(func.calc(T=30), 99)
        self.assertAlmostEqual(func.calc(T=40), 99)
        self.assertAlmostEqual(func.calc(T=50), 99)
        self.assertAlmostEqual(func.calc(T=75), -99)
        self.assertAlmostEqual(func.calc(T=100), -99)

    def test_piecewiseEqnPoly(self):
        """Test that makes a PiecewiseFunction composed of multiple PolynomialFunctions."""
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

        mat = self._createFunction(data)
        func = mat.rho
        self.assertAlmostEqual(func.calc({"T": -100.0}), self.polynomialEvaluation(poly1CoMap, -100.0))
        self.assertAlmostEqual(func.calc({"T": 0.0}), self.polynomialEvaluation(poly1CoMap, 0.0))
        self.assertAlmostEqual(func.calc({"T": 100.0}), self.polynomialEvaluation(poly1CoMap, 100.0))
        self.assertAlmostEqual(func.calc({"T": 200.0}), self.polynomialEvaluation(poly2CoMap, 200.0))
        self.assertAlmostEqual(func.calc({"T": 300.0}), self.polynomialEvaluation(poly2CoMap, 300.0))
        self.assertAlmostEqual(func.calc({"T": 400.0}), self.polynomialEvaluation(poly3CoMap, 400.0))
        self.assertAlmostEqual(func.calc({"T": 500.0}), self.polynomialEvaluation(poly3CoMap, 500.0))

    def test_piecewiseEqnPolyTable(self):
        """Test that makes a PiecewiseFunction composed of a mixture of polynomial and table functions."""
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

        mat = self._createFunction(data)
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

    def test_inputCheckPiecewiseMinTemp(self):
        """Test to make sure an error is thrown when attempting to evaluate below the minimum valid range."""
        self.belowMinimumCheck(self.basePiecewiseData)

    def test_inputCheckPiecewiseMaxTemp(self):
        """Test to make sure an error is thrown when attempting to evaluate above the maximum valid range."""
        self.aboveMaximumCheck(self.basePiecewiseData)

    def _createFunction2D(self, data=None):
        """
        Helper function designed to create a basic viable yaml file for a two dimensional function.

        Parameters
        ----------
        data : dict
            A dictionary containing user specified function child nodes.
        """
        funcBody = {"T": {"min": -100, "max": 100}, "t": {"min": -100, "max": 100}}
        funcBody.update(data or {})
        materialData = {
            "file format": "TESTS",
            "composition": {"Fe": "balance"},
            "material type": "Metal",
            "density": {"function": funcBody, "tabulated data": {}},
        }

        mat = Material()
        mat.loadNode(materialData)

        return mat

    def test_piecewiseEqn2d(self):
        """Test that PiecewiseFunction evaluates correctly with multiple dimensions."""
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

        mat = self._createFunction2D(data)
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

        self.assertAlmostEqual(func.calc(T=10, t=10), 10)
        self.assertAlmostEqual(func.calc(T=10, t=35), 20)
        self.assertAlmostEqual(func.calc(T=35, t=10), 99)
        self.assertAlmostEqual(func.calc(T=35, t=35), 199)

    def test_piecewiseEqnOverlap(self):
        """Test that PiecewiseFunction fails to load with overlapping regions."""
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
            self._createFunction2D(data)

    def test_piecewiseEqnDiffVars(self):
        """Test that PiecewiseFunction fails to load when child functions use different variables."""
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
            self._createFunction2D(data)
