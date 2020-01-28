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
Handles *flags* that trigger behaviors related to reactor parts.

*Flags* are used to trigger certain treatments by the various modules. For instance, if
a module needs to separate **reflector** assemblies from **fuel** assemblies, it can use
flags.

Flags are derived from the user-input name. If a valid flag name is included in a
assembly/block/component name, then that flag will be applied. Words in names that are
not valid flags are ignored from a flags perspective.  Each flag in the name must be
space-delimited to be parsed properly.  If a name includes numbers, they are generally
ignored to avoid defining hundreds of flags for assemblies with many pins in them (e.g.
in pin-level depletion cases). Use ``FUEL A`` or ``FUEL B`` to distinguish if necessary.

Code modules that check the names of objects must use valid flags only.

Things that flags are used for include:

* **Fuel management**: Different kinds of assemblies (LTAs, fuel, reflectors) have
  different shuffling operations and must be distinguished. Often names are good ways to
  pick assemblies but details may need a flag (e.g. ``STATIONARY`` for *grid plate*
  blocks, though keeping grid plates out of the Assemblies may be a better option in
  this case.)

* **Fuel performance**: Knowing what's fuel and what's plenum is important to figure out
  what things to grow and where to move fission gas to.

* **Safety**: Test assemblies like LTAs go in their own special channels and must be
  identified.  Reflectors, control, shields go into bypass channels.  Handling sockets,
  shield blocks, etc.  go in their own axial nodes.

* **Fluid fuel** reactors need to find all the fuel that ever circulates through the
 reactor so it can be depleted with the average flux.

* **Mechanical** often needs to know if an object is solid, fluid, or void (material
 subclassing can handle this).

* **T/H** needs to find the pin bundle in different kinds of assemblies (*radial shield*
  block in *radial shield* assemblies, *fuel* in *fuel*, etc.). Also needs to generate
  3-layer pin models with pin (fuel/control/shield/slug), then gap (liners/gap/bond),
  then clad.

Also:

  * Object names should explicitly tied to their definition in the input


Notes
-----

The flags used to be based only on the user-input name of the object but there was too
much flexibility and inconsistencies arose.

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
from typing import Optional, Sequence, Union

from armi.utils.flags import Flag, auto


# Type alias used for passing type specifications to many of the composite methods. See
# Composite::hasFlags() to understand the semantics for how TypeSpecs are interpreted.
# Anything that interprets a TypeSpec should apply the same semantics.
TypeSpec = Optional[Union[Flag, Sequence[Flag]]]


def __fromStringGeneral(cls, typeSpec, updateMethod):
    """Helper method to minimize code repeat in other fromString methods."""
    result = cls(0)
    typeSpec = typeSpec.upper()
    for conversion in CONVERSIONS:
        if conversion in typeSpec:
            typeSpec = typeSpec.replace(conversion, "")
            result |= CONVERSIONS[conversion]

    for name in typeSpec.split():
        # ignore numbers so we don't have to define flags up to 217+ (number of pins/assem)
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

    a. multiple-word flags are used such as *grid plate* or
       *inlet nozzle* so we use lookups.
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
                "The requested type specification `{}` is invalid. "
                "See armi.reactor.flags documentation.".format(typeSpec)
            )

    return __fromStringGeneral(cls, typeSpec, updateMethod)


def _toString(cls, typeSpec):
    """
    Make flag from string and fail if any unknown words are encountered.

    Notes
    -----
    This converts a flag from ``Flags.A|B`` to ``'A B'``
    """
    return str(typeSpec).split("{}.".format(cls.__name__))[1].replace("|", " ")


class Flags(Flag):
    """
    Defines the valid flags used in the framework.
    """

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

    CORE = auto()
    REACTOR = auto()

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

    @classmethod
    def fromStringIgnoreErrors(cls, typeSpec):
        return _fromStringIgnoreErrors(cls, typeSpec)

    @classmethod
    def fromString(cls, typeSpec):
        return _fromString(cls, typeSpec)

    @classmethod
    def toString(cls, typeSpec):
        return _toString(cls, typeSpec)


class InvalidFlagsError(KeyError):
    """Raised when code attempts to look for an undefined flag."""

    pass


_PLUGIN_FLAGS_REGISTERED = False


def registerPluginFlags(pm):
    """
    Apply flags specified in the passed ``PluginManager`` to the ``Flags`` class.

    See Also
    --------
    armi.plugins.ArmiPlugin.defineFlags
    """
    global _PLUGIN_FLAGS_REGISTERED
    if _PLUGIN_FLAGS_REGISTERED:
        raise RuntimeError(
            "Plugin flags have already been registered. Cannot do it twice!"
        )

    for pluginFlags in pm.hook.defineFlags():
        Flags.extend(pluginFlags)
    _PLUGIN_FLAGS_REGISTERED = True


# string conversions for multiple-word flags
CONVERSIONS = {
    "GRID PLATE": Flags.GRID_PLATE,
    "GRID": Flags.GRID_PLATE,  # often used as component in "grid plate" block
    "INLET NOZZLE": Flags.INLET_NOZZLE,
    "NOZZLE": Flags.INLET_NOZZLE,
    "HANDLING SOCKET": Flags.HANDLING_SOCKET,
    "GUIDE TUBE": Flags.GUIDE_TUBE,
    "FISSION CHAMBER": Flags.FISSION_CHAMBER,
    "SOCKET": Flags.HANDLING_SOCKET,
    "SHIELD BLOCK": Flags.SHIELD_BLOCK,
    "SHIELDBLOCK": Flags.SHIELD_BLOCK,
    "CORE BARREL": Flags.CORE_BARREL,
    "INNERDUCT": Flags.INNER | Flags.DUCT,
    "GAP1": Flags.GAP | Flags.A,
    "GAP2": Flags.GAP | Flags.B,
    "GAP3": Flags.GAP | Flags.C,
    "GAP4": Flags.GAP | Flags.D,
    "GAP5": Flags.GAP | Flags.E,
    "LINER1": Flags.LINER | Flags.A,
    "LINER2": Flags.LINER | Flags.B,
}
