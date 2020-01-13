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
ASCII maps are little grids of letters/numbers that represent some kind of a lattice.

These are commonly used in nuclear analysis to represent core maps, pin layouts, etc.
in input files. This module reads various text and interprets them into meaningful
data structures.

We make classes for different geometries to share code. This will eventually be
expanded for various symmetries that are applicable to cores, assemblies, etc.

See Also
--------
armi.reactor.grids : More powerful, nestable lattices with specific dimensions
    Most input lattices eventually end up as Grid objects.
armi.reactor.blueprints.latticeBlueprint : user input of generic lattices
armi.reactor.geometry : a specific usage of lattices, for core maps

"""


class AsciiMap(object):
    """
    Base class for maps.

    These should be able to read and write ASCII maps.
    """

    def __init__(self, lattice=None):
        self.lattice = lattice or {}

    def readMap(self, text):
        """
        Iterate over an ASCII map and read it into a data structure.

        Parameters
        ----------
        text : str
            The ascii lattice input text

        Returns
        -------
        lattice : dict
            A mapping between (i,j) indices and specifiers, which can be
            one or more non-space chars.

        See Also
        --------
        armi.reactor.grids : Grid objects that this information can be
            turned into
        """
        self.lattice = {}
        for row, line in enumerate(reversed(text.strip().splitlines())):
            line = line.strip()
            base = self._getRowBase(row)
            for col, char in enumerate(line.split()):
                i, j = self._getIndices(base, col)
                self.lattice[i, j] = char
        return self.lattice

    def writeMap(self, stream):
        """Write an ascii map from the internal lattice structure to a stream."""
        colI, rowJ = zip(*sorted(self.lattice.keys(), key=lambda ij: ([ij[1], ij[0]])))
        line = []
        for i, j in zip(colI, reversed(rowJ)):
            if line and i == 0:
                stream.write(" ".join(line) + "\n")
                line = []
            line.append(f"{self.lattice.get((i,j),'-')}")
        stream.write(" ".join(line) + "\n")

    @staticmethod
    def _getRowBase(row):
        raise NotImplementedError()

    @staticmethod
    def _getIndices(base, col):
        raise NotImplementedError()


class AsciiMapCartesian(AsciiMap):
    """
    Read a square or rectangular ascii map.

    This may represent a full assembly or core or some symmetry of that.
    """

    @staticmethod
    def _getRowBase(row):
        """Return the base point for a given row. In Cartesian, this is just the row."""
        return 0, row

    @staticmethod
    def _getIndices(base, col):
        iBase, jBase = base
        return iBase + col, jBase


class AsciiMapHexThird(AsciiMap):
    """
    Read a 1/3-symmetric hex map with flat ends up/down.

    This is often useful for core maps in hex-assembly reactors like VVERs or SFRs.
    This should be missing the overlapping assemblies on the 120-degree line
    like in a nodal DIF3D case.

    This has 2 axes that are at a 60-degree angle. i marches up
    and down the 30-degree ray and j marches up and down the 90-degree
    ray. The center is (0,0). Negative indices are found beyond these
    rays in the 1/3 symmetric map.

    In reading a third core, you just need to figure out what the
    left-hand (i,j) starting point (base) is of any row. Then, as you go across the column
    from left to right, i increments by 2 each time, and j decrements by 1
    each time.

    The base hexes (LHS) as a function of rows from bottom are:
    Row:    0      1      2      3        4      5       6       7       8      9       10      11    12
    Base: (0,0), (1,0)  (0,1),  (1,1),  (0,2), (-1,3), (0,3), (-1,4), (-2,5), (-1,5), (-2,6), (-3,7) (-2,7)

    After the first 3, it's stepping up the 120-degree ray, two steps left,
    one step right, repeat. Very 3-based.

    First, find which triplet you're in (beyond the first): row//3

    Triplet: 0        1      2      3       4
    Base:    N/A   (1,1)  (0,3)  (-1,5) (-2,7)
    Pattern (>0):     (2-triplet, triplet*2-1)

    Then stride inside your triplet by position: row%3
    base = (tI-pos, tJ+pos)

    Of course, this breaks down as soon as you roll off the 120-degree
    symmetry line towards the top of the map. Here we either have to make
    whitespace count or insert dummy placeholders. The placeholders
    are going to be less fragile.
    """

    @staticmethod
    def _getRowBase(row):
        """Get the i,j base of a text row in 1/3 hex."""
        tripletNum = row // 3
        tripletPos = row % 3

        if tripletNum > 0:
            iBase = 2 - tripletNum - tripletPos
            jBase = tripletNum * 2 - 1 + tripletPos
        else:
            iBase, jBase = AsciiMapHexThird._getFirstTripletBase(tripletPos)

        return iBase, jBase

    @staticmethod
    def _getFirstTripletBase(tripletPos):  # pylint: disable=no-self-use
        """Handle base for first triplet at center of core."""
        if tripletPos == 0:
            iBase, jBase = 0, 0
        elif tripletPos == 1:
            iBase, jBase = 1, 0
        else:
            iBase, jBase = 0, 1
        return iBase, jBase

    @staticmethod
    def _getIndices(base, col):  # pylint: disable=no-self-use
        iBase, jBase = base
        return iBase + col * 2, jBase - col

    def writeMap(self, stream):
        """Writing this is easiest if we just make a big ascii map and fill it in."""
        grid = {}
        for (i, j), val in self.lattice.items():
            x = i * 2
            y = j * 2 + i
            grid[x, y] = val

        allI, allJ = zip(*grid.keys())

        lines = []
        for y in reversed(range(min(allJ) - 1, max(allJ) + 1)):
            line = []
            for x in range(min(allI) - 1, max(allI) + 1):
                line.append(f"{grid.get((x,y),' ')}")
            lines.append("".join(line).rstrip())
        stream.write("\n".join(lines))


class AsciiMapHexFullTipsUp(AsciiMap):
    """
    Read a full hexagonal ASCII map with tips of hexagons pointing up.

    This is often useful for pins inside a hexagonal assembly that has
    flat ends of the assembly up.

    In this case, the axes are also 60-degrees offset (above x-axis),
    with i incrementing horizontally and j incrementing up along
    the 60-degree ray.

    This reads in a full hex and puts 0,0 at the center point (using a shift).
    """

    def readMap(self, text):
        lattice = AsciiMap.readMap(self, text)
        self.lattice = self._shiftLattice(lattice)
        return self.lattice

    @staticmethod
    def _getRowBase(row):
        """Get the i,j base of a text row full hex."""
        return -row, row

    @staticmethod
    def _getIndices(base, col):  # pylint: disable=no-self-use
        iBase, jBase = base
        return iBase + col, jBase

    @staticmethod
    def _shiftLattice(lattice):
        """
        Shift lattice indices so 0,0 is in the center rather than the bottom left corner.

        This simply requires shifting down the j-axis.
        """
        shifted = {}
        _allI, allJ = zip(*lattice.keys())
        size = max(allJ) - min(allJ)
        assert not size % 2, "Hex must have odd number of rows"
        shift = size // 2
        for (i, j), spec in lattice.items():
            shifted[i, j - shift] = spec
        return shifted


def asciiMapFromGeomAndSym(geomType: str, symmetry: str):
    """Get a ascii map class from a geometry type."""
    from armi.reactor import geometry

    symmetry = symmetry.replace(geometry.PERIODIC, "")
    symmetry = symmetry.replace(geometry.REFLECTIVE, "")

    MAP_FROM_GEOM = {
        (geometry.HEX, geometry.THIRD_CORE): AsciiMapHexThird,
        (geometry.HEX, geometry.FULL_CORE): AsciiMapHexFullTipsUp,
        (geometry.CARTESIAN, None): AsciiMapCartesian,
        (geometry.CARTESIAN, geometry.FULL_CORE): AsciiMapCartesian,
    }

    return MAP_FROM_GEOM[(geomType, symmetry)]
