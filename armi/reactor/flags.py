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
Handles *flags* that formally bind certain categories to reactor parts.

``Flags`` are used to formally categorize the various ``ArmiObject`` objects that make
up a reactor model. These categories allow parts of the ARMI system to treat different
Assemblies, Blocks, Components, etc. differently.

By default, the specific Flags that are bound to each object are derived by that
object's name when constructed; if the name contains any valid flag names, those Flags
will be assigned to the object. However, specific Flags may be specified within
blueprints, in which case the name is ignored and only the explicitly-requested Flags
are applied (see :ref:`bp-input-file` for more details).

Individual Flags tend to be various nouns and adjectives that describe common objects
that go into a reactor (e.g. "fuel", "shield", "control", "duct", "plenum", etc.). In
addition, there are some generic Flags (e.g., "A", "B", "C", etc.) that aid in
disambiguating between objects that need to be targeted separately but would otherwise
have the same Flags. Flags are stored as integer bitfields within the parameter system,
allowing them to be combined arbitrarily on any ARMI object. Since they are stored in
bitfields, each new flag definition requires widening this bitfield; therefore, the
number of defined Flags should be kept relatively small, and each flag should provide
maximum utility.

Within the code, Flags are usually combined into a "type specification (``TypeSpec``)",
which is either a single combination of Flags, or a list of Flag combinations. More
information about how ``TypeSpec`` is interpreted can be found in
:py:meth:`armi.reactor.composites.ArmiObject.hasFlags`.

Flags are intended to describe `what something is`, rather than `what something should
do`. Historically, Flags have been used to do both, which has led to confusion. The
binding of specific behavior to certain Flags should ideally be controlled through
settings with reasonable defaults, rather than being hard-coded. Currently, much of the
code still uses hard-coded ``TypeSpecs``, and certain Flags are clearly saying `what
something should do` (e.g., ``Flags.DEPLETABLE``).

.. note::
    Flags have a rather storied history. Way back when, code that needed to operate on
    specific objects would do substring searches against object names to decide if they
    were relevant. This was very prone to error, and led to all sorts of surprising
    behavior based on the names used in input files. To improve the situation, Flags
    were developed to better formalize which strings mattered, and to define canonical
    names for things. Still almost all flag checks were hard-coded, and
    aside from up-front error checks, many of the original issues persisted. For
    instance, developing a comprehensive manual of which Flags lead to which behavior
    was very difficult.

    Migrating the `meaning` of Flags into settings will allow us to better document how
    those Flags/settings affect ARMI's behavior.

    As mentioned above, plenty of code still hard-codes Flag ``TypeSpecs``, and certain
    Flags do not follow the `what something is` convention. Future work should improve
    upon this as possible.


Things that Flags are used for include:

* **Fuel management**: Different kinds of assemblies (LTAs, fuel, reflectors) have
  different shuffling operations and must be distinguished. Certain blocks in an
  assembly are stationary, and shouldn't be moved along with the rest of the assembly
  when shuffling is performed. Filtering for stationary blocks can also be done using
  Flags (e.g., ``Flags.GRID_PLATE``).

* **Fuel performance**: Knowing what's fuel (``Flags.FUEL``) and what isn't (e.g.,
  ``Flags.PLENUM``) is important to figure out what things to grow and where to move
  fission gas to.

* **Fluid fuel** reactors need to find all the fuel that ever circulates through the
  reactor so it can be depleted with the average flux.

* **Core Mechanical** analyses often need to know if an object is solid, fluid, or void
  (material subclassing can handle this).

* **T/H** needs to find the pin bundle in different kinds of assemblies (*radial shield*
  block in *radial shield* assemblies, *fuel* in *fuel*, etc.). Also needs to generate
  3-layer pin models with pin (fuel/control/shield/slug), then gap (liners/gap/bond),
  then clad.


Examples
--------
>>> block.hasFlags(Flags.PRIMARY | Flags.TEST | Flags.FUEL)
True

>>> block.hasFlags([Flags.PRIMARY, Flags.TEST, Flags.FUEL])
True

>>> block.getComponent(Flags.INTERDUCTCOOLANT)
<component InterDuctCoolant>

>>> block.getComponents(Flags.FUEL)
[<component fuel1>, <component fuel2>, ...]

