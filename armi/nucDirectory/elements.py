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
Deals with elements of the periodic table.
"""

import os

from armi import context
from armi.utils.units import HEAVY_METAL_CUTOFF_Z

byZ = {}
byName = {}
bySymbol = {}

LANTHANIDE_ELEMENTS = [
    "LA",
    "CE",
    "PR",
    "ND",
    "PM",
    "PX",
    "SM",
    "EU",
    "GD",
    "TB",
    "DY",
    "HO",
    "ER",
    "TM",
    "YB",
    "LU",
]
GASEOUS_ELEMENTS = ["XE", "KR"]


class Element:
    r"""
    Represents an element, defined by its atomic number.

    Attributes
    ----------
    z : int
        atomic number, number of protons

    symbol : str
        element symbol

    name : str
        element name

    nuclideBases : list of nuclideBases
        nuclideBases for this element
    """

    def __init__(self, z, symbol, name):
        r"""
        Creates an instance of an Element.

        Parameters
        ----------
        z : int
            atomic number, number of protons

        symbol : str
            element symbol

        name: str
            element name

        """
        self.z = z
        self.symbol = symbol
        self.name = name
        self.standardWeight = None
        self.nuclideBases = []

        other = byZ.get(z, None)
        if other is not None and other == self:
            raise Exception(
                "Element with atomic weight {} already exists" "".format(self)
            )
        byZ[z] = self
        byName[name] = self
        bySymbol[symbol] = self

    def __repr__(self):
        return "<Element {} {}>".format(self.symbol, self.z)

    def __eq__(self, other):
        return (
            self.z == other.z
            and self.symbol == other.symbol
            and self.name == other.name
        )

    def __hash__(self):
        return hash(self.name)

    def __iter__(self):
        for nuc in self.nuclideBases:
            yield nuc

    def append(self, nuclide):
        self.nuclideBases.append(nuclide)

    def isNaturallyOccurring(self):
        r"""
        Calculates the total natural abundance and if this value is zero returns False.
        If any isotopes are naturally occurring the total abundance will be >0 so it will return True
        """
        totalAbundance = 0.0
        for nuc in self.nuclideBases:
            totalAbundance += nuc.abundance
        return totalAbundance > 0.0

    def getNaturalIsotopics(self):
        """
        Return the nuclide bases of any naturally-occurring isotopes of this element.

        Notes
        -----
        Some elements have no naturally-occurring isotopes (Tc, Pu, etc.). To
        allow this method to be used in loops it will simply return an
        empty list in these situations.
        """
        return [nuc for nuc in self.nuclideBases if nuc.abundance > 0.0 and nuc.a > 0]

    def isHeavyMetal(self):
        return self.z > HEAVY_METAL_CUTOFF_Z


def getName(z=None, symbol=None):
    r"""
    Returns element name

    Parameters
    ----------
    z : int
        Atomic number
    symbol : str
        Element abbreviation e.g. 'Zr'

    Examples
    --------
    >>> elements.getName(10)
    'Neon'
    >>> elements.getName(symbol='Ne')
    'Neon'

    """
    element = None
    if z:
        element = byZ[z]
    else:
        element = byName[symbol.upper()]
    return element.name


def getSymbol(z=None, name=None):
    r"""
    Returns element abbreviation given atomic number Z

    Parameters
    ----------
    z : int
        Atomic number
    name : str
        Element name E.g. Zirconium

    Examples
    --------
    >>> elements.getSymbol(10)
    'Ne'
    >>> elements.getSymbol(name='Neon')
    'Ne'

    """
    element = None
    if z:
        element = byZ[z]
    else:
        element = byName[name.lower()]
    return element.symbol


def getElementZ(symbol=None, name=None):
    """
    Get element atomic number given a symbol or name.

    Parameters
    ----------
    symbol : str
        Element symbol e.g. 'Zr'
    name : str
        Element name e.g. 'Zirconium'

    Examples
    --------
    >>> elements.getZ('Zr')
    40
    >>> elements.getZ(name='Zirconium')
    40

    Notes
    -----
    Element Z is stored in elementZBySymbol, indexed by upper-case element symbol.
    """
    if not symbol and not name:
        return None
    element = None
    if symbol:
        element = bySymbol[symbol.upper()]
    else:
        element = byName[name.lower()]
    return element.z


def clearNuclideBases():
    """
    Delete all nuclide base links.

    Necessary when initializing nuclide base information multiple times (often in testing).
    """
    for _, element in byName.items():
        element.nuclideBases = []


# method to renormalize the nuclide / element relationship
nuclideRenormalization = None


def destroy():
    """Delete all elements."""
    byZ.clear()
    byName.clear()
    bySymbol.clear()


def deriveNaturalWeights():
    """
    Loop over all defined elements and compute the natural isotope-weighted atomic weight.

    Must be run after all nuclideBases are initialized.

    Notes
    -----
    Abundances may not add exactly to 1.0 because they're read from measurements
    that have uncertainties.
    """
    for element in byName.values():
        numer = 0.0
        denom = 0.0
        for nb in element.getNaturalIsotopics():
            numer += nb.weight * nb.abundance
            denom += nb.abundance  # should add roughly to 1.0
        if numer:
            element.standardWeight = numer / denom


def factory():
    """
    Generate the :class:`Elements <Element>` instances.

    .. warning::
        This method gets called by default when loading the module, so don't call it
        unless you know what you're doing.
        Any existing :class:`Nuclides <armi.nucDirectory.nuclide.Nuclide>`
        may lose their reference to the underlying :class:`Element`.
    """
    if len(byZ) == 0:
        destroy()
        # read all.dat -> z, symbol, name
        with open(os.path.join(context.RES, "elements.dat"), "r") as f:
            for line in f:
                # read z, symbol, and name
                lineData = line.split()
                z = int(lineData[0])
                sym = lineData[1].upper()
                name = lineData[2].lower()
                Element(z, sym, name)
        if nuclideRenormalization is not None:
            nuclideRenormalization()  # pylint: disable=not-callable
            # this is used as a method to ensure the nuclides are
            # renormalized to actual elements if the elements.factory()
            # was called for some reason.
        deriveNaturalWeights()  # calling here is only useful after a destroy(); nucBases must exist


factory()
