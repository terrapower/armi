# Copyright 2026 TerraPower, LLC
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

"""Map YAML documents onto typed Python objects, without losing the document.

This is ARMI's replacement for the unmaintained ``yamlize`` package. It covers the same ground --
declare a class with typed, keyed, defaulted attributes and load/dump it -- with one structural
difference that matters a great deal for round tripping.

yamlize parses YAML into its own objects, throws the parsed document away, and then tries to
reconstruct the original formatting at dump time from a cache of node metadata. That cache is keyed
on the *values*, so values that compare equal share an entry and end up wearing each other's YAML
tags and comments. It is the source of a long tail of corruption bugs; see
:py:mod:`armi.reactor.blueprints._yamlizeShims`.

Here the parsed document *is* the round-trip record. ``ruamel.yaml`` already preserves comments,
anchors, aliases, merge keys, quote and flow styles, and literal block scalars in the
``CommentedMap``/``CommentedSeq`` it hands back. So a load keeps that structure attached to the
object it produced, and a dump starts from it and writes back only the fields that actually
changed. The content of anything untouched comes back exactly as it went in, because it was never
taken apart.

Indentation is the one thing deliberately not preserved. ruamel.yaml sets it globally at dump time,
so reproducing a source file would mean guessing its conventions, and hand-written blueprints are
not consistent enough for a guess to be right -- some mix two- and four-space mappings within one
file. Every document is instead written in one house style, so ARMI's output is uniform and input
files converge on a single layout rather than preserving each file's accidents forever.

Typical use::

    class Pitch(YamlObject):
        x = Field(type=float, default=0.0)
        y = Field(type=float, default=0.0)


    class Grid(YamlObject):
        name = Field(type=str)
        geom = Field(type=str, default="hex")
        pitch = Field(key="lattice pitch", type=Pitch, default=None)


    class Grids(KeyedList):
        itemType = Grid
        keyField = Grid.name


    grids = Grids.load(stream)
    grids["core"].geom = "cartesian"
    Grids.dump(grids, outStream)  # comments, anchors and styles all still there
"""

import io

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import LiteralScalarString, ScalarString

# ARMI writes every YAML file it produces in one house style, and normalizes input to it on the way
# back out. ruamel.yaml applies indentation globally at dump time, so matching a source file
# exactly would mean guessing its conventions, and hand-written blueprints are not internally
# consistent enough for a guess to be right. Normalizing is simpler, and it leaves the repository's
# input files converging on one layout instead of preserving each file's accidents forever.
#
# These are ruamel.yaml's own round-trip defaults, which is what ARMI's settings writer already
# emits, so this changes neither ARMI's existing output nor the meaning of anyone's input.

#: Spaces a nested mapping is indented under its key.
MAPPING_INDENT = 2

#: Column, relative to the parent key, where a block sequence item's content starts.
SEQUENCE_INDENT = 4

#: Column, relative to the parent key, where a block sequence item's ``-`` goes.
SEQUENCE_OFFSET = 2

#: Line length the emitter targets before wrapping a flow sequence. Matches the line length ARMI's
#: own source uses. ruamel.yaml's default of 80 is short enough to wrap the rows of block names and
#: material modifications that blueprints are full of, which are far easier to read on one line.
WIDTH = 120


class NODEFAULT:
    """Sentinel for a :py:class:`Field` with no default, i.e. a required one."""

    def __new__(cls):
        raise NotImplementedError("NODEFAULT is a sentinel and cannot be instantiated")


class YamlSchemaError(ValueError):
    """Raised when a document does not match the schema it is being read into."""

    def __init__(self, message, location=None):
        self.location = location
        if location is not None:
            message = "{}\n  at {}".format(message, location)

        super().__init__(message)


def _yaml():
    """A round-trip YAML handler, set up to read and write ARMI's house style."""
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = WIDTH
    yaml.indent(mapping=MAPPING_INDENT, sequence=SEQUENCE_INDENT, offset=SEQUENCE_OFFSET)

    return yaml


