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
import os
import shutil
import unittest

from ruamel.yaml import YAML

import armi.matProps


class FunctionTestClassBase(unittest.TestCase):
    """Base class that provides some common functionality for function related tests."""

    @classmethod
    def setUpClass(cls):
        """Initialization method for TestFunctions. Sets up all class members prior to tests being run."""
        cls.dirname = os.path.join(os.path.dirname(os.path.realpath(__file__)), "outputFiles", "functionTests")
        if os.path.exists(cls.dirname):
            shutil.rmtree(cls.dirname)

        os.makedirs(cls.dirname)

    def setUp(self):
        self.testName = self.id().split(".")[-1]
        searchStr = "test_"
        if self.testName.startswith(searchStr):
            self.testName = self.testName[len(searchStr) :]
        self.testFileName = os.path.join(self.dirname, self.testName + ".yaml")

    @property
    def filePrefix(self):
        """Return the file prefix for a file name."""
        return os.path.splitext(os.path.basename(self.testFileName))[0]

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

    def _create_function_without_table(self, data=None):
        """
        Helper function designed to create a basic viable yaml file without tabulated data in the function.

        Parameters
        ----------
        data : dict
            A dictionary containing user specified function child nodes.
        """
        with open(self.testFileName, "w", encoding="utf-8") as f:
            funcBody = {"T": {"min": -100.0, "max": 500.0}}
            funcBody.update(data or {})
            materialData = {
                "file format": "TESTS",
                "composition": {"Fe": "balance"},
                "material type": "Metal",
                "density": {"function": funcBody},
            }
            yaml = YAML()
            yaml.dump(materialData, f)

        return armi.matProps.load_material(self.testFileName)

    def _create_function(self, data=None, tableData=None, minT=-100.0, maxT=500.0, outFileName=None):
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
        outFileName : str
            String containing path of test file to create.
        """
        if outFileName is None:
            outFileName = self.testFileName
        with open(outFileName, "w", encoding="utf-8") as f:
            funcBody = {"T": {"min": minT, "max": maxT}}
            funcBody.update(data or {})
            materialData = {
                "file format": "TESTS",
                "composition": {"Fe": "balance"},
                "material type": "Metal",
                "density": {
                    "function": funcBody,
                    "tabulated data": tableData or {},
                },
            }
            yaml = YAML()
            yaml.dump(materialData, f)

        return armi.matProps.load_material(outFileName)

    def belowMinimumCheck(self, yamlData, tableData=None):
        """
        Helper function that checks if a ValueError is thrown if attempting to evaluate below the min value of a given T
        variable.
        """
        mat = self._create_function(yamlData, tableData)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": func.get_min_bound("T") - 0.01})

    def aboveMaximumCheck(self, yamlData, tableData=None):
        """
        Helper function that checks if a ValueError is thrown if attempting to evaluate above the max value of the T
        variable.
        """
        mat = self._create_function(yamlData, tableData)
        func = mat.rho
        with self.assertRaises(ValueError):
            func.calc({"T": func.get_max_bound("T") + 0.01})
