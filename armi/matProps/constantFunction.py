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

"""A constant function to a single float value in a material YAML file."""

from armi.matProps.function import Function


class ConstantFunction(Function):
    """A constant function, representing a float value."""

    def __init__(self, mat, prop):
        """
        Constructor for ConstantFunction object.

        Parameters
        ----------
        mat: Material
            Material object with which this ConstantFunction is associated
        prop: Property
            Property that is represented by this ConstantFunction
        """
        super().__init__(mat, prop)
        # Constant value that is returned by ConstantFunction.
        self.value = None

    def __repr__(self):
        """Provides string representation of ConstantFunction object."""
        return f"<ConstantFunction {self.value}>"

    def _parseSpecific(self, node):
        """
        Parses a constant function.

        Parameters
        ----------
        node: dict
            Dictionary containing the node whose values will be parsed to fill object.
        """
        self.value = float(node["function"]["value"])

    def _calcSpecific(self, point: dict) -> float:
        """Returns a constant value."""
        return self.value