def _preserveAnchors(data, seen=None):
    """Mark every anchor in a freshly loaded document so it survives a dump.

    ruamel.yaml only re-emits an anchor that something actually aliases. Blueprints routinely
    define anchors nothing references yet -- they exist so users can alias them from their own
    files -- so letting ruamel.yaml drop them would silently edit the input.
    """
    if seen is None:
        seen = set()

    if id(data) in seen:
        return

    seen.add(id(data))

    anchor = getattr(data, "yaml_anchor", None)
    if anchor is not None:
        existing = data.yaml_anchor()
        if existing is not None and existing.value:
            data.yaml_set_anchor(existing.value, always_dump=True)

    if isinstance(data, dict):
        for value in data.values():
            _preserveAnchors(value, seen)
    elif isinstance(data, (list, tuple)):
        for value in data:
            _preserveAnchors(value, seen)


def _load(stream):
    """Parse a stream, string or open file into ruamel.yaml round-trip data."""
    if isinstance(stream, str):
        stream = io.StringIO(stream)

    data = _yaml().load(stream)
    _preserveAnchors(data)

    return data


def _location(data, key=None):
    """Describe where a piece of loaded data came from, for error messages.

    ruamel.yaml records line/column on ``CommentedMap`` and ``CommentedSeq``, so we can usually
    point the user at the offending line even though we are working with data rather than nodes.
    """
    if key is not None and isinstance(data, CommentedMap):
        try:
            mark = data.lc.key(key)
            return "line {}, column {}".format(mark[0] + 1, mark[1] + 1)
        except (AttributeError, KeyError, TypeError):
            pass

    try:
        return "line {}, column {}".format(data.lc.line + 1, data.lc.col + 1)
    except AttributeError:
        return None


class Field:
    """One attribute of a :py:class:`YamlObject`, and one key/value pair in YAML.

    Parameters
    ----------
    name : str
        Attribute name on the Python class. Filled in automatically from the class body.
    key : str
        Key in the YAML document. Defaults to ``name``, which is why keys with spaces in them --
        ``axial mesh points`` -- have to be given explicitly.
    type : type
        Type the value is coerced to. A :py:class:`YamlObject` subclass nests; a plain type like
        ``float`` is coerced and checked. Left out, the value passes through as whatever YAML said
        it was.
    default : object
        Value to use when the key is absent. Left out, the key is required.
    validator : callable
        Called as ``validator(obj, value)`` on assignment. Returning ``False`` rejects the value;
        raising gives a better message. Usually applied with the :py:meth:`validator` decorator.
    doc : str
        Human-readable description, for generated documentation.
    """

    __slots__ = ("name", "key", "type", "default", "validatorFunc", "doc", "storageName")

    def __init__(self, name=None, key=None, type=NODEFAULT, default=NODEFAULT, validator=None, doc=None):
        self.name = None
        self.storageName = None
        self.key = key
        self.type = None if type is NODEFAULT else type
        self.default = default
        self.validatorFunc = validator
        self.doc = doc

        if name is not None:
            self._setName(name)

    def _setName(self, name):
        """Adopt the attribute name, which also supplies the YAML key if none was given."""
        self.name = name
        self.storageName = "_yamlField_" + name
        if self.key is None:
            self.key = name

    def __repr__(self):
        return "<Field {} (key={!r})>".format(self.name, self.key)

    @property
    def isRequired(self):
        return self.default is NODEFAULT

    def isUnset(self, obj):
        """True if this field has never been assigned on ``obj``, so a dump should skip it."""
        return not hasattr(obj, self.storageName)

    def validator(self, func):
        """Attach a validator, as a decorator.

        Returns a new :py:class:`Field` rather than mutating this one, matching how ``yamlize``
        behaved: the decorated name rebinds the class attribute.
        """
        return type(self)(self.name, self.key, self.type or NODEFAULT, self.default, func, self.doc)

    def coerce(self, value, location=None):
        """Convert ``value`` to this field's type, refusing conversions that change it.

        A coercion that changes the value is a sign the input meant something else -- ``int("3.5")``
        or ``float(None)`` -- so it is an error rather than a silent reinterpretation. The default
        value is exempt, since ``default=None`` on a typed field is a normal way to say "optional".
        """
        if self.type is None or value is None or isinstance(value, self.type):
            return value

        if self.default is not NODEFAULT and value == self.default:
            return value

        try:
            converted = self.type(value)
        except Exception as ee:
            raise YamlSchemaError(
                "Cannot read `{}` as the {} that `{}` requires: {}".format(value, self.type.__name__, self.key, ee),
                location,
            )

        if converted != value:
            raise YamlSchemaError(
                "Reading `{}` as the {} that `{}` requires would change it to `{}`".format(
                    value, self.type.__name__, self.key, converted
                ),
                location,
            )

        return converted

    def __get__(self, obj, owner=None):
        if obj is None:
            return self

        value = getattr(obj, self.storageName, self.default)
        if value is NODEFAULT:
            raise AttributeError("`{}` was never set on {}".format(self.name, obj))

        return value

    def __set__(self, obj, value):
        value = self.coerce(value)

        if self.validatorFunc is not None and self.validatorFunc(obj, value) is False:
            raise ValueError("`{}` is not a valid {}.{}".format(value, type(obj).__name__, self.name))

        setattr(obj, self.storageName, value)

    def __delete__(self, obj):
        if not self.isUnset(obj):
            delattr(obj, self.storageName)


