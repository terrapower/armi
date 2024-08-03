# Copyright 2020 TerraPower, LLC
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
ASCII maps are little grids of letters/numbers that represent some kind of a lattice.

These are commonly used in nuclear analysis to represent core maps, pin layouts, etc.
in input files. This module reads various text and interprets them into meaningful
data structures.

We make classes for different geometries to share code. This will eventually be
expanded for various symmetries that are applicable to cores, assemblies, etc.

This is as attempted reimplementation of AsciiMaps aiming for simplicity,
though inherently this work is complex. Compared to the Previous implimentation 
this utilizes discrete functions for each aspect of the map.

Some vocabulary used here:

column, line
    column and line numbers in the actual ascii text representation. What
    you would see in a text editor.

offset
    The number of spaces needed at the beginning a line to properly orient
    the ascii representation.

i, j
    Indices in the grid itself. For Cartesian, j is like the line number,
    but in other geometries (like hex), it is a totally different
    coordinate system.

See Also
--------
armi.reactor.grids : More powerful, nestable lattices with specific dimensions
    Most input lattices eventually end up as Grid objects.
armi.reactor.blueprints.latticeBlueprint : user input of generic lattices
armi.reactor.geometry : a specific usage of lattices, for core maps

"""
# Refactored by Tyson Limato in collaboration with TerraPower, LLC
import re
from typing import Union, Callable, Literal
from armi import runLog
from armi.reactor import geometry

def getPlaceholder(placeholder: str="-"):
    return placeholder

PLACEHOLDER = "-"

# Instantiate blank Ascii map, Replaces __init__
# To manage state variables AsciiMap is a dictionary and is explicitly passed around
def createAsciiMap(type: Literal["Cartesian", "HexCornersUp", "HexFullFlatsUp", "HexFullTipsUp", "HexThirdFlatsUp"] = None) -> dict:
    """
    Create an empty Ascii map.

    This function initializes an empty ASCII map with various properties
    depending on the specified type. The map is represented as a dictionary
    with several keys to manage its state and structure.

    Parameters
    ----------
    type : {'Cartesian', 'Hex', 'HexCornersUp', 'HexFullFlatsUp', 'HexFullTipsUp', 'HexThirdFlatsUp'}, optional
        The type of ASCII map to create. If not specified, defaults to None.

    Returns
    -------
    dict
        A dictionary representing the ASCII map with the following keys:
        - asciiLines: list of list of str
            A list of lines, each containing a list of ASCII labels for each column. No blanks.
        - asciiOffsets: list of int
            A list of offset integers for each line above that will be prepended before the contents of asciiLines.
        - asciiLabelByIndices: dict
            A mapping from grid location objects to ASCII labels.
        - _spacer: str
            Individual spacing for one 'item' of ASCII.
        - _placeholder: str
            Placeholder for blank data. Also holds the size of ASCII window for each value.
        - _asciiMaxCol: int
            Maximum number of text columns in text representation.
        - _asciiMaxLine: int
            Maximum number of text lines in text representation.
        - _ijMax: int
            Maximum number of i+j indices (max(i) + max(j)), needed mostly for hex.
        - _asciiLinesOffCorner: int
            Number of ASCII lines chopped off corners.
        - _asciiType: str
            The type of ASCII map, one of {'Cartesian', 'Hex', 'HexCornersUp', 'HexFullFlatsUp', 'HexFullTipsUp', 'HexThirdFlatsUp'}.

    Raises
    ------
    ValueError
        If the provided type is not one of the valid types.
    """
    if type not in ["Cartesian", "HexCornersUp", "HexFullFlatsUp", "HexFullTipsUp", "HexThirdFlatsUp"] and type is not None:
        raise ValueError(f"Invalid type: {type}. Valid types are: Cartesian, Hex, HexCornersUp, HexFullFlatsUp, HexFullTipsUp, HexThirdFlatsUp")
    return {
        
        "asciiLines": [], 
        # A list of lines, each containing a list of ascii labels for each column. No blanks.
        "asciiOffsets": [], 
        # A list of offset integers for each line above that will be prepended before the contents of asciiLines
        "asciiLabelByIndices": {}, 
        # A mapping from grid location objects to ascii labels
        "_spacer": " ", 
        # Individual spacing for one 'item' of ascii
        "_placeholder": "-", 
        # Placeholder for blank data. Also holds the size of ascii window for each value
        "_asciiMaxCol": 0, 
        # max number of text columns in text representation
        "_asciiMaxLine": 0, 
        # max number of text lines in text representation
        "_ijMax": 0, 
        # max num of i+j indices (max(i) + max(j)), needed mostly for hex
        "_asciiLinesOffCorner": 0,
        # Number of ascii lines chopped of corners
        "_asciiType": type if type in ["Cartesian", "Hex", "HexCornersUp", "HexFullFlatsUp", "HexFullTipsUp", "HexThirdFlatsUp"] else None
    }
    
# Create ASCII Map from Formatted String
def readAscii(
        ascii_map: dict,
        text: str, 
        LinesToIndices_function: Callable, 
        makeOffsets_function: Callable,
        updateSlotSizeFromData_function: Callable,
        updateDimensionsFromAsciiLines_function: Callable
        ) -> dict:
    """
    Read ASCII representation from a string and update the ASCII map.

    This function reads an ASCII representation from a provided string,
    updates the placeholder size according to the largest item read, and
    updates various properties of the ASCII map using the provided functions.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map to be updated.
    text : str
        Custom string that describes the ASCII map of the core.
    LinesToIndices_function : Callable
        Function to convert lines to indices.
    makeOffsets_function : Callable
        Function to create offsets for the ASCII map.
    updateSlotSizeFromData_function : Callable
        Function to update the slot size from the data.
    updateDimensionsFromAsciiLines_function : Callable
        Function to update the dimensions from the ASCII lines.

    Returns
    -------
    dict
        The updated ASCII map dictionary.

    """
    text = text.strip().splitlines()
    ascii_map["asciiLines"] = []
    ascii_map["_asciiMaxCol"] = 0

    for li, line in enumerate(text):
        columns = line.split()
        ascii_map["asciiLines"].append(columns)
        if len(columns) > ascii_map["_asciiMaxCol"]:
            ascii_map["_asciiMaxCol"] = len(columns)

    ascii_map["_asciiMaxLine"] = li +1
    
    
    updateDimensionsFromAsciiLines_function(ascii_map)
    LinesToIndices_function(ascii_map)
    makeOffsets_function(ascii_map)
    updateSlotSizeFromData_function(ascii_map)
    return ascii_map

# For Human Readables
def ascii_map_to_str(ascii_map: dict) -> str:
    """
    Convert an ASCII map dictionary to a string representation.

    This function converts the ASCII map dictionary into a human-readable
    string format. It ensures that the ASCII lines and offsets are consistent
    and formats the lines according to the specified placeholder and spacer.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map to be converted to a string.
        It must contain the following keys:
        - asciiLines: list of list of str
            A list of lines, each containing a list of ASCII labels for each column.
        - asciiOffsets: list of int
            A list of offset integers for each line above that will be prepended before the contents of asciiLines.
        - _placeholder: str
            The placeholder string used for formatting.
        - _spacer: str
            The spacer string used for formatting.
        - _asciiMaxCol: int
            The maximum number of columns in the ASCII map.
        - _asciiMaxLine: int
            The maximum number of lines in the ASCII map.

    Returns
    -------
    str
        The human-readable string representation of the ASCII map.

    Raises
    ------
    ValueError
        If the ASCII lines are empty or if the number of offsets does not match the number of lines.
    """
    # Check if the asciiLines are empty
    if not ascii_map["asciiLines"]:
        raise ValueError("Cannot write ASCII map before ASCII lines are processed.")
    
    # Check if the number of offsets matches the number of lines
    if len(ascii_map["asciiOffsets"]) != len(ascii_map["asciiLines"]):
        runLog.error(f"AsciiLines: {ascii_map['asciiLines']}")
        runLog.error(f"Offsets: {ascii_map['asciiOffsets']}")
        raise ValueError(
                f"Inconsistent lines ({len(ascii_map['asciiLines'])}) "
                f"and offsets ({len(ascii_map['asciiOffsets'])})"
            )
    
    txt = ""
    fmt = f"{{val:{len(ascii_map['_placeholder'])}s}}"
    
    # Reverse the lines and offsets
    lines = list(reversed(ascii_map["asciiLines"]))
    offsets = list(reversed(ascii_map["asciiOffsets"]))
    
    for offset, line in zip(offsets, lines):
        data = [fmt.format(val=v) for v in line]
        line = ascii_map["_spacer"] * offset + ascii_map["_spacer"].join(data) + "\n"
        txt += line
    
    return txt

# Write output Stream
def writeAscii(ascii_map: dict, stream):
    """
    Write out the ASCII representation to a stream.

    This function converts the ASCII map dictionary into a human-readable
    string format and writes it to the provided stream. If the ASCII map type
    is either "HexThirdFlatsUp" or "HexFullTipsUp", the lines are reversed
    before writing.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map to be written. It must contain
        the necessary keys for conversion, including:
        - asciiLines: list of list of str
            A list of lines, each containing a list of ASCII labels for each column.
        - asciiOffsets: list of int
            A list of offset integers for each line above that will be prepended before the contents of asciiLines.
        - _placeholder: str
            The placeholder string used for formatting.
        - _spacer: str
            The spacer string used for formatting.
        - _asciiType: str
            The type of ASCII map, which determines if lines need to be reversed.
    stream : file-like object
        The stream that the ASCII representation will be written. This can be
        any object with a `write` method, such as a file or an in-memory buffer.

    Raises
    ------
    ValueError
        If the ASCII lines are empty or if the number of offsets does not match the number of lines.
    """
    out = ascii_map_to_str(ascii_map)

    if ascii_map["_asciiType"] == "HexThirdFlatsUp" or ascii_map["_asciiType"] == "HexFullTipsUp":
        out = reverse_lines(out)
    stream.write(out)

def updateSlotSizeFromData(ascii_map: dict):
        """
        Update the slot size for writing based on the data in the ASCII map.

        This function calculates the maximum length of the labels in the
        `asciiLabelByIndices` dictionary and updates the `_spacer` and
        `_placeholder` values in the `ascii_map` dictionary accordingly.

        Parameters
        ----------
        ascii_map : dict
            The dictionary representing the ASCII map. It must contain the key
            `asciiLabelByIndices`, which is a dictionary where the values are
            the labels whose lengths are used to determine the slot size.

        Raises
        ------
        ValueError
            If `asciiLabelByIndices` is empty or not present in the `ascii_map`.
        """
        slotSize = max(len(v) for v in ascii_map["asciiLabelByIndices"].values())
        ascii_map["_spacer"] = " " * slotSize
        fmt = f"{{placeholder:{slotSize}s}}"
        ascii_map["_placeholder"] = fmt.format(placeholder=PLACEHOLDER)

def default_getLineNumsToWrite(ascii_map: dict):
    """
    Get the order of lines to write for the ASCII map.

    This function returns the order of line numbers to write, typically
    indexing from bottom to top for most maps.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the key
        `_asciiMaxLine`, which indicates the maximum line number in the map.

    Returns
    -------
    reversed : range
        A reversed range object from 0 to `_asciiMaxLine`.

    Raises
    ------
    KeyError
        If `_asciiMaxLine` is not present in the `ascii_map`.
    """
    if "_asciiMaxLine" not in ascii_map:
        raise KeyError("_asciiMaxLine must be present in the ascii_map.")
    return reversed(range(ascii_map["_asciiMaxLine"]))

def default_updateDimensionsFromData(ascii_map: dict):
    """
    Update the map dimensions based on the data in the ASCII map.

    This function inspects the `asciiLabelByIndices` dictionary in the
    `ascii_map` and sets the `_ijMax` value to the maximum sum of the
    indices.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the key
        `asciiLabelByIndices`, which maps indices to labels.

    Raises
    ------
    KeyError
        If `asciiLabelByIndices` is not present in the `ascii_map`.

    See Also
    --------
    _updateDimensionsFromAsciiLines : used when reading info from ASCII lines.
    """
    if "asciiLabelByIndices" not in ascii_map:
        raise KeyError("asciiLabelByIndices must be present in the ascii_map.")
    ascii_map["_ijMax"] = max(sum(key) for key in ascii_map["asciiLabelByIndices"])



def gridContentsToAscii(ascii_map: dict,
                        updateDimensionsFromData_function: Callable,
                        LineNumsToWrite_function: Callable,
                        makeOffsets_function: Callable,
                        IJFromColRow_function: Callable) -> dict:
    """
    Convert a prepared asciiLabelByIndices to ASCII lines and offsets.

    This function is used when you have i,j/specifier data and want to create
    an ASCII map from it, as opposed to reading an ASCII map from a stream.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the key
        `asciiLabelByIndices`, which maps indices to labels.
    updateDimensionsFromData_function : Callable
        A function to update the dimensions of the ASCII map based on the data.
    LineNumsToWrite_function : Callable
        A function to get the order of line numbers to write for the ASCII map.
    makeOffsets_function : Callable
        A function to create offsets for the ASCII map.
    IJFromColRow_function : Callable
        A function to convert column and row numbers to i,j indices.

    Returns
    -------
    dict
        The updated ASCII map dictionary with `asciiLines` and `asciiOffsets`.

    Raises
    ------
    ValueError
        If the ASCII map contains blank rows from pure data or if no data is found.

    Notes
    -----
    This function assumes that the map knows how to convert line numbers and
    column numbers into i,j indices universally. In some implementations, this
    operation is in a different method for efficiency.
    """
    updateDimensionsFromData_function(ascii_map)
    ascii_map["asciiLines"] = []
    for lineNum in LineNumsToWrite_function(ascii_map):
        line = []
        for colNum in range(ascii_map["_asciiMaxCol"]):
            if (IJFromColRow_function == HexFullTipsUp_getIJFromColRow) or (IJFromColRow_function == HexFullFlatsUp_getIJFromColRow):
                ij = IJFromColRow_function(ascii_map=ascii_map, colNum=colNum, lineNum=lineNum)
            else:
                ij = IJFromColRow_function(colNum, lineNum)
            # convert to string and strip any whitespace in thing we're representing
            line.append(
                str(ascii_map["asciiLabelByIndices"].get(ij, PLACEHOLDER)).replace(" ", "")
            )
        ascii_map["asciiLines"].append(line)

    # clean data
    noDataLinesYet = True  # handle all-placeholder rows
    newLines = []
    for line in ascii_map["asciiLines"]:
        if re.search(f"^[{PLACEHOLDER}]+$", "".join(line)) and noDataLinesYet:
            continue

        noDataLinesYet = False
        newLine = default_removeTrailingPlaceholders(line)
        if newLine:
            newLines.append(newLine)
        else:
            # if entire newline is wiped out, it's a full row of placeholders!
            # but oops this actually still won't work. Needs more work when
            # doing pure rows from data is made programmatically.
            raise ValueError(
                "Cannot write asciimaps with blank rows from pure data yet."
            )

    if not newLines:
        raise ValueError("No data found")
    ascii_map["asciiLines"] = newLines

    updateSlotSizeFromData(ascii_map)
    makeOffsets_function(ascii_map)
    return ascii_map

@staticmethod
def fromReactor(reactor):
    """Populate mapping from a reactor in preparation of writing out to ascii."""
    raise NotImplementedError


"""
Cartesian ascii map.
Conveniently simple because offsets are always 0
i and j are equal to column, row
"""
def Cartesian_asciiLinesToIndices(ascii_map: dict):
    """
    Convert ASCII lines to indices for a Cartesian grid.

    This function reads the ASCII lines from bottom to top to be consistent
    with Cartesian grid indexing and populates the `asciiLabelByIndices`
    dictionary in the `ascii_map`.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the key
        `asciiLines`, which is a list of ASCII lines.

    Raises
    ------
    KeyError
        If `asciiLines` is not present in the `ascii_map`.

    Notes
    -----
    This function assumes that the Cartesian grid indexing is used, where
    the indices are read from bottom to top.
    """
    if "asciiLines" not in ascii_map:
        raise KeyError("asciiLines must be present in the ascii_map.")
    
    ascii_map["asciiLabelByIndices"] = {}

    # Read from bottom to top to be consistent with Cartesian grid indexing
    for li, line in enumerate(reversed(ascii_map["asciiLines"])):
        for ci, asciiLabel in enumerate(line):
            ij = Cartesian_getIJFromColRow(ci, li)
            ascii_map["asciiLabelByIndices"][ij] = asciiLabel

def Cartesian_updateDimensionsFromData(ascii_map: dict):
    """
    Update the dimensions of the ASCII map for a Cartesian grid.

    This function updates the maximum column and line indices in the
    `ascii_map` based on the `asciiLabelByIndices` data. It also ensures
    that the indices start at less than or equal to zero.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the key
        `asciiLabelByIndices`, which is a dictionary with (i, j) indices
        as keys.

    Raises
    ------
    ValueError
        If the minimum i or j index is greater than zero.

    Notes
    -----
    This function assumes that the Cartesian grid indexing is used.
    """
    default_updateDimensionsFromData(ascii_map)
    ascii_map["_asciiMaxCol"] = max(key[0] for key in ascii_map["asciiLabelByIndices"]) + 1
    ascii_map["_asciiMaxLine"] = max(key[1] for key in ascii_map["asciiLabelByIndices"]) + 1
    iMin = min(key[0] for key in ascii_map["asciiLabelByIndices"])
    jMin = min(key[1] for key in ascii_map["asciiLabelByIndices"])

    if iMin > 0 or jMin > 0:
        raise ValueError(
            "Asciimaps only supports sets of indices that "
            "start at less than or equal to zero, got {}, {}".format(iMin, jMin)
        )

def Cartesian_getIJFromColRow(columnNum, lineNum):
    """
    Convert column and line numbers to Cartesian grid indices.

    Parameters
    ----------
    columnNum : int
        The column number.
    lineNum : int
        The line number.

    Returns
    -------
    tuple
        A tuple (i, j) representing the Cartesian grid indices.
    """
    return columnNum, lineNum

def Cartesian_makeOffsets(ascii_map: dict):
    """
    Set offsets for Cartesian grids to zero.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the key `asciiLines`.

    """
    ascii_map["asciiOffsets"] = []
    for _line in ascii_map["asciiLines"]:
        ascii_map["asciiOffsets"].append(0)

def Cartesian_updateDimensionsFromAsciiLines(ascii_map: dict):
    """
    Update dimensions for Cartesian grids based on ASCII lines.

    This function is a placeholder for the Cartesian grid implementation.
    It cunothing in this case.
    """
    pass

# ---------- END of AsciiMapCartesian Class ----------
# For inheritance classes we can do a simple pass of the asciimap dictionary
# and call the functions as needed
"""
Hex ascii map for 1/3 core flats-up map.

