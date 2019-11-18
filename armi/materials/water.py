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

# cython: profile=False
import math

from armi.utils.units import getTk
from armi.nucDirectory import elements
from armi.materials.material import Fluid
from armi.utils import units


class Water(Fluid):

    """
    Water
    
    This is a good faith implementation of the Revised Supplementary Properties
    of Ordinary Water Substance (1992) by IAPWS -- International Association for
    the Properties of Water and Steam .
    
    This is an abstract class implemented on the Saturated Water Material Class
    and the Saturated Steam Material Class, which should be good enough for
    most uses.
    
    http://www.iapws.org/relguide/supsat.pdf
    IAPWS-IF97 is now the international standard for calculations in the steam
    power industry
    """

    name = "Water"

    references = {
        "vapor pressure": "IAPWS SR1-86 Revised Supplementary Release on Saturation Properties of Ordinary Water and Steam",
        "enthalpy (saturated water)": "IAPWS SR1-86 Revised Supplementary Release on Saturation Properties of Ordinary Water and Steam",
        "enthalpy (saturated steam)": "IAPWS SR1-86 Revised Supplementary Release on Saturation Properties of Ordinary Water and Steam",
        "entropy (saturated water)": "IAPWS SR1-86 Revised Supplementary Release on Saturation Properties of Ordinary Water and Steam",
        "entropy (saturated steam)": "IAPWS SR1-86 Revised Supplementary Release on Saturation Properties of Ordinary Water and Steam",
        "density (saturated water)": "IAPWS SR1-86 Revised Supplementary Release on Saturation Properties of Ordinary Water and Steam",
        "density (saturated steam)": "IAPWS SR1-86 Revised Supplementary Release on Saturation Properties of Ordinary Water and Steam",
    }

    TEMPERATURE_CRITICAL_K = 647.096

    DENSITY_CRITICAL_KGPERCUBICMETER = 322.0
    DENSITY_CRITICAL_GPERCUBICCENTIMETER = (
        DENSITY_CRITICAL_KGPERCUBICMETER * units.G_PER_KG / units.CM3_PER_M3
    )
    VAPOR_PRESSURE_CRITICAL_MPA = 22.064
    VAPOR_PRESSURE_CRITICAL_PA = VAPOR_PRESSURE_CRITICAL_MPA * 1e6
    ALPHA_0 = 1000
    PHI_0 = ALPHA_0 / TEMPERATURE_CRITICAL_K

    # coefficients for auxiliary quantity for enthalpy and entropy
    # kept as d to match original source
    d = {}
    d["alpha"] = -1135.905627715
    d["phi"] = 2319.5246
    d[1] = -5.65134998e-8
    d[2] = 2690.66631
    d[3] = 127.287297
    d[4] = -135.003439
    d[5] = 0.981825814

    def setDefaultMassFracs(self):
        massHydrogen = elements.bySymbol["H"].standardWeight
        massOxygen = elements.bySymbol["O"].standardWeight
        totalMass = 2 * massHydrogen + massOxygen
        massFrac = {"H": 2.0 * massHydrogen / totalMass, "O": massOxygen / totalMass}
        for nucName, mfrac in massFrac.items():
            self.setMassFrac(nucName, mfrac)

    def theta(self, Tk=None, Tc=None):
        """
        returns temperature normalized to the critical temperature
        """
        return getTk(Tc=Tc, Tk=Tk) / self.TEMPERATURE_CRITICAL_K

    def tau(self, Tc=None, Tk=None):
        """
        returns 1 - temperature normalized to the critical temperature
        
        Note
        ----
        thermophysical correlations are give in Tau rather than Tk or Tc
        """
        return 1.0 - self.theta(Tc=Tc, Tk=Tk)

    def vaporPressure(self, Tk=None, Tc=None):
        """
        Returns vapor pressure in (Pa)
        
        Parameters
        ----------
        Tk: float
            temperature in Kelvin
        Tc: float
            temperature in Celcius
                    
        Returns
        -------
        vaporPressure: float
            vapor pressure in Pa
        
        Notes
        -----
        IAPWS-IF97 
        http://www.iapws.org/relguide/supsat.pdf
        IAPWS-IF97 is now the international standard for calculations in the
        steam power industry
        """

        tau = self.tau(Tc=Tc, Tk=Tk)
        T_ratio = self.TEMPERATURE_CRITICAL_K / getTk(Tc=Tc, Tk=Tk)

        a1 = -7.85951783
        a2 = 1.84408259
        a3 = -11.7866497
        a4 = 22.6807411
        a5 = -15.9618719
        a6 = 1.80122502

        sum_coefficients = (
            a1 * tau
            + a2 * tau ** 1.5
            + a3 * tau ** 3
            + a4 * tau ** 3.5
            + a5 * tau ** 4
            + a6 * tau ** 7.5
        )
        log_vapor_pressure = T_ratio * sum_coefficients
        vapor_pressure = self.VAPOR_PRESSURE_CRITICAL_PA * math.e ** (
            log_vapor_pressure
        )
        # past the supercritical point tau's raised to .5 cause complex #'s
        return vapor_pressure.real

    def vaporPressurePrime(self, Tk=None, Tc=None, dT=1e-6):
        """
        approximation of derivative of vapor pressure wrt temperature
        
        Parameters
        ----------
        Tk: float
            temperature in Kelvin
        Tc: float
            temperature in Celcius
        
        Note
        ----
        this uses a numerical approximation
        """
        Tcold = getTk(Tc=Tc, Tk=Tk) - dT / 2.0
        Thot = Tcold + dT

        dp = self.vaporPressure(Tk=Thot) - self.vaporPressure(Tk=Tcold)
        return dp / dT

    def auxiliaryQuantitySpecificEnthalpy(self, Tk=None, Tc=None):
        """
        Returns the auxiliary quantity for specific enthalpy
        
        Parameters
        ----------
        Tk: float
            temperature in Kelvin
        Tc: float
            temperature in Celcius
        
        Returns
        -------
        alpha: float
            specific quantity for enthalpy in J/kg
        
        Notes
        -----
        IAPWS-IF97 
        http://www.iapws.org/relguide/supsat.pdf
        IAPWS-IF97 is now the international standard for calculations in the
        steam power industry
        
        alpha is used in the relations for enthalpy
        h = alpha + T/pressure*dp/dT
        """
        theta = self.theta(Tc=Tc, Tk=Tk)

        normalized_alpha = (
            self.d["alpha"]
            + self.d[1] * theta ** -19
            + self.d[2] * theta
            + self.d[3] * theta ** 4.5
            + self.d[4] * theta ** 5.0
            + self.d[5] * theta ** 54.5
        )

        # past the supercritical point tau's raised to .5 cause complex #'s
        return normalized_alpha.real * self.ALPHA_0

    def auxiliaryQuantitySpecificEntropy(self, Tk=None, Tc=None):
        """
        Returns the auxiliary quantity for specific entropy
        
        Parameters
        ----------
        Tk: float
            temperature in Kelvin
        Tc: float
            temperature in Celcius
        
        Returns
        -------
        phi: float
            specific quantity for entropy in J/(kgK)
        
        Notes
        -----
        IAPWS-IF97 
        http://www.iapws.org/relguide/supsat.pdf
        IAPWS-IF97 is now the international standard for calculations in the
        steam power industry
        
        alpha is used in the relations for enthalpy
        s = phi + 1/pressure*dp/dT
        """
        theta = self.theta(Tc=Tc, Tk=Tk)

        normalized_phi = (
            self.d["phi"]
            + 19.0 / 20.0 * self.d[1] * theta ** -20.0
            + self.d[2] * math.log(theta)
            + 9.0 / 7.0 * self.d[3] * theta ** 3.5
            + 5.0 / 4.0 * self.d[4] * theta ** 4.0
            + 109.0 / 107.0 * self.d[5] * theta ** 53.5
        )

        # past the supercritical point tau's raised to .5 cause complex #'s
        return normalized_phi.real * self.PHI_0

    def enthalpy(self, Tk=None, Tc=None):
        """
        Returns enthalpy of saturated water
        
        Parameters
        ----------
        Tk: float
            temperature in Kelvin
        Tc: float
            temperature in Celcius
        
        Returns
        -------
        enthalpy: float
            vapor pressure in J/kg
        
        Notes
        -----
        IAPWS-IF97 
        http://www.iapws.org/relguide/supsat.pdf
        IAPWS-IF97 is now the international standard for calculations in the
        steam power industry
        """
        alpha = self.auxiliaryQuantitySpecificEnthalpy(Tc=Tc, Tk=Tk)
        T = getTk(Tc=Tc, Tk=Tk)
        rho = self.densityKgM3(Tc=Tc, Tk=Tk)
        dp_dT = self.vaporPressurePrime(Tc=Tc, Tk=Tk)

        return alpha + T / rho * dp_dT

    def entropy(self, Tk=None, Tc=None):
        """
        Returns entropy of saturated water
        
        Parameters
        ----------
        Tk: float
            temperature in Kelvin
        Tc: float
            temperature in Celcius
        
        Returns
        -------
        entropy: float
            entropy in J/(kgK)
        
        Notes
        -----
        IAPWS-IF97 
        http://www.iapws.org/relguide/supsat.pdf
        IAPWS-IF97 is now the international standard for calculations in the
        steam power industry
        """
        phi = self.auxiliaryQuantitySpecificEntropy(Tc=Tc, Tk=Tk)
        rho = self.densityKgM3(Tc=Tc, Tk=Tk)
        dp_dT = self.vaporPressurePrime(Tc=Tc, Tk=Tk)

        return phi + 1.0 / rho * dp_dT

    def density(self, Tk=None, Tc=None):
        raise NotImplementedError(
            "Please use a concrete instance: SaturatedWater or SaturatedSteam."
        )


