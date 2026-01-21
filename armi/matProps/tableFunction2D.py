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

"""A simple implementation for a 2D table to replace analytic curves in the YAML data files."""

import copy
import math

from armi.matProps.interpolationFunctions import find_index, log_linear
from armi.matProps.point import Point
from armi.matProps.tableFunction import TableFunction


class TableFunction2D(TableFunction):
    """
    A 2 dimensional table function. The 2D table function is generally used for ASME properties. The input format,
    below, is permitted to have null values in it, which if used during the calculation/interpolation will throw a
    ValueError.

    The YAML format demonstrating the two dimensional tabulated data is::

        function:
          <var1>: 0
          <var2>: 1
          type: two dimensional table
        tabulated data:
          - [null,   [ 375., 400., 425., 450., 475., 500., 525., 550., 575., 600., 625., 650.]]
          - [1.,     [   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.]]
          - [10.,    [   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.]]
          - [300.,   [   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,  .98,  .93,  .88,  .84]]
          - [30000., [   1.,   1.,   1.,   1.,  .94,  .88,  .84,  .80,  .75, null, null, null]]
          - [300000.,[   1.,   1.,   1.,  .89,  .84,  .79,  .74,  .70,  .65, null, null, null]]
    """

    def __init__(self, mat, prop):
        """
        Constructor for TableFunction2D object.

        Parameters
        ----------
        mat: Material
            Material object with which this TableFunction2D is associated
        prop: Property
            Property that is represented by this TableFunction2D
        """
        super().__init__(mat, prop)

        self._row_values = []
        """List containing all of the time or cycle values for TableFunction2D object."""

        self._column_values = []
        """List containing all of the temperature values for TableFunction2D object."""

        self._data = []
        """List containing all of the property values in TableFunction2D object."""

    def __repr__(self):
        """Provides string representation of TableFunction2D object."""
        return "<TableFunction2D>"

    def _set_bounds(self, node: dict, var: str):
        """
        Validate and set the min and max bounds for a variable.

        Parameters
        ----------
        node: dict
            dictionary that contains min and max values.
        var: str
            name of the variable
        """
        if node == 0:
            cache = None
            if self.independent_vars:
                # Need to re-arrange order.
                cache = copy.deepcopy(self.independent_vars)

            self.independent_vars[var] = (
                float(min(self._column_values)),
                float(max(self._column_values)),
            )

            if cache:
                self.independent_vars[list(cache.keys())[0]] = list(cache.values())[0]
        elif node == 1:
            self.independent_vars[var] = (float(min(self._row_values)), float(max(self._row_values)))

    def _parse_specific(self, prop):
        """
        Parses a 2D table function.

        Parameters
        ----------
        prop: dict
            Node containing tabulated data that needs to be parsed.
        """
        tabulated_data = prop["tabulated data"]

        skipped_first = False
        for row_node in tabulated_data:
            if not skipped_first:
                for c_val_node in row_node[1]:
                    self._column_values.append(float(c_val_node))
                    self._data.append([])

                skipped_first = True
                continue

            current_row_val = float(row_node[0])

            self._row_values.append(current_row_val)
            var1_dependent_data = row_node[1]
            for c_index in range(len(self._column_values)):
                value = var1_dependent_data[c_index]
                if value == "null" or value is None:
                    self._data[c_index].append(None)
                else:
                    self._data[c_index].append(float(value))

    def points(self):
        """
        Get a list of `Point` values represented by this TableFunction2D. This list of Point quantities will have the
        non-NaN `Point` time values.
        """
        points = []
        for c_index in range(len(self._column_values)):
            for r_index in range(len(self._row_values)):
                value = self._data[c_index][r_index]
                if value == "null" or value is None or math.isnan(float(value)):
                    continue

                points.append(
                    Point(
                        self._column_values[c_index],
                        self._row_values[r_index],
                        value,
                    )
                )

        return points

    def _calc_specific(self, point: dict) -> float:
        """
        Performs 2D interpolation on tabular data.

        Parameters
        ----------
        point: dict
            dictionary of independent variable/value pairs
        """
        column_var = list(self.independent_vars.keys())[0]
        row_var = list(self.independent_vars.keys())[1]
        if column_var in point and row_var in point:
            column_val = point[column_var]
            row_val = point[row_var]
        else:
            raise ValueError(f"Specified point does contain the correct independent variables: {self.independent_vars}")

        c_index = find_index(column_val, self._column_values)
        r_val0 = log_linear(row_val, self._row_values, self._data[c_index])
        r_val1 = log_linear(row_val, self._row_values, self._data[c_index + 1])
        c_val0 = self._column_values[c_index]
        c_val1 = self._column_values[c_index + 1]
        return (column_val - c_val0) / (c_val1 - c_val0) * (r_val1 - r_val0) + r_val0

    def lookup(self, column_val: float, row_val: float):
        """Given the two independent values, return the dependent value by interpolating the table data."""
        c_index = find_index(column_val, self._column_values)
        r_index0 = find_index(row_val, self._data[c_index])
        r_index1 = find_index(row_val, self._data[c_index + 1])
        interp_vals = [self._data[c_index][r_index0], self._data[c_index + 1][r_index1]]
        return log_linear(row_val, interp_vals, self._row_values)
