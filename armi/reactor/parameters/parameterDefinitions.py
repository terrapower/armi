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
This module contains the code necessary to represent parameter definitions.

``ParameterDefinition``s are the metadata that describe specific parameters, and aid in
enforcing certain rules upon the parameters themselves and the parameter collections
that contain them.

This module also describes the ``ParameterDefinitionCollection`` class, which serves as
a specialized container to manage related parameter definitions.

See Also
--------
armi.reactor.parameters
"""
import enum
import re
import functools
from typing import Any, Callable, Dict, Optional, Sequence, Tuple, Type

import numpy

from armi.reactor.flags import Flags

from .exceptions import ParameterError, ParameterDefinitionError

# bitwise masks for high-speed operations on the `assigned` attribute
# (see http://www.vipan.com/htdocs/bitwisehelp.html)
# Note that the various operations are responsible for clearing the flags on the events.
# These should be interpreted as:
#   The Parameter or ParameterCollection has been modified SINCE_<time-description>
# In order for that to happen, the flags need to be cleared when the <time-description>
# begins.
SINCE_INITIALIZATION = 1
SINCE_LAST_DB_TRANSMISSION = 2
SINCE_LAST_DISTRIBUTE_STATE = 4
SINCE_LAST_GEOMETRY_TRANSFORMATION = 8
SINCE_BACKUP = 16
SINCE_ANYTHING = (
    SINCE_LAST_DISTRIBUTE_STATE
    | SINCE_LAST_DB_TRANSMISSION
    | SINCE_INITIALIZATION
    | SINCE_LAST_GEOMETRY_TRANSFORMATION
    | SINCE_BACKUP
)
NEVER = 32


class Category:
    """A "namespace" for storing parameter categories."""

    assignInBlueprints = "assign in blueprints"

    retainOnReplacement = "retain on replacement"

    volumeIntegrated = "volumeIntegrated"

    fluxQuantities = "fluxQuantities"

    multiGroupQuantities = "multi-group quantities"


class ParamLocation(enum.Flag):
    """Represents point which a parameter is physically meaningful."""

    TOP = 1
    CENTROID = 2
    BOTTOM = 4
    AVERAGE = 10  # 2 + 8
    MAX = 16
    CORNERS = 32
    EDGES = 64
    VOLUME_INTEGRATED = 128
    CHILDREN = 256  # on some child of a composite, like a pin


class NoDefault:
    r"""Class used to allow distinction between not setting a default and setting a default of ``None``"""

    def __init__(self):
        raise NotImplementedError("You cannot create an instance of NoDefault")


class _Undefined:
    r"""Class used to identify a parameter property as being in the undefined state"""

    def __init__(self):
        raise NotImplementedError("You cannot create an instance of _Undefined.")


class Serializer:
    """
    Abstract class describing serialize/deserialize operations for Parameter data.

    Parameters need to be stored to and read from database files. This currently
    requires that the Parameter data be converted to a numpy array of a datatype
    supported by the ``h5py`` package. Some parameters may contain data that are not
    trivially representable in numpy/HDF5, and need special treatment. Subclassing
    ``Serializer`` and setting it as a ``Parameter``s ``serializer`` allows for special
    operations to be performed on the parameter values as they are stored to the
    database or read back in.

    The ``Database3`` already knows how to handle certain cases where the data are not
    straightforward to get into a numpy array, such as when:

      - There are ``None`` s.

      - The dimensions of the values stored on each object are inconsistent (e.g.,
        "jagged" arrays)

    So, in these cases, a Serializer is not needed. Serializers are necessary for when
    the actual data need to be converted to a native data type (e.g., int, float, etc.)
    For example, we use a Serializer to handle writing ``Flags`` to the Database, as
    they tend to be too big to fit into a system-native integer.

    .. important::

        Defining a Serializer for a Parameter in part defines the underlying
        representation of the data within a database file; the data stored in a database
        are sensitive to the code that wrote them. Changing the method that a Serializer
        uses to pack or unpack data may break compatibility with old databse files.
        Therefore, Serializers should be dilligent about signalling changes by updating
        their version. It is also good practice, whenever possible, to support reading
        old versions so that database files written by old versions can still be read.

    See Also
    --------
    armi.bookkeeping.db.database3.packSpecialData
    armi.bookkeeping.db.database3.unpackSpecialData
    armi.reactor.flags.FlagSerializer
    """

    # This will accompany the packed data as an attribute when written, and will be
    # provided to the unpack() method when reading. If the underlying format of the data
    # changes, make sure to change this.
    version = None

    @staticmethod
    def pack(data: Sequence[any]) -> Tuple[numpy.ndarray, Dict[str, any]]:
        """
        Given unpacked data, return packed data and a dictionary of attributes needed to
        unpack it.

        The should perform the fundamental packing operation, returning the packed data
        and any metadata ("attributes") that would be necessary to unpack the data. The
        class's version is always stored, so no need to provide it as an attribute.

        See Also
        --------
        armi.reactor.flags.FlagSerializer.pack
        """
        raise NotImplementedError()

    @classmethod
    def unpack(
        cls, data: numpy.ndarray, version: Any, attrs: Dict[str, any]
    ) -> Sequence[any]:
        """Given packed data and attributes, return the unpacked data."""
        raise NotImplementedError()


@functools.total_ordering
class Parameter:
    r"""Metadata about a specific parameter"""
    _validName = re.compile("^[a-zA-Z0-9_]+$")

    # Using slots because Parameters are pretty static and mostly POD. __slots__ make
    # this official, and offer some performance benefits in memory (not too important;
    # there aren't that many instances of Parameter to begin with) and attribute access
    # time (more important, since we need to go through Parameter objects to get to a
    # specific parameter's value in a ParameterCollection)
    __slots__ = (
        "name",
        "fieldName",
        "collectionType",
        "location",
        "saveToDB",
        "serializer",
        "units",
        "default",
        "_getter",
        "_setter",
        "description",
        "categories",
        "assigned",
        "_backup",
    )

    def __init__(
        self,
        name,
        units,
        description,
        location,
        saveToDB,
        default,
        setter,
        categories,
        serializer: Optional[Type[Serializer]] = None,
    ):
        assert self._validName.match(name), "{} is not a valid param name".format(name)
        assert not (serializer is not None and not saveToDB)
        # nonsensical to have a serializer with no intention of saving to DB; probably
        # in error
        assert serializer is None or saveToDB
        self.collectionType = _Undefined
        self.name = name
        self.fieldName = "_p_" + name
        self.location = location
        self.saveToDB = saveToDB
        self.serializer = serializer
        self.description = description
        self.units = units
        self.default = default
        self.categories = categories
        self.assigned = NEVER
        self._backup = None

        if self.default is not NoDefault:

            def paramGetter(p_self):
                return getattr(p_self, self.fieldName, self.default)

        else:

            def paramGetter(p_self):
                value = getattr(p_self, self.fieldName)
                if value is NoDefault:
                    raise ParameterError(
                        "Cannot get value for parameter `{}` in `{}` as no default has "
                        "been defined, and no value has been assigned.".format(
                            self.name, type(p_self)
                        )
                    )
                return value

        self._getter = paramGetter
        self._setter = None  # actually, it gets assigned with this:
        self.setter(setter)

    def __repr__(self):
        return "<ParamDef name:{} collectionType:{} units:{} assigned:{}>".format(
            self.name, self.collectionType.__name__, self.units, self.assigned
        )

    def __eq__(self, other):
        """Name defines equality"""
        return self.name == other.name

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        """Sort alphabetically by name"""
        return self.name < other.name

    def __hash__(self):
        return hash(self.name) + id(self)

    def __setstate__(self, state):
        self._backup = state[0]  # a tuple of 1 element.

    def __set__(self, obj, val):
        """This is a property setter, see Python documentation for "descriptor"."""
        self._setter(obj, val)

    def __get__(self, obj, cls=None):
        """This is a property getter, see Python documentation for "descriptor".

        Notes
        -----
        We do not check to see if ``cls != None``. This is an optimization choice, that
        someone may deem unnecessary. As a result, unlike Python's ``property`` class, a
        subclass cannot override the getter method.
        """
        return self._getter(obj)

    def setter(self, setter):
        """Decorator method for assigning setter.

        Notes
        -----
        Unlike the traditional Python ``property`` class, this does not return a new
        instance of a ``Parameter``; therefore it cannot be reassigned in the same way
        that a Python ``property`` can be.

        Examples
        --------
        >>> class MyParameterCollection(parameters.ParameterCollection):
        ...     mass = parameters.Parameter(...)
        ...     @mass.setter
        ...     def mass(self, value):
        ...         if value < 0:
        ...             raise ValueError("Negative mass is not possible, consider a diet.")
        ...         self._p_speed = value
        """
        if setter is NoDefault:

            def paramSetter(p_self, value):
                self.assigned = SINCE_ANYTHING
                p_self.assigned = SINCE_ANYTHING
                setattr(p_self, self.fieldName, value)

        elif setter is None:

            def paramSetter(p_self, value):
                raise ParameterError(
                    "Cannot set value for parameter `{}` on {} to `{}`, it has a restricted setter.".format(
                        self.name, p_self, value
                    )
                )

        elif callable(setter):

            def paramSetter(p_self, value):
                self.assigned = SINCE_ANYTHING
                p_self.assigned = SINCE_ANYTHING
                setter(p_self, value)

        else:
            raise ParameterDefinitionError(
                "The setter for parameter `{}` must be callable. Setter attribute: {}".format(
                    self.name, setter
                )
            )

        self._setter = paramSetter

        return self

    def backUp(self):
        """Back up the assigned state."""
        self._backup = (self._backup, self.assigned)

    def restoreBackup(self, paramsToApply):
        """Restore the backed up state."""
        if self in paramsToApply:
            # retain self.assigned if self in a category
            self._backup, _assigned = self._backup
        else:
            self._backup, self.assigned = self._backup

    def atLocation(self, loc):
        """True if parameter is defined at location."""
        return self.location and self.location & loc


class ParameterDefinitionCollection(object):
    r"""
    A very specialized container for managing parameter definitions.

    Notes
    -----
    ``_representedTypes`` is used to detect if this ``ParameterDefinitionCollection``
    contains definitions for only one type. If the collection only exists for 1 type,
    the lookup (``__getitem__``) can short circuit O(n) logic for O(1) dictionary
    lookup.
    """

    # Slots are not being used here as an attempt at optimization. Rather, they serve to
    # add some needed rigidity to the parameter system.
    __slots__ = ("_paramDefs", "_paramDefDict", "_representedTypes", "_locked")

    def __init__(self):
        self._paramDefs = list()
        self._paramDefDict = dict()
        self._representedTypes = set()
        self._locked = False

    def __iter__(self):
        return iter(self._paramDefs)

    def __len__(self):
        return len(self._paramDefs)

    def __getitem__(self, name):
        r"""Get a parameter by name.

        Notes
        -----
        This method might break if the collection is for multiple composite types, and
        there exists a parameter with the same name in multiple types.
        """
        # O(1) lookup if there is only 1 type, could still raise a KeyError
        if len(self._representedTypes) == 1:
            return self._paramDefDict[name, next(iter(self._representedTypes))]

        # "matches" only checks for the same name, while the add method checks both name
        # and collectionType
        matches = [pd for pd in self if pd.name == name]
        if len(matches) != 1:
            raise KeyError(
                "Too {} parameters with the name `{}`. Matches:\n{}".format(
                    "many" if len(matches) > 1 else "few",
                    name,
                    "\n".join(str(pd) for pd in matches),
                )
            )
        return matches[0]

    def add(self, paramDef):
        r"""add a :py:class:`Parameter` to this collection.
        """
        assert not self._locked, "This ParameterDefinitionCollection has been locked."
        self._paramDefs.append(paramDef)
        self._paramDefDict[paramDef.name, paramDef.collectionType] = paramDef
        self._representedTypes.add(paramDef.collectionType)

    def _filter(self, filterFunc):
        pdc = ParameterDefinitionCollection()
        pdc.extend(filter(filterFunc, self._paramDefs))
        return pdc

    def extend(self, other):
        """
        Grow a parameter definition collection by another parameter definition collection
        """
        assert (
            not self._locked
        ), "This ParameterDefinitionCollection ({}) has been locked.".format(
            self._representedTypes
        )
        assert self is not other
        for pd in other:
            self.add(pd)

    def inCategory(self, categoryName):
        r"""
        Create a :py:class:`ParameterDefinitionCollection` that contains definitions that are in a
        specific category.
        """
        return self._filter(lambda pd: categoryName in pd.categories)

    def atLocation(self, paramLoc):
        """
        Make a param definition collection with all defs defined at a specific location.

        Parameters can be defined at various locations within their container
        based on :py:class:`ParamLocation`. This allows selection by those values.
        """
        return self._filter(lambda pd: pd.atLocation(paramLoc))

    def since(self, mask):
        """
        Create a :py:class:`ParameterDefinitionCollection` that contains definitions that have been
        modified since a specific set of actions.
        """
        return self._filter(lambda pd: pd.assigned & mask)

    def unchanged_since(self, mask):
        """
        Create a :py:class:`ParameterDefinitionCollection` that contains definitions that have not
        been modified since a specific set of actions. This is the complementary set of the
        collection returned by `since`.
        """
        return self._filter(lambda pd: not (pd.assigned & mask))

    def forType(self, compositeType):
        r"""
        Create a :py:class:`ParameterDefinitionCollection` that contains definitions for a
        specific composite type.
        """
        return self._filter(
            lambda pd: issubclass(compositeType.paramCollectionType, pd.collectionType)
        )

    def resetAssignmentFlag(self, mask):
        """
        Clear the `assigned` flag for a certain operation on all parameters.

        These flags will get set by the param definition setters if they get changed again.

        Notes
        -----
        See http://www.vipan.com/htdocs/bitwisehelp.html to understand the bitwise operations
        """
        for pd in self._paramDefs:
            pd.assigned &= ~mask

    def setAssignmentFlag(self, mask):
        for pd in self._paramDefs:
            pd.assigned |= mask

    def byNameAndType(self, name, compositeType):
        r"""Get a :py:class:`Parameter` by compositeType and name."""
        return self._paramDefDict[name, compositeType.paramCollectionType]

    def byNameAndCollectionType(self, name, collectionType):
        r"""Get a :py:class:`Parameter` by compositeType and name."""
        return self._paramDefDict[name, collectionType]

    @property
    def categories(self):
        r"""Get the categories of all the :py:class:`~Parameter` instances within this collection"""
        categories = set()
        for paramDef in self:
            categories |= paramDef.categories
        return categories

    @property
    def names(self):
        return [pd.name for pd in self]

    def lock(self):
        self._locked = True

    @property
    def locked(self):
        return self._locked

    def toWriteToDB(self, assignedMask):
        """
        Get a list of acceptable parameters to store to the database for a level of the data model.

        Parameters
        ----------
        assignedMask : int
            a bitmask to down-filter which params to use based on how "stale" they are.
        """
        return [p for p in self if p.saveToDB and p.assigned & assignedMask]

    def createBuilder(self, *args, **kwargs):
        """
        Create an associated object that can create definitions into this collection

        Using the returned ParameterBuilder will add all defined parameters to this
        ParameterDefinitionCollection, using the passed arguments as defaults. Arguments
        should be valid arguments to ``ParameterBuilder.__init__()``
        """
        paramBuilder = ParameterBuilder(*args, **kwargs)
        paramBuilder.associateParameterDefinitionCollection(self)
        return paramBuilder


class ParameterBuilder(object):
    r"""Factory for creating Parameter and parameter properties"""

    def __init__(
        self,
        location=ParamLocation.AVERAGE,
        default=NoDefault,
        categories=None,
        saveToDB=True,
    ):
        r"""Create a :py:class:`ParameterBuilder`

        """
        self._entered = False
        self._defaultLocation = location
        self._defaultCategories = set(categories or [])  # make sure it is always a set
        self._defaultValue = default
        self._assertDefaultIsProperType(default)
        self._saveToDB = saveToDB
        self._paramDefs = None

    def __enter__(self):
        self._entered = True
        return self

    def __exit__(self, exc_type, exc_value, tracebac):
        if exc_type is not None:
            # allow exceptions to be raised normally, to prevent confusing stack traces
            return
        self._entered = False

    def _assertDefaultIsProperType(self, default):
        if default in (NoDefault, None) or isinstance(
            default, (int, str, float, bool, Flags)
        ):
            return
        raise AssertionError(
            "Cannot specify a default mutable type ({}) value to a parameter; all instances would "
            "share the same list.".format(type(default))
        )

    def associateParameterDefinitionCollection(self, paramDefs):
        """
        Associate this parameter factory with a specific ParameterDefinitionCollection

        Subsequent calls to defParam will automatically add the created
        ParameterDefinitions to this ParameterDefinitionCollection. This results in a
        cleaner syntax when defining many ParameterDefinitions.
        """
        self._paramDefs = paramDefs

    def defParam(
        self,
        name,
        units,
        description,
        location=None,
        saveToDB=NoDefault,
        default=NoDefault,
        setter=NoDefault,
        categories=None,
        serializer: Optional[Type[Serializer]] = None,
    ):
        r"""Create a parameter as a property (with get/set) on a class

        Parameters
        ----------
        name: str
            the official name of the parameter

        units: str
            string representation of the units

        description: str
            a brief, but precise-as-possible description of what the parameter is used
            for.

        location: str
            string representation of the location the attribute is applicable to, such
            as average, max, etc.

        saveToDB: bool
            indicator as to whether the parameter should be written to the database. The
            actual default is defined by the :py:class:`ParameterBuilder`, and is
            :code:`True`.

        default: immutable type
            a default value for this parameter which must be an immutable type. If the
            type is mutable, e.g. a list, dict, an exception should be raised, or
            unknown behavior.

        setter: None or callable
            If ``None``, there is no direct way to set the parameter. If some other
            callable method, (which may have the same name as the property!) then the
            setter method is used instead.

        categories: List of str
            A list of categories to which this Parameter should belong. Categories are
            typically used to engage special treatment for certain Parameters.

        serializer: Optional subclass of Serializer
            A class describing how the parameter data should be stored to the database.
            This is usually only needed in exceptional cases where it is difficult to
            store a parameter in a numpy array.

        Notes
        -----
        It is not possible to initialize the parameter on the class this method would be
        used on, because there is no instance (i.e. self) when this method is run.
        However, this method could access a globally available set of definitions, if
        one existed.
        """
        self._assertDefaultIsProperType(default)
        if location is None and self._defaultLocation is None:
            raise ParameterDefinitionError(
                "The default location is not specified for {}; "
                "a parameter-specific location is required.".format(self)
            )

        paramDef = Parameter(
            name,
            units=units,
            description=description,
            location=location or self._defaultLocation,
            saveToDB=saveToDB if saveToDB is not NoDefault else self._saveToDB,
            default=default if default is not NoDefault else self._defaultValue,
            setter=setter,
            categories=set(categories or []).union(self._defaultCategories),
            serializer=serializer
        )

        if self._paramDefs is not None:
            self._paramDefs.add(paramDef)
        return paramDef


# Container for all parameter definition collections that have been bound to an
# ArmiObject or subclass. These are added from the applyParameters() class method on
# the ParameterCollection class.
ALL_DEFINITIONS = ParameterDefinitionCollection()
