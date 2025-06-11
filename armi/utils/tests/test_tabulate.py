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

"""Tests for tabulate.

This file started out as the MIT-licensed "tabulate". Though we have made, and will continue to make
many arbitrary changes as we need. Thanks to the tabulate team.

https://github.com/astanin/python-tabulate
"""

import unittest
from collections import OrderedDict, UserDict, defaultdict, namedtuple
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from armi.utils.tabulate import (
    SEPARATING_LINE,
    _alignCellVeritically,
    _alignColumn,
    _bool,
    _buildLine,
    _buildRow,
    _format,
    _isMultiline,
    _multilineWidth,
    _normalizeTabularData,
    _tableFormats,
    _type,
    _visibleWidth,
    _wrapTextToColWidths,
    tabulate,
    tabulateFormats,
)


class TestTabulateAPI(unittest.TestCase):
    def test_tabulateFormats(self):
        """API: tabulateFormats is a list of strings."""
        supported = tabulateFormats
        self.assertEqual(type(supported), list)
        for fmt in supported:
            self.assertEqual(type(fmt), str)


class TestTabulateInputs(unittest.TestCase):
    def test_iterableOfEmpties(self):
        """Input: test various empty inputs."""
        ii = iter(map(lambda x: iter(x), []))
        result = tabulate(ii, "firstrow")
        self.assertEqual("", result)

        ij = iter(map(lambda x: iter(x), ["abcde"]))
        expected = "\n".join(
            [
                "a    b    c    d    e",
                "---  ---  ---  ---  ---",
            ]
        )
        result = tabulate(ij, "firstrow")
        self.assertEqual(expected, result)

        ik = iter([])
        expected = "\n".join(
            [
                "a    b    c",
                "---  ---  ---",
            ]
        )
        result = tabulate(ik, "abc")
        self.assertEqual(expected, result)

    def test_iterableOfIterables(self):
        """Input: an iterable of iterables."""
        ii = iter(map(lambda x: iter(x), [range(5), range(5, 0, -1)]))
        expected = "\n".join(["-  -  -  -  -", "0  1  2  3  4", "5  4  3  2  1", "-  -  -  -  -"])
        result = tabulate(ii, headersAlign="center")
        self.assertEqual(expected, result)

    def test_iterableOfIterablesHeaders(self):
        """Input: an iterable of iterables with headers."""
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

    def test_iterableOfIterablesFirstrow(self):
        """Input: an iterable of iterables with the first row as headers."""
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

    def test_listOfLists(self):
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

    def test_listOfListsFirstrow(self):
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

    def test_listOfListsKeys(self):
        """Input: a list of lists with column indices as headers."""
        ll = [["a", "one", 1], ["b", "two", None]]
        expected = "\n".join(["0    1      2", "---  ---  ---", "a    one    1", "b    two"])
        result = tabulate(ll, headers="keys")
        self.assertEqual(expected, result)

    def test_dictLike(self):
        """Input: a dict of iterables with keys as headers."""
        # columns should be padded with None, keys should be used as headers
        dd = {"a": range(3), "b": range(101, 105)}
        # keys' order (hence columns' order) is not deterministic in Python 3
        # => we have to consider both possible results as valid
        expected1 = "\n".join(["  a    b", "---  ---", "  0  101", "  1  102", "  2  103", "     104"])
        result = tabulate(dd, "keys")
        self.assertEqual(result, expected1)

    def test_numpy2d(self):
        """Input: a 2D NumPy array with headers."""
        na = (np.arange(1, 10, dtype=np.float32).reshape((3, 3)) ** 3) * 0.5
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

    def test_numpy2dFirstrow(self):
        """Input: a 2D NumPy array with the first row as headers."""
        na = np.arange(1, 10, dtype=np.int32).reshape((3, 3)) ** 3
        expected = "\n".join(["  1    8    27", "---  ---  ----", " 64  125   216", "343  512   729"])
        result = tabulate(na, headers="firstrow")
        self.assertEqual(expected, result)

    def test_numpy2dKeys(self):
        """Input: a 2D NumPy array with column indices as headers."""
        na = (np.arange(1, 10, dtype=np.float32).reshape((3, 3)) ** 3) * 0.5
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

    def test_numpyRecordArray(self):
        """Input: a 2D NumPy record array without header."""
        na = np.asarray(
            [("Alice", 23, 169.5), ("Bob", 27, 175.0)],
            dtype={
                "names": ["name", "age", "height"],
                "formats": ["S32", "uint8", "float32"],
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

    def test_numpyRecordArrayKeys(self):
        """Input: a 2D NumPy record array with column names as headers."""
        na = np.asarray(
            [("Alice", 23, 169.5), ("Bob", 27, 175.0)],
            dtype={
                "names": ["name", "age", "height"],
                "formats": ["S32", "uint8", "float32"],
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

    def test_numpyRecordArrayHeaders(self):
        """Input: a 2D NumPy record array with user-supplied headers."""
        na = np.asarray(
            [("Alice", 23, 169.5), ("Bob", 27, 175.0)],
            dtype={
                "names": ["name", "age", "height"],
                "formats": ["S32", "uint8", "float32"],
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

    def test_listOfNamedtuples(self):
        """Input: a list of named tuples with field names as headers."""
        NT = namedtuple("NT", ["foo", "bar"])
        lt = [NT(1, 2), NT(3, 4)]
        expected = "\n".join(["-  -", "1  2", "3  4", "-  -"])
        result = tabulate(lt)
        self.assertEqual(expected, result)

    def test_listOfNamedtuplesKeys(self):
        """Input: a list of named tuples with field names as headers."""
        NT = namedtuple("NT", ["foo", "bar"])
        lt = [NT(1, 2), NT(3, 4)]
        expected = "\n".join(["  foo    bar", "-----  -----", "    1      2", "    3      4"])
        result = tabulate(lt, headers="keys")
        self.assertEqual(expected, result)

    def test_listOfDicts(self):
        """Input: a list of dictionaries."""
        lod = [{"foo": 1, "bar": 2}, {"foo": 3, "bar": 4}]
        expected1 = "\n".join(["-  -", "1  2", "3  4", "-  -"])
        expected2 = "\n".join(["-  -", "2  1", "4  3", "-  -"])
        result = tabulate(lod)
        self.assertIn(result, [expected1, expected2])

    def test_listOfUserdicts(self):
        """Input: a list of UserDicts."""
        lod = [UserDict(foo=1, bar=2), UserDict(foo=3, bar=4)]
        expected1 = "\n".join(["-  -", "1  2", "3  4", "-  -"])
        expected2 = "\n".join(["-  -", "2  1", "4  3", "-  -"])
        result = tabulate(lod)
        self.assertIn(result, [expected1, expected2])

    def test_listOfDictsKeys(self):
        """Input: a list of dictionaries, with keys as headers."""
        lod = [{"foo": 1, "bar": 2}, {"foo": 3, "bar": 4}]
        expected1 = "\n".join(["  foo    bar", "-----  -----", "    1      2", "    3      4"])
        expected2 = "\n".join(["  bar    foo", "-----  -----", "    2      1", "    4      3"])
        result = tabulate(lod, headers="keys")
        self.assertIn(result, [expected1, expected2])

    def test_listOfUserdictsKeys(self):
        """Input: a list of UserDicts."""
        lod = [UserDict(foo=1, bar=2), UserDict(foo=3, bar=4)]
        expected1 = "\n".join(["  foo    bar", "-----  -----", "    1      2", "    3      4"])
        expected2 = "\n".join(["  bar    foo", "-----  -----", "    2      1", "    4      3"])
        result = tabulate(lod, headers="keys")
        self.assertIn(result, [expected1, expected2])

    def test_listOfDictsWithMissingKeys(self):
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

    def test_listOfDictsFirstrow(self):
        """Input: a list of dictionaries, with the first dict as headers."""
        lod = [{"foo": "FOO", "bar": "BAR"}, {"foo": 3, "bar": 4, "baz": 5}]
        # if some key is missing in the first dict, use the key name instead
        expected1 = "\n".join(["  FOO    BAR    baz", "-----  -----  -----", "    3      4      5"])
        expected2 = "\n".join(["  BAR    FOO    baz", "-----  -----  -----", "    4      3      5"])
        result = tabulate(lod, headers="firstrow")
        self.assertIn(result, [expected1, expected2])

    def test_listOfDictsWithDictOfHeaders(self):
        """Input: a dict of user headers for a list of dicts."""
        table = [{"letters": "ABCDE", "digits": 12345}]
        headers = {"digits": "DIGITS", "letters": "LETTERS"}
        expected1 = "\n".join(["  DIGITS  LETTERS", "--------  ---------", "   12345  ABCDE"])
        expected2 = "\n".join(["LETTERS      DIGITS", "---------  --------", "ABCDE         12345"])
        result = tabulate(table, headers=headers)
        self.assertIn(result, [expected1, expected2])

    def test_listOfDictsWithListOfHeaders(self):
        """Input: ValueError on a list of headers with a list of dicts."""
        table = [{"letters": "ABCDE", "digits": 12345}]
        headers = ["DIGITS", "LETTERS"]
        with self.assertRaises(ValueError):
            tabulate(table, headers=headers)

    def test_listOfOrdereddicts(self):
        """Input: a list of OrderedDicts."""
        od = OrderedDict([("b", 1), ("a", 2)])
        lod = [od, od]
        expected = "\n".join(["  b    a", "---  ---", "  1    2", "  1    2"])
        result = tabulate(lod, headers="keys")
        self.assertEqual(expected, result)

    def test_listBytes(self):
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

    def test_tightCouplingExample(self):
        """Input: Real world-ish example from tight coupling."""
        # the two examples below should both produce the same output:
        border = "--  ------------------------------  --------------  ----------------------------"
        expected = "\n".join(
            [
                border,
                "      criticalCrIteration: keffUnc    dif3d: power    thInterface: THavgCladTemp",
                border,
                " 0                     9.01234e-05      0.00876543                    0.00123456",
                border,
            ]
        )

        # the data is a regular dictionary
        data = {
            "criticalCrIteration: keffUnc": [9.01234e-05],
            "dif3d: power": [0.00876543],
            "thInterface: THavgCladTemp": [0.00123456],
        }
        result = tabulate(data, headers="keys", showIndex=True, tableFmt="armi")
        self.assertEqual(expected, result)

        # the data is a defaultdict
        dataD = defaultdict(list)
        for key, vals in data.items():
            for val in vals:
                dataD[key].append(val)

        result2 = tabulate(dataD, headers="keys", showIndex=True, tableFmt="armi")
        self.assertEqual(expected, result2)


class TestTabulateInternal(unittest.TestCase):
    def test_alignColumnDecimal(self):
        """Internal: _align_column(..., 'decimal')."""
        column = ["12.345", "-1234.5", "1.23", "1234.5", "1e+234", "1.0e234"]
        result = _alignColumn(column, "decimal")
        expected = [
            "   12.345  ",
            "-1234.5    ",
            "    1.23   ",
            " 1234.5    ",
            "    1e+234 ",
            "    1.0e234",
        ]
        self.assertEqual(expected, result)

    def test_alignColumnDecimalWithThousandSeparators(self):
        """Internal: _align_column(..., 'decimal')."""
        column = ["12.345", "-1234.5", "1.23", "1,234.5", "1e+234", "1.0e234"]
        output = _alignColumn(column, "decimal")
        expected = [
            "   12.345  ",
            "-1234.5    ",
            "    1.23   ",
            "1,234.5    ",
            "    1e+234 ",
            "    1.0e234",
        ]
        self.assertEqual(expected, output)

    def test_alignColDecimalIncorrectThousandSeparators(self):
        """Internal: _align_column(..., 'decimal')."""
        column = ["12.345", "-1234.5", "1.23", "12,34.5", "1e+234", "1.0e234"]
        output = _alignColumn(column, "decimal")
        expected = [
            "     12.345  ",
            "  -1234.5    ",
            "      1.23   ",
            "12,34.5      ",
            "      1e+234 ",
            "      1.0e234",
        ]
        self.assertEqual(expected, output)

    def test_alignColumnNone(self):
        """Internal: _align_column(..., None)."""
        column = ["123.4", "56.7890"]
        output = _alignColumn(column, None)
        expected = ["123.4", "56.7890"]
        self.assertEqual(expected, output)

    def test_alignColumnMultiline(self):
        """Internal: _align_column(..., is_multiline=True)."""
        column = ["1", "123", "12345\n6"]
        output = _alignColumn(column, "center", isMultiline=True)
        expected = ["  1  ", " 123 ", "12345" + "\n" + "  6  "]
        self.assertEqual(expected, output)

    def test_alignCellVeriticallyOneLineOnly(self):
        """Internal: Aligning a single height cell is same regardless of alignment value."""
        lines = ["one line"]
        column_width = 8

        top = _alignCellVeritically(lines, 1, column_width, "top")
        center = _alignCellVeritically(lines, 1, column_width, "center")
        bottom = _alignCellVeritically(lines, 1, column_width, "bottom")
        none = _alignCellVeritically(lines, 1, column_width, None)

        expected = ["one line"]
        assert top == center == bottom == none == expected

    def test_alignCellVertTopSingleTextMultiPad(self):
        """Internal: Align single cell text to top."""
        result = _alignCellVeritically(["one line"], 3, 8, "top")
        expected = ["one line", "        ", "        "]
        self.assertEqual(expected, result)

    def test_alignCellVertCenterSingleTextMultiPad(self):
        """Internal: Align single cell text to center."""
        result = _alignCellVeritically(["one line"], 3, 8, "center")
        expected = ["        ", "one line", "        "]
        self.assertEqual(expected, result)

    def test_alignCellVertBottomSingleTextMultiPad(self):
        """Internal: Align single cell text to bottom."""
        result = _alignCellVeritically(["one line"], 3, 8, "bottom")
        expected = ["        ", "        ", "one line"]
        self.assertEqual(expected, result)

    def test_alignCellVertTopMultiTextMultiPad(self):
        """Internal: Align multiline celltext text to top."""
        text = ["just", "one ", "cell"]
        result = _alignCellVeritically(text, 6, 4, "top")
        expected = ["just", "one ", "cell", "    ", "    ", "    "]
        self.assertEqual(expected, result)

    def test_alignCellVertCenterMultiTextMultiPad(self):
        """Internal: Align multiline celltext text to center."""
        text = ["just", "one ", "cell"]
        result = _alignCellVeritically(text, 6, 4, "center")

        # Even number of rows, can't perfectly center, but we pad less
        # at top when required to do make a judgement
        expected = ["    ", "just", "one ", "cell", "    ", "    "]
        self.assertEqual(expected, result)

    def test_alignCellVertBottomMultiTextMultiPad(self):
        """Internal: Align multiline celltext text to bottom."""
        text = ["just", "one ", "cell"]
        result = _alignCellVeritically(text, 6, 4, "bottom")
        expected = ["    ", "    ", "    ", "just", "one ", "cell"]
        self.assertEqual(expected, result)

    def test_assortedRareEdgeCases(self):
        """Test some of the more rare edge cases in the purely internal functions."""
        from armi.utils.tabulate import (
            _alignHeader,
            _prependRowIndex,
            _removeSeparatingLines,
        )

        self.assertEqual(_alignHeader("123", False, 3, 3, False, None), "123")

        result = _removeSeparatingLines(123)
        self.assertEqual(result[0], 123)
        self.assertIsNone(result[1])

        self.assertEqual(_prependRowIndex([123], None), [123])

    def test_bool(self):
        self.assertTrue(_bool("stuff"))
        self.assertFalse(_bool(""))
        self.assertTrue(_bool(123))
        self.assertFalse(_bool(np.array([1, 0, -1])))

    def test_buildLine(self):
        """Basic sanity test of internal _buildLine() function."""
        lineFormat = _tableFormats["armi"].lineabove
        self.assertEqual(_buildLine([2, 2], ["center", "center"], lineFormat), "--  --")

        formatter = lambda a, b: "xyz"
        self.assertEqual(_buildLine([2, 2], ["center", "center"], formatter), "xyz")

        self.assertIsNone(_buildLine([2, 2], ["center", "center"], None))

    def test_buildRow(self):
        """Basic sanity test of internal _buildRow() function."""
        rowFormat = _tableFormats["armi"].datarow
        self.assertEqual(_buildRow("", [2, 2], ["center", "center"], rowFormat), "")

        formatter = lambda a, b, c: "xyz"
        d = {"a": 1, "b": 2}
        self.assertEqual(_buildRow(d, [2, 2], ["center", "center"], formatter), "xyz")

        lst = ["ab", "cd"]
        self.assertEqual(_buildRow(lst, [2, 2], ["center", "center"], rowFormat), "ab  cd")

        self.assertIsNone(_buildRow("ab", [2, 2], ["center", "center"], ""))

    def test_format(self):
        """Basic sanity test of internal _format() function."""
        self.assertEqual(_format(None, str, "8", "", "X", True), "X")
        self.assertEqual(_format(123, str, "8", "", "X", True), "123")
        self.assertEqual(_format("123", int, "8", "", "X", True), "123")
        self.assertEqual(_format(bytes("abc", "utf-8"), bytes, "8", "", "X", True), "abc")
        self.assertEqual(_format("3.14", float, "4", "", "X", True), "3.14")
        colorNum = "\x1b[31m3.14\x1b[0m"
        self.assertEqual(_format(colorNum, float, "4", "", "X", True), colorNum)
        self.assertEqual(_format(None, None, "8", "", "X", True), "X")

    def test_isMultiline(self):
        """Basic sanity test of internal _isMultiline() function."""
        self.assertFalse(_isMultiline("world"))
        self.assertTrue(_isMultiline("hello\nworld"))
        self.assertFalse(_isMultiline(bytes("world", "utf-8")))
        self.assertTrue(_isMultiline(bytes("hello\nworld", "utf-8")))

    def test_multilineWidth(self):
        """Internal: _multilineWidth()."""
        multilineString = "\n".join(["foo", "barbaz", "spam"])
        self.assertEqual(_multilineWidth(multilineString), 6)
        onelineString = "12345"
        self.assertEqual(_multilineWidth(onelineString), len(onelineString))

    def test_normalizeTabularData(self):
        """Basic sanity test of internal _normalizeTabularData() function."""
        res = _normalizeTabularData([[1, 2], [3, 4]], np.array(["a", "b"]), "default")
        self.assertEqual(res[0], [[1, 2], [3, 4]])
        self.assertEqual(res[1], ["a", "b"])
        self.assertEqual(res[2], 0)

        res = _normalizeTabularData([], "keys", "default")
        self.assertEqual(len(res[0]), 0)
        self.assertEqual(len(res[1]), 0)
        self.assertEqual(res[2], 0)

        res = _normalizeTabularData([], "firstrow", "default")
        self.assertEqual(len(res[0]), 0)
        self.assertEqual(len(res[1]), 0)
        self.assertEqual(res[2], 0)

        @dataclass
        class row:
            a: int
            b: int

        rows = [row(1, 2), row(3, 4)]
        res = _normalizeTabularData(rows, "keys", "default")
        self.assertEqual(res[0], [[1, 2], [3, 4]])
        self.assertEqual(res[1], ["a", "b"])
        self.assertEqual(res[2], 0)

        res = _normalizeTabularData(rows, ["x", "y"], "default")
        self.assertEqual(res[0], [[1, 2], [3, 4]])
        self.assertEqual(res[1], ["x", "y"])
        self.assertEqual(res[2], 0)

    def test_type(self):
        """Basic sanity test of internal _type() function."""
        self.assertEqual(_type(None), type(None))
        self.assertEqual(_type("foo"), type(""))
        self.assertEqual(_type("1"), type(1))
        self.assertEqual(_type("\x1b[31m42\x1b[0m"), type(42))
        self.assertEqual(_type("\x1b[31m42\x1b[0m"), type(42))
        self.assertEqual(_type(datetime.now()), type("2024-12-31"))

    def test_visibleWidth(self):
        """Basic sanity test of internal _visibleWidth() function."""
        self.assertEqual(_visibleWidth("world"), 5)
        self.assertEqual(_visibleWidth("\x1b[31mhello\x1b[0m"), 5)
        self.assertEqual(_visibleWidth(np.ones(3)), 10)

    def test_wrapTextToColWidths(self):
        """Basic sanity test of internal _wrapTextToColWidths() function."""
        res = _wrapTextToColWidths([], [2, 2], True)
        self.assertEqual(len(res), 0)

        res = _wrapTextToColWidths([[1], [2]], [2, 2], True)
        self.assertEqual(res[0][0], 1)
        self.assertEqual(res[1][0], 2)

        res = _wrapTextToColWidths([["1"], ["2"]], [2, 2], False)
        self.assertEqual(res[0][0], "1")
        self.assertEqual(res[1][0], "2")


class TestTabulateOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.testTable = [["spam", 41.9999], ["eggs", "451.0"]]
        cls.testTableWithSepLine = [
            ["spam", 41.9999],
            SEPARATING_LINE,
            ["eggs", "451.0"],
        ]
        cls.testTableHeaders = ["strings", "numbers"]

    def test_plain(self):
        """Output: plain with headers."""
        expected = "\n".join(["strings      numbers", "spam         41.9999", "eggs        451"])
        result = tabulate(self.testTable, self.testTableHeaders, tableFmt="plain")
        self.assertEqual(expected, result)

    def test_plainHeaderless(self):
        """Output: plain without headers."""
        expected = "\n".join(["spam   41.9999", "eggs  451"])
        result = tabulate(self.testTable, tableFmt="plain")
        self.assertEqual(expected, result)

    def test_plainMultilineHeaderless(self):
        """Output: plain with multiline cells without headers."""
        table = [["foo bar\nbaz\nbau", "hello"], ["", "multiline\nworld"]]
        expected = "\n".join(
            [
                "foo bar    hello",
                "  baz",
                "  bau",
                "         multiline",
                "           world",
            ]
        )
        result = tabulate(table, strAlign="center", tableFmt="plain")
        self.assertEqual(expected, result)

    def test_plainMultiline(self):
        """Output: plain with multiline cells with headers."""
        table = [[2, "foo\nbar"]]
        headers = ("more\nspam \x1b[31meggs\x1b[0m", "more spam\n& eggs")
        expected = "\n".join(
            [
                "       more  more spam",
                "  spam \x1b[31meggs\x1b[0m  & eggs",
                "          2  foo",
                "             bar",
            ]
        )
        result = tabulate(table, headers, tableFmt="plain")
        self.assertEqual(expected, result)

    def test_plainMultilineWithLinks(self):
        """Output: plain with multiline cells with links and headers."""
        table = [[2, "foo\nbar"]]
        headers = (
            "more\nspam \x1b]8;;target\x1b\\eggs\x1b]8;;\x1b\\",
            "more spam\n& eggs",
        )
        expected = "\n".join(
            [
                "       more  more spam",
                "  spam \x1b]8;;target\x1b\\eggs\x1b]8;;\x1b\\  & eggs",
                "          2  foo",
                "             bar",
            ]
        )
        result = tabulate(table, headers, tableFmt="plain")
        self.assertEqual(expected, result)

    def test_plainMultilineWithEmptyCells(self):
        """Output: plain with multiline cells and empty cells with headers."""
        table = [
            ["hdr", "data", "fold"],
            ["1", "", ""],
            ["2", "very long data", "fold\nthis"],
        ]
        expected = "\n".join(
            [
                "  hdr  data            fold",
                "    1",
                "    2  very long data  fold",
                "                       this",
            ]
        )
        result = tabulate(table, headers="firstrow", tableFmt="plain")
        self.assertEqual(expected, result)

    def test_plainMultilineWithEmptyCellsHeaderless(self):
        """Output: plain with multiline cells and empty cells without headers."""
        table = [["0", "", ""], ["1", "", ""], ["2", "very long data", "fold\nthis"]]
        expected = "\n".join(["0", "1", "2  very long data  fold", "                   this"])
        result = tabulate(table, tableFmt="plain")
        self.assertEqual(expected, result)

    def test_plainMaxcolwidthAutowraps(self):
        """Output: maxcolwidth will result in autowrapping longer cells."""
        table = [["hdr", "fold"], ["1", "very long data"]]
        expected = "\n".join(["  hdr  fold", "    1  very long", "       data"])
        result = tabulate(table, headers="firstrow", tableFmt="plain", maxColWidths=[10, 10])
        self.assertEqual(expected, result)

    def test_plainMaxcolwidthAutowrapsWithSep(self):
        """Output: maxcolwidth will result in autowrapping longer cells and separating line."""
        table = [
            ["hdr", "fold"],
            ["1", "very long data"],
            SEPARATING_LINE,
            ["2", "last line"],
        ]
        expected = "\n".join(["  hdr  fold", "    1  very long", "       data", "", "    2  last line"])
        result = tabulate(table, headers="firstrow", tableFmt="plain", maxColWidths=[10, 10])
        self.assertEqual(expected, result)

    def test_maxColWidthsingleValue(self):
        """Output: maxcolwidth can be specified as a single number that works for each column."""
        table = [
            ["hdr", "fold1", "fold2"],
            ["mini", "this is short", "this is a bit longer"],
        ]
        expected = "\n".join(
            [
                "hdr    fold1    fold2",
                "mini   this     this",
                "       is       is a",
                "       short    bit",
                "                longer",
            ]
        )
        result = tabulate(table, headers="firstrow", tableFmt="plain", maxColWidths=6)
        self.assertEqual(expected, result)

    def test_maxcolwidthPadTailingWidths(self):
        """Output: maxcolwidth, if only partly specified, pads tailing cols with None."""
        table = [
            ["hdr", "fold1", "fold2"],
            ["mini", "this is short", "this is a bit longer"],
        ]
        expected = "\n".join(
            [
                "hdr    fold1    fold2",
                "mini   this     this is a bit longer",
                "       is",
                "       short",
            ]
        )
        result = tabulate(table, headers="firstrow", tableFmt="plain", maxColWidths=[None, 6])
        self.assertEqual(expected, result)

    def test_maxcolwidthHonorDisableParsenum(self):
        """Output: Using maxcolwidth in conjunction with disable_parsenum is honored."""
        table = [
            ["first number", 123.456789, "123.456789"],
            ["second number", "987654321.123", "987654321.123"],
        ]
        expected = "\n".join(
            [
                "+--------+---------------+--------+",
                "| first  | 123.457       | 123.45 |",
                "| number |               | 6789   |",
                "+--------+---------------+--------+",
                "| second |   9.87654e+08 | 987654 |",
                "| number |               | 321.12 |",
                "|        |               | 3      |",
                "+--------+---------------+--------+",
            ]
        )
        # Grid makes showing the alignment difference a little easier
        result = tabulate(table, tableFmt="grid", maxColWidths=6, disableNumParse=[2])
        self.assertEqual(expected, result)

    def test_plainmaxHeaderColWidthsAutowraps(self):
        """Output: maxHeaderColWidths will result in autowrapping header cell."""
        table = [["hdr", "fold"], ["1", "very long data"]]
        expected = "\n".join(["  hdr  fo", "       ld", "    1  very long", "       data"])
        result = tabulate(
            table,
            headers="firstrow",
            tableFmt="plain",
            maxColWidths=[10, 10],
            maxHeaderColWidths=[None, 2],
        )
        self.assertEqual(expected, result)

    def test_simple(self):
        """Output: simple with headers."""
        expected = "\n".join(
            [
                "strings      numbers",
                "---------  ---------",
                "spam         41.9999",
                "eggs        451",
            ]
        )
        result = tabulate(self.testTable, self.testTableHeaders, tableFmt="simple")
        self.assertEqual(expected, result)

    def test_simpleWithSepLine(self):
        """Output: simple with headers and separating line."""
        expected = "\n".join(
            [
                "strings      numbers",
                "---------  ---------",
                "spam         41.9999",
                "---------  ---------",
                "eggs        451",
            ]
        )
        result = tabulate(self.testTableWithSepLine, self.testTableHeaders, tableFmt="simple")
        self.assertEqual(expected, result)

    def test_readmeExampleWithSep(self):
        table = [["Earth", 6371], ["Mars", 3390], SEPARATING_LINE, ["Moon", 1737]]
        expected = "\n".join(
            [
                "-----  ----",
                "Earth  6371",
                "Mars   3390",
                "-----  ----",
                "Moon   1737",
                "-----  ----",
            ]
        )
        result = tabulate(table, tableFmt="simple")
        self.assertEqual(expected, result)

    def test_simpleMultiline2(self):
        """Output: simple with multiline cells."""
        expected = "\n".join(
            [
                " key     value",
                "-----  ---------",
                " foo      bar",
                "spam   multiline",
                "         world",
            ]
        )
        table = [["key", "value"], ["foo", "bar"], ["spam", "multiline\nworld"]]
        result = tabulate(table, headers="firstrow", strAlign="center", tableFmt="simple")
        self.assertEqual(expected, result)

    def test_simpleMultiline2WithSepLine(self):
        """Output: simple with multiline cells."""
        expected = "\n".join(
            [
                " key     value",
                "-----  ---------",
                " foo      bar",
                "-----  ---------",
                "spam   multiline",
                "         world",
            ]
        )
        table = [
            ["key", "value"],
            ["foo", "bar"],
            SEPARATING_LINE,
            ["spam", "multiline\nworld"],
        ]
        result = tabulate(table, headers="firstrow", strAlign="center", tableFmt="simple")
        self.assertEqual(expected, result)

    def test_simpleHeaderless(self):
        """Output: simple without headers."""
        expected = "\n".join(["----  --------", "spam   41.9999", "eggs  451", "----  --------"])
        result = tabulate(self.testTable, tableFmt="simple")
        self.assertEqual(expected, result)

    def test_simpleHeaderlessWithSepLine(self):
        """Output: simple without headers."""
        expected = "\n".join(
            [
                "----  --------",
                "spam   41.9999",
                "----  --------",
                "eggs  451",
                "----  --------",
            ]
        )
        result = tabulate(self.testTableWithSepLine, tableFmt="simple")
        self.assertEqual(expected, result)

    def test_simpleMultilineHeaderless(self):
        """Output: simple with multiline cells without headers."""
        table = [["foo bar\nbaz\nbau", "hello"], ["", "multiline\nworld"]]
        expected = "\n".join(
            [
                "-------  ---------",
                "foo bar    hello",
                "  baz",
                "  bau",
                "         multiline",
                "           world",
                "-------  ---------",
            ]
        )
        result = tabulate(table, strAlign="center", tableFmt="simple")
        self.assertEqual(expected, result)

    def test_simpleMultiline(self):
        """Output: simple with multiline cells with headers."""
        table = [[2, "foo\nbar"]]
        headers = ("more\nspam \x1b[31meggs\x1b[0m", "more spam\n& eggs")
        expected = "\n".join(
            [
                "       more  more spam",
                "  spam \x1b[31meggs\x1b[0m  & eggs",
                "-----------  -----------",
                "          2  foo",
                "             bar",
            ]
        )
        result = tabulate(table, headers, tableFmt="simple")
        self.assertEqual(expected, result)

    def test_simpleMultilineWithLinks(self):
        """Output: simple with multiline cells with links and headers."""
        table = [[2, "foo\nbar"]]
        headers = (
            "more\nspam \x1b]8;;target\x1b\\eggs\x1b]8;;\x1b\\",
            "more spam\n& eggs",
        )
        expected = "\n".join(
            [
                "       more  more spam",
                "  spam \x1b]8;;target\x1b\\eggs\x1b]8;;\x1b\\  & eggs",
                "-----------  -----------",
                "          2  foo",
                "             bar",
            ]
        )
        result = tabulate(table, headers, tableFmt="simple")
        self.assertEqual(expected, result)

    def test_simpleMultilineWithEmptyCells(self):
        """Output: simple with multiline cells and empty cells with headers."""
        table = [
            ["hdr", "data", "fold"],
            ["1", "", ""],
            ["2", "very long data", "fold\nthis"],
        ]
        expected = "\n".join(
            [
                "  hdr  data            fold",
                "-----  --------------  ------",
                "    1",
                "    2  very long data  fold",
                "                       this",
            ]
        )
        result = tabulate(table, headers="firstrow", tableFmt="simple")
        self.assertEqual(expected, result)

    def test_simpleMultilineWithEmptyCellsHeaderless(self):
        """Output: simple with multiline cells and empty cells without headers."""
        table = [["0", "", ""], ["1", "", ""], ["2", "very long data", "fold\nthis"]]
        expected = "\n".join(
            [
                "-  --------------  ----",
                "0",
                "1",
                "2  very long data  fold",
                "                   this",
                "-  --------------  ----",
            ]
        )
        result = tabulate(table, tableFmt="simple")
        self.assertEqual(expected, result)

    def test_github(self):
        """Output: github with headers."""
        expected = "\n".join(
            [
                "| strings   |   numbers |",
                "|-----------|-----------|",
                "| spam      |   41.9999 |",
                "| eggs      |  451      |",
            ]
        )
        result = tabulate(self.testTable, self.testTableHeaders, tableFmt="github")
        self.assertEqual(expected, result)

    def test_grid(self):
        """Output: grid with headers."""
        expected = "\n".join(
            [
                "+-----------+-----------+",
                "| strings   |   numbers |",
                "+===========+===========+",
                "| spam      |   41.9999 |",
                "+-----------+-----------+",
                "| eggs      |  451      |",
                "+-----------+-----------+",
            ]
        )
        result = tabulate(self.testTable, self.testTableHeaders, tableFmt="grid")
        self.assertEqual(expected, result)

    def test_gridHeaderless(self):
        """Output: grid without headers."""
        expected = "\n".join(
            [
                "+------+----------+",
                "| spam |  41.9999 |",
                "+------+----------+",
                "| eggs | 451      |",
                "+------+----------+",
            ]
        )
        result = tabulate(self.testTable, tableFmt="grid")
        self.assertEqual(expected, result)

    def test_gridMultilineHeaderless(self):
        """Output: grid with multiline cells without headers."""
        table = [["foo bar\nbaz\nbau", "hello"], ["", "multiline\nworld"]]
        expected = "\n".join(
            [
                "+---------+-----------+",
                "| foo bar |   hello   |",
                "|   baz   |           |",
                "|   bau   |           |",
                "+---------+-----------+",
                "|         | multiline |",
                "|         |   world   |",
                "+---------+-----------+",
            ]
        )
        result = tabulate(table, strAlign="center", tableFmt="grid")
        self.assertEqual(expected, result)

    def test_gridMultiline(self):
        """Output: grid with multiline cells with headers."""
        table = [[2, "foo\nbar"]]
        headers = ("more\nspam \x1b[31meggs\x1b[0m", "more spam\n& eggs")
        expected = "\n".join(
            [
                "+-------------+-------------+",
                "|        more | more spam   |",
                "|   spam \x1b[31meggs\x1b[0m | & eggs      |",
                "+=============+=============+",
                "|           2 | foo         |",
                "|             | bar         |",
                "+-------------+-------------+",
            ]
        )
        result = tabulate(table, headers, tableFmt="grid")
        self.assertEqual(expected, result)

    def test_gridMultilineWithEmptyCells(self):
        """Output: grid with multiline cells and empty cells with headers."""
        table = [
            ["hdr", "data", "fold"],
            ["1", "", ""],
            ["2", "very long data", "fold\nthis"],
        ]
        expected = "\n".join(
            [
                "+-------+----------------+--------+",
                "|   hdr | data           | fold   |",
                "+=======+================+========+",
                "|     1 |                |        |",
                "+-------+----------------+--------+",
                "|     2 | very long data | fold   |",
                "|       |                | this   |",
                "+-------+----------------+--------+",
            ]
        )
        result = tabulate(table, headers="firstrow", tableFmt="grid")
        self.assertEqual(expected, result)

    def test_gridMultilineWithEmptyCellsHeaderless(self):
        """Output: grid with multiline cells and empty cells without headers."""
        table = [["0", "", ""], ["1", "", ""], ["2", "very long data", "fold\nthis"]]
        expected = "\n".join(
            [
                "+---+----------------+------+",
                "| 0 |                |      |",
                "+---+----------------+------+",
                "| 1 |                |      |",
                "+---+----------------+------+",
                "| 2 | very long data | fold |",
                "|   |                | this |",
                "+---+----------------+------+",
            ]
        )
        result = tabulate(table, tableFmt="grid")
        self.assertEqual(expected, result)

    def test_pretty(self):
        """Output: pretty with headers."""
        expected = "\n".join(
            [
                "+---------+---------+",
                "| strings | numbers |",
                "+---------+---------+",
                "|  spam   | 41.9999 |",
                "|  eggs   |  451.0  |",
                "+---------+---------+",
            ]
        )
        result = tabulate(self.testTable, self.testTableHeaders, tableFmt="pretty")
        self.assertEqual(expected, result)

    def test_prettyHeaderless(self):
        """Output: pretty without headers."""
        expected = "\n".join(
            [
                "+------+---------+",
                "| spam | 41.9999 |",
                "| eggs |  451.0  |",
                "+------+---------+",
            ]
        )
        result = tabulate(self.testTable, tableFmt="pretty")
        self.assertEqual(expected, result)

    def test_prettyMultilineHeaderless(self):
        """Output: pretty with multiline cells without headers."""
        table = [["foo bar\nbaz\nbau", "hello"], ["", "multiline\nworld"]]
        expected = "\n".join(
            [
                "+---------+-----------+",
                "| foo bar |   hello   |",
                "|   baz   |           |",
                "|   bau   |           |",
                "|         | multiline |",
                "|         |   world   |",
                "+---------+-----------+",
            ]
        )
        result = tabulate(table, tableFmt="pretty")
        self.assertEqual(expected, result)

    def test_prettyMultiline(self):
        """Output: pretty with multiline cells with headers."""
        table = [[2, "foo\nbar"]]
        headers = ("more\nspam \x1b[31meggs\x1b[0m", "more spam\n& eggs")
        expected = "\n".join(
            [
                "+-----------+-----------+",
                "|   more    | more spam |",
                "| spam \x1b[31meggs\x1b[0m |  & eggs   |",
                "+-----------+-----------+",
                "|     2     |    foo    |",
                "|           |    bar    |",
                "+-----------+-----------+",
            ]
        )
        result = tabulate(table, headers, tableFmt="pretty")
        self.assertEqual(expected, result)

    def test_prettyMultilineWithLinks(self):
        """Output: pretty with multiline cells with headers."""
        table = [[2, "foo\nbar"]]
        headers = (
            "more\nspam \x1b]8;;target\x1b\\eggs\x1b]8;;\x1b\\",
            "more spam\n& eggs",
        )
        expected = "\n".join(
            [
                "+-----------+-----------+",
                "|   more    | more spam |",
                "| spam \x1b]8;;target\x1b\\eggs\x1b]8;;\x1b\\ |  & eggs   |",
                "+-----------+-----------+",
                "|     2     |    foo    |",
                "|           |    bar    |",
                "+-----------+-----------+",
            ]
        )
        result = tabulate(table, headers, tableFmt="pretty")
        self.assertEqual(expected, result)

    def test_prettyMultilineWithEmptyCells(self):
        """Output: pretty with multiline cells and empty cells with headers."""
        table = [
            ["hdr", "data", "fold"],
            ["1", "", ""],
            ["2", "very long data", "fold\nthis"],
        ]
        expected = "\n".join(
            [
                "+-----+----------------+------+",
                "| hdr |      data      | fold |",
                "+-----+----------------+------+",
                "|  1  |                |      |",
                "|  2  | very long data | fold |",
                "|     |                | this |",
                "+-----+----------------+------+",
            ]
        )
        result = tabulate(table, headers="firstrow", tableFmt="pretty")
        self.assertEqual(expected, result)

    def test_prettyMultilineWithEmptyCellsHeaderless(self):
        """Output: pretty with multiline cells and empty cells without headers."""
        table = [["0", "", ""], ["1", "", ""], ["2", "very long data", "fold\nthis"]]
        expected = "\n".join(
            [
                "+---+----------------+------+",
                "| 0 |                |      |",
                "| 1 |                |      |",
                "| 2 | very long data | fold |",
                "|   |                | this |",
                "+---+----------------+------+",
            ]
        )
        result = tabulate(table, tableFmt="pretty")
        self.assertEqual(expected, result)

    def test_rst(self):
        """Output: rst with headers."""
        expected = "\n".join(
            [
                "=========  =========",
                "strings      numbers",
                "=========  =========",
                "spam         41.9999",
                "eggs        451",
                "=========  =========",
            ]
        )
        result = tabulate(self.testTable, self.testTableHeaders, tableFmt="rst")
        self.assertEqual(expected, result)

    def test_rstWithEmptyValuesInFirstColumn(self):
        """Output: rst with dots in first column."""
        test_headers = ["", "what"]
        test_data = [("", "spam"), ("", "eggs")]
        expected = "\n".join(
            [
                "====  ======",
                "..    what",
                "====  ======",
                "..    spam",
                "..    eggs",
                "====  ======",
            ]
        )
        result = tabulate(test_data, test_headers, tableFmt="rst")
        self.assertEqual(expected, result)

    def test_rstHeaderless(self):
        """Output: rst without headers."""
        expected = "\n".join(["====  ========", "spam   41.9999", "eggs  451", "====  ========"])
        result = tabulate(self.testTable, tableFmt="rst")
        self.assertEqual(expected, result)

    def test_rstMultiline(self):
        """Output: rst with multiline cells with headers."""
        table = [[2, "foo\nbar"]]
        headers = ("more\nspam \x1b[31meggs\x1b[0m", "more spam\n& eggs")
        expected = "\n".join(
            [
                "===========  ===========",
                "       more  more spam",
                "  spam \x1b[31meggs\x1b[0m  & eggs",
                "===========  ===========",
                "          2  foo",
                "             bar",
                "===========  ===========",
            ]
        )
        result = tabulate(table, headers, tableFmt="rst")
        self.assertEqual(expected, result)

    def test_rstMultilineWithLinks(self):
        """Output: rst with multiline cells with headers."""
        table = [[2, "foo\nbar"]]
        headers = (
            "more\nspam \x1b]8;;target\x1b\\eggs\x1b]8;;\x1b\\",
            "more spam\n& eggs",
        )
        expected = "\n".join(
            [
                "===========  ===========",
                "       more  more spam",
                "  spam \x1b]8;;target\x1b\\eggs\x1b]8;;\x1b\\  & eggs",
                "===========  ===========",
                "          2  foo",
                "             bar",
                "===========  ===========",
            ]
        )
        result = tabulate(table, headers, tableFmt="rst")
        self.assertEqual(expected, result)

    def test_rstMultilineWithEmptyCells(self):
        """Output: rst with multiline cells and empty cells with headers."""
        table = [
            ["hdr", "data", "fold"],
            ["1", "", ""],
            ["2", "very long data", "fold\nthis"],
        ]
        expected = "\n".join(
            [
                "=====  ==============  ======",
                "  hdr  data            fold",
                "=====  ==============  ======",
                "    1",
                "    2  very long data  fold",
                "                       this",
                "=====  ==============  ======",
            ]
        )
        result = tabulate(table, headers="firstrow", tableFmt="rst")
        self.assertEqual(expected, result)

    def test_rstMultilineWithEmptyCellsHeaderless(self):
        """Output: rst with multiline cells and empty cells without headers."""
        table = [["0", "", ""], ["1", "", ""], ["2", "very long data", "fold\nthis"]]
        expected = "\n".join(
            [
                "=  ==============  ====",
                "0",
                "1",
                "2  very long data  fold",
                "                   this",
                "=  ==============  ====",
            ]
        )
        result = tabulate(table, tableFmt="rst")
        self.assertEqual(expected, result)

    def test_noData(self):
        """Output: table with no data."""
        expected = "\n".join(["strings    numbers", "---------  ---------"])
        result = tabulate(None, self.testTableHeaders, tableFmt="simple")
        self.assertEqual(expected, result)

    def test_emptyData(self):
        """Output: table with empty data."""
        expected = "\n".join(["strings    numbers", "---------  ---------"])
        result = tabulate([], self.testTableHeaders, tableFmt="simple")
        self.assertEqual(expected, result)

    def test_noDataWithoutHeaders(self):
        """Output: table with no data and no headers."""
        expected = ""
        result = tabulate(None, tableFmt="simple")
        self.assertEqual(expected, result)

    def test_emptyDataWithoutHeaders(self):
        """Output: table with empty data and no headers."""
        expected = ""
        result = tabulate([], tableFmt="simple")
        self.assertEqual(expected, result)

    def test_intFmt(self):
        """Output: integer format."""
        result = tabulate([[10000], [10]], intFmt=",", tableFmt="plain")
        expected = "10,000\n    10"
        self.assertEqual(expected, result)

    def test_emptyDataWithHeaders(self):
        """Output: table with empty data and headers as firstrow."""
        expected = ""
        result = tabulate([], headers="firstrow")
        self.assertEqual(expected, result)

    def test_floatFmt(self):
        """Output: floating point format."""
        result = tabulate([["1.23456789"], [1.0]], floatFmt=".3f", tableFmt="plain")
        expected = "1.235\n1.000"
        self.assertEqual(expected, result)

    def test_floatFmtMulti(self):
        """Output: floating point format different for each column."""
        result = tabulate([[0.12345, 0.12345, 0.12345]], floatFmt=(".1f", ".3f"), tableFmt="plain")
        expected = "0.1  0.123  0.12345"
        self.assertEqual(expected, result)

    def test_colAlignMulti(self):
        """Output: string columns with custom colAlign."""
        result = tabulate([["one", "two"], ["three", "four"]], colAlign=("right",), tableFmt="plain")
        expected = "  one  two\nthree  four"
        self.assertEqual(expected, result)

    def test_colAlignMultiWithSepLine(self):
        """Output: string columns with custom colAlign."""
        result = tabulate(
            [["one", "two"], SEPARATING_LINE, ["three", "four"]],
            colAlign=("right",),
            tableFmt="plain",
        )
        expected = "  one  two\n\nthree  four"
        self.assertEqual(expected, result)

    def test_columnGlobalAndSpecificAlignment(self):
        """Test `colGlobalAlign` and `"global"` parameter for `colAlign`."""
        table = [[1, 2, 3, 4], [111, 222, 333, 444]]
        colGlobalAlign = "center"
        colAlign = ("global", "left", "right")
        result = tabulate(table, colGlobalAlign=colGlobalAlign, colAlign=colAlign)
        expected = "\n".join(
            [
                "---  ---  ---  ---",
                " 1   2      3   4",
                "111  222  333  444",
                "---  ---  ---  ---",
            ]
        )
        self.assertEqual(expected, result)

    def test_headersGlobalAndSpecificAlignment(self):
        """Test `headersGlobalAlign` and `headersAlign`."""
        table = [[1, 2, 3, 4, 5, 6], [111, 222, 333, 444, 555, 666]]
        colGlobalAlign = "center"
        colAlign = ("left",)
        headers = ["h", "e", "a", "d", "e", "r"]
        headersGlobalAlign = "right"
        headersAlign = ("same", "same", "left", "global", "center")
        result = tabulate(
            table,
            headers=headers,
            colGlobalAlign=colGlobalAlign,
            colAlign=colAlign,
            headersGlobalAlign=headersGlobalAlign,
            headersAlign=headersAlign,
        )
        expected = "\n".join(
            [
                "h     e   a      d   e     r",
                "---  ---  ---  ---  ---  ---",
                "1     2    3    4    5    6",
                "111  222  333  444  555  666",
            ]
        )
        self.assertEqual(expected, result)

    def test_colAlignOrheadersAlignTooLong(self):
        """Test `colAlign` and `headersAlign` too long."""
        table = [[1, 2], [111, 222]]
        colAlign = ("global", "left", "center")
        headers = ["h"]
        headersAlign = ("center", "right", "same")
        result = tabulate(table, headers=headers, colAlign=colAlign, headersAlign=headersAlign)
        expected = "\n".join(["      h", "---  ---", "  1  2", "111  222"])
        self.assertEqual(expected, result)

    def test_floatConversions(self):
        """Output: float format parsed."""
        test_headers = [
            "str",
            "bad_float",
            "just_float",
            "with_inf",
            "with_nan",
            "neg_inf",
        ]
        testTable = [
            ["spam", 41.9999, "123.345", "12.2", "nan", "0.123123"],
            ["eggs", "451.0", 66.2222, "inf", 123.1234, "-inf"],
            ["asd", "437e6548", 1.234e2, float("inf"), float("nan"), 0.22e23],
        ]
        result = tabulate(testTable, test_headers, tableFmt="grid")
        expected = "\n".join(
            [
                "+-------+-------------+--------------+------------+------------+-------------+",
                "| str   | bad_float   |   just_float |   with_inf |   with_nan |     neg_inf |",
                "+=======+=============+==============+============+============+=============+",
                "| spam  | 41.9999     |     123.345  |       12.2 |    nan     |    0.123123 |",
                "+-------+-------------+--------------+------------+------------+-------------+",
                "| eggs  | 451.0       |      66.2222 |      inf   |    123.123 | -inf        |",
                "+-------+-------------+--------------+------------+------------+-------------+",
                "| asd   | 437e6548    |     123.4    |      inf   |    nan     |    2.2e+22  |",
                "+-------+-------------+--------------+------------+------------+-------------+",
            ]
        )
        self.assertEqual(expected, result)

    def test_missingVal(self):
        """Output: substitution of missing values."""
        result = tabulate([["Alice", 10], ["Bob", None]], missingVal="n/a", tableFmt="plain")
        expected = "Alice   10\nBob    n/a"
        self.assertEqual(expected, result)

    def test_missingValMulti(self):
        """Output: substitution of missing values with different values per column."""
        result = tabulate(
            [["Alice", "Bob", "Charlie"], [None, None, None]],
            missingVal=("n/a", "?"),
            tableFmt="plain",
        )
        expected = "Alice  Bob  Charlie\nn/a    ?"
        self.assertEqual(expected, result)

    def test_columnAlignment(self):
        """Output: custom alignment for text and numbers."""
        expected = "\n".join(["-----  ---", "Alice   1", "  Bob  333", "-----  ---"])
        result = tabulate([["Alice", 1], ["Bob", 333]], strAlign="right", numAlign="center")
        self.assertEqual(expected, result)

    def test_dictLikeWithIndex(self):
        """Output: a table with a running index."""
        dd = {"b": range(101, 104)}
        expected = "\n".join(["      b", "--  ---", " 0  101", " 1  102", " 2  103"])
        result = tabulate(dd, "keys", showIndex=True)
        self.assertEqual(expected, result)

    def test_listOfListsWithIndex(self):
        """Output: a table with a running index."""
        dd = zip(*[range(3), range(101, 104)])
        # keys' order (hence columns' order) is not deterministic in Python 3
        # => we have to consider both possible results as valid
        expected = "\n".join(
            [
                "      a    b",
                "--  ---  ---",
                " 0    0  101",
                " 1    1  102",
                " 2    2  103",
            ]
        )
        result = tabulate(dd, headers=["a", "b"], showIndex=True)
        self.assertEqual(expected, result)

    def test_listOfListsWithIndexWithSepLine(self):
        """Output: a table with a running index."""
        dd = [(0, 101), SEPARATING_LINE, (1, 102), (2, 103)]
        # keys' order (hence columns' order) is not deterministic in Python 3
        # => we have to consider both possible results as valid
        expected = "\n".join(
            [
                "      a    b",
                "--  ---  ---",
                " 0    0  101",
                "--  ---  ---",
                " 1    1  102",
                " 2    2  103",
            ]
        )
        result = tabulate(dd, headers=["a", "b"], showIndex=True)
        self.assertEqual(expected, result)

    def test_listOfListsWithSuppliedIndex(self):
        """Output: a table with a supplied index."""
        dd = zip(*[list(range(3)), list(range(101, 104))])
        expected = "\n".join(
            [
                "      a    b",
                "--  ---  ---",
                " 1    0  101",
                " 2    1  102",
                " 3    2  103",
            ]
        )
        result = tabulate(dd, headers=["a", "b"], showIndex=[1, 2, 3])
        self.assertEqual(expected, result)
        # the index must be as long as the number of rows
        with self.assertRaises(ValueError):
            tabulate(dd, headers=["a", "b"], showIndex=[1, 2])

    def test_listOfListsWithIndexFirstrow(self):
        """Output: a table with a running index and header='firstrow'."""
        dd = zip(*[["a"] + list(range(3)), ["b"] + list(range(101, 104))])
        expected = "\n".join(
            [
                "      a    b",
                "--  ---  ---",
                " 0    0  101",
                " 1    1  102",
                " 2    2  103",
            ]
        )
        result = tabulate(dd, headers="firstrow", showIndex=True)
        self.assertEqual(expected, result)
        # the index must be as long as the number of rows
        with self.assertRaises(ValueError):
            tabulate(dd, headers="firstrow", showIndex=[1, 2])

    def test_disableNumParseDefault(self):
        """Output: Default table output with number parsing and alignment."""
        expected = "\n".join(
            [
                "strings      numbers",
                "---------  ---------",
                "spam         41.9999",
                "eggs        451",
            ]
        )
        result = tabulate(self.testTable, self.testTableHeaders)
        self.assertEqual(expected, result)
        result = tabulate(self.testTable, self.testTableHeaders, disableNumParse=False)
        self.assertEqual(expected, result)

    def test_disableNumParseTrue(self):
        """Output: Default table output, but without number parsing and alignment."""
        expected = "\n".join(
            [
                "strings    numbers",
                "---------  ---------",
                "spam       41.9999",
                "eggs       451.0",
            ]
        )
        result = tabulate(self.testTable, self.testTableHeaders, disableNumParse=True)
        self.assertEqual(expected, result)

    def test_disableNumParseList(self):
        """Output: Default table output, but with number parsing selectively disabled."""
        tableHeaders = ["h1", "h2", "h3"]
        testTable = [["foo", "bar", "42992e1"]]
        expected = "\n".join(["h1    h2    h3", "----  ----  -------", "foo   bar   42992e1"])
        result = tabulate(testTable, tableHeaders, disableNumParse=[2])
        self.assertEqual(expected, result)

        expected = "\n".join(["h1    h2        h3", "----  ----  ------", "foo   bar   429920"])
        result = tabulate(testTable, tableHeaders, disableNumParse=[0, 1])
        self.assertEqual(expected, result)
