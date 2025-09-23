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
This module provides fundamental element information to be used throughout the framework and applications.

.. impl:: A tool for querying basic data for elements of the periodic table.
    :id: I_ARMI_ND_ELEMENTS0
    :implements: R_ARMI_ND_ELEMENTS

    The :py:mod:`elements <armi.nucDirectory.elements>` module defines the
    :py:class:`Element <armi.nucDirectory.elements.Element>` class which acts as a data structure for organizing
    information about an individual element, including number of protons, name, chemical symbol, phase (at STP),
    periodic table group, standard weight, and a list of isotope
    :py:class:`nuclideBase <armi.nucDirectory.nuclideBases.NuclideBase>` instances. The module includes a factory that
    generates the :py:class:`Element <armi.nucDirectory.elements.Element>` instances by reading from the
    ``elements.dat`` file stored in the ARMI resources folder. When an
    :py:class:`Element <armi.nucDirectory.elements.Element>` instance is initialized, it is added to a set of global
    dictionaries that are keyed by number of protons, element name, and element symbol. The module includes several
    helper functions for querying these global dictionaries.

The element class structure is outlined :ref:`here <elements-class-diagram>`.

.. _elements-class-diagram:

.. pyreverse:: armi.nucDirectory.elements
    :align: center
    :width: 75%

Examples
--------
>>> elements.byZ[92]
<Element   U (Z=92), Uranium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>

>>> elements.bySymbol["U"]
<Element   U (Z=92), Uranium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>

>>> elements.byName["Uranium"]
<Element   U (Z=92), Uranium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>

Retrieve gaseous elements at Standard Temperature and Pressure (STP):

>>> elements.getElementsByChemicalPhase(elements.ChemicalPhase.GAS)
    [<Element   H (Z=1), Hydrogen, ChemicalGroup.NONMETAL, ChemicalPhase.GAS>,
     <Element  HE (Z=2), Helium, ChemicalGroup.NOBLE_GAS, ChemicalPhase.GAS>,
     <Element   N (Z=7), Nitrogen, ChemicalGroup.NONMETAL, ChemicalPhase.GAS>,
     <Element   O (Z=8), Oxygen, ChemicalGroup.NONMETAL, ChemicalPhase.GAS>,
     <Element   F (Z=9), Fluorine, ChemicalGroup.HALOGEN, ChemicalPhase.GAS>,
     <Element  NE (Z=10), Neon, ChemicalGroup.NOBLE_GAS, ChemicalPhase.GAS>,
     <Element  CL (Z=17), Chlorine, ChemicalGroup.HALOGEN, ChemicalPhase.GAS>,
     <Element  AR (Z=18), Argon, ChemicalGroup.NOBLE_GAS, ChemicalPhase.GAS>,
     <Element  KR (Z=36), Krypton, ChemicalGroup.NOBLE_GAS, ChemicalPhase.GAS>,
     <Element  XE (Z=54), Xenon, ChemicalGroup.NOBLE_GAS, ChemicalPhase.GAS>,
     <Element  RN (Z=86), Radon, ChemicalGroup.NOBLE_GAS, ChemicalPhase.GAS>,
     <Element  OG (Z=118), Oganesson, ChemicalGroup.NOBLE_GAS, ChemicalPhase.GAS>]


Retrieve elements that are classified as actinides:

 >>> elements.getElementsByChemicalGroup(elements.ChemicalGroup.ACTINIDE)
    [<Element  AC (Z=89), Actinium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  TH (Z=90), Thorium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  PA (Z=91), Protactinium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element   U (Z=92), Uranium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  NP (Z=93), Neptunium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  PU (Z=94), Plutonium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  AM (Z=95), Americium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  CM (Z=96), Curium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  BK (Z=97), Berkelium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  CF (Z=98), Californium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  ES (Z=99), Einsteinium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  FM (Z=100), Fermium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  MD (Z=101), Mendelevium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  NO (Z=102), Nobelium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>,
     <Element  LR (Z=103), Lawrencium, ChemicalGroup.ACTINIDE, ChemicalPhase.SOLID>]


