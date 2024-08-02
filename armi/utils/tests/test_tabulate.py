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
from collections import OrderedDict, UserDict
import unittest

import numpy  # TODO: as np

from armi.utils.tabulate import _multilineWidth
from armi.utils.tabulate import tabulate, tabulate_formats


class TestTabulateAPI(unittest.TestCase):
    def test_tabulateFormats(self):
        """API: tabulate_formats is a list of strings."""
        supported = tabulate_formats
        self.assertEqual(type(supported), list)
        for fmt in supported:
            self.assertEqual(type(fmt), str)


class TestTabulateInputs(unittest.TestCase):
    def test_iterableOfIterables(self):
        """Input: an interable of iterables."""
        ii = iter(map(lambda x: iter(x), [range(5), range(5, 0, -1)]))
        expected = "\n".join(
            ["-  -  -  -  -", "0  1  2  3  4", "5  4  3  2  1", "-  -  -  -  -"]
        )
        result = tabulate(ii)
        self.assertEqual(expected, result)

    def test_iterable_of_iterables_headers(self):
        """Input: an interable of iterables with headers."""
        ii = iter(map(lambda x: iter(x), [range(5), range(5, 0, -1)]))
        expected = "\n".join(
            [
                "  a    b    c    d    e",
                "---  ---  ---  ---  ---",
                "  0    1    2    3    4",
                "  5    4    3    2    1",
            ]
        )
        result = tabulate(ii, "abcde")
        self.assertEqual(expected, result)

    def test_iterable_of_iterables_firstrow(self):
        """Input: an interable of iterables with the first row as headers."""
        ii = iter(map(lambda x: iter(x), ["abcde", range(5), range(5, 0, -1)]))
        expected = "\n".join(
            [
                "  a    b    c    d    e",
                "---  ---  ---  ---  ---",
                "  0    1    2    3    4",
                "  5    4    3    2    1",
            ]
        )
        result = tabulate(ii, "firstrow")
        self.assertEqual(expected, result)

    def test_list_of_lists(self):
        """Input: a list of lists with headers."""
        ll = [["a", "one", 1], ["b", "two", None]]
        expected = "\n".join(
            [
                "    string      number",
                "--  --------  --------",
                "a   one              1",
                "b   two",
            ]
        )
        result = tabulate(ll, headers=["string", "number"])
        self.assertEqual(expected, result)

    def test_list_of_lists_firstrow(self):
        """Input: a list of lists with the first row as headers."""
        ll = [["string", "number"], ["a", "one", 1], ["b", "two", None]]
        expected = "\n".join(
            [
                "    string      number",
                "--  --------  --------",
                "a   one              1",
                "b   two",
            ]
        )
        result = tabulate(ll, headers="firstrow")
        self.assertEqual(expected, result)

    def test_list_of_lists_keys(self):
        """Input: a list of lists with column indices as headers."""
        ll = [["a", "one", 1], ["b", "two", None]]
        expected = "\n".join(
            ["0    1      2", "---  ---  ---", "a    one    1", "b    two"]
        )
        result = tabulate(ll, headers="keys")
        self.assertEqual(expected, result)

    def testDictLike(self):
        """Input: a dict of iterables with keys as headers."""
        # columns should be padded with None, keys should be used as headers
        dd = {"a": range(3), "b": range(101, 105)}
        # keys' order (hence columns' order) is not deterministic in Python 3
        # => we have to consider both possible results as valid
        expected1 = "\n".join(
            ["  a    b", "---  ---", "  0  101", "  1  102", "  2  103", "     104"]
        )
        result = tabulate(dd, "keys")
        self.assertEqual(result, expected1)

    def test_numpy_2d(self):
        """Input: a 2D NumPy array with headers."""
        na = (numpy.arange(1, 10, dtype=numpy.float32).reshape((3, 3)) ** 3) * 0.5
        expected = "\n".join(
            [
                "    a      b      c",
                "-----  -----  -----",
                "  0.5    4     13.5",
                " 32     62.5  108",
                "171.5  256    364.5",
            ]
        )
        result = tabulate(na, ["a", "b", "c"])
        self.assertEqual(expected, result)

    def test_numpy_2d_firstrow(self):
        """Input: a 2D NumPy array with the first row as headers."""
        na = numpy.arange(1, 10, dtype=numpy.int32).reshape((3, 3)) ** 3
        expected = "\n".join(
            ["  1    8    27", "---  ---  ----", " 64  125   216", "343  512   729"]
        )
        result = tabulate(na, headers="firstrow")
        self.assertEqual(expected, result)

    def test_numpy_2d_keys(self):
        """Input: a 2D NumPy array with column indices as headers."""
        na = (numpy.arange(1, 10, dtype=numpy.float32).reshape((3, 3)) ** 3) * 0.5
        expected = "\n".join(
            [
                "    0      1      2",
                "-----  -----  -----",
                "  0.5    4     13.5",
                " 32     62.5  108",
                "171.5  256    364.5",
            ]
        )
        result = tabulate(na, headers="keys")
        self.assertEqual(expected, result)

    def test_numpy_record_array(self):
        """Input: a 2D NumPy record array without header."""
        na = numpy.asarray(
            [("Alice", 23, 169.5), ("Bob", 27, 175.0)],
            dtype={
                "names": ["name", "age", "height"],
                "formats": ["a32", "uint8", "float32"],
            },
        )
        expected = "\n".join(
            [
                "-----  --  -----",
                "Alice  23  169.5",
                "Bob    27  175",
                "-----  --  -----",
            ]
        )
        result = tabulate(na)
        self.assertEqual(expected, result)

    def test_numpy_record_array_keys(self):
        """Input: a 2D NumPy record array with column names as headers."""
        na = numpy.asarray(
            [("Alice", 23, 169.5), ("Bob", 27, 175.0)],
            dtype={
                "names": ["name", "age", "height"],
                "formats": ["a32", "uint8", "float32"],
            },
        )
        expected = "\n".join(
            [
                "name      age    height",
                "------  -----  --------",
                "Alice      23     169.5",
                "Bob        27     175",
            ]
        )
        result = tabulate(na, headers="keys")
        self.assertEqual(expected, result)

    def test_numpy_record_array_headers(self):
        """Input: a 2D NumPy record array with user-supplied headers."""
        na = numpy.asarray(
            [("Alice", 23, 169.5), ("Bob", 27, 175.0)],
            dtype={
                "names": ["name", "age", "height"],
                "formats": ["a32", "uint8", "float32"],
            },
        )
        expected = "\n".join(
            [
                "person      years     cm",
                "--------  -------  -----",
                "Alice          23  169.5",
                "Bob            27  175",
            ]
        )
        result = tabulate(na, headers=["person", "years", "cm"])
        self.assertEqual(expected, result)

    def test_list_of_namedtuples(self):
        """Input: a list of named tuples with field names as headers."""
        from collections import namedtuple

        NT = namedtuple("NT", ["foo", "bar"])
        lt = [NT(1, 2), NT(3, 4)]
        expected = "\n".join(["-  -", "1  2", "3  4", "-  -"])
        result = tabulate(lt)
        self.assertEqual(expected, result)

    def test_list_of_namedtuples_keys(self):
        """Input: a list of named tuples with field names as headers."""
        from collections import namedtuple

        NT = namedtuple("NT", ["foo", "bar"])
        lt = [NT(1, 2), NT(3, 4)]
        expected = "\n".join(
            ["  foo    bar", "-----  -----", "    1      2", "    3      4"]
        )
        result = tabulate(lt, headers="keys")
        self.assertEqual(expected, result)

    def test_list_of_dicts(self):
        """Input: a list of dictionaries."""
        lod = [{"foo": 1, "bar": 2}, {"foo": 3, "bar": 4}]
        expected1 = "\n".join(["-  -", "1  2", "3  4", "-  -"])
        expected2 = "\n".join(["-  -", "2  1", "4  3", "-  -"])
        result = tabulate(lod)
        self.assertIn(result, [expected1, expected2])

    def test_list_of_userdicts(self):
        """Input: a list of UserDicts."""
        lod = [UserDict(foo=1, bar=2), UserDict(foo=3, bar=4)]
        expected1 = "\n".join(["-  -", "1  2", "3  4", "-  -"])
        expected2 = "\n".join(["-  -", "2  1", "4  3", "-  -"])
        result = tabulate(lod)
        self.assertIn(result, [expected1, expected2])

    def test_list_of_dicts_keys(self):
        """Input: a list of dictionaries, with keys as headers."""
        lod = [{"foo": 1, "bar": 2}, {"foo": 3, "bar": 4}]
        expected1 = "\n".join(
            ["  foo    bar", "-----  -----", "    1      2", "    3      4"]
        )
        expected2 = "\n".join(
            ["  bar    foo", "-----  -----", "    2      1", "    4      3"]
        )
        result = tabulate(lod, headers="keys")
        self.assertIn(result, [expected1, expected2])

    def test_list_of_userdicts_keys(self):
        """Input: a list of UserDicts."""
        lod = [UserDict(foo=1, bar=2), UserDict(foo=3, bar=4)]
        expected1 = "\n".join(
            ["  foo    bar", "-----  -----", "    1      2", "    3      4"]
        )
        expected2 = "\n".join(
            ["  bar    foo", "-----  -----", "    2      1", "    4      3"]
        )
        result = tabulate(lod, headers="keys")
        self.assertIn(result, [expected1, expected2])

    def test_list_of_dicts_with_missing_keys(self):
        """Input: a list of dictionaries, with missing keys."""
        lod = [{"foo": 1}, {"bar": 2}, {"foo": 4, "baz": 3}]
        expected = "\n".join(
            [
                "  foo    bar    baz",
                "-----  -----  -----",
                "    1",
                "           2",
                "    4             3",
            ]
        )
        result = tabulate(lod, headers="keys")
        self.assertEqual(expected, result)

    def test_list_of_dicts_firstrow(self):
        """Input: a list of dictionaries, with the first dict as headers."""
        lod = [{"foo": "FOO", "bar": "BAR"}, {"foo": 3, "bar": 4, "baz": 5}]
        # if some key is missing in the first dict, use the key name instead
        expected1 = "\n".join(
            ["  FOO    BAR    baz", "-----  -----  -----", "    3      4      5"]
        )
        expected2 = "\n".join(
            ["  BAR    FOO    baz", "-----  -----  -----", "    4      3      5"]
        )
        result = tabulate(lod, headers="firstrow")
        self.assertIn(result, [expected1, expected2])

    def test_list_of_dicts_with_dict_of_headers(self):
        """Input: a dict of user headers for a list of dicts."""
        table = [{"letters": "ABCDE", "digits": 12345}]
        headers = {"digits": "DIGITS", "letters": "LETTERS"}
        expected1 = "\n".join(
            ["  DIGITS  LETTERS", "--------  ---------", "   12345  ABCDE"]
        )
        expected2 = "\n".join(
            ["LETTERS      DIGITS", "---------  --------", "ABCDE         12345"]
        )
        result = tabulate(table, headers=headers)
        self.assertIn(result, [expected1, expected2])

    def test_list_of_dicts_with_list_of_headers(self):
        """Input: ValueError on a list of headers with a list of dicts."""
        table = [{"letters": "ABCDE", "digits": 12345}]
        headers = ["DIGITS", "LETTERS"]
        with self.assertRaises(ValueError):
            tabulate(table, headers=headers)

    def test_list_of_ordereddicts(self):
        """Input: a list of OrderedDicts."""
        od = OrderedDict([("b", 1), ("a", 2)])
        lod = [od, od]
        expected = "\n".join(["  b    a", "---  ---", "  1    2", "  1    2"])
        result = tabulate(lod, headers="keys")
        self.assertEqual(expected, result)

    def test_list_bytes(self):
        """Input: a list of bytes."""
        lb = [["你好".encode("utf-8")], ["你好"]]
        expected = "\n".join(
            [
                "bytes",
                "---------------------------",
                r"b'\xe4\xbd\xa0\xe5\xa5\xbd'",
                "你好",
            ]
        )
        result = tabulate(lb, headers=["bytes"])
        self.assertEqual(expected, result)


class TestTabulateInternal(unittest.TestCase):
    def test_multilineWidth(self):
        """Internal: _multilineWidth()."""
        multilineString = "\n".join(["foo", "barbaz", "spam"])
        self.assertEqual(_multilineWidth(multilineString), 6)
        onelineString = "12345"
        self.assertEqual(_multilineWidth(onelineString), len(onelineString))
