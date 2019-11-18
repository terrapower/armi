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
The nuclideBases module classes for providing *base* nuclide information, such as
Z, A, state and energy release.

The nuclide class structure is outlined in :ref:`nuclide-bases-class-diagram`.

.. _nuclide-bases-class-diagram:

.. pyreverse:: armi.nucDirectory.nuclideBases
    :align: center
    :width: 90%

    Class inheritance diagram for :py:class:`INuclide`.

See Also
--------
armi.nucDirectory.nuclideBases._addNuclideToIndices : builds this object
    
Examples
--------
>>> nuclideBases.byName['U235']
<NuclideBase U235: Z:92, A:235, S:0, label:U_6J, mc2id:U-2355>

>>> nuclideBases.byLabel['U_6J']
<NuclideBase U235: Z:92, A:235, S:0, label:U_6J, mc2id:U-2355>

Retrieve U-235 by the MC**2-v2 ID.

>>> nuclideBases.byMccId['U-2355']
<NuclideBase U235: Z:92, A:235, S:0, label:U_6J, mc2id:U-2355>
U235_7

Can get the same nuclide by the MC**2-v3 ID.

>>> nuclideBases.byMccId['U235_7']
<NuclideBase U235: Z:92, A:235, S:0, label:U_6J, mc2id:U-2355>

Retrieve U-235 by the MCNP ID.

>>> nuclideBases.byMcnpId['92235']
<NuclideBase U235: Z:92, A:235, S:0, label:U235, mc2id:U-2355>
U235_7

Retrieve U-235 by the AAAZZZS ID.

>>> nuclideBases.byAAAZZZSId['2350920']
<NuclideBase U235: Z:92, A:235, S:0, label:U235, mc2id:U-2355>
U235_7


Table of All nuclides:

.. exec::
    from tabulate import tabulate
    from armi.nucDirectory import nuclideBases

    attributes = [ 'type',
                    'name',
                    'a',
                    'z',
                    'state',
                    'weight',
                    'label',
                    'mc2id',
                    'getMcc3Id']

    def getAttributes(nuc):
        return [
            ':py:class:`~armi.nucDirectory.nuclideBases.{}`'.format(nuc.__class__.__name__),
            '``{}``'.format(nuc.name),
            '``{}``'.format(nuc.a),
            '``{}``'.format(nuc.z),
            '``{}``'.format(nuc.state),
            '``{}``'.format(nuc.weight),
            '``{}``'.format(nuc.label),
            '``{}``'.format(nuc.mc2id),
            '``{}``'.format(nuc.getMcc3Id()),
        ]

    sortedNucs = sorted(nuclideBases.instances, key=lambda nb: (nb.z, nb.a))

    return create_table(tabulate(tabular_data=[getAttributes(nuc) for nuc in sortedNucs],
                                 headers=attributes,
                                 tablefmt='rst'),
                        caption='List of nulides')

