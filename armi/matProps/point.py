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

"""A single data point in a YAML file."""


class Point:
    """A single data point in a YAML file."""

    def __init__(self, var1, var2, val):
        """
        Constructor for Point class.

        Parameters
        ----------
        var1: float
            Independent variable 1
        var2: float
            If provided, independent variable 2
        val: float
            Dependent variable value for property
        """
        self.variable1 = var1
        """Value of first independent variable."""

        self.variable2 = var2
        """Value of second independent variable."""

        self.value = val
        """Value of Property dependent value"""

    def __repr__(self):
        """Provides string representation of Point object."""
        return f"<Point {self.variable1}, {self.variable2} -> {self.value}>"
