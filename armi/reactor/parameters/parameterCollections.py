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

import copy
import pickle
import sys
from typing import Any, Callable, Iterator, List, Optional, Set

import numpy as np

from armi import runLog
from armi.reactor.parameters import exceptions, parameterDefinitions
from armi.reactor.parameters.parameterDefinitions import (
    NEVER,
    SINCE_ANYTHING,
    SINCE_BACKUP,
    SINCE_LAST_DISTRIBUTE_STATE,
)
from armi.utils import units

GLOBAL_SERIAL_NUM = -1
"""
The serial number for all ParameterCollections

This is a counter of the number of instances of all types. They are useful for tracking items
through the history of a database.

Warning
-------
This is not MPI safe. We also have not done anything to make it thread safe, except that the GIL
exists.
"""


def _getBaseParameterDefinitions():
    pDefs = parameterDefinitions.ParameterDefinitionCollection()
    pDefs.add(
        parameterDefinitions.Parameter(
            "serialNum",
            units=units.UNITLESS,
            description=(
                "Unique serial integer for all objects in the ARMI Composite Tree. "
                "The numbers are only unique for a simulation, on an MPI rank."
            ),
            location=None,
            saveToDB=True,
            default=parameterDefinitions.NoDefault,
            setter=parameterDefinitions.NoDefault,
            categories=set(),
        )
    )

    return pDefs


class _ParameterCollectionType(type):
    """
    Simple metaclass to make sure that expected class attributes are present.

    These attributes shouldn't  be shared among different subclasses, so this makes sure that each
    subclass gets its own.
    """

    def __new__(mcl, name, bases, attrs):
        attrs["pDefs"] = attrs.get("pDefs") or None
        attrs["_ArmiObject"] = None
        attrs["_allFields"] = []

        return type.__new__(mcl, name, bases, attrs)


