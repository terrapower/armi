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
A piecewise-defined function for used in material YAML files.

Each piece can be of any other type that matProps supports.
"""

import math

from matProps.function import Function


class PiecewiseFunction(Function):
    """
    A piecewise function is composed of many other subfunctions, any of which can be any subclass of the Function type,
    including PiecewiseFunction.

    The PiecewiseFunction uses the `Function.inRange` method to determine which sub-function should be used for
    computing the quantity. An example with the YAML format is::

        function:
            <var1>:
                min: <min1>
                max: <max1>
            <var2>:
                min: <min2>
                max: <max2>
            type: piecewise
            functions:
            - function:
                <var1>:
                    min: <local min1>
                    max: <local max1>
                <var2>:
                    min: <local min2>
                    max: <local max2>
                type: ...
                tabulated data: *alias # it is suggested that the same table is used for the entire range
            - function:
                <var1>:
                    min: <local min1>
                    max: <local max1>
                <var2>:
                    min: <local min2>
                    max: <local max2>
                type: ...
                tabulated data: *alias # it is suggested that the same table is used for the entire range
    """

    def __init__(self, mat, prop):
        """
        Constructor for PiecewiseFunction object.

        Parameters
        ----------
        mat: Material
            Material object with which this PiecewiseFunction is associated
        prop: Property
            Property that is represented by this PiecewiseFunction
        """
        super().__init__(mat, prop)

        self.functions = []
        """List of Function objects used to compose PiecewiseFunction object."""

    def __repr__(self):
        """Provides string representation of PiecewiseFunction object."""
        msg = "<PiecewiseFunction "
        for subFunc in self.functions:
            msg += str(subFunc)

        msg += ">"
        return msg

    def clear(self) -> None:
        for fun in self.functions:
            del fun
        self.functions.clear()

    def _parseSpecific(self, node):
        """
        Parses nodes that are specific to PiecewiseFunction objects.

        Parameters
        ----------
        node : dict
            Dictionary containing the node whose values will be parsed to fill object.
        """

        def checkOverlap(func1, func2):
            """Checks if the valid range for two functions overlaps on all dimensions."""
            for var in self.independentVars:
                min1, max1 = func1.independentVars[var]
                min2, max2 = func2.independentVars[var]

                if math.isclose(max1, min2) or math.isclose(min1, max2):
                    # This handles floating point comparison. Adjoining regions is allowed.
                    return False
                if max1 < min2 or min1 > max2:
                    # overlap on this dimension, so no overlap overall
                    return False

            # Overlap on all dimensions
            return True

        for subFunctionDef in node["function"]["functions"]:
            func = self._factory(self.material, subFunctionDef, self.property)
            self.functions.append(func)

        # Ensure bounds have same variables in parent and child functions.
        for subFunc in self.functions:
            for var in self.independentVars:
                if var not in subFunc.independentVars:
                    raise KeyError(
                        "Piecewise child function must have same variables for valid range as main function."
                    )

        # Check for overlapping regions
        for i, func1 in enumerate(self.functions):
            for func2 in self.functions[i + 1 :]:
                if checkOverlap(func1, func2):
                    raise ValueError(f"Piecewise child functions overlap: {func1}, {func2}")

    def _calcSpecific(self, point: dict) -> float:
        """
        Private method that contains the analytic expression used to return a property value.

        Parameters
        ----------
        point: dict
            dictionary of independent variable/value pairs

        Returns
        -------
        float
            property evaluation at specified independent variable point
        """
        for subFunc in self.functions:
            if subFunc.inRange(point):
                return subFunc.calc(point)

        raise ValueError("PiecewiseFunction error, could not evaluate")
