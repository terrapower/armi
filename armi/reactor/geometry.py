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
from typing import Optional, Union


class GeomType(enum.Enum):
    """
    Enumeration of geometry types.

    Historically, ARMI has used strings to specify and express things like geometry type
    and symmetry conditions. This makes interpretation of user input straightforward,
    but is less ergonomic, less efficient, and more error-prone within the code. For
    instance:

    * is "quarter reflective" the same as "reflective quarter"? Should it be?
    * code that needs to interpret these need to use string operations, which are
      non-trivial compared to enum comparisons.
    * rules about mutual exclusion (hex and Cartesian can't both be used in the same
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

        * Relieve client code from having to if/elif/else on ``isinstance()`` checks
        * Provide a location to instrument these conversions for when we actually try
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
    def fromStr(cls, geomStr: str) -> "GeomType":
        # case-insensitive
        canonical = geomStr.lower().strip()
        if canonical in (HEX, HEX_CORNERS_UP):
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
        errorMsg = "Unrecognized geometry type {}. Valid geometry options are: ".format(
            geomStr
        )
        errorMsg += ", ".join([f"{geom}" for geom in geomTypes])
        raise ValueError(errorMsg)

    @property
    def label(self):
        """Human-presentable label."""
        if self == self.HEX:
            return "Hexagonal"
        elif self == self.CARTESIAN:
            return "Cartesian"
        elif self == self.RZT:
            return "R-Z-Theta"
        else:
            return "R-Z"

    def __str__(self):
        """Inverse of fromStr()."""
        if self == self.HEX:
            return HEX
        elif self == self.CARTESIAN:
            return CARTESIAN
        elif self == self.RZT:
            return RZT
        else:
            return RZ


class DomainType(enum.Enum):
    """Enumeration of shape types."""

    NULL = 0
    FULL_CORE = 1
    THIRD_CORE = 3
    QUARTER_CORE = 4
    EIGHTH_CORE = 8
    SIXTEENTH_CORE = 16

    @classmethod
    def fromAny(cls, source: Union[str, "DomainType"]) -> "DomainType":
        if isinstance(source, DomainType):
            return source
        elif isinstance(source, str):
            return cls.fromStr(source)
        else:
            raise TypeError("Expected str or DomainType; got {}".format(type(source)))

    @classmethod
    def fromStr(cls, shapeStr: str) -> "DomainType":
        # case-insensitive
        canonical = shapeStr.lower().strip()
        if canonical == FULL_CORE:
            return cls.FULL_CORE
        elif canonical == THIRD_CORE:
            return cls.THIRD_CORE
        elif canonical == QUARTER_CORE:
            return cls.QUARTER_CORE
        elif canonical == EIGHTH_CORE:
            return cls.EIGHTH_CORE
        elif canonical == SIXTEENTH_CORE:
            return cls.SIXTEENTH_CORE
        elif canonical == "":
            return cls.NULL

        errorMsg = "{} is not a valid domain option. Valid domain options are:".format(
            str(canonical)
        )
        errorMsg += ", ".join([f"{sym}" for sym in domainTypes])
        raise ValueError(errorMsg)

    @property
    def label(self):
        """Human-presentable label."""
        if self == self.FULL_CORE:
            return "Full"
        elif self == self.THIRD_CORE:
            return "Third"
        elif self == self.QUARTER_CORE:
            return "Quarter"
        elif self == self.EIGHTH_CORE:
            return "Eighth"
        elif self == self.SIXTEENTH_CORE:
            return "Sixteenth"
        else:
            # is NULL
            return ""

    def __str__(self):
        """Inverse of fromStr()."""
        if self == self.FULL_CORE:
            return FULL_CORE
        elif self == self.THIRD_CORE:
            return THIRD_CORE
        elif self == self.QUARTER_CORE:
            return QUARTER_CORE
        elif self == self.EIGHTH_CORE:
            return EIGHTH_CORE
        elif self == self.SIXTEENTH_CORE:
            return SIXTEENTH_CORE
        else:
            # is NULL
            return ""

    def symmetryFactor(self) -> float:
        if self in (self.FULL_CORE, self == self.NULL):
            return 1.0
        elif self == self.THIRD_CORE:
            return 3.0
        elif self == self.QUARTER_CORE:
            return 4.0
        elif self == self.EIGHTH_CORE:
            return 8.0
        elif self == self.SIXTEENTH_CORE:
            return 16.0
        else:
            raise ValueError(
                "Could not calculate symmetry factor for domain size {}. update logic.".format(
                    self.label
                )
            )


class BoundaryType(enum.Enum):
    """Enumeration of boundary types."""

    NO_SYMMETRY = 0
    PERIODIC = 1
    REFLECTIVE = 2

    @classmethod
    def fromAny(cls, source: Union[str, "BoundaryType"]) -> "BoundaryType":
        if isinstance(source, BoundaryType):
            return source
        elif isinstance(source, str):
            return cls.fromStr(source)
        else:
            raise TypeError("Expected str or BoundaryType; got {}".format(type(source)))

    @classmethod
    def fromStr(cls, symmetryStr: str) -> "BoundaryType":
        # case-insensitive
        canonical = symmetryStr.lower().strip()
        if canonical == NO_SYMMETRY:
            return cls.NO_SYMMETRY
        elif canonical == PERIODIC:
            return cls.PERIODIC
        elif canonical == REFLECTIVE:
            return cls.REFLECTIVE

        errorMsg = (
            "{} is not a valid boundary option. Valid boundary options are:".format(
                str(canonical)
            )
        )
        errorMsg += ", ".join([f"{sym}" for sym in boundaryTypes])
        raise ValueError(errorMsg)

    @property
    def label(self):
        """Human-presentable label."""
        if self == self.NO_SYMMETRY:
            return "No Symmetry"
        elif self == self.REFLECTIVE:
            return "Reflective"
        else:
            return "Periodic"

    def __str__(self):
        """Inverse of fromStr()."""
        if self == self.NO_SYMMETRY:
            return ""
        elif self == self.PERIODIC:
            return PERIODIC
        else:
            return REFLECTIVE

    def hasSymmetry(self):
        return self != self.NO_SYMMETRY


class SymmetryType:
    """
    A wrapper for DomainType and BoundaryType enumerations.

    The goal of this class is to provide simple functions for storing these options
    in enumerations and using them to check symmetry conditions, while also providing
    a standard string representation of the options that facilitates interfacing with
    yaml and/or the database nicely.
    """

    VALID_SYMMETRY = {
        (DomainType.FULL_CORE, BoundaryType.NO_SYMMETRY, False),
        (DomainType.FULL_CORE, BoundaryType.NO_SYMMETRY, True),
        (DomainType.THIRD_CORE, BoundaryType.PERIODIC, False),
        (DomainType.QUARTER_CORE, BoundaryType.PERIODIC, False),
        (DomainType.QUARTER_CORE, BoundaryType.REFLECTIVE, False),
        (DomainType.QUARTER_CORE, BoundaryType.PERIODIC, True),
        (DomainType.QUARTER_CORE, BoundaryType.REFLECTIVE, True),
        (DomainType.EIGHTH_CORE, BoundaryType.PERIODIC, False),
        (DomainType.EIGHTH_CORE, BoundaryType.REFLECTIVE, False),
        (DomainType.EIGHTH_CORE, BoundaryType.PERIODIC, True),
        (DomainType.EIGHTH_CORE, BoundaryType.REFLECTIVE, True),
        (DomainType.SIXTEENTH_CORE, BoundaryType.PERIODIC, False),
        (DomainType.SIXTEENTH_CORE, BoundaryType.REFLECTIVE, False),
    }

    @staticmethod
    def _checkIfThroughCenter(centerString: str) -> bool:
        return THROUGH_CENTER_ASSEMBLY in centerString

    def __init__(
        self,
        domainType: "DomainType" = DomainType.THIRD_CORE,
        boundaryType: "BoundaryType" = BoundaryType.PERIODIC,
        throughCenterAssembly: Optional[bool] = False,
    ):
        self.domain = domainType
        self.boundary = boundaryType
        self.isThroughCenterAssembly = throughCenterAssembly

        if not self.checkValidSymmetry():
            errorMsg = "{} is not a valid symmetry option. Valid symmetry options are: ".format(
                str(self)
            )
            errorMsg += ", ".join(
                [f"{sym}" for sym in self.createValidSymmetryStrings()]
            )
            raise ValueError(errorMsg)

    @classmethod
    def createValidSymmetryStrings(cls):
        """Create a list of valid symmetry strings based on the set of tuples in VALID_SYMMETRY."""
        return [
            cls(domain, boundary, isThroughCenter)
            for domain, boundary, isThroughCenter in cls.VALID_SYMMETRY
        ]

    @classmethod
    def fromStr(cls, symmetryString: str) -> "SymmetryType":
        """Construct a SymmetryType object from a valid string."""
        canonical = symmetryString.lower().strip()
        # ignore "assembly" since it is unnecessary and overly-verbose and too specific
        noAssembly = canonical.replace("assembly", "").strip()
        isThroughCenter = cls._checkIfThroughCenter(canonical)
        coreString = noAssembly.replace(THROUGH_CENTER_ASSEMBLY, "").strip()
        trimmedString = coreString.replace("core", "").strip()
        pieces = trimmedString.split()
        domain = DomainType.fromStr(pieces[0])
        if len(pieces) == 1:
            # set the BoundaryType to a default for the DomainType
            if domain == DomainType.FULL_CORE:
                boundary = BoundaryType.NO_SYMMETRY
            elif domain == DomainType.THIRD_CORE:
                boundary = BoundaryType.PERIODIC
            else:
                boundary = BoundaryType.REFLECTIVE
        elif len(pieces) == 2:
            boundary = BoundaryType.fromStr(pieces[1])
        else:
            errorMsg = "{} [{}] is not a valid symmetry option. Valid symmetry options are:".format(
                symmetryString, trimmedString
            )
            errorMsg += ", ".join(
                [f"{sym}" for sym in cls.createValidSymmetryStrings()]
            )
            raise ValueError(errorMsg)
        return cls(domain, boundary, isThroughCenter)

    @classmethod
    def fromAny(cls, source: Union[str, "SymmetryType"]) -> "SymmetryType":
        if isinstance(source, SymmetryType):
            return source
        elif isinstance(source, str):
            return cls.fromStr(source)
        else:
            raise TypeError("Expected str or SymmetryType; got {}".format(type(source)))

    def __str__(self):
        """Combined string of domain and boundary symmetry type."""
        strList = [str(self.domain)]
        if self.boundary.hasSymmetry():
            strList.append(str(self.boundary))
        if self.isThroughCenterAssembly:
            strList.append(THROUGH_CENTER_ASSEMBLY)
        return " ".join(strList)

    def __eq__(self, other):
        """Compare two SymmetryType instances. False if other is not a SymmetryType."""
        if isinstance(other, SymmetryType):
            return (
                self.domain == other.domain
                and self.boundary == other.boundary
                and self.isThroughCenterAssembly == other.isThroughCenterAssembly
            )
        elif isinstance(other, str):
            otherSym = SymmetryType.fromStr(other)
            return (
                self.domain == otherSym.domain
                and self.boundary == otherSym.boundary
                and self.isThroughCenterAssembly == otherSym.isThroughCenterAssembly
            )
        else:
            raise NotImplementedError

    def __hash__(self):
        """Hash a SymmetryType object based on a tuple of its options."""
        return hash((self.domain, self.boundary, self.isThroughCenterAssembly))

    def checkValidSymmetry(self) -> bool:
        """Check if the tuple representation of the SymmetryType can be found in VALID_SYMMETRY."""
        return (
            self.domain,
            self.boundary,
            self.isThroughCenterAssembly,
        ) in self.VALID_SYMMETRY

    def symmetryFactor(self) -> float:
        return self.domain.symmetryFactor()


def checkValidGeomSymmetryCombo(
    geomType: Union[str, "GeomType"],
    symmetryInput: Union[str, "SymmetryType"],
) -> bool:
    """
    Check if the given combination of GeomType and SymmetryType is valid.
    Return a boolean indicating the outcome of the check.
    """
    symmetry = SymmetryType.fromAny(symmetryInput)
    if (symmetry.domain, symmetry.boundary) in VALID_GEOM_SYMMETRY[
        GeomType.fromAny(geomType)
    ]:
        return True
    else:
        raise ValueError(
            "GeomType: {} and SymmetryType: {} is not a valid combination!".format(
                str(geomType), str(symmetry)
            )
        )


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

VALID_GEOM_SYMMETRY = {
    GeomType.HEX: [
        (DomainType.FULL_CORE, BoundaryType.NO_SYMMETRY),
        (DomainType.THIRD_CORE, BoundaryType.PERIODIC),
    ],
    GeomType.CARTESIAN: [
        (DomainType.FULL_CORE, BoundaryType.NO_SYMMETRY),
        (DomainType.QUARTER_CORE, BoundaryType.PERIODIC),
        (DomainType.EIGHTH_CORE, BoundaryType.PERIODIC),
        (DomainType.QUARTER_CORE, BoundaryType.REFLECTIVE),
        (DomainType.EIGHTH_CORE, BoundaryType.REFLECTIVE),
    ],
    GeomType.RZT: [
        (DomainType.FULL_CORE, BoundaryType.NO_SYMMETRY),
        (DomainType.THIRD_CORE, BoundaryType.PERIODIC),
        (DomainType.QUARTER_CORE, BoundaryType.PERIODIC),
        (DomainType.EIGHTH_CORE, BoundaryType.PERIODIC),
        (DomainType.SIXTEENTH_CORE, BoundaryType.PERIODIC),
        (DomainType.QUARTER_CORE, BoundaryType.REFLECTIVE),
        (DomainType.EIGHTH_CORE, BoundaryType.REFLECTIVE),
        (DomainType.SIXTEENTH_CORE, BoundaryType.REFLECTIVE),
    ],
    GeomType.RZ: [(DomainType.FULL_CORE, BoundaryType.NO_SYMMETRY)],
}

FULL_CORE = "full"
THIRD_CORE = "third"
QUARTER_CORE = "quarter"
EIGHTH_CORE = "eighth"
SIXTEENTH_CORE = "sixteenth"
REFLECTIVE = "reflective"
PERIODIC = "periodic"
NO_SYMMETRY = "no symmetry"
# through center assembly applies only to cartesian
THROUGH_CENTER_ASSEMBLY = "through center"

geomTypes = {HEX, CARTESIAN, RZT, RZ}
domainTypes = {FULL_CORE, THIRD_CORE, QUARTER_CORE, EIGHTH_CORE, SIXTEENTH_CORE}
boundaryTypes = {NO_SYMMETRY, PERIODIC, REFLECTIVE}