class FieldCollection:
    """The fields of one :py:class:`YamlObject` subclass, in declaration order."""

    __slots__ = ("order", "byKey", "byName")

    def __init__(self, fields=()):
        self.order = []
        self.byKey = {}
        self.byName = {}
        for field in fields:
            self.add(field)

    def __iter__(self):
        return iter(self.order)

    def __len__(self):
        return len(self.order)

    def add(self, field):
        existing = self.byKey.get(field.key)
        if existing is not None and existing is not field:
            raise KeyError("Two fields claim the YAML key `{}`: {} and {}".format(field.key, existing, field))

        if existing is field:
            return

        # a subclass may override an inherited field; the override replaces it in place
        previous = self.byName.get(field.name)
        if previous is not None:
            self.order[self.order.index(previous)] = field
            del self.byKey[previous.key]
        else:
            self.order.append(field)

        self.byKey[field.key] = field
        self.byName[field.name] = field

    def copy(self):
        new = FieldCollection()
        new.order = list(self.order)
        new.byKey = dict(self.byKey)
        new.byName = dict(self.byName)

        return new


class _SchemaMeta(type):
    """Collects :py:class:`Field` declarations off the class body, including inherited ones."""

    def __init__(cls, name, bases, namespace):
        type.__init__(cls, name, bases, namespace)

        fields = FieldCollection()
        for base in reversed(cls.__mro__[1:]):
            for field in getattr(base, "_fields", ()):
                fields.add(field)

        for attrName, value in namespace.items():
            if not isinstance(value, Field):
                continue

            if value.name is None:
                # declared right here, so the attribute name is its name
                value._setName(attrName)
            elif value.name != attrName:
                # A field belonging to some *other* class, bound here under a different attribute
                # name. ``keyField = Component.name`` is the standard case: it points at the field
                # of the item type that the mapping key fills in, and is not a field of this class.
                continue

            fields.add(value)

        cls._fields = fields

        keyField = None
        for klass in cls.__mro__:
            candidate = klass.__dict__.get("keyField")
            if isinstance(candidate, Field):
                keyField = candidate
                break

        # bypass our own __setattr__, which would try to register this as a field
        type.__setattr__(cls, "_keyFieldRef", keyField)

    def __setattr__(cls, attrName, value):
        """Register fields bolted on after class creation.

        ARMI does this in a few places: component dimensions and plugin-defined parameters are
        discovered at import time and attached to the blueprint classes then.
        """
        type.__setattr__(cls, attrName, value)
        if isinstance(value, Field) and not attrName.startswith("_") and attrName != "keyField":
            if value.name is None:
                value._setName(attrName)
            cls._fields.add(value)


