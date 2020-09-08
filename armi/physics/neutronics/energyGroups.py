"""
Energy group structures for multigroup neutronics calculations.
"""

import itertools
import copy
import math

import numpy

from armi import utils
from armi import runLog
from .const import (
    FAST_FLUX_THRESHOLD_EV,
    MAXIMUM_XS_LIBRARY_ENERGY,
    ULTRA_FINE_GROUP_LETHARGY_WIDTH,
    HIGH_ENERGY_EV,
)


def getFastFluxGroupCutoff(eGrpStruc):
    """
    Given a constant "fast" energy threshold, return which ARMI energy group index contains this threshold.
    """

    gThres = -1
    for g, eV in enumerate(eGrpStruc):
        if eV < FAST_FLUX_THRESHOLD_EV:
            gThres = g
            break

    dE = eGrpStruc[gThres - 1] - eGrpStruc[gThres]  # eV
    fastFluxFracInG = (eGrpStruc[gThres - 1] - FAST_FLUX_THRESHOLD_EV) / dE

    return gThres - 1, fastFluxFracInG


def _flatten(*numbers):
    result = []
    for item in numbers:
        if isinstance(item, int):
            result.append(item)
        else:
            result.extend(item)
    return result


def _create_anl_energies_with_group_lethargies(*group_lethargies):
    anl_energy_max = MAXIMUM_XS_LIBRARY_ENERGY
    en = anl_energy_max
    energies = []
    for ee in _flatten(*group_lethargies):
        energies.append(en)
        en *= math.e ** (-ee * ULTRA_FINE_GROUP_LETHARGY_WIDTH)
    return energies


def getGroupStructure(name):
    """
    Return descending neutron energy group upper bounds in eV for a given structure name.

    Notes
    -----
    Copy of the group structure is return so that modifications of the energy bounds does 
    not propagate back to the `GROUP_STRUCTURE` dictionary.
    """
    try:
        return copy.copy(GROUP_STRUCTURE[name])
    except KeyError as ke:
        runLog.error(
            'Could not find groupStructure with the name "{}".\n'
            "Choose one of: {}".format(name, ", ".join(GROUP_STRUCTURE.keys()))
        )
        raise ke


def getGroupStructureType(neutronEnergyBoundsInEv):
    """
    Return neutron energy group structure name for a given set of neutron energy group bounds in eV.
    """
    neutronEnergyBoundsInEv = numpy.array(neutronEnergyBoundsInEv)
    for groupStructureType in GROUP_STRUCTURE:
        refNeutronEnergyBoundsInEv = numpy.array(getGroupStructure(groupStructureType))
        if len(refNeutronEnergyBoundsInEv) != len(neutronEnergyBoundsInEv):
            continue
        if numpy.allclose(refNeutronEnergyBoundsInEv, neutronEnergyBoundsInEv, 1e-5):
            return groupStructureType
    raise ValueError(
        "Neutron energy group structure type does not exist for the given neutron energy bounds: {}".format(
            neutronEnergyBoundsInEv
        )
    )


GROUP_STRUCTURE = {}
"""
Energy groups for use in multigroup neutronics.

Values are the upper bound of each energy in eV from highest energy to lowest
(because neutrons typically downscatter...)
"""

GROUP_STRUCTURE["2"] = [HIGH_ENERGY_EV, 6.25e-01]

# Nuclear Reactor Engineering: Reactor Systems Engineering, Vol. 1
GROUP_STRUCTURE["4gGlasstoneSesonske"] = [HIGH_ENERGY_EV, 5.00e04, 5.00e02, 6.25e-01]

# http://serpent.vtt.fi/mediawiki/index.php/CASMO_4-group_structure
GROUP_STRUCTURE["CASMO4"] = [HIGH_ENERGY_EV, 8.21e05, 5.53e03, 6.25e-01]


GROUP_STRUCTURE["CASMO12"] = [
    HIGH_ENERGY_EV,
    2.23e06,
    8.21e05,
    5.53e03,
    4.81e01,
    4.00e00,
    6.25e-01,
    3.50e-01,
    2.80e-01,
    1.40e-01,
    5.80e-02,
    3.00e-02,
]


# For typically for use with MCNP will need conversion to MeV,
# and ordering from low to high.
GROUP_STRUCTURE["CINDER63"] = [
    2.5000e07,
    2.0000e07,
    1.6905e07,
    1.4918e07,
    1.0000e07,
    6.0650e06,
    4.9658e06,
    3.6788e06,
    2.8651e06,
    2.2313e06,
    1.7377e06,
    1.3534e06,
    1.1080e06,
    8.2085e05,
    6.3928e05,
    4.9790e05,
    3.8870e05,
    3.0200e05,
    1.8320e05,
    1.1110e05,
    6.7380e04,
    4.0870e04,
    2.5540e04,
    1.9890e04,
    1.5030e04,
    9.1190e03,
    5.5310e03,
    3.3550e03,
    2.8400e03,
    2.4040e03,
    2.0350e03,
    1.2340e03,
    7.4850e02,
    4.5400e02,
    2.7540e02,
    1.6700e02,
    1.0130e02,
    6.1440e01,
    3.7270e01,
    2.2600e01,
    1.3710e01,
    8.3150e00,
    5.0430e00,
    3.0590e00,
    1.8550e00,
    1.1250e00,
    6.8300e-01,
    4.1400e-01,
    2.5100e-01,
    1.5200e-01,
    1.0000e-01,
    8.0000e-02,
    6.7000e-02,
    5.8000e-02,
    5.0000e-02,
    4.2000e-02,
    3.5000e-02,
    3.0000e-02,
    2.5000e-02,
    2.0000e-02,
    1.5000e-02,
    1.0000e-02,
    5.0000e-03,
]

