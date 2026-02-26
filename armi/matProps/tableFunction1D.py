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

"""A simple implementation for a one dimensional table to replace analytic curves in the YAML data files."""

from armi.matProps.interpolationFunctions import linearLinear
from armi.matProps.tableFunction import TableFunction


class TableFunction1D(TableFunction):
    """
    A one dimensional table function, containing pairs of data.

    An example with the YAML format is::

        function:
          <var>: 0
          type: table
          tabulated data:
            - [0.0, 0.0]
            - [50, 1e99]
            - [100, 2e-99]
            - [150, 100]

    """

    def __init__(
        self,
        mat,
        prop,
    ):
        """
        Constructor for TableFunction1D object.

        Parameters
        ----------
        mat: Material
            Material object with which this TableFunction1D is associated
        prop: Property
            Property that is represented by this TableFunction1D
        """
        super().__init__(mat, prop)

        self._var1s = []
        """List of independent variable values for TableFunction1D object."""

        self._values = []
        """List of property values for TableFunction1D object."""

    def __repr__(self):
        """Provides string representation of TableFunction1D object."""
        return "<TableFunction1D>"

    def _setBounds(self, node: dict, var: str):
        """
        Validate and set the min and max bounds for a variable.

        Parameters
        ----------
        node: dict
            dictionary that contains min and max values.
        var: str
            name of the variable
        """
        self.independentVars[var] = (float(min(self._var1s)), float(max(self._var1s)))

    def _parseSpecific(self, prop):
        """
        Parses a temperature dependent table function.

        Parameters
        ----------
        prop: dict
            Node containing tabulated data that needs to be parsed.
        """
        tabulated_data = prop["tabulated data"]
        for val in tabulated_data:
            self._var1s.append(float(val[0]))
            self._values.append(float(val[1]))

    def _calcSpecific(self, point: dict) -> float:
        """
        Performs a linear interpolation on tabular data.

        Parameters
        ----------
        point: dict
            dictionary of independent variable/value pairs
        """
        var = list(self.independentVars.keys())[0]
        if var in point:
            return linearLinear(point[var], self._var1s, self._values)

        raise ValueError(f"Specified point does contain the correct independent variables: {self.independentVars}")
