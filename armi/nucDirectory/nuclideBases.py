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
This module provides fundamental nuclide information to be used throughout the framework and applications.

.. impl:: Isotopes and isomers can be queried by name, label, MC2-3 ID, MCNP ID, and AAAZZZS ID.
    :id: I_ARMI_ND_ISOTOPES0
    :implements: R_ARMI_ND_ISOTOPES

    The :py:mod:`nuclideBases <armi.nucDirectory.nuclideBases>` module defines
    the :py:class:`NuclideBase <armi.nucDirectory.nuclideBases.NuclideBase>`
    class which is used to organize and store metadata about each nuclide. The
    metadata is read from ``nuclides.dat`` file in the ARMI resources folder,
    which contains metadata for 4,614 isotopes. The module also contains classes
    for special types of nuclides, including :py:class:`DummyNuclideBase
    <armi.nucDirectory.nuclideBases.DummyNuclideBase>` for dummy nuclides,
    :py:class:`LumpNuclideBase
    <armi.nucDirectory.nuclideBases.LumpNuclideBase>`, for lumped fission
    product nuclides, and :py:class:`NaturalNuclideBase
    <armi.nucDirectory.nuclideBases.NaturalNuclideBase>` for when data is given
    collectively for an element at natural abundance rather than for individual
    isotopes.

    The :py:class:`NuclideBase <armi.nucDirectory.nuclideBases.NuclideBase>`
    provides a data structure for information about a single nuclide, including
    the atom number, atomic weight, element, isomeric state, half-life, and
    name.

    The :py:mod:`nuclideBases <armi.nucDirectory.nuclideBases>` module provides
    a factory and associated functions for instantiating the
    :py:class:`NuclideBase <armi.nucDirectory.nuclideBases.NuclideBase>` objects
    and building the global nuclide dictionaries, including:

    * ``instances`` (list of nuclides)
    * ``byName`` (keyed by name, e.g., ``U235``)
    * ``byDBName`` (keyed by database name, e.g., ``nU235``)
    * ``byLabel`` (keyed by label, e.g., ``U235``)
    * ``byMcc2Id`` (keyed by MC\ :sup:`2`-2 ID, e.g., ``U-2355``)
    * ``byMcc3Id`` (keyed by MC\ :sup:`2`-3 ID, e.g., ``U235_7``)
    * ``byMcc3IdEndfbVII0`` (keyed by MC\ :sup:`2`-3 ID, e.g., ``U235_7``)
    * ``byMcc3IdEndfbVII1`` (keyed by MC\ :sup:`2`-3 ID, e.g., ``U235_7``)
    * ``byMcnpId`` (keyed by MCNP ID, e.g., ``92235``)
    * ``byAAAZZZSId`` (keyed by AAAZZZS, e.g., ``2350920``)

The nuclide class structure is outlined :ref:`here
<nuclide-bases-class-diagram>`.

.. _nuclide-bases-class-diagram:

.. pyreverse:: armi.nucDirectory.nuclideBases
    :align: center
    :width: 75%

    Class inheritance diagram for :py:class:`INuclide`.

Examples
--------
>>> nuclideBases.byName['U235']
<NuclideBase U235:  Z:92, A:235, S:0, W:2.350439e+02, Label:U235>, HL:2.22160758861e+16, Abund:7.204000e-03>

>>> nuclideBases.byLabel['U235']
<NuclideBase U235:  Z:92, A:235, S:0, W:2.350439e+02, Label:U235>, HL:2.22160758861e+16, Abund:7.204000e-03>

Retrieve U-235 by the MC2-2 ID:

>>> nuclideBases.byMcc2Id['U-2355']
<NuclideBase U235:  Z:92, A:235, S:0, W:2.350439e+02, Label:U235>, HL:2.22160758861e+16, Abund:7.204000e-03>

Retrieve U-235 by the MC2-3 ID:

>>> nuclideBases.byMcc3IdEndfVII0['U235_7']
<NuclideBase U235:  Z:92, A:235, S:0, W:2.350439e+02, Label:U235>, HL:2.22160758861e+16, Abund:7.204000e-03>

Retrieve U-235 by the MCNP ID:

>>> nuclideBases.byMcnpId['92235']
<NuclideBase U235:  Z:92, A:235, S:0, W:2.350439e+02, Label:U235>, HL:2.22160758861e+16, Abund:7.204000e-03>

Retrieve U-235 by the AAAZZZS ID:

>>> nuclideBases.byAAAZZZSId['2350920']
<NuclideBase U235:  Z:92, A:235, S:0, W:2.350439e+02, Label:U235>, HL:2.22160758861e+16, Abund:7.204000e-03>

