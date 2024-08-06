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

"""Pretty-print tabular data."""
from collections import namedtuple
from collections.abc import Iterable, Sized
from functools import reduce, partial
from itertools import chain, zip_longest as izip_longest
import dataclasses
import math
import re
import textwrap
import warnings

__all__ = ["tabulate", "tabulate_formats"]


# minimum extra space in headers
MIN_PADDING = 2

# Whether or not to preserve leading/trailing whitespace in data.
PRESERVE_WHITESPACE = False

_DEFAULT_FLOATFMT = "g"
_DEFAULT_INTFMT = ""
_DEFAULT_MISSINGVAL = ""
# default align will be overwritten by "left", "center" or "decimal" depending on the formatter
_DEFAULT_ALIGN = "default"

# Constant that can be used as part of passed rows to generate a separating line
# It is purposely an unprintable character, very unlikely to be used in a table
SEPARATING_LINE = "\001"

Line = namedtuple("Line", ["begin", "hline", "sep", "end"])
DataRow = namedtuple("DataRow", ["begin", "sep", "end"])

# A table structure is supposed to be:
#
#     --- lineabove ---------
#         headerrow
#     --- linebelowheader ---
#         datarow
#     --- linebetweenrows ---
#     ... (more datarows) ...
#     --- linebetweenrows ---
#         last datarow
#     --- linebelow ---------
#
# TableFormat's line* elements can be
#
#   - either None, if the element is not used,
#   - or a Line tuple,
#   - or a function: [col_widths], [col_alignments] -> string.
#
# TableFormat's *row elements can be
#
#   - either None, if the element is not used,
#   - or a DataRow tuple,
#   - or a function: [cell_values], [col_widths], [col_alignments] -> string.
#
# padding (an integer) is the amount of white space around data values.
#
# withHeaderHide:
#
#   - either None, to display all table elements unconditionally,
#   - or a list of elements not to be displayed if the table has column headers.
#
TableFormat = namedtuple(
    "TableFormat",
    [
        "lineabove",
        "linebelowheader",
        "linebetweenrows",
        "linebelow",
        "headerrow",
        "datarow",
        "padding",
        "withHeaderHide",
    ],
)


def _isSeparatingLine(row):
    rowType = type(row)
    isSl = (rowType is list or rowType is str) and (
        (len(row) >= 1 and row[0] == SEPARATING_LINE)
        or (len(row) >= 2 and row[1] == SEPARATING_LINE)
    )
    return isSl


def _rstEscapeFirstColumn(rows, headers):
    def escapeEmpty(val):
        if isinstance(val, (str, bytes)) and not val.strip():
            return ".."
        else:
            return val

    newHeaders = list(headers)
    newRows = []
    if headers:
        newHeaders[0] = escapeEmpty(headers[0])
    for row in rows:
        newRow = list(row)
        if newRow:
            newRow[0] = escapeEmpty(row[0])
        newRows.append(newRow)
    return newRows, newHeaders


_table_formats = {
    "armi": TableFormat(
        lineabove=Line("", "-", "  ", ""),
        linebelowheader=Line("", "-", "  ", ""),
        linebetweenrows=None,
        linebelow=Line("", "-", "  ", ""),
        headerrow=DataRow("", "  ", ""),
        datarow=DataRow("", "  ", ""),
        padding=0,
        withHeaderHide=None,
    ),
    "simple": TableFormat(
        lineabove=Line("", "-", "  ", ""),
        linebelowheader=Line("", "-", "  ", ""),
        linebetweenrows=None,
        linebelow=Line("", "-", "  ", ""),
        headerrow=DataRow("", "  ", ""),
        datarow=DataRow("", "  ", ""),
        padding=0,
        withHeaderHide=["lineabove", "linebelow"],
    ),
    "plain": TableFormat(
        lineabove=None,
        linebelowheader=None,
        linebetweenrows=None,
        linebelow=None,
        headerrow=DataRow("", "  ", ""),
        datarow=DataRow("", "  ", ""),
        padding=0,
        withHeaderHide=None,
    ),
    "grid": TableFormat(
        lineabove=Line("+", "-", "+", "+"),
        linebelowheader=Line("+", "=", "+", "+"),
        linebetweenrows=Line("+", "-", "+", "+"),
        linebelow=Line("+", "-", "+", "+"),
        headerrow=DataRow("|", "|", "|"),
        datarow=DataRow("|", "|", "|"),
        padding=1,
        withHeaderHide=None,
    ),
    "github": TableFormat(
        lineabove=Line("|", "-", "|", "|"),
        linebelowheader=Line("|", "-", "|", "|"),
        linebetweenrows=None,
        linebelow=None,
        headerrow=DataRow("|", "|", "|"),
        datarow=DataRow("|", "|", "|"),
        padding=1,
        withHeaderHide=["lineabove"],
    ),
    "pretty": TableFormat(
        lineabove=Line("+", "-", "+", "+"),
        linebelowheader=Line("+", "-", "+", "+"),
        linebetweenrows=None,
        linebelow=Line("+", "-", "+", "+"),
        headerrow=DataRow("|", "|", "|"),
        datarow=DataRow("|", "|", "|"),
        padding=1,
        withHeaderHide=None,
    ),
    "psql": TableFormat(
        lineabove=Line("+", "-", "+", "+"),
        linebelowheader=Line("|", "-", "+", "|"),
        linebetweenrows=None,
        linebelow=Line("+", "-", "+", "+"),
        headerrow=DataRow("|", "|", "|"),
        datarow=DataRow("|", "|", "|"),
        padding=1,
        withHeaderHide=None,
    ),
    "rst": TableFormat(
        lineabove=Line("", "=", "  ", ""),
        linebelowheader=Line("", "=", "  ", ""),
        linebetweenrows=None,
        linebelow=Line("", "=", "  ", ""),
        headerrow=DataRow("", "  ", ""),
        datarow=DataRow("", "  ", ""),
        padding=0,
        withHeaderHide=None,
    ),
    "tsv": TableFormat(
        lineabove=None,
        linebelowheader=None,
        linebetweenrows=None,
        linebelow=None,
        headerrow=DataRow("", "\t", ""),
        datarow=DataRow("", "\t", ""),
        padding=0,
        withHeaderHide=None,
    ),
}


tabulate_formats = list(sorted(_table_formats.keys()))

# The table formats for which multiline cells will be folded into subsequent table rows. The key is
# the original format specified at the API. The value is the format that will be used to represent
# the original format.
multiline_formats = {
    "armi": "armi",
    "plain": "plain",
    "simple": "simple",
    "grid": "grid",
    "pretty": "pretty",
    "psql": "psql",
    "rst": "rst",
}

_multilineCodes = re.compile(r"\r|\n|\r\n")
_multilineCodesBytes = re.compile(b"\r|\n|\r\n")