.. only:: html

    For specific data on nuclides within each element, refer to the
    :ref:`nuclide bases summary table <nuclide-bases-table>`.

    .. exec::
        from armi.nucDirectory import elements
        from armi.utils.tabulate import tabulate
        from dochelpers import createTable

        attributes = ['z',
                    'name',
                    'symbol',
                    'phase',
                    'group',
                    'is naturally occurring?',
                    'is heavy metal?',
                    'num. nuclides',]

        def getAttributes(element):
            return [
                f'``{element.z}``',
                f'``{element.name}``',
                f'``{element.symbol}``',
                f'``{element.phase}``',
                f'``{element.group}``',
                f'``{element.isNaturallyOccurring()}``',
                f'``{element.isHeavyMetal()}``',
                f'``{len(element.nuclides)}``',
            ]

        sortedElements = sorted(elements.byZ.values())
        return createTable(tabulate(data=[getAttributes(elem) for elem in sortedElements],
                                    headers=attributes,
                                    tableFmt='rst'),
                           caption='List of elements',
                           label='nuclide-bases-table')
"""

import os
from enum import Enum
from typing import List

from armi import context
from armi.utils.units import HEAVY_METAL_CUTOFF_Z

elements = None
byZ = None
byName = None
bySymbol = None


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
    NOBLE_GAS = 8
    LANTHANIDE = 9
    ACTINIDE = 10
    UNKNOWN = 11


class Element:
    """Represents an element defined on the Periodic Table."""

    def __init__(self, z, symbol, name, phase="UNKNOWN", group="UNKNOWN", skipGlobal=False):
        """
        Creates an instance of an Element.

        .. impl:: An element of the periodic table.
            :id: I_ARMI_ND_ELEMENTS1
            :implements: R_ARMI_ND_ELEMENTS

            The :py:class:`Element <armi.nucDirectory.elements.Element>` class
            acts as a data structure for organizing information about an
            individual element, including number of protons, name, chemical
            symbol, phase (at STP), periodic table group, standard weight, and a
            list of isotope
            :py:class:`nuclideBase <armi.nucDirectory.nuclideBases.NuclideBase>`
            instances.

            The :py:class:`Element <armi.nucDirectory.elements.Element>` class
            has a few methods for appending additional isotopes, checking
            whether an isotope is naturally occurring, retrieving the natural
            isotopic abundance, or whether the element is a heavy metal.

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
        if not skipGlobal:
            addGlobalElement(self)

    def __repr__(self):
        return f"<Element {self.symbol:>3s} (Z={self.z}), {self.name}, {self.group}, {self.phase}>"

    def __hash__(self):
        return hash((self.name, self.z, self.symbol, self.phase, self.group, len(self.nuclides)))

    def __lt__(self, other):
        return self.z < other.z

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __iter__(self):
        for nuc in sorted(self.nuclides):
            yield nuc

    def append(self, nuclide):
        """Assigns and sorts the nuclide to the element and ensures no duplicates."""
        if nuclide in self.nuclides:
            return
        self.nuclides.append(nuclide)
        self.nuclides = sorted(self.nuclides)

    def isNaturallyOccurring(self):
        """Return True if the element is occurs in nature."""
        return any([nuc.abundance > 0.0 for nuc in self.nuclides])

    def getNaturalIsotopics(self):
        """
        Return a list of nuclides that are naturally occurring for this element.

        Notes
        -----
        This method will filter out any NaturalNuclideBases from the `nuclides` attribute.
        """
        return [nuc for nuc in self.nuclides if nuc.abundance > 0.0 and nuc.a > 0]

    def isHeavyMetal(self):
        """
        Return True if all nuclides belonging to the element are heavy metals.

        Notes
        -----
        Heavy metal in this instance is not related to an exact weight or density cut-off, but rather is designated for
        nuclear fuel burn-up evaluations, where the initial heavy metal mass within a component should be tracked. It is
        typical to include any element/nuclide above Actinium.
        """
        return self.z > HEAVY_METAL_CUTOFF_Z


