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

``ParameterDefinition``\ s are the metadata that describe specific parameters, and aid in enforcing
certain rules upon the parameters themselves and the parameter collections that contain them.

This module also describes the ``ParameterDefinitionCollection`` class, which serves as a
specialized container to manage related parameter definitions.

See Also
--------
armi.reactor.parameters
"""

import enum
import functools
import re
from typing import Any, Dict, Optional, Sequence, Tuple, Type

import numpy as np

from armi.reactor.flags import Flags
from armi.reactor.parameters.exceptions import ParameterDefinitionError, ParameterError

# bitwise masks for high-speed operations on the `assigned` attribute
# see: https://web.archive.org/web/20120225043338/http://www.vipan.com/htdocs/bitwisehelp.html
# Note that the various operations are responsible for clearing the flags on the events.
# These should be interpreted as:
#   The Parameter or ParameterCollection has been modified SINCE_<time-description>
# In order for that to happen, the flags need to be cleared when the <time-description> begins.
SINCE_INITIALIZATION = 1
SINCE_LAST_DISTRIBUTE_STATE = 4
SINCE_LAST_GEOMETRY_TRANSFORMATION = 8
SINCE_BACKUP = 16
SINCE_ANYTHING = SINCE_LAST_DISTRIBUTE_STATE | SINCE_INITIALIZATION | SINCE_LAST_GEOMETRY_TRANSFORMATION | SINCE_BACKUP
NEVER = 32


class Category:
    """
    A "namespace" for storing parameter categories.

    Notes
    -----
    * `cumulative` parameters are accumulated over many time steps
    * `pinQuantities` parameters are defined on the pin level within a block
    * `multiGroupQuantities` parameters have group dependence (often a 1D numpy array)
    * `fluxQuantities` parameters are related to neutron or gamma flux
    * `neutronics` parameters are calculated in a neutronics global flux solve
    * `gamma` parameters are calculated in a fixed-source gamma solve
    * `detailedAxialExpansion` parameters are marked as such so that they are mapped from the
       uniform mesh back to the non-uniform mesh
    * `reactivity coefficients` parameters are related to reactivity coefficient or kinetics
       parameters for kinetics solutions
    * `thermal hydraulics` parameters come from a thermal hydraulics physics plugin (e.g., flow
       rates, temperatures, etc.)
    """

    depletion = "depletion"
    cumulative = "cumulative"
    cumulativeOverCycle = "cumulative over cycle"
    assignInBlueprints = "assign in blueprints"
    retainOnReplacement = "retain on replacement"
    pinQuantities = "pinQuantities"
    fluxQuantities = "fluxQuantities"
    multiGroupQuantities = "multi-group quantities"
    neutronics = "neutronics"
    gamma = "gamma"
    detailedAxialExpansion = "detailedAxialExpansion"
    reactivityCoefficients = "reactivity coefficients"
    thermalHydraulics = "thermal hydraulics"


class ParamLocation(enum.Flag):
    """Represents the point on which a parameter is physically meaningful."""

    TOP = 1
    CENTROID = 2
    BOTTOM = 4
    AVERAGE = 10  # 2 + 8
    MAX = 16
    CORNERS = 32
    EDGES = 64
    VOLUME_INTEGRATED = 128
    CHILDREN = 256  # on some child of a composite, like a pin
    NA = 512  # no location


class NoDefault:
    """Class used to allow distinction between not setting a default and setting a default of
    ``None``.
    """

    def __init__(self):
        raise NotImplementedError("You cannot create an instance of NoDefault")


class _Undefined:
    """Class used to identify a parameter property as being in the undefined state."""

    def __init__(self):
        raise NotImplementedError("You cannot create an instance of _Undefined.")


class Serializer:
    r"""
    Abstract class describing serialize/deserialize operations for Parameter data.

    Parameters need to be stored to and read from database files. This currently requires that the
    Parameter data be converted to a numpy array of a datatype supported by the ``h5py`` package.
    Some parameters may contain data that are not trivially representable in numpy/HDF5, and need
    special treatment. Subclassing ``Serializer`` and setting it as a ``Parameter``\ s
    ``serializer`` allows for special operations to be performed on the parameter values as they are
    stored to the database or read back in.

    The ``Database`` already knows how to handle certain cases where the data are not
    straightforward to get into a numpy array, such as when:

      - There are ``None``\ s.

      - The dimensions of the values stored on each object are inconsistent (e.g.,
        "jagged" arrays)

    So, in these cases, a Serializer is not needed. Serializers are necessary for when the actual
    data need to be converted to a native data type (e.g., int, float, etc). For example, we use a
    Serializer to handle writing ``Flags`` to the Database, as they tend to be too big to fit into a
    system-native integer.

    .. important::

        Defining a Serializer for a Parameter in part defines the underlying representation of the
        data within a database file; the data stored in a database are sensitive to the code that
        wrote them. Changing the method that a Serializer uses to pack or unpack data may break
        compatibility with old database files. Therefore, Serializers should be diligent about
        signaling changes by updating their version. It is also good practice, whenever possible,
        to support reading old versions so that database files written by old versions can still be
        read.

    .. impl:: Users can define custom parameter serializers.
        :id: I_ARMI_PARAM_SERIALIZE
        :implements: R_ARMI_PARAM_SERIALIZE

        Important physical parameters are stored in every ARMI object. These parameters represent
        the plant's state during execution of the model. Currently, this requires that the
        parameters be serializable to a numpy array of a datatype supported by the ``h5py`` package
        so that the data can be written to, and subsequently read from, an HDF5 file.

        This class allows for these parameters to be serialized in a custom manner by providing
        interfaces for packing and unpacking parameter data. The user or downstream plugin is able
        to specify how data is serialized if that data is not naturally serializable.

    See Also
    --------
    armi.bookkeeping.db.database.packSpecialData
    armi.bookkeeping.db.database.unpackSpecialData
    armi.reactor.flags.FlagSerializer
    """

    # This will accompany the packed data as an attribute when written, and will be provided to the
    # unpack() method when reading. If the underlying format of the data changes, make sure to
    # change this.
    version: Optional[str] = None

    @staticmethod
    def pack(data: Sequence[any]) -> Tuple[np.ndarray, Dict[str, any]]:
        """
        Given unpacked data, return packed data and a dictionary of attributes needed to unpack it.

        This should perform the fundamental packing operation, returning the packed data and any
        metadata ("attributes") that would be necessary to unpack the data. The class's version is
        always stored, so no need to provide it as an attribute.

        See Also
        --------
        armi.reactor.flags.FlagSerializer.pack
        """
        raise NotImplementedError()

    @classmethod
    def unpack(cls, data: np.ndarray, version: Any, attrs: Dict[str, any]) -> Sequence[any]:
        """Given packed data and attributes, return the unpacked data."""
        raise NotImplementedError()


def isNumpyArray(paramStr):
    """Helper meta-function to create a method that sets a Parameter value to a NumPy array.

    Parameters
    ----------
    paramStr : str
        Name of the Parameter we want to set.

    Returns
    -------
    function
        A setter method on the Parameter class to force the value to be a NumPy array.
    """

    def setParameter(selfObj, value):
        if value is None or isinstance(value, np.ndarray):
            setattr(selfObj, "_p_" + paramStr, value)
        else:
            setattr(selfObj, "_p_" + paramStr, np.array(value))

    return setParameter


def isNumpyF32Array(paramStr: str):
    """Helper meta-function to create a method that sets a Parameter value to a 32 bit float NumPy array.

    Parameters
    ----------
    paramStr
        Name of the Parameter we want to set.

    Returns
    -------
    function
        A setter method on the Parameter class to force the value to be a 32 bit NumPy array.
    """

    def setParameter(selfObj, value):
        if value is None:
            # allow default of None to exist
            setattr(selfObj, "_p_" + paramStr, value)
        else:
            # force to 32 bit
            setattr(selfObj, "_p_" + paramStr, np.array(value, dtype=np.float32))

    return setParameter


@functools.total_ordering
class Parameter:
    """Metadata about a specific parameter."""

    _validName = re.compile("^[a-zA-Z0-9_]+$")

    # Using slots because Parameters are pretty static and mostly POD. __slots__ make this official,
    # and offer some performance benefits in memory (not too important; there aren't that many
    # instances of Parameter to begin with) and attribute access time (more important, since we need
    # to go through Parameter objects to get to a specific parameter's value in a
    # ParameterCollection)
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
        # nonsensical to have a serializer with no intention of saving to DB
        assert not (serializer is not None and not saveToDB)
        assert serializer is None or saveToDB
        assert self._validName.match(name), "{} is not a valid param name".format(name)
        assert len(description), f"Parameter {name} defined without description."

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
                        "Cannot get value for parameter `{}` in `{}` as no default has been "
                        "defined, and no value has been assigned.".format(self.name, type(p_self))
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
        """Name defines equality."""
        return self.name == other.name

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        """Sort alphabetically by name."""
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
        We do not check to see if ``cls != None``. This is an optimization choice, that someone may
        deem unnecessary. As a result, unlike Python's ``property`` class, a subclass cannot
        override the getter method.
        """
        return self._getter(obj)

    def setter(self, setter):
        """Decorator method for assigning setter.

        .. impl:: Provide a way to signal if a parameter needs updating across processes.
            :id: I_ARMI_PARAM_PARALLEL
            :implements: R_ARMI_PARAM_PARALLEL

            Parameters need to be handled properly during parallel code execution. This includes
            notifying processes if a parameter has been updated by another process. This method
            allows for setting a parameter's value as well as an attribute that signals whether this
            parameter has been updated. Future processes will be able to query this attribute so
            that the parameter's status is properly communicated.

        Notes
        -----
        Unlike the traditional Python ``property`` class, this does not return a new instance of a
        ``Parameter``; therefore it cannot be reassigned in the same way that a Python ``property``
        can be.

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
                "The setter for parameter `{}` must be callable. Setter attribute: {}".format(self.name, setter)
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

    def hasCategory(self, category: str) -> bool:
        """True if a parameter has a specific category."""
        return category in self.categories


class ParameterDefinitionCollection:
    """
    A very specialized container for managing parameter definitions.

    Notes
    -----
    ``_representedTypes`` is used to detect if this ``ParameterDefinitionCollection`` contains
    definitions for only one type. If the collection only exists for 1 type, the lookup
    (``__getitem__``) can short circuit O(n) logic for O(1) dictionary lookup.
    """

    # Slots are not being used here as an attempt at optimization. Rather, they serve to add some
    # needed rigidity to the parameter system.
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
        """Get a parameter by name.

        Notes
        -----
        This method might break if the collection is for multiple composite types, and there exists
        a parameter with the same name in multiple types.
        """
        # O(1) lookup if there is only 1 type, could still raise a KeyError
        if len(self._representedTypes) == 1:
            return self._paramDefDict[name, next(iter(self._representedTypes))]

        # "matches" only checks for the same name, while the add method checks both name and
        # collectionType
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
        """Add a :py:class:`Parameter` to this collection."""
        assert not self._locked, "This ParameterDefinitionCollection has been locked."
        self._paramDefs.append(paramDef)
        self._paramDefDict[paramDef.name, paramDef.collectionType] = paramDef
        self._representedTypes.add(paramDef.collectionType)

    def _filter(self, filterFunc):
        pdc = ParameterDefinitionCollection()
        pdc.extend(filter(filterFunc, self._paramDefs))
        return pdc

    def items(self):
        return self._paramDefDict.items()

    def extend(self, other):
        """Grow a parameter definition collection by another parameter definition collection."""
        assert not self._locked, "This ParameterDefinitionCollection ({}) has been locked.".format(
            self._representedTypes
        )
        assert self is not other
        if other is None:
            raise ValueError(
                f"Cannot extend {self} with `None`. Ensure return value of parameter definitions returns something."
            )
        for pd in other:
            self.add(pd)

    def inCategory(self, categoryName):
        """
        Create a :py:class:`ParameterDefinitionCollection` that contains definitions that are in a
        specific category.
        """
        return self._filter(lambda pd: categoryName in pd.categories)

    def atLocation(self, paramLoc):
        """
        Make a param definition collection with all defs defined at a specific location.

        Parameters can be defined at various locations within their container based on
        :py:class:`ParamLocation`. This allows selection by those values.
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
        """
        Create a :py:class:`ParameterDefinitionCollection` that contains definitions for a
        specific composite type.
        """
        return self._filter(lambda pd: issubclass(compositeType.paramCollectionType, pd.collectionType))

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
        """Get a :py:class:`Parameter` by compositeType and name."""
        return self._paramDefDict[name, compositeType.paramCollectionType]

    def byNameAndCollectionType(self, name, collectionType):
        """Get a :py:class:`Parameter` by collectionType and name."""
        return self._paramDefDict[name, collectionType]

    @property
    def categories(self):
        """Get the categories of all the :py:class:`~Parameter` instances within this collection."""
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

    def toWriteToDB(self, assignedMask: Optional[int] = None):
        """
        Get a list of acceptable parameters to store to the database for a level of the data model.

        .. impl:: Filter parameters to write to DB.
            :id: I_ARMI_PARAM_DB
            :implements: R_ARMI_PARAM_DB

            This method is called when writing the parameters to the database file. It queries the
            parameter's ``saveToDB`` attribute to ensure that this parameter is desired for saving
            to the database file. It returns a list of parameters that should be included in the
            database write operation.

        Parameters
        ----------
        assignedMask : int
            A bitmask to down-filter which params to use based on how "stale" they are.
        """
        mask = assignedMask or SINCE_ANYTHING
        return [p for p in self if p.saveToDB and p.assigned & mask]

    def createBuilder(self, *args, **kwargs):
        """
        Create an associated object that can create definitions into this collection.

        Using the returned ParameterBuilder will add all defined parameters to this
        ParameterDefinitionCollection, using the passed arguments as defaults. Arguments should be
        valid arguments to ``ParameterBuilder.__init__()``
        """
        paramBuilder = ParameterBuilder(*args, **kwargs)
        paramBuilder.associateParameterDefinitionCollection(self)
        return paramBuilder


