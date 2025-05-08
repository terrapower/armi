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
"""The units module contains unit conversion functions and constants."""
import math

import scipy.constants

# Units (misc)
DPA = "dpa"
FIMA = "FIMA"
PERCENT_FIMA = r"%FIMA"
MB = "MB"  # megabytes
MOLES = "mole"
MWD = "MWd"
PASCALS = "Pa"
PERCENT = "%"
UNITLESS = ""
USD = "USD"  # US currency (the dollar)
# Units (angles)
DEGREES = "degrees"
RADIANS = "radians"
# Units (energy)
EV = "eV"
MW = "MW"
WATTS = "W"
# Units (length)
CM = "cm"
METERS = "m"
MICRONS = chr(181) + "m"
# Units (mass)
GRAMS = "g"
KG = "kg"
MT = "MT"
# Units (reactivity)
CENTS = "cents"  # 1/100th of a dollar
DOLLARS = "$"  # (dk/k/k') / beta
PCM = "pcm"
REACTIVITY = chr(916) + "k/k/k'"
# Units (temperature)
DEGC = chr(176) + "C"
DEGK = "K"
# Units (time)
DAYS = "days"
MINUTES = "min"
SECONDS = "s"
YEARS = "yr"

# Unit conversions
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

# Cut-off is taken to be any element/nuclide with an atomic number
# that is greater than Actinium (i.e., the first classified Actinide).
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
ASCII_LETTER_a = 97
ASCII_ZERO = 48
TRACE_NUMBER_DENSITY = 1e-50
MIN_FUEL_HM_MOLES_PER_CC = 1e-10

# More than 10 decimals can create floating point comparison problems in MCNP and DIF3D
FLOAT_DIMENSION_DECIMALS = 8
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


def getTk(Tc=None, Tk=None):
    """
    Return a temperature in Kelvin, given a temperature in Celsius or Kelvin.

    Returns
    -------
    T : float
        temperature in Kelvin

    Raises
    ------
    TypeError
        The temperature was not provided as an int or float.
    """
    if not ((Tc is not None) ^ (Tk is not None)):
        raise ValueError(
            f"Cannot produce T in K from Tc={Tc} and Tk={Tk}. "
            "Please supply a single temperature."
        )
    return float(Tk) if Tk is not None else Tc + C_TO_K


def getTc(Tc=None, Tk=None):
    """
    Return a temperature in Celsius, given a temperature in Celsius or Kelvin.

    Returns
    -------
    T : float
        temperature in Celsius

    Raises
    ------
    TypeError
        The temperature was not provided as an int or float.
    """
    if not ((Tc is not None) ^ (Tk is not None)):
        raise ValueError(
            f"Cannot produce T in C from Tc={Tc} and Tk={Tk}. "
            "Please supply a single temperature."
        )
    return float(Tc) if Tc is not None else Tk - C_TO_K


def getTf(Tc=None, Tk=None):
    """
    Return a temperature in Fahrenheit, given a temperature in Celsius or Kelvin.

    Returns
    -------
    T : float
        temperature in Fahrenheit

    Raises
    ------
    TypeError
        The temperature was not provided as an int or float.
    """
    return 1.8 * getTc(Tc, Tk) + 32.0


def getTemperature(Tc=None, Tk=None, tempUnits=None):
    """
    Returns the temperature in the prescribed temperature units.

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
    "Pa": lambda pa: pa,
    "bar": convertBarToPascal,
    "mmHg": convertMmhgToPascal,
    "atm": convertAtmToPascal,
}


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
    Returns parameters A B C D for a plane in the XY direction.

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