- Indices start with (0,0) in the bottom left (origin).
- i increments on the 30-degree ray
- j increments on the 90-degree ray

In all flats-up hex maps, i increments by 2*col for each col
and j decrements by col from the base.

These are much more complex maps than the tips up ones because
there are 2 ascii lines for every j index (jaggedly).

Lines are read from the bottom of the ascii map up in this case.
"""

def HexThirdFlatsUp_asciiLinesToIndices(ascii_map: dict):
    """
    Convert ASCII lines to indices for a 1/3 core flats-up hex grid.

    This function reads the ASCII lines from bottom to top to be consistent
    with hex grid indexing and populates the `asciiLabelByIndices` dictionary
    in the `ascii_map`.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the key
        `asciiLines`, which is a list of ASCII lines.

    Raises
    ------
    KeyError
        If `asciiLines` is not present in the `ascii_map`.

    Notes
    -----
    This function assumes that the hex grid indexing is used, where the indices
    are read from bottom to top.
    """
    if "asciiLines" not in ascii_map:
        raise KeyError("asciiLines must be present in the ascii_map.")
    
    ascii_map["asciiLabelByIndices"] = {}

    # Read from bottom to top so we know that the first item is at i,j = 0,0
    for li, line in enumerate(reversed(ascii_map["asciiLines"])):
        iBase, jBase = HexThirdFlatsUp_getIJBaseByAsciiLine(li)
        for ci, asciiLabel in enumerate(line):
            ij = HexThirdFlatsUp_getIJFromColAndBase(ci, iBase, jBase)
            ascii_map["asciiLabelByIndices"][ij] = asciiLabel

def HexThirdFlatsUp_getIJBaseByAsciiLine(asciiLineNum):
    """
    Get i,j base (starting point) for a row from bottom.

    Notes
    -----
    These are the indices of the far-left item in a row as a function
    of line number from the bottom. These are used in the process
    of computing the indices of items while reading the ascii map.

    For 1/3 symmetric cases, the base is a constant pattern
    vs. row number at least until the top section where the hexagon
    comes off the 1/3 symmetry line.

    The base hexes (LHS) as a function of rows from bottom are:

    Row:    0      1      2      3        4      5       6       7       8      9       10      11    12
    Base: (0,0), (1,0)  (0,1),  (1,1),  (0,2), (-1,3), (0,3), (-1,4), (-2,5), (-1,5), (-2,6), (-3,7) (-2,7)

    Looking graphically, there are basically 3 rays going up at 120 degrees.
    So we can find a consistent pattern for each ray and use a modulus to figure
    out which ray we're on.

    """
    if asciiLineNum == 0:
        return 0, 0
    rayNum = (asciiLineNum - 1) % 3
    indexOnRay = (asciiLineNum - 1) // 3
    if rayNum == 0:
        # middle ray: (1,0), (0,2), (-1,4), (-2,6)
        return 1 - indexOnRay, 2 * indexOnRay
    elif rayNum == 1:
        # leftmost ray: (0,1), (-1,3), (-2,5), ...
        return -indexOnRay, 2 * indexOnRay + 1
    else:
        # innermost ray: (1,1), (0,3), (-1,5)
        return 1 - indexOnRay, 2 * indexOnRay + 1

def HexThirdFlatsUp_getIJFromColAndBase(columnNum, iBase, jBase):
    """
    Map ASCII column and base to i,j hex indices for a 1/3 core flats-up hex grid.

    Parameters
    ----------
    columnNum : int
        The column number in the ASCII map.
    iBase : int
        The base i-coordinate in the hex grid.
    jBase : int
        The base j-coordinate in the hex grid.

    Returns
    -------
    tuple of int
        A tuple (i, j) representing the hex grid indices.

    Notes
    -----
    To move `n` columns to the right, `i` increases by `2n` and `j` decreases by `n`.
    """
    return iBase + 2 * columnNum, jBase - columnNum

def HexThirdFlatsUp_getIJFromColRow(columnNum, lineNum):
    """
    Map ascii column and row to i,j hex indices.

    Notes
    -----
    Not used in reading from file b/c too many calls to base
    but convenient for writing from ij data
    """
    iBase, jBase = HexThirdFlatsUp_getIJBaseByAsciiLine(lineNum)
    return HexThirdFlatsUp_getIJFromColAndBase(columnNum, iBase, jBase)

def HexThirdFlatsUp_makeOffsets(ascii_map: dict):
    """
    Calculate offsets for a 1/3 core flats-up hex grid.

    This function computes the offsets for each line in the ASCII map to ensure
    that the overhanging top fits properly. The offsets are normalized to start
    at zero.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the key
        `asciiLines`, which is a list of ASCII lines.

    Notes
    -----
    The offsets are calculated from bottom to top and then reversed to match
    the order of the ASCII lines. The offsets are then normalized to start at zero.
    """
    ascii_map["asciiOffsets"] = []
    for li, _line in enumerate(ascii_map["asciiLines"]):
        iBase, _ = HexThirdFlatsUp_getIJBaseByAsciiLine(li)
        ascii_map["asciiOffsets"].append(iBase - 1)
    ascii_map["asciiOffsets"].reverse()  # since getIJ works from bottom to top
    newOffsets = []

    # Renormalize the offsets to start at 0
    minOffset = min(ascii_map["asciiOffsets"])
    for offset in ascii_map["asciiOffsets"]:
        newOffsets.append(offset - minOffset)
    ascii_map["asciiOffsets"] = newOffsets

def HexThirdFlatsUp_updateDimensionsFromAsciiLines(ascii_map: dict):
    """
    Update dimensions for a 1/3 core flats-up hex grid based on ASCII lines.

    This function updates the dimension metadata by examining the ASCII lines.
    Specifically, it sets the maximum i index and calculates the number of
    ASCII lines that are offset from the corner.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the key
        `asciiLines`, which is a list of ASCII lines.

    Notes
    -----
    In this case, `_asciiMaxCol` represents the maximum i index.
    """
    ascii_map["_ijMax"] = ascii_map["_asciiMaxCol"] - 1
    ascii_map["_asciiLinesOffCorner"] = len(ascii_map["asciiLines"][-1]) - 1

def HexThirdFlatsUp_updateDimensionsFromData(ascii_map: dict):
    """
    Set map dimension metadata based on populated data structure.

    Notes
    -----
    Used before writing the asciimap from data.

    Add flat-hex specific corner truncation detection that allows
    some positions to be empty near the corners of the full hex,
    as is typical for hexagonal core maps.

    For 1/3 hex, _ijMax represents the outer outline
    """
    default_updateDimensionsFromData(ascii_map)

    # Check the j=0 ray to see how many peripheral locations are blank.
    # assume symmetry with the other corner.
    # The cap is basically the distance from the (I, 0) or (0, J) loc to self._ijMax
    iWithData = [i for i, j in ascii_map["asciiLabelByIndices"] if j == 0]
    maxIWithData = max(iWithData) if iWithData else -1
    ascii_map["_asciiLinesOffCorner"] = (ascii_map["_ijMax"] - maxIWithData) * 2 - 1

    # in jagged systems we have to also check the neighbor.
    # maybe even more corner positions could be left out in very large maps?
    nextIWithData = [i for i, j in ascii_map["asciiLabelByIndices"] if j == 1]
    nextMaxIWithData = max(nextIWithData) if nextIWithData else -1
    if nextMaxIWithData == maxIWithData - 1:
        # the jagged edge is lopped off too.
        ascii_map["_asciiLinesOffCorner"] += 1

    # now that we understand how many corner positions are truncated,
    # we can fully determine the size of the ascii map
    ascii_map["_asciiMaxCol"] = ascii_map["_ijMax"] + 1
    ascii_map["_asciiMaxLine"] = ascii_map["_ijMax"] * 2 + 1 - ascii_map["_asciiLinesOffCorner"]

# ---------- END of AsciiMapHexThirdFlatsUp Class ----------
# For inheritance classes we can do a simple pass of the asciimap dictionary
# and call the functions as needed

"""
Full core flats up ascii map.

