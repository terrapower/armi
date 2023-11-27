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

"""Unit tests for water materials."""
import unittest

from armi.materials.water import SaturatedWater, SaturatedSteam, Water


class Test_Water(unittest.TestCase):
    """Unit tests for water materials."""

    def test_water_at_freezing(self):
        """
        Reproduce verification results from IAPWS-IF97 for water at 0C.

        http://www.iapws.org/relguide/supsat.pdf

        .. test:: There is a base class for fluid materials.
            :id: T_ARMI_MAT_FLUID0
            :tests: R_ARMI_MAT_FLUID
        """
        water = SaturatedWater()
        steam = SaturatedSteam()

        Tk = 273.16
        ref_vapor_pressure = 611.657
        ref_dp_dT = 44.436693
        ref_saturated_water_rho = 999.789
        ref_saturated_steam_rho = 0.00485426
        ref_alpha = -11.529101
        ref_saturated_water_enthalpy = 0.611786
        ref_saturated_steam_enthalpy = 2500.5e3
        ref_phi = -0.04
        ref_saturated_water_entropy = 0
        ref_saturated_steam_entropy = 9.154e3

        self.assertAlmostEqual(ref_vapor_pressure, water.vaporPressure(Tk=Tk), 3)
        self.assertAlmostEqual(ref_vapor_pressure, steam.vaporPressure(Tk=Tk), 3)

        self.assertAlmostEqual(ref_dp_dT, water.vaporPressurePrime(Tk=Tk), 3)
        self.assertAlmostEqual(ref_dp_dT, steam.vaporPressurePrime(Tk=Tk), 3)

        self.assertAlmostEqual(
            ref_saturated_water_rho, water.pseudoDensityKgM3(Tk=Tk), 0
        )
        self.assertAlmostEqual(
            ref_saturated_steam_rho, steam.pseudoDensityKgM3(Tk=Tk), 0
        )

        self.assertAlmostEqual(
            ref_alpha, water.auxiliaryQuantitySpecificEnthalpy(Tk=Tk), 3
        )
        self.assertAlmostEqual(
            ref_alpha, steam.auxiliaryQuantitySpecificEnthalpy(Tk=Tk), 3
        )

        self.assertAlmostEqual(ref_saturated_water_enthalpy, water.enthalpy(Tk=Tk), 2)
        self.assertAlmostEqual(
            ref_saturated_steam_enthalpy / steam.enthalpy(Tk=Tk), 1, 2
        )

        self.assertAlmostEqual(
            ref_phi, water.auxiliaryQuantitySpecificEntropy(Tk=Tk), 2
        )
        self.assertAlmostEqual(
            ref_phi, steam.auxiliaryQuantitySpecificEntropy(Tk=Tk), 2
        )

        self.assertAlmostEqual(ref_saturated_water_entropy, water.entropy(Tk=Tk), 3)
        self.assertAlmostEqual(ref_saturated_steam_entropy / steam.entropy(Tk=Tk), 1, 3)

    def test_water_at_boiling(self):
        """
        Reproduce verification results from IAPWS-IF97 for water at 100C.

        http://www.iapws.org/relguide/supsat.pdf
        """
        water = SaturatedWater()
        steam = SaturatedSteam()

        Tk = 373.1243
        ref_vapor_pressure = 0.101325e6
        ref_dp_dT = 3.616e3
        ref_saturated_water_rho = 958.365
        ref_saturated_steam_rho = 0.597586
        ref_alpha = 417.65e3
        ref_saturated_water_enthalpy = 417.05e3
        ref_saturated_steam_enthalpy = 2675.7e3
        ref_phi = 1.303e3
        ref_saturated_water_entropy = 1.307e3
        ref_saturated_steam_entropy = 7.355e3

        self.assertAlmostEqual(ref_vapor_pressure / water.vaporPressure(Tk=Tk), 1, 3)
        self.assertAlmostEqual(ref_vapor_pressure / steam.vaporPressure(Tk=Tk), 1, 3)

        self.assertAlmostEqual(ref_dp_dT / water.vaporPressurePrime(Tk=Tk), 1, 3)
        self.assertAlmostEqual(ref_dp_dT / steam.vaporPressurePrime(Tk=Tk), 1, 3)

        self.assertAlmostEqual(
            ref_saturated_water_rho, water.pseudoDensityKgM3(Tk=Tk), 0
        )
        self.assertAlmostEqual(
            ref_saturated_steam_rho, steam.pseudoDensityKgM3(Tk=Tk), 0
        )

        self.assertAlmostEqual(
            ref_alpha / water.auxiliaryQuantitySpecificEnthalpy(Tk=Tk), 1, 3
        )
        self.assertAlmostEqual(
            ref_alpha / steam.auxiliaryQuantitySpecificEnthalpy(Tk=Tk), 1, 3
        )

        self.assertAlmostEqual(
            ref_saturated_water_enthalpy / water.enthalpy(Tk=Tk), 1, 2
        )
        self.assertAlmostEqual(
            ref_saturated_steam_enthalpy / steam.enthalpy(Tk=Tk), 1, 2
        )

        self.assertAlmostEqual(
            ref_phi / water.auxiliaryQuantitySpecificEntropy(Tk=Tk), 1, 3
        )
        self.assertAlmostEqual(
            ref_phi / steam.auxiliaryQuantitySpecificEntropy(Tk=Tk), 1, 3
        )

        self.assertAlmostEqual(ref_saturated_water_entropy / water.entropy(Tk=Tk), 1, 3)
        self.assertAlmostEqual(ref_saturated_steam_entropy / steam.entropy(Tk=Tk), 1, 3)

    def test_water_at_critcalPoint(self):
        """
        Reproduce verification results from IAPWS-IF97 for water at 647.096K.

        http://www.iapws.org/relguide/supsat.pdf
        """
        water = SaturatedWater()
        steam = SaturatedSteam()

        Tk = 647.096
        ref_vapor_pressure = 22.064e6
        ref_dp_dT = 268e3
        ref_saturated_water_rho = 322
        ref_saturated_steam_rho = 322
        ref_alpha = 1548e3
        ref_saturated_water_enthalpy = 2086.6e3
        ref_saturated_steam_enthalpy = 2086.6e3
        ref_phi = 3.578e3
        ref_saturated_water_entropy = 4.410e3
        ref_saturated_steam_entropy = 4.410e3

        self.assertAlmostEqual(ref_vapor_pressure / water.vaporPressure(Tk=Tk), 1, 3)
        self.assertAlmostEqual(ref_vapor_pressure / steam.vaporPressure(Tk=Tk), 1, 3)

        self.assertAlmostEqual(ref_dp_dT / water.vaporPressurePrime(Tk=Tk), 1, 3)
        self.assertAlmostEqual(ref_dp_dT / steam.vaporPressurePrime(Tk=Tk), 1, 3)

        self.assertAlmostEqual(
            ref_saturated_water_rho, water.pseudoDensityKgM3(Tk=Tk), 0
        )
        self.assertAlmostEqual(
            ref_saturated_steam_rho, steam.pseudoDensityKgM3(Tk=Tk), 0
        )

        self.assertAlmostEqual(
            ref_alpha / water.auxiliaryQuantitySpecificEnthalpy(Tk=Tk), 1, 3
        )
        self.assertAlmostEqual(
            ref_alpha / steam.auxiliaryQuantitySpecificEnthalpy(Tk=Tk), 1, 3
        )

        self.assertAlmostEqual(
            ref_saturated_water_enthalpy / water.enthalpy(Tk=Tk), 1, 2
        )
        self.assertAlmostEqual(
            ref_saturated_steam_enthalpy / steam.enthalpy(Tk=Tk), 1, 2
        )

        self.assertAlmostEqual(
            ref_phi / water.auxiliaryQuantitySpecificEntropy(Tk=Tk), 1, 3
        )
        self.assertAlmostEqual(
            ref_phi / steam.auxiliaryQuantitySpecificEntropy(Tk=Tk), 1, 3
        )

        self.assertAlmostEqual(ref_saturated_water_entropy / water.entropy(Tk=Tk), 1, 3)
        self.assertAlmostEqual(ref_saturated_steam_entropy / steam.entropy(Tk=Tk), 1, 3)

    def test_massFrac(self):
        for water in [SaturatedWater(), SaturatedSteam()]:
            massFracO = water.getMassFrac("O")
            massFracH = water.getMassFrac("H")
            self.assertAlmostEqual(massFracO, 0.888, places=3)
            self.assertAlmostEqual(massFracO + massFracH, 1.0)

    def test_propertyValidTemperature(self):
        water = SaturatedWater()
        self.assertEqual(len(water.propertyValidTemperature), 0)

        steam = SaturatedSteam()
        self.assertEqual(len(steam.propertyValidTemperature), 0)

    def test_validateNames(self):
        water = Water()
        self.assertEqual(water.name, "Water")

        sat = SaturatedWater()
        self.assertEqual(sat.name, "SaturatedWater")

        steam = SaturatedSteam()
        self.assertEqual(steam.name, "SaturatedSteam")