# Handle ANSI escape sequences for both control sequence introducer (CSI) and operating system
# command (OSC). Both of these begin with 0x1b (or octal 033), which will be shown below as ESC.
#
# CSI ANSI escape codes have the following format, defined in section 5.4 of ECMA-48:
#
# CSI: ESC followed by the '[' character (0x5b)
# Parameter Bytes: 0..n bytes in the range 0x30-0x3f
# Intermediate Bytes: 0..n bytes in the range 0x20-0x2f
# Final Byte: a single byte in the range 0x40-0x7e
#
# Also include the terminal hyperlink sequences as described here:
# https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda
#
# OSC 8 ; params ; uri ST display_text OSC 8 ;; ST
#
# Example: \x1b]8;;https://example.com\x5ctext to show\x1b]8;;\x5c
#
# Where:
# OSC: ESC followed by the ']' character (0x5d)
# params: 0..n optional key value pairs separated by ':' (e.g. foo=bar:baz=qux:abc=123)
# URI: the actual URI with protocol scheme (e.g. https://, file://, ftp://)
# ST: ESC followed by the '\' character (0x5c)
_esc = r"\x1b"
_csi = rf"{_esc}\["
_osc = rf"{_esc}\]"
_st = rf"{_esc}\\"

_ansiEscapePat = rf"""
    (
        # terminal colors, etc
        {_csi}        # CSI
        [\x30-\x3f]*  # parameter bytes
        [\x20-\x2f]*  # intermediate bytes
        [\x40-\x7e]   # final byte
    |
        # terminal hyperlinks
        {_osc}8;        # OSC opening
        (\w+=\w+:?)*    # key=value params list (submatch 2)
        ;               # delimiter
        ([^{_esc}]+)    # URI - anything but ESC (submatch 3)
        {_st}           # ST
        ([^{_esc}]+)    # link text - anything but ESC (submatch 4)
        {_osc}8;;{_st}  # "closing" OSC sequence
    )
"""
_ansiCodes = re.compile(_ansiEscapePat, re.VERBOSE)
_ansiCodesBytes = re.compile(_ansiEscapePat.encode("utf8"), re.VERBOSE)
_ansiColorResetCode = "\033[0m"

_floatWithThousandsSeparators = re.compile(
    r"^(([+-]?[0-9]{1,3})(?:,([0-9]{3}))*)?(?(1)\.[0-9]*|\.[0-9]+)?$"
)


def _isnumberWithThousandsSeparator(string):
    """Function to test of a string is a number with a thousands separator.

    >>> _isnumberWithThousandsSeparator(".")
    False
    >>> _isnumberWithThousandsSeparator("1")
    True
    >>> _isnumberWithThousandsSeparator("1.")
    True
    >>> _isnumberWithThousandsSeparator(".1")
    True
    >>> _isnumberWithThousandsSeparator("1000")
    False
    >>> _isnumberWithThousandsSeparator("1,000")
    True
    >>> _isnumberWithThousandsSeparator("1,0000")
    False
    >>> _isnumberWithThousandsSeparator("1,000.1234")
    True
    >>> _isnumberWithThousandsSeparator(b"1,000.1234")
    True
    >>> _isnumberWithThousandsSeparator("+1,000.1234")
    True
    >>> _isnumberWithThousandsSeparator("-1,000.1234")
    True
    """
    try:
        string = string.decode()
    except (UnicodeDecodeError, AttributeError):
        pass

    return bool(re.match(_floatWithThousandsSeparators, string))


def _isconvertible(conv, string):
    try:
        conv(string)
        return True
    except (ValueError, TypeError):
        return False


def _isnumber(string):
    """Helper function; is this string a number.

    >>> _isnumber("123.45")
    True
    >>> _isnumber("123")
    True
    >>> _isnumber("spam")
    False
    >>> _isnumber("123e45678")
    False
    >>> _isnumber("inf")
    True
    """
    if not _isconvertible(float, string):
        return False
    elif isinstance(string, (str, bytes)) and (
        math.isinf(float(string)) or math.isnan(float(string))
    ):
        return string.lower() in ["inf", "-inf", "nan"]
    return True


def _isint(string, inttype=int):
    """Determine if a string is an integer.

    >>> _isint("123")
    True
    >>> _isint("123.45")
    False
    """
    return (
        type(string) is inttype
        or (
            (hasattr(string, "is_integer") or hasattr(string, "__array__"))
            and str(type(string)).startswith("<class 'numpy.int")
        )  # numpy.int64 and similar
        or (
            isinstance(string, (bytes, str)) and _isconvertible(inttype, string)
        )  # integer as string
    )


def _isbool(string):
    """Test if a string is a boolean.

    >>> _isbool(True)
    True
    >>> _isbool("False")
    True
    >>> _isbool(1)
    False
    """
    return type(string) is bool or (
        isinstance(string, (bytes, str)) and string in ("True", "False")
    )


def _type(string, hasInvisible=True, numparse=True):
    r"""The least generic type (type(None), int, float, str, unicode).

    >>> _type(None) is type(None)
    True
    >>> _type("foo") is type("")
    True
    >>> _type("1") is type(1)
    True
    >>> _type('\x1b[31m42\x1b[0m') is type(42)
    True
    >>> _type('\x1b[31m42\x1b[0m') is type(42)
    True

    """
    if hasInvisible and isinstance(string, (str, bytes)):
        string = _stripAnsi(string)

    if string is None:
        return type(None)
    elif hasattr(string, "isoformat"):
        # datetime.datetime, date, and time
        return str
    elif _isbool(string):
        return bool
    elif _isint(string) and numparse:
        return int
    elif _isnumber(string) and numparse:
        return float
    elif isinstance(string, bytes):
        return bytes
    else:
        return str


def _afterpoint(string):
    """Symbols after a decimal point, -1 if the string lacks the decimal point.

    >>> _afterpoint("123.45")
    2
    >>> _afterpoint("1001")
    -1
    >>> _afterpoint("eggs")
    -1
    >>> _afterpoint("123e45")
    2
    >>> _afterpoint("123,456.78")
    2

    """
    if _isnumber(string) or _isnumberWithThousandsSeparator(string):
        if _isint(string):
            return -1
        else:
            pos = string.rfind(".")
            pos = string.lower().rfind("e") if pos < 0 else pos
            if pos >= 0:
                return len(string) - pos - 1
            else:
                # no point
                return -1
    else:
        # not a number
        return -1


def _padleft(width, s):
    r"""Flush right.

    >>> _padleft(6, '\u044f\u0439\u0446\u0430') == '  \u044f\u0439\u0446\u0430'
    True

    """
    fmt = "{0:>%ds}" % width
    return fmt.format(s)


def _padright(width, s):
    r"""Flush left.

    >>> _padright(6, '\u044f\u0439\u0446\u0430') == '\u044f\u0439\u0446\u0430  '
    True

    """
    fmt = "{0:<%ds}" % width
    return fmt.format(s)


