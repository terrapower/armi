# Copyright 2021 TerraPower, LLC
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

"""Unit tests for the test helpers."""

import unittest

from armi import tests


class TestCompareFiles(unittest.TestCase):
    def test_compareFileLine(self):
        expected = "oh look, a number! 3.14 and some text and another number 1.5 and another 0.0"

        # any line compared with itself should pass
        self.assertTrue(tests.ArmiTestHelper.compareLines(expected, expected))
        self.assertTrue(tests.ArmiTestHelper.compareLines(expected, expected, eps=0.01))

        # if we vary the numbers a tiny bit, the epsilon parameter should correctly control the comparison
        actual = "oh look, a number! 3.15 and some text and another number 1.6 and another 0.0  "
        self.assertFalse(tests.ArmiTestHelper.compareLines(expected, actual, eps=0.04))
        self.assertTrue(tests.ArmiTestHelper.compareLines(expected, actual, eps=0.07))

        # if we add an extra, non-number word, the comparison should fail
        actual = "oh look, a number! 3.15 and some text and another number 1.6 extra and another 0.0"
        self.assertFalse(tests.ArmiTestHelper.compareLines(expected, actual, eps=0.04))

        # if we replace a number with not a number, the comparison should fail
        actual = "oh look, a number! notANumber and some text and another number 1.5 and another 0.0"
        self.assertFalse(tests.ArmiTestHelper.compareLines(expected, actual, eps=0.04))

    def test_onlySomeMatch(self):
        # only the first number in the line matches, so the line should fail
        expected = "oh look, a number! 3.14 and some text and another number 1.5 and another 0.0"
        actual = "oh look, a number! 3.14 and some text and another number 2.2 and another 9.9"
        self.assertFalse(tests.ArmiTestHelper.compareLines(expected, actual, eps=0.01))

        # only the second number in the line matches, so the line should fail
        expected = "oh look, a number! 3.14 and some text and another number 1.5 and another 0.0"
        actual = "oh look, a number! 7.7 and some text and another number 1.5 and another 9.9"
        self.assertFalse(tests.ArmiTestHelper.compareLines(expected, actual, eps=0.01))

        # only the last number in the line matches, so the line should fail
        expected = "oh look, a number! 3.14 and some text and another number 1.5 and another 0.0"
        actual = "oh look, a number! 7.7 and some text and another number 8.5 and another 0.0"
        self.assertFalse(tests.ArmiTestHelper.compareLines(expected, actual, eps=0.01))

    def test_strangeCases(self):
        # comparing the same string should return True, even if there are no numbers
        expected = "There are no numbers"
        self.assertTrue(tests.ArmiTestHelper.compareLines(expected, expected))

        # comparing different strings should return False, even if there are no numbers
        actual = "There are SOME numbers"
        self.assertFalse(tests.ArmiTestHelper.compareLines(expected, actual))

        # comparing empty strings should return True
        self.assertTrue(tests.ArmiTestHelper.compareLines("", ""))

        # comparing equal strings of whitespace should return True
        whiteSpace3 = "   "
        self.assertTrue(tests.ArmiTestHelper.compareLines(whiteSpace3, str(whiteSpace3)))
