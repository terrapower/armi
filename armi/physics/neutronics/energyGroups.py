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
"""Energy group structures for multigroup neutronics calculations."""

import copy
import itertools
import math

import numpy as np

from armi import runLog
from armi.physics.neutronics.const import (
    FAST_FLUX_THRESHOLD_EV,
    HIGH_ENERGY_EV,
    MAXIMUM_XS_LIBRARY_ENERGY,
    ULTRA_FINE_GROUP_LETHARGY_WIDTH,
)
from armi.utils.mathematics import findNearestValue


def getFastFluxGroupCutoff(eGrpStruc):
    """
    Given a constant "fast" energy threshold, return which ARMI energy group
    index contains this threshold.

    .. impl:: Return the energy group index which contains a given energy threshold.
        :id: I_ARMI_EG_FE
        :implements: R_ARMI_EG_FE

        This function returns the energy group within a given group structure
        that contains the fast flux threshold energy. The threshold energy is
        imported from the :py:mod:`constants <armi.physics.neutronics.const>` in
        the neutronics module, where it is defined as 100 keV. This is a
        standard definition for fast flux. This function also calculates and
        returns the fraction of the threshold energy group that is above the 100
        keV threshold.
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
    Return descending neutron energy group upper bounds in eV for a given
    structure name.

    .. impl:: Provide the neutron energy group bounds for a given group structure.
        :id: I_ARMI_EG_NE
        :implements: R_ARMI_EG_NE

        There are several built-in group structures that are defined in this
        module, which are stored in a dictionary. This function takes a group
        structure name as an input parameter, which it uses as a key for the
        group structure dictionary. If the group structure name is valid, it
        returns a copy of the energy group structure resulting from the
        dictionary lookup. Otherwise, it throws an error.

    Notes
    -----
    Copy of the group structure is return so that modifications of the energy
    bounds does not propagate back to the `GROUP_STRUCTURE` dictionary.
    """
    try:
        return copy.copy(GROUP_STRUCTURE[name])
    except KeyError as ke:
        runLog.error(
            'Could not find groupStructure with the name "{}".\nChoose one of: {}'.format(
                name, ", ".join(GROUP_STRUCTURE.keys())
            )
        )
        raise ke


def getGroupStructureType(neutronEnergyBoundsInEv):
    """Return neutron energy group structure name for a given set of neutron energy group bounds in eV."""
    neutronEnergyBoundsInEv = np.array(neutronEnergyBoundsInEv)
    for groupStructureType in GROUP_STRUCTURE:
        refNeutronEnergyBoundsInEv = np.array(getGroupStructure(groupStructureType))
        if len(refNeutronEnergyBoundsInEv) != len(neutronEnergyBoundsInEv):
            continue
        if np.allclose(refNeutronEnergyBoundsInEv, neutronEnergyBoundsInEv, 1e-5):
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

