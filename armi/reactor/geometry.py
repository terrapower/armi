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
from typing import Union, List, Optional

from armi.utils import parsing


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
    HEX_CORNERS_UP = 5

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
    def fromStr(cls, geomStr: str) -> "GeomType":
        # case-insensitive
        x = geomStr.lower().strip()
        for canonical in (x, parsing.findString(geomTypes, x)):
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


class SymmetryType:
    """
    A thin wrapper for ShapeType and BoundaryType enumerations.

    (see GeomType class for explanation of why we want enumerations for ShapeType and
    BoundaryType).

    The goal of this class is to provide simple functions for storing these options
    in enumerations and using them to check symmetry conditions, while also providing
    a standard string representation of the options that facilitates interfacing with
    yaml and/or the database nicely.
    """

    def __init__(
        self,
        shapeType: Union[str, "ShapeType"] = ShapeType.THIRD_CORE,
        boundaryType: Union[str, "BoundaryType"] = BoundaryType.PERIODIC,
        throughCenterAssembly: Optional[bool] = False,
    ) -> "SymmetryType":
        self.shape = ShapeType.fromAny(shapeType)
        self.boundary = BoundaryType.fromAny(boundaryType)
        self.isThroughCenterAssembly = throughCenterAssembly
        return symmetry._returnIfValid()

    @classmethod
    def fromStr(cls, symmetryString: str) -> "SymmetryType":
        symmetry = cls()
        symmetry.shape = ShapeType.fromStr(symmetryString)
        symmetry.boundary = BoundaryType.fromStr(symmetryString)
        symmetry._checkIfThroughCenter(symmetryString)
        return symmetry._returnIfValid()

    @classmethod
    def fromAny(cls, symmetry: Union[str, "SymmetryType"]) -> "SymmetryType":
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
        if isinstance(symmetry, SymmetryType):
            return symmetry._returnIfValid()
        elif isinstance(symmetry, str):
            return cls.fromStr(symmetry)
        else:
            raise TypeError("Expected str or SymmetryType; got {}".format(type(source)))

    def __str__(self):
        """Combined string of shape and boundary symmetry type"""
        strList = [str(self.shape)]
        if self.boundary.hasSymmetry():
            strList.append(str(self.boundary))
        if self.isThroughCenterAssembly:
            strList.append(THROUGH_CENTER_ASSEMBLY)
        return " ".join(strList)

    def _checkIfThroughCenter(self, symmetryString: str):
        self.isThroughCenterAssembly = THROUGH_CENTER_ASSEMBLY in symmetryString

    def _returnIfValid(self):
        if self.checkValidSymmetry():
            return self
        else:
            errorMsg = "{} is not a valid symmetry option. Valid symmetry options are:"
            errorMsg += ", ".join([f"{sym}" for sym in VALID_SYMMETRY])
            raise ValueError(errorMsg)

    def symmetryFactor(self):
        return self.shape.symmetryFactor()

    def checkValidSymmetry(self):
        return str(self) in VALID_SYMMETRY


class ShapeType(enum.Enum):
    """
    Enumeration of shape types.
    """

    NULL = 0
    FULL_CORE = 1
    THIRD_CORE = 3
    QUARTER_CORE = 4
    EIGHTH_CORE = 8
    SIXTEENTH_CORE = 16

    @classmethod
    def fromAny(cls, source: Union[str, "ShapeType"]) -> "ShapeType":
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
        if isinstance(source, ShapeType):
            return source
        elif isinstance(source, str):
            return cls.fromStr(source)
        else:
            raise TypeError("Expected str or ShapeType; got {}".format(type(source)))

    @classmethod
    def fromStr(cls, shapeStr: str) -> "ShapeType":
        # case-insensitive
        x = shapeStr.lower().strip()
        for canonical in (x, parsing.findString(shapeTypes, x)):
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
        return cls.NULL
        # use the original shapeStr with preserved capitalization for better
        # error-finding.
        # raise ValueError("Unrecognized shape type: `{}`".format(shapeStr))

    @property
    def label(self):
        """Human-presentable label"""
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
        elif self == self.NULL:
            return ""

    def __str__(self):
        """Inverse of fromStr()"""
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
        elif self == self.NULL:
            return ""

    def symmetryFactor(self):
        if self == self.FULL_CORE or self == self.NULL:
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
                "Could not calculate symmetry factor for shape {}. update logic.".format(
                    self.label
                )
            )


