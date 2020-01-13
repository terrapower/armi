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
"""
Utility classes and functions for manipulating text files.
"""
import os
import re
import io
import pathlib
from typing import List, Tuple, Union, Optional

import ruamel
from ruamel.yaml.error import FileMark

from armi import runLog
from armi.utils import directoryChangers
from armi.localization import strings


_INCLUDE_CTOR = False


def registerYamlIncludeConstructor():
    """
    Register a custom !include tag constructor with ruamel.yaml.

    This teaches the ruamel.yaml parser to interpret ``!include`` tags as essentially a
    textual inclusion. This is somewhat of a weird feature, as tags are typically used
    to represent custom objects in YAML, rather than to directly manipulate the YAML
    itself. As such it leads to interesting interactions with the yamlize library that
    we use to do much of our input processing.

    See Also
    --------
    resolveMarkupInclusions
    """
    global _INCLUDE_CTOR
    if _INCLUDE_CTOR:
        # already done; short circuit
        return

    def includeCtor(loader, node):
        y = loader.loader
        typ = getattr(y, "typ", None)
        pure = getattr(y, "pure", None)
        yaml = ruamel.yaml.YAML(typ=typ, pure=pure)
        path = pathlib.Path(os.getcwd()) / node.value
        return yaml.load(path)

    ruamel.yaml.Constructor.add_constructor("!include", includeCtor)
    ruamel.yaml.constructor.SafeConstructor.add_constructor("!include", includeCtor)
    ruamel.yaml.constructor.RoundTripConstructor.add_constructor("!include", includeCtor)

    _INCLUDE_CTOR = True


def resolveMarkupInclusions(
    src: Union[io.TextIOBase, pathlib.Path],
    typ: str = None,
    root: Optional[pathlib.Path] = None,
) -> io.StringIO:
    """
    Process a YAML stream, appropriately handling ``!include`` tags."

    This will take the passed string or file path, and attempt to parse it as YAML. In
    the process, any instances of ``!include [path]`` will be replaced with the
    appropriate contents of the ``!include`` file.

    Parameters
    ----------
    src : TextIOBase or Path
        If a Path is provided, read YAML from there. If is stream is provided, consume
        read text from the stream. If a stream is provided, ``root`` must also be
        provided.
    typ : str
        A valid parse type for the ruamel YAML library. Defaults to "rt" to preserve
        round-trip data.
    root : Optional Path
        The root directory to use for resolving relative paths in !include tags. If a
        stream is provided for ``src``, ``root`` must be provided. Otherwise, the
        directory containing the ``src`` path will be used by default.

    Notes
    -----
    This does a full (albeit not Yamlize) parse of the input YAML into the appropriate
    data structure, resolving the textual inclusions along the way. Then, the resulting
    data are re-serialized to a new YAML stream. As such, this is not super efficient.
    We do it this way because we don't have a whole lot of control over how yamlize
    handles the parsing. For instance, yamlize will not honor the custom !include tag.
    This sort of makes sense, as yamlize and YAML tags are two distinct approaches to
    representing custom objects in YAML.

    For now, this is not handling cross-document anchors and aliases, which sucks. We
    may wish to resolve this, but methods to do so are rather complex and not without
    their own drawbacks. There is some pure gold on that topic here:
    https://stackoverflow.com/questions/44910886/pyyaml-include-file-and-yaml-aliases-anchors-references
    """
    registerYamlIncludeConstructor()

    if isinstance(src, pathlib.Path):
        root = root or src.parent.absolute()
    else:
        root = root or pathlib.Path(os.getcwd()).absolute()

    with directoryChangers.DirectoryChanger(root):
        yaml = ruamel.yaml.YAML(typ=typ, pure=True)
        data = yaml.load(src)

    out = io.StringIO()

    yaml.dump(data, out)
    out.seek(0)
    if isinstance(src, io.TextIOBase):
        src.seek(0)

    return out