"""

import os
import yaml
import collections

import armi
from armi.nucDirectory import elements
from armi.nucDirectory import transmutations
from armi.localization import errors
from armi import runLog
from armi.utils.units import HEAVY_METAL_CUTOFF_Z

# used to prevent multiple applications of burn chains, which would snowball
# unphysically. This is a bit of a crutch for the global state that is the nuclide
# directory.
_burnChainImposed = False

instances = []

# Dictionary of INuclides by the INuclide.name for fast indexing
byName = {}

byDBName = {}

byLabel = {}

byMccId = {}

byMcnpId = {}


byAAAZZZSId = {}

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


def isotopes(z):
    return elements.byZ[z].nuclideBases


def getIsotopics(nucName):
    """Expand elemental nuc name to isotopic nuc bases."""
    nb = byName[nucName]
    if isinstance(nb, (LumpNuclideBase, DummyNuclideBase)):
        # skip lumped fission products or dumps
        return []
    elif isinstance(nb, NaturalNuclideBase):
        isotopics = nb.getNaturalIsotopics()
    else:
        isotopics = [nb]
    return isotopics


def fromName(name):
    r"""Get a nuclide from its name.
    """
    matches = [nn for nn in instances if nn.name == name]
    if len(matches) != 1:
        raise errors.nuclides_TooManyOrTooFew_number_MatchesForNuclide_name(
            len(matches), name
        )
    return matches[0]


def nucNameFromDBName(dbName):
    """
    Return the nuc name of the given param name if the param name has a corresponding nuc name.

    If there is no nuc with that param name return None.
    """
    try:
        return byDBName[dbName].name
    except KeyError:
        return None


def isMonoIsotopicElement(name):
    """Return true if this is the only naturally occurring isotope of its element"""
    base = byName[name]
    return (
        base.abundance > 0
        and len([e for e in base.element.nuclideBases if e.abundance > 0]) == 1
    )


def where(predicate):
    r"""Get all :py:class:`INuclides <INuclide>` matching a condition.

    Returns an iterator of :py:class:`INuclides <INuclide>` matching the specified condition.

    Attributes
    ----------

    predicate: lambda
        A lambda, or function, accepting a :py:class:`INuclide` as a parameter

    Examples
    --------

    >>> from armi.nucDirectory import nuclideBases
    >>> [nn.name for nn in nuclideBases.where(lambda nb: 'Z' in nb.name)]
    ['ZN64', 'ZN66', 'ZN67', 'ZN68', 'ZN70', 'ZR90', 'ZR91', 'ZR92', 'ZR94', 'ZR96', 'ZR93', 'ZR95', 'ZR']

    >>> # in order to get length, convert to list
    >>> isomers90 = list(nuclideBases.where(lambda nb: nb.a == 95))
    >>> len(isomers90)
    3
    >>> for iso in isomers: print(iso)
    <NuclideBase MO95: Z:42, A:95, S:0, label:MO2N, mc2id:MO95 5>
    <NuclideBase NB95: Z:41, A:95, S:0, label:NB2N, mc2id:NB95 5>
    <NuclideBase ZR95: Z:40, A:95, S:0, label:ZR2N, mc2id:ZR95 5>

    """
    for nuc in instances:
        if predicate(nuc):
            yield (nuc)


def single(predicate):
    r"""Get a single :py:class:`INuclide` meeting the specified condition.

    Similar to :py:func:`where`, this function uses a lambda input to filter
    the :py:attr:`INuclide instances <instances>`. If there is not 1 and only
    1 match for the specified condition, an exception is raised.

    Examples
    --------

    >>> from armi.nucDirectory import nuclideBases
    >>> nuclideBases.single(lambda nb: nb.name == 'C')
    <NaturalNuclideBase C: Z:6, w:12.0107358968, label:C, mc2id:C    5>

    >>> nuclideBases.single(lambda nb: nb.z == 95 and nb.a == 242 and nb.state == 1)
    <NuclideBase AM242M: Z:95, A:242, S:1, label:AM4C, mc2id:AM242M>

    """
    matches = [nuc for nuc in instances if predicate(nuc)]
    if len(matches) != 1:
        raise errors.general_single_TooManyOrTooFewMatchesFor(matches)
    return matches[0]


def changeLabel(nuclideBase, newLabel):
    nuclideBase.label = newLabel
    byLabel[newLabel] = nuclideBase


def __readRiplNuclides():
    """
    Initialize all nuclides with experimentally-measured masses.

    This includes roughly 4000 nuclides and should represent anything we ever
    want to model. This builds the large set of NuclideBases available.
    
    RIPL is the Reference Input Parameter Library (RIPL-3), which can be found at 
    https://www-nds.iaea.org/RIPL-3/. 
    """
    from armi.nuclearDataIO import ripl

    elements.clearNuclideBases()
    for z, a, symbol, mass, _err in ripl.readFRDMMassFile(
        os.path.join(armi.context.RES, "ripl-mass-frdm95.dat")
    ):
        if z == 0 and a == 1:
            # skip the neutron
            continue
        element = elements.bySymbol[symbol.upper()]
        NuclideBase(element, a, mass, 0, 0, None)


def __readRiplAbundance():
    """
    Read natural abundances of any natural nuclides.

    This adjusts already-existing NuclideBases and Elements with the new information.
    """
    from armi.nuclearDataIO import ripl

    with open(os.path.join(armi.context.RES, "ripl-abundance.dat")) as ripl_abundance:
        for _z, a, sym, percent, _err in ripl.readAbundanceFile(ripl_abundance):
            nb = byName[sym + "{}".format(a)]
            nb.abundance = percent / 100.0


def __readMc2Nuclides():
    """
    Read nuclides as defined in the MC2 library.

    Notes
    -----
    This assigns MC2 labels and often adds metastable versions of nuclides
    that have already been added from RIPL.
    """
    with open(os.path.join(armi.context.RES, "mc2Nuclides.yaml"), "r") as mc2Nucs:
        mc2Nuclides = yaml.load(mc2Nucs, Loader=yaml.FullLoader)
    # now add the mc2 specific nuclideBases, and correct the mc2Ids when a > 0 and state = 0
    for name, data in mc2Nuclides.items():
        z = data["z"]
        a = data["a"]
        state = data["state"]
        iid = data["id"]

        element = elements.byZ[z] if z > 0 else None
        if z == 0:
            weight = data["weight"]
            if "LFP" in name:
                LumpNuclideBase(name, z, iid, weight)
            # Allows names like REGXX to be in the ISOTXS file (macroscopic/region xs considered as 'lumped' parameters)
            elif "LREGN" in name:
                LumpNuclideBase(name, z, iid, weight)
            else:
                DummyNuclideBase(name, iid, weight)
        elif a == 0:
            NaturalNuclideBase(name, element, iid)
        else:
            # state == 0 nuclide *should* already exist
            needToAdd = True
            if state == 0:
                clide = [
                    nn
                    for nn in element.nuclideBases
                    if nn.z == z and nn.a == a and nn.state == state
                ]
                if len(clide) > 1:
                    raise ValueError(
                        "More than 1 nuclide meets specific criteria: {}".format(clide)
                    )
                needToAdd = len(clide) == 0
                if not needToAdd and iid:
                    clide[0].mc2id = iid
                    byMccId[iid] = clide[0]
            # state != 0, nuclide should not exist, create it
            if needToAdd:
                NuclideBase(
                    element, a, element.standardWeight or float(a), 0.0, state, iid
                )

    # special case AM242. Treat the metastable as the main one and specify ground state as AM242G.
    # This is a typical approach in many reactor codes including MCNP since you almost always
    # are interested in AM242M.
    am242g = byName["AM242"]
    am242g.name = "AM242G"
    am242 = byName["AM242M"]
    am242.name = "AM242"
    am242.weight = am242g.weight  # use RIPL mass for metastable too
    byName[am242.name] = am242
    byDBName[am242.getDatabaseName()] = am242
    byName["AM242G"] = am242g
    byDBName[byName["AM242G"].getDatabaseName()] = am242g


def getDepletableNuclides(activeNuclides, obj):
    """Get nuclides in this object that are in the burn chain."""
    return sorted(set(activeNuclides) & set(obj.getNuclides()))


def imposeBurnChain(burnChainStream):
    """
    Apply transmutation and decay information to each nuclide.

    See Also
    --------
    armi.nucDirectory.transmutations : describes file format
    """
    global _burnChainImposed  # pylint: disable=global-statement
    if _burnChainImposed:
        # We cannot apply more than one burn chain at a time, as this would lead to
        # unphysical traits in the nuclide directory (e.g., duplicate decays and
        # transmutations)
        runLog.warning(
            "Applying a burn chain when one has already been applied; "
            "resetting the nuclide directory to it's default state first."
        )
        factory(True)
    _burnChainImposed = True
    burnData = yaml.load(burnChainStream, Loader=yaml.FullLoader)
    for nucName, burnInfo in burnData.items():
        nuclide = byName[nucName]
        # think of this protected stuff as "module level protection" rather than class.
        nuclide._processBurnData(burnInfo)  # pylint: disable=protected-access


def factory(force=False):
    r"""Reads data files to instantiate the :py:class:`INuclides <INuclide>`.

    Reads NIST, MC**2 and burn chain data files to instantiate the :py:class:`INuclides <INuclide>`.
    Also clears and fills in the
    :py:data:`~armi.nucDirectory.nuclideBases.instances`,
    :py:data:`byName`, :py:attr:`byLabel`, and
    :py:data:`byMccId` module attributes. This method is automatically run upon
    loading the module, hence it is not usually necessary to re-run it unless there is a
    change to the data files, which should not happen during run time, or a *bad*
    :py:class`INuclide` is created.

    Notes
    -----
    Nuclide labels from MC2-2, MC2-3, and MCNP are currently handled directly.
    Moving forward, we plan to implement a more generic labeling system so that
    plugins can provide code-specific nuclide labels in a more extensible fashion.

    Attributes
    ----------
    force: bool, optional
        If True, forces the reinstantiation of all :py:class:`INuclides`.
        Any :py:class:`Nuclides <armi.nucDirectory.nuclide.Nuclde>` objects referring to the
        original :py:class:`INuclide` will not update their references, and will probably fail.
    """
    # this intentionally clears and reinstantiates all nuclideBases
    global instances  # pylint: disable=global-statement
    global _burnChainImposed  # pylint: disable=global-statement
    if force or len(instances) == 0:
        _burnChainImposed = False
        # make sure the elements actually exist...
        elements.factory()
        del instances[:]  # there is no .clear() for a list
        byName.clear()
        byDBName.clear()
        byLabel.clear()
        byMccId.clear()
        byMcnpId.clear()
        byAAAZZZSId.clear()
        __readRiplNuclides()
        __readRiplAbundance()
        # load the mc2Nuclide.json file. This will be used to supply nuclide IDs
        __readMc2Nuclides()
        _completeNaturalNuclideBases()
        elements.deriveNaturalWeights()


def _completeNaturalNuclideBases():
    """
    After natural nuclide bases are loaded for mc2, fill in missing ones.

    This is important for libraries that have elementals that differ
    from MC2.
    """
    for element in elements.byZ.values():
        if element.symbol not in byName:
            if element.z <= 92:
                NaturalNuclideBase(element.symbol, element, None)


def _renormalizeElementRelationship():
    for nuc in instances:
        if nuc.element is not None:
            nuc.element = elements.byZ[nuc.z]
            nuc.element.append(nuc)


elements.nuclideRenormalization = _renormalizeElementRelationship


def _addNuclideToIndices(nuc):
    instances.append(nuc)
    byName[nuc.name] = nuc
    byDBName[nuc.getDatabaseName()] = nuc
    byLabel[nuc.label] = nuc
    if nuc.mc2id:
        byMccId[nuc.mc2id] = nuc
    mc3 = nuc.getMcc3Id()
    if mc3:
        byMccId[mc3] = nuc
    if isinstance(nuc, IMcnpNuclide):
        byMcnpId[nuc.getMcnpId()] = nuc
        try:
            byAAAZZZSId[nuc.getAAAZZZSId()] = nuc
        except AttributeError:
            pass


class IMcnpNuclide(object):
    """Interface which defines the contract for getMcnpId.
    """

    def getMcnpId(self):
        """
        Abstract implementation of get MCNP ID.
        """
        raise NotImplementedError

    def getAAAZZZSId(self):
        """
        Abstract implementation of get AAAZZZS ID (used in cinder, etc).
        """
        raise NotImplementedError


class NuclideInterface(object):
    """An abstract nuclide implementation which defining various methods required for a nuclide object."""

    def getDatabaseName(self):
        """Get the name of the nuclide used in the database (i.e. "nPu239")"""
        raise NotImplementedError

    def getDecay(self, decayType):
        r"""Get a :py:class:`~armi.nucDirectory.transmutations.DecayMode`.

        Retrieve the first :py:class:`~armi.nucDirectory.transmutations.DecayMode`
        matching the specified decType.

        Parameters
        ----------
        decType: str
            Name of decay mode, e.g. 'sf', 'alpha'

        Returns
        -------
        decay : :py:class:`DecayModes <armi.nucDirectory.transmutations.DecayMode>`
        """
        raise NotImplementedError

    def getMcc3Id(self):
        """Get the MC**2-v3 nuclide ID (i.e. "PU2397")"""
        raise NotImplementedError

    def getSerpentId(self):
        """Get the SERPENT nuclide ID (i.e. "Pu-239", "Te-129m")"""
        raise NotImplementedError

    def getNaturalIsotopics(self):
        r"""Gets the natural isotopics root :py:class:`~elements.Element`.

        Gets the naturally occurring nuclides for this nuclide.

        Returns
        -------
        nuclides: list
            List of :py:class:`INuclides <INuclide>`
        """
        raise NotImplementedError

    def isFissile(self):
        """Get boolean value indicating whether this nuclide is fissile."""
        raise NotImplementedError

    def isHeavyMetal(self):
        """Get boolean value indicating whether this nuclide is a heavy metal."""
        raise NotImplementedError


class NuclideWrapper(NuclideInterface):
    """A nuclide wrapper class, used as a base class for nuclear data file nuclides"""

    def __init__(self, container, key):
        self._base = None
        self.container = container
        self.containerKey = key
        self.nucLabel = key[:-2]

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, self.containerKey)

    def __format__(self, format_spec):
        return format_spec.format(repr(self))

    @property
    def name(self):
        """Get the underlying nuclide's name (i.e. "PU239").

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
        r"""Get a :py:class:`~armi.nucDirectory.transmutations.DecayMode`.

        Retrieve the first :py:class:`~armi.nucDirectory.transmutations.DecayMode`
        matching the specified decType.

        Parameters
        ----------
        decType: str
            Name of decay mode e.g. 'sf', 'alpha'

        Returns
        -------
        decay : :py:class:`DecayModes <armi.nucDirectory.transmutations.DecayMode>`
        """
        return self._base.getDecay(decayType)

    def getMcc3Id(self):
        """Get the MC**2-v3 nuclide ID (i.e. "PU2397")"""
        return self._base.getMcc3Id()

    def getNaturalIsotopics(self):
        """Get the natural isotopics of the underlying nuclide.."""
        return self._base.getNaturalIsotopics()

    def isFissile(self):
        """Get boolean indicating whether or not the underlying nuclide is fissle."""
        return self._base.isFissile()

    def isHeavyMetal(self):
        """Get boolean indicating whether or not the underlying nuclide is a heavy metal."""
        return self._base.isHeavyMetal()


