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

from armi.utils.tabulate import _alignColumn, _alignCellVeritically, _multilineWidth
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

    def test_align_column_decimal(self):
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

    def test_align_column_decimal_with_thousand_separators(self):
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

    def test_align_column_decimal_with_incorrect_thousand_separators(self):
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
        output = _alignColumn(column, "center", is_multiline=True)
        expected = ["  1  ", " 123 ", "12345" + "\n" + "  6  "]
        self.assertEqual(expected, output)

    def test_align_cell_veritically_one_line_only(self):
        """Internal: Aligning a single height cell is same regardless of alignment value."""
        lines = ["one line"]
        column_width = 8

        top = _alignCellVeritically(lines, 1, column_width, "top")
        center = _alignCellVeritically(lines, 1, column_width, "center")
        bottom = _alignCellVeritically(lines, 1, column_width, "bottom")
        none = _alignCellVeritically(lines, 1, column_width, None)

        expected = ["one line"]
        assert top == center == bottom == none == expected

    def test_align_cell_veritically_top_single_text_multiple_pad(self):
        """Internal: Align single cell text to top."""
        result = _alignCellVeritically(["one line"], 3, 8, "top")
        expected = ["one line", "        ", "        "]
        self.assertEqual(expected, result)

    def test_align_cell_veritically_center_single_text_multiple_pad(self):
        """Internal: Align single cell text to center."""
        result = _alignCellVeritically(["one line"], 3, 8, "center")
        expected = ["        ", "one line", "        "]
        self.assertEqual(expected, result)

    def test_align_cell_veritically_bottom_single_text_multiple_pad(self):
        """Internal: Align single cell text to bottom."""
        result = _alignCellVeritically(["one line"], 3, 8, "bottom")
        expected = ["        ", "        ", "one line"]
        self.assertEqual(expected, result)

    def test_align_cell_veritically_top_multi_text_multiple_pad(self):
        """Internal: Align multiline celltext text to top."""
        text = ["just", "one ", "cell"]
        result = _alignCellVeritically(text, 6, 4, "top")
        expected = ["just", "one ", "cell", "    ", "    ", "    "]
        self.assertEqual(expected, result)

    def test_align_cell_veritically_center_multi_text_multiple_pad(self):
        """Internal: Align multiline celltext text to center."""
        text = ["just", "one ", "cell"]
        result = _alignCellVeritically(text, 6, 4, "center")

        # Even number of rows, can't perfectly center, but we pad less
        # at top when required to do make a judgement
        expected = ["    ", "just", "one ", "cell", "    ", "    "]
        self.assertEqual(expected, result)

    def test_align_cell_veritically_bottom_multi_text_multiple_pad(self):
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

    def test_plain_headerless(self):
        """Output: plain without headers."""
        expected = "\n".join(["spam   41.9999", "eggs  451"])
        result = tabulate(_test_table, tablefmt="plain")
        self.assertEqual(expected, result)

    def test_plain_multiline_headerless(self):
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

    def test_plain_multiline(self):
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

    def test_plain_multiline_with_links(self):
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

    def test_plain_multiline_with_empty_cells(self):
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

    def test_plain_multiline_with_empty_cells_headerless(self):
        """Output: plain with multiline cells and empty cells without headers."""
        table = [["0", "", ""], ["1", "", ""], ["2", "very long data", "fold\nthis"]]
        expected = "\n".join(
            ["0", "1", "2  very long data  fold", "                   this"]
        )
        result = tabulate(table, tablefmt="plain")
        self.assertEqual(expected, result)

    def test_plain_maxcolwidth_autowraps(self):
        """Output: maxcolwidth will result in autowrapping longer cells."""
        table = [["hdr", "fold"], ["1", "very long data"]]
        expected = "\n".join(["  hdr  fold", "    1  very long", "       data"])
        result = tabulate(
            table, headers="firstrow", tablefmt="plain", maxcolwidths=[10, 10]
        )
        self.assertEqual(expected, result)

    def test_plain_maxcolwidth_autowraps_with_sep(self):
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

    def test_maxcolwidth_single_value(self):
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

    def test_maxcolwidth_pad_tailing_widths(self):
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

    def test_maxcolwidth_honor_disable_parsenum(self):
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

    def test_plain_maxheadercolwidths_autowraps(self):
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

    def test_simple_with_sep_line(self):
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

    def test_readme_example_with_sep(self):
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

    def test_simple_multiline_2(self):
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

    def test_simple_multiline_2_with_sep_line(self):
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

    def test_simple_headerless(self):
        """Output: simple without headers."""
        expected = "\n".join(
            ["----  --------", "spam   41.9999", "eggs  451", "----  --------"]
        )
        result = tabulate(_test_table, tablefmt="simple")
        self.assertEqual(expected, result)

    def test_simple_headerless_with_sep_line(self):
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

    def test_simple_multiline_headerless(self):
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

    def test_simple_multiline(self):
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

    def test_simple_multiline_with_links(self):
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

    def test_simple_multiline_with_empty_cells(self):
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

    def test_simple_multiline_with_empty_cells_headerless(self):
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

    def test_grid_headerless(self):
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

    def test_grid_multiline_headerless(self):
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

    def test_grid_multiline(self):
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

    def test_grid_multiline_with_empty_cells(self):
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

    def test_grid_multiline_with_empty_cells_headerless(self):
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

    def test_pretty_headerless(self):
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

    def test_pretty_multiline_headerless(self):
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

    def test_pretty_multiline(self):
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

    def test_pretty_multiline_with_links(self):
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

    def test_pretty_multiline_with_empty_cells(self):
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

    def test_pretty_multiline_with_empty_cells_headerless(self):
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

    def test_rst_with_empty_values_in_first_column(self):
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

    def test_rst_headerless(self):
        """Output: rst without headers."""
        expected = "\n".join(
            ["====  ========", "spam   41.9999", "eggs  451", "====  ========"]
        )
        result = tabulate(_test_table, tablefmt="rst")
        self.assertEqual(expected, result)

    def test_rst_multiline(self):
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

    def test_rst_multiline_with_links(self):
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

    def test_rst_multiline_with_empty_cells(self):
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

    def test_rst_multiline_with_empty_cells_headerless(self):
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

    def test_no_data(self):
        """Output: table with no data."""
        expected = "\n".join(["strings    numbers", "---------  ---------"])
        result = tabulate(None, _test_table_headers, tablefmt="simple")
        self.assertEqual(expected, result)

    def test_empty_data(self):
        """Output: table with empty data."""
        expected = "\n".join(["strings    numbers", "---------  ---------"])
        result = tabulate([], _test_table_headers, tablefmt="simple")
        self.assertEqual(expected, result)

    def test_no_data_without_headers(self):
        """Output: table with no data and no headers."""
        expected = ""
        result = tabulate(None, tablefmt="simple")
        self.assertEqual(expected, result)

    def test_empty_data_without_headers(self):
        """Output: table with empty data and no headers."""
        expected = ""
        result = tabulate([], tablefmt="simple")
        self.assertEqual(expected, result)

    def test_intfmt(self):
        """Output: integer format."""
        result = tabulate([[10000], [10]], intfmt=",", tablefmt="plain")
        expected = "10,000\n    10"
        self.assertEqual(expected, result)

    def test_empty_data_with_headers(self):
        """Output: table with empty data and headers as firstrow."""
        expected = ""
        result = tabulate([], headers="firstrow")
        self.assertEqual(expected, result)

    def test_floatfmt(self):
        """Output: floating point format."""
        result = tabulate([["1.23456789"], [1.0]], floatfmt=".3f", tablefmt="plain")
        expected = "1.235\n1.000"
        self.assertEqual(expected, result)

    def test_floatfmt_multi(self):
        """Output: floating point format different for each column."""
        result = tabulate(
            [[0.12345, 0.12345, 0.12345]], floatfmt=(".1f", ".3f"), tablefmt="plain"
        )
        expected = "0.1  0.123  0.12345"
        self.assertEqual(expected, result)

    def test_colalign_multi(self):
        """Output: string columns with custom colalign."""
        result = tabulate(
            [["one", "two"], ["three", "four"]], colalign=("right",), tablefmt="plain"
        )
        expected = "  one  two\nthree  four"
        self.assertEqual(expected, result)

    def test_colalign_multi_with_sep_line(self):
        """Output: string columns with custom colalign."""
        result = tabulate(
            [["one", "two"], SEPARATING_LINE, ["three", "four"]],
            colalign=("right",),
            tablefmt="plain",
        )
        expected = "  one  two\n\nthree  four"
        self.assertEqual(expected, result)
