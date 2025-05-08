# Copyright 2022 TerraPower, LLC
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

"""Unit tests for air materials."""

import math
import unittest

from armi.materials.air import Air
from armi.utils import densityTools

"""
Reference thermal physical properties from Table A.4 in Incropera, Frank P.,
et al. Fundamentals of heat and mass transfer. Vol. 5. New York: Wiley, 2002.
"""

REFERENCE_Tk = [
    100,
    150,
    200,
    250,
    300,
    350,
    400,
    450,
    500,
    550,
    600,
    650,
    700,
    750,
    800,
    850,
    900,
    950,
    1000,
    1100,
    1200,
    1300,
    1400,
    1500,
    1600,
    1700,
    1800,
    1900,
    2000,
    2100,
    2200,
    2300,
    2400,
    2500,
    3000,
]

REFERENCE_DENSITY_KG_PER_M3 = [
    3.5562,
    2.3364,
    1.7458,
    1.3947,
    1.1614,
    0.995,
    0.8711,
    0.774,
    0.6964,
    0.6329,
    0.5804,
    0.5356,
    0.4972,
    0.4643,
    0.4354,
    0.4097,
    0.3868,
    0.3666,
    0.3482,
    0.3166,
    0.2902,
    0.2679,
    0.2488,
    0.2322,
    0.2177,
    0.2049,
    0.1935,
    0.1833,
    0.1741,
    0.1658,
    0.1582,
    0.1513,
    0.1448,
    0.1389,
    0.1135,
]

REFERENCE_HEAT_CAPACITY_kJ_PER_KG_K = [
    1.032,
    1.012,
    1.007,
    1.006,
    1.007,
    1.009,
    1.014,
    1.021,
    1.03,
    1.04,
    1.051,
    1.063,
    1.075,
    1.087,
    1.099,
    1.11,
    1.121,
    1.131,
    1.141,
    1.159,
    1.175,
    1.189,
    1.207,
    1.23,
    1.248,
    1.267,
    1.286,
    1.307,
    1.337,
    1.372,
    1.417,
    1.478,
    1.558,
    1.665,
    2.726,
]

REFERENCE_THERMAL_CONDUCTIVITY_mJ_PER_M_K = [
    9.34,
    13.8,
    18.1,
    22.3,
    26.3,
    30,
    33.8,
    37.3,
    40.7,
    43.9,
    46.9,
    49.7,
    52.4,
    54.9,
    57.3,
    59.6,
    62,
    64.3,
    66.7,
    71.5,
    76.3,
    82,
    91,
    100,
    106,
    113,
    120,
    128,
    137,
    147,
    160,
    175,
    196,
    222,
]


class Test_Air(unittest.TestCase):
    """unit tests for air materials.

    .. test:: There is a base class for fluid materials.
        :id: T_ARMI_MAT_FLUID1
        :tests: R_ARMI_MAT_FLUID
    """

    def test_pseudoDensity(self):
        """
        Reproduce verification results at 300K from Incropera, Frank P., et al.
        Fundamentals of heat and mass transfer. Vol. 5. New York: Wiley, 2002.
        """
        air = Air()

        for Tk, densKgPerM3 in zip(REFERENCE_Tk, REFERENCE_DENSITY_KG_PER_M3):
            if Tk < 2400:
                error = math.fabs(
                    (air.pseudoDensityKgM3(Tk=Tk) - densKgPerM3) / densKgPerM3
                )
                self.assertLess(error, 1e-2)

    def test_heatCapacity(self):
        """
        Reproduce verification results at 300K from Incropera, Frank P., et al.
        Fundamentals of heat and mass transfer. Vol. 5. New York: Wiley, 2002.
        """
        air = Air()

        for Tk, heatCapacity in zip(REFERENCE_Tk, REFERENCE_HEAT_CAPACITY_kJ_PER_KG_K):
            if Tk < 1300:
                error = math.fabs(
                    (air.heatCapacity(Tk=Tk) - heatCapacity * 1e3)
                    / (heatCapacity * 1e3)
                )
                self.assertLess(error, 1e-2)

    def test_thermalConductivity(self):
        """
        Reproduce verification results at 300K from Incropera, Frank P., et al.
        Fundamentals of heat and mass transfer. Vol. 5. New York: Wiley, 2002.
        """
        air = Air()

        for Tk, thermalConductivity in zip(
            REFERENCE_Tk, REFERENCE_THERMAL_CONDUCTIVITY_mJ_PER_M_K
        ):
            if Tk > 200 and Tk < 850:
                error = math.fabs(
                    (air.thermalConductivity(Tk=Tk) - thermalConductivity * 1e-3)
                    / (thermalConductivity * 1e-3)
                )
                self.assertLess(error, 1e-2)

    def test_massFrac(self):
        """Reproduce the number ratios results to PNNL-15870 Rev 1."""
        air = Air()

        refC = 0.000150
        refN = 0.784431
        refO = 0.210748
        refAR = 0.004671

        nDens = densityTools.getNDensFromMasses(air.pseudoDensity(Tk=300), air.massFrac)

        error = math.fabs(nDens["C"] / sum(nDens.values()) - refC)
        self.assertLess(error, 1e-4)
        error = math.fabs(nDens["N"] / sum(nDens.values()) - refN)
        self.assertLess(error, 1e-4)
        error = math.fabs(nDens["O"] / sum(nDens.values()) - refO)
        self.assertLess(error, 1e-4)
        error = math.fabs(nDens["AR"] / sum(nDens.values()) - refAR)
        self.assertLess(error, 1e-4)

    def test_validRanges(self):
        air = Air()

        den0 = air.density(Tk=101)
        denf = air.density(Tk=2399)
        self.assertLess(denf, den0)

        hc0 = air.heatCapacity(Tk=101)
        hcf = air.heatCapacity(Tk=1299)
        self.assertGreater(hcf, hc0)

        tc0 = air.thermalConductivity(Tk=201)
        tcf = air.thermalConductivity(Tk=849)
        self.assertGreater(tcf, tc0)