class INuclide(NuclideInterface):
    r"""
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
        Isotopic fraction of a naturally occurring nuclide. The sum of all nuclide
        abundances for a naturally occurring element should be 1.0. This is atom
        fraction, not mass fraction.

    name : str
        ARMI's unique name for the given nuclide.

    label : str
        ARMI's unique 4 character label for the nuclide.
        These are not human readable, but do not lose any information.
        The label is effectively the
        :attr:`Element.symbol `armi.nucDirectory.elements.Element.symbol`
        padded to two characters, plus the mass number (A) in base-26 (0-9, A-Z).
        Additional support for meta-states is provided by adding 100 * the state
        to the mass number (A).

    mc2id : str
        The unique id used by MC**2 version 2.

    nuSF : float
        Neutrons released per spontaneous fission.
        This should probably be moved at some point.
    """

    fissile = ["U235", "PU239", "PU241", "AM242M", "CM244", "U233"]
    TRANSMUTATION = "transmutation"
    DECAY = "decay"
    SPONTANEOUS_FISSION = "nuSF"

    def __init__(self, z, a, state, weight, abundance, name, label, mc2id):
        r"""
        Create an instance of an INuclide.

        .. warning::
            Do not call this constructor directly; use the factory instead.

        """
        self.z = z
        self.a = a
        self.state = state
        self.decays = []
        self.trans = []
        self.weight = weight
        self.abundance = abundance
        self.name = name
        self.label = label
        self.element = self.__dict__.get("element", None)
        self.mc2id = mc2id
        self.nuSF = 0.0

        # depletion-ready attributes
        _addNuclideToIndices(self)

    def __hash__(self):
        return hash((self.a, self.z, self.state))

    def __reduce__(self):
        return fromName, (self.name,)

    def __lt__(self, other):
        return (self.z, self.a, self.state) < (other.z, other.a, other.state)

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
                    "Improperly defined ``burn-chain`` of {}. {} should be a single burn type.".format(
                        self, nuclideBurnCategory.keys()
                    )
                )
            nuclideBurnType = list(nuclideBurnCategory.keys())[0]
            if nuclideBurnType == self.TRANSMUTATION:
                self.trans.append(
                    transmutations.Transmutation(
                        self, nuclideBurnCategory[nuclideBurnType]
                    )
                )
            elif nuclideBurnType == self.DECAY:
                self.decays.append(
                    transmutations.DecayMode(self, nuclideBurnCategory[nuclideBurnType])
                )
            elif nuclideBurnType == self.SPONTANEOUS_FISSION:
                self.nuSF = nuclideBurnCategory[nuclideBurnType]
            else:
                raise Exception(
                    "Undefined Burn Data {} for {}. Expected {}, {}, or {}."
                    "".format(
                        nuclideBurnType,
                        self,
                        self.TRANSMUTATION,
                        self.DECAY,
                        self.SPONTANEOUS_FISSION,
                    )
                )

    def getDecay(self, decayType):
        r"""Get a :py:class:`~armi.nucDirectory.transmutations.DecayMode`.

        Retrieve the first :py:class:`~armi.nucDirectory.transmutations.DecayMode`
        matching the specified decType.

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

    def isFissile(self):
        r"""Determine if the nuclide is fissile.

        Determines if the nuclide is fissle.

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
        """Get the name of the nuclide used in the database (i.e. "nPu239")"""
        return "n{}".format(self.name.capitalize())

    def getMcc3Id(self):
        r"""Gets the MC**2-v3 nuclide ID.

        Abstract method, see concrete types for implementation.

        See Also
        --------
        :meth:`NuclideBase.getMcc3Id`
        :meth:`NaturalNuclideBase.getMcc3Id`
        :meth:`LumpNuclideBase.getMcc3Id`
        :meth:`DummyNuclideBase.getMcc3Id`
        """
        raise NotImplementedError

    def isHeavyMetal(self):
        return self.z > HEAVY_METAL_CUTOFF_Z