def _padboth(width, s):
    r"""Center string.

    >>> _padboth(6, '\u044f\u0439\u0446\u0430') == ' \u044f\u0439\u0446\u0430 '
    True

    """
    fmt = "{0:^%ds}" % width
    return fmt.format(s)


def _padnone(ignore_width, s):
    return s


def _stripAnsi(s):
    r"""Remove ANSI escape sequences, both CSI (color codes, etc) and OSC hyperlinks.

    CSI sequences are simply removed from the output, while OSC hyperlinks are replaced with the
    link text. Note: it may be desirable to show the URI instead but this is not supported.

    >>> repr(_stripAnsi('\x1B]8;;https://example.com\x1B\\This is a link\x1B]8;;\x1B\\'))
    "'This is a link'"

    >>> repr(_stripAnsi('\x1b[31mred\x1b[0m text'))
    "'red text'"

    """
    if isinstance(s, str):
        return _ansiCodes.sub(r"\4", s)
    else:  # a bytestring
        return _ansiCodesBytes.sub(r"\4", s)


def _visibleWidth(s):
    r"""Visible width of a printed string. ANSI color codes are removed.

    >>> _visibleWidth('\x1b[31mhello\x1b[0m'), _visibleWidth("world")
    (5, 5)

    """
    if isinstance(s, (str, bytes)):
        return len(_stripAnsi(s))
    else:
        return len(str(s))


def _isMultiline(s):
    if isinstance(s, str):
        return bool(re.search(_multilineCodes, s))
    else:
        # a bytestring
        return bool(re.search(_multilineCodesBytes, s))


def _multilineWidth(multilineS, lineWidthFn=len):
    """Visible width of a potentially multiline content."""
    return max(map(lineWidthFn, re.split("[\r\n]", multilineS)))


def _chooseWidthFn(hasInvisible, isMultiline):
    """Return a function to calculate visible cell width."""
    if hasInvisible:
        lineWidthFn = _visibleWidth
    else:
        lineWidthFn = len

    if isMultiline:
        widthFn = lambda s: _multilineWidth(s, lineWidthFn)
    else:
        widthFn = lineWidthFn

    return widthFn


def _alignColumnChoosePadfn(strings, alignment, hasInvisible):
    if alignment == "right":
        if not PRESERVE_WHITESPACE:
            strings = [s.strip() for s in strings]
        padfn = _padleft
    elif alignment == "center":
        if not PRESERVE_WHITESPACE:
            strings = [s.strip() for s in strings]
        padfn = _padboth
    elif alignment == "decimal":
        if hasInvisible:
            decimals = [_afterpoint(_stripAnsi(s)) for s in strings]
        else:
            decimals = [_afterpoint(s) for s in strings]
        maxdecimals = max(decimals)
        strings = [s + (maxdecimals - decs) * " " for s, decs in zip(strings, decimals)]
        padfn = _padleft
    elif not alignment:
        padfn = _padnone
    else:
        if not PRESERVE_WHITESPACE:
            strings = [s.strip() for s in strings]
        padfn = _padright
    return strings, padfn


def _alignColumnChooseWidthFn(hasInvisible, isMultiline):
    if hasInvisible:
        lineWidthFn = _visibleWidth
    else:
        lineWidthFn = len

    if isMultiline:
        widthFn = lambda s: _alignColumnMultilineWidth(s, lineWidthFn)
    else:
        widthFn = lineWidthFn

    return widthFn


def _alignColumnMultilineWidth(multiline_s, lineWidthFn=len):
    """Visible width of a potentially multiline content."""
    return list(map(lineWidthFn, re.split("[\r\n]", multiline_s)))


def _flatList(nested_list):
    ret = []
    for item in nested_list:
        if isinstance(item, list):
            for subitem in item:
                ret.append(subitem)
        else:
            ret.append(item)
    return ret


def _alignColumn(strings, alignment, minwidth=0, hasInvisible=True, isMultiline=False):
    """[string] -> [padded_string]."""
    strings, padfn = _alignColumnChoosePadfn(strings, alignment, hasInvisible)
    widthFn = _alignColumnChooseWidthFn(hasInvisible, isMultiline)

    sWidths = list(map(widthFn, strings))
    maxwidth = max(max(_flatList(sWidths)), minwidth)
    if isMultiline:
        if not hasInvisible:
            paddedStrings = [
                "\n".join([padfn(maxwidth, s) for s in ms.splitlines()])
                for ms in strings
            ]
        else:
            # enable wide-character width corrections
            sLens = [[len(s) for s in re.split("[\r\n]", ms)] for ms in strings]
            visibleWidths = [
                [maxwidth - (w - ll) for w, ll in zip(mw, ml)]
                for mw, ml in zip(sWidths, sLens)
            ]
            # wcswidth and _visibleWidth don't count invisible characters;
            # padfn doesn't need to apply another correction
            paddedStrings = [
                "\n".join([padfn(w, s) for s, w in zip((ms.splitlines() or ms), mw)])
                for ms, mw in zip(strings, visibleWidths)
            ]
    else:  # single-line cell values
        if not hasInvisible:
            paddedStrings = [padfn(maxwidth, s) for s in strings]
        else:
            # enable wide-character width corrections
            sLens = list(map(len, strings))
            visibleWidths = [maxwidth - (w - ll) for w, ll in zip(sWidths, sLens)]
            # wcswidth and _visibleWidth don't count invisible characters;
            # padfn doesn't need to apply another correction
            paddedStrings = [padfn(w, s) for s, w in zip(strings, visibleWidths)]

    return paddedStrings


def _moreGeneric(type1, type2):
    types = {
        type(None): 0,
        bool: 1,
        int: 2,
        float: 3,
        bytes: 4,
        str: 5,
    }
    invtypes = {
        5: str,
        4: bytes,
        3: float,
        2: int,
        1: bool,
        0: type(None),
    }
    moregeneric = max(types.get(type1, 5), types.get(type2, 5))
    return invtypes[moregeneric]


def _columnType(strings, hasInvisible=True, numparse=True):
    r"""The least generic type all column values are convertible to.

    >>> _columnType([True, False]) is bool
    True
    >>> _columnType(["1", "2"]) is int
    True
    >>> _columnType(["1", "2.3"]) is float
    True
    >>> _columnType(["1", "2.3", "four"]) is str
    True
    >>> _columnType(["four", '\u043f\u044f\u0442\u044c']) is str
    True
    >>> _columnType([None, "brux"]) is str
    True
    >>> _columnType([1, 2, None]) is int
    True
    >>> import datetime as dt
    >>> _columnType([dt.datetime(1991,2,19), dt.time(17,35)]) is str
    True

    """
    types = [_type(s, hasInvisible, numparse) for s in strings]
    return reduce(_moreGeneric, types, bool)