Notes
-----
Currently, this module contains a lot of data in the global scope. But ARMI is in the process of encapsulating this
data, moving it out of the global scope, making it part of the reactor data model, and making it configurable via
Settings. Pardon the mess during this transition.
"""

import os

import numpy as np
from ruamel.yaml import YAML

from armi import context, runLog
from armi.nucDirectory import elements, transmutations
from armi.utils.units import HEAVY_METAL_CUTOFF_Z

# Global nuclide and nuclideBases data
nuclideBases = None
instances = []
burnChainImposed = False
byName = None
byDBName = None
byLabel = None
byMcc2Id = None
byMcc3Id = None  # for backwards compatibility. Identical to byMcc3IdEndfbVII1
byMcc3IdEndfbVII0 = None
byMcc3IdEndfbVII1 = None
byMcnpId = None
byAAAZZZSId = None

# lookup table from https://t2.lanl.gov/nis/data/endf/endfvii-n.html
BASE_ENDFB7_MAT_NUM = {
    "PM": 139,
    "RA": 223,
    "AC": 225,
    "TH": 227,
    "PA": 229,
    "NP": 230,
    "PU": 235,
    "AM": 235,
    "CM": 240,
    "BK": 240,
    "CF": 240,
    "TC": 99,
}


class NuclideInterface:
    """An abstract nuclide implementation which defining various methods required for a nuclide object."""

    def getDatabaseName(self):
        """Return the the nuclide label for the ARMI database (i.e. "nPu239")."""
        raise NotImplementedError

    def getDecay(self, decayType):
        """
        Return a :py:class:`~armi.nucDirectory.transmutations.DecayMode` object.

        Parameters
        ----------
        decType: str
            Name of decay mode, e.g. 'sf', 'alpha'

        Returns
        -------
        decay : :py:class:`DecayModes <armi.nucDirectory.transmutations.DecayMode>`
        """
        raise NotImplementedError

    def getMcc2Id(self):
        """Return the MC2-2 nuclide identification label based on the ENDF/B-V.2 cross section library."""
        return NotImplementedError

    def getMcc3Id(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.1 cross section library."""
        return NotImplementedError

    def getMcc3IdEndfbVII0(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.0 cross section library."""
        return NotImplementedError

    def getMcc3IdEndfbVII1(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.1 cross section library."""
        return NotImplementedError

    def getSerpentId(self):
        """Get the Serpent nuclide identification label."""
        raise NotImplementedError

    def getNaturalIsotopics(self):
        """Return the natural isotopics root :py:class:`~elements.Element`."""
        raise NotImplementedError

    def isFissile(self):
        """Return boolean value indicating whether this nuclide is fissile."""
        raise NotImplementedError

    def isHeavyMetal(self):
        """Return boolean value indicating whether this nuclide is a heavy metal."""
        raise NotImplementedError


class NuclideWrapper(NuclideInterface):
    """A nuclide wrapper class, used as a base class for nuclear data file nuclides."""

    def __init__(self, container, key):
        self._base = None
        self.container = container
        self.containerKey = key
        self.nucLabel = key[:-2]

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.containerKey}>"

    def __format__(self, format_spec):
        return format_spec.format(repr(self))

    @property
    def name(self):
        """
        Return the underlying nuclide's name (i.e. "PU239").

        Notes
        -----
        The nuclide name consists of the capitalized 2 character element symbol and atomic mass number.
        """
        return self._base.name

    @property
    def weight(self):
        """Get the underlying nuclide's weight."""
        return self._base.weight

    def getDatabaseName(self):
        """Get the database name of the underlying nuclide (i.e. "nPu239")."""
        return self._base.getDatabaseName()

    def getDecay(self, decayType):
        """
        Return a :py:class:`~armi.nucDirectory.transmutations.DecayMode` object.

        Parameters
        ----------
        decType: str
            Name of decay mode, e.g. 'sf', 'alpha'

        Returns
        -------
        decay : :py:class:`DecayModes <armi.nucDirectory.transmutations.DecayMode>`
        """
        return self._base.getDecay(decayType)

    def getMcc2Id(self):
        """Return the MC2-2 nuclide based on the ENDF/B-V.2 cross section library."""
        return self._base.getMcc2Id()

    def getMcc3Id(self):
        """Return the MC2-3 nuclide based on the ENDF/B-VII.1 cross section library."""
        return self.getMcc3IdEndfbVII1()

    def getMcc3IdEndfbVII0(self):
        """Return the MC2-3 nuclide based on the ENDF/B-VII.0 cross section library."""
        return self._base.getMcc3IdEndfbVII0()

    def getMcc3IdEndfbVII1(self):
        """Return the MC2-3 nuclide based on the ENDF/B-VII.1 cross section library."""
        return self._base.getMcc3IdEndfbVII1()

    def getNaturalIsotopics(self):
        """Return the natural isotopics root :py:class:`~elements.Element`."""
        return self._base.getNaturalIsotopics()

    def isFissile(self):
        """Return boolean indicating whether or not the underlying nuclide is fissle."""
        return self._base.isFissile()

    def isHeavyMetal(self):
        """Return boolean indicating whether or not the underlying nuclide is a heavy metal."""
        return self._base.isHeavyMetal()


class INuclide(NuclideInterface):
    """
    Nuclide interface, the base of all nuclide objects.

    Attributes
    ----------
    z : int
        Number of protons.
    a : int
        Number of nucleons.
    state : int
        Indicates excitement, 1 is more excited than 0.
    abundance : float
        Isotopic fraction of a naturally occurring nuclide. The sum of all nuclide abundances for a naturally occurring
        element should be 1.0. This is atom fraction, not mass fraction.
    name : str
        ARMI's unique name for the given nuclide.
    label : str
        ARMI's unique 4 character label for the nuclide. These are not human readable, but do not lose any information.
        The label is effectively the :py:attr:`Element.symbol <armi.nucDirectory.elements.Element.symbol>` padded to two
        characters, plus the mass number (A) in base-26 (0-9, A-Z). Additional support for meta-states is provided by
        adding 100 * the state to the mass number (A).
    nuSF : float
        Neutrons released per spontaneous fission. This should probably be moved at some point.
    """

    fissile = ["U235", "PU239", "PU241", "AM242M", "CM244", "U233"]
    TRANSMUTATION = "transmutation"
    DECAY = "decay"
    SPONTANEOUS_FISSION = "nuSF"

    def __init__(
        self,
        element,
        a,
        state,
        weight,
        abundance,
        halflife,
        name,
        label,
        mcc2id=None,
        mcc3idEndfbVII0=None,
        mcc3idEndfbVII1=None,
        addToGlobal=True,
    ):
        """
        Create an instance of an INuclide.

        Warning
        -------
        Do not call this constructor directly; use the factory instead.
        """
        if element not in elements.byName.values():
            raise ValueError(
                f"Error in initializing nuclide {name}. Element {element} does not exist in the global element list."
            )
        if state < 0:
            raise ValueError(
                f"Error in initializing nuclide {name}. An invalid state {state} is provided. The state must be a "
                "positive integer."
            )
        if halflife < 0.0:
            raise ValueError(f"Error in initializing nuclide {name}. The halflife must be a positive value.")

        self.element = element
        self.z = element.z
        self.a = a
        self.state = state
        self.decays = []
        self.trans = []
        self.weight = weight
        self.abundance = abundance
        self.halflife = halflife
        self.name = name
        self.label = label
        self.nuSF = 0.0
        self.mcc2id = mcc2id or ""
        self.mcc3idEndfbVII0 = mcc3idEndfbVII0 or ""
        self.mcc3idEndfbVII1 = mcc3idEndfbVII1 or ""
        if addToGlobal:
            addGlobalNuclide(self)
        self.element.append(self)

    def __hash__(self):
        return hash((self.a, self.z, self.state))

    def __reduce__(self):
        return fromName, (self.name,)

    def __lt__(self, other):
        return (self.z, self.a, self.state) < (other.z, other.a, other.state)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def _processBurnData(self, burnInfo):
        """
        Process YAML burn transmutation, decay, and spontaneous fission data for this nuclide.

        This clears out any existing transmutation/decay information before processing.

        Parameters
        ----------
        burnInfo: list
            List of dictionaries containing burn information for the current nuclide
        """
        self.decays = []
        self.trans = []
        for nuclideBurnCategory in burnInfo:
            # Check that the burn category has only one defined burn type
            if len(nuclideBurnCategory) > 1:
                raise ValueError(
                    f"Improperly defined ``burn-chain`` of {self}. {nuclideBurnCategory.keys()} should be a single "
                    "burn type."
                )
            nuclideBurnType = list(nuclideBurnCategory.keys())[0]
            if nuclideBurnType == self.TRANSMUTATION:
                self.trans.append(transmutations.Transmutation(self, nuclideBurnCategory[nuclideBurnType]))
            elif nuclideBurnType == self.DECAY:
                self.decays.append(transmutations.DecayMode(self, nuclideBurnCategory[nuclideBurnType]))
            elif nuclideBurnType == self.SPONTANEOUS_FISSION:
                userSpontaneousFissionYield = nuclideBurnCategory.get(nuclideBurnType, None)

                # Check for user-defined value of nuSF within the burn-chain data. If this is updated then prefer the
                # user change and then note this to the user. Otherwise, maintain the default loaded from the nuclide
                # bases.
                if userSpontaneousFissionYield:
                    if userSpontaneousFissionYield != self.nuSF:
                        runLog.info(
                            f"nuSF provided for {self} will be updated from {self.nuSF:<8.6e} to "
                            f"{userSpontaneousFissionYield:<8.6e} based on user provided burn-chain data."
                        )
                        self.nuSF = userSpontaneousFissionYield
            else:
                raise Exception(
                    f"Undefined Burn Data {nuclideBurnType} for {self}. Expected {self.TRANSMUTATION}, {self.DECAY}, "
                    f"or {self.SPONTANEOUS_FISSION}."
                )

    def getDecay(self, decayType):
        """Get a :py:class:`~armi.nucDirectory.transmutations.DecayMode`.

        Retrieve the first :py:class:`~armi.nucDirectory.transmutations.DecayMode` matching the specified decType.

        Parameters
        ----------
        decType: str
            Name of decay mode e.g. 'sf', 'alpha'

        Returns
        -------
        decay : :py:class:`DecayModes <armi.nucDirectory.transmutations.DecayMode>`
        """
        for d in self.decays:
            if d.type == decayType:
                return d

        return None

    def isFissile(self):
        """Determine if the nuclide is fissile.

        Returns
        -------
        answer: bool
            True if the :py:class:`INuclide` is fissile, otherwise False.
        """
        return self.name in self.fissile

    def getNaturalIsotopics(self):
        r"""Gets the naturally occurring nuclides for this nuclide.

        Abstract method, see concrete types for implementation.

        Returns
        -------
        nuclides: list
            List of :py:class:`INuclides <INuclide>`

        See Also
        --------
        :meth:`NuclideBase.getNaturalIsotopics`
        :meth:`NaturalNuclideBase.getNaturalIsotopics`
        :meth:`LumpNuclideBase.getNaturalIsotopics`
        :meth:`DummyNuclideBase.getNaturalIsotopics`
        """
        raise NotImplementedError

    def getDatabaseName(self):
        """Get the name of the nuclide used in the database (i.e. "nPu239")."""
        return f"n{self.name.capitalize()}"

    def isHeavyMetal(self):
        return self.z > HEAVY_METAL_CUTOFF_Z