def getElementsByChemicalPhase(phase: ChemicalPhase) -> List[Element]:
    """Pass through to Elements.getElementsByChemicalPhase() for the global Elements object."""
    global elements
    return elements.getElementsByChemicalPhase(phase)


def getElementsByChemicalGroup(group: ChemicalGroup) -> List[Element]:
    """Pass through to Elements.getElementsByChemicalGroup() for the global Elements object."""
    global elements
    return elements.getElementsByChemicalGroup(group)


def getName(z: int = None, symbol: str = None) -> str:
    """Pass through to Elements.getName() for the global Elements object."""
    global elements
    return elements.getName(z, symbol)


def getSymbol(z: int = None, name: str = None) -> str:
    """Pass through to Elements.getSymbol() for the global Elements object."""
    global elements
    return elements.getSymbol(z, name)


def getElementZ(symbol: str = None, name: str = None) -> int:
    """Pass through to Elements.getElementZ() for the global Elements object."""
    global elements
    return elements.getElementZ(symbol, name)


def factory():
    """Pass through to Elements.factory() for the global Elements object."""
    global elements
    global byZ
    global byName
    global bySymbol

    elements = Elements()
    elements.factory()

    byZ = elements.byZ
    byName = elements.byName
    bySymbol = elements.bySymbol


def addGlobalElement(element: Element):
    """Pass through to Elements.addElement() for the global Elements object."""
    global elements
    elements.addElement(element)


def destroyGlobalElements():
    """Pass through to Elements.clear() for the global Elements object."""
    global elements
    elements.clear()


class Elements:
    """
    A container for all the elements information in the simulation.

    By design, you would only expect to have one instance of this object in memory during a simulation.
    """

    def __init__(self):
        self.byZ = {}
        self.byName = {}
        self.bySymbol = {}
        self.elementsFile = os.path.join(context.RES, "elements.dat")

    def clear(self):
        """Empty all the data in this collection."""
        self.byZ.clear()
        self.byName.clear()
        self.bySymbol.clear()

    def addElement(self, element: Element):
        """Add an element to this collection."""
        if element.z in self.byZ or element.name in self.byName or element.symbol in self.bySymbol:
            raise ValueError(f"{element} has already been added and cannot be duplicated.")

        self.byZ[element.z] = element
        self.byName[element.name] = element
        self.bySymbol[element.symbol] = element

    def factory(self):
        """Generate the :class:`Elements <Element>` instances."""
        self.clear()
        with open(self.elementsFile, "r") as f:
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
                standardWeight = lineData[5]
                e = Element(z, sym, name, phase, group, skipGlobal=True)
                if standardWeight != "Derived":
                    e.standardWeight = float(standardWeight)
                self.addElement(e)

    def getElementsByChemicalPhase(self, phase: ChemicalPhase) -> List[Element]:
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

        for element in self.byName.values():
            if element.phase == phase:
                elems.append(element)

        return elems

    def getElementsByChemicalGroup(self, group: ChemicalGroup) -> List[Element]:
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

        for element in self.byName.values():
            if element.group == group:
                elems.append(element)

        return elems

    def getName(self, z: int = None, symbol: str = None) -> str:
        r"""
        Returns element name.

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
            element = self.byZ[z]
        else:
            element = self.byName[symbol.upper()]

        return element.name

    def getSymbol(self, z: int = None, name: str = None) -> str:
        r"""
        Returns element abbreviation given atomic number Z.

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
            element = self.byZ[z]
        else:
            element = self.byName[name.lower()]

        return element.symbol

    def getElementZ(self, symbol: str = None, name: str = None) -> int:
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
            element = self.bySymbol[symbol.upper()]
        else:
            element = self.byName[name.lower()]

        return element.z


factory()
