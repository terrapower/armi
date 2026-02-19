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

from armi.matProps.interpolationFunctions import findIndex, logLinear
from armi.matProps.tableFunction import TableFunction


class TableFunction2D(TableFunction):
    """
    A 2 dimensional table function. The input format, below, is permitted to have null values in it, which if used
    during the calculation/interpolation will throw a ValueError.

    The YAML format demonstrating the two dimensional tabulated data is::

        function:
          <var1>: 0
          <var2>: 1
          type: two dimensional table
        tabulated data:
          - [null,   [ 375., 400., 425., 450., 475., 500., 525., 550., 575., 600., 625., 650.]]
          - [1.,     [   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.]]
          - [10.,    [   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.]]
          - [300.,   [   1.,   1.,   1.,   1.,   1.,   1.,   1.,   1.,  .97,  .91,  .87,  .84]]
          - [30000., [   1.,   1.,   1.,   1.,  .93,  .88,  .83,  .80,  .75, null, null, null]]
          - [300000.,[   1.,   1.,   1.,  .89,  .83,  .79,  .74,  .70,  .66, null, null, null]]
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

        self._rowValues = []
        """List containing all of the time or cycle values for TableFunction2D object."""

        self._columnValues = []
        """List containing all of the temperature values for TableFunction2D object."""

        self._data = []
        """List containing all of the property values in TableFunction2D object."""

    def __repr__(self):
        """Provides string representation of TableFunction2D object."""
        return "<TableFunction2D>"

    def _setBounds(self, node: int, var: str):
        """
        Validate and set the min and max bounds for a variable.

        Parameters
        ----------
        node: int
            This number is zero for columns, and one for rows.
        var: str
            name of the variable

        Notes
        -----
        The method declaration here does not match the one in the super class Function. The type of the "node" arguement
        should be dict, but it is int. This is a surprising and acquard asymmetry.
        """
        if node == 0:
            cache = None
            if self.independentVars:
                # Need to re-arrange order.
                cache = copy.deepcopy(self.independentVars)
                self.independentVars = {}

            self.independentVars[var] = (
                float(min(self._columnValues)),
                float(max(self._columnValues)),
            )

            if cache:
                self.independentVars[list(cache.keys())[0]] = list(cache.values())[0]
        elif node == 1:
            self.independentVars[var] = (float(min(self._rowValues)), float(max(self._rowValues)))
        else:
            raise ValueError(f"The node value must be 0 or 1, but was: {node}")

    def _parseSpecific(self, prop):
        """
        Parses a 2D table function.

        Parameters
        ----------
        prop: dict
            Node containing tabulated data that needs to be parsed.
        """
        tabulatedData = prop["tabulated data"]

        skippedFirst = False
        for rowNode in tabulatedData:
            if not skippedFirst:
                for cValNode in rowNode[1]:
                    self._columnValues.append(float(cValNode))
                    self._data.append([])

                skippedFirst = True
                continue

            currentRowVal = float(rowNode[0])

            self._rowValues.append(currentRowVal)
            var1DependentData = rowNode[1]
            for cIndex in range(len(self._columnValues)):
                value = var1DependentData[cIndex]
                if value == "null" or value is None:
                    self._data[cIndex].append(None)
                else:
                    self._data[cIndex].append(float(value))

    def _calcSpecific(self, point: dict) -> float:
        """
        Performs 2D interpolation on tabular data.

        Parameters
        ----------
        point: dict
            dictionary of independent variable/value pairs
        """
        columnVar = list(self.independentVars.keys())[0]
        rowVar = list(self.independentVars.keys())[1]
        if columnVar in point and rowVar in point:
            columnVal = point[columnVar]
            rowVal = point[rowVar]
        else:
            raise ValueError(f"Specified point does contain the correct independent variables: {self.independentVars}")

        cIndex = findIndex(columnVal, self._columnValues)
        rVal0 = logLinear(rowVal, self._rowValues, self._data[cIndex])
        rVal1 = logLinear(rowVal, self._rowValues, self._data[cIndex + 1])
        cVal0 = self._columnValues[cIndex]
        cVal1 = self._columnValues[cIndex + 1]
        return (columnVal - cVal0) / (cVal1 - cVal0) * (rVal1 - rVal0) + rVal0