class YamlObject(metaclass=_SchemaMeta):
    r"""A Python object that maps onto a YAML mapping.

    Subclasses declare :py:class:`Field`\ s as class attributes. Instances hold the loaded values
    and, when they came from a document, the ``CommentedMap`` they were read out of.
    """

    _fields = FieldCollection()

    #: the ``CommentedMap`` this object was loaded from, or None if it was built in code
    _doc = None

    #: when this object is an entry of a :py:class:`KeyedList`, the field its key supplies. That
    #: field is read from the key and is not written back into the value, so it does not appear
    #: twice in the document.
    _keyField = None

    @classmethod
    def _getKeyField(cls):
        """The item field that an enclosing :py:class:`KeyedList` fills in from the mapping key.

        Read out of ``__dict__`` on purpose. A :py:class:`Field` is a data descriptor, so ordinary
        attribute access invokes it instead of handing it back.
        """
        return cls.__dict__.get("_keyFieldRef")

    @classmethod
    def load(cls, stream):
        """Read an instance from a YAML stream, string, or open file."""
        return cls.fromData(_load(stream))

    @classmethod
    def dump(cls, obj, stream=None):
        """Write ``obj`` as YAML. Returns the text when no stream is given."""
        toString = stream is None
        stream = stream or io.StringIO()
        _yaml().dump(obj.toData(), stream)

        return stream.getvalue() if toString else None

    @classmethod
    def fromData(cls, data, key=None, keyField=None):
        """Build an instance from already-parsed ruamel.yaml data.

        ``key`` and ``keyField`` are supplied when this object is an entry of a
        :py:class:`KeyedList`: the mapping key it sat under, and the field that key fills in.
        """
        if not isinstance(data, dict):
            raise YamlSchemaError(
                "Expected a mapping to read a {} from, got {}".format(cls.__name__, type(data).__name__),
                _location(data),
            )

        self = cls.__new__(cls)
        self._doc = data
        self._keyField = keyField
        self._readFields(data, key)

        return self

    def _readFields(self, data, key=None):
        """Populate fields from ``data``, then check that nothing required is missing."""
        keyField = self._keyField
        if keyField is not None and key is not None:
            keyField.__set__(self, key)

        for docKey, value in data.items():
            field = self._fields.byKey.get(docKey)
            if field is None:
                self._readExtraKey(data, docKey, value)
                continue

            field.__set__(self, _readValue(field.type, value, _location(data, docKey)))

        missing = [f.key for f in self._fields if f.isRequired and f.isUnset(self) and f is not keyField]
        if missing:
            raise YamlSchemaError(
                "{} is missing required {}: {}".format(
                    type(self).__name__, "key" if len(missing) == 1 else "keys", ", ".join(sorted(missing))
                ),
                _location(data),
            )

    def _readExtraKey(self, data, docKey, value):
        """Handle a key with no matching field. Mappings and keyed lists override this."""
        raise YamlSchemaError(
            "`{}` is not a recognized key for {}. Expected one of: {}".format(
                docKey, type(self).__name__, ", ".join(sorted(self._fields.byKey))
            ),
            _location(data, docKey),
        )

    def toData(self):
        """Render back to ruamel.yaml data, reusing the source document where it is unchanged.

        Reusing the document this object was loaded from is what preserves comments, anchors and
        styles: untouched keys are never rebuilt, so there is nothing to reconstruct and nothing to
        get wrong.

        The document is updated in place rather than copied. An alias is *the same node* as its
        anchor, and a merge key is a reference to another node; copying would turn both into
        independent mappings and the emitter would write the content out longhand instead of
        writing ``*anchor`` and ``<<:``. Updating in place is also idempotent, since afterwards the
        document already says what the fields say.
        """
        doc = self._doc if self._doc is not None else CommentedMap()
        self._writeFields(doc)

        return doc

    def _writeFields(self, doc):
        keyField = self._keyField
        for field in self._fields:
            if field is keyField or field.isUnset(self):
                continue

            value = field.__get__(self)
            if value is None and field.default is None and field.key not in doc:
                # an optional field that was never in the document and still holds its default
                continue

            _writeInto(doc, field.key, value)

        for field in self._fields:
            if field.isUnset(self) and field.key in doc and field is not keyField:
                del doc[field.key]


def _readValue(fieldType, value, location=None):
    """Turn one parsed YAML value into whatever the field's type calls for."""
    if fieldType is not None and isinstance(fieldType, type) and issubclass(fieldType, (YamlObject, Sequence)):
        return fieldType.fromData(value)

    return value


def _writeValue(value):
    """Turn one Python value back into something ruamel.yaml can emit."""
    if isinstance(value, (YamlObject, Sequence)):
        return value.toData()

    return _asBlockScalar(value)