class SaturatedWater(Water):

    """
    Saturated Water
    
    This is a good faith implementation of the Revised Supplementary Properties
    of Ordinary Water Substance (1992) by IAPWS -- International Association for
    the Properties of Water and Steam .
    
    This is the Saturated Liquid Water Material Class. For steam look to the
    Saturated  Steam Material Class.
    """

    name = "SaturatedWater"

    def density(self, Tk=None, Tc=None):
        """
        returns density in g/cc
        
        Parameters
        ----------
        Tk: float
            temperature in Kelvin
        Tc: float
            temperature in Celcius
        
        Returns
        -------
        density: float
            density in g/cc
            
        Note
        ----
        IAPWS-IF97 
        http://www.iapws.org/relguide/supsat.pdf
        IAPWS-IF97 is now the international standard for calculations in the steam power industry
        """
        tau = self.tau(Tc=Tc, Tk=Tk)

        b1 = 1.99274064
        b2 = 1.09965342
        b3 = -0.510839303
        b4 = -1.75493479
        b5 = -45.5170352
        b6 = -6.74694450e5

        normalized_rho = (
            1
            + b1 * tau ** (1.0 / 3.0)
            + b2 * tau ** (2.0 / 3.0)
            + b3 * tau ** (5.0 / 3.0)
            + b4 * tau ** (16.0 / 3.0)
            + b5 * tau ** (43.0 / 3.0)
            + b6 * tau ** (111.0 / 3.0)
        )

        # past the supercritical point tau's raised to .5 cause complex #'s
        return normalized_rho.real * self.DENSITY_CRITICAL_GPERCUBICCENTIMETER