"""
import re
from typing import Optional, Sequence, Union

from armi.utils.flags import Flag, FlagType, auto

# Type alias used for passing type specifications to many of the composite methods. See
# Composite::hasFlags() to understand the semantics for how TypeSpecs are interpreted.
# Anything that interprets a TypeSpec should apply the same semantics.
TypeSpec = Optional[Union[FlagType, Sequence[FlagType]]]


def __fromStringGeneral(cls, typeSpec, updateMethod):
    """Helper method to minimize code repeat in other fromString methods."""
    result = cls(0)
    typeSpec = typeSpec.upper()
    for conversion in _CONVERSIONS:
        m = conversion.search(typeSpec)
        if m:
            typeSpec = re.sub(conversion, "", typeSpec)
            result |= _CONVERSIONS[conversion]

    for name in typeSpec.split():
        try:
            # first, check for an exact match, to cover flags with digits
            result |= cls[name]
        except KeyError:
            # ignore numbers so we don't have to define flags up to the number of pins/assem
            typeSpecWithoutNumbers = "".join([c for c in name if not c.isdigit()])
            if not typeSpecWithoutNumbers:
                continue
            result |= updateMethod(typeSpecWithoutNumbers)

    return result


def _fromStringIgnoreErrors(cls, typeSpec):
    """
    Convert string into a set of flags.

    Each word can be its own flag.

    Notes
    -----
    This ignores words in the typeSpec that are not valid flags.

    Complications arise when:

    a. multiple-word flags are used such as *grid plate* or *inlet nozzle* so we use lookups.
    b. Some flags have digits in them. We just strip those off.
    """

    def updateMethodIgnoreErrors(typeSpec):
        try:
            return cls[typeSpec]
        except KeyError:
            return cls(0)

    return __fromStringGeneral(cls, typeSpec, updateMethodIgnoreErrors)


def _fromString(cls, typeSpec):
    """Make flag from string and fail if any unknown words are encountered."""

    def updateMethod(typeSpec):
        try:
            return cls[typeSpec]
        except KeyError:
            raise InvalidFlagsError(
                f"The requested type specification `{typeSpec}` is invalid. "
                "See armi.reactor.flags documentation."
            )

    return __fromStringGeneral(cls, typeSpec, updateMethod)


def _toString(cls, typeSpec):
    """
    Make flag from string and fail if any unknown words are encountered.

    Notes
    -----
    This converts a flag from ``Flags.A|B`` to ``'A B'``
    """
    strings = str(typeSpec).split("{}.".format(cls.__name__))[1]
    return " ".join(sorted(strings.split("|")))


class Flags(Flag):
    """Defines the valid flags used in the framework."""

    # basic classifiers
    PRIMARY = auto()
    SECONDARY = auto()
    TERTIARY = auto()
    ANNULAR = auto()  # ideally this info would be inferred from shape
    A = auto()
    B = auto()
    C = auto()
    D = auto()
    E = auto()
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()

    # general kinds of assemblies or blocks
    MATERIAL = auto()
    FUEL = auto()
    TEST = auto()
    CONTROL = auto()
    ULTIMATE = auto()
    SHUTDOWN = auto()
    SHIELD = auto()
    SHIELD_BLOCK = auto()
    SLUG = auto()
    REFLECTOR = auto()

    # different kinds of fuel
    DRIVER = auto()
    IGNITER = auto()
    FEED = auto()
    STARTER = auto()
    BLANKET = auto()
    BOOSTER = auto()
    TARGET = auto()
    MOX = auto()

    # radial positions
    INNER = auto()
    MIDDLE = auto()
    OUTER = auto()
    RADIAL = auto()

    # axial positions
    AXIAL = auto()
    UPPER = auto()
    LOWER = auto()

    # assembly parts (including kinds of pins)
    DUCT = auto()
    GRID_PLATE = auto()
    HANDLING_SOCKET = auto()
    INLET_NOZZLE = auto()
    PLENUM = auto()
    BOND = auto()  # not empty
    LINER = auto()  # Use PRIMARY or SECONDARY to get multiple liners
    CLAD = auto()
    PIN = auto()  # the "meat" inside the clad
    GAP = auto()  # generally empty
    WIRE = auto()
    COOLANT = auto()
    INTERCOOLANT = auto()
    LOAD_PAD = auto()
    ACLP = auto()  # above core load pad
    SKID = auto()
    VOID = auto()
    INTERDUCTCOOLANT = auto()
    DSPACERINSIDE = auto()
    GUIDE_TUBE = auto()
    FISSION_CHAMBER = auto()
    MODERATOR = auto()

    # more parts
    CORE_BARREL = auto()
    DUMMY = auto()
    BATCHMASSADDITION = auto()

    POISON = auto()

    STRUCTURE = auto()
    DEPLETABLE = auto()

    # Allows movement of lower plenum with control rod
    MOVEABLE = auto()

    @classmethod
    def fromStringIgnoreErrors(cls, typeSpec):
        return _fromStringIgnoreErrors(cls, typeSpec)

    @classmethod
    def fromString(cls, typeSpec):
        """
        Retrieve flag from a string.

        .. impl:: Retrieve flag from a string.
            :id: I_ARMI_FLAG_TO_STR0
            :implements: R_ARMI_FLAG_TO_STR

            For a string passed as ``typeSpec``, first converts the whole string to uppercase. Then
            tries to parse the string for any special phrases, as defined in the module dictionary
            ``_CONVERSIONS``, and converts those phrases to flags directly.

            Then it splits the remaining string into words based on spaces. Looping over each of the
            words, if any word exactly matches a flag name. Otherwise, any numbers are stripped out
            and the remaining string is matched up to any class attribute names. If any matches are
            found these are returned as flags.
        """
        return _fromString(cls, typeSpec)

    @classmethod
    def toString(cls, typeSpec):
        """
        Convert a flag to a string.

        .. impl:: Convert a flag to string.
            :id: I_ARMI_FLAG_TO_STR1
            :implements: R_ARMI_FLAG_TO_STR

            This converts the representation of a bunch of flags from ``typeSpec``, which might look
            like ``Flags.A|B``, into a string with spaces in between the flag names, which would
            look like  ``'A B'``. This is done via nesting string splitting and replacement actions.
        """
        return _toString(cls, typeSpec)


class InvalidFlagsError(KeyError):
    """Raised when code attempts to look for an undefined flag."""

    pass


# string conversions for multiple-word flags
# Beware of how these may interact with the standard flag names! E.g., make sure NOZZLE
# doesn't eat the NOZZLE in INLET_NOZZLE. Make sure that words that would otherwise be a
# substring of a valid flag are wrapped in word-boundary `\b`s
_CONVERSIONS = {
    re.compile(r"\bGRID\s+PLATE\b"): Flags.GRID_PLATE,
    re.compile(r"\bGRID\b"): Flags.GRID_PLATE,
    re.compile(r"\bINLET\s+NOZZLE\b"): Flags.INLET_NOZZLE,
    re.compile(r"\bNOZZLE\b"): Flags.INLET_NOZZLE,
    re.compile(r"\bLOAD\s+PAD\b"): Flags.LOAD_PAD,
    re.compile(r"\bHANDLING\s+SOCKET\b"): Flags.HANDLING_SOCKET,
    re.compile(r"\bGUIDE\s+TUBE\b"): Flags.GUIDE_TUBE,
    re.compile(r"\bFISSION\s+CHAMBER\b"): Flags.FISSION_CHAMBER,
    re.compile(r"\bSOCKET\b"): Flags.HANDLING_SOCKET,
    re.compile(r"\bSHIELD\s+BLOCK\b"): Flags.SHIELD_BLOCK,
    re.compile(r"\bSHIELDBLOCK\b"): Flags.SHIELD_BLOCK,
    re.compile(r"\bCORE\s+BARREL\b"): Flags.CORE_BARREL,
    re.compile(r"\bINNERDUCT\b"): Flags.INNER | Flags.DUCT,
    re.compile(r"\bGAP1\b"): Flags.GAP | Flags.A,
    re.compile(r"\bGAP2\b"): Flags.GAP | Flags.B,
    re.compile(r"\bGAP3\b"): Flags.GAP | Flags.C,
    re.compile(r"\bGAP4\b"): Flags.GAP | Flags.D,
    re.compile(r"\bGAP5\b"): Flags.GAP | Flags.E,
    re.compile(r"\bLINER1\b"): Flags.LINER | Flags.A,
    re.compile(r"\bLINER2\b"): Flags.LINER | Flags.B,
}
