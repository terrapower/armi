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
from collections import namedtuple
from collections import OrderedDict
from collections import UserDict
from datetime import datetime
from textwrap import TextWrapper as OTW
import unittest

import numpy as np

from armi.utils.tabulate import _alignColumn, _alignCellVeritically, _multilineWidth
from armi.utils.tabulate import _CustomTextWrap as CTW
from armi.utils.tabulate import SEPARATING_LINE
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

    def test_iterableOfIterablesFirstrow(self):
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
        expected = "\n".join(
            ["0    1      2", "---  ---  ---", "a    one    1", "b    two"]
        )
        result = tabulate(ll, headers="keys")
        self.assertEqual(expected, result)

    def test_dictLike(self):
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
        expected = "\n".join(
            ["  1    8    27", "---  ---  ----", " 64  125   216", "343  512   729"]
        )
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

    def test_numpyRecordArrayKeys(self):
        """Input: a 2D NumPy record array with column names as headers."""
        na = np.asarray(
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

    def test_numpyRecordArrayHeaders(self):
        """Input: a 2D NumPy record array with user-supplied headers."""
        na = np.asarray(
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

    def test_listOf_namedtuples(self):
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
        expected = "\n".join(
            ["  foo    bar", "-----  -----", "    1      2", "    3      4"]
        )
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
        expected1 = "\n".join(
            ["  foo    bar", "-----  -----", "    1      2", "    3      4"]
        )
        expected2 = "\n".join(
            ["  bar    foo", "-----  -----", "    2      1", "    4      3"]
        )
        result = tabulate(lod, headers="keys")
        self.assertIn(result, [expected1, expected2])

    def test_listOfUserdictsKeys(self):
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
        expected1 = "\n".join(
            ["  FOO    BAR    baz", "-----  -----  -----", "    3      4      5"]
        )
        expected2 = "\n".join(
            ["  BAR    FOO    baz", "-----  -----  -----", "    4      3      5"]
        )
        result = tabulate(lod, headers="firstrow")
        self.assertIn(result, [expected1, expected2])

    def test_listOfDictsWithDictOfHeaders(self):
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

    def test_listOfDicts_with_list_of_headers(self):
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


class TestTabulateInternal(unittest.TestCase):
    def test_multilineWidth(self):
        """Internal: _multilineWidth()."""
        multilineString = "\n".join(["foo", "barbaz", "spam"])
        self.assertEqual(_multilineWidth(multilineString), 6)
        onelineString = "12345"
        self.assertEqual(_multilineWidth(onelineString), len(onelineString))

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

    def test_alignColumnDecimalWithIncorrectThousandSeparators(self):
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

    def test_alignCellVeriticallyTopSingleTextMultiplePad(self):
        """Internal: Align single cell text to top."""
        result = _alignCellVeritically(["one line"], 3, 8, "top")
        expected = ["one line", "        ", "        "]
        self.assertEqual(expected, result)

    def test_alignCellVeriticallyCenterSingleTextMultiplePad(self):
        """Internal: Align single cell text to center."""
        result = _alignCellVeritically(["one line"], 3, 8, "center")
        expected = ["        ", "one line", "        "]
        self.assertEqual(expected, result)

    def test_alignCellVeriticallyBottomSingleTextMultiplePad(self):
        """Internal: Align single cell text to bottom."""
        result = _alignCellVeritically(["one line"], 3, 8, "bottom")
        expected = ["        ", "        ", "one line"]
        self.assertEqual(expected, result)

    def test_alignCellVeriticallyTopMultiTextMultiplePad(self):
        """Internal: Align multiline celltext text to top."""
        text = ["just", "one ", "cell"]
        result = _alignCellVeritically(text, 6, 4, "top")
        expected = ["just", "one ", "cell", "    ", "    ", "    "]
        self.assertEqual(expected, result)

    def test_alignCellVeriticallyCenterMultiTextMultiplePad(self):
        """Internal: Align multiline celltext text to center."""
        text = ["just", "one ", "cell"]
        result = _alignCellVeritically(text, 6, 4, "center")

        # Even number of rows, can't perfectly center, but we pad less
        # at top when required to do make a judgement
        expected = ["    ", "just", "one ", "cell", "    ", "    "]
        self.assertEqual(expected, result)

    def test_alignCellVeriticallyBottomMultiTextMultiplePad(self):
        """Internal: Align multiline celltext text to bottom."""
        text = ["just", "one ", "cell"]
        result = _alignCellVeritically(text, 6, 4, "bottom")
        expected = ["    ", "    ", "    ", "just", "one ", "cell"]
        self.assertEqual(expected, result)


# TODO: JOHN: reformat data
# _test_table shows
#  - coercion of a string to a number,
#  - left alignment of text,
#  - decimal point alignment of numbers
_test_table = [["spam", 41.9999], ["eggs", "451.0"]]
_test_table_with_sep_line = [["spam", 41.9999], SEPARATING_LINE, ["eggs", "451.0"]]
_test_table_headers = ["strings", "numbers"]


class TestTabulateOutput(unittest.TestCase):
    def test_plain(self):
        """Output: plain with headers."""
        expected = "\n".join(
            ["strings      numbers", "spam         41.9999", "eggs        451"]
        )
        result = tabulate(_test_table, _test_table_headers, tablefmt="plain")
        self.assertEqual(expected, result)

    def test_plainHeaderless(self):
        """Output: plain without headers."""
        expected = "\n".join(["spam   41.9999", "eggs  451"])
        result = tabulate(_test_table, tablefmt="plain")
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
        result = tabulate(table, stralign="center", tablefmt="plain")
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
        result = tabulate(table, headers, tablefmt="plain")
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
        result = tabulate(table, headers, tablefmt="plain")
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
        result = tabulate(table, headers="firstrow", tablefmt="plain")
        self.assertEqual(expected, result)

    def test_plainMultilineWithEmptyCellsHeaderless(self):
        """Output: plain with multiline cells and empty cells without headers."""
        table = [["0", "", ""], ["1", "", ""], ["2", "very long data", "fold\nthis"]]
        expected = "\n".join(
            ["0", "1", "2  very long data  fold", "                   this"]
        )
        result = tabulate(table, tablefmt="plain")
        self.assertEqual(expected, result)

    def test_plainMaxcolwidthAutowraps(self):
        """Output: maxcolwidth will result in autowrapping longer cells."""
        table = [["hdr", "fold"], ["1", "very long data"]]
        expected = "\n".join(["  hdr  fold", "    1  very long", "       data"])
        result = tabulate(
            table, headers="firstrow", tablefmt="plain", maxcolwidths=[10, 10]
        )
        self.assertEqual(expected, result)

    def test_plainMaxcolwidthAutowrapsWithSep(self):
        """Output: maxcolwidth will result in autowrapping longer cells and separating line."""
        table = [
            ["hdr", "fold"],
            ["1", "very long data"],
            SEPARATING_LINE,
            ["2", "last line"],
        ]
        expected = "\n".join(
            ["  hdr  fold", "    1  very long", "       data", "", "    2  last line"]
        )
        result = tabulate(
            table, headers="firstrow", tablefmt="plain", maxcolwidths=[10, 10]
        )
        self.assertEqual(expected, result)

    def test_maxcolwidthSingleValue(self):
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
        result = tabulate(table, headers="firstrow", tablefmt="plain", maxcolwidths=6)
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
        result = tabulate(
            table, headers="firstrow", tablefmt="plain", maxcolwidths=[None, 6]
        )
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
        result = tabulate(table, tablefmt="grid", maxcolwidths=6, disableNumparse=[2])
        self.assertEqual(expected, result)

    def test_plainMaxheadercolwidthsAutowraps(self):
        """Output: maxheadercolwidths will result in autowrapping header cell."""
        table = [["hdr", "fold"], ["1", "very long data"]]
        expected = "\n".join(
            ["  hdr  fo", "       ld", "    1  very long", "       data"]
        )
        result = tabulate(
            table,
            headers="firstrow",
            tablefmt="plain",
            maxcolwidths=[10, 10],
            maxheadercolwidths=[None, 2],
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
        result = tabulate(_test_table, _test_table_headers, tablefmt="simple")
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
        result = tabulate(
            _test_table_with_sep_line, _test_table_headers, tablefmt="simple"
        )
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
        result = tabulate(table, tablefmt="simple")
        self.assertEqual(expected, result)

    def testSimpleMultiline2(self):
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
        result = tabulate(
            table, headers="firstrow", stralign="center", tablefmt="simple"
        )
        self.assertEqual(expected, result)

    def testSimpleMultiline2WithSepLine(self):
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
        result = tabulate(
            table, headers="firstrow", stralign="center", tablefmt="simple"
        )
        self.assertEqual(expected, result)

    def test_simpleHeaderless(self):
        """Output: simple without headers."""
        expected = "\n".join(
            ["----  --------", "spam   41.9999", "eggs  451", "----  --------"]
        )
        result = tabulate(_test_table, tablefmt="simple")
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
        result = tabulate(_test_table_with_sep_line, tablefmt="simple")
        self.assertEqual(expected, result)

    def testSimpleMultilineHeaderless(self):
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
        result = tabulate(table, stralign="center", tablefmt="simple")
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
        result = tabulate(table, headers, tablefmt="simple")
        self.assertEqual(expected, result)

    def testSimpleMultilineWithLinks(self):
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
        result = tabulate(table, headers, tablefmt="simple")
        self.assertEqual(expected, result)

    def testSimpleMultilineWithEmptyCells(self):
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
        result = tabulate(table, headers="firstrow", tablefmt="simple")
        self.assertEqual(expected, result)

    def testSimpleMultilineWithEmptyCellsHeaderless(self):
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
        result = tabulate(table, tablefmt="simple")
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
        result = tabulate(_test_table, _test_table_headers, tablefmt="github")
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
        result = tabulate(_test_table, _test_table_headers, tablefmt="grid")
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
        result = tabulate(_test_table, tablefmt="grid")
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
        result = tabulate(table, stralign="center", tablefmt="grid")
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
        result = tabulate(table, headers, tablefmt="grid")
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
        result = tabulate(table, headers="firstrow", tablefmt="grid")
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
        result = tabulate(table, tablefmt="grid")
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
        result = tabulate(_test_table, _test_table_headers, tablefmt="pretty")
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
        result = tabulate(_test_table, tablefmt="pretty")
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
        result = tabulate(table, tablefmt="pretty")
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
        result = tabulate(table, headers, tablefmt="pretty")
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
        result = tabulate(table, headers, tablefmt="pretty")
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
        result = tabulate(table, headers="firstrow", tablefmt="pretty")
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
        result = tabulate(table, tablefmt="pretty")
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
        result = tabulate(_test_table, _test_table_headers, tablefmt="rst")
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
        result = tabulate(test_data, test_headers, tablefmt="rst")
        self.assertEqual(expected, result)

    def test_rstHeaderless(self):
        """Output: rst without headers."""
        expected = "\n".join(
            ["====  ========", "spam   41.9999", "eggs  451", "====  ========"]
        )
        result = tabulate(_test_table, tablefmt="rst")
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
        result = tabulate(table, headers, tablefmt="rst")
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
        result = tabulate(table, headers, tablefmt="rst")
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
        result = tabulate(table, headers="firstrow", tablefmt="rst")
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
        result = tabulate(table, tablefmt="rst")
        self.assertEqual(expected, result)

    def test_noData(self):
        """Output: table with no data."""
        expected = "\n".join(["strings    numbers", "---------  ---------"])
        result = tabulate(None, _test_table_headers, tablefmt="simple")
        self.assertEqual(expected, result)

    def test_emptyData(self):
        """Output: table with empty data."""
        expected = "\n".join(["strings    numbers", "---------  ---------"])
        result = tabulate([], _test_table_headers, tablefmt="simple")
        self.assertEqual(expected, result)

    def test_noDataWithoutHeaders(self):
        """Output: table with no data and no headers."""
        expected = ""
        result = tabulate(None, tablefmt="simple")
        self.assertEqual(expected, result)

    def test_emptyDataWithoutHeaders(self):
        """Output: table with empty data and no headers."""
        expected = ""
        result = tabulate([], tablefmt="simple")
        self.assertEqual(expected, result)

    def test_intfmt(self):
        """Output: integer format."""
        result = tabulate([[10000], [10]], intfmt=",", tablefmt="plain")
        expected = "10,000\n    10"
        self.assertEqual(expected, result)

    def test_emptyDataWithHeaders(self):
        """Output: table with empty data and headers as firstrow."""
        expected = ""
        result = tabulate([], headers="firstrow")
        self.assertEqual(expected, result)

    def test_floatfmt(self):
        """Output: floating point format."""
        result = tabulate([["1.23456789"], [1.0]], floatfmt=".3f", tablefmt="plain")
        expected = "1.235\n1.000"
        self.assertEqual(expected, result)

    def test_floatfmtMulti(self):
        """Output: floating point format different for each column."""
        result = tabulate(
            [[0.12345, 0.12345, 0.12345]], floatfmt=(".1f", ".3f"), tablefmt="plain"
        )
        expected = "0.1  0.123  0.12345"
        self.assertEqual(expected, result)

    def test_colalignMulti(self):
        """Output: string columns with custom colalign."""
        result = tabulate(
            [["one", "two"], ["three", "four"]], colalign=("right",), tablefmt="plain"
        )
        expected = "  one  two\nthree  four"
        self.assertEqual(expected, result)

    def test_colalignMultiWithSepLine(self):
        """Output: string columns with custom colalign."""
        result = tabulate(
            [["one", "two"], SEPARATING_LINE, ["three", "four"]],
            colalign=("right",),
            tablefmt="plain",
        )
        expected = "  one  two\n\nthree  four"
        self.assertEqual(expected, result)

    def test_columnGlobalAndSpecificAlignment(self):
        """Test `colglobalalign` and `"global"` parameter for `colalign`."""
        table = [[1, 2, 3, 4], [111, 222, 333, 444]]
        colglobalalign = "center"
        colalign = ("global", "left", "right")
        result = tabulate(table, colglobalalign=colglobalalign, colalign=colalign)
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
        """Test `headersglobalalign` and `headersalign`."""
        table = [[1, 2, 3, 4, 5, 6], [111, 222, 333, 444, 555, 666]]
        colglobalalign = "center"
        colalign = ("left",)
        headers = ["h", "e", "a", "d", "e", "r"]
        headersglobalalign = "right"
        headersalign = ("same", "same", "left", "global", "center")
        result = tabulate(
            table,
            headers=headers,
            colglobalalign=colglobalalign,
            colalign=colalign,
            headersglobalalign=headersglobalalign,
            headersalign=headersalign,
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

    def test_colalignOrHeadersalignTooLong(self):
        """Test `colalign` and `headersalign` too long."""
        table = [[1, 2], [111, 222]]
        colalign = ("global", "left", "center")
        headers = ["h"]
        headersalign = ("center", "right", "same")
        result = tabulate(
            table, headers=headers, colalign=colalign, headersalign=headersalign
        )
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
        test_table = [
            ["spam", 41.9999, "123.345", "12.2", "nan", "0.123123"],
            ["eggs", "451.0", 66.2222, "inf", 123.1234, "-inf"],
            ["asd", "437e6548", 1.234e2, float("inf"), float("nan"), 0.22e23],
        ]
        result = tabulate(test_table, test_headers, tablefmt="grid")
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

    def test_missingval(self):
        """Output: substitution of missing values."""
        result = tabulate(
            [["Alice", 10], ["Bob", None]], missingval="n/a", tablefmt="plain"
        )
        expected = "Alice   10\nBob    n/a"
        self.assertEqual(expected, result)

    def test_missingvalMulti(self):
        """Output: substitution of missing values with different values per column."""
        result = tabulate(
            [["Alice", "Bob", "Charlie"], [None, None, None]],
            missingval=("n/a", "?"),
            tablefmt="plain",
        )
        expected = "Alice  Bob  Charlie\nn/a    ?"
        self.assertEqual(expected, result)

    def test_columnAlignment(self):
        """Output: custom alignment for text and numbers."""
        expected = "\n".join(["-----  ---", "Alice   1", "  Bob  333", "-----  ---"])
        result = tabulate(
            [["Alice", 1], ["Bob", 333]], stralign="right", numalign="center"
        )
        self.assertEqual(expected, result)

    def test_dictLikeWithIndex(self):
        """Output: a table with a running index."""
        dd = {"b": range(101, 104)}
        expected = "\n".join(["      b", "--  ---", " 0  101", " 1  102", " 2  103"])
        result = tabulate(dd, "keys", showindex=True)
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
        result = tabulate(dd, headers=["a", "b"], showindex=True)
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
        result = tabulate(dd, headers=["a", "b"], showindex=True)
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
        result = tabulate(dd, headers=["a", "b"], showindex=[1, 2, 3])
        self.assertEqual(expected, result)
        # the index must be as long as the number of rows
        with self.assertRaises(ValueError):
            tabulate(dd, headers=["a", "b"], showindex=[1, 2])

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
        result = tabulate(dd, headers="firstrow", showindex=True)
        self.assertEqual(expected, result)
        # the index must be as long as the number of rows
        with self.assertRaises(ValueError):
            tabulate(dd, headers="firstrow", showindex=[1, 2])

    def test_disableNumparseDefault(self):
        """Output: Default table output with number parsing and alignment."""
        expected = "\n".join(
            [
                "strings      numbers",
                "---------  ---------",
                "spam         41.9999",
                "eggs        451",
            ]
        )
        result = tabulate(_test_table, _test_table_headers)
        self.assertEqual(expected, result)
        result = tabulate(_test_table, _test_table_headers, disableNumparse=False)
        self.assertEqual(expected, result)

    def test_disableNumparseTrue(self):
        """Output: Default table output, but without number parsing and alignment."""
        expected = "\n".join(
            [
                "strings    numbers",
                "---------  ---------",
                "spam       41.9999",
                "eggs       451.0",
            ]
        )
        result = tabulate(_test_table, _test_table_headers, disableNumparse=True)
        self.assertEqual(expected, result)

    def test_disableNumparseList(self):
        """Output: Default table output, but with number parsing selectively disabled."""
        table_headers = ["h1", "h2", "h3"]
        test_table = [["foo", "bar", "42992e1"]]
        expected = "\n".join(
            ["h1    h2    h3", "----  ----  -------", "foo   bar   42992e1"]
        )
        result = tabulate(test_table, table_headers, disableNumparse=[2])
        self.assertEqual(expected, result)

        expected = "\n".join(
            ["h1    h2        h3", "----  ----  ------", "foo   bar   429920"]
        )
        result = tabulate(test_table, table_headers, disableNumparse=[0, 1])
        self.assertEqual(expected, result)


class TestTabulateTextWrapper(unittest.TestCase):
    def test_wrapMultiwordNonWide(self):
        """TextWrapper: non-wide character regression tests."""
        data = "this is a test string for regression splitting"
        for width in range(1, len(data)):
            orig = OTW(width=width)
            cust = CTW(width=width)

            self.assertEqual(orig.wrap(data), cust.wrap(data))

    def test_wrapMultiwordNonWideWithHypens(self):
        """TextWrapper: non-wide character regression tests that contain hyphens."""
        data = "how should-we-split-this non-sense string that-has-lots-of-hypens"
        for width in range(1, len(data)):
            orig = OTW(width=width)
            cust = CTW(width=width)

            self.assertEqual(orig.wrap(data), cust.wrap(data))

    def test_wrapLongwordNonWide(self):
        """TextWrapper: Some non-wide character regression tests."""
        data = "ThisIsASingleReallyLongWordThatWeNeedToSplit"
        for width in range(1, len(data)):
            orig = OTW(width=width)
            cust = CTW(width=width)

            self.assertEqual(orig.wrap(data), cust.wrap(data))

    def test_wrapDatetime(self):
        """TextWrapper: Show that datetimes can be wrapped without crashing."""
        data = [
            ["First Entry", datetime(2020, 1, 1, 5, 6, 7)],
            ["Second Entry", datetime(2021, 2, 2, 0, 0, 0)],
        ]
        headers = ["Title", "When"]
        result = tabulate(data, headers=headers, tablefmt="grid", maxcolwidths=[7, 5])

        expected = [
            "+---------+--------+",
            "| Title   | When   |",
            "+=========+========+",
            "| First   | 2020-  |",
            "| Entry   | 01-01  |",
            "|         | 05:06  |",
            "|         | :07    |",
            "+---------+--------+",
            "| Second  | 2021-  |",
            "| Entry   | 02-02  |",
            "|         | 00:00  |",
            "|         | :00    |",
            "+---------+--------+",
        ]
        expected = "\n".join(expected)
        self.assertEqual(expected, result)
