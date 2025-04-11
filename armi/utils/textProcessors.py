# Copyright 2019 TerraPower, LLC
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
"""Utility classes and functions for manipulating text files."""
import io
import os
import pathlib
import re
from typing import List, Optional, TextIO, Tuple, Union

from armi import runLog

_INCLUDE_CTOR = False
_INCLUDE_RE = re.compile(r"^([^#]*\s+)?!include\s+(.*)\n?$")
_INDENT_RE = re.compile(r"^[\s\-\?:]*([^\s\-\?:].*)?$")

# String constants
SCIENTIFIC_PATTERN = r"[+-]?\d*\.\d+[eEdD][+-]\d+"
"""
Matches:
* code:` 1.23e10`
* code:`-1.23Ee10`
* code:`+1.23d10`
* code:`  .23D10`
* code:` 1.23e-10`
* code:` 1.23e+1`
"""

FLOATING_PATTERN = r"[+-]?\d+\.*\d*"
"""Matches 1, 100, 1.0, -1.2, +12.234"""

DECIMAL_PATTERN = r"[+-]?\d*\.\d+"
"""Matches .1, 1.213423, -23.2342, +.023"""


class FileMark:
    def __init__(self, fName, line, column, relativeTo):
        self.path = fName
        self.line = line
        self.column = column
        # if the path is relative, where is it relative to? We need this to be able to
        # normalize relative paths to a root file.
        self.relativeTo = relativeTo

    def __str__(self):
        return "{}, line {}, column {}".format(self.path, self.line, self.column)


def _processIncludes(
    src: Union[TextIO, pathlib.Path],
    out,
    includes: List[Tuple[pathlib.Path, FileMark]],
    root: pathlib.Path,
    indentation=0,
    currentFile="<stream>",
):
    """
    This is the workhorse of ``resolveMarkupInclusions`` and friends.

    Recursively inserts the contents of !included YAML files into the output stream,
    keeping track of indentation and a list of included files along the way.
    """

    def _beginningOfContent(line: str) -> int:
        """
        Return the position of the first "content" character.

        This follows the YAML spec at https://yaml.org/spec/current.html#id2519916

        In short, it will return the position of the first character that is not
        whitespace or one of the special "block collection" markers ("-", "?", and ":")
        """
        m = _INDENT_RE.match(line)
        if m and m.group(1) is not None:
            return m.start(1)
        else:
            return 0

    indentSpace = " " * indentation
    if hasattr(src, "getvalue"):
        # assume stringIO
        lines = [ln + "\n" for ln in src.getvalue().split("\n")]
    else:
        # assume file stream or TextIOBase, and it has a readlines attr
        lines = src.readlines()
    for i, line in enumerate(lines):
        leadingSpace = indentSpace if i > 0 else ""
        m = _INCLUDE_RE.match(line)
        if m:
            # this line has an !include on it
            if m.group(1) is not None:
                out.write(leadingSpace + m.group(1))
            fName = pathlib.Path(os.path.expandvars(m.group(2)))
            path = root / fName
            if not path.exists():
                raise ValueError(
                    "The !included file, `{}` does not exist from {}!".format(
                        fName, root
                    )
                )
            includes.append((fName, FileMark(currentFile, i, m.start(2), root)))

            with open(path, "r") as includedFile:
                firstCharacterPos = _beginningOfContent(line)
                newIndent = indentation + firstCharacterPos
                _processIncludes(
                    includedFile,
                    out,
                    includes,
                    path.parent,
                    indentation=newIndent,
                    currentFile=path,
                )
        else:
            out.write(leadingSpace + line)


