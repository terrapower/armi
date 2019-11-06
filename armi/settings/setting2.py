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
System to handle basic configuration settings.

Notes
-----
This is a re-implementation of setting.py that requires setting objects
be instantiated in code via plugin hooks, or by the framework, rather
than by XML files.

Rather than having subclases for each setting type, we simply derive
the type based on the type of the default, and we enforce it with
schema validation. This also allows for more complex schema validation
for settings that are more complex dictionaries (e.g. XS, rx coeffs, etc.).

One reason for complexity of the previous settings implementation was
good interoperability with the GUI widgets.

We originally thought putting settings definitions in XML files would
help with future internationalization. This is not the case.
Internationalization will likely be added later with string interpolators given
the desire to internationalize, which is nicely compatible with this
code-based re-implementation.
"""

import copy
from collections import namedtuple
from typing import List

import voluptuous as vol

from armi import runLog


# Options are used to imbue existing settings with new Options. This allows a setting
# like `neutronicsKernel` to strictly enforce options, even though the plugin that
# defines it does not know all possible options, which may be provided from other
# plugins.
Option = namedtuple("Option", ["option", "settingName"])
Default = namedtuple("Default", ["value", "settingName"])


class Setting:
    """
    A particular setting.

    Setting objects hold all associated information of a setting in ARMI and should
    typically be accessed through the Settings class methods rather than directly. The
    exception being the SettingAdapter class designed for additional GUI related
    functionality.

    Setting subclasses can implement custom ``load`` and ``dump`` methods
    that can enable serialization (to/from dicts) of custom objects. When
    you set a setting's value, the value will be unserialized into
    the custom object and when you call ``dump``, it will be serialized.
    Just accessing the value will return the actual object in this case.

    """

    def __init__(
        self,
        name,
        default,
        description=None,
        label=None,
        options=None,
        schema=None,
        enforcedOptions=False,
        subLabels=None,
        isEnvironment=False,
    ):
        """
        Initialize a Setting object.

        Parameters
        ----------
        name : str
            the setting's name
        default : object
            The setting's default value
        description : str, optional
            The description of the setting
        label : str, optional
            the shorter description used for the ARMI GUI
        options : list, optional
            Legal values (useful in GUI drop-downs)
        schema : callable, optional
            A function that gets called with the configuration
            VALUES that build this setting. The callable will
            either raise an exception, safely modify/update,
            or leave unchanged the value. If left blank,
            a type check will be performed against the default.
        enforcedOptions : bool, optional
            Require that the value be one of the valid options.
        subLabels : tuple, optional
            The names of the fields in each tuple for a setting that accepts a list
            of tuples. For example, if a setting is a list of (assembly name, file name)
            tuples, the sublabels would be ("assembly name", "file name").
            This is needed for building GUI widgets to input such data.
        isEnvironment : bool, optional
            Whether this should be considered an "environment" setting. These can be
            used by the Case system to propagate environment options through
            command-line flags.

        """
        self.name = name
        self.description = description or name
        self.label = label or name
        self.options = options
        self.enforcedOptions = enforcedOptions
        self.subLabels = subLabels
        self.isEnvironment = isEnvironment

        self._default = default
        # Retain the passed schema so that we don't accidentally stomp on it in
        # addOptions(), et.al.
        self._customSchema = schema
        self._setSchema(schema)
        self._value = copy.deepcopy(default)  # break link from _default

    @property
    def underlyingType(self):
        """Useful in categorizing settings, e.g. for GUI."""
        return type(self._default)

    @property
    def containedType(self):
        """The subtype for lists."""
        # assume schema set to [int] or [str] or something similar
        try:
            containedSchema = self.schema.schema[0]
            if isinstance(containedSchema, vol.Coerce):
                # special case for Coerce objects, which
                # store their underlying type as ``.type``.
                return containedSchema.type
            return containedSchema
        except TypeError:
            # cannot infer. fall back to str
            return str

    def _setSchema(self, schema):
        """Apply or auto-derive schema of the value."""
        if schema:
            self.schema = schema
        elif self.options and self.enforcedOptions:
            self.schema = vol.Schema(vol.In(self.options))
        else:
            # Coercion is needed to convert XML-read migrations (for old cases)
            # as well as in some GUI instances where lists are getting set
            # as strings.
            if isinstance(self.default, list) and self.default:
                # Non-empty default: assume the default has the desired contained type
                # Coerce all values to the first entry in the default so mixed floats and ints work.
                # Note that this will not work for settings that allow mixed
                # types in their lists (e.g. [0, '10R']), so those all need custom schemas.
                self.schema = vol.Schema([vol.Coerce(type(self.default[0]))])
            else:
                self.schema = vol.Schema(vol.Coerce(type(self.default)))

    @property
    def default(self):
        return self._default

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        """
        Set the value directly.

        Notes
        -----
        Can't just decorate ``setValue`` with ``@value.setter`` because
        some callers use setting.value=val and others use setting.setValue(val)
        and the latter fails with ``TypeError: 'XSSettings' object is not callable``
        """
        return self.setValue(val)

    def setValue(self, val):
        """
        Set value of a setting.

        This validates it against its value schema on the way in.

        Some setting values are custom serializable objects.
        Rather than writing them directly to YAML using
        YAML's Python object-writing features, we prefer
        to use our own custom serializers on subclasses.
        """
        try:
            val = self.schema(val)
        except vol.error.MultipleInvalid:
            runLog.error(f"Error in setting {self.name}, val: {val}.")
            raise

        self._value = self._load(val)

    def addOptions(self, options: List[Option]):
        """Extend this Setting's options with extra options."""
        self.options.extend([o.option for o in options])
        self._setSchema(self._customSchema)

    def addOption(self, option: Option):
        """Extend this Setting's options with an extra option."""
        self.addOptions(
            [option,]
        )

    def changeDefault(self, newDefault: Default):
        """Change the default of a setting, and also the current value."""
        self._default = newDefault.value
        self.value = newDefault.value

    def _load(self, inputVal):
        """
        Create setting value from input value.

        In some custom settings, this can return a custom object
        rather than just the input value.
        """
        return inputVal

    def dump(self):
        """
        Return a serializable version of this setting's value.

        Override to define custom deserializers for custom/compund settings.
        """
        return self._value

    def __repr__(self):
        return "<{} {} value:{} default:{}>".format(
            self.__class__.__name__, self.name, self.value, self.default
        )

    def __getstate__(self):
        """
        Remove schema during pickling because it is often unpickleable.

        Notes
        -----
        Errors are often with
        ``AttributeError: Can't pickle local object '_compile_scalar.<locals>.validate_instance'``

        See Also
        --------
        armi.settings.caseSettings.Settings.__setstate__ : regenerates the schema upon load
            Note that we don't do it at the individual setting level because it'd be too
            O(N^2).
        """
        state = copy.deepcopy(self.__dict__)
        for trouble in ("schema", "_customSchema"):
            if trouble in state:
                del state[trouble]
        return state

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

    def getCustomAttributes(self):
        """Hack to work with settings writing system until old one is gone."""
        return {"value": self.value}

    def getDefaultAttributes(self):
        """
        Additional hack, residual from when settings system could write settings definitions.

        This is only needed here due to the unit tests in test_settings."""
        return {
            "value": self.value,
            "type": type(self.default),
            "default": self.default,
        }