class NuclideBase(INuclide, IMcnpNuclide):
    """
    Represents an individual nuclide

    This is meant to be a lookup class, with just one per unique nuclide
    in the problem. That means there won't be copies of these in every block
    that has these nuclideBases.

    """

    def __init__(self, element, a, weight, abundance, state, mc2id):
        IMcnpNuclide.__init__(self)
        self.element = element
        self.element.append(self)
        INuclide.__init__(
            self,
            element.z,
            a,
            state,
            weight,
            abundance,
            NuclideBase._createName(element, a, state),
            NuclideBase._createLabel(element, a, state),
            mc2id,
        )

    def __repr__(self):
        return "<NuclideBase {}: Z:{}, A:{}, S:{}, label:{}, mc2id:{}>".format(
            self.name, self.z, self.a, self.state, self.label, self.mc2id
        )

    @staticmethod
    def _createName(element, a, state):
        # state is either 0 or 1, so some nuclides will get an M at the end
        metaChar = ["", "M"]
        return "{}{}{}".format(element.symbol, a, metaChar[state])

    @staticmethod
    def _createLabel(element, a, state):
        """
        Make label for nuclide base.

        The logic causes labels for things with A<10 to be zero padded like H03 or tritium
        instead of H3. This avoids the metastable tritium collision which would look
        like elemental HE. It also allows things like MO100 to be held within 4 characters,
        which is a constraint of the ISOTXS format if we append 2 characters for XS type.
        """
        # len(e.symbol) is 1 or 2 => a % (either 1000 or 100)
        #                         => gives exact a, or last two digits.
        # the division by 10 removes the last digit.
        firstTwoDigits = (a % (10 ** (4 - len(element.symbol)))) // 10
        # the last digit is either 0-9 if state=0, or A-J if state=1
        lastDigit = "0123456789" "ABCDEFGHIJ"[(a % 10) + state * 10]

        return "{}{}{}".format(element.symbol, firstTwoDigits, lastDigit)

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

    def getMcc3Id(self):
        """Gets the MC**2-v3 nuclide ID.

        Returns
        -------
        name: str
            The MC**2 ID: ``AM42M7``, ``B10__7``, etc.

        See Also
        --------
        :meth:`INuclide.getMcc3Id`
        """
        base = ""
        if self.state > 0:
            base = "{}{}M".format(self.element.symbol, self.a % 100)
        else:
            base = "{}{}".format(self.element.symbol, self.a)
        return "{:_<5}7".format(base)

    def getMcnpId(self):
        """
        Gets the MCNP label for this nuclide

        Returns
        -------
        id : str
            The MCNP ID e.g. ``92235``, ``94239``, ``6000``

        """
        z, a = self.z, self.a

        if z == 95 and a == 242:
            # Am242 has special rules
            if self.state != 1:
                # MCNP uses base state for the common metastable state AM242M , so AM242M is just 95242
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
        Gets the AAAZZZS label for this nuclide

        Returns
        -------
        id : str
            The MCNP ID e.g. ``2350920``, ``2390940``, ``1200600``

        """

        aaa = "{}".format(self.a)
        zzz = "{0:03}".format(self.z)
        s = "1" if self.state > 0 else "0"

        return "{}{}{}".format(aaa, zzz, s)

    def getSerpentId(self):
        """
        Returns the SERPENT style ID for this nuclide.

        Returns
        -------
        id: str
            The ID of this nuclide based on it's elemental name, weight,
            and state, eg ``U-235``, ``Te-129m``,
        """
        symbol = self.element.symbol.capitalize()
        return "{}-{}{}".format(symbol, self.a, "m" if self.state else "")

    def getEndfMatNum(self):
        """
        Gets the ENDF MAT number

        MAT numbers are defined as described in section 0.4.1 of the NJOY manual.
        Basically, it's Z * 100 + I where I is an isotope number. I=25 is defined
        as the lightest known stable isotope of element Z, so for Uranium,
        Z=92 and I=25 refers to U234. The values of I go up by 3 for each
        mass number, so U235 is 9228. This leaves room for three isomeric
        states of each nuclide.

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
                smallestStableA = min(
                    ni.a for ni in naturalIsotopes
                )  # no guarantee they were sorted
            else:
                raise KeyError("Nuclide {0} is unknown in the MAT number lookup")

        isotopeNum = (a - smallestStableA) * 3 + self.state + 25
        mat = z * 100 + isotopeNum
        return "{0}".format(mat)


