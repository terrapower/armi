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
This defines a Setting object and its subclasses that populate the Settings object.

This module is really only needed for its interactions with the submitter GUI.
"""
import os
import copy
import collections
import warnings

import armi
from armi.utils import parsing


class Setting(object):
    r"""Helper class to Settings

    Holds a factory to instantiate the correct sub-type based on the input dictionary with a few expected
    keywords. Setting objects hold all associated information of a setting in ARMI and should typically be accessed
    through the Settings class methods rather than directly. The exception being the SettingAdapter class designed
    for additional GUI related functionality

    """
    __slots__ = ["name", "description", "label", "underlyingType", "_value", "_default"]
    _allSlots = {}

    def __init__(self, name, underlyingType, attrib):
        r"""Initialization used in all subclass calls, some values are to be overwritten
         as they are either uniquely made or optional values.

        All set values should be run through the convertType(self.name,) function as Setting is
        so closely tied to python types being printed to strings and parsed back, convertType(self.name,)
        should cleanly fetch any python values.

        Parameters
        ----------
        name : str
            the setting's name
        underlyingType : type
            The setting's type
        attrib : dict
            the storage bin with the strictly named attributes of the setting

        Attributes
        ----------
        self.underlyingType : type
            explicity states the type of setting, usually a python type, but potentially something like 'file'
        self.value : select allowed python types
            the setting value stored
        self.default : always the same as value
            the backup value of self.value to regress to if desired
        self.description : str
            the helpful description of the purpose and use of a setting, primarily used for GUI tooltip strings
        self.label : str
            the shorter description used for the ARMI GUI

        """
        warnings.warn(
            "The old Setting class is being deprecated, and will "
            "be replaced with the new implementation presently in the setting2 "
            "module."
        )
        self.name = name
        self.description = str(attrib.get("description", ""))
        self.label = str(attrib.get("label", self.name))

        self.underlyingType = underlyingType
        self._value = None
        self._default = None

        self.setValue(attrib["default"])
        self._default = copy.deepcopy(self._value)

    @property
    def schema(self):
        return lambda val: val

    @property
    def default(self):
        return self._default

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self.setValue(v)

    @classmethod
    def _getSlots(cls):
        r"""This method is caches the slots for all subclasses so that they can quickly be retrieved during __getstate__
        and __setstate__."""
        slots = cls._allSlots.get(cls, None)
        if slots is None:
            slots = [
                slot
                for klass in cls.__mro__
                for slot in getattr(klass, "__slots__", [])
            ]
            cls._allSlots[cls] = slots
        return slots

    def __getstate__(self):
        """Get the state of the setting; required when __slots__ are defined"""
        return [
            getattr(self, slot) for slot in self.__class__._getSlots()
        ]  # pylint: disable=protected-access

    def __setstate__(self, state):
        """Set the state of the setting; required when __slots__ are defined"""
        for slot, value in zip(
            self.__class__._getSlots(), state
        ):  # pylint: disable=protected-access
            setattr(self, slot, value)

    def setValue(self, v):
        raise NotImplementedError

    def __repr__(self):
        return "<{} {} value:{} default:{}>".format(
            self.__class__.__name__, self.name, self.value, self.default
        )

    def revertToDefault(self):
        """
        Revert a setting back to its default.

        Notes
        -----
        Skips the property setter because default val
        should already be validated.
        """
        self._value = copy.deepcopy(self.default)

    def isDefault(self):
        """
        Returns a boolean based on whether or not the setting equals its default value

        It's possible for a setting to change and not be reported as such when it is changed back to its default.
        That behavior seems acceptable.
        """
        return self.value == self.default

    @property
    def offDefault(self):
        """Return True if the setting is not the default value for that setting."""
        return not self.isDefault()

    def getDefaultAttributes(self):
        """Returns values associated with the default initialization write out of settings

        Excludes the stored name of the setting

        """
        return collections.OrderedDict(
            [
                ("type", self.underlyingType),
                ("default", self.default),
                ("description", self.description),
                ("label", self.label),
            ]
        )

    def getCustomAttributes(self):
        """Returns values associated with a more terse write out of settings

        """
        return {"value": self.value}

    @staticmethod
    def factory(key, attrib):
        """
        The initialization method for the subclasses of Setting.
        """
        try:
            return SUBSETTING_MAP[attrib["type"]](key, attrib)
        except KeyError:
            raise TypeError(
                "Cannot create a setting for {0} around {1} "
                "as no subsetting exists to manage its declared type.".format(
                    key, attrib
                )
            )


class BoolSetting(Setting):
    """Setting surrounding a python boolean

    No new attributes have been added

    """

    __slots__ = []

    def __init__(self, name, attrib):
        Setting.__init__(self, name, bool, attrib)

    def setValue(self, v):
        """Protection against setting the value to an invalid/unexpected type

        """
        try:
            tenative_value = parsing.parseValue(v, bool, True)
        except ValueError:
            raise ValueError(
                "Cannot set {0} value to {1} as it is not a valid value for {2} "
                "and cannot be converted to one".format(
                    self.name, v, self.__class__.__name__
                )
            )

        self._value = tenative_value


class _NumericSetting(Setting):
    """Between Setting and the numeric subclasses, used for ints and floats

    Attributes
    ----------
    self.units : str
        OPTIONAL - a descriptor of the setting, not used internally
    self.min : int or float, as specified by the subclass initializing this
        OPTIONAL - used to enforce values higher than itself
    self.max : int or float, as specified by the sublcass initializing this
        OPTIONAL - used to enforce values lower than itself

    """

    __slots__ = ["units", "min", "max"]

    def __init__(self, name, underlyingType, attrib):
        self.units = str(attrib.get("units", ""))
        self.min = parsing.parseValue(
            attrib.get("min", None), underlyingType, True, False
        )
        self.max = parsing.parseValue(
            attrib.get("max", None), underlyingType, True, False
        )
        Setting.__init__(self, name, underlyingType, attrib)

    def getDefaultAttributes(self):
        """Adds in the new attributes to the default attribute grab of the base

        """
        attrib = Setting.getDefaultAttributes(self)
        attrib["units"] = self.units
        attrib["min"] = self.min
        attrib["max"] = self.max
        return attrib

    def setValue(self, v):
        """Protection against setting the value to an invalid/unexpected type

        """
        try:
            tenative_value = parsing.parseValue(v, self.underlyingType, True)
        except ValueError:
            raise ValueError(
                "Cannot set {0} value to {1} as it is not a valid value for {2} "
                "and cannot be converted to one".format(
                    self.name, v, self.__class__.__name__
                )
            )

        if self.min and tenative_value < self.min:
            raise ValueError(
                "Cannot set {0} value to {1} as it does not exceed the set minimum of {2}".format(
                    self.name, tenative_value, self.min
                )
            )
        elif self.max and tenative_value > self.max:
            raise ValueError(
                "Cannot set {0} value to {1} as it exceeds the set maximum of {2}".format(
                    self.name, tenative_value, self.max
                )
            )

        self._value = tenative_value


class IntSetting(_NumericSetting):
    """Setting surrounding a python integer"""

    __slots__ = []

    def __init__(self, name, attrib):
        _NumericSetting.__init__(self, name, int, attrib)


class FloatSetting(_NumericSetting):
    """Setting surrounding a python float"""

    __slots__ = []

    def __init__(self, name, attrib):
        _NumericSetting.__init__(self, name, float, attrib)


class StrSetting(Setting):
    """Setting surrounding a python string

    Attributes
    ----------
    self.options : list
        OPTIONAL - a list of strings that self.value is allowed to be set as
    self.enforcedOptions : bool
        OPTIONAL - toggles whether or not we care about self.options

    """

    __slots__ = ["options", "enforcedOptions"]

    def __init__(self, name, attrib):
        self.options = [
            item for item in parsing.parseValue(attrib.get("options", None), list, True)
        ]
        self.enforcedOptions = parsing.parseValue(
            attrib.get("enforcedOptions", None), bool, True
        )
        if self.enforcedOptions and not self.options:
            raise AttributeError(
                "Cannot use enforcedOptions in ({}) {} without supplying options.".format(
                    self.__class__.__name__, self.name
                )
            )
        Setting.__init__(self, name, str, attrib)

    def setValue(self, v):
        """Protection against setting the value to an invalid/unexpected type

        """
        if (
            v is None
        ):  # done for consistency with the rest of the methods using parsing module
            tenative_value = None
        else:
            tenative_value = str(v)

        if self.options and self.enforcedOptions and tenative_value not in self.options:
            raise ValueError(
                "Cannot set {0} value to {1} as it isn't in the allowed options "
                "{2}".format(self.name, tenative_value, self.options)
            )

        self._value = tenative_value

    def getDefaultAttributes(self):
        """Adds in the new attributes to the default attribute grab of the base

        """
        attrib = Setting.getDefaultAttributes(self)
        attrib["options"] = self.options
        attrib["enforcedOptions"] = self.enforcedOptions
        return attrib


class PathSetting(StrSetting):
    """Setting surrounding a python string file path

    Allows for paths relative to various dynamic ARMI environment variables"""

    __slots__ = ["relativeTo", "mustExist"]

    _REMAPS = {
        "RES": armi.context.RES,
        "ROOT": armi.context.ROOT,
        "DOC": armi.context.DOC,
        "FAST_PATH": armi.context.FAST_PATH,
    }

    def __init__(self, name, attrib):
        self.relativeTo = attrib.get("relativeTo", None)
        self.mustExist = parsing.parseValue(attrib.get("mustExist", None), bool, True)
        StrSetting.__init__(self, name, attrib)

    def setValue(self, v):
        """Protection against setting the value to an invalid/unexpected type

        """
        if v is not None:
            if self.relativeTo is not None:
                # Use relative path if the provided path does not exist
                if not os.path.exists(v):
                    v = os.path.join(self._REMAPS[self.relativeTo], v)
            if self.mustExist and not os.path.exists(v):
                raise ValueError(
                    "Cannot set {0} value to {1} as it doesn't exist".format(
                        self.name, v
                    )
                )
        StrSetting.setValue(self, v)

    def getDefaultAttributes(self):
        """Adds in the new attributes to the default attribute grab of the base

        """
        attrib = Setting.getDefaultAttributes(self)
        attrib["relativeTo"] = self.relativeTo
        attrib["mustExist"] = self.mustExist
        return attrib


class ListSetting(Setting):
    """Setting surrounding a python list

    Attributes
    ----------
    self.containedType : any python type
        OPTIONAL - used to ensure all items in the list conform to this specified type,
        if omitted the list is free to hold anything

    """

    __slots__ = ["containedType", "options", "enforcedOptions"]

    def __init__(self, name, attrib):
        self.containedType = parsing.parseType(attrib.get("containedType", None), True)
        self.options = [
            item for item in parsing.parseValue(attrib.get("options", None), list, True)
        ]
        self.enforcedOptions = parsing.parseValue(
            attrib.get("enforcedOptions", None), bool, True
        )

        if self.enforcedOptions and not self.options:
            raise AttributeError(
                "Cannot use enforcedOptions in ({}) {} without supplying options.".format(
                    self.__class__.__name__, self.name
                )
            )

        if self.containedType and self.containedType == type(None):
            raise RuntimeError(
                "Do not use NoneType for containedType in ListSetting. "
                "That does seem helpful and it will cause pickling issues."
            )
        Setting.__init__(self, name, list, attrib)
        self._default = tuple(
            self.default or []
        )  # convert mutable list to tuple so no one changes it after def.

    @property
    def value(self):
        return list(self._value)

    @property
    def default(self):
        return list(self._default or [])

    def setValue(self, v):
        """Protection against setting the value to an invalid/unexpected type

        """
        try:
            tentative_value = parsing.parseValue(v, list, True)
        except ValueError:
            raise ValueError(
                "Cannot set {0} value to {1} as it is not a valid value for {2} "
                "and cannot be converted to one".format(
                    self.name, v, self.__class__.__name__
                )
            )

        if self.containedType and tentative_value:
            ct = self.containedType
            try:
                if ct == str:
                    tentative_value = [str(i) for i in tentative_value]
                else:
                    tentative_value = [
                        parsing.parseValue(i, ct, False) for i in tentative_value
                    ]
            except ValueError:
                raise ValueError(
                    "Cannot set {0} value to {1} as it contains items not of the correct type {2}".format(
                        self.name, tentative_value, self.containedType
                    )
                )

        if (
            self.options
            and self.enforcedOptions
            and any([value not in self.options for value in tentative_value])
        ):
            raise ValueError(
                "Cannot set {0} value to {1} as it isn't in the allowed options {2}".format(
                    self.name, tentative_value, self.options
                )
            )

        self._value = tuple(tentative_value or [])

    def getDefaultAttributes(self):
        """Adds in the new attributes to the default attribute grab of the base

        """
        attrib = Setting.getDefaultAttributes(self)
        attrib["containedType"] = self.containedType
        attrib["options"] = self.options
        attrib["enforcedOptions"] = self.enforcedOptions
        return attrib


# help direct python types to the respective setting type
SUBSETTING_MAP = {
    "bool": BoolSetting,
    "int": IntSetting,
    "long": IntSetting,
    "float": FloatSetting,
    "str": StrSetting,
    "list": ListSetting,
    "path": PathSetting,
}
