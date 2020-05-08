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

# pylint: disable=too-many-lines, invalid-name
"""
The units module contains unit conversion functions and constants.
"""
import math
import itertools
import copy

import numpy
import scipy.constants

from armi import utils
from armi import runLog

# Names
DEGC = chr(176) + "C"
MICRONS = chr(181) + "m"
NOT_APPLICABLE = "N/A"
UNITLESS = ""

# conversions
C_TO_K = 273.15
BOLTZMAN_CONSTANT = 8.6173324e-11  # boltzmann constant in MeV/K
AVOGADROS_NUMBER = 6.0221415e23
CM2_PER_BARN = 1.0e-24
MOLES_PER_CC_TO_ATOMS_PER_BARN_CM = AVOGADROS_NUMBER * CM2_PER_BARN
JOULES_PER_MeV = 1.60217646e-13
JOULES_PER_eV = JOULES_PER_MeV * 1.0e-6
SECONDS_PER_MINUTE = 60.0
MINUTES_PER_HOUR = 60.0
HOURS_PER_DAY = 24.0
SECONDS_PER_HOUR = SECONDS_PER_MINUTE * MINUTES_PER_HOUR
SECONDS_PER_DAY = HOURS_PER_DAY * SECONDS_PER_HOUR
DAYS_PER_YEAR = 365.24219  # mean tropical year
SECONDS_PER_YEAR = 31556926.0
GAS_CONSTANT = 8.3144621  # J/mol-K
HEAVY_METAL_CUTOFF_Z = 89
MICRONS_PER_METER = 1.0e6
CM2_PER_M2 = 1.0e4
CM3_PER_M3 = 1.0e6
METERS_PER_CM = 0.01
WATTS_PER_MW = 1.0e6
EV_PER_MEV = 1.0e6
MM_PER_CM = 10.0
G_PER_KG = 1000.0
LITERS_PER_CUBIC_METER = 1000
CC_PER_LITER = CM3_PER_M3 / LITERS_PER_CUBIC_METER
DEG_TO_RAD = 1.0 / 180.0 * math.pi  # Degrees to Radians
RAD_TO_REV = 1.0 / (2 * math.pi)  # Radians to Revolutions
ATOMIC_MASS_CONSTANT_MEV = scipy.constants.physical_constants[
    "atomic mass constant energy equivalent in MeV"
][0]
ABS_REACTIVITY_TO_PCM = 1.0e5
PA_PER_ATM = scipy.constants.atm
PA_PER_MMHG = 133.322368421053
PA_PER_BAR = 100000.0
CURIE_PER_BECQUEREL = 1.0 / 3.7e10
MICROCURIES_PER_BECQUEREL = CURIE_PER_BECQUEREL * 1e-6
G_PER_CM3_TO_KG_PER_M3 = 1000.0

# constants
ASCII_MIN_CHAR = 44  # First char allowed in various FORTRAN inputs
ASCII_LETTER_A = 65
ASCII_LETTER_Z = 90
ASCII_ZERO = 48
TRACE_NUMBER_DENSITY = 1e-50
MIN_FUEL_HM_MOLES_PER_CC = 1e-10

# More than 10 decimals can create floating point comparison problems in MCNP and DIF3D
FLOAT_DIMENSION_DECIMALS = 10
EFFECTIVELY_ZERO = 10.0 ** (-1 * FLOAT_DIMENSION_DECIMALS)

#
# STEFAN_BOLTZMANN_CONSTANT is for constant for radiation heat transfer [W m^-2 K^-4]
#
STEFAN_BOLTZMANN_CONSTANT = 5.67e-8  # W/m^2-K^4

#
# GRAVITY is the acceleration due to gravity at the Earths surface in [m s^-2].
#
GRAVITY = 9.80665

#
# :code:`REYNOLDS_TURBULENT` is the Reynolds number below which a duct flow will exhibit "laminar"
# conditions. Reyonlds numbers greater than :code:`REYNOLDS_TURBULENT` will involve flows that are
# "transitional" or "turbulent".
#
REYNOLDS_LAMINAR = 2100.0

