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

"""Assorted utilities to help with basic density calculations."""

from typing import Dict, List, Tuple, Union

import numpy as np

from armi import runLog
from armi.nucDirectory import elements, nucDir, nuclideBases
from armi.utils import units


def getNDensFromMasses(rho, massFracs, normalize=False):
    """
    Convert density (g/cc) and massFracs vector into a number densities vector (#/bn-cm).

    .. impl:: Number densities are retrievable from masses.
        :id: I_ARMI_UTIL_MASS2N_DENS
        :implements: R_ARMI_UTIL_MASS2N_DENS

        Loops over all provided nuclides (given as keys in the ``massFracs`` vector) and calculates number densities of
        each, at a given material ``density``. Mass fractions can be provided either as normalized to 1, or as
        unnormalized with subsequent normalization calling ``normalizeNuclideList`` via the ``normalize`` flag.

    Parameters
    ----------
    rho : float
        density in (g/cc)
    massFracs : dict
        vector of mass fractions -- normalized to 1 -- keyed by their nuclide name

    Returns
    -------
    nuclides : np.ndarray[np.bytes_]
        vector of nuclide names as byte strings
    numberDensities : np.ndarray[np.float64]
        vector of number densities (#/bn-cm) for each nuclide in nuclides
    """
    if normalize:
        massFracs = normalizeNuclideList(massFracs, normalization=normalize)

    nuclides = []
    numberDensities = []
    rho = rho * units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
    for nucName, massFrac in massFracs.items():
        atomicWeight = nuclideBases.byName[nucName].weight
        nuclides.append(nucName.encode())
        numberDensities.append(massFrac * rho / atomicWeight)
    return np.array(nuclides), np.array(numberDensities)


def getMassFractions(numberDensities):
    """
    Convert number densities (#/bn-cm) into mass fractions.

    Parameters
    ----------
    numberDensities : dict
        number densities (#/bn-cm) keyed by their nuclide name

    Returns
    -------
    massFracs : dict
        mass fractions -- normalized to 1 -- keyed by their nuclide name
    """
    nucMassFracs = {}
    totalWeight = 0.0
    for nucName, numDensity in numberDensities.items():
        weightI = numDensity * nucDir.getAtomicWeight(nucName)
        nucMassFracs[nucName] = weightI  # will be normalized at end
        totalWeight += weightI

    if totalWeight != 0:
        for nucName in numberDensities:
            nucMassFracs[nucName] /= totalWeight
    else:
        for nucName in numberDensities:
            nucMassFracs[nucName] = 0.0

    return nucMassFracs


def calculateMassDensity(numberDensities):
    """
    Calculates the mass density.

    Parameters
    ----------
    numberDensities : dict
        vector of number densities (atom/bn-cm) indexed by nuclides names

    Returns
    -------
    rho : float
        density in (g/cc)
    """
    rho = 0
    for nucName, nDensity in numberDensities.items():
        atomicWeight = nuclideBases.byName[nucName].weight
        rho += nDensity * atomicWeight / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
    return rho


def calculateNumberDensity(nucName, mass, volume):
    """
    Calculates the number density.

    Parameters
    ----------
    mass : float
    volume : volume
    nucName : armi nuclide name -- e.g. 'U235'

    Returns
    -------
    number density : float
        number density (#/bn-cm)

    See Also
    --------
    armi.reactor.blocks.Block.setMass
    """
    A = nucDir.getAtomicWeight(nucName)
    try:
        return units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * mass / (volume * A)
    except ZeroDivisionError:
        if mass == 0 and volume == 0:
            return 0

        raise ValueError(
            "Could not calculate number density with input.\nmass : {}\nvolume : {}\natomic weight : {}\n".format(
                mass, volume, A
            )
        )


def getMassInGrams(nucName: str, volume: float, numberDensity: Union[float, None] = None) -> float:
    """
    Gets mass of a nuclide of a known volume and know number density.

    Parameters
    ----------
    nucName
        name of nuclide -- e.g. 'U235'
    volume
        volume in (cm3)
    numberDensity
        number density in (at/bn-cm)

    Returns
    -------
    mass
        mass of nuclide (g)
    """
    if not numberDensity:
        return 0.0
    A = nucDir.getAtomicWeight(nucName)
    return numberDensity * volume * A / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM


def formatMaterialCard(
    densities,
    matNum=0,
    minDens=1e-15,
    sigFigs=8,
    mcnp6Compatible=False,
    mcnpLibrary=None,
):
    """
    Formats nuclides and densities into a MCNP material card.

    .. impl:: Create MCNP material card.
        :id: I_ARMI_UTIL_MCNP_MAT_CARD
        :implements: R_ARMI_UTIL_MCNP_MAT_CARD

        Loops over a vector of nuclides (of type ``nuclideBase``) provided in ``densities`` and formats them into a list
        of strings consistent with MCNP material card syntax, skipping dummy nuclides and LFPs.

        A ``matNum`` may optionally be provided for the created material card: if not provided, it is left blank. The
        desired number of significant figures for the created card can be optionally provided by ``sigFigs``. Nuclides
        whose number density falls below a threshold (optionally specified by ``minDens``) are set to the threshold.

        The boolean ``mcnp6Compatible`` may optionally be provided to include the nuclide library at the end of the
        vector of individual nuclides using the "nlib=" syntax leveraged by MCNP. If this boolean is turned on, the
        associated value ``mcnpLibrary`` should generally also be provided, as otherwise, the library will be left blank
        in the resulting material card string.

    Parameters
    ----------
    densities : dict
        number densities indexed by nuclideBase
    matNum : int
        mcnp material number
    minDens : float
        minimum density
    sigFigs : int
        significant figures for the material card

    Returns
    -------
    mCard : list
        list of material card strings
    """
    if all(isinstance(nuc, (nuclideBases.LumpNuclideBase, nuclideBases.DummyNuclideBase)) for nuc in densities):
        return []  # no valid nuclides to write
    if matNum >= 0:
        mCard = ["m{matNum}\n".format(matNum=matNum)]
    else:
        mCard = ["m{}\n"]

    for nuc, dens in sorted(densities.items()):
        # skip LFPs and Dummies.
        if isinstance(nuc, (nuclideBases.LumpNuclideBase)):
            runLog.important("The material card returned will ignore LFPs.", single=True)
            continue
        elif isinstance(nuc, nuclideBases.DummyNuclideBase):
            runLog.info(f"Omitting dummy nuclides such as {nuc}", single=True)
            continue
        mcnpNucName = nuc.getMcnpId()
        newEntry = ("      {nucName:5d} {ndens:." + str(sigFigs) + "e}\n").format(
            nucName=int(mcnpNucName), ndens=max(dens, minDens)
        )  # 0 dens is invalid
        mCard.append(newEntry)

    if mcnp6Compatible:
        mCard.append("      nlib={lib}c\n".format(lib=mcnpLibrary))

    return mCard


def filterNuclideList(nuclideVector, nuclides):
    """
    Filter out nuclides not in the nuclide vector.

    Parameters
    ----------
    nuclideVector : dict
        dictionary of values indexed by nuclide identifiers -- e.g. nucNames or nuclideBases

    nuclides : list
        list of nuclide identifiers

    Returns
    -------
    nuclideVector : dict
        dictionary of values indexed by nuclide identifiers -- e.g. nucNames or nuclideBases
    """
    if not isinstance(list(nuclideVector.keys())[0], nuclides[0].__class__):
        raise ValueError(
            "nuclide vector is indexed by {} where as the nuclides list is {}".format(
                nuclideVector.keys()[0].__class__, nuclides[0].__class__
            )
        )

    for nucName in list(nuclideVector.keys()):
        if nucName not in nuclides:
            del nuclideVector[nucName]

    return nuclideVector


def normalizeNuclideList(nuclideVector, normalization=1.0):
    """
    Normalize the nuclide vector.

    Parameters
    ----------
    nuclideVector : dict
        dictionary of values -- e.g. floats, ints -- indexed by nuclide identifiers -- e.g. nucNames or nuclideBases
    normalization : float

    Returns
    -------
    nuclideVector : dict
        dictionary of values indexed by nuclide identifiers -- e.g. nucNames or nuclideBases
    """
    normalizationFactor = sum(nuclideVector.values()) / normalization

    for nucName, mFrac in nuclideVector.items():
        nuclideVector[nucName] = mFrac / normalizationFactor

    return nuclideVector