class SaturatedSteam(Water):
    """
    Saturated Steam
    
    This is a good faith implementation of the Revised Supplementary Properties
    of Ordinary Water Substance (1992) by IAPWS -- International Association for
    the Properties of Water and Steam .
    
    This is the Saturated Liquid Water Material Class. For steam look to the
    Saturated  Steam Material Class.
    """

    name = "SaturatedSteam"

    def density(self, Tk=None, Tc=None):
        """
        returns density in g/cc
        
        Parameters
        ----------
        Tk: float
            temperature in Kelvin
        Tc: float
            temperature in Celcius
        
        Returns
        -------
        density: float
            density in g/cc
            
        Note
        ----
        IAPWS-IF97 
        http://www.iapws.org/relguide/supsat.pdf
        IAPWS-IF97 is now the international standard for calculations in the steam power industry
        """
        tau = self.tau(Tc=Tc, Tk=Tk)

        c1 = -2.03150240
        c2 = -2.68302940
        c3 = -5.38626492
        c4 = -17.2991605
        c5 = -44.7586581
        c6 = -63.9201063

        log_normalized_rho = (
            c1 * tau ** (2.0 / 6.0)
            + c2 * tau ** (4.0 / 6.0)
            + c3 * tau ** (8.0 / 6.0)
            + c4 * tau ** (18.0 / 6.0)
            + c5 * tau ** (37.0 / 6.0)
            + c6 * tau ** (71.0 / 6.0)
        )

        # past the supercritical point tau's raised to .5 cause complex #'s
        return (
            math.e ** log_normalized_rho.real
            * self.DENSITY_CRITICAL_GPERCUBICCENTIMETER
        )
