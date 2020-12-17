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
This module contains constants and enumerations that are useful for describing system
geometry.
"""
import enum
from typing import Union


class GeomType(enum.Enum):
    """
    Enumeration of geometry types.

    Historically, ARMI has used strings to specify and express things like geometry type
    and symmetry conditions. This makes interpretation of user input straightforward,
    but is less ergonomic, less efficient, and more error-prone within the code. For
    instance:
     - is "quarter reflective" the same as "reflective quarter"? Should it be?
     - code that needs to interpret these need to use string operations, which are
       non-trivial compared to enum comparisons.
     - rules about mutual exclusion (hex and Cartesian can't both be used in the same
       context) and composability (geometry type + domain + symmetry type) are harder to
       enforce.

    Instead, we hope to parse user input into a collection of enumerations and use those
    internally throughout the code. Future work should expand this to satisfy all needs
    of the geometry system and refactor to replace use of the string constants.
    """

    HEX = 1
    CARTESIAN = 2
    RZT = 3
    RZ = 4

    @classmethod
    def fromAny(cls, source: Union[str, "GeomType"]) -> "GeomType":
        """
        Safely convert from string representation, no-op if already an enum instance.

        This is useful as we transition to using enumerations more throughout the code.
        There will remain situations where a geomType may be provided in string or enum
        form, in which the consuming code would have to check the type before
        proceeding. This function serves two useful purposes:
         - Relieve client code from having to if/elif/else on ``isinstance()`` checks
         - Provide a location to instrument these conversions for when we actually try
           to deprecate the strings. E.g., produce a warning when this is called, or
           eventually forbidding the conversion entirely.
        """
        if isinstance(source, GeomType):
            return source
        elif isinstance(source, str):
            return cls.fromStr(source)
        else:
            raise TypeError("Expected str or GeomType; got {}".format(type(source)))

    @classmethod
    def fromStr(cls, geomStr):
        # case-insensitive
        canonical = geomStr.lower().strip()
        if canonical == HEX or canonical == HEX_CORNERS_UP:
            # corners-up is used to rotate grids, but shouldn't be needed after the grid
            # is appropriately oriented, so we collapse to HEX in the enumeration. If
            # there is a good reason to make corners-up HEX its own geom type, we will
            # need to figure out how to design around that.
            return cls.HEX
        elif canonical == CARTESIAN:
            return cls.CARTESIAN
        elif canonical == RZT:
            return cls.RZT
        elif canonical == RZ:
            return cls.RZ

        # use the original geomStr with preserved capitalization for better
        # error-finding.
        raise ValueError("Unrecognized geometry type: `{}`".format(geomStr))

    @property
    def label(self):
        """Human-presentable label"""

        if self == self.HEX:
            return "Hexagonal"
        elif self == self.CARTESIAN:
            return "Cartesian"
        elif self == self.RZT:
            return "R-Z-Theta"
        elif self == self.RZ:
            return "R-Z"

    def __str__(self):
        """Inverse of fromStr()"""

        if self == self.HEX:
            return HEX
        elif self == self.CARTESIAN:
            return CARTESIAN
        elif self == self.RZT:
            return RZT
        elif self == self.RZ:
            return RZ


SYSTEMS = "systems"
VERSION = "version"

HEX = "hex"
HEX_CORNERS_UP = "hex_corners_up"
RZT = "thetarz"
RZ = "rz"
CARTESIAN = "cartesian"

DODECAGON = "dodecagon"
REC_PRISM = "RecPrism"
HEX_PRISM = "HexPrism"
CONCENTRIC_CYLINDER = "ConcentricCylinder"
ANNULUS_SECTOR_PRISM = "AnnulusSectorPrism"

VALID_GEOMETRY_TYPE = {HEX, HEX_CORNERS_UP, RZT, RZ, CARTESIAN}

FULL_CORE = "full"
THIRD_CORE = "third "
QUARTER_CORE = "quarter "
EIGHTH_CORE = "eighth "
SIXTEENTH_CORE = "sixteenth "
REFLECTIVE = "reflective"
PERIODIC = "periodic"
THROUGH_CENTER_ASSEMBLY = (
    " through center assembly"  # through center assembly applies only to cartesian
)

VALID_SYMMETRY = {
    FULL_CORE,
    FULL_CORE + THROUGH_CENTER_ASSEMBLY,
    THIRD_CORE + PERIODIC,  # third core reflective is not geometrically consistent.
    QUARTER_CORE + PERIODIC,
    QUARTER_CORE + REFLECTIVE,
    QUARTER_CORE + PERIODIC + THROUGH_CENTER_ASSEMBLY,
    QUARTER_CORE + REFLECTIVE + THROUGH_CENTER_ASSEMBLY,
    EIGHTH_CORE + PERIODIC,
    EIGHTH_CORE + REFLECTIVE,
    EIGHTH_CORE + PERIODIC + THROUGH_CENTER_ASSEMBLY,
    EIGHTH_CORE + REFLECTIVE + THROUGH_CENTER_ASSEMBLY,
    SIXTEENTH_CORE + PERIODIC,
    SIXTEENTH_CORE + REFLECTIVE,
}


SYMMETRY_FACTORS = {}
for symmetry in VALID_SYMMETRY:
    if FULL_CORE in symmetry:
        SYMMETRY_FACTORS[symmetry] = 1.0
    elif THIRD_CORE in symmetry:
        SYMMETRY_FACTORS[symmetry] = 3.0
    elif QUARTER_CORE in symmetry:
        SYMMETRY_FACTORS[symmetry] = 4.0
    elif EIGHTH_CORE in symmetry:
        SYMMETRY_FACTORS[symmetry] = 8.0
    elif SIXTEENTH_CORE in symmetry:
        SYMMETRY_FACTORS[symmetry] = 16.0
    else:
        raise ValueError(
            "Could not calculate symmetry factor for symmetry {}. update logic.".format(
                symmetry
            )
        )


