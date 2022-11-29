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
from typing import List
from enum import Enum

from armi import context
from armi.utils.units import HEAVY_METAL_CUTOFF_Z

byZ = {}
byName = {}
bySymbol = {}


class ChemicalPhase(Enum):
    GAS = 1
    LIQUID = 2
    SOLID = 3
    UNKNOWN = 4


class ChemicalGroup(Enum):
    ALKALI_METAL = 1
    ALKALINE_EARTH_METAL = 2
    NONMETAL = 3
    TRANSITION_METAL = 4
    POST_TRANSITION_METAL = 5
    METALLOID = 6
    HALOGEN = 7
    NOBEL_GAS = 8
    LANTHANIDE = 9
    ACTINIDE = 10
    UNKNOWN = 11


class Element:
    """Represents an element defined on the Periodic Table."""

    def __init__(self, z, symbol, name, phase="UNKNOWN", group="UNKNOWN"):
        """
        Creates an instance of an Element.

        Parameters
        ----------
        z : int
            atomic number, number of protons
        symbol : str
            element symbol
        name: str
            element name
        phase : str
            Chemical phase of the element at standard temperature and pressure (e.g., gas, liquid, solid).
        group : str
            Chemical group of the element.
        """
        self.z = z
        self.symbol = symbol
        self.name = name
        self.phase = ChemicalPhase[phase]
        self.group = ChemicalGroup[group]
        self.standardWeight = None
        self.nuclides = []
        addGlobalElement(self)

    def __repr__(self):
        return f"<Element {self.symbol:>3s} (Z={self.z}), {self.name}, {self.group}, {self.phase}>"

    def __eq__(self, other):
        return (
            self.z == other.z
            and self.symbol == other.symbol
            and self.name == other.name
            and self.phase == other.phase
            and self.group == other.group
            and len(self.nuclides) == len(other.nuclides)
        )

    def __hash__(self):
        return hash(self.name)

    def __iter__(self):
        for nuc in sorted(self.nuclides):
            yield nuc

    def append(self, nuclide):
        """Assigns and sorts the nuclide to the element and ensures no duplicates."""
        from armi.nucDirectory.nuclideBases import NuclideBase

        if nuclide in self.nuclides or not isinstance(nuclide, NuclideBase):
            return
        self.nuclides.append(nuclide)
        self.nuclides = sorted(self.nuclides)

    def isNaturallyOccurring(self):
        """Return True if the element is occurs in nature."""
        return any([nuc.abundance > 0.0 for nuc in self.nuclides])

    def getNaturalIsotopics(self):
        """Return a list of nuclides that are naturally occurring for this element."""
        return [nuc for nuc in self.nuclides if nuc.abundance > 0.0 and nuc.a > 0]

    def isHeavyMetal(self):
        """
        Return True if the atomic number of greater than 89 (i.e., Z > 89).

        Notes
        -----
        Heavy metal in this instance is not related to an exact weight or density
        cut-off, but rather is designated for nuclear fuel burn-up evaluations, where
        the initial heavy metal mass within a component should be tracked. It is typical
        to include any element/nuclide above Actinium.
        """
        return self.z > HEAVY_METAL_CUTOFF_Z


def getElementsByChemicalPhase(phase) -> List[Element]:
    """
    Returns all elements that are of the given chemical phase.

    Parameters
    ----------
    phase: ChemicalPhase
        This should be one of the valid options from the `ChemicalPhase` class.

    Returns
    -------
    elems : List[Element]
        A list of elements that are associated with the given chemical phase.
    """
    elems = []
    if not isinstance(phase, ChemicalPhase):
        raise ValueError(f"{phase} is not an instance of {ChemicalPhase}")
    for element in byName.values():
        if element.phase == phase:
            elems.append(element)
    return elems


def getElementsByChemicalGroup(group) -> List[Element]:
    """
    Returns all elements that are of the given chemical group.

    Parameters
    ----------
    group: ChemicalGroup
        This should be one of the valid options from the `ChemicalGroup` class.

    Returns
    -------
    elems : List[Element]
        A list of elements that are associated with the given chemical group.
    """
    elems = []
    if not isinstance(group, ChemicalGroup):
        raise ValueError(f"{group} is not an instance of {ChemicalGroup}")
    for element in byName:
        if element.group == group.values():
            elems.append(element)
    return elems


def getName(z: int = None, symbol: str = None) -> str:
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


def getSymbol(z: int = None, name: str = None) -> str:
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


def getElementZ(symbol: str = None, name: str = None) -> int:
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
        element.nuclides = []


# method to renormalize the nuclide / element relationship
nuclideRenormalization = None


def addGlobalElement(element: Element):
    """Add an element to the global dictionaries."""
    if element.z in byZ or element.name in byName or element.symbol in bySymbol:
        raise ValueError(f"{element} has already been added and cannot be duplicated.")

    byZ[element.z] = element
    byName[element.name] = element
    bySymbol[element.symbol] = element


def destroyGlobalElements():
    """Delete all global elements."""
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
        destroyGlobalElements()
        with open(os.path.join(context.RES, "elements.dat"), "r") as f:
            for line in f:
                # Skip header lines
                if line.startswith("#") or line.startswith("Z"):
                    continue
                # read z, symbol, name, phase, and chemical group
                lineData = line.split()
                z = int(lineData[0])
                sym = lineData[1].upper()
                name = lineData[2]
                phase = lineData[3]
                group = lineData[4]

                Element(z, sym, name, phase, group)
        if nuclideRenormalization is not None:
            nuclideRenormalization()  # pylint: disable=not-callable
            # this is used as a method to ensure the nuclides are
            # renormalized to actual elements if the elements.factory()
            # was called for some reason.
        deriveNaturalWeights()  # calling here is only useful after a destroy(); nucBases must exist


factory()