def _format(val, valtype, floatfmt, intfmt, missingval="", hasInvisible=True):
    r"""Format a value according to its type.

    Unicode is supported:

    >>> hrow = ['\u0431\u0443\u043a\u0432\u0430', '\u0446\u0438\u0444\u0440\u0430'] ; \
        tbl = [['\u0430\u0437', 2], ['\u0431\u0443\u043a\u0438', 4]] ; \
        good_result = '\\u0431\\u0443\\u043a\\u0432\\u0430      \\u0446\\u0438\\u0444\\u0440\\u0430\\n-------  -------\\n\\u0430\\u0437             2\\n\\u0431\\u0443\\u043a\\u0438           4' ; \
        tabulate(tbl, headers=hrow) == good_result
    True

    """  # noqa
    if val is None:
        return missingval

    if valtype is str:
        return f"{val}"
    elif valtype is int:
        return format(val, intfmt)
    elif valtype is bytes:
        try:
            return str(val, "ascii")
        except (TypeError, UnicodeDecodeError):
            return str(val)
    elif valtype is float:
        isAColoredNumber = hasInvisible and isinstance(val, (str, bytes))
        if isAColoredNumber:
            rawVal = _stripAnsi(val)
            formattedVal = format(float(rawVal), floatfmt)
            return val.replace(rawVal, formattedVal)
        else:
            return format(float(val), floatfmt)
    else:
        return f"{val}"


def _alignHeader(
    header, alignment, width, visibleWidth, isMultiline=False, widthFn=None
):
    """Pad string header to width chars given known visibleWidth of the header."""
    if isMultiline:
        headerLines = re.split(_multilineCodes, header)
        paddedLines = [
            _alignHeader(h, alignment, width, widthFn(h)) for h in headerLines
        ]
        return "\n".join(paddedLines)
    # else: not multiline
    ninvisible = len(header) - visibleWidth
    width += ninvisible
    if alignment == "left":
        return _padright(width, header)
    elif alignment == "center":
        return _padboth(width, header)
    elif not alignment:
        return f"{header}"
    else:
        return _padleft(width, header)


def _removeSeparatingLines(rows):
    if type(rows) is list:
        separatingLines = []
        sansRows = []
        for index, row in enumerate(rows):
            if _isSeparatingLine(row):
                separatingLines.append(index)
            else:
                sansRows.append(row)
        return sansRows, separatingLines
    else:
        return rows, None


def _reinsertSeparatingLines(rows, separatingLines):
    if separatingLines:
        for index in separatingLines:
            rows.insert(index, SEPARATING_LINE)


def _prependRowIndex(rows, index):
    """Add a left-most index column."""
    if index is None or index is False:
        return rows
    if isinstance(index, Sized) and len(index) != len(rows):
        raise ValueError(
            "index must be as long as the number of data rows: "
            + "len(index)={} len(rows)={}".format(len(index), len(rows))
        )
    sansRows, separatingLines = _removeSeparatingLines(rows)
    newRows = []
    indexIter = iter(index)
    for row in sansRows:
        indexV = next(indexIter)
        newRows.append([indexV] + list(row))
    rows = newRows
    _reinsertSeparatingLines(rows, separatingLines)
    return rows


def _bool(val):
    """A wrapper around standard bool() which doesn't throw on NumPy arrays."""
    try:
        return bool(val)
    except ValueError:
        # val is likely to be a numpy array with many elements
        return False


def _normalizeTabularData(tabularData, headers, showindex="default"):
    """Transform a supported data type to a list of lists & a list of headers, with header padding.

    Supported tabular data types:

    * list-of-lists or another iterable of iterables
    * list of named tuples (usually used with headers="keys")
    * list of dicts (usually used with headers="keys")
    * list of OrderedDicts (usually used with headers="keys")
    * list of dataclasses (Python 3.7+ only, usually used with headers="keys")
    * 2D NumPy arrays
    * NumPy record arrays (usually used with headers="keys")
    * dict of iterables (usually used with headers="keys")
    * pandas.DataFrame (usually used with headers="keys")

    The first row can be used as headers if headers="firstrow",
    column indices can be used as headers if headers="keys".

    If showindex="default", show row indices of the pandas.DataFrame.
    If showindex="always", show row indices for all types of data.
    If showindex="never", don't show row indices for all types of data.
    If showindex is an iterable, show its values as row indices.
    """
    try:
        bool(headers)
    except ValueError:
        # numpy.ndarray, pandas.core.index.Index, ...
        headers = list(headers)

    index = None
    if hasattr(tabularData, "keys") and hasattr(tabularData, "values"):
        # dict-like and pandas.DataFrame?
        if hasattr(tabularData.values, "__call__"):
            # likely a conventional dict
            keys = tabularData.keys()
            rows = list(
                izip_longest(*tabularData.values())
            )  # columns have to be transposed
        elif hasattr(tabularData, "index"):
            # values is a property, has .index => it's likely a pandas.DataFrame (pandas 0.11.0)
            keys = list(tabularData)
            if (
                showindex in ["default", "always", True]
                and tabularData.index.name is not None
            ):
                if isinstance(tabularData.index.name, list):
                    keys[:0] = tabularData.index.name
                else:
                    keys[:0] = [tabularData.index.name]
            vals = tabularData.values  # values matrix doesn't need to be transposed
            # for DataFrames add an index per default
            index = list(tabularData.index)
            rows = [list(row) for row in vals]
        else:
            raise ValueError("tabular data doesn't appear to be a dict or a DataFrame")

        if headers == "keys":
            headers = list(map(str, keys))  # headers should be strings

    else:  # it's a usual iterable of iterables, or a NumPy array, or an iterable of dataclasses
        rows = list(tabularData)

        if headers == "keys" and not rows:
            # an empty table (issue #81)
            headers = []
        elif (
            headers == "keys"
            and hasattr(tabularData, "dtype")
            and getattr(tabularData.dtype, "names")
        ):
            # numpy record array
            headers = tabularData.dtype.names
        elif (
            headers == "keys"
            and len(rows) > 0
            and isinstance(rows[0], tuple)
            and hasattr(rows[0], "_fields")
        ):
            # namedtuple
            headers = list(map(str, rows[0]._fields))
        elif len(rows) > 0 and hasattr(rows[0], "keys") and hasattr(rows[0], "values"):
            # dict-like object
            uniqKeys = set()  # implements hashed lookup
            keys = []  # storage for set
            if headers == "firstrow":
                firstdict = rows[0] if len(rows) > 0 else {}
                keys.extend(firstdict.keys())
                uniqKeys.update(keys)
                rows = rows[1:]
            for row in rows:
                for k in row.keys():
                    # Save unique items in input order
                    if k not in uniqKeys:
                        keys.append(k)
                        uniqKeys.add(k)
            if headers == "keys":
                headers = keys
            elif isinstance(headers, dict):
                # a dict of headers for a list of dicts
                headers = [headers.get(k, k) for k in keys]
                headers = list(map(str, headers))
            elif headers == "firstrow":
                if len(rows) > 0:
                    headers = [firstdict.get(k, k) for k in keys]
                    headers = list(map(str, headers))
                else:
                    headers = []
            elif headers:
                raise ValueError(
                    "headers for a list of dicts is not a dict or a keyword"
                )
            rows = [[row.get(k) for k in keys] for row in rows]
        elif (
            headers == "keys"
            and hasattr(tabularData, "description")
            and hasattr(tabularData, "fetchone")
            and hasattr(tabularData, "rowcount")
        ):
            # Python Database API cursor object (PEP 0249)
            # print tabulate(cursor, headers='keys')
            headers = [column[0] for column in tabularData.description]
        elif (
            dataclasses is not None
            and len(rows) > 0
            and dataclasses.is_dataclass(rows[0])
        ):
            # Python 3.7+'s dataclass
            fieldNames = [field.name for field in dataclasses.fields(rows[0])]
            if headers == "keys":
                headers = fieldNames
            rows = [[getattr(row, f) for f in fieldNames] for row in rows]
        elif headers == "keys" and len(rows) > 0:
            # keys are column indices
            headers = list(map(str, range(len(rows[0]))))

    # take headers from the first row if necessary
    if headers == "firstrow" and len(rows) > 0:
        if index is not None:
            headers = [index[0]] + list(rows[0])
            index = index[1:]
        else:
            headers = rows[0]
        headers = list(map(str, headers))  # headers should be strings
        rows = rows[1:]
    elif headers == "firstrow":
        headers = []

    headers = list(map(str, headers))
    rows = list(map(lambda r: r if _isSeparatingLine(r) else list(r), rows))

    # add or remove an index column
    showIndexIsSStr = type(showindex) in [str, bytes]
    if showindex == "default" and index is not None:
        rows = _prependRowIndex(rows, index)
    elif isinstance(showindex, Sized) and not showIndexIsSStr:
        rows = _prependRowIndex(rows, list(showindex))
    elif isinstance(showindex, Iterable) and not showIndexIsSStr:
        rows = _prependRowIndex(rows, showindex)
    elif showindex == "always" or (_bool(showindex) and not showIndexIsSStr):
        if index is None:
            index = list(range(len(rows)))
        rows = _prependRowIndex(rows, index)
    elif showindex == "never" or (not _bool(showindex) and not showIndexIsSStr):
        pass

    # pad with empty headers for initial columns if necessary
    headersPad = 0
    if headers and len(rows) > 0:
        headersPad = max(0, len(rows[0]) - len(headers))
        headers = [""] * headersPad + headers

    return rows, headers, headersPad