class ParameterBuilder:
    """Factory for creating Parameter and parameter properties."""

    def __init__(
        self,
        location=ParamLocation.AVERAGE,
        default=NoDefault,
        categories=None,
        saveToDB=True,
    ):
        """Create a :py:class:`ParameterBuilder`."""
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

    @staticmethod
    def _assertDefaultIsProperType(default):
        if default in (NoDefault, None) or isinstance(default, (int, str, float, bool, Flags)):
            return
        raise AssertionError(
            "Cannot specify a default mutable type ({}) value to a parameter; all instances would "
            "share the same list.".format(type(default))
        )

    def associateParameterDefinitionCollection(self, paramDefs):
        """
        Associate this parameter factory with a specific ParameterDefinitionCollection.

        Subsequent calls to defParam will automatically add the created ParameterDefinitions to this
        ParameterDefinitionCollection. This results in a cleaner syntax when defining many
        ParameterDefinitions.
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
        r"""Create a parameter as a property (with get/set) on a class.

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
        It is not possible to initialize the parameter on the class this method would be used on,
        because there is no instance (i.e. self) when this method is run. However, this method could
        access a globally available set of definitions, if one existed.
        """
        self._assertDefaultIsProperType(default)
        if location is None and self._defaultLocation is None:
            raise ParameterDefinitionError(
                "The default location is not specified for {}; a parameter-specific location is required.".format(self)
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
            serializer=serializer,
        )

        if self._paramDefs is not None:
            self._paramDefs.add(paramDef)
        return paramDef


# Container for all parameter definition collections that have been bound to an ArmiObject or
# subclass. These are added from the applyParameters() method on the ParameterCollection class.
ALL_DEFINITIONS = ParameterDefinitionCollection()