def _asBlockScalar(value):
    r"""Mark a multi-line string to be written as a literal block scalar (``|``).

    In a blueprint a multi-line string is a picture: a lattice map, a pin map, a core map. Its line
    breaks and column alignment *are* the data, and people read and edit them in a text editor.

    ruamel.yaml will only write a plain ``str`` as a block scalar if something tells it to.
    Otherwise it picks a quoted style, escapes the newlines and folds the result at the emitter
    width, which turns a legible map into an unreadable one::

        lattice map: "P00  P01 ... P21\n    \  P22  P23 ...

    Strings read from a ``|`` block already come back as ``LiteralScalarString`` and keep their
    style on their own. This covers the other way in: a map assigned from code, where expecting
    every caller to remember to wrap it is a trap that only shows up in the written file.
    """
    if isinstance(value, str) and not isinstance(value, ScalarString) and "\n" in value:
        return LiteralScalarString(value)

    return value


def _writeInto(doc, key, value):
    """Put ``value`` under ``key`` in ``doc``, without disturbing it if it is already there.

    Leaving an unchanged entry alone is the whole point: the moment we reassign it, we replace the
    node ruamel.yaml parsed -- along with its quote style, tag, anchor and comments -- with a bare
    Python value. Nested objects still get rendered, because they update their own slice of the
    document in place and hand back the very node that is already sitting there.
    """
    if isinstance(value, (YamlObject, Sequence)):
        rendered = value.toData()
        if doc.get(key, None) is not rendered:
            doc[key] = rendered
        return

    value = _asBlockScalar(value)
    if key in doc and _sameScalar(doc[key], value):
        return

    doc[key] = value


def _sameScalar(docValue, value):
    """True if the document already says exactly ``value``.

    Compared by type as well as equality, because ``0``, ``0.0``, ``False`` and ``""`` are all
    equal to one another in Python but mean different things in YAML. Conflating them is precisely
    the yamlize defect this module exists to avoid.
    """
    if type(docValue) is not type(value):
        return False

    return docValue == value


class Sequence:
    """A YAML sequence whose items are all of one type.

    Behaves like a list. Like :py:class:`YamlObject`, it hangs on to the ``CommentedSeq`` it was
    read from so that a dump can reuse it.
    """

    #: type each item is coerced to; ``None`` lets items through as YAML parsed them
    itemType = None

    def __init__(self, items=()):
        self._doc = None
        self._items = []
        self.extend(items)

    @classmethod
    def load(cls, stream):
        return cls.fromData(_load(stream))

    @classmethod
    def dump(cls, obj, stream=None):
        toString = stream is None
        stream = stream or io.StringIO()
        _yaml().dump(obj.toData(), stream)

        return stream.getvalue() if toString else None

    @classmethod
    def fromData(cls, data):
        if not isinstance(data, (list, tuple)):
            raise YamlSchemaError(
                "Expected a list to read a {} from, got {}".format(cls.__name__, type(data).__name__),
                _location(data),
            )

        self = cls()
        self._doc = data
        self.extend(data)

        return self

    def toData(self):
        if self._doc is not None and len(self._doc) == len(self._items):
            if all(_sameItem(d, i) for d, i in zip(self._doc, self._items)):
                # nothing changed; hand back the original, styles and comments intact
                return self._doc

        out = CommentedSeq([_writeValue(item) for item in self._items])
        if self._doc is not None:
            # keep flow vs block style even though the contents changed
            out.fa.set_flow_style() if self._doc.fa.flow_style() else out.fa.set_block_style()

        return out

    def _coerce(self, item):
        if self.itemType is None or item is None or isinstance(item, self.itemType):
            return item

        if isinstance(self.itemType, type) and issubclass(self.itemType, (YamlObject, Sequence)):
            return self.itemType.fromData(item)

        try:
            converted = self.itemType(item)
        except Exception as ee:
            raise YamlSchemaError(
                "Cannot read `{}` as the {} that {} holds: {}".format(
                    item, self.itemType.__name__, type(self).__name__, ee
                ),
                _location(item),
            )

        if converted != item:
            raise YamlSchemaError(
                "Reading `{}` as the {} that {} holds would change it to `{}`".format(
                    item, self.itemType.__name__, type(self).__name__, converted
                ),
                _location(item),
            )

        return converted

    def append(self, item):
        self._items.append(self._coerce(item))

    def extend(self, items):
        for item in items:
            self.append(item)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]

    def __setitem__(self, index, value):
        self._items[index] = self._coerce(value)

    def __delitem__(self, index):
        del self._items[index]

    def __eq__(self, other):
        if isinstance(other, Sequence):
            other = list(other)
        if not isinstance(other, (list, tuple)):
            return NotImplemented

        return self._items == list(other)

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self._items)