def _wrapTextToColwidths(listOfLists, colwidths, numparses=True):
    if len(listOfLists):
        numCols = len(listOfLists[0])
    else:
        numCols = 0
    numparses = _expandIterable(numparses, numCols, True)

    result = []

    for row in listOfLists:
        new_row = []
        for cell, width, numparse in zip(row, colwidths, numparses):
            if _isnumber(cell) and numparse:
                new_row.append(cell)
                continue

            if width is not None:
                wrapper = _CustomTextWrap(width=width)
                # Cast based on our internal type handling
                # Any future custom formatting of types (such as datetimes)
                # may need to be more explicit than just `str` of the object
                casted_cell = (
                    str(cell) if _isnumber(cell) else _type(cell, numparse)(cell)
                )
                wrapped = [
                    "\n".join(wrapper.wrap(line))
                    for line in casted_cell.splitlines()
                    if line.strip() != ""
                ]
                new_row.append("\n".join(wrapped))
            else:
                new_row.append(cell)
        result.append(new_row)

    return result


def _toStr(s, encoding="utf8", errors="ignore"):
    """
    A type safe wrapper for converting a bytestring to str.

    This is essentially just a wrapper around .decode() intended for use with things like map(), but
    with some specific behavior:

    1. if the given parameter is not a bytestring, it is returned unmodified
    2. decode() is called for the given parameter and assumes utf8 encoding, but the default error
       behavior is changed from 'strict' to 'ignore'

    >>> repr(_toStr(b'foo'))
    "'foo'"

    >>> repr(_toStr('foo'))
    "'foo'"

    >>> repr(_toStr(42))
    "'42'"

    """
    if isinstance(s, bytes):
        return s.decode(encoding=encoding, errors=errors)
    return str(s)