# fmt: off
# Group structures below here are derived from Appendix E in 
# https://www.osti.gov/biblio/1483949-mc2-multigroup-cross-section-generation-code-fast-reactor-analysis-nuclear
GROUP_STRUCTURE["ANL9"] = _create_anl_energies_with_group_lethargies(
    222, 120, itertools.repeat(180, 5), 540, 300
)

GROUP_STRUCTURE["ANL33"] = _create_anl_energies_with_group_lethargies(
    42, itertools.repeat(60, 28), 90, 240, 29, 1
)

GROUP_STRUCTURE["ANL70"] = _create_anl_energies_with_group_lethargies(
    42, itertools.repeat(30, 67), 29, 1
)

GROUP_STRUCTURE["ANL230"] = _create_anl_energies_with_group_lethargies(
    [
         3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,
         3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  1,  1,  1,  3,  3,  3,  3,  3,
         6,  6,  6,  3,  3,  3,  3,  6,  6,  6,  6,  6,  6,  3,  3,  3,  3,  6,  6,
         6,  6,  2,  2,  1,  1,  2,  2,  2,  6,  6,  3,  3,  3,  3,  6,  6,  3,  3,
         3,  3,  6,  6,  6,  6,  3,  3,  6,  6,  6,  3,  2,  1,  6,  6,  6,  6,  6,
         6,  6,  6,  6,  6,  6,  3,  3,  3,  3,  6,  6,  6,  6,  6,  6,  6,  6,  6,
         3,  3,  3,  3,  3,  3,  6,  6,  6,  6,  6,  6,  6,  6,  6,  3,  3,  3,  3,
         6,  6,  6,  6,  6,  6,  6, 15, 15, 15, 15,  9,  6,  6,  9, 15, 15, 15,  3,
         3,  9, 15,  9,  6,  3,  3,  9,  3, 12, 15, 15, 15, 15, 15, 15, 15, 15, 15,
        15, 12, 12,  6,  6, 12, 12, 12,  7,  5,  6,  6, 12, 12, 12, 12,  6,  6, 12,
        12,  6,  6,  6,  6,  6, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30,
        30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30,  6, 24, 10, 20,
        29,  1,
    ]
)

# Reactor agnostic. Similar to ANL1041 but with 6 UFGs grouped together.
# More likely to not error out on memory than 703
GROUP_STRUCTURE["348"] = _create_anl_energies_with_group_lethargies(
    itertools.repeat(6, 346), 5, 1
)

# Note that at one point the MC2 manual was inconsistent with the code itself
GROUP_STRUCTURE["ANL703"] = _create_anl_energies_with_group_lethargies(
    [
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2, 2, 1, 1, 2, 2,
        2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 2, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 1, 3, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        3, 3, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 3, 3, 3, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2,
        1,
    ]
)

GROUP_STRUCTURE["ANL1041"] = _create_anl_energies_with_group_lethargies(
    itertools.repeat(2, 1041)
)

GROUP_STRUCTURE["ANL2082"] = _create_anl_energies_with_group_lethargies(
    itertools.repeat(1, 2082)
)

# fmt: on
def _create_anl_energies_with_group_energies(group_energy_bounds):
    """Set energy group bounds to the nearest ultra-fine group boundaries."""
    ufgEnergies = _create_anl_energies_with_group_lethargies(itertools.repeat(1, 2082))
    modifiedEnergyBounds = []
    for energyBound in group_energy_bounds:
        modifiedEnergyBounds.append(utils.findNearestValue(ufgEnergies, energyBound))
    return modifiedEnergyBounds


# Energy bounds of ARMI33 and ARMI45 are modified to the nearest ultra-fine group boundaries
GROUP_STRUCTURE["ARMI33"] = _create_anl_energies_with_group_energies(
    [
        1.4190e07,
        1.0000e07,
        6.0650e06,
        3.6780e06,
        2.2313e06,
        1.3530e06,
        8.2080e05,
        4.9787e05,
        3.0190e05,
        1.8310e05,
        1.1109e05,
        6.7370e04,
        4.0860e04,
        2.4788e04,
        1.5030e04,
        9.1180e03,
        5.5308e03,
        3.3540e03,
        2.0340e03,
        1.2341e03,
        7.4850e02,
        4.5390e02,
        3.0432e02,
        1.4860e02,
        9.1660e01,
        6.7904e01,
        4.0160e01,
        2.2600e01,
        1.3709e01,
        8.3150e00,
        4.0000e00,
        5.4000e-01,
        4.1400e-01,
    ]
)

GROUP_STRUCTURE["ARMI45"] = _create_anl_energies_with_group_energies(
    [
        1.419e07,
        1.000e07,
        6.065e06,
        4.966e06,
        3.679e06,
        2.865e06,
        2.231e06,
        1.738e06,
        1.353e06,
        1.108e06,
        8.209e05,
        6.393e05,
        4.979e05,
        3.887e05,
        3.020e05,
        1.832e05,
        1.111e05,
        6.738e04,
        4.087e04,
        2.554e04,
        1.989e04,
        1.503e04,
        9.119e03,
        5.531e03,
        3.355e03,
        2.840e03,
        2.404e03,
        2.035e03,
        1.234e03,
        7.485e02,
        4.540e02,
        2.754e02,
        1.670e02,
        1.013e02,
        6.144e01,
        3.727e01,
        2.260e01,
        1.371e01,
        8.315e00,
        5.043e00,
        3.059e00,
        1.855e00,
        1.125e00,
        6.830e-01,
        4.140e-01,
    ]
)
