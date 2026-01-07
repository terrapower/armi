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
A Flag class, similar to ``enum.Flag``.

This is an alternate implementation of the standard-library ``enum.Flag`` class. We use this to implement
:py:class:`armi.reactor.flags.Flags`. We used to use the standard-library implementation, but that became limiting when
we wanted to make it possible for plugins to define their own flags; the standard implementation does not support
extension. We also considered the ``aenum`` package, which permits extension of ``Enum`` classes, but unfortunately does
not support extension of ``Flags``. So, we had to make our own. This is a much simplified version of what comes with
``aenum``, but still provides most of the safety and functionality.
"""

import math
from typing import Dict, List, Sequence, Tuple, Union

from armi import runLog


class auto:  # noqa: N801
    """
    Empty class for requesting a lazily-evaluated automatic field value.

    This can be used to automatically provision a value for a field, when the specific value does not matter.

    In the future, it would be nice to support some arithmetic for these so that automatically-derived combinations of
    other automatically defined fields can be specified as well.
    """

    def __iter__(self):
        """
        Dummy __iter__ implementation.

        This is only needed to make mypy happy when it type checks things that have FlagTypes in them, since these can
        normally be iterated over, but mypy doesn't know that the metaclass consumes the autos.
        """
        raise NotImplementedError(
            f"__iter__() is not actually implemented on {type(self)}; it is only defined to appease mypy."
        )


class _FlagMeta(type):
    """
    Metaclass for defining new Flag classes.

    This attempts to do the minimum required to make the Flag class and its subclasses function properly. It mostly
    digests the class attributes, resolves automatic values and creates instances of the class as it's own class
    attributes for each field. The rest of the functionality lives in the base ``Flag`` class as plain-old code.

    .. tip:: Because individual flags are defined as *class* attributes (as opposed to instance attributes), we have to
        customize the way a Flag subclass itself is built, which requires a metaclass.
    """

    def __new__(cls, name, bases, attrs):
        autoAt = 1
        explicitFields = [(attr, val) for attr, val in attrs.items() if isinstance(val, int)]
        explicitValues = set(val for name, val in explicitFields)

        flagClass = type.__new__(cls, name, bases, attrs)

        # Make sure that none of the values collide
        assert len(explicitValues) == len(explicitFields)

        # Assign numeric values to the autos
        for aName, aVal in attrs.items():
            if isinstance(aVal, auto):
                while autoAt in explicitValues:
                    autoAt *= 2
                attrs[aName] = autoAt
                autoAt *= 2

        # Auto fields have been resolved, so now collect all ints
        allFields = {name: val for name, val in attrs.items() if isinstance(val, int)}
        allFields = {n: v for n, v in allFields.items() if not _FlagMeta.isdunder(n)}
        flagClass._nameToValue = allFields
        flagClass._valuesTaken = set(val for _, val in allFields.items())
        flagClass._autoAt = autoAt
        flagClass._width = math.ceil(len(flagClass._nameToValue) / 8)

        # Replace the original class attributes with instances of the class itself.
        for name, value in allFields.items():
            instance = flagClass()
            instance._value = value
            setattr(flagClass, name, instance)

        return flagClass

    @staticmethod
    def isdunder(s):
        return s.startswith("__") and s.endswith("__")

    def __getitem__(cls, key):
        """
        Implement indexing at the class level.

        This has to be done at the metaclass level, since the python interpreter looks to
        ``type(klass).__getitem__(klass, key)``, which for an implementation of Flag is this metaclass.
        """
        return cls(cls._nameToValue[key])


class Flag(metaclass=_FlagMeta):
    """
    A collection of bitwise flags.

    This is intended to emulate ``enum.Flag``, except with the possibility of extension after the class has been
    defined. Most docs for ``enum.Flag`` should be relevant here, but there are sure to be occasional differences.

    .. impl:: No two flags have equivalence.
        :id: I_ARMI_FLAG_DEFINE
        :implements: R_ARMI_FLAG_DEFINE

        A bitwise flag class intended to emulate the standard library's ``enum.Flag``, with the added functionality that
        it allows for extension after the class has been defined. Each Flag is unique; no two Flags are equivalent.

        Note that while Python allows for arbitrary-width integers, exceeding the system-native integer size can lead to
        challenges in storing data, e.g. in an HDF5 file. In this case, the ``from_bytes()`` and ``to_bytes()`` methods
        are provided to represent a Flag's values in smaller chunks so that writeability can be maintained.

    .. warning::
        Python features arbitrary-width integers, allowing one to represent an practically unlimited number of fields.
        *However*, including more flags than can be represented in the system-native integer types may lead to strange
        behavior when interfacing with non-pure Python code. For instance, exceeding 64 fields makes the underlying
        value not trivially-storable in an HDF5 file. In such circumstances, the ``from_bytes()`` and ``to_bytes()``
        methods are available to represent a Flag's values in smaller chunks.
    """

    _autoAt = None
    _nameToValue = dict()
    _valuesTaken = set()
    _width = None

    def __init__(self, init=0):
        self._value = int(init)

    def _flagsOn(self):
        flagsOn = set()
        for k, v in self._nameToValue.items():
            if self._value & v:
                flagsOn.add(k)

        return flagsOn

    def __repr__(self):
        return f"<{type(self).__name__}.{'|'.join(self._flagsOn())}: {self._value}>"

    def __str__(self):
        return f"{type(self).__name__}.{'|'.join(self._flagsOn())}"

    def __getstate__(self):
        return self._value

    def __setstate__(self, state: int):
        self._value = state

    @classmethod
    def _registerField(cls, name, value):
        """
        Plug a new field into the Flags.

        This makes sure everything is consistent and does error/collision checks. Mostly useful for extending an
        existing class with more fields.
        """
        if name in cls._nameToValue:
            runLog.debug(f"The flag {name} already exists and does not need to be recreated.")
            return

        cls._valuesTaken.add(value)
        cls._nameToValue[name] = value
        cls._width = math.ceil(len(cls._nameToValue) / 8)
        instance = cls(value)
        setattr(cls, name, instance)

    @classmethod
    def _resolveAutos(cls, fields: Sequence[str]) -> List[Tuple[str, int]]:
        """Assign values to autos, based on the current state of the class."""
        # There is some opportunity for code reuse between this and the metaclass...
        resolved = []
        for field in fields:
            while cls._autoAt in cls._valuesTaken:
                cls._autoAt *= 2
            value = cls._autoAt
            resolved.append((field, value))
            cls._autoAt *= 2
        return resolved

    @classmethod
    def width(cls):
        """Return the number of bytes needed to store all of the flags on this class."""
        return cls._width

    @classmethod
    def fields(cls):
        """Return a dictionary containing a mapping from field name to integer value."""
        return cls._nameToValue

    @classmethod
    def sortedFields(cls):
        """Return a list of all field names, sorted by increasing integer value."""
        return [i[0] for i in sorted(cls._nameToValue.items(), key=lambda item: item[1])]

    @classmethod
    def extend(cls, fields: Dict[str, Union[int, auto]]):
        """
        Extend the Flags object with new fields.

        .. warning::
            This alters the class that it is called upon! Existing instances should see the new data, since classes are
            mutable.

        .. impl:: Set of flags are extensible without loss of uniqueness.
            :id: I_ARMI_FLAG_EXTEND0
            :implements: R_ARMI_FLAG_EXTEND

            A class method to extend a ``Flag`` with a vector of provided additional ``fields``, with field names as
            keys, without loss of uniqueness. Values for the additional ``fields`` can be explicitly specified, or an
            instance of ``auto`` can be supplied.

        Parameters
        ----------
        fields : dict
            A dictionary containing field names as keys, and their desired values, or an instance of ``auto`` as values.

        Example
        -------
        >>> class MyFlags(Flags):
        ...     FOO = auto()
        ...     BAR = 1
        ...     BAZ = auto()
        >>> MyFlags.extend({"SUPER": auto()})
        >>> print(MyFlags.SUPER)
        <MyFlags.SUPER: 8>
        """
        # add explicit values first, so that autos know about them
        for field, value in ((f, v) for f, v in fields.items() if isinstance(v, int)):
            cls._registerField(field, value)

        # find auto values (ignore if they already exist)
        toResolve = [field for field, val in fields.items() if isinstance(val, auto)]
        toResolve = [field for field in toResolve if field not in cls._nameToValue]
        resolved = cls._resolveAutos(toResolve)
        for field, value in resolved:
            cls._registerField(field, value)

    def to_bytes(self, byteorder="little"):
        """
        Return a byte stream representing the flag.

        This is useful when storing Flags in a data type of limited size. Python ints can be of arbitrary size, while
        most other systems can only represent integers of 32 or 64 bits. For compatibility, this function allows to
        convert the flags to a sequence of single-byte elements.

        Note that this uses snake_case to mimic the method on the Python-native int type.
        """
        return self._value.to_bytes(self.width(), byteorder=byteorder)

    @classmethod
    def from_bytes(cls, bytes, byteorder="little"):
        """Return a Flags instance given a byte stream."""
        return cls(int.from_bytes(bytes, byteorder=byteorder))

    def __int__(self):
        return self._value

    def __and__(self, other):
        return type(self)(self._value & other._value)

    def __or__(self, other):
        return type(self)(self._value | other._value)

    def __xor__(self, other):
        return type(self)(self._value ^ other._value)

    def __invert__(self):
        """
        Implement unary ~.

        Note
        ----
        This is avoiding just ~ on the ``_value`` because it might not be safe. Using the int directly is slightly
        dangerous in that python ints are not of fixed width, so the result of inverting one Flag might not be as wide
        as the result of inverting another Flag. Typically, one would want to invert a Flag to create a mask for
        unsetting a bit on another Flag, like ``f1 &= ~f2``. If ``f2`` is narrower than ``f1`` the field of ones that
        you need to keep ``f1`` bits on might not cover the width of ``f1``, erroneously turning off its upper bits. Not
        sure if this was an issue before or not. Once things are working, might makes sense to play with this more.
        """
        new = self._value
        for _, val in self._nameToValue.items():
            if val & new:
                new -= val
            else:
                new += val
        return type(self)(new)

    def __iter__(self):
        for _, value in self._nameToValue.items():
            if value & self._value:
                yield type(self)(value)

    def __bool__(self):
        return bool(self._value)

    def __eq__(self, other):
        return self._value == other._value

    def __contains__(self, other):
        return bool(other & self)

    def __hash__(self):
        return hash(self._value)


# Type alias to reliably check for a proper Flag type. This cannot just be `Flag`, since mypy gets confused by `auto`
# because it doesn't go to the trouble of resolving them in the metaclass.
FlagType = Union[Flag, auto]