def resolveMarkupInclusions(
    src: Union[TextIO, pathlib.Path], root: Optional[pathlib.Path] = None
) -> io.StringIO:
    r"""
    Process a text stream, appropriately handling ``!include`` tags.

    This will take the passed IO stream or file path, replacing any instances of
    ``!include [path]`` with the appropriate contents of the ``!include`` file.

    What is returned is a new text stream, containing the contents of all of the files
    stitched together.

    Parameters
    ----------
    src : StringIO or TextIOBase/Path
        If a Path is provided, read text from there. If is stream is provided, consume
        text from the stream. If a stream is provided, ``root`` must also be provided.
    root : Optional Path
        The root directory to use for resolving relative paths in !include tags. If a
        stream is provided for ``src``, ``root`` must be provided. Otherwise, the
        directory containing the ``src`` path will be used by default.

    Notes
    -----
    While the use of ``!include`` appears as though it would invoke some sort of special
    custom YAML constructor code, this does not do that. Processing these inclusions as
    part of the document parsing/composition that comes with ruamel.yaml could
    work, but has a number of prohibitive drawbacks (or at least reasons why it might
    not be worth doing). Using a custom constructor is more-or-less supported by
    ruamel.yaml (which we do use, as it is what underpins the yamlize package), but it
    carries limitations about how anchors and aliases can cross included-file
    boundaries. Getting around this requires either monkey-patching ruamel.yaml, or
    subclassing it, which in turn would require monkey-patching yamlize.

    Instead, we treat the ``!include``\ s as a sort of pre-processor directive, which
    essentially pastes the contents of the ``!include``\ d file into the location of the
    ``!include``. The result is a text stream containing the entire contents, with all
    ``!include``\ s resolved. The only degree of sophistication lies in how indentation
    is handled; since YAML cares about indentation to keep track of object hierarchy,
    care must be taken that the included file contents are indented appropriately.

    To precisely describe how the indentation works, it helps to have some definitions:

     - Included file: The file specified in the ``!include [Included file]``
     - Including line: The line that actually contains the ``!include [Included file]``
     - Meaningful YAML content: Text in a YAML file that is not either indentation or a
       special character like "-", ":" or "?".

    The contents of the included file will be indented such that that the first
    character of each line in the included file will be found at the first column in the
    including line that contains meaningful YAML content. The only exception is the
    first line of the included file, which starts at the location of the ``!include``
    itself and is not deliberately indented.

    In the future, we may wish to do the more sophisticated processing of the
    ``!include``\ s as part of the YAML parse. For future reference, there is some pure
    gold on that topic here:
    https://stackoverflow.com/questions/44910886/pyyaml-include-file-and-yaml-aliases-anchors-references
    """
    return _resolveMarkupInclusions(src, root)[0]


def _getRootFromSrc(
    src: Union[TextIO, pathlib.Path], root: Optional[pathlib.Path]
) -> pathlib.Path:
    if isinstance(src, pathlib.Path):
        root = root or src.parent.absolute()
    elif isinstance(src, io.TextIOBase):
        if root is None:
            raise ValueError("A stream was provided without a root directory.")
    else:
        raise TypeError("Unsupported source type: `{}`!".format(type(src)))

    return root


def findYamlInclusions(
    src: Union[TextIO, pathlib.Path], root: Optional[pathlib.Path] = None
) -> List[Tuple[pathlib.Path, FileMark]]:
    """
    Return a list containing all of the !included YAML files from a root file.

    This will attempt to "normalize" relative paths to the passed root. If that is not
    possible, then an absolute path will be used instead. For example, if a file (A)
    !includes another file (B) by an absolute path, which in turn !includes more files
    relative to (B), all of (B)'s relative includes will be turned into absolute paths
    from the perspective of the root file (A).
    """
    includes = _resolveMarkupInclusions(src, root)[1]
    root = _getRootFromSrc(src, root)
    normalizedIncludes = []

    for path, mark in includes:
        if not path.is_absolute():
            try:
                path = (mark.relativeTo / path).relative_to(root or os.getcwd())
            except ValueError:
                # Can't make a relative path. IMO, pathlib gives up a little too early,
                # but we still probably want to decay to absolute paths if the files
                # aren't in the same tree.
                path = (mark.relativeTo / path).absolute()

        normalizedIncludes.append((path, mark))

    return normalizedIncludes


def _resolveMarkupInclusions(
    src: Union[TextIO, pathlib.Path], root: Optional[pathlib.Path] = None
) -> Tuple[io.StringIO, List[Tuple[pathlib.Path, FileMark]]]:
    root = _getRootFromSrc(src, root)

    if isinstance(src, pathlib.Path):
        # this is inefficient, but avoids having to play with io buffers
        with open(src, "r") as rootFile:
            src = io.StringIO(rootFile.read())

    out = io.StringIO()
    includes = []
    _processIncludes(src, out, includes, root)

    out.seek(0)
    # be kind; rewind
    src.seek(0)

    return out, includes