:meta hide-value:
"""

GROUP_STRUCTURE["2"] = [HIGH_ENERGY_EV, 6.25e-01]

# for calculating fast flux
GROUP_STRUCTURE["FastFlux"] = [HIGH_ENERGY_EV, FAST_FLUX_THRESHOLD_EV]

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

GROUP_STRUCTURE["ANL116"] = _create_anl_energies_with_group_lethargies(
    15*[6] + [3] + 2*[6] + [3] + [12] + 3*[6] + 3*[12] + 2*[6] + 2*[12] + [4] + [6] + [2] +
    [12] + 2*[6] + [12] + 2*[6] +2*[12] + [6] + [12] + 2*[6] + 6*[12] + [6] + 4*[12] + 4*[6] +
    5*[12] + [6] + 3*[12] + [6] + 2*[30] + 2*[15] + [30] + 4*[15] + [18] + [12] + 5*[30] +
    [24] + [12] + [24] + [19] + [11] + [18] + [24] + 3*[18] + 2*[12] + 14*[60] + 2*[30] + [29] + [1]
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
def _create_multigroup_structures_on_finegroup_energies(multigroup_energy_bounds, finegroup_energy_bounds):
    """Set energy group bounds to the nearest ultra-fine group boundaries."""
    modifiedEnergyBounds = set()
    modifiedEnergyBounds.add(max(finegroup_energy_bounds))
    for energyBound in multigroup_energy_bounds[1:]:
        modifiedEnergyBounds.add(findNearestValue(finegroup_energy_bounds, energyBound))

    return sorted(modifiedEnergyBounds, reverse=True)


def _create_anl_energies_with_group_energies(group_energy_bounds):
    """Set energy group bounds to the nearest ultra-fine group boundaries."""
    ufgEnergies = _create_anl_energies_with_group_lethargies(itertools.repeat(1, 2082))
    return _create_multigroup_structures_on_finegroup_energies(group_energy_bounds, ufgEnergies)


"""
Taken from Section A3.1 SHEM-361 in
Ngeleka, Tholakele Prisca. "Examination and improvement of the SHEM energy
group structure for HTR and deep burn HTR design and analysis." (2012).
"""
GROUP_STRUCTURE["SHEM361"] = [
    19640300,
    14918200,
    13840300,
    11618300,
    9999990,
    9048360,
    8187300,
    7408170,
    6703190,
    6065300,
    4965850,
    4065690,
    3328710,
    2725310,
    2231300,
    1901390,
    1636540,
    1405770,
    1336940,
    1286960,
    1162050,
    1051150,
    951119,
    860006,
    706511,
    578443,
    494002,
    456021,
    412501,
    383884,
    320646,
    267826,
    230014,
    195008,
    164999,
    140000,
    122773,
    115624,
    94664.5,
    82297.4,
    67379.4,
    55165.6,
    49915.9,
    40867.7,
    36978.6,
    33459.6,
    29281,
    27394.4,
    26100.1,
    24999.1,
    22699.4,
    18584.7,
    16200.5,
    14899.7,
    13603.7,
    11137.7,
    9118.81,
    7465.85,
    6112.52,
    5004.51,
    4097.35,
    3481.07,
    2996.18,
    2700.24,
    2397.29,
    2084.1,
    1811.83,
    1586.2,
    1343.58,
    1134.67,
    1064.32,
    982.494,
    909.681,
    832.218,
    748.517,
    677.287,
    646.837,
    612.834,
    600.099,
    592.941,
    577.146,
    539.204,
    501.746,
    453.999,
    419.094,
    390.76,
    371.703,
    353.575,
    335.323,
    319.928,
    295.922,
    288.327,
    284.888,
    276.468,
    268.297,
    256.748,
    241.796,
    235.59,
    224.325,
    212.108,
    200.958,
    195.996,
    193.078,
    190.204,
    188.877,
    187.559,
    186.251,
    184.952,
    183.295,
    175.229,
    167.519,
    163.056,
    154.176,
    146.657,
    139.504,
    132.701,
    126.229,
    120.554,
    117.577,
    116.524,
    115.48,
    112.854,
    110.288,
    105.646,
    103.038,
    102.115,
    101.605,
    101.098,
    100.594,
    97.3287,
    93.3256,
    88.7741,
    83.9393,
    79.3679,
    76.3322,
    73.5595,
    71.8869,
    69.0682,
    66.8261,
    66.4929,
    66.1612,
    65.8312,
    65.5029,
    65.046,
    64.5923,
    63.6306,
    62.3083,
    59.925,
    57.0595,
    54.06,
    52.9895,
    51.7847,
    49.2591,
    47.5173,
    46.2053,
    45.2904,
    44.1721,
    43.1246,
    42.1441,
    41.227,
    39.7295,
    38.7874,
    37.7919,
    37.3038,
    36.8588,
    36.4191,
    36.0568,
    35.698,
    34.5392,
    33.0855,
    31.693,
    27.8852,
    24.6578,
    22.5356,
    22.3788,
    22.1557,
    22.0011,
    21.7018,
    21.4859,
    21.336,
    21.2296,
    21.1448,
    21.0604,
    20.9763,
    20.7676,
    20.6847,
    20.6021,
    20.5199,
    20.4175,
    20.2751,
    20.0734,
    19.5974,
    19.3927,
    19.1997,
    19.0848,
    17.9591,
    17.759,
    17.5648,
    17.4457,
    16.8305,
    16.5501,
    16.0498,
    15.7792,
    14.8662,
    14.7301,
    14.5952,
    14.4702,
    14.2505,
    14.0496,
    13.546,
    13.3297,
    12.6,
    12.4721,
    12.3086,
    12.1302,
    11.9795,
    11.8153,
    11.7094,
    11.5894,
    11.2694,
    11.0529,
    10.8038,
    10.5793,
    9.50002,
    9.14031,
    8.97995,
    8.80038,
    8.67369,
    8.52407,
    8.30032,
    8.13027,
    7.97008,
    7.83965,
    7.73994,
    7.60035,
    7.38015,
    7.13987,
    6.99429,
    6.91778,
    6.87021,
    6.83526,
    6.8107,
    6.79165,
    6.77605,
    6.75981,
    6.74225,
    6.71668,
    6.63126,
    6.60611,
    6.58829,
    6.57184,
    6.55609,
    6.53907,
    6.51492,
    6.48178,
    6.43206,
    6.35978,
    6.28016,
    6.16011,
    6.05991,
    5.96014,
    5.80021,
    5.72015,
    5.61979,
    5.53004,
    5.48817,
    5.41025,
    5.38003,
    5.32011,
    5.21008,
    5.10997,
    4.93323,
    4.76785,
    4.4198,
    4.30981,
    4.21983,
    4,
    3.88217,
    3.71209,
    3.54307,
    3.14211,
    2.88405,
    2.77512,
    2.74092,
    2.7199,
    2.70012,
    2.64004,
    2.62005,
    2.59009,
    2.55,
    2.46994,
    2.33006,
    2.27299,
    2.21709,
    2.15695,
    2.0701,
    1.98992,
    1.90008,
    1.77997,
    1.66895,
    1.58803,
    1.51998,
    1.44397,
    1.41001,
    1.38098,
    1.33095,
    1.29304,
    1.25094,
    1.21397,
    1.16999,
    1.14797,
    1.12997,
    1.11605,
    1.10395,
    1.09198,
    1.07799,
    1.03499,
    1.02101,
    1.00904,
    0.996501,
    0.981959,
    0.96396,
    0.944022,
    0.919978,
    0.880024,
    0.800371,
    0.719999,
    0.624999,
    0.594993,
    0.55499,
    0.520011,
    0.475017,
    0.431579,
    0.390001,
    0.352994,
    0.325008,
    0.305012,
    0.279989,
    0.254997,
    0.231192,
    0.20961,
    0.190005,
    0.161895,
    0.137999,
    0.119995,
    0.104298,
    0.0897968,
    0.0764969,
    0.0651999,
    0.0554982,
    0.0473019,
    0.0402999,
    0.0343998,
    0.0292989,
    0.0249394,
    0.0200104,
    0.01483,
    0.0104505,
    0.00714526,
    0.00455602,
    0.0024999,
]

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

# Energy bounds of SHEM33_361 is ANL33 modified to the nearest SHEM361 fine group boundaries
GROUP_STRUCTURE["SHEM33_361"] = _create_multigroup_structures_on_finegroup_energies(
    GROUP_STRUCTURE["ANL33"], GROUP_STRUCTURE["SHEM361"]
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

"""
Taken from Table 5.1 of "GAMSOR: Gamma Source Preparation and DIF3D Flux Solution",
ANL/NE-16/50 Rev 2.0, M.A. Smith, C.H. Lee, R.N. Hill, Aug 30 2022.
"""
GROUP_STRUCTURE["ANL21G"] = [
    2.0e7,
    1.0e7,
    8.0e6,
    7.0e6,
    6.0e6,
    5.0e6,
    4.0e6,
    3.0e6,
    2.5e6,
    2.0e6,
    1.5e6,
    1.0e6,
    7.0e5,
    4.5e5,
    3.0e5,
    1.5e5,
    1.0e5,
    7.5e4,
    4.5e4,
    3.0e4,
    2.0e4,
]

"""
Taken from Table 5.2 of "GAMSOR: Gamma Source Preparation and DIF3D Flux Solution",
ANL/NE-16/50 Rev 2.0, M.A. Smith, C.H. Lee, R.N. Hill, Aug 30 2022.
"""
GROUP_STRUCTURE["ANL94G"] = [
    2.000e07,
    1.400e07,
    1.200e07,
    1.100e07,
    1.060e07,
    1.000e07,
    9.500e06,
    9.000e06,
    8.500e06,
    8.000e06,
    7.750e06,
    7.500e06,
    7.250e06,
    7.000e06,
    6.750e06,
    6.500e06,
    6.250e06,
    6.000e06,
    5.750e06,
    5.500e06,
    5.400e06,
    5.200e06,
    5.000e06,
    4.700e06,
    4.500e06,
    4.400e06,
    4.200e06,
    4.000e06,
    3.900e06,
    3.800e06,
    3.650e06,
    3.500e06,
    3.333e06,
    3.166e06,
    3.000e06,
    2.833e06,
    2.666e06,
    2.500e06,
    2.333e06,
    2.166e06,
    2.000e06,
    1.875e06,
    1.750e06,
    1.660e06,
    1.600e06,
    1.500e06,
    1.420e06,
    1.330e06,
    1.250e06,
    1.200e06,
    1.125e06,
    1.000e06,
    9.000e05,
    8.650e05,
    8.250e05,
    8.000e05,
    7.500e05,
    7.000e05,
    6.750e05,
    6.500e05,
    6.250e05,
    6.000e05,
    5.750e05,
    5.500e05,
    5.250e05,
    5.000e05,
    4.500e05,
    4.250e05,
    4.000e05,
    3.750e05,
    3.500e05,
    3.250e05,
    3.000e05,
    2.600e05,
    2.200e05,
    1.900e05,
    1.600e05,
    1.500e05,
    1.400e05,
    1.200e05,
    1.000e05,
    9.000e04,
    8.000e04,
    7.500e04,
    6.500e04,
    6.000e04,
    5.500e04,
    4.500e04,
    4.000e04,
    3.500e04,
    3.000e04,
    2.000e04,
    1.500e04,
    1.000e04,
]