Notes
-----
Rather than making a consistent base, we switch base angles
with this one because otherwise there would be a ridiculous
number of placeholders on the left. This makes this one's
base computation more complex.

We also allow all corners to be cut off on these, further
complicating things.
"""
def HexFullFlatsUp_getIJBaseByAsciiLine(ascii_map: dict, asciiLineNum: int) -> tuple:
    """
    Get i,j base (starting point) for a row from bottom.

    Starts out in simple pattern and then shifts.

    Recall that there are 2 ascii lines per j index because jagged.

    If hex corners are omitted, we must offset the line num to get
    the base right (complexity!)

    In this orientation, we need the _ijMax to help orient us. This
    represents the number of ascii lines between the center of the core
    and the top (or bottom).

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the keys
        `_asciiLinesOffCorner` and `_ijMax`.
    asciiLineNum : int
        The line number in the ASCII map.

    Returns
    -------
    tuple
        A tuple (i, j) representing the base i,j coordinates for the given line number.
    """
    # handle potentially-omitted corners
    asciiLineNum += ascii_map["_asciiLinesOffCorner"]
    if asciiLineNum < ascii_map["_ijMax"]:
        # goes from (0,-9), (-1,-8), (-2,7)...
        i, j = -asciiLineNum, (-1 * ascii_map["_ijMax"]) + asciiLineNum
    elif not (asciiLineNum - ascii_map["_ijMax"]) % 2:
        # goes JAGGED from (-9,0), (-8, 0), (-9,2)...
        # this is the outermost upward ray
        index = (asciiLineNum - ascii_map["_ijMax"]) // 2
        i, j = -ascii_map["_ijMax"], index
    else:
        # this is the innermost upward ray
        index = (asciiLineNum - ascii_map["_ijMax"]) // 2
        i, j = -ascii_map["_ijMax"] + 1, index

    return i, j

def HexFullFlatsUp_makeOffsets(ascii_map: dict):
    """
    Calculate offsets for full-hex flat grids.

    This function handles the offsets for full-hex flat grids, taking into
    account the staggered nature of the grid. It computes the offsets for
    each line in the ASCII map, ensuring that the overhanging top fits
    properly. The offsets are normalized to start at zero.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the keys
        `_ijMax` and `_asciiLinesOffCorner`.

    Notes
    -----
    Due to the staggered nature, these grids have 0 or 1 offsets on the top
    and then 0 or 1 plus an actual offset on the bottom. The function also
    handles cut-off corners by truncating the offsets accordingly.
    """
    # max lines required if corners were not cut off
    maxIJIndex = ascii_map["_ijMax"]
    ascii_map["asciiOffsets"] = []
    # grab top left edge going down until corner where it lifts off edge.
    # Due to the placeholders these just oscillate
    for li in range(maxIJIndex * 3):
        ascii_map["asciiOffsets"].append((li - ascii_map["_asciiLinesOffCorner"]) % 2)

    # going away from the left edge, the offsets increase linearly
    ascii_map["asciiOffsets"].extend(range(maxIJIndex + 1))

    # since we allow cut-off corners, we must truncate the offsets
    # number of items in last line indicates how many
    # need to be cut. (first line has placeholders...)
    cutoff = ascii_map["_asciiLinesOffCorner"]
    if cutoff:
        ascii_map["asciiOffsets"] = ascii_map["asciiOffsets"][cutoff:-cutoff]

def HexFullFlatsUp_updateDimensionsFromData(ascii_map: dict):
    """
    Update dimensions for a full-hex flats-up grid based on populated data.

    This function updates the dimension metadata by examining the populated
    data structure. It calls the `HexThirdFlatsUp_updateDimensionsFromData`
    function to perform common updates, then adjusts the maximum column and line
    indices specific to the full-hex flats-up grid.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the keys
        `_ijMax` and `_asciiLinesOffCorner`.

    Notes
    -----
    This function assumes that the hex grid indexing is used and adjusts the
    dimensions accordingly.
    """
    HexThirdFlatsUp_updateDimensionsFromData(ascii_map)
    ascii_map["_asciiMaxCol"] = ascii_map["_ijMax"] + 1
    ascii_map["_asciiMaxLine"] = ascii_map["_ijMax"] * 4 + 1 - ascii_map["_asciiLinesOffCorner"] * 2


def HexFullFlatsUp_asciiLinesToIndices(ascii_map: dict):
    """
    Convert ASCII lines to grid indices for a full-hex flats-up grid.

    This function processes the ASCII lines from the bottom to the top,
    converting each character to its corresponding grid indices. It updates
    the `asciiLabelByIndices` dictionary in the `ascii_map` with the grid
    indices as keys and the ASCII labels as values.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the keys
        `asciiLines` and `asciiLabelByIndices`.

    Notes
    -----
    This function assumes that the hex grid indexing is used and processes
    the ASCII lines accordingly.
    """
    ascii_map["asciiLabelByIndices"] = {}

    # read from bottom to top so we know that first item is at i,j = 0,0
    for li, line in enumerate(reversed(ascii_map["asciiLines"])):
        iBase, jBase = HexFullFlatsUp_getIJBaseByAsciiLine(ascii_map=ascii_map, asciiLineNum=li)
        for ci, asciiLabel in enumerate(line):
            ij = HexThirdFlatsUp_getIJFromColAndBase(ci, iBase, jBase)
            ascii_map["asciiLabelByIndices"][ij] = asciiLabel

def HexFullFlatsUp_getIJFromColRow(ascii_map: dict, colNum, lineNum):
    """
    Map ascii column and row to i,j hex indices.

    Notes
    -----
    Not used in reading from file b/c too many calls to base
    but convenient for writing from ij data
    """
    iBase, jBase = HexFullFlatsUp_getIJBaseByAsciiLine(ascii_map=ascii_map, asciiLineNum=lineNum)
    return HexThirdFlatsUp_getIJFromColAndBase(colNum, iBase, jBase)

# ---------- END of AsciiMapHexFullFlatsUp Class ----------
# For inheritance classes we can do a simple pass of the asciimap dictionary
# and call the functions as needed
"""
Full hex with tips up of the smaller cells.