class BoundaryType(enum.Enum):
    """
    Enumeration of boundary types.
    """

    NO_SYMMETRY = 0
    PERIODIC = 1
    REFLECTIVE = 2

    @classmethod
    def fromAny(cls, source: Union[str, "BoundaryType"]) -> "BoundaryType":
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
        if isinstance(source, BoundaryType):
            return source
        elif isinstance(source, str):
            return cls.fromStr(source)
        else:
            raise TypeError("Expected str or BoundaryType; got {}".format(type(source)))

    @classmethod
    def fromStr(cls, symmetryStr: str) -> "BoundaryType":
        # case-insensitive
        x = symmetryStr.lower().strip()
        for canonical in (x, parsing.findString(boundaryTypes, x)):
            if canonical == NO_SYMMETRY:
                return cls.NO_SYMMETRY
            elif canonical == PERIODIC:
                return cls.PERIODIC
            elif canonical == REFLECTIVE:
                return cls.REFLECTIVE
        return cls.NO_SYMMETRY

    @property
    def label(self):
        """Human-presentable label"""

        if self == self.NO_SYMMETRY:
            return "No Symmetry"
        elif self == self.REFLECTIVE:
            return "Reflective"
        elif self == self.PERIODIC:
            return "Periodic"

    def __str__(self):
        """Inverse of fromStr()"""
        if self == self.NO_SYMMETRY:
            return NO_SYMMETRY  # should we return an empty string here instead?
        elif self == self.PERIODIC:
            return PERIODIC
        elif self == self.REFLECTIVE:
            return REFLECTIVE

    def hasSymmetry(self):
        return not self == self.NO_SYMMETRY


def checkValidGeomSymmetryCombo(
    geomType: Union[str, GeomType], symmetryType: Union[str, SymmetryType]
) -> bool:
    """
    Check if the given combination of GeomType and SymmetryType is valid.
    Return a boolean indicating the outcome of the check.
    """

    geomType = GeomType.fromStr(str(geomType))
    symmetryType = SymmetryType.fromStr(str(symmetryType))

    if not symmetryType.checkValidSymmetry():
        errorMsg = "{} is not a valid symmetry option. Valid symmetry options are:"
        errorMsg += ", ".join([f"{sym}" for sym in VALID_SYMMETRY])
        raise ValueError(errorMsg)

    validCombo = False
    if geomType == GeomType.HEX:
        validCombo = symmetryType.shape in [ShapeType.FULL_CORE, ShapeType.THIRD_CORE]
    elif geomType == GeomType.CARTESIAN:
        validCombo = symmetryType.shape in [
            ShapeType.FULL_CORE,
            ShapeType.QUARTER_CORE,
            ShapeType.EIGHTH_CORE,
        ]
    elif geomType == GeomType.RZT:
        validCombo = True  # any domain size could be valid for RZT
    elif geomType == GeomType.RZ:
        validCombo = symmetryType.shape == ShapeType.FULL_CORE

    if validCombo:
        return True
    else:
        raise ValueError(
            "GeomType: {} and SymmetryType: {} is not a valid combination!".format(
                str(geomType, str(symmetryType))
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

FULL_CORE = "full"
THIRD_CORE = "third"
QUARTER_CORE = "quarter"
EIGHTH_CORE = "eighth"
SIXTEENTH_CORE = "sixteenth"
REFLECTIVE = "reflective"
PERIODIC = "periodic"
NO_SYMMETRY = "no symmetry"
THROUGH_CENTER_ASSEMBLY = (
    "through center assembly"  # through center assembly applies only to cartesian
)

VALID_SYMMETRY = {
    FULL_CORE,
    " ".join([FULL_CORE, THROUGH_CENTER_ASSEMBLY]),
    " ".join(
        [THIRD_CORE, PERIODIC]
    ),  # third core reflective is not geometrically consistent.
    " ".join([QUARTER_CORE, PERIODIC]),
    " ".join([QUARTER_CORE, REFLECTIVE]),
    " ".join([QUARTER_CORE, PERIODIC, THROUGH_CENTER_ASSEMBLY]),
    " ".join([QUARTER_CORE, REFLECTIVE, THROUGH_CENTER_ASSEMBLY]),
    " ".join([EIGHTH_CORE, PERIODIC]),
    " ".join([EIGHTH_CORE, REFLECTIVE]),
    " ".join([EIGHTH_CORE, PERIODIC, THROUGH_CENTER_ASSEMBLY]),
    " ".join([EIGHTH_CORE, REFLECTIVE, THROUGH_CENTER_ASSEMBLY]),
    " ".join([SIXTEENTH_CORE, PERIODIC]),
    " ".join([SIXTEENTH_CORE, REFLECTIVE]),
}


geomTypes = {HEX, CARTESIAN, RZT, RZ}
shapeTypes = {FULL_CORE, THIRD_CORE, QUARTER_CORE, EIGHTH_CORE, SIXTEENTH_CORE}
boundaryTypes = {NO_SYMMETRY, PERIODIC, REFLECTIVE}