def expandElementalMassFracsToNuclides(
    massFracs: dict,
    elementExpansionPairs: Tuple[elements.Element, List[nuclideBases.NuclideBase]],
):
    """
    Expand elemental mass fractions to natural nuclides.

    Modifies the input ``massFracs`` in place to contain nuclides.

    Notes
    -----
    This indirectly updates number densities through mass fractions.

    .. impl:: Expand mass fractions to nuclides.
        :id: I_ARMI_UTIL_EXP_MASS_FRACS
        :implements: R_ARMI_UTIL_EXP_MASS_FRACS

        Given a vector of elements and nuclides with associated mass fractions (``massFracs``), expands the elements in-
        place into a set of nuclides using ``expandElementalNuclideMassFracs``. Isotopes to expand into are provided for
        each element by specifying them with ``elementExpansionPairs``, which maps each element to a list of particular
        NuclideBases; if left unspecified, all naturally-occurring isotopes are included.

        Explicitly specifying the expansion isotopes provides a way for particular naturally-occurring isotopes to be
        excluded from the expansion, e.g. excluding O-18 from an expansion of elemental oxygen.

    Parameters
    ----------
    massFracs : dict(str, float)
        dictionary of nuclide or element names with mass fractions. Elements will be expanded in place using natural
        isotopics.
    elementExpansionPairs : (Element, [NuclideBase]) pairs
        element objects to expand (from nuclidBase.element) and list of NuclideBases to expand into (or None for all
        natural)
    """
    # expand elements
    for element, isotopicSubset in elementExpansionPairs:
        massFrac = massFracs.pop(element.symbol, None)
        if massFrac is None:
            continue

        expandedNucs = expandElementalNuclideMassFracs(element, massFrac, isotopicSubset)
        massFracs.update(expandedNucs)

        total = sum(expandedNucs.values())
        if massFrac > 0.0 and abs(total - massFrac) / massFrac > 1e-6:
            raise ValueError(f"Mass fractions not normalized properly {(total, massFrac)}!")


def expandElementalNuclideMassFracs(
    element: elements.Element,
    massFrac: float,
    isotopicSubset: List[nuclideBases.NuclideBase] = None,
):
    """
    Return a dictionary of nuclide names to isotopic mass fractions.

    If an isotopic subset is passed in, the mass fractions get scaled up s.t. the total mass fraction remains constant.

    Parameters
    ----------
    element : Element
        The element to expand to natural isotopics
    massFrac : float
        Mass fraction of the initial element
    isotopicSubset : list of NuclideBases
        Natural isotopes to include in the expansion. Useful e.g. for excluding O18 from an expansion of Oxygen.
    """
    elementNucBases = element.getNaturalIsotopics()
    if isotopicSubset:
        expandedNucBases = [nb for nb in elementNucBases if nb in isotopicSubset]
    else:
        expandedNucBases = elementNucBases
    elementalWeightGperMole = sum(nb.weight * nb.abundance for nb in expandedNucBases)
    if not any(expandedNucBases):
        raise ValueError("Cannot expand element `{}` into isotopes: `{}`".format(element, expandedNucBases))
    expanded = {}
    for nb in expandedNucBases:
        expanded[nb.name] = massFrac * nb.abundance * nb.weight / elementalWeightGperMole
    return expanded


def getChemicals(nuclideInventory):
    """
    Groups the inventories of nuclides by their elements.

    Parameters
    ----------
    nuclideInventory : dict
        nuclide inventories indexed by nuc -- either nucNames or nuclideBases

    Returns
    -------
    chemicals : dict
        inventory of elements indexed by element symbol -- e.g. 'U' or 'PU'
    """
    chemicals = {}
    for nuc, N in nuclideInventory.items():
        nb = nuc if isinstance(nuc, nuclideBases.INuclide) else nuclideBases.byName[nuc]

        if nb.element.symbol in chemicals:
            chemicals[nb.element.symbol] += N
        else:
            chemicals[nb.element.symbol] = N

    return chemicals


def applyIsotopicsMix(material, enrichedMassFracs: Dict[str, float], fertileMassFracs: Dict[str, float]):
    """
    Update material heavy metal mass fractions based on its enrichment and two nuclide feeds.

    This will remix the heavy metal in a Material object based on the object's ``class1_wt_frac`` parameter and the
    input nuclide information.

    This can be used for inputting mixtures of two external custom isotopic feeds as well as for fabricating assemblies
    from two  closed-cycle collections of material.

    See Also
    --------
    armi.materials.material.FuelMaterial

    Parameters
    ----------
    material : material.Material
        The object to modify. Must have a ``class1_wt_frac`` param set
    enrichedMassFracs : dict
        Nuclide names and weight fractions of the class 1 nuclides
    fertileMassFracs : dict
        Nuclide names and weight fractions of the class 2 nuclides
    """
    total = sum(material.massFrac.values())
    hm = 0.0
    for nucName, massFrac in material.massFrac.items():
        nb = nuclideBases.byName[nucName]
        if nb.isHeavyMetal():
            hm += massFrac

    hmFrac = hm / total
    hmEnrich = material.class1_wt_frac
    for nucName in (
        set(enrichedMassFracs.keys()).union(set(fertileMassFracs.keys())).union(set(material.massFrac.keys()))
    ):
        nb = nuclideBases.byName[nucName]
        if nb.isHeavyMetal():
            material.massFrac[nucName] = hmFrac * (
                hmEnrich * enrichedMassFracs.get(nucName, 0.0) + (1 - hmEnrich) * fertileMassFracs.get(nucName, 0.0)
            )
