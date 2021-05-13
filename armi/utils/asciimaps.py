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
though inherently this work is complex.

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
import re

from typing import Union

from armi import runLog
from armi.reactor import geometry

PLACEHOLDER = "-"


class AsciiMap:
    """
    Base class for maps.

    These should be able to read and write ASCII maps loaded either from text
    or programatically with i,j / specifiers.
    """

    def __init__(self):
        self.asciiLines = []
        """A list of lines, each containing a list of ascii labels for each column. No blanks."""

        self.asciiOffsets = []
        """A list of offsets for each line that will be prepended before the contents of asciiLines"""

        self.asciiLabelByIndices = {}
        """A mapping from grid location objects to ascii labels"""

        self._spacer = " "
        """Individual spacing for one 'item' of ascii"""

        self._placeholder = PLACEHOLDER
        """Placeholder for blank data. Also holds the size of ascii window for each value"""

        self._asciiMaxCol = 0
        self._asciiMaxLine = 0
        self._ijMax = 0
        """Various dimensions of the ascii mesh and data"""

        self._asciiLinesOffCorner = 0
        """Number of ascii lines chopped of corners"""

    def writeAscii(self, stream):
        """Write out the ascii representation"""
        if not self.asciiLines:
            raise ValueError("Cannot write ASCII map before ASCII lines are processed")
        if len(self.asciiOffsets) != len(self.asciiLines):
            runLog.error(f"AsciiLines: {self.asciiLines}")
            runLog.error(f"Offsets: {self.asciiOffsets}")
            raise ValueError(
                f"Inconsistent lines ({len(self.asciiLines)}) "
                f"and offsets ({len(self.asciiOffsets)})"
            )
        fmt = f"{{val:{len(self._placeholder)}s}}"
        for offset, line in zip(self.asciiOffsets, self.asciiLines):
            data = [fmt.format(val=v) for v in line]
            line = self._spacer * offset + self._spacer.join(data) + "\n"
            stream.write(line)

    def readAscii(self, text):
        """
        Read ascii representation from a stream.

        Update placeholder size according to largest thing read."""
        text = text.strip().splitlines()
        self.asciiLines = []
        self._asciiMaxCol = 0
        for li, line in enumerate(text):
            columns = line.split()
            self.asciiLines.append(columns)
            if len(columns) > self._asciiMaxCol:
                self._asciiMaxCol = len(columns)
        self._asciiMaxLine = li + 1  # pylint: disable=undefined-loop-variable
        self._updateDimensionsFromAsciiLines()
        self._asciiLinesToIndices()
        self._makeOffsets()
        self._updateSlotSizeFromData()

    def _updateSlotSizeFromData(self):
        """After reading data, update slot size for writing."""
        slotSize = max(len(v) for v in self.asciiLabelByIndices.values())
        self._spacer = " " * slotSize
        fmt = f"{{placeholder:{slotSize}s}}"
        self._placeholder = fmt.format(placeholder=PLACEHOLDER)

    def _updateDimensionsFromAsciiLines(self):
        """
        When converting ascii to data we need to infer the ijMax before reading
        the ij indices.

        See Also
        --------
        _updateDimensionsFromData : used to infer this information when loading from i,j data
        """
        raise NotImplementedError

    def _updateDimensionsFromData(self):
        """
        After data is loaded, figure out the bounds.

        See Also
        --------
        _updateDimensionsFromAsciiLines : used when reading info from ascii lines
        """
        self._ijMax = max(sum(key) for key in self.asciiLabelByIndices)

    @staticmethod
    def fromReactor(reactor):
        """
        Populate mapping from a reactor in preparation of writing out to ascii.
        """
        raise NotImplementedError

    def gridContentsToAscii(self):
        """
        Convert a prepared asciiLabelByIndices to ascii lines and offsets.

        This is used when you have i,j/specifier data and want to create a ascii map from it
        as opposed to reading a ascii map from a stream.

        As long as the map knows how to convert lineNum and colNums into ij indices, this
        is universal. In some implementations, this operation is in a different
        method for efficiency.
        """
        self._updateDimensionsFromData()
        self.asciiLines = []
        for lineNum in reversed(range(self._asciiMaxLine)):
            line = []
            for colNum in range(self._asciiMaxCol):
                ij = self._getIJFromColRow(colNum, lineNum)
                # convert to string and strip any whitespace in thing we're representing
                line.append(
                    str(self.asciiLabelByIndices.get(ij, PLACEHOLDER)).replace(" ", "")
                )
            self.asciiLines.append(line)

        # clean data
        noDataLinesYet = True  # handle all-placeholder rows
        newLines = []
        for line in self.asciiLines:
            if re.search(f"^[{PLACEHOLDER}]+$", "".join(line)) and noDataLinesYet:
                continue
            else:
                noDataLinesYet = False
                newLine = self._removeTrailingPlaceholders(line)
                if newLine:
                    newLines.append(newLine)
                else:
                    # if entire newline is wiped out, it's a full row of placeholders!
                    # but oops this actually still won't work. Needs more work when
                    # doing pure rows from data is made programmatically.
                    # newLines.append(line)
                    raise ValueError(
                        "Cannot write asciimaps with blank rows from pure data yet."
                    )
        if not newLines:
            raise ValueError("No data found")
        self.asciiLines = newLines

        self._updateSlotSizeFromData()
        self._makeOffsets()

    @staticmethod
    def _removeTrailingPlaceholders(line):
        newLine = []
        noDataYet = True
        for col in reversed(line):
            if col == PLACEHOLDER and noDataYet:
                continue
            else:
                noDataYet = False
            newLine.append(col)
        newLine.reverse()
        return newLine

    def _asciiLinesToIndices(self):
        """Convert read in ASCII lines to a asciiLabelByIndices structure"""

    def _getIJFromColRow(self, colNum: int, lineNum: int) -> tuple:
        """
        Get ij data indices from ascii map text coords.

        lineNum is typically from the bottom of the ascii... I think.
        """
        raise NotImplementedError

    def __getitem__(self, ijKey):
        """Get ascii item by grid i,j index."""
        return self.asciiLabelByIndices[ijKey]

    def _makeOffsets(self):
        """Build offsets"""

    def items(self):
        return self.asciiLabelByIndices.items()