class StrList(Sequence):
    """A sequence of strings."""

    itemType = str


class IntList(Sequence):
    """A sequence of ints."""

    itemType = int


class FloatList(Sequence):
    """A sequence of floats."""

    itemType = float


class _MappingBase(YamlObject):
    """Shared plumbing for the two mapping flavors, which both mix fields with free-form keys."""

    def __init__(self, *args, **kwargs):
        self._doc = None
        self._data = dict(*args, **kwargs)

    @classmethod
    def fromData(cls, data, key=None, keyField=None):
        if not isinstance(data, dict):
            raise YamlSchemaError(
                "Expected a mapping to read a {} from, got {}".format(cls.__name__, type(data).__name__),
                _location(data),
            )

        self = cls.__new__(cls)
        self._doc = data
        self._keyField = keyField
        self._data = {}
        self._readFields(data, key)

        return self

    def toData(self):
        doc = self._doc if self._doc is not None else CommentedMap()
        self._writeFields(doc)
        self._writeItems(doc)

        return doc

    def _writeItems(self, doc):
        raise NotImplementedError

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data

    def __getitem__(self, key):
        return self._data[key]

    def __delitem__(self, key):
        del self._data[key]

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self._data)


class Map(_MappingBase):
    """A YAML mapping of typed keys to typed values, optionally with fixed fields mixed in.

    Any key that matches a declared :py:class:`Field` is read into that field; everything else
    becomes a dictionary entry. That is how a blueprint section can carry both known settings and
    an open-ended set of user-chosen names.
    """

    keyType = None
    valueType = None

    def _readExtraKey(self, data, docKey, value):
        self._data[_coerceTo(self.keyType, docKey, _location(data, docKey))] = _readValue(
            self.valueType, value, _location(data, docKey)
        )

    def _writeItems(self, doc):
        for key, value in self._data.items():
            _writeInto(doc, key, value)

        for key in [k for k in doc if k not in self._data and k not in self._fields.byKey]:
            del doc[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __iter__(self):
        """Iterate keys, the way a dict does."""
        return iter(self._data)


class KeyedList(_MappingBase):
    """A YAML mapping whose keys are really an attribute of the values.

    ``blocks:`` in a blueprint is the canonical example: each key names a block, and that name is
    also the block's ``name`` field. Unlike a :py:class:`Map`, iterating gives the *values*, since
    the keys are already carried by them.
    """

    #: the :py:class:`YamlObject` subclass each entry is read into
    itemType = None

    #: the field of ``itemType`` that the mapping key supplies
    keyField = None

    def _readExtraKey(self, data, docKey, value):
        self._data[docKey] = self.itemType.fromData(value, key=docKey, keyField=type(self)._getKeyField())

    def _writeItems(self, doc):
        for key, value in self._data.items():
            _writeInto(doc, key, value)

        for key in [k for k in doc if k not in self._data and k not in self._fields.byKey]:
            del doc[key]

    def __setitem__(self, key, value):
        actual = type(self)._getKeyField().__get__(value)
        if actual != key:
            raise KeyError(
                "Cannot file a {} named `{}` under the key `{}`; the two have to match.".format(
                    type(value).__name__, actual, key
                )
            )

        value._keyField = type(self)._getKeyField()
        self._data[key] = value

    def add(self, item):
        """Insert ``item`` under whatever its key field says its name is."""
        self[type(self)._getKeyField().__get__(item)] = item

    def __iter__(self):
        """Iterate values, not keys: the keys are already an attribute of each value."""
        return iter(self._data.values())


def _coerceTo(type_, value, location=None):
    """Coerce a bare value to ``type_``, refusing conversions that change it."""
    if type_ is None or value is None or isinstance(value, type_):
        return value

    try:
        converted = type_(value)
    except Exception as ee:
        raise YamlSchemaError("Cannot read `{}` as a {}: {}".format(value, type_.__name__, ee), location)

    if converted != value:
        raise YamlSchemaError(
            "Reading `{}` as a {} would change it to `{}`".format(value, type_.__name__, converted), location
        )

    return converted


def _sameItem(docItem, item):
    """True if a sequence slot already holds ``item``, so the sequence need not be rebuilt."""
    if isinstance(item, (YamlObject, Sequence)):
        return docItem is item._doc

    return _sameScalar(docItem, item)