class SequentialReader:
    r"""
    Fast sequential reader that must be used within a with statement.

    Attributes
    ----------
    line : str
        value of the current line
    match : re.match
        value of the current match

    Notes
    -----
    This reader will sequentially search a file for a regular expression pattern or
    string depending on the method used. When the pattern/string is matched/found, the
    reader will stop, return :code:`True`, and set the attributes :code:`line` and
    :code:`match`.

    This pattern makes it easy to cycle through repetitive output in a very fast manner.
    For example, if you had a text file with consistent chunks of information that
    always started with the same text followed by information, you could do something
    like this:

    >>> with SequentialReader('somefile') as sr:
    ...     data = []
    ...     while sr.searchForText('start of data chunk'):
    ...         # this needs to repeat for as many chunks as there are.
    ...         if sr.searchForPatternOnNextLine('some-(?P<data>\w+)-pattern'):
    ...             data.append(sr.match['data'])
    """

    def __init__(self, filePath):
        self._filePath = filePath
        self._stream = None
        self.line = ""
        self.match = None
        self._textErrors = []
        self._textWarnings = []
        self._patternErrors = []
        self.ignoreAllErrors = False

    def issueWarningOnFindingText(self, text, warning):
        """Add a text search for every line of the file, if the text is found the specified warning will be issued.

        This is important for determining if issues occurred while searching for text.

        Parameters
        ----------
        text : str
            text to find within the file
        warning : str
            An warning message to issue.

        See Also
        --------
        raiseErrorOnFindingText
        raiseErrorOnFindingPattern
        """
        self._textWarnings.append((text, warning))

    def raiseErrorOnFindingText(self, text, error):
        """Add a text search for every line of the file, if the text is found the specified error
        will be raised.

        This is important for determining if errors occurred while searching for text.

        Parameters
        ----------
        text : str
            text to find within the file

        error : Exception
            An exception to raise.

        See Also
        --------
        raiseErrorOnFindingPattern
        """
        self._textErrors.append((text, error))

    def raiseErrorOnFindingPattern(self, pattern, error):
        """Add a pattern search for every line of the file, if the pattern is found the specified
        error will be raised.

        This is important for determining if errors occurred while searching for text.

        Parameters
        ----------
        pattern : str
            regular expression pattern

        error : Exception
            An exception to raise.

        See Also
        --------
        raiseErrorOnFindingText
        """
        self._patternErrors.append((re.compile(pattern), error))

    def __repr__(self):
        return "<{} {} {}>".format(
            self.__class__.__name__,
            self._filePath,
            "open" if self._stream is not None else "closed",
        )

    def __enter__(self):
        if not os.path.exists(self._filePath):
            raise OSError("Cannot open non-existing file {}".format(self._filePath))
        self._stream = open(self._filePath, "r")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # if checking for errors, we need to keep reading
        if (
            exc_type is not None
            and not self.ignoreAllErrors
            and (self._patternErrors or self._textErrors)
        ):
            while self._readLine():  # all lines have '\n' terminators
                pass

        if self._stream is not None:
            try:
                self._stream.close()
            except Exception:
                # We really don't care if anything fails here, plus an exception in exit is ignored anyway
                pass
        self._stream = None

    def searchForText(self, text):
        """Search the file for the next occurrence of :code:`text`, and set the
        :code:`self.line` attribute to that line's value if it matched.

        Notes
        -----
        This will search the file line by line until it finds the text.  This sets the
        attribute :code:`self.line`. If the previous :code:`_searchFor*` method did not
        match, the last line it did not match will be searched first.

        Returns
        -------
        matched : bool
            Boolean indicating whether or not the pattern matched
        """
        self.match = None
        while True:
            if text in self.line:
                return True
            self.line = self._readLine()
            if self.line == "":
                break
        return False

    def searchForPattern(self, pattern):
        """Search the file for the next occurece of :code:`pattern` and set the :code:`self.line` attribute to that
        line's value if it matched.

        Notes
        -----
        This will search the file line by line until it finds the pattern.
        This sets the attribute :code:`self.line`. If the previous :code:`_searchFor*`
        method did not match, the last line it did not match will be searched first.

        Returns
        -------
        matched : bool
            Boolean indicating whether or not the pattern matched
        """
        while True:
            self.match = re.search(pattern, self.line)
            if self.match is not None:
                return True
            self.line = self._readLine()
            if self.line == "":
                break
        return False

    def searchForPatternOnNextLine(self, pattern):
        """Search the next line for a given pattern, and set the :code:`self.line` attribute to that line's value if it
        matched.

        Notes
        -----
        This sets the attribute :code:`self.line`. If the previous :code:`_searchFor*`
        method did not match, the last line it did not match will be searched first.

        Returns
        -------
        matched : bool
            Boolean indicating whether or not the pattern matched
        """
        self.match = re.search(pattern, self.line)
        if self.match is None:
            self.line = self._readLine()
            self.match = re.search(pattern, self.line)
        return self.match is not None

    def _readLine(self):
        line = self._stream.readline()
        if not self.ignoreAllErrors:
            for text, error in self._textErrors:
                if text in line:
                    raise error
            for text, warning in self._textWarnings:
                if text in line:
                    runLog.warning(warning)
            for regex, error in self._patternErrors:
                if regex.match(line):
                    raise error
        return line

    def consumeLine(self):
        """Consumes the line.

        This is necessary when searching for the same pattern repetitively, because
        otherwise searchForPatternOnNextLine would not work.
        """
        self.line = ""
        self.match = None