- I axis is pure horizontal here
- J axis is 60 degrees up. (upper right corner)
- (0,0) is in the center of the hexagon.

Frequently used for pins inside hex assemblies.

This does not currently support omitted positions on the hexagonal corners.

In this geometry, the outline-defining _ijMax is equal to I at the far right of the hex. Thus, ijMax represents the
number of positions from the center to the outer edge towards any of the 6 corners.
"""

def HexFullTipsUp_asciiLinesToIndices(ascii_map: dict):
    """
    Convert ASCII lines to grid indices for a full-hex tips-up grid.

    This function processes the ASCII lines from the top to the bottom,
    converting each character to its corresponding grid indices. It updates
    the `asciiLabelByIndices` dictionary in the `ascii_map` with the grid
    indices as keys and the ASCII labels as values.

    Parameters
    ----------
    ascii_map : dict
        The dictionary representing the ASCII map. It must contain the keys
        `asciiLines` and `asciiLabelByIndices`.

    Notes
    -----
    This function assumes that the hex grid indexing is used and processes
    the ASCII lines accordingly.
    """
    ascii_map["asciiLabelByIndices"] = {}

    for li, line in enumerate(ascii_map["asciiLines"]):
        iBase, jBase = HexFullTipsUp_getIJBaseByAsciiLine(ascii_map,li)
        for ci, asciiLabel in enumerate(line):
            ij = HexFullTipsUp_getIJFromColAndBase(ci, iBase, jBase)
            ascii_map["asciiLabelByIndices"][ij] = asciiLabel
        ascii_map["asciiOffsets"].append(li)

def HexFullTipsUp_getIJFromColAndBase(columnNum, iBase, jBase):
    """
    Map ascii column and base to i,j hex indices.

    Indices simply increment from the base across the rows.
    """
    return iBase + columnNum + jBase, -(iBase + columnNum)

def HexFullTipsUp_getIJFromColRow(ascii_map: dict, colNum, lineNum):
    """
    Map indices from ascii.

    Notes
    -----
    Not used in reading from file b/c inefficient/repeated base calc but required for writing from ij data.
    """
    iBase, jBase = HexFullTipsUp_getIJBaseByAsciiLine(ascii_map, lineNum)
    return HexFullTipsUp_getIJFromColAndBase(colNum, iBase, jBase)

def HexFullTipsUp_getIJBaseByAsciiLine(ascii_map: dict, asciiLineNum):
    """
    Get i,j base (starting point) for a row counting from the top.

    Upper left is shifted by (size-1)//2

    for a 19-line grid, we have the top left as (-18,9) and then: (-17, 8), (-16, 7), ...
    """
    shift = ascii_map["_ijMax"]
    iBase = -shift * 2 + asciiLineNum
    jBase = shift - asciiLineNum
    return iBase, jBase

def HexFullTipsUp_updateDimensionsFromAsciiLines(ascii_map: dict):
    """Update dimension metadata when reading ascii."""
    # ijmax here can be inferred directly from the max number of columns in the asciimap text
    ascii_map["_ijMax"] = (ascii_map["_asciiMaxCol"] - 1) // 2

def HexFullTipsUp_updateDimensionsFromData(ascii_map: dict):
    """Update asciimap dimensions from data before writing ascii."""
    default_updateDimensionsFromData(ascii_map)
    ascii_map["_asciiMaxCol"] = ascii_map["_ijMax"] * 2 + 1
    ascii_map["_asciiMaxLine"] = ascii_map["_ijMax"] * 2 + 1

def HexFullTipsUp_getLineNumsToWrite(ascii_map):
    """
    Get order of lines to write.
    This map indexes lines from top to bottom.
    """
    return range(ascii_map["_asciiMaxLine"])

def HexFullTipsUp_makeOffsets(ascii_map: dict):
    """Full hex tips-up grids have linearly incrementing offset."""
    ascii_map["asciiOffsets"] = []
    for li, _line in enumerate(ascii_map["asciiLines"]):
        ascii_map["asciiOffsets"].append(li)

# ---------- END of AsciiMapHexFullTipsUp_makeOffsets Class ----------
# For inheritance classes we can do a simple pass of the asciimap dictionary
# and call the functions as needed

# Helper Functions For Conversion
# Additional update and helper functions are needed to properly manage the state of the ascii_map dictionary.
# Requires more scrutiny when fixing the format conversion functions.
@staticmethod
def default_removeTrailingPlaceholders(line):
    """
    Remove trailing placeholder characters from a line.

    This function processes a line in reverse order, removing any trailing
    placeholder characters until a non-placeholder character is encountered.
    The modified line is then returned in its original order.

    Parameters
    ----------
    line : list
        A list of characters representing a line in the ASCII map.

    Returns
    -------
    newLine : list
        The modified line with trailing placeholder characters removed.

    Notes
    -----
    The function assumes that `PLACEHOLDER` is a predefined constant
    representing the placeholder character.
    """
    newLine = []
    noDataYet = True
    for col in reversed(line):
        if col == PLACEHOLDER and noDataYet:
            continue
        noDataYet = False
        newLine.append(col)
    newLine.reverse()
    return newLine

# From The AsciiMapHexThirdFlatsUp Class
def default_getIJBaseByAsciiLine(ascii_map: dict):
    """
    Get i,j base (starting point) for a row from bottom.

    These are the indices of the far-left item in a row as a function
    of line number from the bottom. These are used in the process
    of computing the indices of items while reading the ascii map.

    For 1/3 symmetric cases, the base is a constant pattern
    vs. row number at least until the top section where the hexagon
    comes off the 1/3 symmetry line.

    The base hexes (LHS) as a function of rows from bottom are:

    Row:    0      1      2      3        4      5       6       7       8      9       10      11    12
    Base: (0,0), (1,0)  (0,1),  (1,1),  (0,2), (-1,3), (0,3), (-1,4), (-2,5), (-1,5), (-2,6), (-3,7) (-2,7)

    Looking graphically, there are basically 3 rays going up at 120 degrees.
    So we can find a consistent pattern for each ray and use a modulus to figure
    out which ray we're on.

    """
    if ascii_map["asciiLineNum"] == 0:
        return 0, 0
    rayNum = (ascii_map["asciiLineNum"] - 1) % 3
    indexOnRay = (ascii_map["asciiLineNum"] - 1) // 3
    if rayNum == 0:
        # middle ray: (1,0), (0,2), (-1,4), (-2,6)
        return 1 - indexOnRay, 2 * indexOnRay
    elif rayNum == 1:
        # leftmost ray: (0,1), (-1,3), (-2,5), ...
        return -indexOnRay, 2 * indexOnRay + 1
    else:
        # innermost ray: (1,1), (0,3), (-1,5)
        return 1 - indexOnRay, 2 * indexOnRay + 1
    
def default_getLineNumsToWrite(ascii_map: dict):
    """
    Get order of lines to write.

    This map indexes lines from top to bottom.
    """
    return range(ascii_map["_asciiMaxLine"])
        
def getItem(ascii_map: dict, ijKey):
    """Get ascii item by grid i,j index."""
    return ascii_map["asciiLabelByIndices"][ijKey]

def setItem(ascii_map: dict, ijKey, item):
    ascii_map["asciiLabelByIndices"][ijKey] = item


def items(ascii_map: dict):
    return ascii_map["asciiLabelByIndices"].items()

def keys(ascii_map: dict):
    return ascii_map["asciiLabelByIndices"].keys()

def reverse_lines(text: str) -> str:
    lines = text.rstrip('\n').split('\n')
    reversed_lines = '\n'.join(reversed(lines))
    reversed_lines += '\n'
    return reversed_lines

# Create ASCII Map from Geometry and Domain
# TODO: Conversion Functions need to be replaced with discrete operators
# THIS HAS NOT BEEN VALIDATED
def asciiMapFromGeomAndDomain(
    ascii_map: dict,
    geomType: Union[str, geometry.GeomType], 
    domain: Union[str, geometry.DomainType]
):
    """Get an ASCII map from ASCII lines based on geometry and domain type."""
    
    # Convert string inputs to Enum types if necessary
    if isinstance(geomType, str):
        geomType = geometry.GeomType.fromAny(geomType)
    if isinstance(domain, str):
        domain = geometry.DomainType.fromAny(domain)

    # Handle HEX_CORNERS_UP by converting it to HEX
    if geomType == "hex_corners_up":
        geomType = geometry.GeomType.HEX

    # Define a mapping from geometry and domain types to the corresponding conversion functions
    map_from_geom = {
        (geometry.GeomType.HEX, geometry.DomainType.THIRD_CORE): HexThirdFlatsUp_asciiLinesToIndices,
        (geometry.GeomType.HEX, geometry.DomainType.FULL_CORE): HexFullFlatsUp_getIJBaseByAsciiLine,
        (geometry.GeomType.CARTESIAN, None): Cartesian_asciiLinesToIndices,
        (geometry.GeomType.CARTESIAN, geometry.DomainType.FULL_CORE): Cartesian_asciiLinesToIndices,
        (geometry.GeomType.CARTESIAN, geometry.DomainType.QUARTER_CORE): Cartesian_asciiLinesToIndices,
    }

    # Special case handling for HEX_CORNERS_UP with FULL_CORE
    if geomType == geometry.GeomType.HEX and domain == geometry.DomainType.FULL_CORE:
        return HexFullTipsUp_asciiLinesToIndices(ascii_map)

    # Retrieve the conversion function from the map
    conversion_function = map_from_geom.get((geomType, domain))

    # Check if a valid function is found
    if conversion_function:
        # Call the conversion function with the ASCII lines to get the ASCII map
        return conversion_function(ascii_map)
    else:
        # Handle unsupported combinations of geometry and domain
        raise ValueError(f"Unsupported combination of geometry '{geomType}' and domain '{domain}'")