def tabulate(
    tabular_data,
    headers=(),
    tablefmt="simple",
    floatfmt=_DEFAULT_FLOATFMT,
    intfmt=_DEFAULT_INTFMT,
    numalign=_DEFAULT_ALIGN,
    stralign=_DEFAULT_ALIGN,
    missingval=_DEFAULT_MISSINGVAL,
    showindex="default",
    disableNumparse=False,
    colglobalalign=None,
    colalign=None,
    maxcolwidths=None,
    headersglobalalign=None,
    headersalign=None,
    rowalign=None,
    maxheadercolwidths=None,
):
    r"""Format a fixed width table for pretty printing.

    >>> print(tabulate([[1, 2.34], [-56, "8.999"], ["2", "10001"]]))
    ---  ---------
      1      2.34
    -56      8.999
      2  10001
    ---  ---------

    The first required argument (`tabular_data`) can be a list-of-lists (or another iterable of
    iterables), a list of named tuples, a dictionary of iterables, an iterable of dictionaries, an
    iterable of dataclasses (Python 3.7+), a two-dimensional NumPy array, NumPy record array, or a
    Pandas' dataframe.

    Table headers
    -------------

    To print nice column headers, supply the second argument (`headers`):

      - `headers` can be an explicit list of column headers
      - if `headers="firstrow"`, then the first row of data is used
      - if `headers="keys"`, then dictionary keys or column indices are used

    Otherwise a headerless table is produced.

    If the number of headers is less than the number of columns, they are supposed to be names of
    the last columns. This is consistent with the plain-text format of R and Pandas' dataframes.

    >>> print(tabulate([["sex","age"],["Alice","F",24],["Bob","M",19]],
    ...       headers="firstrow"))
           sex      age
    -----  -----  -----
    Alice  F         24
    Bob    M         19

    By default, pandas.DataFrame data have an additional column called row index. To add a similar
    column to all other types of data, use `showindex="always"` or `showindex=True`. To suppress row
    indices for all types of data, pass `showindex="never" or `showindex=False`. To add a custom row
    index column, pass `showindex=some_iterable`.

    >>> print(tabulate([["F",24],["M",19]], showindex="always"))
    -  -  --
    0  F  24
    1  M  19
    -  -  --

    Column and Headers alignment
    ----------------------------

    `tabulate` tries to detect column types automatically, and aligns the values properly. By
    default it aligns decimal points of the numbers (or flushes integer numbers to the right), and
    flushes everything else to the left. Possible column alignments (`numalign`, `stralign`) are:
    "right", "center", "left", "decimal" (only for `numalign`), and None (to disable alignment).

    `colglobalalign` allows for global alignment of columns, before any specific override from
        `colalign`. Possible values are: None (defaults according to coltype), "right", "center",
        "decimal", "left".
    `colalign` allows for column-wise override starting from left-most column. Possible values are:
        "global" (no override), "right", "center", "decimal", "left".
    `headersglobalalign` allows for global headers alignment, before any specific override from
        `headersalign`. Possible values are: None (follow columns alignment), "right", "center",
        "left".
    `headersalign` allows for header-wise override starting from left-most given header. Possible
        values are: "global" (no override), "same" (follow column alignment), "right", "center",
        "left".

    Note on intended behaviour: If there is no `tabular_data`, any column alignment argument is
        ignored. Hence, in this case, header alignment cannot be inferred from column alignment.

    Table formats
    -------------
    `intfmt` is a format specification used for columns which contain numeric data without a decimal
    point. This can also be a list or tuple of format strings, one per column.

    `floatfmt` is a format specification used for columns which contain numeric data with a decimal
    point. This can also be a list or tuple of format strings, one per column.

    `None` values are replaced with a `missingval` string (like `floatfmt`, this can also be a list
    of values for different columns):

    >>> print(tabulate([["spam", 1, None],
    ...                 ["eggs", 42, 3.14],
    ...                 ["other", None, 2.7]], missingval="?"))
    -----  --  ----
    spam    1  ?
    eggs   42  3.14
    other   ?  2.7
    -----  --  ----

    Various plain-text table formats (`tablefmt`) are supported: 'plain', 'simple', 'grid',
    'orgtbl', 'rst', and `tsv`. Variable `tabulate_formats` contains the list of currently supported
    formats.

    "plain" format doesn't use any pseudographics to draw tables, it separates columns with a double
    space:

    >>> print(tabulate([["spam", 41.9999], ["eggs", "451.0"]],
    ...                 ["strings", "numbers"], "plain"))
    strings      numbers
    spam         41.9999
    eggs        451

    >>> print(tabulate([["spam", 41.9999], ["eggs", "451.0"]], tablefmt="plain"))
    spam   41.9999
    eggs  451

    "simple" format is like Pandoc simple_tables:

    >>> print(tabulate([["spam", 41.9999], ["eggs", "451.0"]],
    ...                 ["strings", "numbers"], "simple"))
    strings      numbers
    ---------  ---------
    spam         41.9999
    eggs        451

    >>> print(tabulate([["spam", 41.9999], ["eggs", "451.0"]], tablefmt="simple"))
    ----  --------
    spam   41.9999
    eggs  451
    ----  --------

    "grid" is similar to tables produced by Emacs table.el package or Pandoc grid_tables:

    >>> print(tabulate([["spam", 41.9999], ["eggs", "451.0"]],
    ...                ["strings", "numbers"], "grid"))
    +-----------+-----------+
    | strings   |   numbers |
    +===========+===========+
    | spam      |   41.9999 |
    +-----------+-----------+
    | eggs      |  451      |
    +-----------+-----------+

    >>> print(tabulate([["spam", 41.9999], ["eggs", "451.0"]], tablefmt="grid"))
    +------+----------+
    | spam |  41.9999 |
    +------+----------+
    | eggs | 451      |
    +------+----------+

    "rst" is like a simple table format from reStructuredText; please note that reStructuredText
    accepts also "grid" tables:

    >>> print(tabulate([["spam", 41.9999], ["eggs", "451.0"]],
    ...                ["strings", "numbers"], "rst"))
    =========  =========
    strings      numbers
    =========  =========
    spam         41.9999
    eggs        451
    =========  =========

    >>> print(tabulate([["spam", 41.9999], ["eggs", "451.0"]], tablefmt="rst"))
    ====  ========
    spam   41.9999
    eggs  451
    ====  ========

    Number parsing
    --------------
    By default, anything which can be parsed as a number is a number. This ensures numbers
    represented as strings are aligned properly. This can lead to weird results for particular
    strings such as specific git SHAs e.g. "42992e1" will be parsed into the number 429920 and
    aligned as such.

    To completely disable number parsing (and alignment), use `disableNumparse=True`. For more fine
    grained control, a list column indices is used to disable number parsing only on those columns
    e.g. `disableNumparse=[0, 2]` would disable number parsing only on the first and third columns.

    Column Widths and Auto Line Wrapping
    ------------------------------------
    Tabulate will, by default, set the width of each column to the length of the longest element in
    that column. However, in situations where fields are expected to reasonably be too long to look
    good as a single line, tabulate can help automate word wrapping long fields for you. Use the
    parameter `maxcolwidth` to provide a list of maximal column widths

    >>> print(tabulate( \
          [('1', 'John Smith', \
            'This is a rather long description that might look better if it is wrapped a bit')], \
          headers=("Issue Id", "Author", "Description"), \
          maxcolwidths=[None, None, 30], \
          tablefmt="grid"  \
        ))
    +------------+------------+-------------------------------+
    |   Issue Id | Author     | Description                   |
    +============+============+===============================+
    |          1 | John Smith | This is a rather long         |
    |            |            | description that might look   |
    |            |            | better if it is wrapped a bit |
    +------------+------------+-------------------------------+

    Header column width can be specified in a similar way using `maxheadercolwidth`.
    """
    if tabular_data is None:
        tabular_data = []

    listOfLists, headers, headersPad = _normalizeTabularData(
        tabular_data, headers, showindex=showindex
    )
    listOfLists, separatingLines = _removeSeparatingLines(listOfLists)

    if maxcolwidths is not None:
        if len(listOfLists):
            numCols = len(listOfLists[0])
        else:
            numCols = 0
        if isinstance(maxcolwidths, int):  # Expand scalar for all columns
            maxcolwidths = _expandIterable(maxcolwidths, numCols, maxcolwidths)
        else:  # Ignore col width for any 'trailing' columns
            maxcolwidths = _expandIterable(maxcolwidths, numCols, None)

        numparses = _expandNumparse(disableNumparse, numCols)
        listOfLists = _wrapTextToColwidths(
            listOfLists, maxcolwidths, numparses=numparses
        )

    if maxheadercolwidths is not None:
        numCols = len(listOfLists[0])
        if isinstance(maxheadercolwidths, int):  # Expand scalar for all columns
            maxheadercolwidths = _expandIterable(
                maxheadercolwidths, numCols, maxheadercolwidths
            )
        else:  # Ignore col width for any 'trailing' columns
            maxheadercolwidths = _expandIterable(maxheadercolwidths, numCols, None)

        numparses = _expandNumparse(disableNumparse, numCols)
        headers = _wrapTextToColwidths(
            [headers], maxheadercolwidths, numparses=numparses
        )[0]

    # empty values in the first column of RST tables should be escaped (issue #82)
    # "" should be escaped as "\\ " or ".."
    if tablefmt == "rst":
        listOfLists, headers = _rstEscapeFirstColumn(listOfLists, headers)

    # PrettyTable formatting does not use any extra padding. Numbers are not parsed and are treated
    # the same as strings for alignment. Check if pretty is the format being used and override the
    # defaults so it does not impact other formats.
    min_padding = MIN_PADDING
    if tablefmt == "pretty":
        min_padding = 0
        disableNumparse = True
        numalign = "center" if numalign == _DEFAULT_ALIGN else numalign
        stralign = "center" if stralign == _DEFAULT_ALIGN else stralign
    else:
        numalign = "decimal" if numalign == _DEFAULT_ALIGN else numalign
        stralign = "left" if stralign == _DEFAULT_ALIGN else stralign

    # optimization: look for ANSI control codes once, enable smart width functions only if a control
    # code is found
    #
    # convert the headers and rows into a single, tab-delimited string ensuring that any bytestrings
    # are decoded safely (i.e. errors ignored)
    plain_text = "\t".join(
        chain(
            # headers
            map(_toStr, headers),
            # rows: chain the rows together into a single iterable after mapping the bytestring
            # conversino to each cell value
            chain.from_iterable(map(_toStr, row) for row in listOfLists),
        )
    )

    hasInvisible = _ansiCodes.search(plain_text) is not None

    if (
        not isinstance(tablefmt, TableFormat)
        and tablefmt in multiline_formats
        and _isMultiline(plain_text)
    ):
        tablefmt = multiline_formats.get(tablefmt, tablefmt)
        isMultiline = True
    else:
        isMultiline = False
    widthFn = _chooseWidthFn(hasInvisible, isMultiline)

    # format rows and columns, convert numeric values to strings
    cols = list(izip_longest(*listOfLists))
    numparses = _expandNumparse(disableNumparse, len(cols))
    coltypes = [_columnType(col, numparse=np) for col, np in zip(cols, numparses)]
    if isinstance(floatfmt, str):
        # old version: just duplicate the string to use in each column
        floatFormats = len(cols) * [floatfmt]
    else:  # if floatfmt is list, tuple etc we have one per column
        floatFormats = list(floatfmt)
        if len(floatFormats) < len(cols):
            floatFormats.extend((len(cols) - len(floatFormats)) * [_DEFAULT_FLOATFMT])
    if isinstance(intfmt, str):
        # old version: just duplicate the string to use in each column
        intFormats = len(cols) * [intfmt]
    else:  # if intfmt is list, tuple etc we have one per column
        intFormats = list(intfmt)
        if len(intFormats) < len(cols):
            intFormats.extend((len(cols) - len(intFormats)) * [_DEFAULT_INTFMT])
    if isinstance(missingval, str):
        missingVals = len(cols) * [missingval]
    else:
        missingVals = list(missingval)
        if len(missingVals) < len(cols):
            missingVals.extend((len(cols) - len(missingVals)) * [_DEFAULT_MISSINGVAL])
    cols = [
        [_format(v, ct, flFmt, intFmt, missV, hasInvisible) for v in c]
        for c, ct, flFmt, intFmt, missV in zip(
            cols, coltypes, floatFormats, intFormats, missingVals
        )
    ]

    # align columns
    # first set global alignment
    if colglobalalign is not None:  # if global alignment provided
        aligns = [colglobalalign] * len(cols)
    else:  # default
        aligns = [numalign if ct in [int, float] else stralign for ct in coltypes]

    # then specific alignements
    if colalign is not None:
        assert isinstance(colalign, Iterable)
        if isinstance(colalign, str):
            warnings.warn(
                f"As a string, `colalign` is interpreted as {[c for c in colalign]}. Did you "
                + f'mean `colglobalalign = "{colalign}"` or `colalign = ("{colalign}",)`?',
                stacklevel=2,
            )
        for idx, align in enumerate(colalign):
            if not idx < len(aligns):
                break
            elif align != "global":
                aligns[idx] = align
    minwidths = (
        [widthFn(h) + min_padding for h in headers] if headers else [0] * len(cols)
    )
    cols = [
        _alignColumn(c, a, minw, hasInvisible, isMultiline)
        for c, a, minw in zip(cols, aligns, minwidths)
    ]

    alignsHeaders = None
    if headers:
        # align headers and add headers
        tCols = cols or [[""]] * len(headers)
        # first set global alignment
        if headersglobalalign is not None:  # if global alignment provided
            alignsHeaders = [headersglobalalign] * len(tCols)
        else:  # default
            alignsHeaders = aligns or [stralign] * len(headers)
        # then specific header alignements
        if headersalign is not None:
            assert isinstance(headersalign, Iterable)
            if isinstance(headersalign, str):
                warnings.warn(
                    f"As a string, `headersalign` is interpreted as {[c for c in headersalign]}. "
                    + f'Did you mean `headersglobalalign = "{headersalign}"` or `headersalign = '
                    + f'("{headersalign}",)`?',
                    stacklevel=2,
                )
            for idx, align in enumerate(headersalign):
                hidx = headersPad + idx
                if not hidx < len(alignsHeaders):
                    break
                elif align == "same" and hidx < len(aligns):  # same as column align
                    alignsHeaders[hidx] = aligns[hidx]
                elif align != "global":
                    alignsHeaders[hidx] = align
        minwidths = [
            max(minw, max(widthFn(cl) for cl in c)) for minw, c in zip(minwidths, tCols)
        ]
        headers = [
            _alignHeader(h, a, minw, widthFn(h), isMultiline, widthFn)
            for h, a, minw in zip(headers, alignsHeaders, minwidths)
        ]
        rows = list(zip(*cols))
    else:
        minwidths = [max(widthFn(cl) for cl in c) for c in cols]
        rows = list(zip(*cols))

    if not isinstance(tablefmt, TableFormat):
        tablefmt = _table_formats.get(tablefmt, _table_formats["simple"])

    ra_default = rowalign if isinstance(rowalign, str) else None
    rowaligns = _expandIterable(rowalign, len(rows), ra_default)
    _reinsertSeparatingLines(rows, separatingLines)

    return _formatTable(
        tablefmt,
        headers,
        alignsHeaders,
        rows,
        minwidths,
        aligns,
        isMultiline,
        rowaligns=rowaligns,
    )


