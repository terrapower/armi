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
The nucDirectory module contains general nuclide information through the
:py:mod:`~armi.nucDirectory.nuclideBases` module, and
information for :py:mod:`~armi.nucDirectory.nuclide` module.

#. :ref:`Element data <doc-elements>` - name, symbol, atomic number (Z).
#. :ref:`Generic nuclide data <doc-nuclide-bases>` - this includes  mass, atomic number, natural
   abundance and various names and labels that are used in ARMI for the nuclide. It also includes
   decay and transmutation modes.
#. Nuclide specific :ref:`cross section information <doc-nuclides>`.

.. _doc-elements:

Elements
========

:py:class:`Elements <armi.nucDirectory.elements.Element>` are simple objects containing minimal
information about... elements! This information is loaded from a data file within ARMI;
consequently modifying the data file will modify the list of elements in ARMI.

:py:class:`Elements <armi.nucDirectory.elements.Element>` are not used very often within armi,
and are mainly used as a building block of the nuclide objects discussed below. If you need to
grab an element for some reason there are three available dictionaries provided for rapid
access.::

    >>> from armi.nucDirectory import elements
    >>> uranium = elements.byZ[92]
    >>> uranium.name
    'uranium'
    >>> uranium.z
    92

Likewise, elements can be retrieved by their name or symbol.::

    >>> ironFromZ = elements.byZ[26]
    >>> ironFromName = elements.byName['iron']
    >>> ironFromSymbol = elements.bySymbol['FE']
    >>> ironFromZ == ironFromName == ironFromSymbol
    True

.. warning ::
    Note that :py:data:`~armi.nucDirectory.elements.byName` and
    :py:data:`~armi.nucDirectory.elements.bySymbol` are case specific;
    names are *lower case* and symbols are *UPPER CASE*.

The elements are truly the *same* :py:class:`~armi.nucDirectory.elements.Element` object.
The :py:mod:`~armi.nucDirectory`
makes efficient use of the memory being used by elements and will only ever contain ~118
:py:class:`Elements <armi.nucDirectory.elements.Element>`.::

    >>> id(ironFromZ) == id(ironFromName) == id(ironFromSymbol)
    True

.. _doc-nuclide-bases:

Nuclide Bases
=============

The :py:mod:`~armi.nucDirectory` allows ARMI to get information about various nuclides, like
U235 or FE56. Often times you need to look up cross section or densities for nuclides, or you
might need the atomic weight or the natural isotopic distribution. The
:py:mod:`~armi.nucDirectory` is here to help you with these common tasks.

The fundamental object of nuclide management in ARMI is the
:py:class:`~armi.nucDirectory.nuclideBases.INuclide` object. After construction, they contain
some basic information, such as Z, A, and atomic weight (if known). Similar to
:py:class:`Elements <armi.nucDirectory.elements.Element>`, the information is loaded from a
series of data files within ARMI. The data is originally from [NIST]_::

    >>> from armi.nucDirectory import nuclideBases
    >>> u235= nuclideBases.byName['U235']
    >>> u235.z
    92
    >>> u235.weight
    235.0439299
    >>> u235.a
    235

.. [NIST] http://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl

Upon loading the :py:mod:`armi.nucDirectory` package, the
:py:data:`nuclideBases.instances <armi.nucDirectory.nuclideBases.instances>`, will
be filled with nuclide base objects. Nuclide bases do not *do* much, but they contain a lot of
basic information about a nuclide, such as the atomic mass, atomic number (Z), the mass
number (A), the natural abundance, and all of the decay and transmutation modes (well, ARMI's
decay and transmutation modes).

Nuclide names, labels and MC\*\*2 IDs
-------------------------------------
Nuclides have names, labels and IDs. 

:py:attr:`INuclide.name <armi.nucDirectory.nuclideBases.INuclide.name>`
    The nuclide name is what *should* be used within ARMI itself. This is a human readable name
    such as, ``U235`` or ``FE``. The names contain **only** capital letters and numbers, made up
    from the corresponding element symbol and mass number (A).

:py:attr:`INuclide.label <armi.nucDirectory.nuclideBases.INuclide.label>`
    The nuclide label is a unique 4 character name which identifies the nuclide from all others
    within MC\*\*2 and DIF3D. The label must be 4 characters, because MC\*\*2 and DIF3D only
    allow 6 character labels, two of which we reserver for the cross section ID. Labels
    are not necessarily human readable, but are generally the nuclide symbol followed by
    the last two digits of the mass number (A), so the nuclide for U235 has the label
    ``U235``, but PU239 has the label ``PU39``.

:py:attr:`INuclide.mc2id <armi.nucDirectory.nuclideBases.INuclide.mc2id>`
    The mc2id is the MC\*\*2 id used for MC\*\*2 version 2. This should only be used
    when loading an ISOTXS file, or writing MC\*\*2 input.

:py:meth:`INuclide.mc3id() <armi.nucDirectory.nuclideBases.INuclide.mc3id>`
    The mc3id is the MC\*\*2 id used for MC\*\*2 version 3. This should only be used
    when loading an ISOTXS file, or writing MC\*\*2 input.

For reference, there is a complete list of the nuclides along with the names, labels and IDs
:py:mod:`here <armi.nucDirectory.nuclideBases>`.

Indices - rapid access
----------------------

There are three main ways to retrieve a nuclide, which are provided for convenience depending on
what information you have, or "know," about a nuclide. For example, if you know a nuclide name, use
the :py:data:`~armi.nucDirectory.nuclideBases.byName` dictionary. There are also dictionaries
available for retrieving by the label, :py:data:`~armi.nucDirectory.nuclideBases.byLabel`, and by
the MC\*\*2 ID, :py:data:`~armi.nucDirectory.nuclideBases.byMccId` (this works for both version 2
and version 3 IDs).

    >>> from armi.nucDirectory import nuclideBases
    >>> pu239 = nuclideBases.byName['PU239']
    >>> pu239.z
    94

Just like with elements, the item retrieved from the various dictionaries are the same object.

    >>> tinFromName = nuclideBases.byName['SN112']
    >>> tinFromLabel = nuclideBases.byLabel['SN112']
    >>> tinFromMcc2Id = nuclideBases.byName['SN1125']
    >>> tinFromMcc3Id = nuclideBases.byLabel['SN1127']
    >>> tinFromName == tinFromLabel == tinFromMcc2Id == tinFromMcc3Id
    True
    >>> id(tinFromName) == id(tinFromLabel) == id(tinFromMcc2Id) == id(tinFromMcc3Id)
    True

.. warning::
    If you find yourself using a name or label within ARMI itself, it is probably not as efficient
    as it could be. Many older, but still existing, data structures within ARMI use nuclide names
    and labels for indexing certain information about the nuclide, such as number density.
    However, often times they will also need other information, such as the mass. Consequently,
    the index which contains the name or label is not fulfilling its intended purpose; in order to
    perform the operation, ``weight * numberDensity``, you'll still need the nuclide object!

.. _doc-nuclides:

Nuclides
========

Another closely related object is the :py:class:`armi.nucDirectory.nuclide.Nuclide`.
:py:class:`Nuclides <nuclide.Nuclide>` are created when loading an ISOTXS file from MC\*\*2.
:py:class:`Nuclides <nuclide.Nuclide>` contain the same information as
:py:class:`INuclides <INuclide>`, but also contain multi-group microscopic cross section data.

"""
