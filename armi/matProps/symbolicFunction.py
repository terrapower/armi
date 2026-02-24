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

"""A generic symbolic function support for curves in a material YAML file."""

# Import math so that it is available for the eval statement
import math
from copy import copy

from sympy import symbols
from sympy.parsing import parse_expr
from sympy.utilities.lambdify import lambdastr

from armi.matProps.function import Function


class SymbolicFunction(Function):
    """
    A symbolic function. A functional form defined in the YAML file is parsed.

    An example with the YAML format is::

        function:
          <var1>:
            min: <min1>
            max: <max1>
          <var2>:
            min: <min2>
            max: <max2>
          ...
          type: symbolic
          equation: <functional form>
    """

    def __init__(self, mat, prop):
        """
        Constructor for SymbolicFunction object.

        Parameters
        ----------
        mat: Material
            Material object with which this SymbolicFunction is associated
        prop: Property
            Property that is represented by this SymbolicFunction
        """
        super().__init__(mat, prop)
        self.eqn = None
        self.sympyStr = None

    def _parseSpecific(self, node):
        """
        Parses nodes that are specific to Symbolic Function object.

        Parameters
        ----------
        node: dict
            Dictionary containing the node whose values will be parsed to fill object.
        """
        eqn = str(node["function"]["equation"])

        try:
            symbolList = []
            for var in self.independentVars:
                symbolList.append(symbols(var))
            sympyEqn = parse_expr(eqn, evaluate=False)
            self.sympyStr = lambdastr(symbolList, sympyEqn)
            self.eqn = eval(self.sympyStr)

            # Try evaluating the function at the maximum bound. This should result in a number if the equation is
            # properly formatted. Bad equations will throw an error either in the `lambdastr` `eval` or this `float( )`
            # line. This is important to catch poor equations now before they cause problems intermittently later (only
            # when calc is called for that equation).
            point = []
            for var in self.independentVars:
                point.append(self.getMaxBound(var))

            float(self.eqn(*point))
        except Exception as e:
            raise ValueError(
                f"Equation provided could not be interpreted:"
                f" {eqn}, {getattr(self, 'sympyStr', 'Symbolic string not created yet.')}"
            ) from e

    def _calcSpecific(self, point: dict) -> float:
        """
        Returns an evaluation for a symbolic function.

        Parameters
        ----------
        point: dict
            dictionary of independent variable/value pairs
        """
        result = self.eqn(*[point[var] for var in self.independentVars])
        if isinstance(result, complex):
            raise ValueError(f"Function is undefined at {point}. Evaluates to complex number: {result}")
        if math.isnan(result):
            raise ValueError(f"Function is undefined at {point}. Evaluates to not a number.")

        return float(result)

    def __repr__(self):
        """Provides string representation of SymbolicFunction object."""
        return f"<SymbolicFunction {self.sympyStr}>"

    def __getstate__(self):
        d = copy(self.__dict__)
        d["eqn"] = None
        return d

    def __setstate__(self, s):
        self.__dict__ = s
        self.eqn = eval(self.sympyStr)