class ParameterCollection(metaclass=_ParameterCollectionType):
    """An empty class for holding state information in the ARMI data structure.

    A parameter collection stores one or more formally-defined values ("parameters"). Until a given
    ParameterCollection subclass has been instantiated, new parameters may be added to its parameter
    definitions (e.g., from plugins). Upon first instantiation, ``applyParameters()`` will be
    called, binding the parameter definitions to the Collection class as descriptors.

    It is illegal to redefine a parameter with the same name in the same class, or its subclasses,
    and attempting to do so should result in exceptions in ``applyParameters()``.

    Attributes
    ----------
    _backup : str
        A pickle dump of the __getstate__, or None.

    _hist : dict
        Keys are ``(paramName, timeStep)``.

    assigned : int Flag
        indicates the synchronization state of the parameter collection. This is used to reduce the
        amount of information that is transmitted during database, and MPI operations as well as
        determine the collection's state when exiting a ``Composite.retainState``.

        This attribute when used with the ``Parameter.assigned`` attribute allows us to efficiently
        perform many operations.

    See Also
    --------
    armi.reactors.parameters
    """

    pDefs: parameterDefinitions.ParameterDefinitionCollection = (
        _getBaseParameterDefinitions()
    )
    _allFields: List[str] = []

    _ArmiObject = None
    """The ArmiObject class that this ParameterCollection belongs to.

    Crucially **not** the instance that owns this collection. For any
    ``ArmiObject``, the following are true::

        >>> self.p._ArmiObject is not self
        >>> isinstance(self, self.p._ArmiObject)

    """

    # A set of all instance attributes that are settable on an instance. This prevents inadvertent
    # setting of values that aren't proper parameters. Named _slots, as it is used to emulate some
    # of the behaviors of __slots__.
    _slots: Set[str] = set()

    def __init__(self, _state: Optional[List[Any]] = None):
        """
        Create a new ParameterCollection instance.

        Parameters
        ----------
        _state:
            Optional list of parameter values, ordered by _allFields. Passed values
            should come from a call to __getstate__(). This should only be used
            internally to this model.
        """
        # add a hook to make this readOnly
        self._slots.add("readOnly")
        self.readOnly = False

        if self.pDefs is None or not self.pDefs.locked:
            type(self).applyParameters()

        assert self.pDefs.locked, (
            "It looks like parameter definitions haven't been "
            "set up yet for {}; be sure that applyAllParameters() is being called "
            "somewhere.".format(type(self))
        )

        self._backup = None
        # used by the history tracker when a parameter key is a tuple (name, timestep)
        self._hist = {}

        # Initialize all parameter values to **something**. This is crucial to getting
        # the split-key dictionary memory savings in lieu of using __slots__!
        if _state is None:
            for pDef in self.paramDefs:
                setattr(self, pDef.fieldName, pDef.default)
        else:
            for key, val in zip(self._allFields, _state):
                self.__dict__[key] = val

        self.assigned = NEVER

        global GLOBAL_SERIAL_NUM
        self.serialNum = GLOBAL_SERIAL_NUM = GLOBAL_SERIAL_NUM + 1

        if self.serialNum > sys.maxsize:
            runLog.warning(
                "Created serial number larger than an integer. Current serial: {}".format(
                    GLOBAL_SERIAL_NUM
                )
            )

    @classmethod
    def applyParameters(cls):
        """
        Apply the definitions from a ParameterDefinitionCollection as properties.

        This places the parameter definitions in the associated
        ParameterDefinitionCollection onto this ParameterCollection class as class
        attributes. In the process it recursively calls the same method on base classes,
        and adds their parameter definitions as well. Since each instance of Parameter
        implements the descriptor protocol, these are effectively behaving as
        ``@property``-style accessors.

        This function must act on each ParameterCollection subclass before the first
        instance is created. Subsequent calls will short-circuit. Before calling this
        method, it is possible to add more Parameters to the associated
        ParameterDefinitionCollection, ``cls.pDefs``. After calling this method, the
        ParameterDefinitionCollection will be locked, preventing any further additions.

        This method is called in the ``__init__()`` method, but can also be called
        proactively to compile the parameter definitions earlier, if desired.

        See Also
        --------
        armi.reactor.parameters.parameterDefinitions.ParameterDefinitionCollection
        """
        if bool(cls._allFields):
            # Short-circuit if this has already been done
            return

        # Ensure that we have at least something to start with
        cls.pDefs = cls.pDefs or parameterDefinitions.ParameterDefinitionCollection()

        # Collect definitions from base ParameterCollection classes. E.g.,
        # HelixParameterCollection also gets parameter definitions from
        # ComponentParameterCollection.
        if not cls.pDefs.locked:
            basePDefs = parameterDefinitions.ParameterDefinitionCollection()
            for base in [
                b for b in cls.__bases__ if issubclass(b, ParameterCollection)
            ]:
                base.applyParameters()
                if base.pDefs is not None:
                    basePDefs.extend(base.pDefs)

            # Check for duplicate parameter definitions
            seen = set()
            duplicates = set()
            for name in cls.pDefs.names:
                if name in seen:
                    duplicates.add(name)
                seen.add(name)
            if duplicates:
                raise exceptions.ParameterDefinitionError(
                    "The following parameters were multiply-defined:\n    {}".format(
                        duplicates
                    )
                )
            overriddenParameters = set(cls.pDefs.names).intersection(
                set(basePDefs.names)
            )
            if overriddenParameters:
                raise exceptions.ParameterDefinitionError(
                    "The following parameters "
                    "have been redefined in a subclass: {}\n"
                    "current type: {}\n"
                    "bases: {}".format(overriddenParameters, cls, cls.__bases__)
                )

        # Bind the parameter definitions as descriptors to the collection
        for pd in cls.pDefs:
            pd.collectionType = cls
            setattr(cls, pd.name, pd)
            parameterDefinitions.ALL_DEFINITIONS.add(pd)

        cls.pDefs.extend(basePDefs)

        # prevent the addition of new parameter definitions. This will lead to errors
        # early, rather than mysterious attribute access errors later.
        cls.pDefs.lock()
        cls._allFields = list(
            sorted(
                ["_backup", "_hist", "assigned"] + [pd.fieldName for pd in cls.pDefs]
            )
        )

        cls._slots = set(cls._allFields).union({pd.name for pd in cls.pDefs})

    def __repr__(self):
        return "<{} assigned:{}>".format(self.__class__.__name__, self.assigned)

    def __setattr__(self, key, value):
        assert key in self._slots, (
            "Trying to set undefined attribute `{}` on "
            "a ParameterCollection!".format(key)
        )

        if getattr(self, "readOnly", False):
            if key == "readOnly":
                raise RuntimeError(
                    "A read-only Parameter Collection cannot be made writeable."
                )
            else:
                raise RuntimeError(f"Cannot set a read-only parameter {key}.")

        object.__setattr__(self, key, value)

    def __deepcopy__(self, memo):
        """
        Returns a new instance of ParameterCollection with a new ``serialNum``.

        Notes
        -----
        This operates under the assumption that ``__deepcopy__`` is used when needing a
        new instance, which should get its own serial number. This follows from the
        assumption that parameter collections are typically copied when copying an
        ArmiObject to which it may belong. In this case, serialNum needs to be
        incremented so that the objects are unique. serialNum is special.
        """
        # Grabbing state first and passing it into __init__() as a performance
        # optimization. This avoids the extra work in __init__() of defaulting all of
        # the parameters, only to set them in __setstate__(). Instead we pass them in,
        # so that __init__() can set them.
        state = copy.deepcopy(self.__getstate__(), memo)
        memo[id(self)] = newPC = self.__class__(_state=state)
        return newPC

    def __reduce__(self):
        """
        Implement pickle __reduce__ protocol.

        We need to do this because most subclasses of ParameterCollection are created
        from a metaclass, and are therefore not top-level objects and not trivially
        picklable. This implementation works by asking the ArmiObject itself to give an
        instance of its associated ParameterCollection class, then setting its state.
        """
        assert type(self)._ArmiObject is not None, (
            "Cannot reduce {}, since it does not have an associated ArmiObject, and is "
            "therefore not tied to the world of the living.".format(type(self))
        )
        return type(self)._ArmiObject.getParameterCollection, (), self.__getstate__()

    def __getstate__(self):
        # reduce data to one giant list, ordered by _allFields (sorted). Use NoDefault
        # when a value is missing
        data = [
            getattr(self, fieldName, parameterDefinitions.NoDefault)
            for fieldName in self._allFields
        ]
        return data

    def __setstate__(self, state):
        # does the reverse of __getstate__
        for key, val in zip(self._allFields, state):
            setattr(self, key, val)

    def __getitem__(self, name):
        try:
            return getattr(self, name)
        except TypeError:  # allows for history parameter tuples
            return self._hist[name]
        except AttributeError:
            raise exceptions.UnknownParameterError(
                "Parameter {} is not defined for {}".format(name, type(self))
            )

    def __setitem__(self, name, value):
        try:
            setattr(self, name, value)
        except TypeError:  # allows for history parameter tuples
            if isinstance(name, tuple):
                self._hist[name] = value
            else:
                raise
        except AttributeError:  # for clarity
            raise exceptions.UnknownParameterError(
                "Cannot locate definition for parameter {} in {}".format(
                    name, type(self)
                )
            )

    def __delitem__(self, name):
        if isinstance(name, str):
            pd = self.paramDefs[name]
            if hasattr(self, pd.fieldName):
                pd.assigned = SINCE_ANYTHING
                delattr(self, pd.fieldName)
        else:
            del self._hist[name]

    def __contains__(self, name):
        if isinstance(name, str):
            return hasattr(self, "_p_" + name)
        else:
            return name in self._hist

    def __eq__(self, other: "ParameterCollection"):
        if not isinstance(other, self.__class__):
            return False

        for pd in self.paramDefs:
            fieldName = pd.fieldName
            haveValue = (hasattr(self, fieldName), hasattr(other, fieldName))
            if all(haveValue):
                if getattr(self, fieldName) != getattr(self, fieldName):
                    return False
            elif any(haveValue):
                return False

        return True

    def __iter__(self) -> Iterator[str]:
        """Iterate over names of assigned parameters define on this collection."""
        return (
            pd.name
            for pd in self.paramDefs
            if pd.assigned != NEVER
            and getattr(self, pd.fieldName) is not parameterDefinitions.NoDefault
        )

    def items(self):
        keys = list(iter(self))
        return zip(keys, (getattr(self, key) for key in keys))

    def get(self, key, default=None):
        """Return a requested parameter value, if possible.

        This functions similarly to the same method on a dict or similar. If there is a
        value present for the requested parameter on this parameter collection, return
        it. Otherwise, return the supplied default. The main reason for using this is
        for safely attempting to access a parameter that doesn't have a default value,
        and may not have been set. Other methods for accessing parameters would raise
        an exception.
        """
        try:
            return self[key]
        except exceptions.ParameterError:
            return default

    def keys(self):
        return list(iter(self)) + list(self._hist.keys())

    def values(self):
        paramVals = list(
            getattr(self, pd.fieldName)
            for pd in self.paramDefs
            if hasattr(self, pd.fieldName)
        )
        return paramVals + list(self._hist.values())

    def update(self, someDict):
        for k, val in someDict.items():
            self[k] = val

    @property
    def paramDefs(self) -> parameterDefinitions.ParameterDefinitionCollection:
        r"""
        Get the :py:class:`ParameterDefinitionCollection` associated with this instance.

        This serves as both an alias for the pDefs class attribute, and as a read-only
        accessor for them. Most non-parameter-system related interactions with an
        object's ``ParameterCollection`` should go through this. In the future, it
        probably makes sense to make the ``pDefs`` that the ``applyDefinitions`` and
        ``ResolveParametersMeta`` things are sensitive to more hidden from outside the
        parameter system.
        """
        return type(self).pDefs

    def getSyncData(self):
        """
        Get all changed parameters SINCE_LAST_DISTRIBUTE_STATE (or ``syncMpiState``).

        If this ParmaterCollection (proxy for a ``Composite``) has been modified
        ``SINCE_LAST_DISTRIBUTE_STATE``, this will return a dictionary of parameter name
        keys and values, otherwise ``None``.
        """
        if self.assigned & SINCE_LAST_DISTRIBUTE_STATE:
            syncData = {
                paramDef.name: getattr(self, paramDef.fieldName)
                for paramDef in self.paramDefs
                if paramDef.assigned & SINCE_LAST_DISTRIBUTE_STATE
                and paramDef.name in self
            }
            return syncData
        return None

    def backUp(self):
        """Back up the state in a Pickle."""
        try:
            self._backup = pickle.dumps(self.__getstate__())
            # this reads as assigned & everything_but(SINCE_BACKUP)
            self.assigned &= ~SINCE_BACKUP
        except:
            runLog.error("Attempted to pickle {}.".format(self))
            raise

    def restoreBackup(self, paramsToApply):
        """Restore the backed up the state in a from a pickle.

        Parameters
        ----------
        paramsToApply : list of ParmeterDefinitions
            restores the state of all parameters not in `paramsToApply`
        """
        currentData = dict()

        if self.assigned & SINCE_BACKUP:
            compParams = (pd for pd in paramsToApply.intersection(set(self.paramDefs)))
            currentData = {
                pd: getattr(self, pd.fieldName)
                for pd in compParams
                if hasattr(self, pd.fieldName)
            }

        self.__setstate__(pickle.loads(self._backup))

        for pd, currentValue in currentData.items():
            # correct for global paramDef.assigned assumption
            retainedValue = getattr(self, pd.fieldName)
            if isinstance(retainedValue, np.ndarray) or isinstance(
                currentValue, np.ndarray
            ):
                if (retainedValue != currentValue).any():
                    setattr(self, pd.fieldName, currentValue)
                    pd.assigned = SINCE_ANYTHING
                    self.assigned = SINCE_ANYTHING
            elif retainedValue != currentValue:
                setattr(self, pd.fieldName, currentValue)
                pd.assigned = SINCE_ANYTHING
                self.assigned = SINCE_ANYTHING

    def where(
        self, f: Callable[[parameterDefinitions.Parameter], bool]
    ) -> Iterator[parameterDefinitions.Parameter]:
        """Produce an iterator over parameters that meet some criteria.

        Parameters
        ----------
        f : callable function f(parameter) -> bool
            Function to check if a parameter should be fetched during the iteration.

        Returns
        -------
        iterator of :class:`armi.reactor.parameters.Parameter`
            Iterator, **not** list or tuple, that produces each parameter that
            meets ``f(parameter) == True``.

        Examples
        --------
        >>> block = r.core[0][0]
        >>> pdef = block.p.paramDefs
        >>> for param in pdef.where(lambda pd: pd.atLocation(ParamLocation.EDGES)):
        ...     print(param.name, block.p[param.name])

        """
        return filter(f, self.paramDefs)


def collectPluginParameters(pm):
    """Apply parameters from plugins to their respective object classes."""
    for pluginParamDefnCollections in pm.hook.defineParameters():
        for klass, pDefs in pluginParamDefnCollections.items():
            klass.pDefs.extend(pDefs)


def applyAllParameters(klass=None):
    klass = klass or ParameterCollection
    klass.applyParameters()
    for derived in klass.__subclasses__():
        applyAllParameters(derived)
