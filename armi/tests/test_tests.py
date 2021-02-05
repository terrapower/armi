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

"""
Unit tests for the test helpers.
"""

import unittest

from armi import tests


class Test_CompareFiles(unittest.TestCase):
    def test_compareFileLine(self):
        expected = "oh look, a number! 3.14 and some text and another number 1.5"

        self.assertTrue(tests.ArmiTestHelper.compareLines(expected, expected))
        self.assertTrue(tests.ArmiTestHelper.compareLines(expected, expected, eps=0.01))

        actual = "oh look, a number! 3.15 and some text and another number 1.6  "
        self.assertFalse(tests.ArmiTestHelper.compareLines(expected, actual, eps=0.04))
        self.assertTrue(tests.ArmiTestHelper.compareLines(expected, actual, eps=0.07))

        actual = "oh look, a number! 3.15 and some text and another number 1.6 extra"
        self.assertFalse(tests.ArmiTestHelper.compareLines(expected, actual, eps=0.04))

        actual = "oh look, a number! notANumber and some text and another number 1.5"
        self.assertFalse(tests.ArmiTestHelper.compareLines(expected, actual, eps=0.04))
