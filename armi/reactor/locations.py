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

r"""
The location module is responsible for identifying the spatial position of objects in the reactor model.

It also contains code useful for traversing regular meshes (hexagons, etc.).

The Location Object
-------------------
Each ARMI Block (and Assembly) contains a Location object whose purpose it is to identify where in the
core the structure resides. Location objects are represented as strings when printed or written because
their original primary usage was to be written directly to textual neutronics input files, but they contain
much more functionality. An assembly location in ARMI is based on the DIF3D region definition and
has a somewhat strange representation for this reason. The coordinate system is counterclockwise
spiral, as seen in the figure below.

.. image:: /.static/coreMap.png
       :width: 100%

Here are some examples of using a Location object::

    loc =  a.getLocationObject()
    ring, pos = loc.mainIndices()
    x,y = loc.coords(p=assemPitch)
    locStr = a.getLocation() # the string representation of a location object


ThetaRZ Location Objects
------------------------
ARMI can use theta-r-z objects to help it understand cylindrical systems -- as
opposed to hexagonal systems. However, the radial segment discretizations of a
cylindrical mesh are less structured than a hexagonal array. Therefore, to
these ThetaRZ location objects use a mesh object to translate integer
coordinates to spatial dimensions. Location objects as implemented
are best suited for structured grids (e.g. triangular, hexagonal, Cartesian).

.. note:: Theta-RZ is used instead of the more common RZ-Theta because the DIF3D code
          uses this convention. In turn, DIF3D uses this convention to allow the same
          numerical solver algorithms to solve all geometry options consistently.
          The numerical methods for X and Y plane solutions are analogous to
          the 2-D theta-R planes, and Z in the final position is consistent between
          XYZ, Triangular-Z, Hex-Z, and TRZ solvers.

"""
import math
import itertools

import numpy

import armi.runLog as runLog
from armi import utils
from armi.utils import hexagon
from armi.reactor import geometry


COS30 = math.sqrt(3.0) / 2.0
SIN30 = 0.5

from armi.reactor.grids import (
    BOUNDARY_0_DEGREES,
    BOUNDARY_60_DEGREES,
    BOUNDARY_120_DEGREES,
    BOUNDARY_CENTER,
    AXIAL_CHARS,
    ASCII_LETTER_A,
)
from armi.reactor import grids


def dotProduct(v1, v2):
    """
    Determines the dot product of two vectors.

    Parameters
    ----------
    v1, v2 : tuple
        Vector represented as an n dimensional tuple

    Returns
    -------
    The dot product of two vectors.
    """
    return sum((a * b) for a, b in zip(v1, v2))


def vectorLength(v1, v2=None):
    """
    Determines the length of a vector

    Parameters
    ----------
    v1, v2 : tuple
        Vector represented as an n dimensional tuple

    """
    if v2 is None:
        v2 = v1
    return math.sqrt(dotProduct(v1, v2))


def angleBetweenVectors(v1, v2):
    """
    Determines the angle between two vectors in radians.

    Parameters
    ----------
    v1, v2 : tuple
        Vector represented as an n dimensional tuple

    """
    v2Size = vectorLength(v2)
    if not v2Size:
        theta = 0.0
    else:
        theta = math.acos(dotProduct(v1, v2) / v2Size)
    return theta


