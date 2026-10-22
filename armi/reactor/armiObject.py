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
Definition of the `Component` interface for the composite design pattern underlying the reactor package, which ARMI
calls `ArmiObject`.

This follows the principles of the `Composite Design Pattern <https://en.wikipedia.org/wiki/Composite_pattern>`_ to
allow the construction of a part/whole hierarchy representing a physical nuclear reactor in a tree strucutre. The
`ArmiObject` class defines a shared abstract interface to other child classes (this is the `Component` class in
`Gang of Four <https://en.wikipedia.org/wiki/Design_Patterns>`_). This design was chosen because of the close analogy
of the model to the physical nature of nuclear reactors.

See Also
--------
:doc:`/developer/index`.
armi.reactor.composites.Composite
armi.reactor.components.component.Component
"""

import itertools
from abc import ABCMeta, abstractmethod
from typing import (
    TYPE_CHECKING,
    Dict,
    Optional,
    Tuple,
    Type,
    Union,
)

import numpy as np

from armi import runLog, utils
from armi.nucDirectory import nucDir, nuclideBases
from armi.physics.neutronics.fissionProductModel import fissionProductModel
from armi.reactor import grids, parameters
from armi.reactor.flags import Flags, TypeSpec
from armi.reactor.parameters import resolveCollections
from armi.utils import densityTools, units
from armi.utils.densityTools import calculateNumberDensity
from armi.utils.flags import auto

if TYPE_CHECKING:
    from armi.reactor.components.component import Component


class FlagSerializer(parameters.Serializer):
    """
    Serializer implementation for Flags.

    This operates by converting each set of Flags (too large to fit in a uint64) into a
    sequence of enough uint8 elements to represent all flags. These constitute a
    dimension of a 2-D numpy array containing all Flags for all objects provided to the
    ``pack()`` function.
    """

    version = "1"

    @staticmethod
    def pack(data):
        """
        Flags are represented as a 2D numpy array of uint8 (single-byte, unsigned
        integers), where each row contains the bytes representing a single Flags
        instance. We also store the list of field names so that we can verify that the
        reader and the writer can agree on the meaning of each bit.

        Under the hood, this calls the private implementation providing the
        :py:class:`armi.reactor.flags.Flags` class as the target output class.
        """
        return FlagSerializer._packImpl(data, Flags)

    @staticmethod
    def _packImpl(data, flagCls: Type[utils.Flag]):
        """
        Implement the pack operation given a target output Flag class.

        This is kept separate from the public interface to permit testing of the
        functionality without having to do unholy things to ARMI's actual set of
        ``reactor.flags.Flags``.
        """
        npa = np.array([b for f in data for b in f.to_bytes()], dtype=np.uint8).reshape((len(data), flagCls.width()))

        return npa, {"flag_order": flagCls.sortedFields()}

    @staticmethod
    def _remapBits(inp: int, mapping: Dict[int, int]):
        """
        Given an input bitfield, map each bit to the appropriate new bit position based
        on the passed mapping.

        Parameters
        ----------
        inp : int
            input bitfield
        mapping : dict
            dictionary mapping from old bit position -> new bit position
        """
        f = 0
        for bit in itertools.count():
            if (1 << bit) > inp:
                break
            if (1 << bit) & inp:
                f = f | (1 << mapping[bit])

        return f

    @classmethod
    def unpack(cls, data, version, attrs):
        """
        Reverse the pack operation.

        This will allow for some degree of conversion from old flags to a new set of
        flags, as long as all of the source flags still exist in the current set of
        flags.

        Under the hood, this calls the private implementation providing the
        :py:class:`armi.reactor.flags.Flags` class as the target output class.
        """
        return cls._unpackImpl(data, version, attrs, Flags)

    @classmethod
    def _unpackImpl(cls, data, version, attrs, flagCls: Type[utils.Flag]):
        """
        Implement the unpack operation given a target output Flag class.

        This is kept separate from the public interface to permit testing of the
        functionality without having to do unholy things to ARMI's actual set of
        ``reactor.flags.Flags``.

        If the set of flags for the currently-configured App match the input set of
        flags, they are read in directly, which is good and cheap. However, if the set
        of flags differ from the input and the current App, we will try to convert them
        (as long as all of the input flags exist in the current App). Conversion is done
        by forming a map from all input bit positions to the current-App bit positions
        of the same meaning. E.g., if FUEL flag used to be the 3rd bit position, but now
        it is the 6th bit position, the map will contain ``map[3] = 6``. Then for each
        bitfield that is read in, each bit position is queried and if present, mapped to
        the proper corresponding new bit position. The result of this mapping is used to
        construct the Flags object.
        """
        flagOrderPassed = attrs["flag_order"]
        flagOrderNow = flagCls.sortedFields()

        if version != cls.version:
            raise ValueError(
                f"The FlagSerializer version used to pack the data ({version}) does not match "
                f"the current version ({cls.version})! This database either needs to be migrated, "
                "or on-the-fly inter-version conversion needs to be implemented."
            )

        flagSetIn = set(flagOrderPassed)
        flagSetNow = set(flagOrderNow)

        # Make sure that all of the old flags still exist
        if not flagSetIn.issubset(flagSetNow):
            missingFlags = flagSetIn - flagSetNow
            runLog.warning(
                "The set of flags in the database includes unknown flags. For convenience, we will "
                f"add these to the system: {missingFlags}"
            )
            flagCls.extend({k: auto() for k in missingFlags})

        flagOrderNow = flagCls.sortedFields()

        if all(i == j for i, j in zip(flagOrderPassed, flagOrderNow)):
            out = [flagCls.from_bytes(row.tobytes()) for row in data]
        else:
            newFlags = {i: flagOrderNow.index(oldFlag) for (i, oldFlag) in enumerate(flagOrderPassed)}
            out = [flagCls(cls._remapBits(int.from_bytes(row.tobytes(), byteorder="little"), newFlags)) for row in data]

        return out


def _defineBaseParameters():
    """
    Return parameter definitions that all ArmiObjects must have to function properly.

    For now, this pretty much just includes ``flags``, since these are used throughout
    the composite model to filter which objects are considered when traversing the
    reactor model.

    Note also that the base ParameterCollection class also has a ``serialNum``
    parameter. These are defined in different locations, since serialNum is a guaranteed
    feature of a ParameterCollection (for serialization to the database and history
    tracking), while the ``flags`` parameter is more a feature of the composite model.

    .. important::
        Notice that the ``flags`` parameter is not written to the database. This is for
        a couple of reasons:
        * Flags are derived from an ArmiObject's name. Since the name is stored on
        the DB, it is possible to recover the flags from that.
        * Storing flags to the DB may be complicated, since it is easier to imagine a
        number of flags that is greater than the width of natively-supported integer
        types, requiring some extra tricks to store the flags in an HDF5 file.
        * Allowing flags to be modified by plugins further complicates things, in that
        it is important to ensure that the meaning of all bits in the flag value are
        consistent between a database state and the current ARMI environment. This may
        require encoding these meanings in to the database as some form of metadata.
    """
    pDefs = parameters.ParameterDefinitionCollection()

    pDefs.add(
        parameters.Parameter(
            "flags",
            units=units.UNITLESS,
            description="The type specification of this object",
            location=parameters.ParamLocation.AVERAGE,
            saveToDB=True,
            default=Flags(0),
            setter=parameters.NoDefault,
            categories=set(),
            serializer=FlagSerializer,
        )
    )

    return pDefs


class ArmiObjectModelType(resolveCollections.ResolveParametersMeta):
    """
    Metaclass for tracking subclasses of ArmiObject.

    It is often useful to have an easily-accessible collection of all classes that participate in
    the ARMI composite reactor model. This metaclass maintains a collection of all defined
    subclasses, called TYPES.
    """

    TYPES: Dict[str, Type] = dict()
    """
    Dictionary mapping class name to class object for all subclasses.

    :meta hide-value:
    """

    def __new__(cls, name, bases, attrs):
        newType = resolveCollections.ResolveParametersMeta.__new__(cls, name, bases, attrs)

        ArmiObjectModelType.TYPES[name] = newType

        return newType


class ArmiObjectModelTypeABC(ABCMeta, ArmiObjectModelType):
    """Metaclass that combines ArmiObjectModelType with ABCMeta to allow ArmiObject to be an ABC."""

    pass


class ArmiObject(metaclass=ArmiObjectModelTypeABC):
    """
    The abstract base class for all composites and leaves.

    This:

    * declares the interface for objects in the composition
    * implements default behavior for the interface common to all classes
    * Defines an interface for accessing parents.

    Called "component" in gang of four, this is an ArmiObject here because the word component was
    already taken in ARMI.

    The :py:class:`armi.reactor.parameters.ResolveParametersMeta` metaclass is used to automatically
    create ``ParameterCollection`` subclasses for storing parameters associated with any particular
    subclass of ArmiObject. Defining a ``pDefs`` class attribute in the definition of a subclass of
    ArmiObject will lead to the creation of a new subclass of
    py:class:`armi.reactor.parameters.ParameterCollection`, which will contain the definitions from
    that class's ``pDefs`` as well as the definitions for all of its parents. A new
    ``paramCollectionType`` class attribute will be added to the ArmiObject subclass to reflect
    which type of parameter collection should be used.

    .. impl:: Parameters are accessible throughout the armi tree.
        :id: I_ARMI_PARAM1
        :implements: R_ARMI_PARAM

        An ARMI reactor model is composed of collections of ARMIObject objects. These
        objects are combined in a hierarchical manner. Each level of the composite tree
        is able to be assigned parameters which define it, such as temperature, flux,
        or keff values. This class defines an attribute of type ``ParameterCollection``,
        which contains all the functionality of an ARMI ``Parameter`` object. Because
        the entire model is composed of ARMIObjects at the most basic level, each level
        of the Composite tree contains this parameter attribute and can thus be queried.

    Attributes
    ----------
    name : str
        Object name
    parent : ArmiObject
        The object's parent in a hierarchical tree
    cached : dict
        Some cached values for performance
    p : ParameterCollection
        The state variables
    spatialGrid : grids.Grid
        The spatial grid that this object contains
    spatialLocator : grids.LocationBase
        The location of this object in its parent grid, or global space

    See Also
    --------
    armi.reactor.parameters
    """

    paramCollectionType: Optional[Type[parameters.ParameterCollection]] = None
    pDefs = _defineBaseParameters()

    def __init__(self, name):
        self.name = name
        self.parent = None
        self.cached = {}
        self._backupCache = None
        self.p = self.paramCollectionType()
        # NOTE: LFPs are not serialized to the database, which could matter when loading an old DB.
        self._lumpedFissionProducts = None
        self.spatialGrid = None
        self.spatialLocator = grids.CoordinateLocation(0.0, 0.0, 0.0, None)

    @abstractmethod
    def __iter__(self):
        """The part/whole hierarchy makes use of an __iter__ method that is used recurseively, so it should be defined
        in the interface.
        """

    @abstractmethod
    def __len__(self):
        """The part/whole hierarchy makes use of an __len__ method that is used recurseively, so it should be defined
        in the interface.
        """

    def __lt__(self, other):
        """
        Implement the less-than operator.

        Implementing this on the ArmiObject allows most objects, under most circumstances, to be
        sorted. This is useful from the context of the Database classes, so that they can produce a
        stable layout of the serialized composite structure.

        By default, this sorts using the spatial locator in K, J, I order, which should give a
        relatively intuitive order. It also makes sure that the objects being sorted live in the
        same grid.
        """
        if self.spatialLocator is None or other.spatialLocator is None:
            runLog.error(f"could not compare {self} and {other}")
            raise ValueError("One or more of the compared objects have no spatialLocator")

        if self.spatialLocator.grid is not other.spatialLocator.grid:
            runLog.error(f"could not compare {self} and {other}")
            raise ValueError(
                "Composite grids must be the same to compare:\n"
                f"This grid: {self.spatialGrid}\n"
                f"Other grid: {other.spatialGrid}"
            )
        try:
            t1 = tuple(reversed(self.spatialLocator.getCompleteIndices()))
            t2 = tuple(reversed(other.spatialLocator.getCompleteIndices()))
            return t1 < t2
        except ValueError:
            runLog.error(f"failed to compare {self.spatialLocator} and {other.spatialLocator}")
            raise

    def __getstate__(self):
        """
        Python method for reducing data before pickling.

        This removes links to parent objects, which allows one to, for example, pickle
        an assembly without pickling the entire reactor. Likewise, one could
        MPI_COMM.bcast an assembly without broadcasting the entire reactor.

        Notes
        -----
        Special treatment of ``parent`` is not enough, since the spatialGrid also
        contains a reference back to the armiObject. Consequently, the ``spatialGrid``
        needs to be reassigned in ``__setstate__``.
        """
        state = self.__dict__.copy()
        state["parent"] = None

        if "r" in state:
            raise RuntimeError("An ArmiObject should never contain the entire Reactor.")

        return state

    def __setstate__(self, state):
        """
        Sets the state of this ArmiObject.

        Notes
        -----
        This ArmiObject may have lost a reference to its parent. If the parent (a Composite or Composite subclass) was
        also pickled (serialized), then the parent should update the ``.parent`` attribute during its own
        ``__setstate__`` call. That means within the context of ``__setstate__`` one should not rely upon
        ``self.parent``.
        """
        self.__dict__.update(state)

        if self.spatialGrid is not None:
            self.spatialGrid.armiObject = self

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"

    def __format__(self, spec):
        return format(str(self), spec)

    def __bool__(self):
        """
        Flag that says this is non-zero in a boolean context.

        Notes
        -----
        The default behavior for ``not [obj]`` that has a  ``__len__`` defined is to see
        if the length is zero. However, for these composites, we'd like Assemblies, etc.
        to be considered non-zero even if they don't have any blocks. This is important
        for parent resolution, etc. If one of these objects exists, it is non-zero,
        regardless of its contents.
        """
        return True

    @property
    def nuclideBases(self):
        from armi.reactor.reactors import Reactor

        r = self.getAncestor(lambda c: isinstance(c, Reactor))
        if r:
            return r.nuclideBases
        else:
            return nuclideBases.nuclideBases

    def _getCached(self, name):
        """
        Obtain a value from the cache.

        Cached values can be used to temporarily store frequently read but long-to-compute values.
        The practice is generally discouraged because it's challenging to make sure to properly
        invalidate the cache when the state changes.
        """
        return self.cached.get(name, None)

    def _setCache(self, name, val):
        """
        Set a value in the cache.

        See Also
        --------
        _getCached : returns a previously-cached value
        """
        self.cached[name] = val

    def clearCache(self):
        """Clear the cache so all new values are recomputed."""
        self.cached = {}

    def copyParamsFrom(self, other):
        """
        Overwrite this object's params with other object's.

        Parameters
        ----------
        other : ArmiObject
            The object to copy params from
        """
        self.p = other.p.__class__()
        for p, val in other.p.items():
            self.p[p] = val

    def updateParamsFrom(self, new):
        """
        Update this object's params with a new object's.

        Parameters
        ----------
        new : ArmiObject
            The object to copy params from
        """
        for paramName, val in new.p.items():
            self.p[paramName] = val

    @classmethod
    def getParameterCollection(cls):
        """
        Return a new instance of the specific ParameterCollection type associated with this object.

        This has the same effect as ``obj.paramCollectionType()``. Getting a new
        instance through a class method like this is useful in situations where the
        ``paramCollectionType`` is not a top-level object and therefore cannot be
        trivially pickled. Since we know that by the time we want to make any instances
        of/unpickle a given ``ArmiObject``, such a class attribute will have been
        created and associated. So, we use this top-level method to dig
        dynamically down to the underlying parameter collection type.

        .. impl:: Composites (and all ARMI objects) have parameter collections.
            :id: I_ARMI_CMP_PARAMS
            :implements: R_ARMI_CMP_PARAMS

            This class method allows a user to obtain the
            ``paramCollection`` object, which is the object containing the interface for
            all parameters of an ARMI object.

        See Also
        --------
        :py:meth:`armi.reactor.parameters.parameterCollections.ParameterCollection.__reduce__`
        """
        return cls.paramCollectionType()

    def getParamNames(self):
        """
        Get a list of parameters keys that are available on this object.

        Will not have any corner, edge, or timenode dependence.
        """
        return sorted(k for k in self.p.keys() if not isinstance(k, tuple))

    def nameContains(self, s):
        """
        True if s is in this object's name (eg. nameContains('fuel')==True for 'testfuel'.

        Notes
        -----
        Case insensitive (all gets converted to lower)
        """
        name = self.name.lower()
        if isinstance(s, list):
            return any(n.lower() in name for n in s)
        else:
            return s.lower() in name

    def getName(self):
        """Get ArmiObject name."""
        return self.name

    def setName(self, name):
        self.name = name

    def hasFlags(self, typeID: TypeSpec, exact=False):
        """
        Determine if this object is of a certain type.

        .. impl:: Composites have queryable flags.
            :id: I_ARMI_CMP_FLAG0
            :implements: R_ARMI_CMP_FLAG

            This method queries the flags (i.e. the ``typeID``) of the Composite for a
            given type, returning a boolean representing whether or not the candidate
            flag is present in this ArmiObject. Candidate flags cannot be passed as a
            ``string`` type and must be of a type ``Flag``. If no flags exist in the
            object then ``False`` is returned.

            If a list of flags is provided, then all input flags will be
            checked against the flags of the object. If exact is ``False``, then the
            object must have at least one of candidates exactly. If it is ``True`` then
            the object flags and candidates must match exactly.

        Parameters
        ----------
        typeID : TypeSpec
            Flags to test the object against, to see if it contains them. If a list is
            provided, each element is treated as a "candidate" set of flags. Return True
            if any of candidates match. When exact is True, the object must match one of
            the candidates exactly. If exact is False, the object must have at least the
            flags contained in a candidate for that candidate to be a match; extra flags
            on the object are permitted. None matches all objects if exact is False, or
            no objects if exact is True.

        exact : bool, optional
            Require the type of the object to fully match the provided typeID(s)

        Returns
        -------
        hasFlags : bool
            True if this object is in the typeID list.

        Notes
        -----
        Type comparisons use bitwise comparisons using valid flags.

        If you have an 'inner control' assembly, then this will evaluate True for the
        INNER | CONTROL flag combination. If you just want all FUEL, simply use FUEL
        with no additional qualifiers. For more complex comparisons, use bitwise
        operations.

        Always returns true if typeID is none and exact is False, allowing for default
        parameters to be passed in when the method does not care about the object type.
        If the typeID is none and exact is True, this will always return False.

        Examples
        --------
        If you have an object with the ``INNER``, ``DRIVER``, and ``FUEL`` flags, then

        >>> obj.getType()
        [some integer]

        >>> obj.hasFlags(Flags.FUEL)
        True

        >>> obj.hasFlags(Flags.INNER | Flags.DRIVER | Flags.FUEL)
        True

        >>> obj.hasFlags(Flags.OUTER | Flags.DRIVER | Flags.FUEL)
        False

        >>> obj.hasFlags(Flags.INNER | Flags.FUEL)
        True

        >>> obj.hasFlags(Flags.INNER | Flags.FUEL, exact=True)
        False

        >>> obj.hasFlags([Flags.INNER | Flags.DRIVER | Flags.FUEL, Flags.OUTER | Flags.DRIVER | Flags.FUEL], exact=True)
        False

        """
        if not typeID:
            return not exact
        if isinstance(typeID, str):
            raise TypeError("Must pass Flags, or an iterable of Flags; Strings are no longer supported")

        elif not isinstance(typeID, Flags):
            # list behavior gives a spec1 OR spec2 OR ... behavior.
            return any(self.hasFlags(typeIDi, exact=exact) for typeIDi in typeID)

        if not self.p.flags:
            # default still set, or null flag. Do down here so we get proper error
            # handling of invalid typeSpecs
            return False

        if exact:
            # all bits must be identical for exact match
            return self.p.flags == typeID

        # all bits that are 1s in the typeID must be present
        return self.p.flags & typeID == typeID

    def getType(self):
        """Return the object type."""
        return self.p.type

    def setType(self, typ, flags: Optional[Flags] = None):
        """
        Set the object type.

        .. impl:: Composites have modifiable flags.
            :id: I_ARMI_CMP_FLAG1
            :implements: R_ARMI_CMP_FLAG

            This method allows for the setting of flags parameter of the Composite.

        Parameters
        ----------
        typ : str
            The desired "type" for the object. Type describes the general class of the
            object, and typically corresponds to the name of the blueprint that created
            it.

        flags : Flags, optional
            The set of Flags to apply to the object. If these are omitted, then Flags
            will be derived from the ``typ``.
        """
        self.p.flags = flags or Flags.fromStringIgnoreErrors(typ)
        self.p.type = typ

    def backUp(self):
        """
        Create and store a backup of the state.

        This needed to be overridden due to linked components which actually have a parameter value
        of another ARMI component.
        """
        self._backupCache = (self.cached, self._backupCache)
        self.cached = {}  # don't .clear(), using reference above!
        self.p.backUp()
        if self.spatialGrid:
            self.spatialGrid.backUp()

    def restoreBackup(self, paramsToApply):
        """
        Restore the parameters from previously created backup.

        Parameters
        ----------
        paramsToApply : list of ParmeterDefinitions
            restores the state of all parameters not in `paramsToApply`
        """
        self.p.restoreBackup(paramsToApply)
        self.cached, self._backupCache = self._backupCache
        if self.spatialGrid:
            self.spatialGrid.restoreBackup()

    @abstractmethod
    def getVolume(self):
        """Get the volume of the ArmiObject."""

    @abstractmethod
    def getArea(self, cold=False):
        """Get the area of the ArmiObject."""

    def getVolumeFraction(self):
        """Return the volume fraction that this object takes up in its parent."""
        if self.parent is not None:
            for child, frac in self.parent.getVolumeFractions():
                if child is self:
                    return frac

        raise ValueError(f"No parent is defined for {self}. Cannot compute its volume fraction.")

    @abstractmethod
    def getMass(self, nuclideNames: Union[None, str, list[str]] = None) -> float:
        """
        Determine the mass in grams of nuclide(s) and/or elements in this object.

        Parameters
        ----------
        nuclideNames
            The nuclide/element specifier to get the mass of in the object.
            If omitted, total mass is returned.

        Returns
        -------
        mass : float
            The mass in grams.
        """

    def getMassFrac(self, nucName):
        """
        Get the mass fraction of a nuclide.

        Notes
        -----
        If you need multiple mass fractions, use ``getMassFracs``.
        """
        nuclideNames = self._getNuclidesFromSpecifier(nucName)
        massFracs = self.getMassFracs()
        return sum(massFracs.get(nucName, 0.0) for nucName in nuclideNames)

    def getMicroSuffix(self):
        raise NotImplementedError(
            f"Cannot get the suffix on {type(self)} objects. Only certain subclasses"
            " of composite such as Blocks or Components have the concept of micro suffixes."
        )

    def _getNuclidesFromSpecifier(self, nucSpec: Union[None, str, list[str]]):
        """
        Convert a nuclide specification to a list of valid nuclide/element keys.

        nucSpec : nuclide specifier
            Can be a string name of a nuclide or element, or a list of such strings.

        This might get Zr isotopes when ZR is passed in if they exist, or it will get elemental ZR if that exists. When
        expanding elements, all known nuclides are returned, not just the natural ones.
        """
        allNuclidesHere = self.getNuclides()
        if nucSpec is None:
            return allNuclidesHere
        elif isinstance(nucSpec, (str)):
            nuclideNames = [nucSpec]
        elif isinstance(nucSpec, list):
            nuclideNames = nucSpec
        else:
            raise TypeError(f"nucSpec={nucSpec} is an invalid specifier. It is a {type(nucSpec)}")

        # expand elementals if appropriate.
        convertedNucNames = []
        for nucName in nuclideNames:
            if nucName in allNuclidesHere:
                convertedNucNames.append(nucName)
                continue
            try:
                # Need all nuclide bases, not just natural isotopics because, e.g. PU
                # has no natural isotopics!
                nucs = [
                    nb.name
                    for nb in self.nuclideBases.elements.bySymbol[nucName].nuclides
                    if not isinstance(nb, nuclideBases.NaturalNuclideBase)
                ]
                convertedNucNames.extend(nucs)
            except KeyError:
                convertedNucNames.append(nucName)

        return sorted(set(convertedNucNames))

    def getMassFracs(self):
        """
        Get mass fractions of all nuclides in object.

        Ni [1/cm3] * Ai [g/mole]  ~ mass
        """
        numDensities = self.getNumberDensities()
        return densityTools.getMassFractions(numDensities)

    def setMassFrac(self, nucName, val):
        """
        Adjust the composition of this object so the mass fraction of nucName is val.

        See Also
        --------
        setMassFracs : efficiently set multiple mass fractions at the same time.
        """
        self.setMassFracs({nucName: val})

    def setMassFracs(self, massFracs):
        r"""
        Apply one or more adjusted mass fractions.

        This will adjust the total mass of the object, as the mass of everything
        designated will change, while anything else will not.

        .. math::

            m_i = \frac{M_i}{\sum_j(M_j)}

            (M_{j \ne i} + M_i) m_i = M_i

            \frac{m_i M_{j \ne i}}{1-m_i} = M_i

            \frac{m_i M_{j \ne i}}{V(1-m_i)} = M_i/V = m_i \rho

            N_i = \frac{m_i \rho N_A}{A_i}

            N_i = \frac{m_i M_{j \ne i} N_A}{V (1-m_i) {A_i}}

            \frac{M_{j \ne i}}{V} = m_{j \ne i} \rho

            m_{j \ne i} = 1 - m_i

        Notes
        -----
        You can't just change one mass fraction though, you have scale all others to
        fill the remaining frac.

        Parameters
        ----------
        massFracs: dict
            nucName : new mass fraction pairs.
        """
        rho = self.density()
        if not rho:
            raise ValueError(f"Cannot set mass fractions on {self} because the mass density is zero.")
        oldMassFracs = self.getMassFracs()
        totalFracSet = 0.0
        for nucName, massFrac in massFracs.items():
            self.setNumberDensity(
                nucName,
                (massFrac * rho * units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM / nucDir.getAtomicWeight(nucName)),
            )
            if nucName in oldMassFracs:
                del oldMassFracs[nucName]
            totalFracSet += massFrac

        totalOther = sum(oldMassFracs.values())
        if totalOther:
            # we normalize the remaining mass fractions so their concentrations relative
            # to each other stay constant.
            normalizedOtherMassFracs = {nucNameOther: val / totalOther for nucNameOther, val in oldMassFracs.items()}
            for nucNameOther, massFracOther in normalizedOtherMassFracs.items():
                self.setNumberDensity(
                    nucNameOther,
                    (
                        (1.0 - totalFracSet)
                        * massFracOther
                        * rho
                        * units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
                        / nucDir.getAtomicWeight(nucNameOther)
                    ),
                )

    def adjustMassFrac(
        self,
        nuclideToAdjust=None,
        elementToAdjust=None,
        nuclideToHoldConstant=None,
        elementToHoldConstant=None,
        val=0.0,
    ):
        r"""
        Set the initial Zr mass fraction while maintaining Uranium enrichment, but general purpose.

        Parameters
        ----------
        nuclideToAdjust : str, optional
            The nuclide name to adjust
        elementToAdjust : str, optional
            The element to adjust. All isotopes in this element will adjust
        nuclideToHoldconstant : str, optional
            A nuclide to hold constant
        elementToHoldConstant : str
            Same
        val : float
            The value to set the adjust mass fraction to be.

        Notes
        -----
        If you use this for two elements one after the other, you will probably get
        something wrong. For instance, if you have U-10Zr and add Pu at 10% mass
        fraction, the Zr fraction will drop below 10% of the total. The U-Zr fractions
        will remain constant though. So this is mostly useful if you have U-10Zr and
        want to change it to U-5Zr.

        Theory:

        Mass fraction of each nuclide to be adjusted = Ai where A1+A2+A...+AI = A
        Mass fraction of nuclides to be held constant = Ci where sum = C
        Mass fraction of other nuclides is Oi, sum = O
        new value for A is v

        A+C+O = 1.0
        A'=v. If A>0, then A'=A*f1=v where f1 = v/A
        If A=0, then Ai' = v/len(A), distributing the value evenly among isotopes

        Now, to adjust the other nuclides, we know
        A'+C+O' = 1.0 , or v+C+O' = 1.0
        So, O'= 1.0-v-C
        We can scale each Oi evenly by multiplying by the factor f2
        Oi' = Oi * (1-C-v)/O = Oi * f2  where f2= (1-C-v)

        See Also
        --------
        setMassFrac
        getMassFrac
        """
        self.clearCache()  # don't keep densities around or anything.
        if val > 1.0 or val < 0:
            raise ValueError(f"Invalid mass fraction {val} for {nuclideToAdjust}/{elementToAdjust} in {self.getName()}")
        if not nuclideToAdjust and not elementToAdjust:
            raise TypeError("Must provide a nuclide or element to adjust to adjustMassFrac")

        # sum of other nuclide mass fractions before change is Y
        # need Yx+newZr = 1.0 where x is a scaling factor
        # so x=(1-newZr)/Y

        # determine nuclides to hold constant
        nuclides = set(self.getNuclides())
        if nuclideToHoldConstant or elementToHoldConstant:
            # note that if these arguments are false, you'll get ALL nuclides in the
            # material use material.getNuclides to get only non-zero ones.  use
            # nucDir.getNuclides to get all. Intersect with current nuclides to
            # eliminate double counting of element/isotopes
            constantNuclides = set(
                nucDir.getNuclideNames(nucName=nuclideToHoldConstant, elementSymbol=elementToHoldConstant)
            ).intersection(nuclides)
            constantSum = sum(self.getMassFrac(nucName) for nucName in constantNuclides)
        else:
            constantNuclides = []
            constantSum = 0.0

        # determine which nuclides we're adjusting.
        # Rather than calling this material's getNuclides method, we call the
        # nucDirectory to do this. this way, even zeroed-out nuclides will get in the mix
        adjustNuclides = set(
            nucDir.getNuclideNames(nucName=nuclideToAdjust, elementSymbol=elementToAdjust)
        ).intersection(nuclides)
        # get original mass frac A of those to be adjusted.
        A = sum(self.getMassFrac(ni) for ni in adjustNuclides)

        factor1 = val / A if A else None

        # set the ones we're adjusting to their given value.
        numNucs = len(adjustNuclides)
        newA = 0.0
        newMassFracs = {}
        for nuc in adjustNuclides:
            if factor1 is None:
                # this is for when adjust nuclides have zero mass fractions. Like Zr.
                # In this case, if there are multiple nuclides, we will distribute them
                # evenly because we have no other indication of how to adjust them.
                newMassFrac = val / numNucs
            else:
                # this is for when the nuclides we're adjusting already exist
                # with non-zero mass fractions could be Pu vector.
                newMassFrac = self.getMassFrac(nuc) * factor1
            newA += newMassFrac
            newMassFracs[nuc] = newMassFrac
            if nuc == "ZR":
                # custom parameter only set here to determine how to behave for UZr
                # density, linear expansion. Can't let it roam with each mass frac
                # 'cause then the density roams too and there are "oscillations"
                self.zrFrac = newMassFrac

        # error checking.
        if abs(newA - val) > 1e-10:
            runLog.error(f"Adjust Mass fraction did not adjust {adjustNuclides} from {A} to {val}. It got to {newA}")
            raise RuntimeError("Failed to adjust mass fraction.")

        # determine the mass fraction of the nuclides that will be adjusted to
        # accommodate the requested change
        othersSum = 1.0 - A - constantSum
        if not othersSum:
            # no others to be modified.
            factor2 = 1.0
        else:
            # use newA rather than val
            factor2 = (1.0 - newA - constantSum) / othersSum

        # change all the other nuclides using f2 factor
        for nuc in self.getNuclides():
            if nuc not in adjustNuclides and nuc not in constantNuclides:
                newMassFracs[nuc] = self.getMassFrac(nuc) * factor2

        self.setMassFracs(newMassFracs)

    @abstractmethod
    def getNuclideNumberDensities(self, nucNames):
        """Return a list of number densities in atoms/barn-cm for the nuc names requested.

        Parameters
        ----------
        nucNames : list of str
            Nuclide names to get number densities for, e.g. ['U233', 'U235', 'Pu239']
        """

    @abstractmethod
    def _getNdensHelper(self):
        """Return a number densities dict with unexpanded lfps."""

    @abstractmethod
    def getNumberDensity(self, nucName):
        """Return the number density of a nuclide in atoms/barn-cm.

        Parameters
        ----------
        nucName : str
            Nuclide name to get number density for, e.g. 'U233'.

        """

    def getNumberDensities(self, expandFissionProducts=False):
        """
        Retrieve the number densities in atoms/barn-cm of all nuclides (or those requested) in the object.

        .. impl:: Number density of composite is retrievable.
            :id: I_ARMI_CMP_NUC
            :implements: R_ARMI_CMP_NUC

            This method provides a way for retrieving the number densities
            of all nuclides within the Composite. It does this by leveraging the
            ``_getNdensHelper`` method, which invokes the ``getNuclideNumberDensities``
            method. This method considers the nuclides within each child Composite of
            this composite (if they exist). If the ``expandFissionProducts`` flag is
            ``True``, then the lumped fission products are expanded to include their
            constituent elements via the ``_expandLFPs`` method.

        Parameters
        ----------
        expandFissionProducts : bool (optional)
            expand the fission product number densities

        Returns
        -------
        numberDensities : dict
            nucName keys, number density values (atoms/bn-cm)
        """
        numberDensities = self._getNdensHelper()
        if expandFissionProducts:
            return self._expandLFPs(numberDensities)
        return numberDensities

    def _expandLFPs(self, numberDensities):
        """
        Expand the LFPs on the numberDensities dictionary using this composite's
        lumpedFissionProductCollection.
        """
        lfpCollection = self.getLumpedFissionProductCollection()
        if lfpCollection:  # may not have lfps in non-fuel
            lfpDensities = lfpCollection.getNumberDensities(self)
            numberDensities = {
                nucName: numberDensities.get(nucName, 0.0) + lfpDensities.get(nucName, 0.0)
                for nucName in set(numberDensities) | set(lfpDensities)
            }
            # remove LFPs from the result
            for lfpName in lfpCollection:
                numberDensities.pop(lfpName, None)
        else:
            lfpMass = sum(
                dens
                for name, dens in numberDensities.items()
                if isinstance(self.nuclideBases.byName[name], nuclideBases.LumpNuclideBase)
            )
            if lfpMass:
                raise RuntimeError(
                    f"Composite {self} is attempting to expand lumped fission products, but does not have "
                    "an lfpCollection."
                )
        return numberDensities

    def getAncestor(self, fn):
        """
        Return the first ancestor that satisfies the supplied predicate.

        Parameters
        ----------
        fn : Function-like object
            The predicate used to test the validity of an ancestor. Should return true
            if the ancestor satisfies the caller's requirements
        """
        if fn(self):
            return self
        if self.parent is None:
            return None
        else:
            return self.parent.getAncestor(fn)

    def getAncestorAndDistance(self, fn, _distance=0) -> Optional[Tuple["ArmiObject", int]]:
        """
        Return the first ancestor that satisfies the supplied predicate, along with how
        many levels above self the ancestor lies.

        Parameters
        ----------
        fn : Function-like object
            The predicate used to test the validity of an ancestor. Should return true
            if the ancestor satisfies the caller's requirements
        """
        if fn(self):
            return self, _distance
        if self.parent is None:
            return None
        else:
            return self.parent.getAncestorAndDistance(fn, _distance + 1)

    def getAncestorWithFlags(self, typeSpec: TypeSpec, exactMatch=False, excludeSelf=False):
        """
        Return the first ancestor that matches the passed flags.

        Parameters
        ----------
        typeSpec : TypeSpec
            A collection of flags to match on candidate parents
        exactMatch : bool
            Whether the flags match should be exact
        excludeSelf : bool
            Whether to exclude the reciever object in the ancestor tree.

        Returns
        -------
        armi.composites.ArmiObject
            the first ancestor up the chain of parents that matches the passed flags

        Warning
        -------
        The receiver object will return itself if it contains the flags in typeSpec and excludeSelf is False.

        See Also
        --------
        ArmiObject.hasFlags()
        """
        if not (excludeSelf):
            if self.hasFlags(typeSpec, exact=exactMatch):
                return self

        if self.parent is None:
            return None
        else:
            return self.parent.getAncestorWithFlags(typeSpec, exactMatch=exactMatch)

    def getTotalNDens(self):
        """
        Return the total number density of all atoms in this object.

        Returns
        -------
        nTot : float
            Total ndens of all nuclides in atoms/bn-cm. Not homogenized.
        """
        nFPsPerLFP = fissionProductModel.NUM_FISSION_PRODUCTS_PER_LFP  # LFPs count as two! Big deal in non BOL cases.
        return sum(dens * (nFPsPerLFP if "LFP" in name else 1.0) for name, dens in self.getNumberDensities().items())

    @abstractmethod
    def setNumberDensity(self, nucName, val):
        """
        Set the number density of this nuclide to this value.

        Parameters
        ----------
        nucName : str
            Nuclide number density to modify
        val : float
            Number density to set in atoms/bn-cm (heterogeneous)
        """

    @abstractmethod
    def setNumberDensities(self, numberDensities):
        """
        Set one or more multiple number densities. Reset any non-listed nuclides to 0.0.

        Parameters
        ----------
        numberDensities : dict
            nucName: ndens pairs.
        """

    @abstractmethod
    def updateNumberDensities(self, numberDensities):
        """
        Set one or more multiple number densities. Leaves unlisted number densities alone.

        Parameters
        ----------
        numberDensities : dict
            nucName: ndens pairs.
        """

    @abstractmethod
    def changeNDensByFactor(self, factor):
        """Change the number density of all nuclides within the object by a multiplicative factor."""

    def clearNumberDensities(self):
        """
        Reset all the number densities to nearly zero.

        Set to almost zero, so components remember which nuclides are where.
        """
        ndens = {nuc: units.TRACE_NUMBER_DENSITY for nuc in self.getNuclides()}
        self.setNumberDensities(ndens)

    def density(self):
        """Returns the mass density of the object in g/cc."""
        density = 0.0
        for nuc in self.getNuclides():
            density += (
                self.getNumberDensity(nuc) * nucDir.getAtomicWeight(nuc) / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
            )

        return density

    def getNumberOfAtoms(self, nucName):
        """Return the number of atoms of nucName in this object."""
        numDens = self.getNumberDensity(nucName)  # atoms/bn-cm
        return numDens * self.getVolume() / units.CM2_PER_BARN

    def getLumpedFissionProductCollection(self):
        """
        Get collection of LFP objects. Will work for global or block-level LFP models.

        Returns
        -------
        lfps : LumpedFissionProduct
            lfpName keys , lfp object values

        See Also
        --------
        armi.physics.neutronics.fissionProductModel.lumpedFissionProduct.LumpedFissionProduct : LFP object
        """
        return self._lumpedFissionProducts

    def setLumpedFissionProducts(self, lfpCollection):
        self._lumpedFissionProducts = lfpCollection

    def getFissileMassEnrich(self):
        """Returns the fissile mass enrichment."""
        hm = self.getHMMass()
        if hm > 0:
            return self.getFissileMass() / hm
        else:
            return 0.0

    def getUraniumNumEnrich(self):
        """Returns fissile uranium number fraction."""
        uraniumNucs = self._getNuclidesFromSpecifier("U")
        totalU = sum(self.getNuclideNumberDensities(uraniumNucs))
        if totalU < 1e-10:
            return 0.0
        fissileU = sum(self.getNuclideNumberDensities(["U233", "U235"]))

        return fissileU / totalU

    def isFuel(self):
        """True if this is a fuel block."""
        return self.hasFlags(Flags.FUEL)

    @abstractmethod
    def getNuclides(self):
        """
        Determine which nuclides are present in this armi object.

        Returns
        -------
        nucs : list of str
            Nuclide names that exist in this ArmiObject
        """

    def getFissileMass(self):
        """Returns fissile mass in grams."""
        return self.getMass(nuclideBases.NuclideBase.fissile)

    def getHMMass(self):
        """Returns heavy metal mass in grams."""
        nucs = []
        for nucName in self.getNuclides():
            if nucDir.isHeavyMetal(nucName):
                nucs.append(nucName)

        mass = self.getMass(nucs)
        return mass

    def getHMMoles(self):
        """
        Get the number of moles of heavy metal in this object.

        Notes
        -----
        If an object is on a symmetry line, the volume reported by getVolume
        is reduced to reflect that the block is not wholly within the reactor. This
        reduction in volume reduces the reported HM moles.
        """
        return self.getHMDens() / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * self.getVolume()

    def getHMDens(self):
        """
        Compute the total heavy metal density of this object.

        Returns
        -------
        hmDens : float
            The total heavy metal number (atom) density in atoms/bn-cm.
        """
        hmNuclides = [nuclide for nuclide in self.getNuclides() if nucDir.isHeavyMetal(nuclide)]
        hmDens = np.sum(self.getNuclideNumberDensities(hmNuclides))
        return hmDens

    def getFPMass(self):
        """Returns mass of fission products in this block in grams."""
        nucs = []
        for nucName in self.getNuclides():
            if "LFP" in nucName:
                nucs.append(nucName)
        mass = self.getMass(nucs)
        return mass

    @abstractmethod
    def getFuelMass(self):
        """Returns mass of fuel in grams."""

    def getAtomicWeight(self):
        r"""
        Calculate the atomic weight of this object in g/mole of atoms.

        .. warning:: This is not the molecular weight, which is grams per mole of
            molecules (grams/gram-molecule). That requires knowledge of the chemical
            formula. Don't be surprised when you run this on UO2 and find it to be 90;
            there are a lot of Oxygen atoms in UO2.

        .. math::

            A =  \frac{\sum_i N_i A_i }{\sum_i N_i}
        """
        numerator = 0.0
        denominator = 0.0
        numDensities = self.getNumberDensities()

        for nucName, nDen in numDensities.items():
            atomicWeight = self.nuclideBases.byName[nucName].weight
            numerator += atomicWeight * nDen
            denominator += nDen

        return numerator / denominator

    def getMasses(self):
        """
        Return a dictionary of masses indexed by their nuclide names.

        Notes
        -----
        Implemented to get number densities and then convert to mass
        because getMass is too slow on a large tree.
        """
        numDensities = self.getNumberDensities()
        vol = self.getVolume()
        return {nucName: densityTools.getMassInGrams(nucName, vol, ndens) for nucName, ndens in numDensities.items()}

    @abstractmethod
    def getIntegratedMgFlux(self, adjoint=False, gamma=False):
        """
        Return the multigroup neutron tracklength in [n-cm/s].

        The first entry is the first energy group (fastest neutrons). Each additional group is the
        next energy group, as set in the ISOTXS library.

        Parameters
        ----------
        adjoint : bool, optional
            Return adjoint flux instead of real
        gamma : bool, optional
            Whether to return the neutron flux or the gamma flux.

        Returns
        -------
        integratedFlux : multigroup neutron tracklength in [n-cm/s]
        """

    def getMgFlux(self, adjoint=False, average=False, gamma=False):
        """
        Return the multigroup neutron flux in [n/cm^2/s].

        The first entry is the first energy group (fastest neutrons). Each additional group is the next energy group, as
        set in the ISOTXS library.

        On blocks, it is stored integrated over volume on <block>.p.mgFlux

        Parameters
        ----------
        adjoint : bool, optional
            Return adjoint flux instead of real
        average : bool, optional
            If true, will return average flux between latest and previous. Doesn't work
            for pin detailed yet
        gamma : bool, optional
            Whether to return the neutron flux or the gamma flux.

        Returns
        -------
        flux : np.ndarray
            multigroup neutron flux in [n/cm^2/s]
        """
        if average:
            raise NotImplementedError(
                f"{self.__class__} class has no method for producing average MG flux -- tryusing blocks"
            )

        volume = self.getVolume()
        return self.getIntegratedMgFlux(adjoint=adjoint, gamma=gamma) / volume

    def removeMass(self, nucName, mass):
        self.addMass(nucName, -mass)

    def addMass(self, nucName, mass):
        """Add mass to a particular nuclide.

        Parameters
        ----------
        nucName : str
            nuclide name e.g. 'U235'
        mass : float
            mass in grams of nuclide to be added to this armi Object
        """
        volume = self.getVolume()
        addedNumberDensity = densityTools.calculateNumberDensity(nucName, mass, volume)
        self.setNumberDensity(nucName, self.getNumberDensity(nucName) + addedNumberDensity)

    def addMasses(self, masses):
        """
        Adds a vector of masses.

        Parameters
        ----------
        masses : dict
            a dictionary of masses (g) indexed by nucNames (string)
        """
        for nucName, mass in masses.items():
            if mass:
                self.addMass(nucName, mass)

    def setMass(self, nucName, mass):
        """
        Set the mass in an object by adjusting the ndens of the nuclides.

        Parameters
        ----------
        nucName : str
            Nuclide name to set mass of
        mass : float
            Mass in grams to set.
        """
        d = calculateNumberDensity(nucName, mass, self.getVolume())
        self.setNumberDensity(nucName, d)

    def setMasses(self, masses):
        """
        Set a vector of masses.

        Parameters
        ----------
        masses : dict
            a dictionary of masses (g) indexed by nucNames (string)
        """
        self.clearNumberDensities()
        for nucName, mass in masses.items():
            self.setMass(nucName, mass)

    def getSymmetryFactor(self):
        """
        Return a scaling factor due to symmetry on the area of the object or its children.

        See Also
        --------
        armi.reactor.blocks.HexBlock.getSymmetryFactor : concrete implementation
        """
        return 1.0

    def expandAllElementalsToIsotopics(self):
        reactorNucs = self.getNuclides()
        for elemental in self.nuclideBases.where(
            lambda nb: isinstance(nb, nuclideBases.NaturalNuclideBase) and nb.name in reactorNucs
        ):
            self.expandElementalToIsotopics(elemental)

    def _expandElementalToIsotopics(self, component: "Component", elementalNuclide: "nuclideBases.NaturalNuclideBase"):
        """
        Expand the density of an element on a component to its natural isotopic distribution.

        Parameters
        ----------
        component : :class:`armi.reactor.components.component.Component` in which to expand the element
        elementalNuclide : :class:`armi.nucDirectory.nuclideBases.NaturalNuclideBase` element to
            expand into natural isotopic distribution.
        """
        natName = elementalNuclide.name
        elementalDensity = component.getNumberDensity(natName)
        if elementalDensity > 0.0:
            keepIndex = np.where(component.p.nuclides != natName.encode())[0]
            newNuclides = [nuc.decode() for nuc in component.p.nuclides[keepIndex]]
            newNDens = component.p.numberDensities[keepIndex]
            component.updateNumberDensities(dict(zip(newNuclides, newNDens)), wipe=True)

            # add in isotopics
            for natNuc in elementalNuclide.getNaturalIsotopics():
                component.setNumberDensity(natNuc.name, elementalDensity * natNuc.abundance)

    @abstractmethod
    def expandElementalToIsotopics(self, elementalNuclide):
        """
        Expand the density of a specific element to its natural isotopic distribution.

        Parameters
        ----------
        elementalNuclide : :class:`armi.nucDirectory.nuclideBases.NaturalNuclide` element to
            expand into natural isotopic distribution.
        """

    @abstractmethod
    def getReactionRates(self, nucName, nDensity=None):
        """
        Get the reaction rates of a certain nuclide on this ArmiObject.

        Parameters
        ----------
        nucName : str
            nuclide name -- e.g. 'U235'
        nDensity : float
            number Density

        Returns
        -------
        rxnRates : dict
            reaction rates (1/s) for nG, nF, n2n, nA and nP
        """

    def _getReactionRates(self, nucName, nDensity=None):
        """
        Wrapper around logic to get reaction rates for a certain nuclide, to handle any errors.

        Parameters
        ----------
        nucName : str
            nuclide name -- e.g. 'U235'
        nDensity : float
            number density

        Returns
        -------
        rxnRates : dict
            dictionary of reaction rates (rxn/s) for nG, nF, n2n, nA and nP

        Notes
        -----
        If you set nDensity to 1/CM2_PER_BARN this makes 1 group cross section generation easier.

        This method is not designed to work on ``Assembly``, ``Core``, or anything higher on the
        hierarchy than ``Block``.
        """
        from armi.reactor.blocks import Block
        from armi.reactor.reactors import Core

        if nDensity is None:
            nDensity = self.getNumberDensity(nucName)

        try:
            return self._getReactionRateDict(
                nucName,
                self.getAncestor(lambda c: isinstance(c, Core)).lib,
                self.getAncestor(lambda x: isinstance(x, Block)).getMicroSuffix(),
                self.getIntegratedMgFlux(),
                nDensity,
            )
        except AttributeError:
            runLog.warning(
                f"Object {self} does not belong to a core and so has no reaction rates.",
                single=True,
            )
            return {"nG": 0, "nF": 0, "n2n": 0, "nA": 0, "nP": 0}
        except KeyError:
            runLog.warning(
                f"Attempting to get a reaction rate on an isotope not in the lib {nucName}.",
                single=True,
            )
            return {"nG": 0, "nF": 0, "n2n": 0, "nA": 0, "nP": 0}

    def _getReactionRateDict(self, nucName, lib, xsSuffix, mgFlux, nDens):
        """
        Helper to get the reaction rates of a certain nuclide on one ArmiObject.

        Parameters
        ----------
        nucName : str
            nuclide name -- e.g. 'U235', 'PU239', etc. Not to be confused with the nuclide _label_, see
            the nucDirectory module for a description of the difference.
        lib : isotxs
            cross section library
        xsSuffix : str
            cross section suffix, consisting of the type followed by the burnup group, e.g. 'AB' for the
            second burnup group of type A
        mgFlux : np.ndarray
            integrated mgFlux (n-cm/s)
        nDens : float
            number density (atom/bn-cm)

        Returns
        -------
        rxnRates - dict
            dictionary of reaction rates (rxn/s) for nG, nF, n2n, nA and nP

        Notes
        -----
        Assume there is no n3n cross section in ISOTXS
        """
        nucLabel = self.nuclideBases.byName[nucName].label
        key = f"{nucLabel}{xsSuffix}"
        libNuc = lib[key]
        rxnRates = {"n3n": 0}
        for rxName, mgXSs in [
            ("nG", libNuc.micros.nGamma),
            ("nF", libNuc.micros.fission),
            ("n2n", libNuc.micros.n2n),
            ("nA", libNuc.micros.nalph),
            ("nP", libNuc.micros.np),
        ]:
            rxnRates[rxName] = nDens * sum(mgXSs * mgFlux)

        return rxnRates

    def _syncParameters(self, allSyncData, errors):
        """Ensure no overlap with syncedKeys, use errors to report overlapping data."""
        syncedKeys = set()
        for nodeRank, nodeSyncData in enumerate(allSyncData):
            if nodeSyncData is None:
                continue

            for key, val in nodeSyncData.items():
                if key in syncedKeys:
                    # Edge Case: an ArmiObject object is flagged as out of sync, and this parameter
                    # was also globally modified and readjusted to the original value.
                    curVal = self.p[key]
                    if isinstance(val, np.ndarray) or isinstance(curVal, np.ndarray):
                        if (val != curVal).any():
                            errors[self, key].append(nodeRank)
                    elif curVal != val:
                        errors[self, key].append(nodeRank)
                        runLog.error(f"in {self}, {key} differ ({curVal} != {val})")
                    continue
                syncedKeys.add(key)
                self.p[key] = val

        self.clearCache()
        return len(syncedKeys)
