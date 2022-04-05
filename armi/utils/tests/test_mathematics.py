# Copyright 2022 TerraPower, LLC
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
r""" Testing mathematics utilities
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access,no-member,disallowed-name,invalid-name
from math import sqrt
import unittest

import numpy as np

from armi.utils.mathematics import (
    average1DWithinTolerance,
    convertToSlice,
    efmt,
    expandRepeatedFloats,
    findClosest,
    findNearestValue,
    fixThreeDigitExp,
    getFloat,
    getStepsFromValues,
    linearInterpolation,
    minimizeScalarFunc,
    newtonsMethod,
    parabolaFromPoints,
    parabolicInterpolation,
    relErr,
    resampleStepwise,
    rotateXY,
)


class TestMath(unittest.TestCase):
    """Tests for various math utilities"""

    def test_average1DWithinTolerance(self):
        vals = np.array([np.array([1, 2, 3]), np.array([4, 5, 6]), np.array([7, 8, 9])])
        result = average1DWithinTolerance(vals, 0.1)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], 4.0)
        self.assertEqual(result[1], 5.0)
        self.assertEqual(result[2], 6.0)

    def test_average1DWithinToleranceInvalid(self):
        vals = np.array(
            [np.array([1, -2, 3]), np.array([4, -5, 6]), np.array([7, -8, 9])]
        )
        with self.assertRaises(ValueError):
            average1DWithinTolerance(vals, 0.1)

    def test_convertToSlice(self):
        slice1 = convertToSlice(2)
        self.assertEqual(slice1, slice(2, 3, None))
        slice1 = convertToSlice(2.0, increment=-1)
        self.assertEqual(slice1, slice(1, 2, None))
        slice1 = convertToSlice(None)
        self.assertEqual(slice1, slice(None, None, None))
        slice1 = convertToSlice([1, 2, 3])
        self.assertTrue(np.allclose(slice1, np.array([1, 2, 3])))
        slice1 = convertToSlice(slice(2, 3, None))
        self.assertEqual(slice1, slice(2, 3, None))
        slice1 = convertToSlice(np.array([1, 2, 3]))
        self.assertTrue(np.allclose(slice1, np.array([1, 2, 3])))
        with self.assertRaises(Exception):
            slice1 = convertToSlice("slice")

    def test_efmt(self):
        self.assertAlmostEqual(efmt("1.0e+001"), "1.0E+01")
        self.assertAlmostEqual(efmt("1.0E+01"), "1.0E+01")

    def test_expandRepeatedFloats(self):
        repeatedFloats = ["150", "2R", 200.0, 175, "4r", 180.0, "0R"]
        expectedFloats = [150] * 3 + [200] + [175] * 5 + [180]
        self.assertEqual(expandRepeatedFloats(repeatedFloats), expectedFloats)

    def test_findClosest(self):
        l1 = range(10)
        self.assertEqual(findClosest(l1, 5.6), 6)
        self.assertEqual(findClosest(l1, 10.1), 9)
        self.assertEqual(findClosest(l1, -200), 0)

        # with index
        self.assertEqual(findClosest(l1, 5.6, indx=True), (6, 6))

    def test_findNearestValue(self):
        searchList = [0.1, 0.2, 0.25, 0.35, 0.4]
        searchValue = 0.225
        self.assertEqual(findNearestValue(searchList, searchValue), 0.2)
        searchValue = 0.226
        self.assertEqual(findNearestValue(searchList, searchValue), 0.25)
        searchValue = 0.0
        self.assertEqual(findNearestValue(searchList, searchValue), 0.1)
        searchValue = 10
        self.assertEqual(findNearestValue(searchList, searchValue), 0.4)

    def test_fixThreeDigitExp(self):
        fixed = fixThreeDigitExp("-9.03231714805651E+101")
        self.assertEqual(-9.03231714805651e101, fixed)
        fixed = fixThreeDigitExp("9.03231714805651-101")
        self.assertEqual(9.03231714805651e-101, fixed)
        fixed = fixThreeDigitExp("-2.4594981981654+101")
        self.assertEqual(-2.4594981981654e101, fixed)
        fixed = fixThreeDigitExp("-2.4594981981654-101")
        self.assertEqual(-2.4594981981654e-101, fixed)

    def test_getFloat(self):
        self.assertEqual(getFloat(1.0), 1.0)
        self.assertEqual(getFloat("1.0"), 1.0)
        self.assertIsNone(getFloat("word"))

    def test_getStepsFromValues(self):
        steps = getStepsFromValues([1.0, 3.0, 6.0, 10.0], prevValue=0.0)
        self.assertListEqual(steps, [1.0, 2.0, 3.0, 4.0])

    def test_linearInterpolation(self):
        y = linearInterpolation(1.0, 2.0, 3.0, 4.0, targetX=20.0)
        x = linearInterpolation(1.0, 2.0, 3.0, 4.0, targetY=y)

        x2 = linearInterpolation(1.0, 1.0, 2.0, 2.0, targetY=50)

        self.assertEqual(x, 20.0)
        self.assertEqual(x2, 50.0)

        with self.assertRaises(ZeroDivisionError):
            _ = linearInterpolation(1.0, 1.0, 1.0, 2.0)

    def test_minimizeScalarFunc(self):
        f = lambda x: (x + 1) ** 2
        minimum = minimizeScalarFunc(f, -3.0, 10.0, maxIterations=10)
        self.assertAlmostEqual(minimum, -1.0, places=3)
        minimum = minimizeScalarFunc(
            f, -3.0, 10.0, maxIterations=10, positiveGuesses=True
        )
        self.assertAlmostEqual(minimum, 0.0, places=3)

    def test_newtonsMethod(self):
        f = lambda x: (x + 2) * (x - 1)
        root = newtonsMethod(f, 0.0, 5.0, maxIterations=10, positiveGuesses=True)
        self.assertAlmostEqual(root, 1.0, places=3)
        root = newtonsMethod(f, 0.0, -10.0, maxIterations=10)
        self.assertAlmostEqual(root, -2.0, places=3)

    def test_parabola(self):
        # test the parabola function
        a, b, c = parabolaFromPoints((0, 1), (1, 2), (-1, 2))
        self.assertEqual(a, 1.0)
        self.assertEqual(b, 0.0)
        self.assertEqual(c, 1.0)

        with self.assertRaises(Exception):
            a, b, c = parabolaFromPoints((0, 1), (0, 1), (-1, 2))

    def test_parabolicInterpolation(self):
        realRoots = parabolicInterpolation(2.0e-6, -5.0e-4, 1.02, 1.0)
        self.assertAlmostEqual(realRoots[0][0], 200.0)
        self.assertAlmostEqual(realRoots[0][1], 3.0e-4)
        self.assertAlmostEqual(realRoots[1][0], 50.0)
        self.assertAlmostEqual(realRoots[1][1], -3.0e-4)
        noRoots = parabolicInterpolation(2.0e-6, -4.0e-4, 1.03, 1.0)
        self.assertAlmostEqual(noRoots[0][0], -100.0)
        self.assertAlmostEqual(noRoots[0][1], 0.0)
        # 3. run time error
        with self.assertRaises(RuntimeError):
            _ = parabolicInterpolation(2.0e-6, 4.0e-4, 1.02, 1.0)

    def test_relErr(self):
        self.assertAlmostEqual(relErr(1.00, 1.01), 0.01)
        self.assertAlmostEqual(relErr(100.0, 97.0), -0.03)
        self.assertAlmostEqual(relErr(0.00, 1.00), -1e99)

    def test_resampleStepwiseAvg0(self):
        """Test resampleStepwise() averaging when in and out bins match"""
        xin = [0, 1, 2, 13.3]
        yin = [4.76, 9.99, -123.456]
        xout = [0, 1, 2, 13.3]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertAlmostEqual(yout[0], 4.76)
        self.assertAlmostEqual(yout[1], 9.99)
        self.assertAlmostEqual(yout[2], -123.456)

    def test_resampleStepwiseAvg1(self):
        """Test resampleStepwise() averaging for one arbitrary case"""
        xin = [0, 1, 2, 3, 4]
        yin = [3, 2, 5, 3]
        xout = [0, 2, 3.5, 4]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 2.5)
        self.assertAlmostEqual(yout[1], 4.333333333333333)
        self.assertEqual(yout[2], 3)

    def test_resampleStepwiseAvg2(self):
        """Test resampleStepwise() averaging for another arbitrary case"""
        xin = [0, 1, 2, 3, 4, 5]
        yin = [3, 2, 5, 3, 4]
        xout = [0, 2, 3.5, 5]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 2.5)
        self.assertAlmostEqual(yout[1], 4.333333333333333)
        self.assertAlmostEqual(yout[2], 3.6666666666666665)

    def test_resampleStepwiseAvg3(self):
        """Test resampleStepwise() averaging for another arbitrary case"""
        xin = [0, 1, 2, 3, 4, 6]
        yin = [3, 2, 5, 3, 4]
        xout = [0, 2, 3.5, 6]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 2.5)
        self.assertAlmostEqual(yout[1], 4.333333333333333)
        self.assertEqual(yout[2], 3.8)

    def test_resampleStepwiseAvg4(self):
        """Test resampleStepwise() averaging for matching, but uneven intervals"""
        xin = [0, 3, 5, 6.777, 9.123]
        yin = [3.1, 2.2, 5.3, 3.4]
        xout = [0, 3, 5, 6.777, 9.123]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 3.1)
        self.assertEqual(yout[1], 2.2)
        self.assertEqual(yout[2], 5.3)
        self.assertEqual(yout[3], 3.4)

    def test_resampleStepwiseAvg5(self):
        """Test resampleStepwise() averaging for almost matching intervals"""
        xin = [0, 3, 5, 6.777, 9.123]
        yin = [3.1, 2.2, 5.3, 3.4]
        xout = [0, 5, 9.123]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 2.74)
        self.assertAlmostEqual(yout[1], 4.21889400921659)

    def test_resampleStepwiseAvg6(self):
        """Test resampleStepwise() averaging when the intervals don't line up"""
        xin = [0, 1, 2, 3, 4]
        yin = [11, 22, 33, 44]
        xout = [2, 3, 4, 5, 6]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 33)
        self.assertEqual(yout[1], 44)
        self.assertEqual(yout[2], 0)
        self.assertEqual(yout[3], 0)

    def test_resampleStepwiseAvg7(self):
        """Test resampleStepwise() averaging when the intervals don't line up"""
        xin = [2, 4, 6, 8, 10]
        yin = [11, 22, 33, 44]
        xout = [-1, 0, 1, 2, 3, 4]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 0)
        self.assertEqual(yout[1], 0)
        self.assertEqual(yout[2], 0)
        self.assertEqual(yout[3], 11)
        self.assertEqual(yout[4], 11)

    def test_resampleStepwiseSum0(self):
        """Test resampleStepwise() summing when in and out bins match"""
        xin = [0, 1, 2, 13.3]
        yin = [4.76, 9.99, -123.456]
        xout = [0, 1, 2, 13.3]

        yout = resampleStepwise(xin, yin, xout, avg=False)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertAlmostEqual(yout[0], 4.76)
        self.assertAlmostEqual(yout[1], 9.99)
        self.assertAlmostEqual(yout[2], -123.456)
        self.assertAlmostEqual(sum(yin), sum(yout))

    def test_resampleStepwiseSum1(self):
        """Test resampleStepwise() summing for one arbitrary case"""
        xin = [0, 1, 2, 3, 4]
        yin = [3, 2, 5, 3]
        xout = [0, 2, 3.5, 4]

        yout = resampleStepwise(xin, yin, xout, avg=False)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 5)
        self.assertEqual(yout[1], 6.5)
        self.assertEqual(yout[2], 1.5)
        self.assertEqual(sum(yin), sum(yout))

    def test_resampleStepwiseSum2(self):
        """Test resampleStepwise() summing for another arbitrary case"""
        xin = [0, 1, 2, 3, 4, 5]
        yin = [3, 2, 5, 3, 4]
        xout = [0, 2, 3.5, 5]

        yout = resampleStepwise(xin, yin, xout, avg=False)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 5)
        self.assertEqual(yout[1], 6.5)
        self.assertEqual(yout[2], 5.5)
        self.assertEqual(sum(yin), sum(yout))

    def test_resampleStepwiseSum3(self):
        """Test resampleStepwise() summing for another arbitrary case"""
        xin = [0, 1, 2, 3, 4, 6]
        yin = [3, 2, 5, 3, 4]
        xout = [0, 2, 3.5, 6]

        yout = resampleStepwise(xin, yin, xout, avg=False)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 5)
        self.assertEqual(yout[1], 6.5)
        self.assertEqual(yout[2], 5.5)
        self.assertEqual(sum(yin), sum(yout))

    def test_resampleStepwiseSum4(self):
        """Test resampleStepwise() summing for matching, but uneven intervals"""
        xin = [0, 3, 5, 6.777, 9.123]
        yin = [3.1, 2.2, 5.3, 3.4]
        xout = [0, 3, 5, 6.777, 9.123]

        yout = resampleStepwise(xin, yin, xout, avg=False)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 3.1)
        self.assertEqual(yout[1], 2.2)
        self.assertEqual(yout[2], 5.3)
        self.assertEqual(yout[3], 3.4)
        self.assertEqual(sum(yin), sum(yout))

    def test_resampleStepwiseSum5(self):
        """Test resampleStepwise() summing for almost matching intervals"""
        xin = [0, 3, 5, 6.777, 9.123]
        yin = [3.1, 2.2, 5.3, 3.4]
        xout = [0, 5, 9.123]

        yout = resampleStepwise(xin, yin, xout, avg=False)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertAlmostEqual(yout[0], 5.3)
        self.assertAlmostEqual(yout[1], 8.7)
        self.assertAlmostEqual(sum(yin), sum(yout))

    def test_resampleStepwiseSum6(self):
        """Test resampleStepwise() summing when the intervals don't line up"""
        xin = [0, 1, 2, 3, 4]
        yin = [11, 22, 33, 44]
        xout = [2, 3, 4, 5, 6]

        yout = resampleStepwise(xin, yin, xout, avg=False)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 33)
        self.assertEqual(yout[1], 44)
        self.assertEqual(yout[2], 0)
        self.assertEqual(yout[3], 0)

    def test_resampleStepwiseSum7(self):
        """Test resampleStepwise() summing when the intervals don't line up"""
        xin = [2, 4, 6, 8, 10]
        yin = [11, 22, 33, 44]
        xout = [-1, 0, 1, 2, 3, 4]

        yout = resampleStepwise(xin, yin, xout, avg=False)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 0)
        self.assertEqual(yout[1], 0)
        self.assertEqual(yout[2], 0)
        self.assertAlmostEqual(yout[3], 11 / 2)
        self.assertAlmostEqual(yout[4], 11 / 2)

    def test_resampleStepwiseAvgAllNones(self):
        """Test resampleStepwise() averaging when the inputs are all None"""
        xin = [0, 1, 2, 13.3]
        yin = [None, None, None]
        xout = [0, 1, 2, 13.3]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertIsNone(yout[0])
        self.assertIsNone(yout[1])
        self.assertIsNone(yout[2])

    def test_resampleStepwiseAvgOneNone(self):
        """Test resampleStepwise() averaging when one input is None"""
        xin = [0, 1, 2, 13.3]
        yin = [None, 1, 2]
        xout = [0, 1, 2, 13.3]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertIsNone(yout[0])
        self.assertEqual(yout[1], 1)
        self.assertEqual(yout[2], 2)

    def test_resampleStepwiseSumAllNones(self):
        """Test resampleStepwise() summing when the inputs are all None"""
        xin = [0, 1, 2, 13.3]
        yin = [None, None, None]
        xout = [0, 1, 2, 13.3]

        yout = resampleStepwise(xin, yin, xout, avg=False)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertIsNone(yout[0])
        self.assertIsNone(yout[1])
        self.assertIsNone(yout[2])

    def test_resampleStepwiseSumOneNone(self):
        """Test resampleStepwise() summing when one inputs is None"""
        xin = [0, 1, 2, 13.3]
        yin = [None, 1, 2]
        xout = [0, 1, 2, 13.3]

        yout = resampleStepwise(xin, yin, xout, avg=False)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertIsNone(yout[0])
        self.assertEqual(yout[1], 1)
        self.assertEqual(yout[2], 2)

    def test_resampleStepwiseAvgComplicatedNone(self):
        """Test resampleStepwise() averaging with a None value, when the intervals don't line up"""
        xin = [2, 4, 6, 8, 10]
        yin = [11, None, 33, 44]
        xout = [-1, 0, 1, 2, 4, 7, 9]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 0)
        self.assertEqual(yout[1], 0)
        self.assertEqual(yout[2], 0)
        self.assertEqual(yout[3], 11)
        self.assertIsNone(yout[4])
        self.assertEqual(yout[5], 38.5)

    def test_resampleStepwiseAvgNpArray(self):
        """Test resampleStepwise() averaging when some of the values are arrays"""
        xin = [0, 1, 2, 3, 4]
        yin = [11, np.array([1, 1]), np.array([2, 2]), 44]
        xout = [2, 4, 5, 6, 7]

        yout = resampleStepwise(xin, yin, xout, avg=True)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertTrue(isinstance(yout[0], type(yin[1])))
        self.assertEqual(yout[0][0], 23.0)
        self.assertEqual(yout[0][1], 23.0)
        self.assertEqual(yout[1], 0)
        self.assertEqual(yout[2], 0)
        self.assertEqual(yout[3], 0)

    def test_resampleStepwiseAvgNpArray(self):
        """Test resampleStepwise() summing when some of the values are arrays"""
        xin = [0, 1, 2, 3, 4]
        yin = [11, np.array([1, 1]), np.array([2, 2]), 44]
        xout = [2, 4, 5, 6, 7]

        yout = resampleStepwise(xin, yin, xout, avg=False)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertTrue(isinstance(yout[0], type(yin[1])))
        self.assertEqual(yout[0][0], 46.0)
        self.assertEqual(yout[0][1], 46.0)
        self.assertEqual(yout[1], 0)
        self.assertEqual(yout[2], 0)
        self.assertEqual(yout[3], 0)

    def test_rotateXY(self):
        x = [1.0, -1.0]
        y = [1.0, 1.0]

        # test operation on scalar
        xr, yr = rotateXY(x[0], y[0], 45.0)
        self.assertAlmostEqual(xr, 0.0)
        self.assertAlmostEqual(yr, sqrt(2))

        xr, yr = rotateXY(x[1], y[1], 45.0)
        self.assertAlmostEqual(xr, -sqrt(2))
        self.assertAlmostEqual(yr, 0.0)

        # test operation on list
        xr, yr = rotateXY(x, y, 45.0)
        self.assertAlmostEqual(xr[0], 0.0)
        self.assertAlmostEqual(yr[0], sqrt(2))
        self.assertAlmostEqual(xr[1], -sqrt(2))
        self.assertAlmostEqual(yr[1], 0.0)


if __name__ == "__main__":
    unittest.main()