def findYamlInclusions(
    src: Union[io.TextIOBase, pathlib.Path], root: Optional[pathlib.Path] = None
) -> List[Tuple[pathlib.Path, FileMark]]:
    """
    Return a list of paths to ``!include`` files.

    src : TextIOBase or Path
        If a Path is provided, read YAML from there. If is stream is provided, consume
        read text from the stream. If a stream is provided, ``root`` must also be
        provided.
    root : Optional Path
        The root directory to use for resolving relative paths in !include tags. If a
        stream is provided for ``src``, the current working directory is implied.
        Otherwise, the directory containing the ``src`` path will be used by default.

    This is useful for determining which files need to be copied in order to have a
    complete input, without explicitly inserting the content from ``!include`` tags.
    """
    if isinstance(src, pathlib.Path):
        root = root or src.parent.absolute()
    else:
        root = root or pathlib.Path(os.getcwd()).absolute()

    includes = []

    def includeCtor(loader, node):
        y = loader.loader
        yaml = ruamel.yaml.YAML(typ=y.typ, pure=y.pure)
        includes.append((root / pathlib.Path(node.value), node.start_mark))
        return yaml.load(root / pathlib.Path(node.value))

    yaml = ruamel.yaml.YAML(typ="safe", pure=True)
    yaml.Constructor.add_constructor("!include", includeCtor)
    yaml.load(src)

    if isinstance(src, io.TextIOBase):
        src.seek(0)

    return includes


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
    For example, if you had a text file with consistent chuncks of information that
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
        """Add a text search for every line of the file, if the text is found the specified error will be raised.

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
        """Add a pattern search for every line of the file, if the pattern is found the specified error will be raised.

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
            except:  # pylint: disable=bare-except
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
            Boolean inidcating whether or not the pattern matched
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
            Boolean inidcating whether or not the pattern matched
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
            Boolean inidcating whether or not the pattern matched
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
    """
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
    For example, if you had a text file with consistent chuncks of information that
    always started with the same text followed by information, you could do something
    like this:

    >>> with SequentialReader('somefile') as sr:
    ...     data = []
    ...     while sr.searchForText('start of data chunk'):
    ...         # this needs to repeat for as many chunks as there are.
    ...         if sr.searchForPatternOnNextLine('some-(?P<data>\w+)-pattern'):
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

    scipat = strings.SCIENTIFIC_PATTERN
    number = strings.FLOATING_PATTERN
    decimal = strings.DECIMAL_PATTERN

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
                # note: Could make it check before instantiating...
                runLog.warning(
                    'Cannot open file "{0}" for text processing.\n'
                    "CWD is {1}".format(fname, os.getcwd())
                )
        if not highMem:
            # keep the file on disk, read as necessary
            self.f = f
        else:
            # read all of f into memory and set up a list that remembers where it is.
            self.f = SmartList(f)

    def reset(self):
        r"""rewinds the file so you can search through it again"""
        self.f.seek(0)

    def __repr__(self):
        return "<Text file at {0}>".format(self.f.name)

    def errorChecking(self, checkForErrors):
        self.eChecking = checkForErrors

    def checkErrors(self, line):
        pass

    def fsearch(self, pattern, msg=None, killOn=None, textFlag=False):
        r"""
        Searches file f for pattern and displays msg when found. Returns line in which
        pattern is found or FALSE if no pattern is found.
        Stops searching if finds killOn first

        If you specify textFlag=True, the search won't use a regular expression (and
        can't). The basic result is you get less powerful matching capabilities at a
        huge speedup (10x or so probably, but that's just a guess.) pattern and killOn
        must be pure text if you do this.
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


class SmartList:
    r"""A list that does stuff like files do i.e. remembers where it was, can seek, etc.
    Actually this is pretty slow. so much for being smart. nice idea though. """

    def __init__(self, f):
        self.lines = f.readlines()
        self.position = 0
        self.name = f.name
        self.length = len(self.lines)

    def __getitem__(self, index):
        return self.lines[index]

    def __setitem__(self, index, line):
        self.lines[index] = line

    def next(self):
        if self.position >= self.length:
            self.position = 0
            raise StopIteration
        else:
            c = self.position
            self.position += 1
            return self.lines[c]

    def __iter__(self):
        return self

    def __len__(self):
        return len(self.lines)

    def seek(self, line):
        self.position = line

    def close(self):
        pass
