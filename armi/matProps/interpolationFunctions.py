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

"""Some basic interpolation routines."""

import math


def find_index(val: float, x: list) -> int:
    """
    Find the location of the provided value in the provided collection.

    Parameters
    ----------
    val: float
        Value whose index is needed in x
    x: list
        List of numbers

    Returns
    -------
    int
        Integer containing index wherein x[i] <= Tc <= x[i+1]
    """
    if val < x[0]:
        raise ValueError(f"Value {val} out of bounds: {x}")

    for ii in range(len(x) - 1):
        Tc1 = x[ii]
        Tc2 = x[ii + 1]
        if val >= Tc1 and val <= Tc2:
            return ii

    raise ValueError(f"Value {val} out of bounds: {x}")


def linear_linear(Tc: float, x: list, y: list) -> float:
    """
    Find the approximate value on a XY table assuming a linear-linear curve.

    Parameters
    ----------
    Tc: float
        Independent variable at which an interpolation value is desired.
    x: list
        List of independent variable values
    y: list
        List of dependent variable values

    Returns
    -------
    float
        Float containing final interpolation value based on a linear-linear interpolation.
    """
    ii: int = find_index(Tc, x)
    Tc1: float = x[ii]
    Tc2: float = x[ii + 1]
    return (Tc - Tc1) / (Tc2 - Tc1) * (y[ii + 1] - y[ii]) + y[ii]


def log_linear(Tc: float, x: list, y: list) -> float:
    """
    Find the approximate value on a XY table assuming a log-linear curve.

    Parameters
    ----------
    Tc: float
        Independent variable at which an interpolation value is desired.
    x: list
        List of independent variable values
    y: list
        List of dependent variable values

    Returns
    -------
    float
        Float containing final interpolation value based on a log-linear interpolation.
    """
    ii: int = find_index(Tc, x)
    Tc1: float = math.log10(x[ii])
    Tc2: float = math.log10(x[ii + 1])
    return (math.log10(Tc) - Tc1) / (Tc2 - Tc1) * (y[ii + 1] - y[ii]) + y[ii]