class DummyNuclideBase(INuclide):
    """
    Dummy nuclides are used nuclides which transmute into isotopes that are not defined in blueprints.

    Notes
    -----
    If DMP number density is not very small, cross section may be artifically depressed.
    """

    def __init__(self, name, mc2id, weight):
        INuclide.__init__(
            self, 0, 0, 0, weight, 0.0, name, "DMP" + name[4], mc2id  # z  # a  # state
        )

    def __repr__(self):
        return "<DummyNuclideBase {}: Z:{}, w:{}, label:{}, mc2id:{}>" "".format(
            self.name, self.z, self.weight, self.label, self.mc2id
        )

    def getNaturalIsotopics(self):
        r"""Gets the natural isotopics, an empty iterator.

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

    def getMcc3Id(self):
        r"""Gets the MC**2-v3 nuclide ID.

        Returns
        -------
        name: str
            The MC**2 ID: ``DUMMY`` for all.

        See Also
        --------
        :meth:`INuclide.getMcc3Id`
        """
        return "DUMMY"


class LumpNuclideBase(INuclide):
    """
    Lump nuclides are used for lumped fission products.

    See Also
    --------
    armi.physics.neutronics.fissionProduct model:
        Describes what nuclides LumpNuclideBase is expend to.
    """

    def __init__(self, name, z, mc2id, weight):
        INuclide.__init__(self, z, 0, 0, weight, 0.0, name, name[1:], mc2id)

    def __repr__(self):
        return "<LumpNuclideBase {}: Z:{}, w:{}, label:{}, mc2id:{}>" "".format(
            self.name, self.z, self.weight, self.label, self.mc2id
        )

    def getNaturalIsotopics(self):
        r"""Gets the natural isotopics, an empty iterator.

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

    def getMcc3Id(self):
        r"""Gets the MC**2-v3 nuclide ID.

        Returns
        -------
        name: str
            The MC**2 ID: ``LFP38``, etc.

        See Also
        --------
        :meth:`INuclide.getMcc3Id`
        """
        return self.mc2id


