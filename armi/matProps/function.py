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

"""Generic class for a function to be defined in a YAML."""


class Function:
    """
    An abstract function class for computing quantities of a Property. The Function class makes up a majority of the
    actual code, as well as functionality of armi.matProps. The various Function types are read through YAML, and
    interpreted at run time. The sub-classes of Function have specific requirements on the YAML format.
    """

    # This is the list of all nodes that are associated with functions in the YAML input file. Any node named something
    # not in this list is assumed to be an independent variable for the function. This list needs to remain updated if
    # any child class adds a new YAML node.
    FUNCTION_NODES = {
        "type",  # All equations have this to define the child class type
        "tabulated data",  # Optional for all equations, required for table functions
        "equation",  # Used by SymbolicFunction for the equation definition
        "functions",  # Used by PiecewiseFunction to define the child functions
        "reference temperature",  # Optional for all equations
    }

    def __init__(self, mat, prop):
        """
        Constructor for base Function class.

        Parameters
        ----------
        mat: Material
            Material object with which this Function is associated
        prop: Property
            Property that is represented by this Function
        """
        self.material = mat
        """A pointer back to the parent Material for this Function."""

        self.property = prop
        """The Property this Function represents."""

        self.independent_vars: dict = {}  # Keys are the independent variables, values are a tuple of the min/max bounds

        self.table_data = None
        """A TableFunction containing verification data for this specific function.
        Note that for actual TableFunction instances, the table_data property is NULL."""

        self._reference_temperature: float = -274.0
        """Reference temperature. Initialized be less than absolute zero in degrees Celsius"""

        self._references = []
        """Reference data"""

    def clear(self):
        if self.table_data != self:
            del self.table_data
        else:
            self.table_data = None

    @staticmethod
    def is_table():
        """Returns True if a subclass of TableFunction, otherwise False."""
        return False

    def get_reference_temperature(self):
        """
        Returns the reference temperature if it is defined.

        Returns
        -------
        float
            Reference temperature
        """
        # If this statement below is true, either the reference temperature was not provided in the material YAML file
        # or was a non-physical value.
        if self._reference_temperature < -273.15:
            raise ValueError("Reference temperature is undefined or set to less than absolute zero.")

        return self._reference_temperature

    def get_independent_variables(self):
        """
        Returns the independent variables that are required for this function.

        Returns
        -------
        list
            list of independent variable strings
        """
        return list(self.independent_vars.keys())

    def get_min_bound(self, var) -> float:
        """
        Returns the minimum bound for the requested variable.

        Returns
        -------
        float
            Minimum valid value
        """
        return self.independent_vars[var][0]

    def get_max_bound(self, var) -> float:
        """
        Returns the minimum bound for the requested variable.

        Returns
        -------
        float
            Maximum valid value
        """
        return self.independent_vars[var][1]

    def get_references(self):
        """The reference accessor."""
        return self._references

    def calc(self, point: dict):
        """
        Calculate the quantity of a specific Property.

        Parameters
        ----------
        point: dict
            dictionary of independent variable/value pairs

        Returns
        -------
        float
            property evaluation
        """
        if not self.independent_vars.keys() <= point.keys():
            raise KeyError(
                f"Specified point {point} does contain the correct independent variables: {self.independent_vars}"
            )
        if not self.in_range(point):
            raise ValueError(f"Requested calculation point, {point} is not in the valid range of the function")

        return self._calc_specific(point)

    def in_range(self, point: dict) -> bool:
        """
        Determine if a point is within range of the function.

        Parameters
        ----------
        point: dict
            dictionary of independent variable/value pairs

        Returns
        -------
        bool
            True if the point is in the valid range, False otherwise.
        """
        for var, bounds in self.independent_vars.items():
            if point[var] < bounds[0] or point[var] > bounds[1]:
                return False
        return True

    def points(self):
        """Returns a list of points within the TableFunction of this Function."""
        if self.table_data:
            return self.table_data.points()
        else:
            msg = f"Requested points from {self.property} on {self.material}, which is not "
            msg += "tabulated data and therefore has no points."
            raise KeyError(msg)

    def __repr__(self):
        """Provides string representation of Function object."""
        return f"<{self.__class__.__name__}>"

    @staticmethod
    def _factory(mat, node, prop):
        """
        Parsing a property node and using that information to construct a Function object. This method is responsible
        for searching for the assigning the Function object to the appropriate child class instance.

        Parameters
        ----------
        mat: Material
            Material object which is associated with the returned Function object
        node: dict
            YAML object representing root level node of material yaml file being parsed
        prop: Property
            Property object that is being populated on the Material

        Returns
        -------
        Function
            Function pointer parsed from the specified property.
        """
        from armi.matProps.piecewiseFunction import PiecewiseFunction
        from armi.matProps.symbolicFunction import SymbolicFunction
        from armi.matProps.tableFunction1D import TableFunction1D
        from armi.matProps.tableFunction2D import TableFunction2D

        func_node = node["function"]
        func_type = str(func_node["type"])
        func = None
        # TODO: Move this switch to a dict visible at a higher scope
        # TODO: at the very least, these strings should be constants
        if func_type == "symbolic":
            func = SymbolicFunction(mat, prop)
        elif func_type == "table":
            func = TableFunction1D(mat, prop)
        elif func_type == "two dimensional table":
            func = TableFunction2D(mat, prop)
        elif func_type == "piecewise":
            func = PiecewiseFunction(mat, prop)
        else:
            raise KeyError(f"Unknown function type `{func_type}`")

        func._parse(node)  # noqa: SLF001
        return func

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
        if "min" not in node or "max" not in node:
            raise KeyError(
                f"The independent variable node, {var}, is not formatted correctly: {node}. If this node is not "
                "intended to be an independent variable, please ensure that the Function.FUNCTION_NODES set is updated "
                "properly."
            )
        minVal = float(node["min"])
        maxVal = float(node["max"])
        if maxVal < minVal:
            raise ValueError(f"Maximum bound {maxVal} cannot be less than the minimum bound {minVal}")
        self.independent_vars[var] = (minVal, maxVal)

    def _parse(self, node):
        """
        Method used to parse property node and fill in appropriate Function data members.

        Parameters
        ----------
        node
            YAML containing object to be parsed
        """
        from armi.matProps.reference import Reference
        from armi.matProps.tableFunction1D import TableFunction1D
        from armi.matProps.tableFunction2D import TableFunction2D

        func_node = node["function"]

        ref_temp_node = func_node.get("reference temperature", None)
        if ref_temp_node is not None:
            self._reference_temperature = float(ref_temp_node)

        func_type = str(func_node["type"])
        references = node.get("references", [])
        for ref in references:
            self._references.append(Reference._factory(ref))  # noqa: SLF001

        tabulated_node = node.get("tabulated data", None)
        if tabulated_node:
            if func_type == "two dimensional table":
                self.table_data = TableFunction2D(self.material, self.property)
            else:
                self.table_data = TableFunction1D(self.material, self.property)

            if self.is_table():
                self._parse_specific(node)
                self.table_data = self
            else:
                self.table_data._parse_specific(node)
        elif self.is_table():
            raise KeyError("Missing node `tabulated data`")

        for var in func_node:
            if var not in self.FUNCTION_NODES:
                self._set_bounds(func_node[var], var)

        if not self.is_table():
            self._parse_specific(node)

    def _parse_specific(self, node):
        """
        Abstract method that is used to parse information specific to Function child classes.

        Parameters
        ----------
        node
            YAML containing object information to parse and fill in Function
        """
        raise NotImplementedError()

    def _calc_specific(self, point: dict) -> float:
        """
        Private method that contains the analytic expression used to return a property value.

        Parameters
        ----------
        point : dict
            dictionary of independent variable/value pairs

        Returns
        -------
        float
            property evaluation at specified independent variable point
        """
        raise NotImplementedError()
