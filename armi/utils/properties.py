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

"""This module contains methods for adding properties with custom behaviors to classes."""

import numpy as np


def areEqual(val1, val2, relativeTolerance=0.0):
    hackEqual = numpyHackForEqual(val1, val2)
    if hackEqual or not relativeTolerance:  # takes care of dictionaries and strings.
        return hackEqual
    return np.allclose(val1, val2, rtol=relativeTolerance, atol=0.0)  # does not work for dictionaries or strings


def numpyHackForEqual(val1, val2):
    """Checks lots of types for equality like strings and dicts."""
    # when doing this with numpy arrays you get an array of booleans which causes the value error
    if isinstance(val1, np.ndarray) and isinstance(val2, np.ndarray):
        if val1.size != val2.size:
            return False

    notEqual = val1 != val2
    try:  # should work for everything but numpy arrays
        if isinstance(notEqual, np.ndarray) and notEqual.size == 0:
            return True
        return not notEqual.__bool__()
    except (AttributeError, ValueError):  # from comparing 2 numpy arrays
        return not notEqual.any()


def createImmutableProperty(name, dependencyAction, doc):
    """Create a properrty that raises useful AttributeErrors when the attribute has not been assigned.

    Parameters
    ----------
    name : str
        Name of the property. This is unfortunately necessary, because the method does not know the name of
        the property being assigned by the developer.

    dependencyAction : str
        Description of an action that needs to be performed in order to set the value of the property.

    doc : str
        Docstring of the property.

    See Also
    --------
    armi.utils.properties.unlockImmutableProperties
    armi.utils.properties.lockImmutableProperties

    Examples
    --------
    The following example is essentially exactly how this should be used.

    >>> class SomeClass:
    ...     myNum = createImmutableProperty("myNum", "You must invoke the initialize() method", "My random number")
    ...
    ...     def initialize(self, val):
    ...         unlockImmutableProperties(self)
    ...         try:
    ...             self.myNum = val
    ...         finally:
    ...             lockImmutableProperties(self)
    >>> sc = SomeClass()
    >>> sc.myNum.__doc__
    My Random Number
    >>> sc.myNum  # raises error, because it hasn't been assigned
    ImmutablePropertyError
    >>> sc.myNum = 42.1
    >>> sc.myNum
    42.1
    >>> sc.myNum = 21.05 * 2  # raises error, because the value cannot change after it has been assigned.
    ImmutablePropertyError
    >>> sc.initialize(42.1)  # this works, because the values are the same.
    >>> sc.initialize(100)  # this fails, because the value cannot change
    ImmutablePropertyError
    """
    privateName = "_" + name

    def _getter(self):
        try:
            return getattr(self, privateName)
        except AttributeError:
            if getattr(self, "-unlocked", False):
                return None
            raise ImmutablePropertyError(
                "Attribute {} on {} has not been set, must read {} file first.".format(name, self, dependencyAction)
            )

    def _setter(self, value):
        if hasattr(self, privateName):
            currentVal = getattr(self, privateName)
            if currentVal is None or value is None:
                setattr(self, privateName, value if currentVal is None else currentVal)
            elif not numpyHackForEqual(currentVal, value):
                raise ImmutablePropertyError(
                    "{} on {} has already been set by reading {} file.\n"
                    "The original value:           ({})\n"
                    "does not match the new value: ({}).".format(name, self, dependencyAction, currentVal, value)
                )
        else:
            setattr(self, privateName, value)

    return property(_getter, _setter, doc=doc)


class ImmutablePropertyError(Exception):
    """Exception raised when performing an illegal operation on an immutable property."""


def unlockImmutableProperties(lib):
    """Unlock an object that has immutable properties for modification.

    This will prevent raising errors when reading or assigning values to an immutable property

    See Also
    --------
    armi.utils.properties.createImmutableProperty
    """
    setattr(lib, "-unlocked", True)


def lockImmutableProperties(lib):
    """Lock an object that has immutable properties such that accessing unassigned properties, or attempting
    to modify the properties raises an exception.

    See Also
    --------
    armi.utils.properties.createImmutableProperty
    """
    del lib.__dict__["-unlocked"]