class Location(object):
    """Abstract Location object used a as a base class for other concrete definitions."""

    def __init__(self, i1=None, i2=None, axial=None, label=None):
        """
        Instantiate a new Location object.

        Parameters
        ----------
        i1 : int, optional
            1st coordinate index in core 2d map (ring number in hexes)

        i2 : int, optional
            2nd coordinate in core map (ring position in hex)

        axial : str, or int optional
            a letter representing axial slab ('A', 'B', etc.). If no axial is given,
            this is a 2D (radial) location

        label : str, optional
            A label for this location, e.g. 'ExCore', 'SFP'. If in Location-label format,
            i1, i2, and axial will be inherited from it. Otherwise, the location
            will be considered Ex-core

        """
        self.i1 = i1  # will be 1 for center.
        self.i2 = i2
        self.setAxial(axial)
        if not label:
            self.label = "ExCore"
            self.makeLabel()
        else:
            self.fromLabel(label)
        self.firstChar = None

    def __eq__(self, other):
        """
        Check equality between locations.

        .. warning:: Because a Location object is mutable, this is NOT guaranteed to be consistent
                     for the same two objects.
        """
        if not issubclass(other.__class__, Location):
            return False
        considerations = [
            self.i1 == other.i1,
            self.i2 == other.i2,
            self.axial == other.axial,
            self.label == other.label,
        ]
        return all(considerations)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        """Compare two locations in a less-than sense. This allows sorting."""
        if self.i1 is None or other.i1 is None:
            return False
        if self.i1 < other.i1:
            return True
        elif self.i1 == other.i1:
            if self.i2 < other.i2:
                return True
            elif self.i2 == other.i2:
                if self.axial is None and other.axial is None:
                    return False
                elif self.axial < other.axial:
                    return True
        return False

    def __gt__(self, other):
        """Compare two locations in a greater-than sense."""
        if self.i1 > other.i1:
            return True
        elif self.i1 == other.i1:
            if self.i2 > other.i2:
                return True
            elif self.i2 == other.i2 and self.axial > other.axial:
                return True
        return False

    def setAxial(self, axialIndexOrChar):
        """
        Axial index used to be a letter A_Z but is now a number 0 through N.

        When axial index has to be represented as a single character (e.g. in some global flux solvers),
        ASCII characters listed in ``locations.AXIAL_CHARS`` are valid.
        """
        if axialIndexOrChar is None:
            axial = None
        elif isinstance(axialIndexOrChar, int):
            axial = axialIndexOrChar
        elif isinstance(axialIndexOrChar, str):
            # convert A to 0, B to 1, etc.
            axial = AXIAL_CHARS.index(axialIndexOrChar)
        else:
            raise ValueError(
                "Invalid location axial setting {0}".format(axialIndexOrChar)
            )

        if axial is not None and (axial < 0 or axial >= len(AXIAL_CHARS)):
            raise ValueError("Too many or too few axial nodes: {}".format(axial))

        self.axial = axial

    def __repr__(self):
        """
        Represent the location object as a string.

        An example Location is represented as A5002B. The first two digits represent the ring. A5 is actually
        ring 05. A7 is 07. B3 is 13. The final digit represents the axial location, starting with A at the
        bottom. The representation starts with a letter because DIF3D doesn't allow region labels to start
        with a numeric character, and the original purpose of Location was to be written directly to DIF3D inputs.
        But you don't have to convert the name to get the ring number. Just use
        the Location.mainIndices method.
        """
        self.makeLabel()  # update the label in case it's changed.
        return self.label

    def __format__(self, spec):
        return format(str(self), spec)

    def duplicate(self):
        l = self.__class__(self.i1, self.i2, self.axial)
        l.label = self.label
        return l

    def setIndexNames(self):
        pass

    def isInCore(self):
        if self.i1 is None:
            return False
        else:
            return True

    def makeLabel(self):
        """
        Creates a label based on the location. Something in ring 3, position 10, axial slab 3 will
        get A3010C

        The original purpose of these labels to name DIF3D regions

        """

        self.setIndexNames()

        if self.isInCore():
            self.getFirstChar()
        else:
            # stick with what we have. (default:ExCore)
            return
        self.label = self.firstChar + "{0:03d}".format(self.i2)
        if self.axial is not None:
            # add axial letter
            self.label = self.label + AXIAL_CHARS[self.axial]

    def setLabel(self, desc):
        """Allows for special labels like "discharged" or "fresh". """
        self.label = desc

    def coords(self, p=None, rotationDegreesCCW=0.0):
        raise NotImplementedError

    def isInSameStackAs(self, loc):
        """Determines if another location is stacked with this one (for equivalence testing)."""
        if self.i1 == loc.i1 and self.i2 == loc.i2:
            return True
        else:
            return False

    def uniqueInt(self):
        """Create a unique integer based on the location. Good for adding to SQL databases."""
        # handle empty locations too
        i1 = self.i1 or 0  # converts None to 0
        i2 = self.i2 or 0
        axial = self.axial or 0
        return 100000 * i1 + i2 * 100 + axial

    def fromUniqueInt(self, uniqInt):
        """
        Create a location based on the unique int generated above.
        
        ring 30, position 174, axial B would be 3017466.
        
        Notes
        -----
        Limits: No more than 999 positions, 99 axial positions.
        """

        if not isinstance(uniqInt, (int, numpy.integer)):
            raise ValueError(
                "Unique int {} of type {} was not an integer".format(
                    uniqInt, type(uniqInt)
                )
            )
        if uniqInt < 0:
            raise ValueError("Unique int {} was negative".format(uniqInt))
        if uniqInt >= 10 ** 8:  # 3 ints for i1, 3 for i2 and 2 for axial
            # while 999 rings is not possible with only 999 positions, other geometries (eg Cartesian) might need 999
            raise ValueError(
                "Unique int {} was larger than expected. "
                "This likely indicates more than 999 positions in the i1 (ring in hex) dimension".format(
                    uniqInt
                )
            )

        s = "{:09d}".format(uniqInt)
        self.i1 = int(s[:-5])  # or None # everything else is ring
        self.i2 = int(s[-5:-2])  # or None  # the next three from the right are position
        self.axial = int(s[-2:])  # grab the last two letters

        self.makeLabel()

    def fromLabel(self, label):
        """
        Set location parameters from a string label.

        given a label like A2034B, create a location. This allows the reverse of makeLabel to occur.
        Given a region name in REBUS, this can figure out where in the core it is. That's assuming
        someone set up the REBUS file according to our standards, of course.

        A "location label" is in the format 11222A where 11 represents the i1 index,
        222 represents the i2 index, and A represents the axial signifier.

        Parameters
        ----------
        label : str
            The label to process.

        Examples
        --------
        >>> loc.fromLabel('A2024')

        See Also
        --------
        makeLabel : does the opposite

        """
        indices = grids.ringPosFromRingLabel(label)

        if indices is None:
            # arbitrary label. excore.
            # set it up as if it's a freshly initialized one
            self.axial = None
            self.i1 = None
            self.i2 = None
            self.label = label
        else:
            self.i1, self.i2, self.axial = indices

        self.getFirstChar()
        self.makeLabel()

    def getFirstChar(self):
        """
        Converts a ring number into a character since REBUS can't handle region names
        that start with numbers.

        1 - 9  -> A
        10- 19 -> B
        20- 29 -> C, etc.
        """
        if self.i1 is None:
            self.firstChar = None
        else:
            chrNum = int(self.i1 // 10)
            if chrNum < 26:
                # should result in something like A4 for 4, B6 for 16
                self.firstChar = chr(ASCII_LETTER_A + chrNum) + str(self.i1 % 10)
            else:
                runLog.warning(
                    "invalid location. ring {0} is too many rings!".format(self.i1),
                    self,
                )

    def mainIndices(self):
        """
        This returns the standard (i1, i2) = (ring, pos) hex indices.
        ring and pos begin with 1 (not 0).
        Note how this is different than HexLocation.indices, which returns MCNP GEODST indices.

        Note that (i, j) refers to (ring, pos) in fluxRecon.py, while (i, j) refers to the MCNP
        GEODST (grid-like) indices in locations.py. Sorry for any confusion!

        Parameters
        ----------
        None

        Returns
        -------
        self.i1, self.i2 : int pair
            The value of (i2, i2) = (ring, pos) for the HexLocation object.

        Examples
        --------
        >>> loc.mainIndices()
        (4, 5)

        See Also
        --------
        locations.HexLocation.indices
        """
        return self.i1, self.i2

    def fromIndices(self, i1, i2):
        self.i1 = i1
        self.i2 = i2
        self.makeLabel()

    def getDistanceOfLocationToPoint(self, targetCoords=None, pitch=None):
        """
        Calculates the distance between the current coordinates and the targetCoords.

        This is used to help determine the optimal packing for a core

        Parameters
        ----------

        targetCoords : tuple or HexLocation
            the x, y coordinates that will be compared to current coords of this location

        pitch : float
            the pitch of the assemblies
        """

        # auto detect what the input is for auto coords and translate into a tuple
        if targetCoords:
            if not isinstance(targetCoords, tuple):
                targetCoords = targetCoords.coords(p=pitch)
        else:
            targetCoords = (0, 0)

        currentCoords = self.coords(pitch)
        d = math.sqrt(
            (currentCoords[0] - targetCoords[0]) ** 2
            + (currentCoords[1] - targetCoords[1]) ** 2
        )
        return d

    def getAngle(
        self, targetPoint=None, pointOfVectorIntersection=None, pitch=1.0, degrees=False
    ):
        """
        Determines the angle of this location compared to a targetPoint using a vector intersection point.

        The location object coordinates and targetPoint are used with the pointOfVectorIntersection to produce
        vectors.  Using these vectors, the angle between them can be calculated

        Parameters
        ----------
        targetPoint : tuple, location object
            A tuple of the x, y coordinates to be compared with

        pointOfVectorIntersection : tuple, location object
            A tuple of the x, y coordinates to be compared with

        degrees : bool, optional
            If true, return degrees
        """

        if targetPoint is None:
            targetPoint = (1, 0)
        if pointOfVectorIntersection is None:
            pointOfVectorIntersection = (0.0, 0.0)

        # auto detect what the input is for auto coords and translate into a tuple
        if targetPoint and not isinstance(targetPoint, tuple):
            targetPoint = targetPoint.coords(p=pitch)  # pylint:disable=no-member

        # auto detect what the input is for auto coords and translate into a tuple
        if pointOfVectorIntersection and not isinstance(
            pointOfVectorIntersection, tuple
        ):
            pointOfVectorIntersection = pointOfVectorIntersection.coords(
                p=pitch
            )  # pylint:disable=no-member

        referenceVector = (
            targetPoint[0] - pointOfVectorIntersection[0],
            targetPoint[1] - pointOfVectorIntersection[1],
        )
        locationVector = (
            self.coords(p=pitch)[0] - pointOfVectorIntersection[0],
            self.coords(p=pitch)[1] - pointOfVectorIntersection[1],
        )

        theta = angleBetweenVectors(referenceVector, locationVector)

        if locationVector[1] < 0:
            theta = 2.0 * math.pi - theta
        if degrees:
            theta *= 180.0 / math.pi

        return theta

    def isOnWhichSymmetryLine(self):
        """
        Return flag for which symmetry line this location is on.

        See Also
        --------
        armi.reactor.locations.HexLocation.isOnWhichSymmetryLine

        """
        return False

    def indices(self):
        return self.i1, self.i2

    def fromLocator(self, indices):
        self.i1, self.i2, self.axial = indices
        self.makeLabel()


class HexLocation(Location):
    """
    Single location in a regular hexagonal mesh.

    This is mutable. It represents a single location at a given time but any instance
    can be changed to represent any location.

    For this reason, whenever storing data for a single location, a tuple (i1, i2, ...)
    should be used instead of the location object.
    """

    def setIndexNames(self):
        self.ring = self.i1
        self.pos = self.i2

    def niceLabel(self):
        if self.isInCore():
            return "Ring,Pos= {0:3d} {1:3d}".format(self.ring, self.pos)
        else:
            return self.label

    def fromLabel(self, label):
        Location.fromLabel(self, label)
        self.ring = self.i1
        self.pos = self.i2

    def isOnWhichSymmetryLine(self):
        """
        Returns a list of what lines of symmetry this is on. If none, returns []
        If on a line of symmetry in 1/6 geometry, returns a list containing a 6.
        If on a line of symmetry in 1/3 geometry, returns a list containing a 3.
        It seems that only the 1/3 core view geometry is actually coded in here right now.

        Ring  Edge1 Edge2 Edge3
        1       1     1     1
        3       12    2     4
        5       23    3     7
        7       34    4    10
        9       45    5    13
        """

        if self.ring is None:
            return None
        else:
            if not self.ring % 2:
                # only odd numbered rings can cut lines of symmetry
                return None

            r = self.ring
            if self.pos == 1 and self.ring == 1:
                symmetryLine = BOUNDARY_CENTER
            elif self.pos == (r - 1) * 6 - ((r + 1) // 2 - 2):
                # edge 1: 1/3 symmetry line (bottom horizontal side in 1/3 core view, theta = 0)
                symmetryLine = BOUNDARY_0_DEGREES
            elif self.pos == (r + 1) // 2:
                # edge 2: 1/6 symmetry line (bisects 1/3 core view, theta = pi/3)
                symmetryLine = BOUNDARY_60_DEGREES
            elif self.pos == 1 + ((r + 1) // 2 - 1) * 3:
                # edge 3: 1/3 symmetry line (left oblique side in 1/3 core view, theta = 2*pi/3)
                symmetryLine = BOUNDARY_120_DEGREES
            else:
                symmetryLine = None

            return symmetryLine

    def coords(self, p=None, rotationDegreesCCW=0.0):
        """Figures out x, y coordinates of this location given a hex pitch p."""
        if p is None:
            p = 1.0  # useful for doing relative distance comparisons.

        i, j = self.indices()
        x = p * (COS30 * i)
        y = p * (SIN30 * i + j)

        if rotationDegreesCCW:
            x, y = utils.rotateXY(x, y, rotationDegreesCCW)

        return x, y

    def indicesAndEdge(self):
        """
        Return the i, j 0-based indices of a location in a grid as well as the edge.

        Like, for instance, in an MCNP repeated geometry grid...

        These are called MCNP GEODST coordinates.
        They look like oblique (angled or bent) x-y coordinates.

        From the MCNP5 Manual, VOL2: Figure 4-26, pg. 4-36 or so

        So, ring 5, pos 1 becomes (4, 0).
        Ring 6, pos 2 becomes (4, 1)
        Ring 3, pos 12 becomes (2, -1)
        etc.

        Notes
        -----
        This is being replaced by utils.grids.
        """
        if self.ring is None:
            return None, None, None

        ring = self.ring - 1
        pos = self.pos - 1

        if ring == 0:
            return 0, 0, 0

        ## Edge indicates which edge of the ring in which the hexagon resides.
        ## Edge 0 is the NW edge, edge 1 is the N edge, etc.
        ## Offset is (0-based) index of the hexagon in that edge. For instance,
        ## ring 3, pos 12 resides in edge 5 at index 1; it is the second hexagon
        ## in ring 3, edge 5.
        edge, offset = divmod(pos, ring)  # = pos//ring, pos%ring
        if edge == 0:
            i = ring - offset
            j = offset
        elif edge == 1:
            i = -offset
            j = ring
        elif edge == 2:
            i = -ring
            j = -offset + ring
        elif edge == 3:
            i = -ring + offset
            j = -offset
        elif edge == 4:
            i = offset
            j = -ring
        elif edge == 5:
            i = ring
            j = offset - ring
        else:
            raise ValueError(
                "Edge {} is invalid. From ring {}, pos {}".format(edge, ring, pos)
            )

        return i, j, edge

    def indices(self):
        """Return the i, j indices of a location in a grid"""
        i, j, _edge = self.indicesAndEdge()
        return i, j

    def getSymmetricIdenticalsThird(self, ring=None, pos=None, locClass=None):
        r"""
        Find the locations that are symmetric to this one in 1/3 geometry

        The number of positions :math:`N_i` in hex ring :math:`i` is

        .. math::

            N_i=
            \begin{cases}
             1              & \text{if }  i = 0 \\
             6 \times (i-1) &  \text{if } i > 0
            \end{cases}

        There are :math:`\frac{N_i}{3}` positions between one position and
        its 1/3-symmetric position. The symmetric identical are
        computed accordingly.

        .. NOTE:: If a position is computed that is greater than
             the maximum number of positions in a ring, the roll-over
             is computed by subtracting the maximum number of positions.

        Parameters
        ----------
        ring : int, optional
            ring number. Defaults to this location's ring number
        pos : int, optional
            position in ring, defaults to this location's position number
        locClass : Location object, optional
            The location object to instantiate. Defaults to HexLocation

        Returns
        -------
        otherAssems :  2 other locations that are identical in 1/3 -symmetry

        """

        if not locClass:
            locClass = HexLocation
        if ring is None:
            ring = self.ring
            pos = self.pos
        if ring == 1:
            # nothing symmetric in the center.
            return []
        locs = []
        grid = grids.hexGridFromPitch(1.0)
        indices = grid.getIndicesFromRingAndPos(ring, pos)
        identicalsIJ = grid.getSymmetricIdenticalsThird(indices)
        for ij in identicalsIJ:
            ring, pos = grid.getRingPos(ij)
            locs.append(locClass(ring, pos, self.axial))
        return locs

    def getSymmetricIdenticalsSixth(self, locClass=None):
        """Returns locations that are identical in 1/6 -symmetry"""
        if not locClass:
            locClass = HexLocation
        if self.ring == 1:
            # nothing symmetric in the center.
            return []
        numInRing = (self.ring - 1) * 6
        locs = []
        pos = self.pos
        for others_ in range(5):
            pos += self.ring - 1
            if pos > numInRing:
                pos -= numInRing
            locs.append(locClass(self.ring, pos, self.axial))
        return locs

    def getNumPositions(self, rings=None):
        """
        Return The total number of positions in the specified number of rings.

        Notes
        -----
        a single pin counts as 1 ring.
        """
        if rings is None:
            rings = self.ring

        if rings == 0:
            return 0
        else:
            return 1 + sum([6 * n for n in range(rings)])

    def getNumPosInRing(self, ring=None):
        """Return number of positions in a ring."""
        ring = self.ring if ring is None else ring
        return hexagon.numPositionsInRing(ring)

    def getNumRings(self, nPins, silent=False):
        """Return the number of rings required to hold a specific number of items, rounding up."""
        nRings = hexagon.numRingsToHoldNumCells(nPins)
        if not silent:
            nPinsFullRings = self.getNumPositions(rings=nRings)
            if nPins != nPinsFullRings:
                runLog.warning(
                    "{0} does not fit exactly into a hex grid of any number of rings. "
                    "Rounding up to {1} rings which can hold {2} pins)"
                    "".format(nPins, nRings, nPinsFullRings),
                    single=True,
                    label="Non-exact number of positions in hex lattice",
                )
        return nRings

    def getNumPinsInLine(self, rings=None):
        """Return how many pins in a line fit in the center of a hex w/ this many rings."""
        if rings is None:
            if self.ring < 1:
                raise RuntimeError(
                    (
                        "Cannot determine number of pins in a hex "
                        "bundle of {0} (or no) rings"
                    ).format(rings)
                )
            rings = self.ring

        return 1 + 2 * (rings - 1)

    def containsWhichFDMeshPoints(
        self, resolution=1, fullCore=False, rectangular=False
    ):
        r"""
        Compute the difference mesh points contained in a certain location.

        When building finite different meshes, a lookup table from mesh point to
        block is required. This method returns a list of x, y indices that
        the triangle meshes in this location will have in 1/3 symmetric 120 geometry.

        The mesh indices returned will be 2-d (just x and y) and will start at 1.

        See Figures 2.4 and 2.6 in the DIF3D manual to understand.

        Parameters
        ----------
        resolution : int, optional
            How many subdivisions are made in the side of each hex
                1 means there are 6 triangles.
                2 means there are 6*4 = 24
                3 means there are 6*9 = 54
                4 means there are 6*4*4 = 96, etc.

        fullCore : bool, optional
            Makes this relevant for full core with DIFNT (but not DIF3D, which uses "cartesian" triangle meshing)

        rectangular : bool, optional
            Use the rectangular indexing domain instead of the parallelogram domain.

        Notes
        -----
        DIF3D full core uses a "rectangular" mesh layout while DIFNT full core uses the rhomboid full core mesh layout
        so for full core DIFNT, use this. For full core DIF3D, use `rectangular=True`

        If a hex side is broken into d divisions, then there are
          * 4d-1 triangles along the center of the hex in the i direction
          * 2d+1 triangles along the bottom of the hex in the i direction
          * 2d stacks of triangles in the j-direction.

        The number of triangles in the i-direction between the first triangle above the centerpoint of two
        neighboring hexagons is equal to (num center -1)/2 + (num bottom - 1)/2+1, which reduces to 3d.

        Results should come out left-to-right, top-to-bottom.

        .. figure:: /.static/triangle_and_hex_mesh.png
            :target: ../_static/triangle_and_hex_mesh.png
            :align: center
            :alt: Finite difference mesh layout diagram
            :width: 50%

            **Figure 1.** Finite-difference mesh layout of 4 assemblies in locations (1, 1), (2, 1), (2, 2), (2, 6)
        """

        if not fullCore:
            symLine = self.isOnWhichSymmetryLine()
        else:
            symLine = False
        numTriangleStacks = 2 * resolution
        numAcrossCenter = 4 * resolution - 1

        topCenterI, topCenterJ = self._getTopCenterIndices(resolution, rectangular)
        # with this one known, we can find all others

        deltaMeshJ = self._getDeltaMeshJ(numTriangleStacks, symLine)

        # Loop through each j row and determine which i indices are present
        indicesHere = []
        for delta in reversed(deltaMeshJ):  # top-to-bottom
            if delta < 0:
                # bottom half of the hexagon
                if symLine == BOUNDARY_120_DEGREES or symLine == BOUNDARY_CENTER:
                    # is on 120-degree line. only get half the guys.
                    # 2 level:  num = 1
                    # 4 levels: num = 1, then 1, 2, 3
                    # 8 levels: num = 1, then 1, 2, 3, then 1, 2, 3, 4, 5, ...
                    # so...
                    # the -1 level will have (numAcrossCenter-1)/2 items (1, 3, 5 for 2, 4, 8 levels)
                    # the -2 level will have (numAcrossCenter-1)/2-1*2
                    # the -3 level will have (numAcrossCenter-1)/2-2*2
                    # the -4 level will have (numAcrossCenter-1)/2-3*2
                    # in general: the x-level will have
                    numHere = (numAcrossCenter - 1) // 2 + 2 * (
                        delta + 1
                    )  # delta is negative!
                    start = 1  # always starts at one if on this symmetry line.
                else:
                    numHere = numAcrossCenter - 2 * abs(delta + 1)
                    start = topCenterI - (numHere - 1) // 2 + (not rectangular) * delta
            else:
                # top half of the hex.
                if symLine == BOUNDARY_120_DEGREES or symLine == BOUNDARY_CENTER:
                    # special allowance for central positions.)
                    # one of the three triangles on the top half of the is missing in 120 sym, but it's there otherwise.
                    # 120-degree symmetry line.
                    start = 1
                    # constant number in this half.
                    numHere = (numAcrossCenter - 1) // 2 + 1
                else:
                    numHere = numAcrossCenter - 2 * abs(delta)
                    start = topCenterI - (numHere - 1) // 2 + (not rectangular) * delta

            for i in range(numHere):
                ii, ji = start + i, topCenterJ + delta
                indicesHere.append((ii, ji))

        return indicesHere

    def _getTopCenterIndices(self, resolution, rectangular):
        """Determine the mesh indices of the top-center mesh point in this location."""
        # get x, y indices to get away from the ring basis.
        # indices starts with (0, 0) in the middle, with (r2, p1) -> (1, 0), etc.  (x is on the pos 1 ray)

        numAxialLevels = 2 * resolution
        xi, yi = self.indices()
        if rectangular:
            topCenterI = 2 + (3 * resolution) * xi
        else:
            # 4*d b/c each increase in xi moves you back by numstacks/2
            topCenterI = 1 + (4 * resolution) * xi + (yi * numAxialLevels)
        topCenterJ = 1 + xi * numAxialLevels // 2 + numAxialLevels * yi
        return topCenterI, topCenterJ

    def _getDeltaMeshJ(self, numAxialLevels, symLine):
        """Determine the values of the axial coordinates contained in this hex."""
        if symLine == BOUNDARY_0_DEGREES or symLine == BOUNDARY_CENTER:
            # this is cut on the bottom. will only have top levels
            deltaAxial = range(numAxialLevels // 2)
        else:
            deltaAxial = range(-numAxialLevels // 2, numAxialLevels // 2)
            # -1 0 for 2 axial levels.
            # -2, -1, 0, 1 for 4 axial levels. Perfect since we're already in top

        return deltaAxial

    def fromLocator(self, indices):
        i, j, self.axial = indices
        self.i1, self.i2 = grids.indicesToRingPos(i, j)
        self.makeLabel()


class CartesianLocation(Location):
    """
    Single location in a regular Cartesian grid.

    This is mutable. It represents a single location at a given time but any instance
    can be changed to represent any location.

    For this reason, whenever storing data for a single location, a tuple (i1, i2, ...)
    should be used instead of the location object.
    """

    def coords(self, pitchTuple=None, rotationDegreesCCW=0.0):
        """Returns x, y coords of the center of this location, assuming square if only xw is given."""
        if self.xi is None:
            return (None, None)
        if pitchTuple is None:
            pitchTuple = (1.0, 1.0)  # useful for relative comparisons.
        xw, yw = pitchTuple
        if not yw:
            yw = xw

        x = (self.xi + 0.5) * xw
        y = (self.yi + 0.5) * yw
        if rotationDegreesCCW:
            x, y = utils.rotateXY(x, y, rotationDegreesCCW)
        return x, y

    def setIndexNames(self):
        """Create a label based on indices."""
        self.xi = self.i1
        self.yi = self.i2

    def getNumPosInRing(self, ring=None):
        """Get number of positions in a ring."""
        if ring is None:
            ring = self.i1

        if ring == 0:
            return 0
        elif ring == 1:
            return 1
        else:
            return (ring - 1) * 8

    def getNumPositions(self, rings=None):
        """Return The total number of positions in the specified number of rings."""
        if rings is None:
            rings = self.i1
        return sum(self.getNumPosInRing(ringNum) for ringNum in range(rings + 1))

    def getNumRings(self, nPins, silent=False):
        """Return the number of rings required to hold a specific number of items, rounding up."""
        numPositions = 0
        for nRings in itertools.count(0):
            numPositions += self.getNumPosInRing(nRings)
            if not silent and numPositions > nPins:
                runLog.warning(
                    "{0} does not fit exactly into a cartisian grid of any number of rings. "
                    "Rounding up to {1} rings which can hold {2} pins)"
                    "".format(nPins, nRings, numPositions),
                    single=True,
                    label="Non-exact number of positions in cartesian lattice",
                )
            if numPositions >= nPins:
                return nRings


class ThetaRZLocation(Location):
    """
    Location that works in 3-D cylindrical geometry.

    .. note:: that this location object only works if there is a ThRZmesh
              object with directions labeled ('R' and 'Th')

    ThetaRZ location object names represent their discrete position in the mesh
    object just like in Hexagonal Location Objects. The first two digits represent
    the azimuthal position, the next three digits represent the radial position and
    the last digits represents the axial position. For Example, ThetaRZ location
    A5002B is in the fifth (A5 > 5) azimuthal position, the second radial position (002 > 2) and the
    second axial (B > 2) position.

    """

    def __init__(self, i1=None, i2=None, axial=None, label=None, ThRZmesh=None):
        r""" use the general location method plus add mesh and Theta RZ specific labels"""
        Location.__init__(self, i1=i1, i2=i2, axial=axial, label=label)
        if ThRZmesh is None:
            ThRZmesh = Mesh()
        self.ThRZmesh = ThRZmesh
        self.setIndexNames()

    def getMeshObject(self):
        return self.ThRZmesh

    def duplicate(self):
        l = Location.duplicate(self)
        l.ThRZmesh = self.ThRZmesh
        return l

    def setIndexNames(self):
        """Set ThetaRZ specific index labels."""
        self.theta = self.i1
        self.radial = self.i2

    def niceLabel(self):
        if self.isInCore():
            runLog.info("Theta, Radial= {0:3d} {1:3d}".format(self.theta, self.radial))
        else:
            return self.label

    def fromLabel(self, label):
        """Transform lable to ThetaRZ coordinates."""
        super(ThetaRZLocation, self).fromLabel(label)
        self.setIndexNames()

    def Rcoords(self):
        """
        Figures out R coordinates of the center of a Theta-R-Z voxel given theta-R mesh object 
        parameters.
        """
        if self.radial > 0 and self.radial < len(self.ThRZmesh.getPositions(label="R")):
            R = (self.radialInner() + self.radialOuter()) / 2.0
        else:
            # n = 0
            runLog.warning(
                "Error: Radial Index ({}) location not INSIDE mesh ".format(self.radial)
            )
            runLog.warning(self.ThRZmesh.getPositions(label="R"))
            R = None
        return R

    def ThRcoords(self):
        """
        Figures out R, theta coordinates of the center of a Theta-R-Z voxel given theta-R mesh 
        object parameters
        """
        R = self.Rcoords()

        if self.theta > 0 and self.theta < len(self.ThRZmesh.getPositions(label="Th")):
            Th = (self.thetaInner() + self.thetaOuter()) / 2.0
        else:
            runLog.warning(
                "Error: Azimuthal Index ({0}) location not INSIDE mesh ".format(
                    self.theta
                )
            )
            runLog.warning(self.ThRZmesh.getPositions(label="Th"))
            Th = None

        return Th, R

    def ThRZcoords(self):
        """
        Figures out R, theta and Z coordinates of the center of a Theta-R-Z voxel given theta-R 
        mesh object parameters.
        """
        Th, R = self.ThRcoords()

        if self.axial >= 0 and self.axial < len(self.ThRZmesh.getPositions(label="Z")):
            Z = (
                self.ThRZmesh.getUpper(label="Z", n=(self.axial - 1))
                + self.ThRZmesh.getUpper(label="Z", n=(self.axial))
            ) * 0.5
        else:
            runLog.warning(
                "Error: Axial Index ({0}) location not INSIDE mesh ".format(self.axial)
            )
            runLog.warning(self.ThRZmesh.getPositions(label="Z"))
            Z = None

        return Th, R, Z

    def radialInner(self):
        """
        This method returns the inner radial position of a Theta-R-Z voxel given a Theta-R mesh 
        object.
        """
        if self.radial in range(1, len(self.ThRZmesh.getPositions(label="R"))):
            R = self.ThRZmesh.getUpper(label="R", n=(self.radial - 1))
        else:
            runLog.warning(
                "Error: Radial Index ({0}) location not INSIDE mesh ".format(
                    self.radial
                )
            )
            runLog.warning(self.ThRZmesh.getPositions(label="R"))
            R = None
        return R

    def radialOuter(self):
        """
        This method returns the outer radial position of a Theta-R-Z voxel given a Theta-R mesh 
        object.
        """
        if self.radial in range(1, len(self.ThRZmesh.getPositions(label="R"))):
            R = self.ThRZmesh.getUpper(label="R", n=(self.radial))
        else:
            runLog.warning(
                "Error: Radial Index ({0}) location not INSIDE mesh ".format(
                    self.radial
                )
            )
            runLog.warning(self.ThRZmesh.getPositions(label="R"))
            R = None
        return R

    def thetaInner(self):
        """
        This method returns the inner theta position of a Theta-R-Z voxel given a Theta-R mesh 
        object.
        """
        if self.theta in range(1, len(self.ThRZmesh.getPositions(label="Th"))):
            Th = self.ThRZmesh.getUpper(label="Th", n=(self.theta - 1))
        else:
            runLog.warning(
                "Error: Azimuthal Index ({0}) location not INSIDE mesh ".format(
                    self.theta
                )
            )
            runLog.warning(self.ThRZmesh.getPositions(label="Th"))
            Th = None
        return Th

    def axialOuter(self):
        r"""
        This method returns the outer axial position of a Theta-R-Z voxel given a Theta-R mesh 
        object.
        """
        if (self.axial + 1) in range(1, len(self.ThRZmesh.getPositions(label="Z"))):
            Z = self.ThRZmesh.getUpper(label="Z", n=(self.axial + 1))
        else:
            Z = None
        return Z

    def axialInner(self):
        r"""
        This method returns the inner axial position of a Theta-R-Z voxel given a Theta-R mesh 
        object.
        """
        if self.axial in range(0, len(self.ThRZmesh.getPositions(label="Z"))):
            Z = self.ThRZmesh.getUpper(label="Z", n=self.axial)
        else:
            Z = None
        return Z

    def thetaOuter(self):
        r"""
        This method returns the outer radial position of a Theta-R-Z voxel given a Theta-R mesh 
        object.
        """
        if self.theta in range(1, len(self.ThRZmesh.getPositions(label="Th"))):
            Th = self.ThRZmesh.getUpper(label="Th", n=(self.theta))
        else:
            runLog.warning(
                "Error: Azimuthal Index ({}) location not INSIDE mesh ".format(
                    self.theta
                )
            )
            runLog.warning(self.ThRZmesh.getPositions(label="Th"))
            Th = None
        return Th

    def coords(self, p=None, rotationDegreesCCW=0.0):
        """
        Figures out x, y coordinates of the center of a Theta-R-Z voxel given theta-R mesh object 
        parameters.

        Notes
        ----- 
        p is a dummy variable only there so this method is consistent with the coords method from
        HexLocation so getDistanceOfLocationToPoint can be defined at the base Location object level
        """
        Th, R = self.ThRcoords()

        x = R * math.cos(Th)
        y = R * math.sin(Th)
        if rotationDegreesCCW:
            x, y = utils.rotateXY(x, y, rotationDegreesCCW)
        return x, y

    def getVolume(self, refHeight=None, axial=None):
        """
        Return the volume of the radial segment.

        Parameters
        ----------
        refHeight : float
            the height of a radial node in the same units as the
            locations mesh object

        axial : int
            the axial node of the mesh

        Notes
        -----
        adding an axial node will over write a reference height
        also, there needs to be a 'Z'-labeled mesh in the mesh object for this
        to define the height, but you knew that already
        """

        if axial and ("Z" in self.ThRZmesh.getLabelDimensions()):
            refHeight = self.ThRZmesh.getDi(n=axial, label="Z")
        if refHeight:
            return self.getZArea() * refHeight
        else:
            runLog.warning(
                "Cannot calculate volume with height of {0}".format(refHeight)
            )
            return None

    def getInnerRArea(self, refHeight=None, axial=None):
        """
        Return the area normal to the r direction on the inside of the radial segment.

        Parameters
        ----------
        refHeight : float
            the height of a radial node in the same units as the
            locations mesh object

        axial : int
            the axial node of the mesh

        Notes
        -----
        adding an axial node will over write a reference height
        also, there needs to be a 'Z'-labeled mesh in the mesh object for this
        to define the height, but you knew that already
        """
        if axial and ("Z" in self.ThRZmesh.getLabelDimensions()):
            refHeight = self.ThRZmesh.getDi(n=axial, label="Z")
        if refHeight:
            return (
                (self.thetaOuter() - self.thetaInner()) * self.radialInner() * refHeight
            )

    def getOuterRArea(self, refHeight=None, axial=None):

        if axial and ("Z" in self.ThRZmesh.getLabelDimensions()):
            refHeight = self.ThRZmesh.getDi(n=axial, label="Z")
        if refHeight:
            return (
                (self.thetaOuter() - self.thetaInner()) * self.radialOuter() * refHeight
            )

    def getZArea(self):
        return (
            (self.radialOuter() ** 2 - self.radialInner() ** 2)
            / 2.0
            * (self.thetaOuter() - self.thetaInner())
        )


class Mesh(object):
    """
    This object helps ARMI define and pass structured orthogonal meshes (X, Y, Z)
    or (R, Z, Th). When going from X, Y, Z on orthogonal, but non-regular meshes
    (the pitch isn't constant) you need to know what the mesh is in order to
    determine the cartesian coordinates
    also, you're not limited to 3 dimensions so this mesh

    Rebase meshes such that index 1 is the first index rather than 0
    This is accomplished by setting 0 as the first index

    Notes
    -----
    This is intended to be replaced with the newer grids.ThetaRZGrid functionality.
    """

    def __init__(self):
        """
        Initilizes mesh object.

        self.di dictionary indexed by direction label ('X', 'Y', etc) of differences
        self.i dictionary indexed by direction label('X', 'Y', etc) of positions
        """
        # set of lists of nodal differences
        self.di = {}
        # self of upper boudns
        self.i = {}

    def getNumDimensions(self):
        """Returns the number of dimensions in the mesh."""
        return len(self.di.keys())

    def getLabelDimensions(self):
        """Returns the labels of the dimensions in the mesh."""
        return self.di.keys()

    def getDiLength(self, label):
        """ 
        Rreturns the difference in lengths in the mesh in the direction labeled.
        
        Parameters
        ----------
        label: string
            The label of the direction (i.e 'X', 'Y', 'Theta', 'R', 'Z', 'E')
        """
        return len(self.di[label])

    def getDi(self, n=None, label=None):
        """
        Returns the n-th difference in lengths in the mesh in the direction labeled.
        
        Parameters
        ----------
        n: integer
            The index of position with in mesh structure.
            
        label: string
            The label of the direction (i.e 'X', 'Y', 'Theta', 'R', 'Z', 'E')
        """
        return self.di[label][n]

    def getUpper(self, n=None, label=None):
        """
        Returns the outer position of the n-th element in the mesh in the direction labeled.
        
        Parameters
        ----------
        n: integer 
            The index of position with in mesh structure
            
        label: string
            The label of the direction (i.e 'X', 'Y', 'Theta', 'R', 'Z', 'E')
        """
        return self.i[label][n]

    def getUpperLowerFromPosition(self, p=None, label=None, sigma=1e-7):
        """
        Get the upper and lower interface indexes for a given position in a given direction.
        
        p is the position in the direction labeled label is the string name of the target 
        directions label.
        """

        if p in self.getPositions(label=label):
            return self.i[label].index(p), self.i[label].index(p)
        elif p < self.i[label][0]:
            # print "Warning: position %1.5E is less than lowest interface %1.5E" % (p, self.i[label][0])
            return None, 0
        elif p > (self.i[label][-1] * (1 + sigma)):
            # print "Warning: position %1.5E is greater than the greatest interface %1.5E" % (p, self.i[label][-1])
            return len(self.i[label]) + 1, None
        j = 0
        while j + 1 <= len(self.i[label]):
            if (self.i[label][j] * (1 - sigma)) <= p and p < (
                self.i[label][j + 1] * (1 + sigma)
            ):
                return j, (j + 1)
            j += 1

    def isPositionInMesh(self, label=None, p=None, sigma=1e-3):

        pI = self.getClosestUpperFromPosition(p, label)

        if math.fabs(self.i[label][pI] - p) < sigma:
            return True
        else:
            return False

    def getClosestUpperFromPosition(self, p=None, label=None):
        """Returns the closest position in the mesh in the direction labeled, label."""
        if p in self.i[label]:
            return self.i[label].index(p)
        else:
            """
            i = 0
            self.i[label][i]-p
            self.di[label][i]
            len(self.i[label])
            while math.fabs(self.i[label][i]-p) > self.di[label][i] and i < len(self.i[label]):
                i += 1
            if  math.fabs(p - self.i[label][i]) < (self.di[label][i]/2):
                # closer to lower bounds
                # or looped through the mesh without finding a closest match
                if i == (len(self.i[label])-1) or math.fabs(p - self.i[label][i]) < math.fabs(p - self.i[label][i+1]):
                    return i
                else:
                    return (i + 1)
            else:
                return i + 1
            """
            return self.i[label].index(min(self.i[label], key=lambda x: abs(x - p)))

    def addFromDeltas(self, deltas=None, labels=None):
        """
        Define mesh(s) in the labeled direction(s).
        
        Parameters
        ----------
        deltas: a list, either a list of lists or a single list of mesh differences (like heights in an assembly)
        labels: a string or list of strings of the labels (i.e 'X', 'Y', 'Theta', 'R', 'Z', 'E') of directions

        Notes
        -----
        If you want to define multiple directions in one command then deltas should be a 
        list of lists, and there should be a label for every direction and the order of labels and 
        deltas should be lined up.
        """

        # ensure there's a label for each direction
        if hasattr(labels, "__iter__"):
            if len(labels) <= len(deltas):
                # labels will be made up
                for i in range(
                    (len(self.di) + len(labels)),
                    len(self.di) + 1 + len(deltas) - len(labels),
                ):
                    label = "Direction%d" % i
                    labels.append(label)
            else:
                # there is a label for each direction
                pass
        elif labels is None:
            if hasattr(deltas[0], "__iter___"):
                # there are multiple directions that need labels
                labels = []
                for i in range(1, 1 + len(deltas) - len(labels)):
                    label = "Direction%d" % i
                    labels.append(label)
            else:
                labels = "Direction%d" % (len(self.di) + 1)

        if hasattr(deltas[0], "__iter__"):
            # there are multiple lists
            for delta, label in zip(deltas, labels):
                self.addOneDirectionFromDeltas(deltas=delta, label=label)
        else:
            self.addOneDirectionFromDeltas(deltas=deltas, label=labels)

    def addFromPositions(self, positions=None, labels=None):
        """ 
        Define mesh(s) in the labeled direction(s).
        
        Parameters
        ----------
        positions: list 
            Either a list of lists or a single list of mesh positions
        
        labels: a string or list of strings of the labels (i.e 'X', 'Y', 'Theta', 'R', 'Z', 'E') of directions

        Notes
        -----
        If you want to define multiple directions in one command then positions should be a list of lists,
        and there should be a label for every direction and the order of labels and positions should be lined up
        """

        # ensure there's a label for each direction
        if isinstance(labels, list):
            if len(labels) <= len(positions):
                # labels will be made up
                for i in range(
                    (len(self.di) + len(labels)),
                    len(self.di) + 1 + len(positions) - len(labels),
                ):
                    label = "Direction%d" % i
                    labels.append(label)
            else:
                # there is a label for each direction
                pass
        elif labels is None:
            if isinstance(positions[0], list):
                # there are multiple directions that need labels
                labels = []
                for i in range(1, 1 + len(positions) - len(labels)):
                    label = "Direction%d" % i
                    labels.append(label)
            else:
                labels = "Direction%d" % (len(self.di) + 1)

        if isinstance(positions[0], list):
            # there are multiple lists
            for label, position in zip(labels, positions):
                self.addOneDirectionFromPositions(positions=position, label=label)
        else:
            self.addOneDirectionFromPositions(positions=positions, label=labels)

    def addFromRegularIntervals(self, dIs=None, Ns=None, labels=None):
        """
        Defines regular intervals mesh(s) in the labeled direction(s).
        
        Parameters
        ----------
        dIs: a float or a list of floats of the regular difference (think pitch)
        labels: a string or list of strings of the labels (i.e 'X', 'Y', 'Theta', 'R', 'Z', 'E') of directions
        Ns: a float or a list of floats of the number of elements in the mesh

        Notes
        -----
        If you want to define multiple directions in one command then dIs and Ns should be a list,
        and there should be a label for every direction and the order of labels, dIs and Ns should be lined up
        """

        # ensure there's a label for each direction
        if hasattr(labels, "__iter__"):
            if len(labels) <= len(dIs):
                # labels will be made up
                for i in range(1, 1 + len(dIs) - len(labels)):
                    label = "Direction{0}".format(i)
                    labels.append(label)
            else:
                # there is a label for each direction
                pass

        elif labels is None:
            if hasattr(dIs[0], "__iter__"):
                # there are multiple directions that need labels
                labels = []
                for i in range(1, 1 + len(dIs) - len(labels)):
                    label = "Direction{0}".format(i)
                    labels.append(label)
            else:
                labels = "Direction{0}".format(len(self.di) + 1)

        for dI, N, label in zip(dIs, Ns, labels):
            self.addOneDirectionFromRegInterval(dI=dI, N=N, label=label)

    def addFromMaximums(self, Maxs=None, Ns=None, labels=None):
        """
        Defines regular intervals mesh(s) in the labeled direction(s) from a maximum position and
        number of nodes.
        
        Parameters
        ----------
        Maxs: a float or a list of floats of the regular difference (think pitch)
        labels: a string or list of strings of the labels (i.e 'X', 'Y', 'Theta', 'R', 'Z', 'E') of directions

        (note) if you want to define multiple directions in one command then deltas should be a list of lists,
        and there should be a label for every direction and the order of labels and deltas should be lined up
        """
        if hasattr(Maxs, "__iter__"):
            dIs = []
            for max, n in zip(Maxs, Ns):
                dIs.append(max / n)
            self.addFromRegularIntervals(dIs=dIs, Ns=Ns, labels=labels)
        else:
            self.addRegDirectionFromMax(L=Maxs, N=Ns, label=labels)

    def addOneDirectionFromDeltas(self, deltas=None, label=None):
        """
        Defines regular intervals mesh in a single direction.
        
        Parameters
        ----------
        deltas: a list of mesh differences (like heights in an assembly)
        label: a string of the labels (i.e 'X', 'Y', 'Theta', 'R', 'Z', 'E') of directions
        """

        # add a direction based on the position differences
        # assume deltas is 1-D list
        if label is None:
            label = "Direction%d" % (len(self.di.keys()) + 1)
        L = 0
        self.di[label] = []
        self.i[label] = []

        for dl in deltas:
            self.di[label].append(dl)
            L += dl
            self.i[label].append(L)

        self.checkMesh(label=label)

    def addOneDirectionFromPositions(self, positions=None, label=None):
        """
        Defines regular intervals mesh in a single direction.
        
        Parameters
        ----------
        positions: a list of mesh positions
        label: a string of the labels (i.e 'X', 'Y', 'Theta', 'R', 'Z', 'E') of directions
        """
        # add a direction based on the position differences
        # assume deltas is 1-D list
        if label is None:
            label = "Direction{0}".format(len(self.i.keys()) + 1)
        self.di[label] = []
        self.i[label] = []
        l = 0

        for L in sorted(positions):
            dl = L - l
            self.di[label].append(dl)
            self.i[label].append(L)
            l = L
        self.checkMesh(label=label)

    def addOneDirectionFromRegInterval(self, dI=None, N=None, label=None):
        """
        Defines regular intervals mesh in a single direction.
        
        Parameters
        ----------
        dI: the standard regular interval
        N: the number of elements in a mesh
        label: a string of the labels (i.e 'X', 'Y', 'Theta', 'R', 'Z', 'E') of directions
        """

        if label is None:
            label = "Direction{0}".format(len(self.i.keys()) + 1)
        self.di[label] = []
        self.i[label] = []
        L = 0
        self.di[label] = [L]
        self.i[label] = [L]
        for n in range(N):
            L += dI
            self.di[label].append(dI)
            self.i[label].append(L)

    def addRegDirectionFromMax(self, L=None, N=None, label=None):
        """
        Defines regular intervals mesh in a single direction based on the maximum position.
        
        Parameters
        ----------
        Maximum: the maximum position on a mesh (think height of an assembly)
        N: the number of elements in a mesh
        label: a string of the labels (i.e 'X', 'Y', 'Theta', 'R', 'Z', 'E') of directions
        """
        dI = L / N
        self.addOneDirectionFromRegInterval(dI=dI, N=N, label=label)

    def checkMesh(self, label=None):
        """
        This ensures that 0 is included in the mesh.
        
        Notes
        ----- 
        If the mesh includes both negative and positive values it doesn't
        need to have a 0 position, otherwise its inferred that you need a 0
        position and this helps you generated it
        """
        if (
            (self.i[label][0] > 0 and self.i[label][-1] > 0)
            or (self.i[label][0] < 0 and self.i[label][-1] < 0)
            and (0 not in self.i[label])
        ):
            # the mesh is entirely on one side of 0
            # these meshes should include 0 so that the first index defines the upper bound and index - 1 defines the lower bounds
            self.appendUpper(label=label, p=0)

    def setIInternal(self):
        """If you define a meshes set of differences this updates the positions."""
        # if the di vectors are defined this method populates the upper limit vector
        self.i = {}
        for label in self.di.keys():
            self.i[label] = []
            L = 0
            for l in self.di[label]:
                L += l
                self.i[label].append(L)

    def setDiInternal(self):
        """If you define a meshes set of positions this updates the differences."""
        # if the di vectors are defined this method populates the upper limit vector
        self.di = {}
        for label in self.i.keys():
            self.di[label] = []
            l = 0
            for L in self.i[label]:
                dl = L - l
                self.di[label].append(dl)
                l = L

    def appendUpper(self, label=None, p=None):
        """
        This method adds an additional position in the I vector to a given direction.
        
        Examples
        --------
        If you are defining a grid you can define an additional stack of
        elements with a verticle mesh that doesn't align with the initial mesh and
        use this method to fill in the gaps and update the differences.
        """

        # check to see if direction is defined
        if label not in self.i.keys():
            self.i[label] = []
            self.di[label] = []

        if len(self.i[label]) == 0:
            self.i[label].append(0)
            self.di[label].append(0)
            if p != 0:
                self.i[label].append(p)
                self.di[label].append(p)

        if p not in self.i[label]:

            # determine where the position p fits into the grid
            L, U = self.getUpperLowerFromPosition(p=p, label=label)

            if L is None:
                # p is below the lowest position in the mesh
                self.i[label] = [p] + self.i[label]
                if len(self.i[label]) > 1:
                    self.di[label] = [p, (self.di[label][0] - p)] + self.di[label][1:]
                else:
                    self.di[label] = [p, (self.di[label][0] - p)] + self.di[label][1:]

            elif U is None:
                # p is above hightest position in the mesh
                self.di[label].append(p - self.i[label][-1])
                self.i[label] = self.i[label] + [p]

            else:
                # position p is between positions (L, U) in the direction
                # update the differences
                # self.di[label] = self.di[label][:L] + [(p - self.i[label][L]), (self.i[label][U] - p)] + self.di[label][U:]
                self.di[label] = (
                    self.di[label][:U]
                    + [(p - self.i[label][L]), (self.i[label][U] - p)]
                    + self.di[label][U + 1 :]
                )
                # redefine the mesh with new position
                self.i[label] = self.i[label][:U] + [p] + self.i[label][U:]
        else:
            # p is already in the mesh, so you're done
            pass

    def appendFromBounds(self, label=None, p1=None, p2=None, n=None):
        """
        Adds mesh points from bounds (upper and lower) and number of cells between the bounds.

        Parameters
        ----------
        label : string
            direction label

        p1: float
            inner position

        p2: float
            outer position

        n: int
            number of cells between the bounds

        See Also
        --------
        armi.reactor.reactors.findAllAziMeshPoints
        armi.reactor.reactors.findAllRadMeshPoints
        """

        di = (p2 - p1) / n

        p = p1
        self.appendUpper(label=label, p=p)
        for i in range(1, n):
            p += di
            self.appendUpper(label=label, p=p)
        self.appendUpper(label=label, p=p2)

    def getPositions(self, label=None):
        return self.i[label][:]

    def getDifferences(self, label=None):
        return self.di[label][:]

    def getMaximum(self, label=None):
        return self.i[label][-1]

    def getThRLocations(self):
        r"""
        This method returns a list of location objects for each node bound by the positions in the 
        mesh.
        
                  ----------- I['R'][r+1]
                  |          |
                  |          |
        I['Th'][t]| Location | I['Theta'][t+1]
                  |[t+1][r+1]|
                  |          |
                  ------------I['R'][r]
        
        """
        # check directions for see there is an R and Th direction
        if not self.checkThR():
            runLog.warning(
                "Warning both R and Th are not present in mesh object with dimensions:"
            )
            runLog.warning(self.getLabelDimensions())

        locations = []
        for theta in range(1, self.getDiLength(label="Th")):
            for radial in range(1, self.getDiLength(label="R")):
                locations.append(ThetaRZLocation(i1=theta, i2=radial, ThRZmesh=self))

        return locations

    def getThRZLocationsFromBounds(
        self,
        r1=None,
        r2=None,
        t1=None,
        t2=None,
        z1=None,
        z2=None,
        units="Radians",
        sigma=1e-4,
    ):
        """
        This method returns a list of locations bounded by defined surfaces.

        Parameters
        ----------
        r1 : float
            inner radius of control volume
        r2 : float
            outer radius of control volume
        t1 : float
            inner azimuthal location of control volume
        t2 : float
            inner azimuthal of control volume
        z1 : float
            inner axial location of control volume
        z2 : float
            inner axial of control volume
        units: string
            flag to use either radians (default) or degrees
        sigma: float
            acceptable relative error (i.e. if one of the positions in the mesh are within this
            error it'll act the same if it matches a position in the mesh)

        """

        if units.lower() == "degrees":
            mult = math.pi / 180.0
            t1 = math.pi / 180.0 * t1
            t2 = math.pi / 180.0 * t2

        # check that mesh includes Th and R
        if not self.checkThR():
            runLog.warning(
                "Warning both R and Th are not present in mesh object with dimensions:"
            )
            runLog.warning(self.getLabelDimensions())

        locations = []
        # check to see if positions are in mesh
        # if r1 in self.getPositions('R') and r2 in self.getPositions('R') and t1 in self.getPositions('Th') and t2 in self.getPositions('Th') and z1 in self.getPositions('Z') and z2 in self.getPositions('Z'):

        if (
            self.isPositionInMesh(p=r1, label="R", sigma=sigma)
            and self.isPositionInMesh(p=r2, label="R", sigma=sigma)
            and self.isPositionInMesh(p=t1, label="Th", sigma=sigma)
            and self.isPositionInMesh(p=t2, label="Th", sigma=sigma)
            and self.isPositionInMesh(p=z1, label="Z", sigma=sigma)
            and self.isPositionInMesh(p=z2, label="Z", sigma=sigma)
        ):

            #'yay! the bounds are in the mesh'

            rIndexLower = self.getClosestUpperFromPosition(p=r1, label="R")
            rIndexUpper = self.getClosestUpperFromPosition(p=r2, label="R")
            thIndexLower = self.getClosestUpperFromPosition(p=t1, label="Th")
            thIndexUpper = self.getClosestUpperFromPosition(p=t2, label="Th")
            zIndexLower = self.getClosestUpperFromPosition(p=z1, label="Z")
            zIndexUpper = self.getClosestUpperFromPosition(p=z2, label="Z")

        else:
            runLog.warning(
                "Warning not all positions are in the Th-R mesh, the locations are the closest"
            )
            runLog.warning(t1, t2, r1, r2, z1, z2)
            runLog.warning(self.i)
            i1, i2 = self.getUpperLowerFromPosition(p=r1, label="R", sigma=sigma)
            rIndexLower = i1
            i1, i2 = self.getUpperLowerFromPosition(p=r2, label="R", sigma=sigma)
            rIndexUpper = i2
            i1, i2 = self.getUpperLowerFromPosition(p=t1, label="Th", sigma=sigma)
            thIndexLower = i1
            i1, i2 = self.getUpperLowerFromPosition(p=t2, label="Th", sigma=sigma)
            thIndexUpper = i2
            i1, i2 = self.getUpperLowerFromPosition(p=z1, label="Z", sigma=sigma)
            zIndexLower = i1
            i1, i2 = self.getUpperLowerFromPosition(p=z2, label="Z", sigma=sigma)
            zIndexUpper = i2
        try:
            for radial in range(rIndexLower + 1, rIndexUpper + 1):
                for theta in range(thIndexLower + 1, thIndexUpper + 1):
                    for z in range(zIndexLower, zIndexUpper + 1):
                        locations.append(
                            ThetaRZLocation(i1=theta, i2=radial, ThRZmesh=self)
                        )
                        locations[-1].setAxial(z)
                        locations[-1].makeLabel()

        except TypeError:
            # got a NoneType instead of an integer ... so fail by returning whatever we have for integer
            pass

        return locations


class Area(object):
    def __init__(self):

        self.lines = {}

    def sense(self, cartesianTuple):

        S = -1
        for line, s in self.lines.items():
            if s * line.sense(cartesianTuple) > 0:
                S = 1
                break

        return S


class Line(object):

    # a quadradic equation that represents a line in 2D cartesian space

    def __init__(self):
        self.origin = (0, 0)
        # a reference point on this line

        self.coefficients = {"c": 0, "x1": 0, "x2": 0, "y1": 0, "y2": 0}
        # polynomical coefficients that define this line

        self.cardinalDirection = "y"
        # a flag

    def sense(self, cartesian):
        """
        This method returns the 'sense' of a cartesian point (x, y) with
        respect to the line. The sense of a point is useful in establishing
        whethor or not a point is within a defined area or volume.

        Parameters
        ----------
        cartesian: tuple-like of float-like
            the first element is the x-coordinate and the second element is the y-coordinate

        Returns
        -------
        sense: float
            this can be negative (inside) positive (outside) or zero (actually on the line,
            the cartesian point satisfies the polynomial equation)

        """
        s = self.coefficients["c"]
        s += (
            self.coefficients["x1"] * cartesian[0]
            + self.coefficients["x2"] * cartesian[0] ** 2
        )
        s += (
            self.coefficients["y1"] * cartesian[1]
            + self.coefficients["y2"] * cartesian[1] ** 2
        )
        return s

    def getY(self, x=0):
        """
        This method returns the a list of y-values that satisfy the polynomial equation of
        this line by using the quadratic formula.

        Parameters
        ----------
        x: float-like
            x-coordinate

        Returns
        -------
        sense: [y1, (y2)]
            The solutions to the polynomial equation, this method returns [None]
            if there are no real intercepts and 'inf' if there are this is a
            constant value line (c=0)

        """
        if x is not None:
            a = self.coefficients["y2"]
            b = self.coefficients["y1"]
            c = (
                self.coefficients["c"]
                + self.coefficients["x2"] * x ** 2.0
                + self.coefficients["x1"] * x
            )

            return self.quadratic(a, b, c)
        else:
            return [None]

    def getX(self, y=0):
        """
        This method returns the a list of x-values that satisfy the polynomial equation of
        this line by using the quadratic formula.

        Parameters
        ----------
        y: float-like
            y-coordinate

        Returns
        -------
        sense: [x1, (x2)]
            The solutions to the polynomial equation, this method returns [None]
            if there are no real intercepts and 'inf' if there are this is a
            constant value line (c=0)

        """
        if y is not None:
            a = self.coefficients["x2"]
            b = self.coefficients["x1"]
            c = (
                self.coefficients["c"]
                + self.coefficients["y2"] * y ** 2.0
                + self.coefficients["y1"] * y
            )

            return self.quadratic(a, b, c)
        else:
            return [None]

    def quadratic(self, a, b, c):
        """
        This method solves the quadratic equation (a*x**2 + b*x + c = 0).

        Parameters
        ----------
        a, b, c : float-like
            coefficients in a quadratic equation: (a*x**2 + b*x + c = 0).

        Returns
        -------
        [x1, (x2)]: list of floats
            Solutions to the polynomial.

        """
        if a == 0 and b == 0:
            return ["inf"]
        elif a == 0 and b != 0:
            # form b*y + c = 0
            return [-c / b]
        elif (b ** 2 - 4 * a * c) > 0:
            # standard quadradic formula
            return [
                (-b + (b ** 2 - 4.0 * a * c) ** 0.5) / (2.0 * a),
                (-b - (b ** 2 - 4.0 * a * c) ** 0.5) / (2.0 * a),
            ]
        elif (b ** 2 - 4 * a * c) == 0:
            return [-b / (2.0 * a)]
        else:
            # only interested in real solutions, so toss out imaginary ones
            runLog.warning("warning no intercepts")
            return [None]

    def arcLength(self, x1=None, x2=None, n=10):

        # numerically integrate
        if self.cardinalDirection == "x":
            # transform coordinates from y-based to x-based
            dy = float(x2 - x1) / n
        else:
            dx = float(x2 - x1) / n

        s = 0

        for i in range(n):

            if self.cardinalDirection == "y":
                x = x1 + (i + 0.5) * dx
                s += (
                    dx ** 2
                    + (
                        dx
                        * (
                            -2.0 * self.coefficients["x2"] / self.coefficients["y1"] * x
                            - self.coefficients["x1"] / self.coefficients["y1"]
                        )
                    )
                    ** 2
                ) ** 0.5
            else:
                y = x1 + (i + 0.5) * dy
                s += (
                    dy ** 2
                    + (
                        dy
                        * (
                            -2.0 * self.coefficients["y2"] / self.coefficients["x1"] * y
                            - self.coefficients["y1"] / self.coefficients["x1"]
                        )
                    )
                    ** 2
                ) ** 0.5
        return s


def locationFactory(geomType):
    """Choose a location class."""
    options = {
        geometry.CARTESIAN: CartesianLocation,
        geometry.RZT: ThetaRZLocation,
        geometry.HEX: HexLocation,
        geometry.DODECAGON: HexLocation,  # yes, it's same as hex. That's what we want.
        geometry.RZ: ThetaRZLocation,
        # database names...
        geometry.REC_PRISM: CartesianLocation,
        geometry.HEX_PRISM: HexLocation,
        geometry.ANNULUS_SECTOR_PRISM: ThetaRZLocation,
    }

    locClass = options.get(geomType)
    if not locClass:
        raise ValueError('Unsupported geometry option: "{}"'.format(geomType))

    return locClass
