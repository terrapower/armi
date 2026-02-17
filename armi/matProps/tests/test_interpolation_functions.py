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

"""Program that runs all of the tests contained in the TestInterpolationFunctions class."""

import unittest

import numpy as np
from scipy import interpolate

from matProps.interpolationFunctions import linearLinear, logLinear


class TestInterpolationFunctions(unittest.TestCase):
    """Class which creates tests for the matProps InterpolationFunctions files."""

    def test_linearLinear(self):
        """
        Test which validates the values returned from the linear-linear interpolation method.

        Uses numpy linspace function to generate values at which interpolation will be performed.
        """
        x = np.arange(10)
        y = [1.0 + xx + xx**2 for xx in range(10)]
        f = interpolate.interp1d(x, y, bounds_error=False)
        for nn in np.linspace(0, 9, 20):
            self.assertTrue(np.allclose(f(nn), linearLinear(nn, x.tolist(), y)))

    def test_linearLinearInterpolation(self):
        """
        Duplicate test validating that the correct values are returned from a linear-linear interpolation.

        Differs from test_linearLinear by constructing interpolation points using standard lists instead of numpy
        linspace.
        """
        x = [0.0, 1.0]
        y = [1.0, 2.0]
        for xx, yy in [(0.0, 1.0), (0.5, 1.5), (1.0, 2.0)]:
            self.assertAlmostEqual(yy, linearLinear(xx, x, y))

    def test_linearLinearExtrapolation(self):
        """Check to make sure a ValueError is thrown if attempting an interpolation outside the function domain."""
        x = [0.0, 1.0]
        y = [1.0, 2.0]
        with self.assertRaisesRegex(ValueError, "out of bounds"):
            linearLinear(-2.0, x, y)

    def test_logLinear(self):
        """Test that validates the values returned from the log-linear interpolation function."""
        x = np.arange(1.0, 11.0)
        y = -42.0 + x + x**-2
        n_vals = np.interp(np.log10(np.linspace(1, 10, 20)), np.log10(x), y)
        m_vals = [logLinear(nn, x, y) for nn in np.linspace(1, 10, 20)]
        self.assertTrue(
            np.allclose(n_vals, m_vals),
            f"np:  {n_vals}\nmatProps:{np.array(m_vals)}",
        )

    def test_logLinearExtrapolation(self):
        """A ValueError should be thrown if performing a log-linear interpolation outside the function domain."""
        x = np.arange(1.0, 11.0)
        y = -42.0 + x + x**-2
        with self.assertRaisesRegex(ValueError, "out of bounds"):
            logLinear(0.5, x, y)