class NaturalNuclideBase(INuclide, IMcnpNuclide):
    def __init__(self, name, element, mc2id):
        self.element = element
        INuclide.__init__(
            self,
            element.z,
            0,
            0,
            sum([nn.weight * nn.abundance for nn in element.getNaturalIsotopics()]),
            0.0,  # keep abundance 0.0 to not interfere with the isotopes
            name,
            name,
            mc2id,
        )
        self.element.append(self)

    def __repr__(self):
        return "<NaturalNuclideBase {}: Z:{}, w:{}, label:{}, mc2id:{}>" "".format(
            self.name, self.z, self.weight, self.label, self.mc2id
        )

    def getNaturalIsotopics(self):
        r"""Gets the natural isotopics root :py:class:`~elements.Element`.

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

    def getMcc3Id(self):
        r"""Gets the MC**2-v3 nuclide ID.

        Returns
        -------
        id: str
            The MC**2 ID: ``FE___7``, ``C____7``, etc.

        See Also
        --------
        :meth:`INuclide.getMcc3Id`
        """
        return "{:_<5}7".format(self.element.symbol)

    def getMcnpId(self):
        """Gets the MCNP ID for this element.

        Returns
        -------
        id : str
            The MCNP ID e.g. ``1000``, ``92000``. Not zero-padded on the left.
        """
        return "{0:d}000".format(self.z)

    def getAAAZZZSId(self):
        """Gets the AAAZZZS ID for a few elements.

        Notes
        -----
        the natural nuclides 'C' and 'V' do not have isotopic nuclide data for MC2 so sometimes they tag along in the
        list of active nuclides. This method is designed to fail in the same as if there was not getAAAZZZSId method
        defined.
        """
        if self.element.symbol == "C":
            return "120060"
        elif self.element.symbol == "V":
            return "510230"
        else:
            return None

    def getSerpentId(self):
        """Gets the SERPENT ID for this natural nuclide.

        Returns
        -------
        id: str
            SERPENT ID: ``C-nat``, `Fe-nat``
        """
        return "{}-nat".format(self.element.symbol.capitalize())

    def getEndfMatNum(self):
        """Get the ENDF mat number for this element."""
        if self.z != 6:
            runLog.warning(
                "The only elemental in ENDF/B VII.1 is carbon. "
                "ENDF mat num was requested for the elemental {} and will not be helpful "
                "for working with ENDF/B VII.1. Try to expandElementalsToIsotopics".format(
                    self
                )
            )
        return "{0}".format(self.z * 100)


def initReachableActiveNuclidesThroughBurnChain(numberDensityDict, activeNuclides):
    """
    March through the depletion chain and find all nuclides that can be reached by depleting nuclides passed in.

    This limits depletion to the smallest set of nuclides that matters.

    Parameters
    ----------
    numberDensityDict : dict
        Starting number densities.

    activeNuclides : OrderedSet
        Active nuclides defined on the reactor blueprints object. See: armi.reactor.blueprints.py
    """
    missingActiveNuclides = set()
    memo = set()
    difference = set(numberDensityDict).difference(memo)
    while any(difference):
        nuclide = difference.pop()
        memo.add(nuclide)
        # Skip the nuclide if it is not `active` in the burn-chain
        if not nuclide in activeNuclides:
            continue
        nuclideObj = byName[nuclide]
        for interaction in nuclideObj.trans + nuclideObj.decays:
            try:
                # Interaction nuclides can only be added to the number density
                # dictionary if they are a part of the user-defined active nuclides
                productNuclide = interaction.getPreferredProduct(activeNuclides)
                if productNuclide not in numberDensityDict:
                    numberDensityDict[productNuclide] = 0.0
            except KeyError:
                # Keep track of the first production nuclide
                missingActiveNuclides.add(interaction.productNuclides)

        difference = set(numberDensityDict).difference(memo)

    if missingActiveNuclides:
        _failOnMissingActiveNuclides(missingActiveNuclides)


def _failOnMissingActiveNuclides(missingActiveNuclides):
    """Raise ValueError with notification of which nuclides to include in the burn-chain."""
    msg = "Missing active nuclides in loading file. Add the following nuclides:"
    for i, nucList in enumerate(missingActiveNuclides, 1):
        msg += "\n {} - ".format(i)  # Index of
        for j, nuc in enumerate(nucList, 1):
            delimiter = " or " if j < len(nucList) else ""
            msg += "{}{}".format(nuc, delimiter)
    raise ValueError(msg)
