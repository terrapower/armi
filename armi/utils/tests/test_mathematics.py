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
import unittest

from armi.utils.mathematics import resampleStepwise


class TestMath(unittest.TestCase):
    """Tests for various math utilities"""

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


if __name__ == "__main__":
    unittest.main()