#
# :code:`REYNOLDS_TURBULENT` is the Reynolds number above which a duct flow will exhibit "turbulent"
# conditions. Reynolds numbers lower than :code:`REYNOLDS_TURBULENT` will involve flows that are
# "transitional" or "laminar".
#
REYNOLDS_TURBULENT = 4000.0

#
# FAST_FLUX_THRESHOLD_EV is the energy threshold above which neutrons are considered "fast" [eV]
#
FAST_FLUX_THRESHOLD_EV = 100000.0  # eV

# CROSS SECTION LIBRARY GENERATION CONSTANTS
MAXIMUM_XS_LIBRARY_ENERGY = 1.4190675e7  # eV
ULTRA_FINE_GROUP_LETHARGY_WIDTH = 1.0 / 120.0


def getTk(Tc=None, Tk=None):
    """
    Return a temperature in Kelvin, given a temperature in Celsius or Kelvin

    Returns
    -------
    T : float
        temperature in Kelvin

    Raises
    ------
    TypeError
        The temperature was not provided as an int or float.
    """
    if Tk is not None:
        return float(Tk)
    if Tc is not None:
        return Tc + C_TO_K
    raise TypeError(
        "Cannot produce T in K from Tc={0} and Tk={1}. Please supply a temperature.".format(
            Tc, Tk
        )
    )


def getTc(Tc=None, Tk=None):
    """
    Return a temperature in Celcius, given a temperature in Celsius or Kelvin

    Returns
    -------
    T : float
        temperature in Celsius

    Raises
    ------
    TypeError
        The temperature was not provided as an int or float.
    """
    if Tc is not None:
        return float(Tc)
    if Tk is not None:
        return Tk - C_TO_K
    raise TypeError(
        "Cannot produce T in C from Tc={0} and Tk={1}. Supply a temperature. ".format(
            Tc, Tk
        )
    )


def getTf(Tc=None, Tk=None):
    """
    Return a temperature in Fahrenheit, given a temperature in Celsius or Kelvin

    Returns
    -------
    T : float
        temperature in Fahrenheit

    Raises
    ------
    TypeError
        The temperature was not provided as an int or float.
    """
    if Tc is not None:
        return 9.0 * Tc / 5.0 + 32.0
    if Tk is not None:
        return 9.0 * (Tk - C_TO_K) / 5.0 + 32.0
    raise TypeError(
        "Cannot produce T in F from Tc={0} and Tk={1}. Supply a temperature. ".format(
            Tc, Tk
        )
    )


def getTemperature(Tc=None, Tk=None, tempUnits=None):
    """
    Returns the temperature in the prescribed temperature units

    Parameters
    ----------
    Tc : float
        temperature in Celsius
    Tk : float
        temperature in Kelvin
    tempUnits : str
        a flag for the temperature units of the correlation 'Tk', 'K', 'Kelvin',
        'Tc', 'C', or 'Celsius' are acceptable.

    Returns
    -------
    T : float
        temperature in units defined by the tempUnits flag

    Raises
    ------
    ValueError
        When an invalid tempUnits input is provided.
    """
    if tempUnits in ["Tk", "K", "Kelvin"]:
        return getTk(Tc=Tc, Tk=Tk)
    if tempUnits in ["Tc", "C", "Celsius"]:
        return getTc(Tc=Tc, Tk=Tk)
    raise ValueError("Invalid inputs provided. Check docstring.")


def getTmev(Tc=None, Tk=None):
    Tk = getTk(Tc, Tk)
    return BOLTZMAN_CONSTANT * Tk


def convertPascalToPascal(pascal):
    """Converts pressure from pascal to pascal.

    Parameters
    ----------
    pascal : float
        pressure in pascal

    Returns
    -------
    pascal : float
        pressure in pascal

    Note
    ----
    a function is used so all the calculatePressure function can use a
    consistent algorithm -- including converting pressure to pascal using a
    function

    See Also
    --------
    armi.materials.chlorides.chloride.calculatePressure
    """
    return pascal


