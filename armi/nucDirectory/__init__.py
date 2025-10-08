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
The nucDirectory module contains tools to access nuclide information in the :py:mod:`~armi.nucDirectory.nuclideBases`
module, and information for :py:mod:`~armi.nucDirectory.nuclide` module.

#. :ref:`Element data <doc-elements>` - name, symbol, atomic number (Z).
#. :ref:`Generic nuclide data <doc-nuclide-bases>` - this includes  mass, atomic number, natural abundance and various
   names and labels that are used in ARMI for the nuclide. It also includes decay and transmutation modes.

.. _doc-elements:

Elements
========

:py:class:`Elements <armi.nucDirectory.elements.Element>` are simple objects containing minimal information about
atomic elements. This information is loaded from a data file within ARMI; elements.dat.

:py:class:`Elements <armi.nucDirectory.elements.Element>` are mainly used as a building block of the nuclide objects
, as discussed below. If you need to grab an element there are three available dictionaries provided for rapid access.::

    >>> r = Reactor("testReactor", bp)
    >>> elements = r.nuclideBases.elements
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

.. note::
    The :py:attr:`~armi.nucDirectory.elements.Elements.byName` and
    :py:attr:`~armi.nucDirectory.elements.Elements.bySymbol` are case specific; names are *lower case* and symbols are
    *UPPER CASE*.

The elements are truly the *same* :py:class:`~armi.nucDirectory.elements.Element` object. The
:py:mod:`~armi.nucDirectory` makes efficient use of the memory being used by elements and will only ever contain ~118
:py:class:`Elements <armi.nucDirectory.elements.Element>`.::

    >>> id(ironFromZ) == id(ironFromName) == id(ironFromSymbol)
    True

.. _doc-nuclide-bases:

Nuclide Bases
=============

The :py:mod:`~armi.nucDirectory` allows ARMI to get information about various nuclides, like U235 or FE56. Often times
you need to look up cross section or densities for nuclides, or you might need the atomic weight or the natural isotopic
distribution. The :py:mod:`~armi.nucDirectory` is here to help.

The fundamental object of nuclide management in ARMI is the :py:class:`~armi.nucDirectory.nuclideBases.INuclide` object.
After construction, they contain basic information, such as Z, A, and atomic weight (if known). Similar to
:py:class:`Elements <armi.nucDirectory.elements.Element>`, the information is loaded from a series of data files within
ARMI. The data is originally from [NIST]_::

    >>> r = Reactor("testReactor", bp)
    >>> u235= r.nuclideBases.byName['U235']
    >>> u235.z
    92
    >>> u235.weight
    235.0439299
    >>> u235.a
    235

.. [NIST] http://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl

Upon creating a Reactor, a fully fledged ``NuclideBases`` object will be created. In that object there will be a full
Upon loading the :py:mod:`armi.nucDirectory` package, inside that will be a fully instantiated ``Elements`` object and a
list called.:py:data:`nuclideBases.instances <armi.nucDirectory.nuclideBases.instances>`. The ``instances`` will
be filled with nuclide base objects. Nuclide bases contain a lot of basic information about a nuclide, such as the
atomic mass, atomic number (Z), the mass number (A), and the natural abundance.

Nuclide names, labels, and IDs
------------------------------
Nuclides have names, labels and IDs.

:py:attr:`INuclide.name <armi.nucDirectory.nuclideBases.INuclide.name>`
    The nuclide name is what *should* be used within ARMI and ARMI-based appliations. This is a human readable name such
    as, ``U235`` or ``FE``. The names contain **only** capital letters and numbers, made up from the corresponding
    element symbol and mass number (A).

:py:attr:`INuclide.label <armi.nucDirectory.nuclideBases.INuclide.label>`
    The nuclide label is a unique 4 character name which identifies the nuclide from all others. The label is fixed to
    4 characters to conform with the CCCC standard files, which traditionally only allow for a maximum of 6 character
    labels in legacy nuclear codes. Of the 6 allowable characters, 4 are reserved for the unique identifier of the
    nuclide and 2 characters are reserved for cross section labels (i.e., AA, AB, ZA, etc.). The cross section labels
    are based on the cross section group manager implementation within the framework. These labels are not necessarily
    human readable/interpretable, but are generally the nuclide symbol followed by the last two digits of the mass
    number (A), so the nuclide for U235 has the label ``U235``, but PU239 has the label ``PU39``.

For reference, the data used to build the nuclide bases in ARMI comes from a file called ``nuclides.dat``.

Indices - rapid access
----------------------

There are three main ways to retrieve a nuclide, which are provided depending on what information you have about a
nuclide. For example, if you know a nuclide name, use ``NuclideBases.byName`` dictionary. There are also dictionaries
available for retrieving by the label, ``NuclideBases.byLabel``, and by other software-specific IDs (i.e., MCNP,
MC2-2, and MC2-3). The software-specific labels are incorporated into the framework to support plugin developments and
may be extended as needed by end-users as needs arise.

    >>> r = Reactor("testReactor", bp)
    >>> pu239 = r.nuclideBases.byName['PU239']
    >>> pu239.z
    94

Just like with elements, the item retrieved from the various dictionaries are the same object.

    >>> tinFromName = r.nuclideBases.byName['SN112']
    >>> tinFromLabel = r.nuclideBases.byLabel['SN112']
    >>> tinFromMcc2Id = r.nuclideBases.byName['SN1125']
    >>> tinFromMcc3Id = r.nuclideBases.byLabel['SN1127']
    >>> tinFromName == tinFromLabel == tinFromMcc2Id == tinFromMcc3Id
    True
    >>> id(tinFromName) == id(tinFromLabel) == id(tinFromMcc2Id) == id(tinFromMcc3Id)
    True

"""