class IMcnpNuclide:
    """Abstract class for retrieving nuclide identifiers for the MCNP software."""

    def getMcnpId(self):
        """Return a string that represents a nuclide label for a material card in MCNP."""
        raise NotImplementedError

    def getAAAZZZSId(self):
        """Return a string that is ordered by the mass number, A, the atomic number, Z, and the isomeric state, S."""
        raise NotImplementedError


class NuclideBase(INuclide, IMcnpNuclide):
    r"""Represents an individual nuclide/isotope.

    .. impl:: Isotopes and isomers can be queried by name and label.
        :id: I_ARMI_ND_ISOTOPES1
        :implements: R_ARMI_ND_ISOTOPES

        The :py:class:`NuclideBase <armi.nucDirectory.nuclideBases.NuclideBase>` class provides a data structure for
        information about a single nuclide, including the atom number, atomic weight, element, isomeric state,
        half-life, and name. The class contains static methods for creating an internal ARMI name or label for a
        nuclide. There are instance methods for generating the nuclide ID for external codes, e.g. MCNP or Serpent, and
        retrieving the nuclide ID for MC\ :sup:`2`-2 or MC\ :sup:`2`-3. There are also instance methods for generating
        an AAAZZZS ID and an ENDF MAT number.
    """

    def __init__(self, element, a, weight, abundance, state, halflife, addToGlobal=True):
        IMcnpNuclide.__init__(self)
        INuclide.__init__(
            self,
            element=element,
            a=a,
            state=state,
            weight=weight,
            abundance=abundance,
            halflife=halflife,
            name=NuclideBase._createName(element, a, state),
            label=NuclideBase._createLabel(element, a, state),
            addToGlobal=addToGlobal,
        )

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} {self.name}:  Z:{self.z}, A:{self.a}, S:{self.state}, "
            + f"W:{self.weight:<12.6e}, Label:{self.label}>, HL:{self.halflife:<15.11e}, "
            + f"Abund:{self.abundance:<8.6e}>"
        )

    @staticmethod
    def _createName(element, a, state):
        metaChar = ["", "M", "M2", "M3"]
        if state > len(metaChar):
            raise ValueError(f"The state of NuclideBase is not valid and must not be larger than {len(metaChar)}.")

        return f"{element.symbol}{a}{metaChar[state]}"

    @staticmethod
    def _createLabel(element, a, state):
        """
        Make label for nuclide base.

        The logic causes labels for things with A<10 to be zero padded like H03 or tritium instead of H3. This avoids
        the metastable tritium collision which would look like elemental HE. It also allows things like MO100 to be held
        within 4 characters, which is a constraint of the ISOTXS format if we append 2 characters for XS type.
        """
        # len(e.symbol) is 1 or 2 => a % (either 1000 or 100)
        #                         => gives exact a, or last two digits.
        # the division by 10 removes the last digit.
        firstTwoDigits = (a % (10 ** (4 - len(element.symbol)))) // 10
        # the last digit is either 0-9 if state=0, or A-J if state=1, or K-T if state=2, or U-d if state=3
        lastDigit = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcd"[(a % 10) + state * 10]
        return f"{element.symbol}{firstTwoDigits}{lastDigit}"

    def getNaturalIsotopics(self):
        """Gets the natural isotopics root :py:class:`~elements.Element`.

        Gets the naturally occurring nuclides for this nuclide.

        Returns
        -------
        nuclides: list
            List of :py:class:`INuclides <INuclide>`

        See Also
        --------
        :meth:`INuclide.getNaturalIsotopics`
        """
        return self.element.getNaturalIsotopics()

    def getMcc2Id(self):
        """Return the MC2-2 nuclide identification label based on the ENDF/B-V.2 cross section library.

        .. impl:: Isotopes and isomers can be queried by MC2-2 ID.
            :id: I_ARMI_ND_ISOTOPES2
            :implements: R_ARMI_ND_ISOTOPES

            This method returns the ``mcc2id`` attribute of a
            :py:class:`NuclideBase <armi.nucDirectory.nuclideBases.NuclideBase>` instance. This attribute is initially
            populated by reading from the mcc-nuclides.yaml file in the ARMI resources folder.
        """
        return self.mcc2id

    def getMcc3Id(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.1 cross section library."""
        return self.getMcc3IdEndfbVII1()

    def getMcc3IdEndfbVII0(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.0 cross section library.

        .. impl:: Isotopes and isomers can be queried by MC2-3 ENDF/B-VII.0 ID.
            :id: I_ARMI_ND_ISOTOPES3
            :implements: R_ARMI_ND_ISOTOPES

            This method returns the ``mcc3idEndfbVII0`` attribute of a
            :py:class:`NuclideBase <armi.nucDirectory.nuclideBases.NuclideBase>`
            instance. This attribute is initially populated by reading from the
            mcc-nuclides.yaml file in the ARMI resources folder.
        """
        return self.mcc3idEndfbVII0

    def getMcc3IdEndfbVII1(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.1 cross section library.

        .. impl:: Isotopes and isomers can be queried by MC2-3 ENDF/B-VII.1 ID.
            :id: I_ARMI_ND_ISOTOPES7
            :implements: R_ARMI_ND_ISOTOPES

            This method returns the ``mcc3idEndfbVII1`` attribute of a
            :py:class:`NuclideBase <armi.nucDirectory.nuclideBases.NuclideBase>`
            instance. This attribute is initially populated by reading from the
            mcc-nuclides.yaml file in the ARMI resources folder.
        """
        return self.mcc3idEndfbVII1

    def getMcnpId(self):
        """
        Gets the MCNP label for this nuclide.

        .. impl:: Isotopes and isomers can be queried by MCNP ID.
            :id: I_ARMI_ND_ISOTOPES4
            :implements: R_ARMI_ND_ISOTOPES

            This method generates the MCNP ID for an isotope using the standard
            MCNP format based on the atomic number A, number of protons Z, and
            excited state. The implementation includes the special rule for
            Am-242m, which is 95242. 95642 is used for the less common ground
            state Am-242.

        Returns
        -------
        id : str
            The MCNP ID e.g. ``92235``, ``94239``, ``6000``
        """
        z, a = self.z, self.a

        if z == 95 and a == 242:
            # Am242 has special rules
            if self.state != 1:
                # MCNP uses base state for the common metastable state AM242M, so AM242M is just 95242
                # AM242 base state is called 95642 (+400) in mcnp.
                # see https://mcnp.lanl.gov/pdf_files/la-ur-08-1999.pdf
                # New ACE-Formatted Neutron and Proton Libraries Based on ENDF/B-VII.0
                a += 300 + 100 * max(self.state, 1)
        elif self.state > 0:
            # in general mcnp adds 300 + 100*m to the Z number for metastables. see above source
            a += 300 + 100 * self.state

        return "{z:d}{a:03d}".format(z=z, a=a)

    def getAAAZZZSId(self):
        """
        Return a string that is ordered by the mass number, A, the atomic number, Z, and the isomeric state, S.

        .. impl:: Isotopes and isomers can be queried by AAAZZZS ID.
            :id: I_ARMI_ND_ISOTOPES5
            :implements: R_ARMI_ND_ISOTOPES

            This method generates the AAAZZZS format ID for an isotope. Where
            AAA is the mass number, ZZZ is the atomic number, and S is the
            isomeric state. This is a general format independent of any code that
            precisely defines an isotope or isomer.

        Notes
        -----
        An example would be for U235, where A=235, Z=92, and S=0, returning ``2350920``.
        """
        return f"{self.a}{self.z:>03d}{self.state}"

    def getSerpentId(self):
        """
        Returns the SERPENT style ID for this nuclide.

        Returns
        -------
        id: str
            The ID of this nuclide based on it's elemental name, weight,
            and state, eg ``U-235``, ``Te-129m``.
        """
        symbol = self.element.symbol.capitalize()
        return f"{symbol}-{self.a}{'m' if self.state else ''}"

    def getEndfMatNum(self):
        """
        Gets the ENDF MAT number.

        MAT numbers are defined as described in section 0.4.1 of the NJOY manual. Basically, it's Z * 100 + I where I is
        an isotope number. I=25 is defined as the lightest known stable isotope of element Z, so for Uranium, Z=92 and
        I=25 refers to U234. The values of I go up by 3 for each mass number, so U235 is 9228. This leaves room for
        three isomeric states of each nuclide.

        Returns
        -------
        id : str
            The MAT number e.g. ``9237`` for U238
        """
        z, a = self.z, self.a
        if self.element.symbol in BASE_ENDFB7_MAT_NUM:
            # no stable isotopes (or other special case). Use lookup table
            smallestStableA = BASE_ENDFB7_MAT_NUM[self.element.symbol]
        else:
            naturalIsotopes = self.getNaturalIsotopics()
            if naturalIsotopes:
                smallestStableA = min(ni.a for ni in naturalIsotopes)  # no guarantee they were sorted
            else:
                raise KeyError(f"Nuclide {self} is unknown in the MAT number lookup")

        isotopeNum = (a - smallestStableA) * 3 + self.state + 25
        mat = z * 100 + isotopeNum
        return str(mat)


class NaturalNuclideBase(INuclide, IMcnpNuclide):
    """
    Represents an individual nuclide/isotope that is naturally occurring.

    Notes
    -----
    This is meant to represent the combination of all naturally occurring nuclides within an element. The abundance is
    forced to zero here so that it does not have any interactions with the NuclideBase objects.
    """

    def __init__(self, name, element, addToGlobal=True):
        INuclide.__init__(
            self,
            element=element,
            a=0,
            state=0,
            weight=sum([nn.weight * nn.abundance for nn in element.getNaturalIsotopics()]),
            abundance=0.0,
            halflife=np.inf,
            name=name,
            label=name,
            addToGlobal=addToGlobal,
        )

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name}:  Z:{self.z}, W:{self.weight:<12.6e}, Label:{self.label}>"

    def getNaturalIsotopics(self):
        """Gets the natural isotopics root :py:class:`~elements.Element`.

        Gets the naturally occurring nuclides for this nuclide.

        Returns
        -------
        nuclides: list
            List of :py:class:`INuclides <INuclide>`.

        See Also
        --------
        :meth:`INuclide.getNaturalIsotopics`
        """
        return self.element.getNaturalIsotopics()

    def getMcnpId(self):
        """Gets the MCNP ID for this element.

        Returns
        -------
        id : str
            The MCNP ID e.g. ``1000``, ``92000``. Not zero-padded on the left.
        """
        return "{0:d}000".format(self.z)

    def getMcc2Id(self):
        """Return the MC2-2 nuclide identification label based on the ENDF/B-V.2 cross section library."""
        return self.mcc2id

    def getMcc3Id(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.1 cross section library."""
        return self.getMcc3IdEndfbVII1()

    def getMcc3IdEndfbVII0(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.0 cross section library."""
        return self.mcc3idEndfbVII0

    def getMcc3IdEndfbVII1(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.1 cross section library."""
        return self.mcc3idEndfbVII1

    def getSerpentId(self):
        """Gets the SERPENT ID for this natural nuclide.

        Returns
        -------
        id: str
            SERPENT ID: ``C-nat``, `Fe-nat``
        """
        return f"{self.element.symbol.capitalize()}-nat"

    def getEndfMatNum(self):
        """Get the ENDF mat number for this element."""
        if self.z != 6:
            runLog.warning(
                f"The only elemental in ENDF/B VII.1 is carbon. ENDF mat num was requested for the elemental {self} and"
                "will not be helpful for working with ENDF/B VII.1. Try to expandElementalsToIsotopics"
            )

        return str(self.z * 100)


class DummyNuclideBase(INuclide):
    """
    Represents a dummy/placeholder nuclide within the system.

    Notes
    -----
    This may be used to store mass from a depletion calculation, specifically in the instances where the burn chain is
    truncated.
    """

    def __init__(self, name, weight, addToGlobal=True):
        INuclide.__init__(
            self,
            element=elements.byName["Dummy"],
            a=0,
            state=0,
            weight=weight,
            abundance=0.0,
            halflife=np.inf,
            name=name,
            label="DMP" + name[4],
            addToGlobal=addToGlobal,
        )

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name}:  W:{self.weight:<12.6e}, Label:{self.label}>"

    def __hash__(self):
        return hash((self.a, self.z, self.state, self.weight))

    def __lt__(self, other):
        return (self.z, self.a, self.state, self.weight) < (
            other.z,
            other.a,
            other.state,
            other.weight,
        )

    def getNaturalIsotopics(self):
        """Gets the natural isotopics, an empty iterator.

        Gets the naturally occurring nuclides for this nuclide.

        Returns
        -------
        empty: iterator
            An empty generator

        See Also
        --------
        :meth:`INuclide.getNaturalIsotopics`
        """
        return
        yield

    def isHeavyMetal(self):
        return False

    def getMcc2Id(self):
        """Return the MC2-2 nuclide identification label based on the ENDF/B-V.2 cross section library."""
        return self.mcc2id

    def getMcc3Id(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.1 cross section library."""
        return self.getMcc3IdEndfbVII1()

    def getMcc3IdEndfbVII0(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.0 cross section library."""
        return self.mcc3idEndfbVII0

    def getMcc3IdEndfbVII1(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.1 cross section library."""
        return self.mcc3idEndfbVII1


class LumpNuclideBase(INuclide):
    """
    Represents a combination of many nuclides from `NuclideBases` into a single lumped nuclide.

    See Also
    --------
    armi.physics.neutronics.fissionProduct model:
        Describes what nuclides LumpNuclideBase is expend to.
    """

    def __init__(self, name, weight, addToGlobal=True):
        INuclide.__init__(
            self,
            element=elements.byName["LumpedFissionProduct"],
            a=0,
            state=0,
            weight=weight,
            abundance=0.0,
            halflife=np.inf,
            name=name,
            label=name[1:],
            addToGlobal=addToGlobal,
        )

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name}:  W:{self.weight:<12.6e}, Label:{self.label}>"

    def __hash__(self):
        return hash((self.a, self.z, self.state, self.weight))

    def __lt__(self, other):
        return (self.z, self.a, self.state, self.weight) < (
            other.z,
            other.a,
            other.state,
            other.weight,
        )

    def getNaturalIsotopics(self):
        """Gets the natural isotopics, an empty iterator.

        Gets the naturally occurring nuclides for this nuclide.

        Returns
        -------
        empty: iterator
            An empty generator

        See Also
        --------
        :meth:`INuclide.getNaturalIsotopics`
        """
        return
        yield

    def isHeavyMetal(self):
        return False

    def getMcc2Id(self):
        """Return the MC2-2 nuclide identification label based on the ENDF/B-V.2 cross section library."""
        return self.mcc2id

    def getMcc3Id(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.1 cross section library."""
        return self.getMcc3IdEndfbVII1()

    def getMcc3IdEndfbVII0(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.0 cross section library."""
        return self.mcc3idEndfbVII0

    def getMcc3IdEndfbVII1(self):
        """Return the MC2-3 nuclide identification label based on the ENDF/B-VII.1 cross section library."""
        return self.mcc3idEndfbVII1


def initReachableActiveNuclidesThroughBurnChain(nuclides, numberDensities, activeNuclides):
    """Pass through to NuclideBases.initReachableActiveNuclidesThroughBurnChain() for the global NuclideBases object."""
    global nuclideBases
    return nuclideBases.initReachableActiveNuclidesThroughBurnChain(nuclides, numberDensities, activeNuclides)


def getIsotopics(nucName):
    """Pass through to NuclideBases.getIsotopics() for the global NuclideBases object."""
    global nuclideBases
    return nuclideBases.getIsotopics(nucName)


def fromName(name):
    """Pass through to NuclideBases.fromName() for the global NuclideBases object."""
    global nuclideBases
    return nuclideBases.fromName(name)


def isMonoIsotopicElement(name):
    """Pass through to NuclideBases.isMonoIsotopicElement() for the global NuclideBases object."""
    global nuclideBases
    return nuclideBases.isMonoIsotopicElement(name)


def where(predicate):
    """Pass through to NuclideBases.where() for the global NuclideBases object."""
    global nuclideBases
    return nuclideBases.where(predicate)


def single(predicate):
    """Pass through to NuclideBases.single() for the global NuclideBases object."""
    global nuclideBases
    return nuclideBases.single(predicate)


def changeLabel(nuclideBase, newLabel):
    """Pass through to NuclideBases.changeLabel() for the global NuclideBases object."""
    global nuclideBases
    nuclideBases.changeLabel(nuclideBase, newLabel)


def getDepletableNuclides(activeNuclides, obj):
    """Get nuclides in this object that are in the burn chain."""
    return sorted(set(activeNuclides) & set(obj.getNuclides()))


def imposeBurnChain(burnChainStream):
    """Pass through to NuclideBases.imposeBurnChain() for the global NuclideBases object."""
    global nuclideBases
    nuclideBases.imposeBurnChain(burnChainStream)


def factory():
    """Pass through to NuclideBases.factory() for the global NuclideBases object."""
    global nuclideBases
    global burnChainImposed
    global instances
    global byName
    global byDBName
    global byLabel
    global byMcc2Id
    global byMcc3Id
    global byMcc3IdEndfbVII0
    global byMcc3IdEndfbVII1
    global byMcnpId
    global byAAAZZZSId

    nuclideBases = NuclideBases()

    instances = nuclideBases.instances
    burnChainImposed = nuclideBases.burnChainImposed
    byName = nuclideBases.byName
    byDBName = nuclideBases.byDBName
    byLabel = nuclideBases.byLabel
    byMcc2Id = nuclideBases.byMcc2Id
    byMcc3Id = nuclideBases.byMcc3Id  # for backwards compatibility. Identical to byMcc3IdEndfbVII1
    byMcc3IdEndfbVII0 = nuclideBases.byMcc3IdEndfbVII0
    byMcc3IdEndfbVII1 = nuclideBases.byMcc3IdEndfbVII1
    byMcnpId = nuclideBases.byMcnpId
    byAAAZZZSId = nuclideBases.byAAAZZZSId


def addNuclideBases():
    """Pass through to NuclideBases.addNuclideBases() for the global NuclideBases object."""
    global nuclideBases
    nuclideBases.addNuclideBases()


def readMCCNuclideData():
    """Pass through to NuclideBases.readMCCNuclideData() for the global NuclideBases object."""
    global nuclideBases
    nuclideBases.readMCCNuclideData()


def updateNuclideBasesForSpecialCases():
    """Pass through to NuclideBases.updateNuclideBasesForSpecialCases() for the global NuclideBases object."""
    global nuclideBases
    nuclideBases.updateNuclideBasesForSpecialCases()


def addGlobalNuclide(nuclide: NuclideBase):
    """Pass through to NuclideBases.addNuclide() for the global NuclideBases object."""
    global nuclideBases
    nuclideBases.addNuclide(nuclide)


def destroyGlobalNuclides():
    """Pass through to NuclideBases.clear() for the global NuclideBases object."""
    global nuclideBases
    nuclideBases.clear()


class NuclideBases:
    """
    A container for all the nuclide information in the simulation.

    By design, you would only expect to have one instance of this object in memory during a simulation.

    Attributes
    ----------
    burnChainImposed: bool
        Have we applied transmutation and decay data to each nuclide?
    instances: list[INuclide]
        A simple list of the nuclides in this class.
    byName: dict[str, INuclide]
        A dictionary of the nuclides in this class, keyed by name, e.g., "U235".
    byDBName: dict[str, INuclide]
        A dictionary of the nuclides in this class, keyed by database name, e.g., "nU235".
    byLabel: dict[str, INuclide]
        A dictionary of the nuclides in this class, keyed by label, e.g., "U235".
    byMcc2Id: dict[str, INuclide]
        A dictionary of the nuclides in this class, keyed by MC2-2 ID, e.g., "U-2355".
    byMcc3Id: dict[str, INuclide]
        A dictionary of the nuclides in this class, keyed by MC2-3 ID, e.g., "U235_7".
        (This exists for backwards compat. Identical to byMcc3IdEndfbVII1.)
    byMcc3IdEndfbVII0: dict[str, INuclide]
        A dictionary of the nuclides in this class, keyed by MC2-3 ID, e.g., "U235_7".
    byMcc3IdEndfbVII1: dict[str, INuclide]
        A dictionary of the nuclides in this class, keyed by MC2-3 ID, e.g., "U235_7".
    byMcnpId: dict[int, INuclide]
        A dictionary of the nuclides in this class, keyed by MCNP ID, e.g., 92235.
    byAAAZZZSId: dict[int, INuclide]
        A dictionary of the nuclides in this class, keyed by AAAZZZS, e.g., 2350920.
    nuclidesFile: str
        File path to the custom ARMI "nuclides.dat" file, containing a plain text description of all the nuclides to be
        modeled including: Z, number of neutrons, mass number, amu, natural abundance, half life and nu-bar and more.
    mccNuclidesFile: str
        File path to the "mcc-nuclides.yaml" file, containing nuclides defined by the MC2-2 and MC2-3 codes, with
        various ENDF/B-V mappings.
    """

    def __init__(self):
        self.burnChainImposed: bool = False
        self.instances: list[INuclide] = []
        self.byName: dict[str, INuclide] = {}
        self.byDBName: dict[str, INuclide] = {}
        self.byLabel: dict[str, INuclide] = {}
        self.byMcc2Id: dict[str, INuclide] = {}
        self.byMcc3Id: dict[str, INuclide] = {}
        self.byMcc3IdEndfbVII0: dict[str, INuclide] = {}
        self.byMcc3IdEndfbVII1: dict[str, INuclide] = {}
        self.byMcnpId: dict[int, INuclide] = {}
        self.byAAAZZZSId: dict[int, INuclide] = {}
        self.nuclidesFile: str = os.path.join(context.RES, "nuclides.dat")
        self.mccNuclidesFile: str = os.path.join(context.RES, "mcc-nuclides.yaml")
        self.factory()

    def clear(self):
        """Empty all the data containers in this object."""
        # grab all the globals
        global burnChainImposed
        global instances
        global byName
        global byDBName
        global byLabel
        global byMcc2Id
        global byMcc3Id
        global byMcc3IdEndfbVII0
        global byMcc3IdEndfbVII1
        global byMcnpId
        global byAAAZZZSId

        # reset the class attributes
        self.burnChainImposed = False
        self.instances = []
        self.byName = {}
        self.byDBName = {}
        self.byLabel = {}
        self.byMcc2Id = {}
        self.byMcc3Id = {}
        self.byMcc3IdEndfbVII0 = {}
        self.byMcc3IdEndfbVII1 = {}
        self.byMcnpId = {}
        self.byAAAZZZSId = {}

        # reset the globals
        instances = self.instances
        burnChainImposed = self.burnChainImposed
        byName = self.byName
        byDBName = self.byDBName
        byLabel = self.byLabel
        byMcc2Id = self.byMcc2Id
        byMcc3Id = self.byMcc3Id
        byMcc3IdEndfbVII0 = self.byMcc3IdEndfbVII0
        byMcc3IdEndfbVII1 = self.byMcc3IdEndfbVII1
        byMcnpId = self.byMcnpId
        byAAAZZZSId = self.byAAAZZZSId

    def addNuclide(self, nuclide: INuclide):
        """Add an element to the dictionaries in this class."""
        if nuclide.name in self.byName or nuclide.getDatabaseName() in self.byDBName or nuclide.label in self.byLabel:
            raise ValueError(f"{nuclide} has already been added.")

        self.instances.append(nuclide)
        self.byName[nuclide.name] = nuclide
        self.byDBName[nuclide.getDatabaseName()] = nuclide
        self.byLabel[nuclide.label] = nuclide

        # Add look-up based on the MCNP nuclide ID
        if isinstance(nuclide, IMcnpNuclide):
            if nuclide.getMcnpId() in self.byMcnpId:
                raise ValueError(f"{nuclide} with McnpId {nuclide.getMcnpId()} has already been added.")
            self.byMcnpId[nuclide.getMcnpId()] = nuclide

        if not isinstance(nuclide, (NaturalNuclideBase, LumpNuclideBase, DummyNuclideBase)):
            self.byAAAZZZSId[nuclide.getAAAZZZSId()] = nuclide

    def factory(self):
        """
        Reads data files to instantiate the :py:class:`INuclides <INuclide>`.

        Reads NIST, MC**2 and burn chain data files to instantiate the :py:class:`INuclides <INuclide>`. Also clears and
        fills in the class attibues: instances, byName, byLabel, byMcc3IdEndfbVII0, and byMcc3IdEndfbVII1. This method
        is automatically run upon initializing the class, hence it is not usually necessary to re-run it unless there is
        a change to the data files, which should not happen during run time, or a *bad* :py:class`INuclide` is created.

        Notes
        -----
        This cannot be run more than once. NuclideBase instances are used throughout the ARMI ecosystem and are even
        class attributes in some cases. Re-instantiating them would orphan any existing ones and break everything.
        """
        if len(self.instances) != 0:
            raise RuntimeError(
                "Nuclides are already initialized and cannot be re-initialized unless `nuclideBases.clear()` is called "
                "first."
            )

        self.addNuclideBases()
        self.__addNaturalNuclideBases()
        self.__addDummyNuclideBases()
        self.__addLumpedFissionProductNuclideBases()
        self.updateNuclideBasesForSpecialCases()
        self.readMCCNuclideData()
        self.__renormalizeNuclideToElementRelationship()
        self.__deriveElementalWeightsByNaturalNuclideAbundances()

        # reload the thermal scattering library with the new nuclideBases too
        from armi.nucDirectory import thermalScattering

        thermalScattering.factory(self.byName)

    def initReachableActiveNuclidesThroughBurnChain(self, nuclides, numberDensities, activeNuclides):
        """
        March through the depletion chain and find all nuclides that can be reached by depleting nuclides passed in.

        This limits depletion to the smallest set of nuclides that matters.

        Parameters
        ----------
        nuclides : np.array, dtype="S6"
            Starting array of nuclide names
        numberDensities : np.array, dtype=np.float64
            Starting array of number densities
        activeNuclides : OrderedSet
            Active nuclides defined on the reactor blueprints object. See: armi.reactor.blueprints.py
        """
        if not self.burnChainImposed:
            return nuclides, numberDensities

        missingActiveNuclides = set()
        memo = set()
        nucNames = [nucName.decode() for nucName in nuclides]
        difference = set(nucNames).difference(memo)
        while any(difference):
            newNucs = set()
            nuclide = difference.pop()
            memo.add(nuclide)
            # Skip the nuclide if it is not `active` in the burn-chain
            if nuclide not in activeNuclides:
                continue

            nuclideObj = self.byName[nuclide]

            for interaction in nuclideObj.trans + nuclideObj.decays:
                try:
                    # Interaction nuclides can only be added to the number density dictionary if they are a part of the
                    # user-defined active nuclides
                    productNuclide = interaction.getPreferredProduct(activeNuclides)
                    if productNuclide not in nucNames:
                        newNucs.add(productNuclide.encode())
                except KeyError:
                    # Keep track of the first production nuclide
                    missingActiveNuclides.add(interaction.productNuclides)

            # add the new nuclides to the number density arrays
            newNDens = np.zeros(len(newNucs), dtype=np.float64)
            nuclides = np.append(nuclides, list(newNucs))
            numberDensities = np.append(numberDensities, newNDens)

            nucNames = [nucName.decode() for nucName in nuclides]
            difference = set(nucNames).difference(memo)

        if self.burnChainImposed and missingActiveNuclides:
            self._failOnMissingActiveNuclides(missingActiveNuclides)

        return nuclides, numberDensities

    def _failOnMissingActiveNuclides(self, missingActiveNuclides):
        """Raise ValueError with notification of which nuclides to include in the burn-chain."""
        msg = "Missing active nuclides in loading file. Add the following nuclides:"
        for i, nucList in enumerate(missingActiveNuclides, 1):
            msg += f"\n {i} - "  # Index of
            for j, nuc in enumerate(nucList, 1):
                delimiter = " or " if j < len(nucList) else ""
                msg += f"{nuc}{delimiter}"

        raise ValueError(msg)

    def getIsotopics(self, nucName):
        """Expand elemental nuc name to isotopic nuc bases."""
        nb = self.byName[nucName]
        if isinstance(nb, (LumpNuclideBase, DummyNuclideBase)):
            # skip lumped fission products or dumps
            return []
        elif isinstance(nb, NaturalNuclideBase):
            isotopics = nb.getNaturalIsotopics()
        else:
            isotopics = [nb]

        return isotopics

    def fromName(self, name):
        """Return a nuclide from its name."""
        matches = [nn for nn in self.instances if nn.name == name]
        if len(matches) != 1:
            raise Exception(f"Too many or too few ({len(matches)}) matches for {name}")

        return matches[0]

    def isMonoIsotopicElement(self, name):
        """Return true if this is the only naturally occurring isotope of its element."""
        base = self.byName[name]
        return base.abundance > 0 and len([e for e in base.element.nuclides if e.abundance > 0]) == 1

    def where(self, predicate):
        """
        Return all :py:class:`INuclides <INuclide>` objects matching a condition.

        Returns an iterator of :py:class:`INuclides <INuclide>` matching the specified condition.

        Attributes
        ----------
        predicate: lambda
            A lambda, or function, accepting a :py:class:`INuclide` as a parameter

        Examples
        --------
        >>> from armi.nucDirectory.nuclideBases import NuclideBases
        >>> nuclideBases = NuclideBases()
        >>> [nn.name for nn in nuclideBases.where(lambda nb: 'Z' in nb.name)]
        ['ZN64', 'ZN66', 'ZN67', 'ZN68', 'ZN70', 'ZR90', 'ZR91', 'ZR92', 'ZR94', 'ZR96', 'ZR93', 'ZR95', 'ZR']
        >>> # in order to get length, convert to list
        >>> isomers90 = list(nuclideBases.where(lambda nb: nb.a == 95))
        >>> len(isomers90)
        3
        >>> for iso in isomers: print(iso)
        <NuclideBase MO95: Z:42, A:95, S:0, label:MO2N>
        <NuclideBase NB95: Z:41, A:95, S:0, label:NB2N>
        <NuclideBase ZR95: Z:40, A:95, S:0, label:ZR2N>
        """
        return filter(predicate, self.instances)

    def single(self, predicate):
        """
        Return a single :py:class:`INuclide` object meeting the specified condition.

        Similar to :py:func:`where`, this function uses a lambda input to filter the
        :py:attr:`INuclide instances <instances>`. If there is not 1 and only 1 match for the specified condition, an
        exception is raised.

        Examples
        --------
        >>> from armi.nucDirectory import nuclideBases
        >>> nuclideBases.single(lambda nb: nb.name == 'C')
        <NaturalNuclideBase C: Z:6, w:12.0107358968, label:C>
        >>> nuclideBases.single(lambda nb: nb.z == 95 and nb.a == 242 and nb.state == 1)
        <NuclideBase AM242M: Z:95, A:242, S:1, label:AM4C>
        """
        matches = [nuc for nuc in self.instances if predicate(nuc)]
        if len(matches) != 1:
            raise IndexError(
                "Expected single match, but got {} matches:\n  {}".format(
                    len(matches), "\n  ".join(str(mo) for mo in matches)
                )
            )

        return matches[0]

    def changeLabel(self, nuclideBase, newLabel):
        """
        Updates a nuclide label and modifies the ``byLabel`` look-up dictionary.

        Notes
        -----
        Since nuclide objects are defined and stored globally, any change to the attributes will be maintained.
        """
        nuclideBase.label = newLabel
        self.byLabel[newLabel] = nuclideBase

    def imposeBurnChain(self, burnChainStream):
        """
        Apply transmutation and decay information to each nuclide.

        Notes
        -----
        You cannot impose a burn chain twice. Doing so would require that you clean out the transmutations and decays
        from all the module-level nuclide bases, which generally requires that you rebuild them. But rebuilding those is
        not an option because some of them get set as class-level attributes and would be orphaned. If a need to change
        burn chains mid-run re-arises, then a better nuclideBase-level burnchain cleanup should be implemented so the
        objects don't have to change identity.

        See Also
        --------
        armi.nucDirectory.transmutations : describes file format
        """
        if self.burnChainImposed:
            # The only time this should happen is if in a unit test that has already processed conftest.py and is now
            # building a Case that also imposes this.
            runLog.warning("Burn chain already imposed. Skipping reimposition.")
            return

        self.burnChainImposed = True
        global burnChainImposed
        burnChainImposed = True
        yaml = YAML(typ="rt")
        yaml.allow_duplicate_keys = False
        burnData = yaml.load(burnChainStream)

        for nucName, burnInfo in burnData.items():
            nuclide = self.byName[nucName]
            # think of this protected stuff as "module level protection" rather than class.
            nuclide._processBurnData(burnInfo)

    def addNuclideBases(self):
        """
        Read natural abundances of any natural nuclides.

        This adjusts already-existing NuclideBases and Elements with the new information.

        .. impl:: Separating natural abundance data from code.
            :id: I_ARMI_ND_DATA0
            :implements: R_ARMI_ND_DATA

            This function reads the ``nuclides.dat`` file from the ARMI resources folder. This file contains metadata
            for 4,614 nuclides, including number of protons, number of neutrons, atomic number, excited state, element
            symbol, atomic mass, natural abundance, half-life, and spontaneous fission yield. The data in
            ``nuclides.dat`` have been collected from multiple different sources; the references are given in comments
            at the top of that file.
        """
        with open(self.nuclidesFile, "r") as f:
            for line in f:
                # Skip header lines
                if line.startswith("#") or line.startswith("Z"):
                    continue
                lineData = line.split()
                _z = int(lineData[0])
                _n = int(lineData[1])
                a = int(lineData[2])
                state = int(lineData[3])
                sym = lineData[4].upper()
                mass = float(lineData[5])
                abun = float(lineData[6])
                halflife = lineData[7]
                if halflife == "inf":
                    halflife = np.inf
                else:
                    halflife = float(halflife)
                nuSF = float(lineData[8])

                element = elements.bySymbol[sym]
                nb = NuclideBase(element, a, mass, abun, state, halflife, addToGlobal=False)
                nb.nuSF = nuSF
                self.addNuclide(nb)

    def __addNaturalNuclideBases(self):
        """Generates a complete set of nuclide bases for each naturally occurring element."""
        for element in elements.byZ.values():
            if element.symbol not in self.byName:
                if element.isNaturallyOccurring():
                    self.addNuclide(NaturalNuclideBase(element.symbol, element, addToGlobal=False))

    def __addDummyNuclideBases(self):
        """
        Generates a set of dummy nuclides.

        Notes
        -----
        These nuclides can be used to truncate a depletion / burn-up chain within the MC2 program.
        """
        self.addNuclide(DummyNuclideBase(name="DUMP1", weight=10.0, addToGlobal=False))
        self.addNuclide(DummyNuclideBase(name="DUMP2", weight=240.0, addToGlobal=False))

    def __addLumpedFissionProductNuclideBases(self):
        """Generates a set of nuclides for use as lumped fission products."""
        self.addNuclide(LumpNuclideBase(name="LFP35", weight=233.273, addToGlobal=False))
        self.addNuclide(LumpNuclideBase(name="LFP38", weight=235.78, addToGlobal=False))
        self.addNuclide(LumpNuclideBase(name="LFP39", weight=236.898, addToGlobal=False))
        self.addNuclide(LumpNuclideBase(name="LFP40", weight=237.7, addToGlobal=False))
        self.addNuclide(LumpNuclideBase(name="LFP41", weight=238.812, addToGlobal=False))
        self.addNuclide(LumpNuclideBase(name="LREGN", weight=1.0, addToGlobal=False))

    def readMCCNuclideData(self):
        r"""Read in the label data for the MC2-2 and MC2-3 cross section codes to the nuclide bases.

        .. impl:: Separating MCC data from code.
            :id: I_ARMI_ND_DATA1
            :implements: R_ARMI_ND_DATA

            This function reads the mcc-nuclides.yaml file from the ARMI resources folder. This file contains the
            MC\ :sup:`2`-2 ID (from ENDF/B-V.2) and MC\ :sup:`2`-3 ID (from ENDF/B-VII.0) for all nuclides in
            MC\ :sup:`2`. The ``mcc2id``, ``mcc3idEndfVII0``, and  ``mcc3idEndfVII1`` attributes of each
            :py:class:`NuclideBase <armi.nucDirectory.nuclideBases.NuclideBase>` instance are updated as the data is
            read, and the global dictionaries ``byMcc2Id`` ``byMcc3IdEndfVII0`` and ``byMcc3IdEndfVII1`` are populated
            with the nuclide bases keyed by their corresponding ID for each code.
        """
        with open(self.mccNuclidesFile, "r") as f:
            yaml = YAML(typ="rt")
            nuclides = yaml.load(f)

        for n in nuclides:
            nb = self.byName[n]
            mcc2id = nuclides[n]["ENDF/B-V.2"]
            mcc3idEndfbVII0 = nuclides[n]["ENDF/B-VII.0"]
            mcc3idEndfbVII1 = nuclides[n]["ENDF/B-VII.1"]
            if mcc2id is not None:
                nb.mcc2id = mcc2id
                self.byMcc2Id[nb.getMcc2Id()] = nb
            if mcc3idEndfbVII0 is not None:
                nb.mcc3idEndfbVII0 = mcc3idEndfbVII0
                self.byMcc3IdEndfbVII0[nb.getMcc3IdEndfbVII0()] = nb
            if mcc3idEndfbVII1 is not None:
                nb.mcc3idEndfbVII1 = mcc3idEndfbVII1
                self.byMcc3IdEndfbVII1[nb.getMcc3IdEndfbVII1()] = nb

        # Have the byMcc3Id dictionary be VII.1 IDs.
        self.byMcc3Id = self.byMcc3IdEndfbVII1

    def updateNuclideBasesForSpecialCases(self):
        """
        Update the nuclide bases for special case name changes.

        .. impl:: The special case name Am242g is supported.
            :id: I_ARMI_ND_ISOTOPES6
            :implements: R_ARMI_ND_ISOTOPES

            This function updates the keys for the :py:class:`NuclideBase <armi.nucDirectory.nuclideBases.NuclideBase>`
            instances for Am-242m and Am-242 in the ``byName`` and ``byDBName`` global dictionaries. This function
            associates the more common isomer Am-242m with the name "AM242", and uses "AM242G" to denote the ground
            state.

        Notes
        -----
        This function is specifically added to change the definition of `AM242` to refer to its metastable isomer,
        `AM242M` by default. `AM242M` is most common isomer of `AM242` and is typically the desired isomer when being
        requested rather than than the ground state (i.e., S=0) of `AM242`.
        """
        # Change the name of `AM242` to specific represent its ground state.
        am242g = self.byName["AM242"]
        am242g.name = "AM242G"
        self.byName["AM242G"] = am242g
        self.byDBName[self.byName["AM242G"].getDatabaseName()] = am242g

        # Update the pointer of `AM242` to refer to `AM242M`.
        am242m = self.byName["AM242M"]
        self.byName["AM242"] = am242m
        self.byDBName["nAm242"] = am242m
        self.byDBName[self.byName["AM242"].getDatabaseName()] = am242m

    def __renormalizeNuclideToElementRelationship(self):
        """Fill in the missing element data for each nuclide."""
        for nuc in self.instances:
            if nuc.element is None:
                nuc.element = elements.byZ[nuc.z]
                nuc.element.append(nuc)

    def __deriveElementalWeightsByNaturalNuclideAbundances(self):
        """Derives and sets the standard atomic weights for each element that has naturally occurring nuclides."""
        for element in elements.byName.values():
            numer = 0.0
            denom = 0.0
            for nb in element.getNaturalIsotopics():
                numer += nb.weight * nb.abundance
                denom += nb.abundance

            if denom:
                element.standardWeight = numer / denom


factory()