def _expandNumparse(disableNumparse, columnCount):
    """
    Return a list of bools of length `columnCount` which indicates whether number parsing should be
    used on each column.

    If `disableNumparse` is a list of indices, each of those indices are False, and everything else
    is True. If `disableNumparse` is a bool, then the returned list is all the same.
    """
    if isinstance(disableNumparse, Iterable):
        numparses = [True] * columnCount
        for index in disableNumparse:
            numparses[index] = False
        return numparses
    else:
        return [not disableNumparse] * columnCount


def _expandIterable(original, numDesired, default):
    """
    Expands the `original` argument to return a return a list of length `numDesired`. If `original`
    is shorter than `numDesired`, it will be padded with the value in `default`.

    If `original` is not a list to begin with (i.e. scalar value) a list of length `numDesired`
    completely populated with `default will be returned
    """
    if isinstance(original, Iterable) and not isinstance(original, str):
        return original + [default] * (numDesired - len(original))
    else:
        return [default] * numDesired


def _padRow(cells, padding):
    if cells:
        pad = " " * padding
        paddedCells = [pad + cell + pad for cell in cells]
        return paddedCells
    else:
        return cells


def _buildSimpleRow(paddedCells, rowfmt):
    """Format row according to DataRow format without padding."""
    begin, sep, end = rowfmt
    return (begin + sep.join(paddedCells) + end).rstrip()


