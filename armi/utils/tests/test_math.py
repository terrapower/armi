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

from armi.utils.math import resampleStepwise


class TestMath(unittest.TestCase):
    """Tests for various math utilities"""

    def test_resampleStepwiseAvg0(self):
        """Test resampleStepwise() averaging when in and out bins match"""
        xin = [0, 1, 2, 13.3]
        yin = [4.76, 9.99, -123.456]
        xout = [0, 1, 2, 13.3]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 4.76)
        self.assertEqual(yout[1], 9.99)
        self.assertEqual(yout[2], -123.456)

    def test_resampleStepwiseAvg1(self):
        """Test resampleStepwise() averaging for one arbitrary case"""
        xin = [0, 1, 2, 3, 4]
        yin = [3, 2, 5, 3]
        xout = [0, 2, 3.5, 4]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 2.5)
        self.assertAlmostEqual(yout[1], 4.333333333333333, delta=1e-6)
        self.assertEqual(yout[2], 3)

    def test_resampleStepwiseAvg2(self):
        """Test resampleStepwise() averaging for another arbitrary case"""
        xin = [0, 1, 2, 3, 4, 5]
        yin = [3, 2, 5, 3, 4]
        xout = [0, 2, 3.5, 5]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 2.5)
        self.assertAlmostEqual(yout[1], 4.333333333333333, delta=1e-6)
        self.assertAlmostEqual(yout[2], 3.6666666666666665, delta=1e-6)

    def test_resampleStepwiseAvg3(self):
        """Test resampleStepwise() averaging for another arbitrary case"""
        xin = [0, 1, 2, 3, 4, 6]
        yin = [3, 2, 5, 3, 4]
        xout = [0, 2, 3.5, 6]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 2.5)
        self.assertAlmostEqual(yout[1], 4.333333333333333, delta=1e-6)
        self.assertEqual(yout[2], 3.8)

    def test_resampleStepwiseAvg4(self):
        """Test resampleStepwise() averaging for mathing, but uneven intervals"""
        xin = [0, 3, 5, 6.777, 9.123]
        yin = [3.1, 2.2, 5.3, 3.4]
        xout = [0, 3, 5, 6.777, 9.123]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 3.1)
        self.assertEqual(yout[1], 2.2)
        self.assertEqual(yout[2], 5.3)
        self.assertEqual(yout[3], 3.4)

    def test_resampleStepwiseAvg4(self):
        """Test resampleStepwise() averaging for mathing, almost matching intervals"""
        xin = [0, 3, 5, 6.777, 9.123]
        yin = [3.1, 2.2, 5.3, 3.4]
        xout = [0, 5, 9.123]

        yout = resampleStepwise(xin, yin, xout)

        self.assertEqual(len(yout), len(xout) - 1)
        self.assertEqual(yout[0], 2.74)
        self.assertAlmostEqual(yout[1], 4.21889400921659, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
