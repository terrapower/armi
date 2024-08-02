# Copyright 2024 TerraPower, LLC
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
#
# NOTE: This code originally started out as the MIT-licensed "tabulate":
#       This was originally https://github.com/astanin/python-tabulate

"""Tests for tabulate."""
import unittest

from armi.utils.tabulate import tabulate, tabulate_formats


class TestTabulate(unittest.TestCase):
    def test_tabulateFormats(self):
        """API: tabulate_formats is a list of strings."""
        supported = tabulate_formats
        self.assertEqual(type(supported), list)
        for fmt in supported:
            self.assertEqual(type(fmt), str)

    def test_iterableOfIterables(self):
        """Input: an interable of iterables."""
        ii = iter(map(lambda x: iter(x), [range(5), range(5, 0, -1)]))
        expected = "\n".join(
            ["-  -  -  -  -", "0  1  2  3  4", "5  4  3  2  1", "-  -  -  -  -"]
        )
        result = tabulate(ii)
        self.assertEqual(expected, result)