class SequentialStringIOReader(SequentialReader):
    r"""
    Fast sequential reader that must be used within a with statement.

    Attributes
    ----------
    line : str
        value of the current line
    match : re.match
        value of the current match

    Notes
    -----
    This reader will sequentially search a file for a regular expression pattern or
    string depending on the method used. When the pattern/string is matched/found, the
    reader will stop, return :code:`True`, and set the attributes :code:`line` and
    :code:`match`.

    This pattern makes it easy to cycle through repetitive output in a very fast manner.
    For example, if you had a text file with consistent chunks of information that
    always started with the same text followed by information, you could do something
    like this:

    >>> with SequentialReader('somefile') as sr:
    ...     data = []
    ...     while sr.searchForText('start of data chunk'):
    ...         # this needs to repeat for as many chunks as there are.
    ...         if sr.searchForPatternOnNextLine('some-(?P<data>\\w+)-pattern'):
    ...             data.append(sr.match['data'])
    """

    def __init__(self, stringIO):
        SequentialReader.__init__(self, "StringIO")
        self._stream = stringIO

    def __enter__(self):
        """
        Override to prevent trying to open/reopen a StringIO object.

        We don't need to override :code:`__exit__`, because it doesn't care if closing
        the object fails.

        """
        return self


class TextProcessor:
    """
    A general text processing object that extends python's abilities to scan through huge files.

    Use this instead of a raw file object to read data out of output files, etc.
    """

    scipat = SCIENTIFIC_PATTERN
    number = FLOATING_PATTERN
    decimal = DECIMAL_PATTERN

    def __init__(self, fname, highMem=False):
        self.eChecking = False
        # Preserve python 2-like behavior for unit tests that pass None and provide
        # their own text data (in py2, passing None to abspath yields cwd; py3 raises)
        self.fpath = os.path.dirname(os.path.abspath(fname or os.getcwd()))
        f = None
        if fname is not None:
            if os.path.exists(fname):
                f = open(fname)
            else:
                # need this not to fail for detecting when RXSUM doesn't exist, etc.
                # Note: Could make it check before instantiating...
                raise FileNotFoundError(f"{fname} does not exist.")
        self.f = f

    def reset(self):
        """Rewinds the file so you can search through it again."""
        self.f.seek(0)

    def __repr__(self):
        return "<Text file at {0}>".format(self.f.name)

    def errorChecking(self, checkForErrors):
        self.eChecking = checkForErrors

    def checkErrors(self, line):
        pass

    def fsearch(self, pattern, msg=None, killOn=None, textFlag=False):
        """
        Searches file f for pattern and displays msg when found. Returns line in which pattern is
        found or FALSE if no pattern is found. Stops searching if finds killOn first.

        If you specify textFlag=True, the search won't use a regular expression (and can't). The
        basic result is you get less powerful matching capabilities at a huge speedup (10x or so
        probably, but that's just a guess.) pattern and killOn must be pure text if you do this.
        """
        current = 0
        result = ""
        if textFlag:
            # fast, text-only mode
            for line in self.f:
                if self.eChecking:
                    self.checkErrors(line)
                if pattern in line:
                    result = line
                    break
                elif killOn and killOn in line:
                    result = ""
                    break
            else:
                result = ""
        else:
            # slower regular expression mode
            cpat = re.compile(pattern)
            if killOn:
                kpat = re.compile(killOn)
            for line in self.f:
                if self.eChecking:
                    self.checkErrors(line)
                if killOn:
                    kill = re.search(kpat, line)
                    if kill:
                        # the kill phrase was found first, so die.
                        result = ""
                        break
                current = re.search(cpat, line)
                if current:
                    if msg:
                        print(msg)
                    result = line
                    break
            if not current:
                result = ""

        return result