def convertMmhgToPascal(mmhg):
    """Converts pressure from mmhg to pascal.

    Parameters
    ----------
    mmhg : float
        pressure in mmhg

    Returns
    -------
    pascal : float
        pressure in pascal
    """
    return mmhg * PA_PER_MMHG


def convertBarToPascal(pBar):
    """Converts pressure from bar to pascal.

    Parameters
    ----------
    pBar : float
        pressure in bar

    Returns
    -------
    pascal : float
        pressure in pascal
    """
    return pBar * PA_PER_BAR


def convertAtmToPascal(pAtm):
    """Converts pressure from atomspheres to pascal.

    Parameters
    ----------
    pAtm : float
        pressure in atomspheres

    Returns
    -------
    pascal : float
        pressure in pascal
    """
    return pAtm * PA_PER_ATM


PRESSURE_CONVERTERS = {
    "Pa": convertPascalToPascal,
    "bar": convertBarToPascal,
    "mmHg": convertMmhgToPascal,
    "atm": convertAtmToPascal,
}


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
    Return neutron energy group bounds in eV for a given structure type.

    Notes
    -----
    Copy of the group structure is return so that modifications of the energy bounds does not propagate back to
    the `GROUP_STRUCTURE` dictionary.
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
    """Return neutron energy group structure type for a given set of neutron energy group bounds in eV."""
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


# LOWEST_ENERGY_EV cannot be zero due to integrating lethargy, and lethargy is undefined at 0.0
# The lowest lower boundary of many group structures such as any WIMS, SCALE or CASMO
# is 1e-5 eV, therefore it is chosen here. This number must be lower than all of the
# defined group structures, and as of this writing the lowest in this module is cinder63 with a
# lowest upper boundary of 5e-3 eV. The chosen 1e-5 eV is rather arbitrary but expected to be low
# enough to  support other group structures. For fast reactors, there will be
# no sensitivity at all to this value since there is no flux in this region.
LOWEST_ENERGY_EV = 1.0e-5


# Highest energy will typically depend on what physics code is being run, but this is
# a decent round number to use.
HIGH_ENERGY_EV = 1.5e07

GROUP_STRUCTURE = {}
"""
Energy groups for use in MC**2 and CINDER.

Values are the upper bound of each energy in eV.
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
# Group structures below hear are derived from MC2-3
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
)  #

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


def sanitizeAngle(theta):
    """
    Returns an angle between 0 and 2pi.

    Parameters
    ----------
    theta : float
        an angle

    Returns
    -------
    theta : float
        an angle between 0 and 2*pi
    """

    if theta < 0:
        theta = theta + (1 + -1 * int(theta / (math.pi * 2.0))) * math.pi * 2.0

    if theta > 2.0 * math.pi:
        theta = theta - int(theta / (math.pi * 2.0)) * math.pi * 2.0

    return theta


def getXYLineParameters(theta, x=0, y=0):
    """
    returns parameters A B C D for a plane in the XY direction

    Parameters
    ----------
    theta : float
        angle above x-axis in radians

    x : float
        x coordinate

    y : float
        y coordinate

    Returns
    -------
    A : float
        line coefficient

    B : float
        line coefficient

    C : float
        line coefficient

    D : float
        line coefficient

    See Also
    --------
    terrapower.physics.neutronics.mcnp.mcnpInterface.getSenseWrtTheta

    Notes
    -----
    the line is in the form of A*x + B*y + C*z - D = 0 -- this corresponds to a MCNP arbitrary line equation
    """

    theta = sanitizeAngle(theta)

    if (
        math.fabs(theta) < 1e-10
        or math.fabs(theta - math.pi) < 1e-10
        or math.fabs(theta - 2.0 * math.pi) < 1e-10
    ):
        # this is a py plane so y is always y
        return 0.0, 1.0, 0.0, y

    if (
        math.fabs(theta - math.pi / 2.0) > 1e-10
        or math.fabs(theta - 3 * math.pi / 2.0) > 1e-10
    ):
        # this is a px plane so x is always x
        return 1.0, 0.0, 0.0, x

    A = -1.0 / math.cos(theta)
    B = 1.0 / math.sin(theta)
    C = 0.0
    D = A * x + B * y

    return A, B, C, D