class AsciiMapCartesian(AsciiMap):
    """
    Cartesian ascii map.

    Conveniently simple because offsets are always 0
    """

    def _asciiLinesToIndices(self):
        self.asciiLabelByIndices = {}

        # read from bottom to top to be consistent
        # with cartesian grid indexing
        for li, line in enumerate(reversed(self.asciiLines)):
            for ci, asciiLabel in enumerate(line):
                ij = self._getIJFromColRow(ci, li)
                self.asciiLabelByIndices[ij] = asciiLabel

    def _getIJFromColRow(self, columNum, lineNum):
        return columNum, lineNum

    def _makeOffsets(self):
        """Cartesian grids have 0 offset on all lines."""
        AsciiMap._makeOffsets(self)
        for _line in self.asciiLines:
            self.asciiOffsets.append(0)

    def _updateDimensionsFromAsciiLines(self):
        self._ijMax = self._asciiMaxCol


class AsciiMapHexThirdFlatsUp(AsciiMap):
    """
    Hex ascii map for 1/3 core flats-up map.

    In all flats-up hex maps, i increments by 2*col for each col
    and j decrements by col from the base.

    These are much more complex maps than the tips up ones because
    there are 2 ascii lines for every j index (jaggedly).
    """

    def _asciiLinesToIndices(self):
        self.asciiLabelByIndices = {}

        # read from bottom to top to be consistent
        # so we know that first item is at i,j = 0,0
        for li, line in enumerate(reversed(self.asciiLines)):
            iBase, jBase = self._getIJBaseByAsciiLine(li)
            for ci, asciiLabel in enumerate(line):
                # To move n columns right, i increases by 2n, j decreases by n
                ij = iBase + 2 * ci, jBase - ci
                self.asciiLabelByIndices[ij] = asciiLabel

    def _getIJFromColRow(self, columNum, lineNum):
        """Not used in reading from file b/c slow but required for writing from ij data"""
        iBase, jBase = self._getIJBaseByAsciiLine(lineNum)
        return iBase + 2 * columNum, jBase - columNum

    def _getIJBaseByAsciiLine(self, asciiLineNum):
        """
        Get i,j base (starting point) for a row from bottom.

        For 1/3 symmetric cases, the base is a constant pattern
        vs. row number at least until the top section.

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

    def _makeOffsets(self):
        """
        One third hex grids have larger offsets at the bottom.
        """
        self.asciiOffsets = []
        for li, _line in enumerate(self.asciiLines):
            iBase, _ = self._getIJBaseByAsciiLine(li)
            self.asciiOffsets.append(iBase - 1)
        self.asciiOffsets.reverse()  # since getIJ works from bottom to top
        newOffsets = []

        # renomalize the offsets to start at 0
        minOffset = min(self.asciiOffsets)
        for li, (_, offset) in enumerate(zip(self.asciiLines, self.asciiOffsets)):
            newOffsets.append(offset - minOffset)
        self.asciiOffsets = newOffsets

    def _updateDimensionsFromAsciiLines(self):
        self._ijMax = self._asciiMaxCol - 1
        self._asciiLinesOffCorner = len(self.asciiLines[-1]) - 1

    def _updateDimensionsFromData(self):
        """Add flat-hex specific corner truncation detection"""
        AsciiMap._updateDimensionsFromData(self)

        # generally the distance from the i, 0 or 0, j index to self._ijMax
        maxIWithData = max(i for i, j in self.asciiLabelByIndices if j == 0)
        self._asciiLinesOffCorner = (self._ijMax - maxIWithData) * 2 - 1
        # in jagged systems we have to also check the neighbor
        nextMaxIWithData = max(i for i, j in self.asciiLabelByIndices if j == 1)
        if nextMaxIWithData == maxIWithData - 1:
            # the jagged edge is lopped off too.
            self._asciiLinesOffCorner += 1

        self._asciiMaxCol = self._ijMax + 1
        self._asciiMaxLine = self._ijMax * 2 + 1 - self._asciiLinesOffCorner


class AsciiMapHexFullFlatsUp(AsciiMapHexThirdFlatsUp):
    """
    Full core flats up.

    Rather than making a consistent base, we switch base angles
    with this one because otherwise there would be a ridiculous
    number of placeholders. This makes this one's base computation
    more complex.

    We also allow the corners to be cut off on these, further
    complicating things.
    """

    def _getIJBaseByAsciiLine(self, asciiLineNum):
        """
        Get i,j base (starting point) for a row from bottom.

        Starts out in simple pattern and then shifts.

        Recall that there are 2 ascii lines per j index because jagged.

        If hex corners are omitted, we must offset the line num to get
        the base right (complexity!)
        """
        # handle potentially-omitted corners
        asciiLineNum += self._asciiLinesOffCorner
        if asciiLineNum < self._ijMax:
            # goes from (0,-9), (-1,-8), (-2,7)...
            i, j = -asciiLineNum, -self._ijMax + asciiLineNum
        elif not (asciiLineNum - self._ijMax) % 2:
            # goes JAGGED from (-9,0), (-8, 0), (-9,2)...
            # this is the outermost upward ray
            index = (asciiLineNum - self._ijMax) // 2
            i, j = -self._ijMax, index
        else:
            # this is the innermost upward ray
            index = (asciiLineNum - self._ijMax) // 2
            i, j = -self._ijMax + 1, index

        return i, j

    def _makeOffsets(self):
        """
        Handle offsets for full-hex flat grids.

        Due to the staggered nature, these have 0 or 1 offsets on
        top and and then 0 or 1 + an actual offset on the bottom.
        """
        # max lines required if corners were not cut off
        maxIJIndex = self._ijMax
        self.asciiOffsets = []
        # grap top left edge going down until corner where it lifts off edge.
        # Due to the placeholders these just oscillate
        for li in range(maxIJIndex * 3):
            self.asciiOffsets.append((li - self._asciiLinesOffCorner) % 2)

        # going away from the left edge, the offsets increase linearly
        self.asciiOffsets.extend(range(maxIJIndex + 1))

        # since we allow cut-off corners, we must truncate the offsets
        # number of items in last line indicates how many
        # need to be cut. (first line has placeholders...)
        cutoff = self._asciiLinesOffCorner
        if cutoff:
            self.asciiOffsets = self.asciiOffsets[cutoff:-cutoff]

    def _updateDimensionsFromData(self):
        AsciiMapHexThirdFlatsUp._updateDimensionsFromData(self)
        self._asciiMaxCol = self._ijMax + 1
        self._asciiMaxLine = self._ijMax * 4 + 1 - self._asciiLinesOffCorner * 2


class AsciiMapHexFullTipsUp(AsciiMap):
    """
    Full hex with tips up of the smaller cells.

    I axis is pure horizontal here
    J axis is 60 degrees up. (upper right corner)

    Frequently used for pins inside hex assemblies.
    """

    def _asciiLinesToIndices(self):
        self.asciiLabelByIndices = {}

        for li, line in enumerate(self.asciiLines):
            iBase, jBase = self._getIJBaseByAsciiLine(li)
            for ci, asciiLabel in enumerate(line):
                ij = iBase + ci, jBase
                self.asciiLabelByIndices[ij] = asciiLabel
            self.asciiOffsets.append(li)

    def _getIJFromColRow(self, columNum, lineNum):
        """Not used in reading from file b/c slow but required for writing from ij data"""
        iBase, jBase = self._getIJBaseByAsciiLine(lineNum)
        return iBase + columNum, jBase

    def _getIJBaseByAsciiLine(self, asciiLineNum):
        """
        Get i,j base (starting point) for a row from top.
        Easy and consistent.

        Upper left is shifted by (size-1)//2

        for a 19-line grid, we have the top left as (-18,9)
        and then: (-17, 8), (-16, 7), ...
        """
        shift = self._ijMax
        iBase = -shift * 2 + asciiLineNum
        jBase = shift - asciiLineNum
        return iBase, jBase

    def _updateDimensionsFromAsciiLines(self):
        self._ijMax = (self._asciiMaxCol - 1) // 2


def asciiMapFromGeomAndSym(
    geomType: Union[str, geometry.GeomType], symmetry: Union[str, geometry.SymmetryType]
) -> "AsciiMap":
    """Get a ascii map class from a geometry and symmetry type."""
    from armi.reactor import geometry

    if str(geomType) == geometry.HEX_CORNERS_UP and geometry.FULL_CORE in str(symmetry):
        return AsciiMapHexFullTipsUp

    MAP_FROM_GEOM = {
        (
            geometry.GeomType.HEX,
            geometry.DomainType.THIRD_CORE,
        ): AsciiMapHexThirdFlatsUp,
        (geometry.GeomType.HEX, geometry.DomainType.FULL_CORE): AsciiMapHexFullFlatsUp,
        (geometry.GeomType.CARTESIAN, None): AsciiMapCartesian,
        (geometry.GeomType.CARTESIAN, geometry.DomainType.FULL_CORE): AsciiMapCartesian,
        (
            geometry.GeomType.CARTESIAN,
            geometry.DomainType.QUARTER_CORE,
        ): AsciiMapCartesian,
    }

    return MAP_FROM_GEOM[
        (
            geometry.GeomType.fromAny(geomType),
            geometry.SymmetryType.fromAny(symmetry).domain,
        )
    ]