def _buildRow(paddedCells, colwidths, colaligns, rowfmt):
    """Return a string which represents a row of data cells."""
    if not rowfmt:
        return None
    if hasattr(rowfmt, "__call__"):
        return rowfmt(paddedCells, colwidths, colaligns)
    else:
        return _buildSimpleRow(paddedCells, rowfmt)


def _appendBasicRow(lines, paddedCells, colwidths, colaligns, rowfmt, rowalign=None):
    # NOTE: rowalign is ignored and exists for api compatibility with _appendMultilineRow
    lines.append(_buildRow(paddedCells, colwidths, colaligns, rowfmt))
    return lines


def _alignCellVeritically(textLines, numLines, columnWidth, rowAlignment):
    delta_lines = numLines - len(textLines)
    blank = [" " * columnWidth]
    if rowAlignment == "bottom":
        return blank * delta_lines + textLines
    elif rowAlignment == "center":
        topDelta = delta_lines // 2
        bottom_delta = delta_lines - topDelta
        return topDelta * blank + textLines + bottom_delta * blank
    else:
        return textLines + blank * delta_lines


def _appendMultilineRow(
    lines, paddedMultilineCells, padded_widths, colaligns, rowfmt, pad, rowalign=None
):
    colwidths = [w - 2 * pad for w in padded_widths]
    cells_lines = [c.splitlines() for c in paddedMultilineCells]
    nlines = max(map(len, cells_lines))  # number of lines in the row

    cells_lines = [
        _alignCellVeritically(cl, nlines, w, rowalign)
        for cl, w in zip(cells_lines, colwidths)
    ]
    linesCells = [[cl[i] for cl in cells_lines] for i in range(nlines)]
    for ln in linesCells:
        padded_ln = _padRow(ln, pad)
        _appendBasicRow(lines, padded_ln, colwidths, colaligns, rowfmt)
    return lines


def _build_line(colwidths, colaligns, linefmt):
    """Return a string which represents a horizontal line."""
    if not linefmt:
        return None
    if hasattr(linefmt, "__call__"):
        return linefmt(colwidths, colaligns)
    else:
        begin, fill, sep, end = linefmt
        cells = [fill * w for w in colwidths]
        return _buildSimpleRow(cells, (begin, sep, end))


def _appendLine(lines, colwidths, colaligns, linefmt):
    lines.append(_build_line(colwidths, colaligns, linefmt))
    return lines


def _formatTable(
    fmt, headers, headersaligns, rows, colwidths, colaligns, isMultiline, rowaligns
):
    """Produce a plain-text representation of the table."""
    lines = []
    hidden = fmt.withHeaderHide if (headers and fmt.withHeaderHide) else []
    pad = fmt.padding
    headerrow = fmt.headerrow

    padded_widths = [(w + 2 * pad) for w in colwidths]
    if isMultiline:
        pad_row = lambda row, _: row
        append_row = partial(_appendMultilineRow, pad=pad)
    else:
        pad_row = _padRow
        append_row = _appendBasicRow

    padded_headers = pad_row(headers, pad)
    padded_rows = [pad_row(row, pad) for row in rows]

    if fmt.lineabove and "lineabove" not in hidden:
        _appendLine(lines, padded_widths, colaligns, fmt.lineabove)

    if padded_headers:
        append_row(lines, padded_headers, padded_widths, headersaligns, headerrow)
        if fmt.linebelowheader and "linebelowheader" not in hidden:
            _appendLine(lines, padded_widths, colaligns, fmt.linebelowheader)

    if padded_rows and fmt.linebetweenrows and "linebetweenrows" not in hidden:
        # initial rows with a line below
        for row, ralign in zip(padded_rows[:-1], rowaligns):
            append_row(
                lines, row, padded_widths, colaligns, fmt.datarow, rowalign=ralign
            )
            _appendLine(lines, padded_widths, colaligns, fmt.linebetweenrows)
        # the last row without a line below
        append_row(
            lines,
            padded_rows[-1],
            padded_widths,
            colaligns,
            fmt.datarow,
            rowalign=rowaligns[-1],
        )
    else:
        separating_line = (
            fmt.linebetweenrows
            or fmt.linebelowheader
            or fmt.linebelow
            or fmt.lineabove
            or Line("", "", "", "")
        )
        for row in padded_rows:
            # test to see if either the 1st column or the 2nd column (account for showindex) has the
            # SEPARATING_LINE flag
            if _isSeparatingLine(row):
                _appendLine(lines, padded_widths, colaligns, separating_line)
            else:
                append_row(lines, row, padded_widths, colaligns, fmt.datarow)

    if fmt.linebelow and "linebelow" not in hidden:
        _appendLine(lines, padded_widths, colaligns, fmt.linebelow)

    if headers or rows:
        return "\n".join(lines)
    else:  # a completely empty table
        return ""


class _CustomTextWrap(textwrap.TextWrapper):
    """A custom implementation of CPython's textwrap.TextWrapper. This supports both wide characters
    (Korea, Japanese, Chinese) - including mixed string.
    """

    def __init__(self, *args, **kwargs):
        self._active_codes = []
        self.max_lines = None  # For python2 compatibility
        textwrap.TextWrapper.__init__(self, *args, **kwargs)

    @staticmethod
    def _len(item):
        """Custom len that gets console column width for wide and non-wide characters as well as
        ignores color codes.
        """
        stripped = _stripAnsi(item)
        return len(stripped)

    def _updateLines(self, lines, new_line):
        """Adds a new line to the list of lines the text is being wrapped into.

        This function will also track any ANSI color codes in this string as well as add any colors
        from previous lines order to preserve the same formatting as a single unwrapped string.
        """
        code_matches = [x for x in _ansiCodes.finditer(new_line)]
        color_codes = [
            code.string[code.span()[0] : code.span()[1]] for code in code_matches
        ]

        # Add color codes from earlier in the unwrapped line, and then track any new ones we add.
        new_line = "".join(self._active_codes) + new_line

        for code in color_codes:
            if code != _ansiColorResetCode:
                self._active_codes.append(code)
            else:  # A single reset code resets everything
                self._active_codes = []

        # Always ensure each line is color terminted if any colors are still active, otherwise
        # colors will bleed into other cells on the console
        if len(self._active_codes) > 0:
            new_line = new_line + _ansiColorResetCode

        lines.append(new_line)
