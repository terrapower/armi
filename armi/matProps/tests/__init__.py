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

"""Generic testing tools for the matProps package."""

import math
import unittest

from armi.matProps.material import Material


class MatPropsFunTestBase(unittest.TestCase):
    """Base class that provides some common functionality for testing matProps Functions."""

    def setUp(self):
        self.testName = self.id().split(".")[-1]
        searchStr = "test_"
        if self.testName.startswith(searchStr):
            self.testName = self.testName[len(searchStr) :]

    @staticmethod
    def polynomialEvaluation(powerMap, value):
        """
        Perform a polynomial evaluation at a specified value.

        Parameters
        ----------
        powerMap : dict
            Dictionary mapping power to its corresponding coefficient.
        value: float
            Independent variable to evaluate the polynomial at.

        Returns
        -------
        float
            The polynomial evaluation
        """
        return sum(coefficient * pow(value, power) for power, coefficient in powerMap.items())

    @staticmethod
    def powerLawEvaluation(coefficients, value):
        """Perform a power law evaluation at a specified value."""
        intercept = coefficients.get("intercept", 0.0)
        outerMultiplier = coefficients.get("outer multiplier", 1.0)
        innerAdder = coefficients["inner adder"]
        exponent = coefficients["exponent"]

        return intercept + outerMultiplier * (value + innerAdder) ** exponent

    @staticmethod
    def hyperbolicEvaluation(coefficients, value):
        """Perform a hyperbolic function evaluation at a specified value."""
        intercept = coefficients["intercept"]
        outerMultiplier = coefficients["outer multiplier"]
        innerAdder = coefficients["inner adder"]
        innerDenominator = coefficients["inner denominator"]

        return intercept + outerMultiplier * math.tanh((value + innerAdder) / innerDenominator)

    @staticmethod
    def createEqnPoly(coefficients):
        """Creates a symbolic polynomial function from a dictionary of powers."""
        eqn = ""
        for power, value in coefficients.items():
            if not eqn:
                # Make sure we don't have a leading + sign
                eqn += f"{value}*T**{power}"
            else:
                eqn += f" + {value}*T**{power}"
        return eqn

    @staticmethod
    def createEqnPower(coefficients):
        """Creates a symbolic power law function from a dictionary of constants."""
        eqn = f"{coefficients.get('intercept', '')}"
        if "outer multiplier" in coefficients:
            eqn += f" + {coefficients['outer multiplier']}*"
        else:
            eqn += " +"
        eqn += f"(T + {coefficients['inner adder']})**{coefficients['exponent']}"
        return eqn

    @staticmethod
    def createEqnHyper(coefficients):
        """Creates a symbolic hyperbolic function from a dictionary of constants."""
        return (
            f"{coefficients['intercept']} + "
            f"{coefficients['outer multiplier']}*"
            f"{coefficients['hyperbolic function']}("
            f"(T+{coefficients['inner adder']})/{coefficients['inner denominator']})"
        )

    def _createFunctionWithoutTable(self, data=None):
        """
        Helper function designed to create a basic viable yaml file without tabulated data in the function.

        Parameters
        ----------
        data : dict
            A dictionary containing user specified function child nodes.
        """
        funcBody = {"T": {"min": -100.0, "max": 500.0}}
        funcBody.update(data or {})
        materialData = {
            "file format": "TESTS",
            "composition": {"Fe": "balance"},
            "material type": "Metal",
            "density": {"function": funcBody},
        }

        mat = Material()
        mat.loadNode(materialData)

        return mat

    def _createFunction(self, data=None, tableData=None, minT=-100.0, maxT=500.0):
        """
        Helper function designed to create a basic viable yaml file.

        Parameters
        ----------
        data : dict
            A dictionary containing user specified function child nodes.
        tableData : dict
            Table data to include in the function definition
        minT : float
            Float containing the minimum T variable value for the function.
        maxT : float
            Float containing the maximum T variable value for the function.
        """
        funcBody = {"T": {"min": minT, "max": maxT}}
        funcBody.update(data or {})
        materialData = {
            "file format": "TESTS",
            "composition": {"Fe": "balance"},
            "material type": "Metal",
            "density": {"function": funcBody, "tabulated data": tableData or {}},
        }

        mat = Material()
        mat.loadNode(materialData)

        return mat

    def belowMinimumCheck(self, yamlData, tableData=None):
        """Check if a ValueError is thrown if attempting to evaluate below the min value of a given T variable."""
        mat = self._createFunction(yamlData, tableData)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": func.getMinBound("T") - 0.01})

    def aboveMaximumCheck(self, yamlData, tableData=None):
        """Checksif a ValueError is thrown if attempting to evaluate above the max value of the T variable."""
        mat = self._createFunction(yamlData, tableData)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": func.getMaxBound("T") + 0.01})
